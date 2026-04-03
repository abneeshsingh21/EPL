"""
EPL Web Playground
==================
Browser-based IDE for trying EPL in seconds.
Usage:  python main.py playground [--port 8080]
"""

import io
import os
import sys
import json
import html
import traceback
import threading
import contextlib
from epl.errors import EPLError

def _safe_error(e):
    """Return error message, sanitizing non-EPL exceptions."""
    return str(e) if isinstance(e, EPLError) else 'Internal error'

# ── Public API ───────────────────────────────────────────

def start_playground(port: int = 8080, open_browser: bool = True):
    """Start the EPL Web Playground server."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class PlaygroundHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                self._serve_html()
            elif self.path == '/api/examples':
                self._serve_examples()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/api/run':
                self._run_code()
            elif self.path == '/api/transpile':
                self._transpile_code()
            else:
                self.send_error(404)

        def _serve_html(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(_PLAYGROUND_HTML.encode('utf-8'))

        def _serve_examples(self):
            examples = _get_examples()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(examples).encode('utf-8'))

        def _run_code(self):
            length = int(self.headers.get('Content-Length', 0))
            if length > 1_000_000:
                self._json_response(400, {'error': 'Code too large (max 1MB)'})
                return
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {'error': 'Invalid JSON'})
                return
            code = data.get('code', '')
            if not code.strip():
                self._json_response(400, {'error': 'No code provided'})
                return
            result = _execute_epl(code)
            self._json_response(200, result)

        def _transpile_code(self):
            length = int(self.headers.get('Content-Length', 0))
            if length > 1_000_000:
                self._json_response(400, {'error': 'Code too large (max 1MB)'})
                return
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {'error': 'Invalid JSON'})
                return
            code = data.get('code', '')
            target = data.get('target', 'python')
            if not code.strip():
                self._json_response(400, {'error': 'No code provided'})
                return
            result = _transpile_epl(code, target)
            self._json_response(200, result)

        def _json_response(self, status, data):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))

    server = HTTPServer(('127.0.0.1', port), PlaygroundHandler)
    print(f"  EPL Web Playground running at http://127.0.0.1:{port}")
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
        print("\n  Playground stopped.")
        server.server_close()


# ── EPL Execution Engine ─────────────────────────────────

def _execute_epl(code: str) -> dict:
    """Execute EPL code and capture output (sandboxed with timeout)."""
    output = io.StringIO()
    error = None
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
            old_stdout = sys.stdout
            old_stderr = sys.stderr
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
        t.join(timeout=10)  # 10 second timeout

        if not done.is_set():
            result = {'output': '', 'error': 'Execution timed out (10s limit)'}
        return result

    except Exception as e:
        return {'output': '', 'error': _safe_error(e)}


def _transpile_epl(code: str, target: str) -> dict:
    """Transpile EPL code to the target language."""
    try:
        from epl.lexer import Lexer
        from epl.parser import Parser

        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        if target == 'python':
            from epl.python_transpiler import transpile_to_python
            result = transpile_to_python(program)
        elif target == 'javascript':
            from epl.js_transpiler import transpile_to_js
            result = transpile_to_js(program)
        else:
            return {'error': f'Unknown target: {target}'}

        return {'code': result, 'error': None}
    except Exception as e:
        return {'code': '', 'error': _safe_error(e)}


def _get_examples() -> list:
    """Return a curated list of EPL examples."""
    return [
        {
            'name': 'Hello World',
            'code': 'display "Hello, World!"\ndisplay "Welcome to EPL!"'
        },
        {
            'name': 'Variables & Math',
            'code': 'set name to "Alice"\nset age to 25\nset score to 95.5\ndisplay "Name: " + name\ndisplay "Age: " + age\ndisplay "Score: " + score'
        },
        {
            'name': 'If/Else',
            'code': 'set score to 85\n\nif score > 90 then\n    display "Grade: A"\notherwise if score > 80 then\n    display "Grade: B"\notherwise\n    display "Grade: C"\nend'
        },
        {
            'name': 'Loops',
            'code': 'display "Counting:"\nrepeat 5 times\n    display "Hello!"\nend\n\nfor i from 1 to 5\n    display "Number: " + i\nend'
        },
        {
            'name': 'Functions',
            'code': 'function greet takes name\n    display "Hello, " + name + "!"\nend\n\ngreet("Alice")\ngreet("Bob")\n\nfunction add takes a and b\n    return a + b\nend\n\nset result to add(10, 20)\ndisplay "10 + 20 = " + result'
        },
        {
            'name': 'Lists',
            'code': 'set fruits to ["apple", "banana", "cherry"]\ndisplay "Fruits: " + fruits\ndisplay "First: " + fruits[0]\n\nfor each fruit in fruits\n    display "I like " + fruit\nend'
        },
        {
            'name': 'Classes',
            'code': 'class Animal\n    set name to "Unknown"\n    set sound to "..."\n\n    function speak\n        display name + " says " + sound\n    end\nend\n\nset dog to new Animal\ndog.name = "Rex"\ndog.sound = "Woof!"\ndog.speak()'
        },
        {
            'name': 'Try/Catch',
            'code': 'try\n    set result to 10 / 0\ncatch error\n    display "Caught error: " + error\nend\n\ndisplay "Program continues!"'
        },
        {
            'name': 'Fibonacci',
            'code': 'function fibonacci takes n\n    if n <= 1 then\n        return n\n    end\n    return fibonacci(n - 1) + fibonacci(n - 2)\nend\n\nfor i from 0 to 10\n    display "fib(" + i + ") = " + fibonacci(i)\nend'
        },
        {
            'name': 'FizzBuzz',
            'code': 'for i from 1 to 30\n    if i % 15 == 0 then\n        display "FizzBuzz"\n    otherwise if i % 3 == 0 then\n        display "Fizz"\n    otherwise if i % 5 == 0 then\n        display "Buzz"\n    otherwise\n        display i\n    end\nend'
        }
    ]


# ── HTML Template ────────────────────────────────────────

_PLAYGROUND_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPL Playground</title>
<style>
:root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --accent-hover: #79c0ff;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --purple: #bc8cff;
    --font-mono: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    --radius: 8px;
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
}

/* Header */
header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
header .logo {
    display: flex;
    align-items: center;
    gap: 10px;
}
header .logo h1 {
    font-size: 1.2em;
    font-weight: 700;
    color: var(--accent);
}
header .logo span {
    font-size: 0.8em;
    color: var(--text-dim);
    background: var(--bg);
    padding: 2px 8px;
    border-radius: 12px;
}
header .actions {
    display: flex;
    gap: 8px;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    font-size: 0.85em;
    cursor: pointer;
    transition: all 0.15s;
}
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn-primary {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
    font-weight: 600;
}
.btn-primary:hover { background: var(--accent-hover); }
.btn-success { background: #238636; color: #fff; border-color: #238636; }
.btn-success:hover { background: #2ea043; }
.btn kbd {
    background: rgba(255,255,255,0.1);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.85em;
}

/* Main layout */
main {
    display: flex;
    flex: 1;
    overflow: hidden;
}

/* Panel */
.panel {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
}
.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    font-size: 0.82em;
    color: var(--text-dim);
    flex-shrink: 0;
}
.panel-header .tabs {
    display: flex;
    gap: 2px;
}
.tab {
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
}
.tab:hover { background: rgba(255,255,255,0.05); }
.tab.active { background: var(--accent); color: #fff; }

/* Divider */
.divider {
    width: 3px;
    background: var(--border);
    cursor: col-resize;
    flex-shrink: 0;
    transition: background 0.15s;
}
.divider:hover, .divider.active { background: var(--accent); }

/* Editor */
#editor {
    flex: 1;
    padding: 14px;
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
    border: none;
    resize: none;
    outline: none;
    tab-size: 4;
    overflow: auto;
}
#editor::placeholder { color: var(--text-dim); }

/* Output */
#output {
    flex: 1;
    padding: 14px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.5;
    background: var(--bg);
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
}
.output-line { margin: 1px 0; }
.output-error { color: var(--red); }
.output-success { color: var(--green); }
.output-info { color: var(--text-dim); font-style: italic; }

/* Transpiled output */
#transpiled {
    flex: 1;
    padding: 14px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.5;
    background: var(--bg);
    overflow: auto;
    white-space: pre-wrap;
    display: none;
}

/* Sidebar */
.sidebar {
    width: 240px;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
}
.sidebar h3 {
    padding: 12px 14px 6px;
    font-size: 0.78em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-dim);
}
.example-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 6px 10px;
}
.example-item {
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85em;
    transition: all 0.1s;
}
.example-item:hover { background: rgba(255,255,255,0.06); }
.example-item.active { background: rgba(88,166,255,0.15); color: var(--accent); }

/* Status bar */
.statusbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 14px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    font-size: 0.75em;
    color: var(--text-dim);
    flex-shrink: 0;
}
.status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}
.status-dot.ready { background: var(--green); }
.status-dot.running { background: var(--orange); animation: pulse 1s infinite; }
.status-dot.error { background: var(--red); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Responsive */
@media (max-width: 768px) {
    main { flex-direction: column; }
    .sidebar { width: 100%; max-height: 140px; border-left: 0; border-top: 1px solid var(--border); }
    .divider { width: 100%; height: 3px; cursor: row-resize; }
}
</style>
</head>
<body>

<header>
    <div class="logo">
        <h1>EPL Playground</h1>
        <span>English Programming Language</span>
    </div>
    <div class="actions">
        <button class="btn" onclick="clearOutput()" title="Clear output">Clear</button>
        <select class="btn" id="transpileTarget" title="Transpile target">
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
        </select>
        <button class="btn" onclick="transpileCode()" title="Transpile code">Transpile</button>
        <button class="btn btn-primary" onclick="runCode()" title="Run code (Ctrl+Enter)">
            Run <kbd>Ctrl+Enter</kbd>
        </button>
    </div>
</header>

<main>
    <!-- Editor Panel -->
    <div class="panel" id="editorPanel" style="flex: 1;">
        <div class="panel-header">
            <span>editor.epl</span>
            <span id="lineInfo">Ln 1, Col 1</span>
        </div>
        <textarea id="editor" spellcheck="false" placeholder="Write your EPL code here...

Example:
  display &quot;Hello, World!&quot;
  set name to &quot;Alice&quot;
  display &quot;Welcome, &quot; + name"></textarea>
    </div>

    <!-- Divider -->
    <div class="divider" id="divider"></div>

    <!-- Output Panel -->
    <div class="panel" id="outputPanel" style="flex: 1;">
        <div class="panel-header">
            <div class="tabs">
                <div class="tab active" data-tab="output" onclick="switchTab('output')">Output</div>
                <div class="tab" data-tab="transpiled" onclick="switchTab('transpiled')">Transpiled</div>
            </div>
            <span id="execTime"></span>
        </div>
        <div id="output"><span class="output-info">Press Run or Ctrl+Enter to execute your code.</span></div>
        <div id="transpiled"></div>
    </div>

    <!-- Examples Sidebar -->
    <div class="sidebar" id="sidebar">
        <h3>Examples</h3>
        <div class="example-list" id="exampleList"></div>
    </div>
</main>

<div class="statusbar">
    <span><span class="status-dot ready" id="statusDot"></span><span id="statusText">Ready</span></span>
    <span>EPL Playground &bull; Safe Mode</span>
</div>

<script>
const editor = document.getElementById('editor');
const output = document.getElementById('output');
const transpiled = document.getElementById('transpiled');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const execTime = document.getElementById('execTime');

// Update line/col info
editor.addEventListener('keyup', updateLineInfo);
editor.addEventListener('click', updateLineInfo);

function updateLineInfo() {
    const pos = editor.selectionStart;
    const text = editor.value.substring(0, pos);
    const lines = text.split('\n');
    document.getElementById('lineInfo').textContent =
        `Ln ${lines.length}, Col ${lines[lines.length-1].length + 1}`;
}

// Tab key support
editor.addEventListener('keydown', function(e) {
    if (e.key === 'Tab') {
        e.preventDefault();
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 4;
    }
    if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        runCode();
    }
});

// Run code
async function runCode() {
    const code = editor.value.trim();
    if (!code) return;

    setStatus('running', 'Running...');
    output.innerHTML = '';
    switchTab('output');
    const start = performance.now();

    try {
        const res = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });
        const data = await res.json();
        const elapsed = ((performance.now() - start) / 1000).toFixed(2);
        execTime.textContent = `${elapsed}s`;

        if (data.output) {
            const escaped = escapeHtml(data.output);
            output.innerHTML = escaped.split('\n')
                .map(l => `<div class="output-line">${l}</div>`).join('');
        }
        if (data.error) {
            output.innerHTML += `<div class="output-error">${escapeHtml(data.error)}</div>`;
            setStatus('error', 'Error');
        } else {
            setStatus('ready', 'Done');
        }
    } catch (err) {
        output.innerHTML = `<div class="output-error">Connection error: ${escapeHtml(err.message)}</div>`;
        setStatus('error', 'Error');
    }
}

// Transpile code
async function transpileCode() {
    const code = editor.value.trim();
    if (!code) return;

    const target = document.getElementById('transpileTarget').value;
    switchTab('transpiled');

    try {
        const res = await fetch('/api/transpile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, target })
        });
        const data = await res.json();
        if (data.error) {
            transpiled.innerHTML = `<span class="output-error">${escapeHtml(data.error)}</span>`;
        } else {
            transpiled.textContent = data.code;
        }
    } catch (err) {
        transpiled.innerHTML = `<span class="output-error">${escapeHtml(err.message)}</span>`;
    }
}

function clearOutput() {
    output.innerHTML = '<span class="output-info">Output cleared.</span>';
    transpiled.textContent = '';
    execTime.textContent = '';
    setStatus('ready', 'Ready');
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    output.style.display = tab === 'output' ? 'block' : 'none';
    transpiled.style.display = tab === 'transpiled' ? 'block' : 'none';
}

function setStatus(state, text) {
    statusDot.className = 'status-dot ' + state;
    statusText.textContent = text;
}

function escapeHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Load examples
async function loadExamples() {
    try {
        const res = await fetch('/api/examples');
        const examples = await res.json();
        const list = document.getElementById('exampleList');
        examples.forEach((ex, i) => {
            const div = document.createElement('div');
            div.className = 'example-item';
            div.textContent = ex.name;
            div.onclick = () => {
                editor.value = ex.code;
                document.querySelectorAll('.example-item').forEach(e => e.classList.remove('active'));
                div.classList.add('active');
                updateLineInfo();
            };
            list.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load examples:', e);
    }
}

// Resizable divider
const divider = document.getElementById('divider');
const editorPanel = document.getElementById('editorPanel');
const outputPanel = document.getElementById('outputPanel');
let isDragging = false;

divider.addEventListener('mousedown', e => {
    isDragging = true;
    divider.classList.add('active');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', e => {
    if (!isDragging) return;
    const main = document.querySelector('main');
    const rect = main.getBoundingClientRect();
    const sidebar = document.getElementById('sidebar');
    const sidebarW = sidebar.getBoundingClientRect().width;
    const available = rect.width - sidebarW - 3; // divider width
    const offset = e.clientX - rect.left;
    const ratio = Math.max(0.2, Math.min(0.8, offset / available));
    editorPanel.style.flex = ratio.toString();
    outputPanel.style.flex = (1 - ratio).toString();
});

document.addEventListener('mouseup', () => {
    if (isDragging) {
        isDragging = false;
        divider.classList.remove('active');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
});

// Init
loadExamples();
</script>
</body>
</html>
'''
