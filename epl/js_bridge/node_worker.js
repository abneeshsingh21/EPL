/**
 * EPL JavaScript/TypeScript Bridge — Node.js Worker
 *
 * A persistent Node.js subprocess that handles JSON-RPC requests over stdin/stdout.
 * Supports module loading (require), method calls, property access, and property setting.
 * Complex JS objects are tracked via an opaque handle registry.
 *
 * Protocol: Newline-delimited JSON
 *   Request:  {"id": 1, "action": "require", "module": "path"}
 *   Response: {"id": 1, "ok": true, "result": {"type": "handle", "handle": "h1", "typeName": "object"}}
 */

const readline = require('readline');

// ─── Handle Registry ─────────────────────────────────────
let nextHandle = 1;
const handles = new Map();

function storeHandle(obj) {
    const id = 'h' + (nextHandle++);
    handles.set(id, obj);
    return id;
}

// ─── Serialization ───────────────────────────────────────

function serialize(value) {
    if (value === null || value === undefined) {
        return { type: 'null', value: null };
    }
    if (typeof value === 'boolean') {
        return { type: 'boolean', value: value };
    }
    if (typeof value === 'number') {
        return { type: 'number', value: value };
    }
    if (typeof value === 'string') {
        return { type: 'string', value: value };
    }
    if (Array.isArray(value)) {
        return { type: 'array', value: value.map(serialize) };
    }
    if (typeof value === 'function') {
        const h = storeHandle(value);
        return { type: 'handle', handle: h, typeName: 'Function' };
    }
    if (typeof value === 'object') {
        // Check if it's a "simple" plain object we can serialize directly
        const proto = Object.getPrototypeOf(value);
        if (proto === Object.prototype || proto === null) {
            try {
                const result = {};
                for (const key of Object.keys(value)) {
                    result[key] = serialize(value[key]);
                }
                return { type: 'object', value: result };
            } catch (e) {
                // If serialization fails, fall through to handle
            }
        }
        // Complex object — store as handle
        const h = storeHandle(value);
        const typeName = value.constructor ? value.constructor.name : 'Object';
        return { type: 'handle', handle: h, typeName: typeName };
    }
    // Fallback
    return { type: 'string', value: String(value) };
}

function deserialize(data) {
    if (!data || !data.type) return data;
    switch (data.type) {
        case 'null':    return null;
        case 'boolean': return data.value;
        case 'number':  return data.value;
        case 'string':  return data.value;
        case 'handle':  return handles.get(data.handle);
        case 'array':   return (data.value || []).map(deserialize);
        case 'object': {
            const result = {};
            for (const [k, v] of Object.entries(data.value || {})) {
                result[k] = deserialize(v);
            }
            return result;
        }
        default: return data.value;
    }
}

// ─── Request Handlers ────────────────────────────────────

function handleRequire(msg) {
    try {
        const mod = require(msg.module);
        const h = storeHandle(mod);
        const typeName = typeof mod === 'function' ? 'Function' :
                         typeof mod === 'object' ? 'Module' : typeof mod;
        return { id: msg.id, ok: true, result: { type: 'handle', handle: h, typeName: typeName } };
    } catch (e) {
        return { id: msg.id, ok: false, error: `Cannot load module "${msg.module}": ${e.message}` };
    }
}

function handleCall(msg) {
    try {
        const obj = handles.get(msg.handle);
        if (!obj) return { id: msg.id, ok: false, error: `Invalid handle: ${msg.handle}` };

        const method = obj[msg.method];
        if (typeof method !== 'function') {
            return { id: msg.id, ok: false, error: `"${msg.method}" is not a function on this object.` };
        }

        const args = (msg.args || []).map(deserialize);
        const result = method.apply(obj, args);

        // Handle promises
        if (result && typeof result.then === 'function') {
            return result.then(val => ({
                id: msg.id, ok: true, result: serialize(val)
            })).catch(err => ({
                id: msg.id, ok: false, error: err.message || String(err)
            }));
        }

        return { id: msg.id, ok: true, result: serialize(result) };
    } catch (e) {
        return { id: msg.id, ok: false, error: e.message || String(e) };
    }
}

function handleGet(msg) {
    try {
        const obj = handles.get(msg.handle);
        if (!obj) return { id: msg.id, ok: false, error: `Invalid handle: ${msg.handle}` };

        const value = obj[msg.prop];
        return { id: msg.id, ok: true, result: serialize(value) };
    } catch (e) {
        return { id: msg.id, ok: false, error: e.message || String(e) };
    }
}

function handleSet(msg) {
    try {
        const obj = handles.get(msg.handle);
        if (!obj) return { id: msg.id, ok: false, error: `Invalid handle: ${msg.handle}` };

        obj[msg.prop] = deserialize(msg.value);
        return { id: msg.id, ok: true, result: { type: 'null', value: null } };
    } catch (e) {
        return { id: msg.id, ok: false, error: e.message || String(e) };
    }
}

function handleCallDirect(msg) {
    try {
        const fn = handles.get(msg.handle);
        if (typeof fn !== 'function') {
            return { id: msg.id, ok: false, error: `Handle ${msg.handle} is not callable.` };
        }

        const args = (msg.args || []).map(deserialize);
        const result = fn(...args);

        if (result && typeof result.then === 'function') {
            return result.then(val => ({
                id: msg.id, ok: true, result: serialize(val)
            })).catch(err => ({
                id: msg.id, ok: false, error: err.message || String(err)
            }));
        }

        return { id: msg.id, ok: true, result: serialize(result) };
    } catch (e) {
        return { id: msg.id, ok: false, error: e.message || String(e) };
    }
}

// ─── Main Loop ───────────────────────────────────────────

const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on('line', async (line) => {
    let msg;
    try {
        msg = JSON.parse(line);
    } catch (e) {
        process.stdout.write(JSON.stringify({ id: null, ok: false, error: 'Invalid JSON' }) + '\n');
        return;
    }

    let response;
    switch (msg.action) {
        case 'require':    response = handleRequire(msg); break;
        case 'call':       response = handleCall(msg); break;
        case 'callDirect': response = handleCallDirect(msg); break;
        case 'get':        response = handleGet(msg); break;
        case 'set':        response = handleSet(msg); break;
        case 'ping':       response = { id: msg.id, ok: true, result: { type: 'string', value: 'pong' } }; break;
        default:
            response = { id: msg.id, ok: false, error: `Unknown action: ${msg.action}` };
    }

    // Handle async responses (promises)
    try {
        const resolved = await Promise.resolve(response);
        process.stdout.write(JSON.stringify(resolved) + '\n');
    } catch (e) {
        process.stdout.write(JSON.stringify({
            id: msg.id, ok: false, error: e.message || String(e)
        }) + '\n');
    }
});

// Signal readiness
process.stderr.write('[EPL JS Bridge] Worker ready.\n');
