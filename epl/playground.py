"""
EPL Web Playground
==================
Browser-based IDE for trying EPL in seconds.
Usage:  python main.py playground [--port 8080]
"""

import contextlib
import io
import json
import os
import subprocess
import sys

from epl import _debug_log
from epl.errors import EPLError

PLAYGROUND_MAX_BODY_BYTES = 1_000_000
PLAYGROUND_EXEC_TIMEOUT_SECONDS = 10
_PLAYGROUND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _safe_error(e):
    """Return error message, sanitizing non-EPL exceptions."""
    return str(e) if isinstance(e, EPLError) else 'Internal error'


# ── Public API ───────────────────────────────────────────


def start_playground(port: int = 8080, open_browser: bool = True):
    """Start the EPL Web Playground server."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
            self.send_header('Cache-Control', 'no-store')
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
            if length > PLAYGROUND_MAX_BODY_BYTES:
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
            if length > PLAYGROUND_MAX_BODY_BYTES:
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
            if length > PLAYGROUND_MAX_BODY_BYTES:
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
            encoded = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(('127.0.0.1', port), PlaygroundHandler)
    print(f'  EPL Web Playground running at http://127.0.0.1:{port}')
    print('  Press Ctrl+C to stop')

    if open_browser:
        try:
            import webbrowser

            webbrowser.open(f'http://127.0.0.1:{port}')
        except Exception:
            _debug_log.suppressed('playground:152')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Playground stopped.')
        server.server_close()


# ── EPL Execution Engine ─────────────────────────────────


def _worker_environment():
    env = os.environ.copy()
    pythonpath = env.get('PYTHONPATH')
    if pythonpath:
        env['PYTHONPATH'] = os.pathsep.join([_PLAYGROUND_ROOT, pythonpath])
    else:
        env['PYTHONPATH'] = _PLAYGROUND_ROOT
    return env


def _execute_epl_worker_payload(code: str) -> dict:
    """Execute EPL code in an isolated worker process."""
    try:
        from epl.interpreter import Interpreter
        from epl.lexer import Lexer
        from epl.parser import Parser

        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        captured = io.StringIO()
        interp = Interpreter(safe_mode=True)
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            try:
                interp.execute(program)
                return {'output': captured.getvalue(), 'error': None}
            except SystemExit:
                return {'output': captured.getvalue(), 'error': None}
            except Exception as exc:
                return {'output': captured.getvalue(), 'error': _safe_error(exc)}
    except Exception as exc:
        return {'output': '', 'error': _safe_error(exc)}


def _playground_worker_main() -> int:
    """Subprocess entrypoint for isolated code execution."""
    try:
        payload = json.loads(sys.stdin.read() or '{}')
        result = _execute_epl_worker_payload(payload.get('code', ''))
    except Exception as exc:
        result = {'output': '', 'error': _safe_error(exc)}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    return 0


def _execute_epl(code: str) -> dict:
    """Execute EPL code in a subprocess so timeout is a real kill boundary."""
    if not code.strip():
        return {'output': '', 'error': None}

    try:
        completed = subprocess.run(
            [sys.executable, '-m', 'epl.playground', '--worker-run'],
            input=json.dumps({'code': code}),
            capture_output=True,
            text=True,
            timeout=PLAYGROUND_EXEC_TIMEOUT_SECONDS,
            cwd=_PLAYGROUND_ROOT,
            env=_worker_environment(),
        )
    except subprocess.TimeoutExpired:
        return {
            'output': '',
            'error': f'Execution timed out ({PLAYGROUND_EXEC_TIMEOUT_SECONDS}s limit)',
        }
    except Exception as exc:
        return {'output': '', 'error': _safe_error(exc)}

    if not completed.stdout.strip():
        return {'output': '', 'error': 'Internal error'}

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {'output': '', 'error': 'Internal error'}

    if not isinstance(result, dict):
        return {'output': '', 'error': 'Internal error'}
    return {
        'output': result.get('output', ''),
        'error': result.get('error'),
    }


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


def _assist_playground(message: str, code: str = '', mode: str = 'auto') -> dict:
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
        {'name': 'Hello World', 'code': 'Say "Hello, World!"\nSay "Welcome to EPL!"'},
        {
            'name': 'Variables & Math',
            'code': 'Create name = "Alice"\nCreate age = 25\nCreate score = 95.5\nSay "Name: " + name\nSay "Age: " + age\nSay "Score: " + score',
        },
        {
            'name': 'If/Else',
            'code': 'Create score = 85\n\nIf score > 90 Then\n    Say "Grade: A"\nOtherwise If score > 80 Then\n    Say "Grade: B"\nOtherwise\n    Say "Grade: C"\nEnd',
        },
        {
            'name': 'Loops',
            'code': 'Say "Counting:"\nRepeat 5 times\n    Say "Hello!"\nEnd\n\nFor i from 1 to 5\n    Say "Number: " + i\nEnd',
        },
        {
            'name': 'Functions',
            'code': 'Function greet takes name\n    Return "Hello, " + name + "!"\nEnd\n\nSay greet("Alice")\nSay greet("Bob")\n\nFunction add(a, b)\n    Return a + b\nEnd\n\nCreate result = add(10, 20)\nSay "10 + 20 = " + result',
        },
        {
            'name': 'Lists',
            'code': 'Create fruits = ["apple", "banana", "cherry"]\nSay "Fruits: " + fruits\nSay "First: " + fruits[0]\n\nFor each fruit in fruits\n    Say "I like " + fruit\nEnd',
        },
        {
            'name': 'Classes',
            'code': 'Class Animal\n    Set name to "Unknown"\n    Set sound to "..."\n\n    Function speak\n        Return name + " says " + sound\n    End\nEnd\n\nCreate dog = new Animal()\ndog.name = "Rex"\ndog.sound = "Woof!"\nSay dog.speak()',
        },
        {
            'name': 'Try/Catch',
            'code': 'Try\n    Create result = 10 / 0\nCatch error\n    Say "Caught error: " + error\nEnd\n\nSay "Program continues!"',
        },
        {
            'name': 'Fibonacci',
            'code': 'Function fibonacci takes n\n    If n <= 1 Then\n        Return n\n    End\n    Return fibonacci(n - 1) + fibonacci(n - 2)\nEnd\n\nFor i from 0 to 10\n    Say "fib(" + i + ") = " + fibonacci(i)\nEnd',
        },
        {
            'name': 'FizzBuzz',
            'code': 'For i from 1 to 30\n    If i % 15 == 0 Then\n        Say "FizzBuzz"\n    Otherwise If i % 3 == 0 Then\n        Say "Fizz"\n    Otherwise If i % 5 == 0 Then\n        Say "Buzz"\n    Otherwise\n        Say i\n    End\nEnd',
        },
        {
            'name': 'Maps',
            'code': 'Create profile = Map with name = "Ada" and role = "builder"\nSay profile.name\nSay profile.role',
        },
    ]


# ── HTML Template ────────────────────────────────────────

_PLAYGROUND_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light">
<title>EPL Playground — Run English Programming Language in your browser</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%23007DF3'/%3E%3Cstop offset='1' stop-color='%237C5CFF'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='32' height='32' rx='7' fill='url(%23g)'/%3E%3Ctext x='16' y='22' font-family='Arial' font-size='16' font-weight='700' fill='white' text-anchor='middle'%3EE%3C/text%3E%3C/svg%3E">
<meta name="description" content="Write and run EPL — the English Programming Language — in your browser. Sandboxed, instant, no install.">
<meta property="og:title" content="EPL Playground">
<meta property="og:description" content="Run English Programming Language in your browser — sandboxed and instant.">
<meta name="robots" content="index,follow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script type="importmap">
{
  "imports": {
    "@codemirror/state": "https://esm.sh/@codemirror/state@6.4.1",
    "@codemirror/view": "https://esm.sh/@codemirror/view@6.26.3?external=@codemirror/state",
    "@codemirror/commands": "https://esm.sh/@codemirror/commands@6.5.0?external=@codemirror/state,@codemirror/view",
    "@codemirror/language": "https://esm.sh/@codemirror/language@6.10.1?external=@codemirror/state,@codemirror/view",
    "@codemirror/autocomplete": "https://esm.sh/@codemirror/autocomplete@6.16.0?external=@codemirror/state,@codemirror/view,@codemirror/language",
    "@codemirror/theme-one-dark": "https://esm.sh/@codemirror/theme-one-dark@6.1.2?external=@codemirror/state,@codemirror/view,@codemirror/language"
  }
}
</script>
<style>
:root{
    --bg:#ffffff; --chrome:rgba(255,255,255,.82);
    --ink:#111113; --dim:#5f6066; --faint:#8a8b92;
    --line:rgba(17,17,19,.1); --line-soft:rgba(17,17,19,.06);
    --panel:#0d0f14; --panel-2:#0a0c10; --panel-line:rgba(255,255,255,.09);
    --code:#e6e7ea; --code-dim:#9aa0aa;
    --accent:#007DF3; --green:#21C7A8; --red:#FF5C7A; --amber:#FF9F45; --violet:#7C5CFF;
    --display:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    --mono:'JetBrains Mono','Cascadia Code','Fira Code',Consolas,monospace;
    --ease:cubic-bezier(.16,1,.3,1);
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%}
body{
    font-family:var(--sans); background:var(--bg); color:var(--ink);
    height:100vh; display:flex; flex-direction:column; overflow:hidden;
    -webkit-font-smoothing:antialiased;
}

/* ── Top nav ───────────────────────────────────────────── */
.pg-nav{
    display:flex; align-items:center; justify-content:space-between;
    gap:18px; padding:14px clamp(16px,3vw,30px);
    background:var(--chrome); backdrop-filter:saturate(160%) blur(16px);
    border-bottom:1px solid var(--line-soft); flex-shrink:0; z-index:5;
}
.pg-brand{display:flex; align-items:center; gap:12px; min-width:0}
.pg-mark{
    font-family:var(--display); font-weight:800; font-size:20px; letter-spacing:-.03em;
    background:linear-gradient(135deg,#007DF3,#7C5CFF); -webkit-background-clip:text;
    background-clip:text; -webkit-text-fill-color:transparent;
}
.pg-brand .sep{width:1px; height:20px; background:var(--line)}
.pg-title{font-family:var(--display); font-weight:600; font-size:15.5px; letter-spacing:-.01em}
.pg-badge{
    font-family:var(--mono); font-size:10.5px; letter-spacing:.06em; color:var(--dim);
    border:1px solid var(--line); border-radius:999px; padding:3px 10px; white-space:nowrap;
}
.pg-tools{display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end}
.pg-select, .pg-btn{
    font-family:var(--sans); font-size:13.5px; font-weight:500;
    border:1px solid var(--line); border-radius:10px; background:#fff; color:var(--ink);
    padding:9px 14px; cursor:pointer; transition:all .2s var(--ease); outline:none;
}
.pg-select:hover, .pg-btn:hover{border-color:var(--ink); transform:translateY(-1px)}
.pg-select{padding-right:30px; appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%235f6066' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat:no-repeat; background-position:right 12px center;
}
.pg-btn-ghost{background:transparent}
.pg-btn-primary{
    background:var(--ink); color:#fff; border-color:var(--ink); font-weight:600;
    display:inline-flex; align-items:center; gap:9px;
}
.pg-btn-primary:hover{background:#000; color:#fff}
.pg-btn-primary kbd{
    font-family:var(--mono); font-size:10.5px; background:rgba(255,255,255,.16);
    padding:2px 6px; border-radius:5px; color:#e6e7ea;
}
.pg-btn:disabled{opacity:.5; cursor:default; transform:none}

/* ── Stage ─────────────────────────────────────────────── */
.pg-stage{
    position:relative; flex:1; display:flex; min-height:0;
    padding:clamp(14px,2vw,26px); gap:clamp(14px,2vw,22px);
    background:
        radial-gradient(circle at 1px 1px, rgba(17,17,19,.05) 1px, transparent 1px);
    background-size:24px 24px;
}
.pg-stage::before{
    content:''; position:absolute; left:50%; top:54%; transform:translate(-50%,-50%);
    width:min(1100px,94%); height:64%; z-index:0;
    background:radial-gradient(ellipse at center, rgba(46,160,255,.13), rgba(124,92,255,.09) 45%, transparent 72%);
    filter:blur(34px); pointer-events:none;
}
.pg-pane{
    position:relative; z-index:1; display:flex; flex-direction:column; min-width:0;
    background:var(--panel); border:1px solid var(--panel-line); border-radius:16px;
    overflow:hidden; box-shadow:0 40px 90px -50px rgba(17,17,19,.5);
}
.pg-pane::before{
    content:''; position:absolute; top:0; left:0; right:0; height:2px; z-index:3;
    background:linear-gradient(90deg,#2EA0FF,#7C5CFF,#FF5C7A,#FF9F45,#FFD23F,#21C7A8);
    opacity:0; transition:opacity .45s var(--ease);
}
.pg-pane:focus-within::before{opacity:.9}
.pg-editor{flex:1.05}
.pg-output{flex:.95}
.pane-bar{
    display:flex; align-items:center; justify-content:space-between; gap:10px;
    padding:11px 16px; background:var(--panel-2); border-bottom:1px solid var(--panel-line);
    flex-shrink:0;
}
.pane-bar .file{
    display:flex; align-items:center; gap:9px;
    font-family:var(--mono); font-size:12.5px; color:var(--code-dim);
}
.pane-bar .dots{display:flex; gap:6px}
.pane-bar .dots i{width:11px; height:11px; border-radius:50%; background:rgba(255,255,255,.13)}
.pane-meta{font-family:var(--mono); font-size:11.5px; color:var(--faint)}

/* tabs */
.tabs{display:flex; gap:3px}
.tab{
    font-size:12.5px; font-weight:500; color:var(--code-dim);
    padding:5px 12px; border-radius:8px; cursor:pointer; transition:all .15s; user-select:none;
}
.tab:hover{background:rgba(255,255,255,.06); color:var(--code)}
.tab.active{background:rgba(46,160,255,.16); color:#7db8ff}

/* editor */
#editorHost{flex:1; min-height:0; overflow:hidden; background:var(--panel)}
.cm-editor{height:100%; background:transparent !important}
.cm-editor.cm-focused{outline:none !important}
.cm-scroller{font-family:var(--mono) !important; font-size:13.5px; line-height:1.7}
.cm-gutters{background:transparent !important; border-right:1px solid var(--panel-line) !important; color:var(--faint) !important}
#fallbackEditor{
    flex:1; width:100%; padding:16px 18px; border:none; outline:none; resize:none;
    font-family:var(--mono); font-size:13.5px; line-height:1.7; tab-size:4;
    background:var(--panel); color:var(--code);
}

/* output console */
.console{flex:1; min-height:0; overflow:auto; padding:16px 18px;
    font-family:var(--mono); font-size:13px; line-height:1.62; color:var(--code)}
.console::-webkit-scrollbar, #editorHost ::-webkit-scrollbar{width:10px; height:10px}
.console::-webkit-scrollbar-thumb, #editorHost ::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12); border-radius:8px}
.out-line{white-space:pre-wrap; word-break:break-word}
.out-err{color:var(--red); white-space:pre-wrap; word-break:break-word}
.out-ok{color:var(--green)}
.out-hint{color:var(--faint); font-style:italic}
/* NOTE: visibility is owned solely by .view-pane / .view-pane.active below.
   Do NOT add display:none to these #id rules — an id selector (1,0,0) outranks
   .view-pane.active (0,2,0), so the pane would stay hidden after switchView(). */
#transpiled{flex:1; min-height:0; overflow:auto; padding:16px 18px;
    font-family:var(--mono); font-size:13px; line-height:1.62; color:var(--code);
    white-space:pre-wrap; word-break:break-word}
#assistant{flex:1; min-height:0; overflow:auto; padding:14px}
.view-pane{display:none}
.view-pane.active{display:flex; flex-direction:column}

/* assistant */
.as-stack{display:flex; flex-direction:column; gap:12px}
.as-card{border:1px solid var(--panel-line); border-radius:12px; background:var(--panel-2); padding:13px 14px}
.as-card h4{font-size:11px; text-transform:uppercase; letter-spacing:.12em; color:var(--faint); margin-bottom:9px; font-family:var(--mono)}
.as-card p, .as-card li, .as-card pre{font-family:var(--mono); font-size:12px; line-height:1.6; color:var(--code)}
#assistantPrompt{width:100%; min-height:78px; resize:vertical; padding:10px 12px;
    border:1px solid var(--panel-line); border-radius:9px; background:var(--panel); color:var(--code);
    font-family:var(--mono); font-size:12.5px; outline:none}
#assistantPrompt:focus{border-color:var(--accent)}
.as-actions{display:flex; flex-wrap:wrap; gap:7px; margin-top:10px}
.as-btn{font-size:12px; font-weight:500; padding:7px 12px; border-radius:8px;
    border:1px solid var(--panel-line); background:var(--panel); color:var(--code); cursor:pointer; transition:all .15s}
.as-btn:hover{border-color:var(--accent); color:#7db8ff}
.as-btn.primary{background:var(--accent); color:#fff; border-color:var(--accent)}
.as-reply, .as-code{white-space:pre-wrap; word-break:break-word}
.as-diags{display:flex; flex-direction:column; gap:6px}
.as-diag{border-left:3px solid var(--panel-line); padding-left:10px}
.as-diag.error{border-left-color:var(--red)}
.as-diag.warning{border-left-color:var(--amber)}
.as-diag.info, .as-diag.hint{border-left-color:var(--accent)}
.as-diag strong{display:block; margin-bottom:2px}
.syntax-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:9px}
.syntax-section{border:1px solid var(--panel-line); border-radius:9px; background:var(--panel); padding:10px}
.syntax-section h5{font-size:12px; color:#7db8ff; margin-bottom:4px; font-family:var(--mono)}
.syntax-section p{font-family:var(--sans); font-size:11.5px; color:var(--code-dim); margin-bottom:6px}
.syntax-section code{display:block; white-space:pre-wrap; color:var(--code); font-family:var(--mono); font-size:11px}

/* status bar */
.pg-status{
    display:flex; align-items:center; justify-content:space-between; gap:12px;
    padding:8px clamp(16px,3vw,30px); background:var(--chrome);
    border-top:1px solid var(--line-soft); font-size:12px; color:var(--dim); flex-shrink:0;
    backdrop-filter:saturate(160%) blur(16px);
}
.st-left{display:flex; align-items:center; gap:9px}
.dot{width:8px; height:8px; border-radius:50%; background:var(--green); flex-shrink:0}
.dot.running{background:var(--amber); animation:pulse 1s infinite}
.dot.error{background:var(--red)}
.dot.ready{background:var(--green)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.st-right{font-family:var(--mono); font-size:11px; color:var(--faint); display:flex; align-items:center; gap:14px}

/* responsive */
@media(max-width:860px){
    .pg-stage{flex-direction:column}
    .pg-title{display:none}
}
@media(max-width:560px){
    .pg-badge, .pg-btn-primary kbd{display:none}
    .pg-tools{gap:7px}
}
</style>
</head>
<body>

<nav class="pg-nav">
    <div class="pg-brand">
        <span class="pg-mark">EPL</span>
        <span class="sep"></span>
        <span class="pg-title">Playground</span>
        <span class="pg-badge" id="verBadge">safe sandbox</span>
    </div>
    <div class="pg-tools">
        <select class="pg-select" id="exampleSelect" title="Load an example" aria-label="Load an example">
            <option value="">Examples…</option>
        </select>
        <select class="pg-select" id="transpileTarget" title="Transpile target" aria-label="Transpile target">
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
        </select>
        <button class="pg-btn pg-btn-ghost" onclick="transpileCode()" title="Transpile code">Transpile</button>
        <button class="pg-btn pg-btn-ghost" onclick="switchView('assistant')" title="Open the syntax-aware assistant">Assistant</button>
        <button class="pg-btn pg-btn-ghost" onclick="clearConsole()" title="Clear the console">Clear</button>
        <button class="pg-btn pg-btn-primary" id="runBtn" onclick="runCode()" title="Run (Ctrl/Cmd+Enter)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
            Run <kbd>⌘↵</kbd>
        </button>
    </div>
</nav>

<main class="pg-stage">
    <section class="pg-pane pg-editor">
        <div class="pane-bar">
            <span class="file"><span class="dots"><i></i><i></i><i></i></span> main.epl</span>
            <span class="pane-meta" id="lineInfo">Ln 1, Col 1</span>
        </div>
        <div id="editorHost"></div>
    </section>

    <section class="pg-pane pg-output">
        <div class="pane-bar">
            <div class="tabs">
                <div class="tab active" data-view="output" onclick="switchView('output')">Output</div>
                <div class="tab" data-view="transpiled" onclick="switchView('transpiled')">Transpiled</div>
                <div class="tab" data-view="assistant" onclick="switchView('assistant')">Assistant</div>
            </div>
            <span class="pane-meta" id="execTime"></span>
        </div>

        <div class="console view-pane active" id="output"><span class="out-hint">Press Run (or ⌘/Ctrl + Enter) to execute your EPL.</span></div>
        <pre id="transpiled" class="view-pane"></pre>

        <div id="assistant" class="view-pane">
            <div class="as-stack">
                <div class="as-card">
                    <h4>Ask the assistant</h4>
                    <textarea id="assistantPrompt" spellcheck="false" placeholder="e.g. build a chatbot API, explain this code, fix this syntax, improve this route…"></textarea>
                    <div class="as-actions">
                        <button class="as-btn primary" onclick="askAssistant('generate')">Generate</button>
                        <button class="as-btn" onclick="askAssistant('fix')">Fix</button>
                        <button class="as-btn" onclick="askAssistant('explain')">Explain</button>
                        <button class="as-btn" onclick="askAssistant('improve')">Improve</button>
                        <button class="as-btn" id="applyAssistantBtn" onclick="applyAssistantCode()" style="display:none">Apply to editor</button>
                    </div>
                </div>
                <div class="as-card"><h4>Reply</h4><div id="assistantReply" class="as-reply">The assistant uses the real EPL parser and syntax guide, then checks generated code before returning it.</div></div>
                <div class="as-card"><h4>Suggested code</h4><pre id="assistantCode" class="as-code">No suggestion yet.</pre></div>
                <div class="as-card"><h4>Diagnostics</h4><div id="assistantDiagnostics" class="as-diags"><span class="out-hint">Diagnostics will appear here.</span></div></div>
                <div class="as-card"><h4>EPL syntax</h4><div id="syntaxGuide" class="syntax-grid"></div></div>
            </div>
        </div>
    </section>
</main>

<footer class="pg-status">
    <span class="st-left"><span class="dot ready" id="statusDot"></span><span id="statusText">Ready</span></span>
    <span class="st-right"><span>English Programming Language</span><span>Safe Mode · 10s limit</span></span>
</footer>

<script type="module">
import {EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, dropCursor} from "@codemirror/view";
import {EditorState} from "@codemirror/state";
import {defaultKeymap, history, historyKeymap, indentWithTab} from "@codemirror/commands";
import {StreamLanguage, syntaxHighlighting, defaultHighlightStyle, bracketMatching, indentOnInput} from "@codemirror/language";
import {closeBrackets} from "@codemirror/autocomplete";
import {oneDark} from "@codemirror/theme-one-dark";

window.__cmReady = (async () => {
    // Lightweight EPL highlighter
    const KW = new Set(("create webapp app route page section div span nav header footer heading text link button image list item form input field label end if else elif while for each in repeat times function define return set to let print display show shows send json responds with called import use class new true false null and or not is equals then do try catch throw break continue of as from match when stylesheet script meta font favicon note segment style query map get post put delete handler module export const var").split(" "));
    const eplLang = StreamLanguage.define({
        token(stream){
            if(stream.match(/^Note:.*/)) return "comment";
            if(stream.sol() && stream.match(/^#.*/)) return "comment";
            if(stream.match(/^"(?:[^"\\]|\\.)*"?/)) return "string";
            if(stream.match(/^'(?:[^'\\]|\\.)*'?/)) return "string";
            if(stream.match(/^-?\d+(?:\.\d+)?/)) return "number";
            if(stream.match(/^[A-Za-z_][\w-]*/)){
                const w = stream.current().toLowerCase();
                if(KW.has(w)) return "keyword";
                if(/^[A-Z]/.test(stream.current())) return "typeName";
                return "variableName";
            }
            stream.next();
            return null;
        }
    });
    const lineInfoEl = document.getElementById('lineInfo');
    const updateListener = EditorView.updateListener.of(v => {
        if(v.selectionSet || v.docChanged){
            const head = v.state.selection.main.head;
            const line = v.state.doc.lineAt(head);
            lineInfoEl.textContent = `Ln ${line.number}, Col ${head - line.from + 1}`;
        }
    });
    const runKeys = keymap.of([{ key: "Mod-Enter", preventDefault: true, run(){ window.runCode && window.runCode(); return true; } }]);
    const theme = EditorView.theme({
        "&": { color: "#e6e7ea", backgroundColor: "transparent" },
        ".cm-content": { caretColor: "#2EA0FF", padding: "14px 0" },
        ".cm-cursor": { borderLeftColor: "#2EA0FF" },
        ".cm-activeLine": { backgroundColor: "rgba(255,255,255,.035)" },
        ".cm-activeLineGutter": { backgroundColor: "rgba(255,255,255,.04)" },
        ".cm-gutters": { backgroundColor: "transparent", border: "none", color: "#8a8b92" },
        ".cm-line": { padding: "0 16px" }
    }, { dark: true });

    const view = new EditorView({
        state: EditorState.create({
            doc: 'Print "Hello from EPL"\n',
            extensions: [
                lineNumbers(), highlightActiveLineGutter(), history(), drawSelection(), dropCursor(),
                indentOnInput(), bracketMatching(), closeBrackets(), highlightActiveLine(),
                syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
                eplLang, oneDark, theme, updateListener, runKeys,
                keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab])
            ]
        }),
        parent: document.getElementById('editorHost')
    });
    window.__cmView = view;
    return view;
})().catch(err => { console.warn('CodeMirror failed, using fallback editor:', err); window.__cmView = null; return null; });
</script>

<script type="module">
// ── Editor abstraction (CodeMirror with textarea fallback) ──
let cmView = null;
let fallbackTA = null;

function getCode(){
    if(cmView) return cmView.state.doc.toString();
    if(fallbackTA) return fallbackTA.value;
    return '';
}
function setCode(text){
    if(cmView){ cmView.dispatch({ changes: { from: 0, to: cmView.state.doc.length, insert: text } }); cmView.focus(); }
    else if(fallbackTA){ fallbackTA.value = text; updateLineInfoTA(); }
}

function mountFallback(initial){
    const host = document.getElementById('editorHost');
    host.innerHTML = '';
    fallbackTA = document.createElement('textarea');
    fallbackTA.id = 'fallbackEditor';
    fallbackTA.spellcheck = false;
    fallbackTA.value = initial || 'Print "Hello from EPL"\n';
    host.appendChild(fallbackTA);
    fallbackTA.addEventListener('keydown', e => {
        if(e.key === 'Tab'){ e.preventDefault(); const s=fallbackTA.selectionStart, en=fallbackTA.selectionEnd;
            fallbackTA.value = fallbackTA.value.slice(0,s)+'    '+fallbackTA.value.slice(en); fallbackTA.selectionStart=fallbackTA.selectionEnd=s+4; }
        if(e.key === 'Enter' && (e.ctrlKey||e.metaKey)){ e.preventDefault(); runCode(); }
    });
    fallbackTA.addEventListener('keyup', updateLineInfoTA);
    fallbackTA.addEventListener('click', updateLineInfoTA);
}
function updateLineInfoTA(){
    if(!fallbackTA) return;
    const pos = fallbackTA.selectionStart;
    const lines = fallbackTA.value.substring(0,pos).split('\n');
    document.getElementById('lineInfo').textContent = `Ln ${lines.length}, Col ${lines[lines.length-1].length+1}`;
}

// element refs
const output = document.getElementById('output');
const transpiled = document.getElementById('transpiled');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const execTime = document.getElementById('execTime');
const runBtn = document.getElementById('runBtn');
const assistantPrompt = document.getElementById('assistantPrompt');
const assistantReply = document.getElementById('assistantReply');
const assistantCode = document.getElementById('assistantCode');
const assistantDiagnostics = document.getElementById('assistantDiagnostics');
const applyAssistantBtn = document.getElementById('applyAssistantBtn');
let latestAssistantCode = '';
let examplesCache = [];

function setStatus(state, text){ statusDot.className = 'dot ' + state; statusText.textContent = text; }
function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function switchView(view){
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
    document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
    const el = document.getElementById(view);
    if(el) el.classList.add('active');
}

async function runCode(){
    const code = getCode().trim();
    if(!code){ return; }
    setStatus('running','Running…'); runBtn.disabled = true;
    output.innerHTML = ''; switchView('output');
    const start = performance.now();
    try{
        const res = await fetch('/api/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ code }) });
        const data = await res.json();
        execTime.textContent = ((performance.now()-start)/1000).toFixed(2) + 's';
        let html = '';
        if(data.output){ html += escapeHtml(data.output).split('\n').map(l => `<div class="out-line">${l}</div>`).join(''); }
        if(data.error){ html += `<div class="out-err">${escapeHtml(data.error)}</div>`; setStatus('error','Error'); }
        else { setStatus('ready','Done'); if(!data.output) html = '<span class="out-ok">Program finished with no output.</span>'; }
        output.innerHTML = html;
    }catch(err){
        output.innerHTML = `<div class="out-err">Connection error: ${escapeHtml(err.message)}</div>`;
        setStatus('error','Error');
    }finally{ runBtn.disabled = false; }
}

async function transpileCode(){
    const code = getCode().trim();
    if(!code) return;
    const target = document.getElementById('transpileTarget').value;
    switchView('transpiled');
    transpiled.textContent = 'Transpiling…';
    try{
        const res = await fetch('/api/transpile', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ code, target }) });
        const data = await res.json();
        if(data.error){ transpiled.innerHTML = `<span class="out-err">${escapeHtml(data.error)}</span>`; }
        else { transpiled.textContent = data.code || '(no output)'; }
    }catch(err){ transpiled.innerHTML = `<span class="out-err">${escapeHtml(err.message)}</span>`; }
}

async function askAssistant(mode='auto'){
    const message = assistantPrompt.value.trim();
    const code = getCode();
    if(!message && !code.trim()) return;
    switchView('assistant'); setStatus('running','Assistant…');
    assistantReply.textContent = 'Thinking with the real EPL syntax guide…';
    assistantCode.textContent = 'No suggestion yet.';
    assistantDiagnostics.innerHTML = '<span class="out-hint">Analyzing…</span>';
    applyAssistantBtn.style.display = 'none'; latestAssistantCode = '';
    try{
        const res = await fetch('/api/assist', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ message, code, mode }) });
        const data = await res.json();
        assistantReply.textContent = data.reply || 'No reply returned.';
        latestAssistantCode = data.code || '';
        assistantCode.textContent = latestAssistantCode || 'No code suggestion returned.';
        applyAssistantBtn.style.display = latestAssistantCode ? 'inline-flex' : 'none';
        renderDiagnostics(data.diagnostics || []);
        renderSyntaxGuide(data.syntax_sections || []);
        setStatus(data.syntax_ok === false ? 'error' : 'ready', data.syntax_ok === false ? 'Needs review' : 'Assistant ready');
    }catch(err){
        assistantReply.textContent = 'Assistant error: ' + err.message;
        assistantDiagnostics.innerHTML = `<div class="as-diag error"><strong>Request failed</strong>${escapeHtml(err.message)}</div>`;
        setStatus('error','Assistant error');
    }
}
function applyAssistantCode(){ if(!latestAssistantCode) return; setCode(latestAssistantCode); setStatus('ready','Suggestion applied'); }
function renderDiagnostics(d){
    if(!d.length){ assistantDiagnostics.innerHTML = '<span class="out-ok">No syntax issues found.</span>'; return; }
    assistantDiagnostics.innerHTML = d.map(x => {
        const level = escapeHtml(x.level || 'info');
        const line = x.line ? `Line ${x.line}` : 'General';
        const code = x.code ? ` (${escapeHtml(String(x.code))})` : '';
        return `<div class="as-diag ${level}"><strong>${line}${code}</strong>${escapeHtml(x.message || '')}</div>`;
    }).join('');
}
function renderSyntaxGuide(sections){
    const g = document.getElementById('syntaxGuide');
    if(!sections.length){ g.innerHTML = '<span class="out-hint">Syntax guidance will appear here.</span>'; return; }
    g.innerHTML = sections.map(s => {
        const ex = (s.examples || []).slice(0,2).map(e => `<code>${escapeHtml(e)}</code>`).join('');
        return `<div class="syntax-section"><h5>${escapeHtml(s.title || '')}</h5><p>${escapeHtml(s.summary || '')}</p>${ex}</div>`;
    }).join('');
}
function clearConsole(){ output.innerHTML = '<span class="out-hint">Console cleared.</span>'; transpiled.textContent=''; execTime.textContent=''; switchView('output'); setStatus('ready','Ready'); }

// expose for inline handlers + the module script
window.runCode = runCode; window.transpileCode = transpileCode; window.switchView = switchView;
window.askAssistant = askAssistant; window.applyAssistantCode = applyAssistantCode; window.clearConsole = clearConsole;

// ── Examples ──
async function loadExamples(){
    try{
        const res = await fetch('/api/examples');
        examplesCache = await res.json();
        const sel = document.getElementById('exampleSelect');
        examplesCache.forEach((ex,i) => { const o = document.createElement('option'); o.value = String(i); o.textContent = ex.name; sel.appendChild(o); });
        sel.addEventListener('change', () => { const i = sel.value; if(i === '') return; const ex = examplesCache[Number(i)]; if(ex){ setCode(ex.code); } });
        // seed editor with the first example for an immediately-runnable default
        if(examplesCache[0] && examplesCache[0].code){ setCode(examplesCache[0].code); }
    }catch(e){ console.error('Failed to load examples:', e); }
}
async function loadSyntaxGuide(){
    try{ const res = await fetch('/api/syntax'); const data = await res.json(); renderSyntaxGuide((data && data.sections) || []); }
    catch(e){ console.error('Failed to load syntax guide:', e); }
}

// ── Boot: wait for CodeMirror (or fall back), then wire data ──
(async function boot(){
    let view = null;
    if(window.__cmReady){ try { view = await window.__cmReady; } catch(e){ view = null; } }
    cmView = view || (window.__cmView || null);
    if(!cmView){ mountFallback('Print "Hello from EPL"\n'); }
    await loadExamples();
    loadSyntaxGuide();
    setStatus('ready','Ready');
})();
</script>
</body>
</html>
"""


if __name__ == '__main__':
    if '--worker-run' in sys.argv:
        raise SystemExit(_playground_worker_main())
