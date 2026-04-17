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
            elif self.path == '/api/syntax':
                self._serve_syntax()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/api/run':
                self._run_code()
            elif self.path == '/api/transpile':
                self._transpile_code()
            elif self.path == '/api/assist':
                self._assist_code()
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

        def _serve_syntax(self):
            self._json_response(200, _get_syntax_reference())

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

        def _assist_code(self):
            length = int(self.headers.get('Content-Length', 0))
            if length > 1_000_000:
                self._json_response(400, {'error': 'Request too large (max 1MB)'})
                return
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {'error': 'Invalid JSON'})
                return

            message = data.get('message', '')
            code = data.get('code', '')
            mode = data.get('mode', 'auto')
            if not message.strip() and not code.strip():
                self._json_response(400, {'error': 'Provide a prompt or some EPL code.'})
                return

            result = _assist_playground(message, code=code, mode=mode)
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


def _assist_playground(message: str, code: str = "", mode: str = "auto") -> dict:
    """Run the syntax-aware playground assistant."""
    from epl.copilot import assist_request

    return assist_request(message, current_code=code, mode=mode)


def _get_syntax_reference() -> dict:
    """Return the authoritative syntax guide used by the playground assistant."""
    from epl.syntax_reference import get_syntax_sections, get_syntax_text

    return {
        'sections': get_syntax_sections(),
        'text': get_syntax_text(),
    }


def _get_examples() -> list:
    """Return a curated list of EPL examples."""
    return [
        {
            'name': 'Hello World',
            'code': 'Say "Hello, World!"\nSay "Welcome to EPL!"'
        },
        {
            'name': 'Variables & Math',
            'code': 'Create name = "Alice"\nCreate age = 25\nCreate score = 95.5\nSay "Name: " + name\nSay "Age: " + age\nSay "Score: " + score'
        },
        {
            'name': 'If/Else',
            'code': 'Create score = 85\n\nIf score > 90 Then\n    Say "Grade: A"\nOtherwise If score > 80 Then\n    Say "Grade: B"\nOtherwise\n    Say "Grade: C"\nEnd'
        },
        {
            'name': 'Loops',
            'code': 'Say "Counting:"\nRepeat 5 times\n    Say "Hello!"\nEnd\n\nFor i from 1 to 5\n    Say "Number: " + i\nEnd'
        },
        {
            'name': 'Functions',
            'code': 'Function greet takes name\n    Return "Hello, " + name + "!"\nEnd\n\nSay greet("Alice")\nSay greet("Bob")\n\nFunction add(a, b)\n    Return a + b\nEnd\n\nCreate result = add(10, 20)\nSay "10 + 20 = " + result'
        },
        {
            'name': 'Lists',
            'code': 'Create fruits = ["apple", "banana", "cherry"]\nSay "Fruits: " + fruits\nSay "First: " + fruits[0]\n\nFor each fruit in fruits\n    Say "I like " + fruit\nEnd'
        },
        {
            'name': 'Classes',
            'code': 'Class Animal\n    Set name to "Unknown"\n    Set sound to "..."\n\n    Function speak\n        Return name + " says " + sound\n    End\nEnd\n\nCreate dog = new Animal()\ndog.name = "Rex"\ndog.sound = "Woof!"\nSay dog.speak()'
        },
        {
            'name': 'Try/Catch',
            'code': 'Try\n    Create result = 10 / 0\nCatch error\n    Say "Caught error: " + error\nEnd\n\nSay "Program continues!"'
        },
        {
            'name': 'Fibonacci',
            'code': 'Function fibonacci takes n\n    If n <= 1 Then\n        Return n\n    End\n    Return fibonacci(n - 1) + fibonacci(n - 2)\nEnd\n\nFor i from 0 to 10\n    Say "fib(" + i + ") = " + fibonacci(i)\nEnd'
        },
        {
            'name': 'FizzBuzz',
            'code': 'For i from 1 to 30\n    If i % 15 == 0 Then\n        Say "FizzBuzz"\n    Otherwise If i % 3 == 0 Then\n        Say "Fizz"\n    Otherwise If i % 5 == 0 Then\n        Say "Buzz"\n    Otherwise\n        Say i\n    End\nEnd'
        },
        {
            'name': 'Maps',
            'code': 'Create profile = Map with name = "Ada" and role = "builder"\nSay profile.name\nSay profile.role'
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

/* Assistant */
#assistant {
    flex: 1;
    padding: 14px;
    background: var(--bg);
    overflow: auto;
    display: none;
}
.assistant-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 100%;
}
.assistant-card {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    padding: 12px;
}
.assistant-card h4 {
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-dim);
    margin-bottom: 8px;
}
.assistant-card p,
.assistant-card li,
.assistant-card pre,
.assistant-card textarea {
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.6;
}
.assistant-card textarea {
    width: 100%;
    min-height: 88px;
    resize: vertical;
    padding: 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg);
    color: var(--text);
    outline: none;
}
.assistant-card textarea:focus { border-color: var(--accent); }
.assistant-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}
.assistant-actions .btn { font-size: 0.8em; }
.assistant-reply {
    white-space: pre-wrap;
    word-break: break-word;
}
.assistant-diagnostics {
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.assistant-diagnostic {
    border-left: 3px solid var(--border);
    padding-left: 10px;
}
.assistant-diagnostic.error { border-left-color: var(--red); }
.assistant-diagnostic.warning { border-left-color: var(--orange); }
.assistant-diagnostic.info,
.assistant-diagnostic.hint { border-left-color: var(--accent); }
.assistant-diagnostic strong {
    display: block;
    margin-bottom: 2px;
}
.assistant-code {
    white-space: pre-wrap;
    word-break: break-word;
}
.syntax-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
}
.syntax-section {
    border: 1px solid var(--border);
    border-radius: 6px;
    background: rgba(255,255,255,0.02);
    padding: 10px;
}
.syntax-section h5 {
    font-size: 0.82em;
    color: var(--accent);
    margin-bottom: 4px;
}
.syntax-section p {
    font-family: var(--font-sans);
    font-size: 0.78em;
    color: var(--text-dim);
    margin-bottom: 6px;
}
.syntax-section code {
    display: block;
    white-space: pre-wrap;
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 11px;
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
        <button class="btn" onclick="switchTab('assistant')" title="Open syntax-aware assistant">Assist</button>
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
                <div class="tab" data-tab="assistant" onclick="switchTab('assistant')">Assistant</div>
            </div>
            <span id="execTime"></span>
        </div>
        <div id="output"><span class="output-info">Press Run or Ctrl+Enter to execute your code.</span></div>
        <div id="transpiled"></div>
        <div id="assistant">
            <div class="assistant-stack">
                <div class="assistant-card">
                    <h4>Assistant Prompt</h4>
                    <textarea id="assistantPrompt" spellcheck="false" placeholder="Ask for help, for example: build a chatbot API, explain this code, fix this syntax, improve this route..."></textarea>
                    <div class="assistant-actions">
                        <button class="btn btn-primary" onclick="askAssistant('generate')">Generate</button>
                        <button class="btn" onclick="askAssistant('fix')">Fix</button>
                        <button class="btn" onclick="askAssistant('explain')">Explain</button>
                        <button class="btn" onclick="askAssistant('improve')">Improve</button>
                        <button class="btn" id="applyAssistantBtn" onclick="applyAssistantCode()" style="display:none;">Apply To Editor</button>
                    </div>
                </div>
                <div class="assistant-card">
                    <h4>Assistant Reply</h4>
                    <div id="assistantReply" class="assistant-reply">The assistant uses the real EPL parser and syntax guide, then checks generated code before returning it.</div>
                </div>
                <div class="assistant-card">
                    <h4>Suggested Code</h4>
                    <pre id="assistantCode" class="assistant-code">No suggestion yet.</pre>
                </div>
                <div class="assistant-card">
                    <h4>Diagnostics</h4>
                    <div id="assistantDiagnostics" class="assistant-diagnostics"><span class="output-info">Diagnostics will appear here.</span></div>
                </div>
                <div class="assistant-card">
                    <h4>Real EPL Syntax</h4>
                    <div id="syntaxGuide" class="syntax-grid"></div>
                </div>
            </div>
        </div>
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
const assistant = document.getElementById('assistant');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const execTime = document.getElementById('execTime');
const assistantPrompt = document.getElementById('assistantPrompt');
const assistantReply = document.getElementById('assistantReply');
const assistantCode = document.getElementById('assistantCode');
const assistantDiagnostics = document.getElementById('assistantDiagnostics');
const applyAssistantBtn = document.getElementById('applyAssistantBtn');

let latestAssistantCode = '';

assistantPrompt.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        askAssistant('auto');
    }
});

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

async function askAssistant(mode = 'auto') {
    const message = assistantPrompt.value.trim();
    const code = editor.value;
    if (!message && !code.trim()) return;

    switchTab('assistant');
    setStatus('running', 'Assistant...');
    assistantReply.textContent = 'Thinking with the real EPL syntax guide...';
    assistantCode.textContent = 'No suggestion yet.';
    assistantDiagnostics.innerHTML = '<span class="output-info">Analyzing...</span>';
    applyAssistantBtn.style.display = 'none';
    latestAssistantCode = '';

    try {
        const res = await fetch('/api/assist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, code, mode })
        });
        const data = await res.json();

        assistantReply.textContent = data.reply || 'No reply returned.';
        latestAssistantCode = data.code || '';
        assistantCode.textContent = latestAssistantCode || 'No code suggestion returned.';
        applyAssistantBtn.style.display = latestAssistantCode ? 'inline-flex' : 'none';
        renderDiagnostics(data.diagnostics || []);
        renderSyntaxGuide(data.syntax_sections || []);
        setStatus(data.syntax_ok === false ? 'error' : 'ready', data.syntax_ok === false ? 'Needs Review' : 'Assistant Ready');
    } catch (err) {
        assistantReply.textContent = 'Assistant error: ' + err.message;
        assistantDiagnostics.innerHTML = `<div class="assistant-diagnostic error"><strong>Request failed</strong>${escapeHtml(err.message)}</div>`;
        setStatus('error', 'Assistant Error');
    }
}

function applyAssistantCode() {
    if (!latestAssistantCode) return;
    editor.value = latestAssistantCode;
    updateLineInfo();
    setStatus('ready', 'Suggestion Applied');
}

function renderDiagnostics(diagnostics) {
    if (!diagnostics.length) {
        assistantDiagnostics.innerHTML = '<span class="output-success">No syntax issues found.</span>';
        return;
    }
    assistantDiagnostics.innerHTML = diagnostics.map(diag => {
        const level = escapeHtml(diag.level || 'info');
        const line = diag.line ? `Line ${diag.line}` : 'General';
        const code = diag.code ? ` (${escapeHtml(String(diag.code))})` : '';
        return `<div class="assistant-diagnostic ${level}"><strong>${line}${code}</strong>${escapeHtml(diag.message || '')}</div>`;
    }).join('');
}

function renderSyntaxGuide(sections) {
    const syntaxGuide = document.getElementById('syntaxGuide');
    if (!sections.length) {
        syntaxGuide.innerHTML = '<span class="output-info">Syntax guidance will appear here.</span>';
        return;
    }
    syntaxGuide.innerHTML = sections.map(section => {
        const examples = (section.examples || []).slice(0, 2).map(example => `<code>${escapeHtml(example)}</code>`).join('');
        return `<div class="syntax-section"><h5>${escapeHtml(section.title || '')}</h5><p>${escapeHtml(section.summary || '')}</p>${examples}</div>`;
    }).join('');
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
    assistant.style.display = tab === 'assistant' ? 'block' : 'none';
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

async function loadSyntaxGuide() {
    try {
        const res = await fetch('/api/syntax');
        const data = await res.json();
        renderSyntaxGuide((data && data.sections) || []);
    } catch (e) {
        console.error('Failed to load syntax guide:', e);
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
loadSyntaxGuide();
</script>
</body>
</html>
'''
