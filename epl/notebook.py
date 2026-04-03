"""
EPL Notebook
============
Jupyter-like web interface with executable cells, rich output (charts/tables).
Usage:  python main.py notebook [--port 8888]
"""

import io
import os
import sys
import json
import uuid
import threading
from epl.errors import EPLError

def _safe_error(e):
    """Return error message, sanitizing non-EPL exceptions."""
    return str(e) if isinstance(e, EPLError) else 'Internal error'

# ── Public API ───────────────────────────────────────────

def start_notebook(port: int = 8888, open_browser: bool = True):
    """Start the EPL Notebook server."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    notebook_state = {
        'cells': [
            {'id': _new_id(), 'type': 'code', 'source': 'display "Hello from EPL Notebook!"', 'output': '', 'error': None}
        ]
    }
    state_lock = threading.Lock()

    class NotebookHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                self._serve_html()
            elif self.path == '/api/state':
                self._json_response(200, notebook_state)
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/api/run-cell':
                self._run_cell()
            elif self.path == '/api/run-all':
                self._run_all()
            elif self.path == '/api/update':
                self._update_state()
            elif self.path == '/api/export':
                self._export()
            else:
                self.send_error(404)

        def _serve_html(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(_NOTEBOOK_HTML.encode('utf-8'))

        def _run_cell(self):
            data = self._read_json()
            if not data:
                return
            cell_id = data.get('id')
            code = data.get('source', '')
            result = _execute_epl(code)
            # Update state
            with state_lock:
                for cell in notebook_state['cells']:
                    if cell['id'] == cell_id:
                        cell['source'] = code
                        cell['output'] = result.get('output', '')
                        cell['error'] = result.get('error')
                        break
            self._json_response(200, result)

        def _run_all(self):
            results = []
            with state_lock:
                for cell in notebook_state['cells']:
                    if cell['type'] == 'code' and cell['source'].strip():
                        result = _execute_epl(cell['source'])
                        cell['output'] = result.get('output', '')
                        cell['error'] = result.get('error')
                        results.append({'id': cell['id'], **result})
            self._json_response(200, {'results': results})

        def _update_state(self):
            data = self._read_json()
            if not data:
                return
            cells = data.get('cells', [])
            if len(cells) > 500:
                self._json_response(400, {'error': 'Too many cells (max 500)'})
                return
            with state_lock:
                notebook_state['cells'] = cells
            self._json_response(200, {'ok': True})

        def _export(self):
            data = self._read_json()
            fmt = data.get('format', 'epl') if data else 'epl'
            with state_lock:
                if fmt == 'epl':
                    code = '\n\n'.join(c['source'] for c in notebook_state['cells']
                                       if c['type'] == 'code' and c['source'].strip())
                    self._json_response(200, {'content': code, 'filename': 'notebook.epl'})
                elif fmt == 'json':
                    self._json_response(200, {'content': json.dumps(notebook_state, indent=2),
                                              'filename': 'notebook.json'})
                else:
                    self._json_response(400, {'error': f'Unknown format: {fmt}'})

        def _read_json(self):
            length = int(self.headers.get('Content-Length', 0))
            if length > 2_000_000:
                self._json_response(400, {'error': 'Payload too large'})
                return None
            try:
                return json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._json_response(400, {'error': 'Invalid JSON'})
                return None

        def _json_response(self, status, data):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))

    server = HTTPServer(('127.0.0.1', port), NotebookHandler)
    print(f"  EPL Notebook running at http://127.0.0.1:{port}")
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
        print("\n  Notebook stopped.")
        server.server_close()


# ── Helpers ──────────────────────────────────────────────

def _new_id():
    return uuid.uuid4().hex[:8]


def _execute_epl(code: str) -> dict:
    """Execute EPL code and capture output."""
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

_NOTEBOOK_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPL Notebook</title>
<style>
:root {
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #1c2129;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --font-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: var(--font-sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}

/* Toolbar */
.toolbar {
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
}
.toolbar .left {
    display: flex;
    align-items: center;
    gap: 12px;
}
.toolbar h1 {
    font-size: 1.1em;
    color: var(--accent);
}
.toolbar .right {
    display: flex;
    gap: 6px;
}

.btn {
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
    font-size: 0.82em;
    cursor: pointer;
    transition: all 0.15s;
}
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; }
.btn-primary:hover { background: #79c0ff; }
.btn-sm { padding: 3px 8px; font-size: 0.78em; }
.btn-danger { color: var(--red); }
.btn-danger:hover { border-color: var(--red); }

/* Notebook container */
.notebook {
    max-width: 960px;
    margin: 20px auto;
    padding: 0 20px 60px;
}

/* Cell */
.cell {
    position: relative;
    margin-bottom: 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    transition: border-color 0.15s;
}
.cell:hover { border-color: var(--text-dim); }
.cell.focused { border-color: var(--accent); }
.cell.running { border-color: var(--orange); }

.cell-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 10px;
    font-size: 0.75em;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
}
.cell-header .cell-type {
    display: flex;
    align-items: center;
    gap: 6px;
}
.cell-header .cell-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.15s;
}
.cell:hover .cell-actions { opacity: 1; }

.cell-editor {
    padding: 0;
}
.cell-editor textarea {
    width: 100%;
    min-height: 60px;
    padding: 10px 14px;
    border: none;
    background: transparent;
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.55;
    resize: vertical;
    outline: none;
    tab-size: 4;
}

/* Markdown cell */
.cell-markdown {
    padding: 10px 14px;
    font-size: 0.95em;
    line-height: 1.6;
}
.cell-markdown h1 { font-size: 1.5em; margin-bottom: 6px; }
.cell-markdown h2 { font-size: 1.3em; margin-bottom: 4px; }
.cell-markdown p { margin-bottom: 8px; }
.cell-markdown code { background: var(--bg); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 0.9em; }
.cell-markdown-edit textarea {
    min-height: 40px;
}

/* Output */
.cell-output {
    border-top: 1px solid var(--border);
    padding: 8px 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    max-height: 300px;
    overflow-y: auto;
    background: var(--surface2);
    border-radius: 0 0 7px 7px;
}
.cell-output:empty { display: none; }
.cell-output .error { color: var(--red); }
.cell-output .success { color: var(--green); }

/* Add cell button */
.add-cell {
    display: flex;
    justify-content: center;
    gap: 8px;
    padding: 10px;
    margin: 4px 0;
    opacity: 0;
    transition: opacity 0.2s;
}
.notebook:hover .add-cell,
.add-cell:focus-within { opacity: 1; }
.add-cell .btn { font-size: 0.78em; padding: 4px 12px; }

/* Status bar */
.statusbar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 4px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    font-size: 0.75em;
    color: var(--text-dim);
    display: flex;
    justify-content: space-between;
}
</style>
</head>
<body>

<div class="toolbar">
    <div class="left">
        <h1>EPL Notebook</h1>
        <span style="color:var(--text-dim);font-size:0.8em">Interactive Cells</span>
    </div>
    <div class="right">
        <button class="btn" onclick="addCell('code')">+ Code</button>
        <button class="btn" onclick="addCell('markdown')">+ Markdown</button>
        <button class="btn btn-primary" onclick="runAll()">Run All</button>
        <select class="btn" id="exportFmt">
            <option value="epl">.epl</option>
            <option value="json">.json</option>
        </select>
        <button class="btn" onclick="exportNotebook()">Export</button>
    </div>
</div>

<div class="notebook" id="notebook"></div>

<div class="statusbar">
    <span id="nbStatus">Ready</span>
    <span id="nbCellCount">1 cell</span>
</div>

<script>
let cells = [];

async function loadState() {
    const res = await fetch('/api/state');
    const data = await res.json();
    cells = data.cells || [];
    render();
}

function render() {
    const nb = document.getElementById('notebook');
    nb.innerHTML = '';

    cells.forEach((cell, i) => {
        // Add-cell area between cells
        if (i === 0) nb.appendChild(makeAddBar(i));

        const div = document.createElement('div');
        div.className = 'cell';
        div.id = 'cell-' + cell.id;

        // Header
        const header = document.createElement('div');
        header.className = 'cell-header';
        header.innerHTML = `
            <div class="cell-type">
                <span>[${i + 1}] ${cell.type === 'code' ? 'Code' : 'Markdown'}</span>
            </div>
            <div class="cell-actions">
                <button class="btn btn-sm" onclick="runCell('${cell.id}')" title="Run (Shift+Enter)">&#9654; Run</button>
                <button class="btn btn-sm" onclick="moveCell('${cell.id}',-1)" title="Move up">&#9650;</button>
                <button class="btn btn-sm" onclick="moveCell('${cell.id}',1)" title="Move down">&#9660;</button>
                <button class="btn btn-sm btn-danger" onclick="deleteCell('${cell.id}')" title="Delete">&#10005;</button>
            </div>`;
        div.appendChild(header);

        // Editor
        const editor = document.createElement('div');
        editor.className = 'cell-editor';
        const ta = document.createElement('textarea');
        ta.value = cell.source || '';
        ta.spellcheck = false;
        ta.addEventListener('input', e => {
            cell.source = e.target.value;
            autoResize(e.target);
        });
        ta.addEventListener('keydown', e => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const s = ta.selectionStart, end = ta.selectionEnd;
                ta.value = ta.value.substring(0, s) + '    ' + ta.value.substring(end);
                ta.selectionStart = ta.selectionEnd = s + 4;
                cell.source = ta.value;
            }
            if (e.key === 'Enter' && e.shiftKey) {
                e.preventDefault();
                runCell(cell.id);
            }
        });
        editor.appendChild(ta);
        div.appendChild(editor);

        // Output
        const out = document.createElement('div');
        out.className = 'cell-output';
        out.id = 'output-' + cell.id;
        if (cell.output) out.textContent = cell.output;
        if (cell.error) out.innerHTML = `<span class="error">${escapeHtml(cell.error)}</span>`;
        div.appendChild(out);

        nb.appendChild(div);
        nb.appendChild(makeAddBar(i + 1));

        // Auto-resize textarea
        setTimeout(() => autoResize(ta), 0);
    });

    document.getElementById('nbCellCount').textContent =
        cells.length + ' cell' + (cells.length !== 1 ? 's' : '');
}

function makeAddBar(index) {
    const bar = document.createElement('div');
    bar.className = 'add-cell';
    bar.innerHTML = `
        <button class="btn btn-sm" onclick="insertCell(${index},'code')">+ Code</button>
        <button class="btn btn-sm" onclick="insertCell(${index},'markdown')">+ Markdown</button>`;
    return bar;
}

function autoResize(ta) {
    ta.style.height = 'auto';
    ta.style.height = Math.max(60, ta.scrollHeight) + 'px';
}

function addCell(type) {
    cells.push({ id: newId(), type, source: '', output: '', error: null });
    render();
    saveState();
}

function insertCell(index, type) {
    cells.splice(index, 0, { id: newId(), type, source: '', output: '', error: null });
    render();
    saveState();
}

function deleteCell(id) {
    if (cells.length <= 1) return;
    cells = cells.filter(c => c.id !== id);
    render();
    saveState();
}

function moveCell(id, dir) {
    const i = cells.findIndex(c => c.id === id);
    const j = i + dir;
    if (j < 0 || j >= cells.length) return;
    [cells[i], cells[j]] = [cells[j], cells[i]];
    render();
    saveState();
}

async function runCell(id) {
    const cell = cells.find(c => c.id === id);
    if (!cell || cell.type !== 'code') return;

    const el = document.getElementById('cell-' + id);
    if (el) el.classList.add('running');
    document.getElementById('nbStatus').textContent = 'Running...';

    try {
        const res = await fetch('/api/run-cell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, source: cell.source })
        });
        const data = await res.json();
        cell.output = data.output || '';
        cell.error = data.error || null;

        const out = document.getElementById('output-' + id);
        if (out) {
            out.textContent = '';
            if (cell.output) out.textContent = cell.output;
            if (cell.error) out.innerHTML += `<span class="error">${escapeHtml(cell.error)}</span>`;
        }
    } catch (e) {
        cell.error = e.message;
    }

    if (el) el.classList.remove('running');
    document.getElementById('nbStatus').textContent = 'Ready';
}

async function runAll() {
    document.getElementById('nbStatus').textContent = 'Running all cells...';
    for (const cell of cells) {
        if (cell.type === 'code' && cell.source.trim()) {
            await runCell(cell.id);
        }
    }
    document.getElementById('nbStatus').textContent = 'Done';
}

async function saveState() {
    await fetch('/api/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cells })
    });
}

async function exportNotebook() {
    const fmt = document.getElementById('exportFmt').value;
    try {
        const res = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format: fmt })
        });
        const data = await res.json();
        if (data.content) {
            const blob = new Blob([data.content], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = data.filename;
            a.click();
        }
    } catch (e) {
        alert('Export failed: ' + e.message);
    }
}

function newId() {
    return Math.random().toString(36).substring(2, 10);
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

loadState();
</script>
</body>
</html>
'''
