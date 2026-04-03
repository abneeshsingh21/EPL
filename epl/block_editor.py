"""
EPL Visual Block Editor
=======================
Scratch-like drag-and-drop web interface that generates valid EPL code.
Usage:  python main.py blocks [--port 8090]
"""

import io
import sys
import json
import threading
from epl.errors import EPLError

def _safe_error(e):
    """Return error message, sanitizing non-EPL exceptions."""
    return str(e) if isinstance(e, EPLError) else 'Internal error'

# ── Public API ───────────────────────────────────────────

def start_block_editor(port: int = 8090, open_browser: bool = True):
    """Start the EPL Visual Block Editor server."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class BlockHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                self._serve_html()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/api/run':
                self._run_code()
            else:
                self.send_error(404)

        def _serve_html(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(_BLOCK_EDITOR_HTML.encode('utf-8'))

        def _run_code(self):
            length = int(self.headers.get('Content-Length', 0))
            if length > 1_000_000:
                self._json_response(400, {'error': 'Too large'})
                return
            try:
                data = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._json_response(400, {'error': 'Invalid JSON'})
                return
            code = data.get('code', '')
            result = _execute_epl(code)
            self._json_response(200, result)

        def _json_response(self, status, data):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))

    server = HTTPServer(('127.0.0.1', port), BlockHandler)
    print(f"  EPL Block Editor running at http://127.0.0.1:{port}")
    print("  Press Ctrl+C to stop")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{port}')
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Block Editor stopped.")
        server.server_close()


def _execute_epl(code: str) -> dict:
    """Execute EPL code with timeout and sandbox."""
    try:
        from epl.lexer import Lexer
        from epl.parser import Parser
        from epl.interpreter import Interpreter
        from epl.environment import Environment

        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        env = Environment()
        interp = Interpreter(safe_mode=True)

        result = {'output': '', 'error': None}
        done = threading.Event()

        def _run():
            nonlocal result
            old_stdout, old_stderr = sys.stdout, sys.stderr
            captured = io.StringIO()
            sys.stdout = captured
            sys.stderr = captured
            try:
                interp.execute(program)
                result['output'] = captured.getvalue()
            except SystemExit:
                result['output'] = captured.getvalue()
            except Exception as e:
                result['output'] = captured.getvalue()
                result['error'] = _safe_error(e)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                done.set()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=10)
        if not done.is_set():
            result = {'output': '', 'error': 'Execution timed out (10s limit)'}
        return result
    except Exception as e:
        return {'output': '', 'error': _safe_error(e)}


# ── HTML Template ────────────────────────────────────────

_BLOCK_EDITOR_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPL Block Editor</title>
<style>
:root {
    --bg: #1e1e2e;
    --surface: #181825;
    --surface2: #11111b;
    --border: #313244;
    --text: #cdd6f4;
    --text-dim: #6c7086;
    --blue: #89b4fa;
    --green: #a6e3a1;
    --red: #f38ba8;
    --mauve: #cba6f7;
    --peach: #fab387;
    --yellow: #f9e2af;
    --teal: #94e2d5;
    --pink: #f5c2e7;
    --font-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: var(--font-sans);
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    user-select: none;
}

/* Header */
header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
header h1 { font-size: 1.1em; color: var(--blue); }
.header-actions { display: flex; gap: 6px; }

.btn {
    padding: 5px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
    font-size: 0.82em;
    cursor: pointer;
    transition: all 0.15s;
}
.btn:hover { border-color: var(--blue); color: var(--blue); }
.btn-run { background: var(--green); color: var(--surface2); border-color: var(--green); font-weight: 600; }
.btn-run:hover { opacity: 0.9; }

/* Main layout */
main {
    display: flex;
    flex: 1;
    overflow: hidden;
}

/* Block palette */
.palette {
    width: 220px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    flex-shrink: 0;
    padding: 10px;
}
.palette h3 {
    font-size: 0.72em;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-dim);
    margin: 12px 0 6px;
}
.palette h3:first-child { margin-top: 4px; }

.block-template {
    padding: 7px 10px;
    margin: 3px 0;
    border-radius: 6px;
    font-size: 0.82em;
    cursor: grab;
    transition: transform 0.1s, box-shadow 0.1s;
    border-left: 3px solid;
}
.block-template:hover { transform: translateX(3px); box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.block-template:active { cursor: grabbing; }
.cat-output { background: rgba(166,227,161,0.1); border-color: var(--green); color: var(--green); }
.cat-variable { background: rgba(250,179,135,0.1); border-color: var(--peach); color: var(--peach); }
.cat-control { background: rgba(137,180,250,0.1); border-color: var(--blue); color: var(--blue); }
.cat-logic { background: rgba(203,166,247,0.1); border-color: var(--mauve); color: var(--mauve); }
.cat-function { background: rgba(245,194,231,0.1); border-color: var(--pink); color: var(--pink); }
.cat-list { background: rgba(148,226,213,0.1); border-color: var(--teal); color: var(--teal); }
.cat-math { background: rgba(249,226,175,0.1); border-color: var(--yellow); color: var(--yellow); }

/* Workspace (drop zone) */
.workspace {
    flex: 1;
    display: flex;
    flex-direction: column;
}
.workspace-header {
    padding: 6px 14px;
    font-size: 0.78em;
    color: var(--text-dim);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
}

.drop-zone {
    flex: 1;
    padding: 14px;
    overflow-y: auto;
    min-height: 200px;
}
.drop-zone.dragover { background: rgba(137,180,250,0.04); }

.placed-block {
    padding: 8px 12px;
    margin: 3px 0;
    border-radius: 6px;
    font-size: 0.85em;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    position: relative;
    border-left: 3px solid;
}
.placed-block:hover { box-shadow: 0 0 0 1px var(--border); }
.placed-block .delete-block {
    position: absolute;
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--red);
    cursor: pointer;
    font-size: 1em;
    opacity: 0;
    transition: opacity 0.15s;
}
.placed-block:hover .delete-block { opacity: 1; }

.placed-block input, .placed-block select {
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 0.9em;
    width: auto;
    min-width: 60px;
}
.placed-block input:focus { border-color: var(--blue); outline: none; }

.indent-block {
    margin-left: 24px;
    border-left: 2px solid var(--border);
    padding-left: 8px;
}

/* Code preview */
.code-area {
    flex: 0 0 auto;
    max-height: 250px;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
}
.code-area-header {
    padding: 4px 14px;
    font-size: 0.75em;
    color: var(--text-dim);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
}
#codePreview {
    padding: 10px 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.5;
    background: var(--surface2);
    overflow: auto;
    white-space: pre-wrap;
    flex: 1;
}

/* Output panel */
.output-panel {
    width: 300px;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
}
.output-panel-header {
    padding: 6px 14px;
    font-size: 0.78em;
    color: var(--text-dim);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
}
#outputArea {
    flex: 1;
    padding: 10px 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.5;
    overflow: auto;
    white-space: pre-wrap;
}
.out-error { color: var(--red); }
</style>
</head>
<body>

<header>
    <h1>EPL Block Editor</h1>
    <div class="header-actions">
        <button class="btn" onclick="clearWorkspace()">Clear</button>
        <button class="btn" onclick="copyCode()">Copy Code</button>
        <button class="btn btn-run" onclick="runBlocks()">&#9654; Run</button>
    </div>
</header>

<main>
    <!-- Block Palette -->
    <div class="palette">
        <h3>Output</h3>
        <div class="block-template cat-output" draggable="true" data-block="display">display &quot;...&quot;</div>
        <div class="block-template cat-output" draggable="true" data-block="input">ask input into ...</div>

        <h3>Variables</h3>
        <div class="block-template cat-variable" draggable="true" data-block="set">set ... to ...</div>
        <div class="block-template cat-variable" draggable="true" data-block="change">change ... by ...</div>

        <h3>Control</h3>
        <div class="block-template cat-control" draggable="true" data-block="if">if ... then ... end</div>
        <div class="block-template cat-control" draggable="true" data-block="if-else">if ... then ... otherwise ... end</div>
        <div class="block-template cat-control" draggable="true" data-block="repeat">repeat N times ... end</div>
        <div class="block-template cat-control" draggable="true" data-block="while">while ... end</div>
        <div class="block-template cat-control" draggable="true" data-block="for">for i from ... to ... end</div>
        <div class="block-template cat-control" draggable="true" data-block="foreach">for each ... in ... end</div>

        <h3>Logic</h3>
        <div class="block-template cat-logic" draggable="true" data-block="compare">... == ...</div>
        <div class="block-template cat-logic" draggable="true" data-block="and-or">... and ...</div>
        <div class="block-template cat-logic" draggable="true" data-block="not">not ...</div>

        <h3>Functions</h3>
        <div class="block-template cat-function" draggable="true" data-block="function">function name ... end</div>
        <div class="block-template cat-function" draggable="true" data-block="call">call function</div>
        <div class="block-template cat-function" draggable="true" data-block="return">return ...</div>

        <h3>Lists</h3>
        <div class="block-template cat-list" draggable="true" data-block="list">set list to [...]</div>
        <div class="block-template cat-list" draggable="true" data-block="add-to-list">add ... to list</div>

        <h3>Math</h3>
        <div class="block-template cat-math" draggable="true" data-block="math">... + ...</div>
        <div class="block-template cat-math" draggable="true" data-block="random">random 1 to 10</div>
    </div>

    <!-- Workspace -->
    <div class="workspace">
        <div class="workspace-header">
            <span>Drag blocks here to build your program</span>
            <span id="blockCount">0 blocks</span>
        </div>
        <div class="drop-zone" id="dropZone"></div>
        <div class="code-area">
            <div class="code-area-header">Generated EPL Code</div>
            <div id="codePreview"></div>
        </div>
    </div>

    <!-- Output -->
    <div class="output-panel">
        <div class="output-panel-header">Output</div>
        <div id="outputArea"><span style="color:var(--text-dim)">Click Run to see output</span></div>
    </div>
</main>

<script>
let blocks = [];
let dragType = null;

// Block templates → EPL code generation
const BLOCK_DEFS = {
    'display': {
        cat: 'cat-output',
        fields: [{name:'text', type:'text', default:'Hello, World!', label:'display'}],
        toEPL: (f) => `display "${f.text.replace(/\\/g,'\\\\').replace(/"/g,'\\"')}"`
    },
    'input': {
        cat: 'cat-output',
        fields: [{name:'var', type:'text', default:'answer', label:'ask input into'}],
        toEPL: (f) => { const v = f.var.replace(/[^A-Za-z0-9_]/g,''); return `ask "${v}?" store in ${v}`; }
    },
    'set': {
        cat: 'cat-variable',
        fields: [{name:'var', type:'text', default:'x', label:'set'}, {name:'value', type:'text', default:'10', label:'to'}],
        toEPL: (f) => { const v = f.var.replace(/[^A-Za-z0-9_]/g,''); if(isNaN(f.value)){const e=f.value.replace(/\\/g,'\\\\').replace(/"/g,'\\"');return `set ${v} to "${e}"`;} return `set ${v} to ${f.value}`; }
    },
    'change': {
        cat: 'cat-variable',
        fields: [{name:'var', type:'text', default:'x', label:'change'}, {name:'amount', type:'text', default:'1', label:'by'}],
        toEPL: (f) => `set ${f.var} to ${f.var} + ${f.amount}`
    },
    'if': {
        cat: 'cat-control',
        fields: [{name:'cond', type:'text', default:'x > 5', label:'if'}],
        toEPL: (f) => `if ${f.cond} then`,
        hasBody: true, closer: 'end'
    },
    'if-else': {
        cat: 'cat-control',
        fields: [{name:'cond', type:'text', default:'x > 5', label:'if'}],
        toEPL: (f) => `if ${f.cond} then`,
        hasBody: true, hasMid: 'otherwise', closer: 'end'
    },
    'repeat': {
        cat: 'cat-control',
        fields: [{name:'count', type:'text', default:'5', label:'repeat'}, {name:'_', type:'label', default:'times'}],
        toEPL: (f) => `repeat ${f.count} times`,
        hasBody: true, closer: 'end'
    },
    'while': {
        cat: 'cat-control',
        fields: [{name:'cond', type:'text', default:'x < 10', label:'while'}],
        toEPL: (f) => `while ${f.cond}`,
        hasBody: true, closer: 'end'
    },
    'for': {
        cat: 'cat-control',
        fields: [
            {name:'var', type:'text', default:'i', label:'for'},
            {name:'start', type:'text', default:'1', label:'from'},
            {name:'end', type:'text', default:'10', label:'to'}
        ],
        toEPL: (f) => `for ${f.var} from ${f.start} to ${f.end}`,
        hasBody: true, closer: 'end'
    },
    'foreach': {
        cat: 'cat-control',
        fields: [
            {name:'var', type:'text', default:'item', label:'for each'},
            {name:'list', type:'text', default:'items', label:'in'}
        ],
        toEPL: (f) => `for each ${f.var} in ${f.list}`,
        hasBody: true, closer: 'end'
    },
    'compare': {
        cat: 'cat-logic',
        fields: [
            {name:'left', type:'text', default:'x', label:''},
            {name:'op', type:'select', options:['==','!=','>','<','>=','<='], default:'=='},
            {name:'right', type:'text', default:'10', label:''}
        ],
        toEPL: (f) => `${f.left} ${f.op} ${f.right}`,
        isExpression: true
    },
    'and-or': {
        cat: 'cat-logic',
        fields: [
            {name:'left', type:'text', default:'x > 0', label:''},
            {name:'op', type:'select', options:['and','or'], default:'and'},
            {name:'right', type:'text', default:'x < 100', label:''}
        ],
        toEPL: (f) => `${f.left} ${f.op} ${f.right}`,
        isExpression: true
    },
    'not': {
        cat: 'cat-logic',
        fields: [{name:'expr', type:'text', default:'done', label:'not'}],
        toEPL: (f) => `not ${f.expr}`,
        isExpression: true
    },
    'function': {
        cat: 'cat-function',
        fields: [{name:'name', type:'text', default:'myFunction', label:'function'}, {name:'params', type:'text', default:'', label:'takes'}],
        toEPL: (f) => f.params ? `function ${f.name} takes ${f.params}` : `function ${f.name}`,
        hasBody: true, closer: 'end'
    },
    'call': {
        cat: 'cat-function',
        fields: [{name:'name', type:'text', default:'myFunction', label:'call'}, {name:'args', type:'text', default:'', label:'with'}],
        toEPL: (f) => f.args ? `${f.name}(${f.args})` : `${f.name}()`
    },
    'return': {
        cat: 'cat-function',
        fields: [{name:'value', type:'text', default:'result', label:'return'}],
        toEPL: (f) => `return ${f.value}`
    },
    'list': {
        cat: 'cat-list',
        fields: [{name:'var', type:'text', default:'items', label:'set'}, {name:'values', type:'text', default:'1, 2, 3', label:'to ['}],
        toEPL: (f) => `set ${f.var} to [${f.values}]`
    },
    'add-to-list': {
        cat: 'cat-list',
        fields: [{name:'value', type:'text', default:'"apple"', label:'add'}, {name:'list', type:'text', default:'items', label:'to'}],
        toEPL: (f) => `add ${f.value} to ${f.list}`
    },
    'math': {
        cat: 'cat-math',
        fields: [
            {name:'left', type:'text', default:'x', label:''},
            {name:'op', type:'select', options:['+','-','*','/','%','**'], default:'+'},
            {name:'right', type:'text', default:'1', label:''}
        ],
        toEPL: (f) => `${f.left} ${f.op} ${f.right}`,
        isExpression: true
    },
    'random': {
        cat: 'cat-math',
        fields: [{name:'min', type:'text', default:'1', label:'random'}, {name:'max', type:'text', default:'10', label:'to'}],
        toEPL: (f) => `random(${f.min}, ${f.max})`,
        isExpression: true
    }
};

// Drag-drop
document.querySelectorAll('.block-template').forEach(el => {
    el.addEventListener('dragstart', e => {
        dragType = el.dataset.block;
        e.dataTransfer.effectAllowed = 'copy';
    });
});

const dropZone = document.getElementById('dropZone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (dragType) {
        addBlock(dragType);
        dragType = null;
    }
});

function addBlock(type) {
    const def = BLOCK_DEFS[type];
    if (!def) return;
    const fields = {};
    def.fields.forEach(f => { if (f.type !== 'label') fields[f.name] = f.default; });
    const block = { id: Math.random().toString(36).substr(2,8), type, fields, children: [], elseChildren: [] };
    blocks.push(block);
    renderBlocks();
    updateCode();
}

function deleteBlock(id) {
    blocks = blocks.filter(b => b.id !== id);
    renderBlocks();
    updateCode();
}

function renderBlocks() {
    dropZone.innerHTML = '';
    blocks.forEach(block => {
        dropZone.appendChild(createBlockElement(block));
    });
    document.getElementById('blockCount').textContent = blocks.length + ' block' + (blocks.length !== 1 ? 's' : '');
}

function createBlockElement(block) {
    const def = BLOCK_DEFS[block.type];
    const el = document.createElement('div');
    el.className = 'placed-block ' + def.cat;

    // Build fields
    def.fields.forEach(f => {
        if (f.label) {
            const lbl = document.createElement('span');
            lbl.textContent = f.label;
            el.appendChild(lbl);
        }
        if (f.type === 'text') {
            const inp = document.createElement('input');
            inp.type = 'text';
            inp.value = block.fields[f.name] || f.default;
            inp.style.width = Math.max(60, (inp.value.length + 2) * 8) + 'px';
            inp.addEventListener('input', e => {
                block.fields[f.name] = e.target.value;
                inp.style.width = Math.max(60, (e.target.value.length + 2) * 8) + 'px';
                updateCode();
            });
            el.appendChild(inp);
        } else if (f.type === 'select') {
            const sel = document.createElement('select');
            f.options.forEach(o => {
                const opt = document.createElement('option');
                opt.value = o; opt.textContent = o;
                if (o === block.fields[f.name]) opt.selected = true;
                sel.appendChild(opt);
            });
            sel.addEventListener('change', e => { block.fields[f.name] = e.target.value; updateCode(); });
            el.appendChild(sel);
        } else if (f.type === 'label') {
            const lbl = document.createElement('span');
            lbl.textContent = f.default;
            el.appendChild(lbl);
        }
    });

    // Delete button
    const del = document.createElement('button');
    del.className = 'delete-block';
    del.innerHTML = '&times;';
    del.onclick = () => deleteBlock(block.id);
    el.appendChild(del);

    return el;
}

function updateCode() {
    const lines = [];
    blocks.forEach(block => {
        const def = BLOCK_DEFS[block.type];
        if (def.isExpression) return; // Skip pure expressions in top-level
        const line = def.toEPL(block.fields);
        lines.push(line);
        if (def.hasBody) {
            lines.push('    display "..."');
            if (def.hasMid) lines.push(def.hasMid, '    display "..."');
            lines.push(def.closer);
        }
    });
    document.getElementById('codePreview').textContent = lines.join('\n');
}

async function runBlocks() {
    const code = document.getElementById('codePreview').textContent;
    if (!code.trim()) return;

    const out = document.getElementById('outputArea');
    out.innerHTML = '<span style="color:var(--yellow)">Running...</span>';

    try {
        const res = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });
        const data = await res.json();
        out.innerHTML = '';
        if (data.output) out.textContent = data.output;
        if (data.error) out.innerHTML += `<span class="out-error">${escapeHtml(data.error)}</span>`;
        if (!data.output && !data.error) out.innerHTML = '<span style="color:var(--text-dim)">No output</span>';
    } catch(e) {
        out.innerHTML = `<span class="out-error">${escapeHtml(e.message)}</span>`;
    }
}

function clearWorkspace() {
    blocks = [];
    renderBlocks();
    updateCode();
    document.getElementById('outputArea').innerHTML = '<span style="color:var(--text-dim)">Cleared</span>';
}

function copyCode() {
    const code = document.getElementById('codePreview').textContent;
    navigator.clipboard.writeText(code).then(() => {
        const btn = event.target;
        const old = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = old, 1500);
    });
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Initial render
renderBlocks();
updateCode();
</script>
</body>
</html>
'''
