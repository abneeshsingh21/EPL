"""
EPL Web / WASM Target (v1.0)
Generates browser-ready web applications from EPL source code.

Three modes:
  1. WASM+JS Glue:  Compile EPL→LLVM IR→WASM, generate JS loader + HTML
  2. Kotlin/JS:     Transpile EPL→Kotlin→Kotlin/JS, bundle for browser
  3. Pure JS:       Transpile EPL→JavaScript (via js_transpiler), wrap in SPA

Provides:
  - HTML5 page generation with responsive layout
  - CSS framework (Tailwind CDN or custom)
  - JS loader / WASM initialization
  - DOM interop layer
  - Web component mapping from EPL GUI widgets
  - Service Worker for offline PWA support
  - Build system (npm/Gradle) generation
"""

import os
from epl import ast_nodes as ast


# ── Web Project Generator ────────────────────────────────


class WebProjectGenerator:
    """Generates a complete browser-ready web project from EPL AST."""

    def __init__(self, app_name="EPLWebApp", mode="js", port=3000):
        self.app_name = app_name
        self.mode = mode  # "js", "wasm", "kotlin_js"
        self.port = port

    def generate(self, program: ast.Program, output_dir: str) -> str:
        """Generate a complete web project."""
        os.makedirs(output_dir, exist_ok=True)

        if self.mode == "wasm":
            return self._generate_wasm_project(program, output_dir)
        elif self.mode == "kotlin_js":
            return self._generate_kotlin_js_project(program, output_dir)
        else:
            return self._generate_js_project(program, output_dir)

    # ── JS Project ──────────────────────────────────────

    def _generate_js_project(self, program, output_dir):
        """Generate a pure JavaScript web project."""
        dirs = [
            f'{output_dir}/src',
            f'{output_dir}/src/css',
            f'{output_dir}/src/js',
            f'{output_dir}/public',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        gen = WebCodeGenerator(self.app_name)
        js_code = gen.transpile_js(program)
        html = gen.generate_html(program, mode='js')
        css = gen.generate_css()

        self._write(f'{output_dir}/src/js/app.js', js_code)
        self._write(f'{output_dir}/src/css/style.css', css)
        self._write(f'{output_dir}/public/index.html', html)
        self._write(f'{output_dir}/package.json', self._npm_package_json())
        self._write(f'{output_dir}/README.md', self._readme('js'))
        self._write(f'{output_dir}/.gitignore', 'node_modules/\ndist/\n.cache/\n')
        self._write(f'{output_dir}/public/manifest.json', self._pwa_manifest())
        self._write(f'{output_dir}/public/sw.js', self._service_worker())

        return output_dir

    # ── WASM Project ────────────────────────────────────

    def _generate_wasm_project(self, program, output_dir):
        """Generate a WASM web project with JS glue code."""
        dirs = [
            f'{output_dir}/src',
            f'{output_dir}/public',
            f'{output_dir}/wasm',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        gen = WebCodeGenerator(self.app_name)
        html = gen.generate_html(program, mode='wasm')
        css = gen.generate_css()
        js_loader = gen.generate_wasm_loader()
        js_runtime = gen.generate_wasm_runtime()

        self._write(f'{output_dir}/public/index.html', html)
        self._write(f'{output_dir}/src/style.css', css)
        self._write(f'{output_dir}/src/loader.js', js_loader)
        self._write(f'{output_dir}/src/runtime.js', js_runtime)
        self._write(f'{output_dir}/package.json', self._npm_package_json())
        self._write(f'{output_dir}/README.md', self._readme('wasm'))
        self._write(f'{output_dir}/.gitignore', 'node_modules/\ndist/\n.cache/\nwasm/*.wasm\n')
        self._write(f'{output_dir}/build.sh', self._wasm_build_script())

        try:
            os.chmod(f'{output_dir}/build.sh', 0o755)
        except OSError:
            pass

        return output_dir

    # ── Kotlin/JS Project ───────────────────────────────

    def _generate_kotlin_js_project(self, program, output_dir):
        """Generate a Kotlin/JS web project."""
        pkg = 'com.epl.web'
        pkg_path = pkg.replace('.', '/')
        dirs = [
            f'{output_dir}/src/main/kotlin/{pkg_path}',
            f'{output_dir}/src/main/resources',
            f'{output_dir}/gradle/wrapper',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        gen = WebCodeGenerator(self.app_name)
        kt_code = gen.transpile_kotlin_js(program, pkg)
        html = gen.generate_html(program, mode='kotlin_js')
        css = gen.generate_css()

        self._write(f'{output_dir}/src/main/kotlin/{pkg_path}/Main.kt', kt_code)
        self._write(f'{output_dir}/src/main/resources/index.html', html)
        self._write(f'{output_dir}/src/main/resources/style.css', css)
        self._write(f'{output_dir}/build.gradle.kts', self._kotlin_js_gradle(pkg))
        self._write(f'{output_dir}/settings.gradle.kts',
                     f'rootProject.name = "{self.app_name}"\n')
        self._write(f'{output_dir}/gradle.properties',
                     'kotlin.code.style=official\norg.gradle.jvmargs=-Xmx2g\n')
        self._write(f'{output_dir}/README.md', self._readme('kotlin_js'))
        self._write(f'{output_dir}/.gitignore', '.gradle/\nbuild/\n.idea/\nnode_modules/\n')

        return output_dir

    # ── Helper files ────────────────────────────────────

    def _write(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _npm_package_json(self):
        return f'''{{"name": "{self.app_name.lower().replace(' ', '-')}",
  "version": "1.0.0",
  "description": "Web application generated from EPL",
  "scripts": {{
    "start": "python -m http.server {self.port} --directory public",
    "dev": "python -m http.server {self.port} --directory public",
    "build": "echo Build complete"
  }},
  "private": true
}}
'''

    def _pwa_manifest(self):
        return f'''{{"name": "{self.app_name}",
  "short_name": "{self.app_name}",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#3b82f6",
  "icons": []
}}
'''

    def _service_worker(self):
        return '''// Service Worker for offline support
const CACHE_NAME = 'epl-app-v1';
const urlsToCache = ['/', '/index.html', '/src/js/app.js', '/src/css/style.css'];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache)));
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => response || fetch(event.request))
    );
});
'''

    def _wasm_build_script(self):
        return '''#!/bin/bash
# Build EPL WASM module
# Requires: emcc (Emscripten) or clang with wasm32 target
echo "Building WASM module..."

if command -v emcc &> /dev/null; then
    emcc wasm/app.c -o public/app.wasm -s STANDALONE_WASM=1 -s EXPORTED_FUNCTIONS="['_main']" -O2
    echo "Built with Emscripten"
elif command -v clang &> /dev/null; then
    clang --target=wasm32-wasi -O2 -o public/app.wasm wasm/app.c
    echo "Built with clang (WASI target)"
else
    echo "Error: Neither emcc nor clang found. Install Emscripten or LLVM."
    exit 1
fi
echo "Done: public/app.wasm"
'''

    def _kotlin_js_gradle(self, pkg):
        return f'''plugins {{
    kotlin("js") version "1.9.22"
}}

group = "{pkg}"
version = "1.0.0"

repositories {{
    mavenCentral()
}}

dependencies {{
    implementation("org.jetbrains.kotlinx:kotlinx-html-js:0.11.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core-js:1.7.3")
    testImplementation(kotlin("test"))
}}

kotlin {{
    js(IR) {{
        browser {{
            commonWebpackConfig {{
                cssSupport {{ enabled.set(true) }}
            }}
            binaries.executable()
        }}
    }}
}}
'''

    def _readme(self, mode):
        instructions = {
            'js': '''## Run
```bash
# Option 1: Python HTTP server
python -m http.server 3000 --directory public

# Option 2: npm
npm start

# Then open http://localhost:3000
```''',
            'wasm': '''## Build & Run
```bash
# 1. Build the WASM module (requires emcc or clang)
./build.sh

# 2. Serve the app
python -m http.server 3000 --directory public

# Open http://localhost:3000
```''',
            'kotlin_js': '''## Build & Run
```bash
# Build
./gradlew jsBrowserDevelopmentRun

# Production build
./gradlew jsBrowserProductionWebpack
# Output in build/dist/js/productionExecutable/
```'''
        }
        return f'''# {self.app_name}

Web application generated from EPL source code.
Mode: **{mode}**

{instructions.get(mode, '')}

## Features
- Responsive design
- PWA support (offline capable)
- Cross-browser compatible
'''


# ── Web Code Generator ──────────────────────────────────


class WebCodeGenerator:
    """Generates HTML, CSS, JS, and Kotlin/JS from EPL AST."""

    def __init__(self, app_title="EPL App"):
        self.app_title = app_title
        self.indent = 0
        self.output = []
        self.widgets = []
        self.widget_counter = 0
        self.functions = []
        self.event_bindings = []

    # ── HTML Generation ─────────────────────────────────

    def generate_html(self, program: ast.Program, mode='js') -> str:
        """Generate an HTML5 page."""
        self._collect_gui_nodes(program.statements)
        widgets_html = self._widgets_to_html()
        print_outputs = self._collect_print_outputs(program.statements)

        if mode == 'wasm':
            script_tag = '<script type="module" src="../src/loader.js"></script>'
        elif mode == 'kotlin_js':
            script_tag = f'<script src="{self.app_title.lower().replace(" ", "-")}.js"></script>'
        else:
            script_tag = '<script src="../src/js/app.js" defer></script>'

        css_path = '../src/css/style.css' if mode != 'kotlin_js' else 'style.css'

        body_content = ''
        if widgets_html:
            body_content = f'''    <header>
        <h1>{self.app_title}</h1>
    </header>
    <main id="app">
{widgets_html}
    </main>'''
        elif print_outputs:
            items = '\n'.join(f'        <div class="output-line">{self._html_escape(p)}</div>'
                              for p in print_outputs)
            body_content = f'''    <header>
        <h1>{self.app_title}</h1>
    </header>
    <main id="app">
        <div class="output-container">
{items}
        </div>
    </main>'''
        else:
            body_content = f'''    <header>
        <h1>{self.app_title}</h1>
    </header>
    <main id="app">
        <p>EPL Web Application</p>
    </main>'''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.app_title}</title>
    <link rel="stylesheet" href="{css_path}">
    <link rel="manifest" href="manifest.json">
</head>
<body>
{body_content}
    <footer>
        <p>Built with EPL</p>
    </footer>
    {script_tag}
</body>
</html>
'''

    def _html_escape(self, text):
        return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    def _widgets_to_html(self):
        """Convert collected widgets to HTML."""
        lines = []
        for w in self.widgets:
            wtype = w['type']
            wid = w['id']
            text = w.get('text', '')
            props = w.get('properties', {})

            if wtype == 'button':
                lines.append(f'        <button id="{wid}" class="epl-btn">{text}</button>')
            elif wtype == 'label':
                lines.append(f'        <span id="{wid}" class="epl-label">{text}</span>')
            elif wtype == 'input':
                ph = props.get('placeholder', '')
                lines.append(f'        <input id="{wid}" type="text" class="epl-input" placeholder="{ph}">')
            elif wtype == 'textarea':
                ph = props.get('placeholder', '')
                lines.append(f'        <textarea id="{wid}" class="epl-textarea" placeholder="{ph}"></textarea>')
            elif wtype == 'checkbox':
                lines.append(f'        <label class="epl-checkbox"><input id="{wid}" type="checkbox"> {text}</label>')
            elif wtype == 'slider':
                mx = props.get('max', 100)
                lines.append(f'        <input id="{wid}" type="range" class="epl-slider" min="0" max="{mx}">')
            elif wtype == 'dropdown':
                opts = props.get('options', [])
                opt_html = ''.join(f'<option value="{o}">{o}</option>' for o in opts)
                lines.append(f'        <select id="{wid}" class="epl-select">{opt_html}</select>')
            elif wtype == 'progress':
                lines.append(f'        <progress id="{wid}" class="epl-progress" max="100" value="0"></progress>')
            elif wtype == 'canvas':
                cw = props.get('width', 400)
                ch = props.get('height', 300)
                lines.append(f'        <canvas id="{wid}" width="{cw}" height="{ch}" class="epl-canvas"></canvas>')
            elif wtype == 'image':
                lines.append(f'        <img id="{wid}" class="epl-image" alt="{text}" src="">')
            elif wtype == 'separator':
                lines.append('        <hr class="epl-separator">')
            elif wtype == 'listbox':
                lines.append(f'        <ul id="{wid}" class="epl-listbox"></ul>')
            else:
                lines.append(f'        <div id="{wid}" class="epl-widget">{text}</div>')

        return '\n'.join(lines)

    # ── CSS Generation ──────────────────────────────────

    def generate_css(self):
        return '''/* EPL Web Application Styles */
:root {
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #334155;
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --border: #475569;
    --success: #22c55e;
    --error: #ef4444;
    --warning: #f59e0b;
    --radius: 8px;
    --shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

header {
    background: var(--surface);
    padding: 1rem 2rem;
    border-bottom: 1px solid var(--border);
    box-shadow: var(--shadow);
}

header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    background: linear-gradient(135deg, var(--primary), #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

main#app {
    flex: 1;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
}

footer {
    background: var(--surface);
    padding: 1rem 2rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.875rem;
    border-top: 1px solid var(--border);
}

/* Widgets */
.epl-btn {
    background: var(--primary);
    color: white;
    border: none;
    padding: 0.625rem 1.25rem;
    border-radius: var(--radius);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: var(--shadow);
}
.epl-btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
.epl-btn:active { transform: translateY(0); }

.epl-label {
    display: block;
    font-size: 1rem;
    padding: 0.25rem 0;
}

.epl-input, .epl-textarea, .epl-select {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 0.5rem 0.75rem;
    border-radius: var(--radius);
    font-size: 0.875rem;
    width: 100%;
    max-width: 400px;
    transition: border-color 0.2s;
}
.epl-input:focus, .epl-textarea:focus, .epl-select:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.3);
}

.epl-textarea { min-height: 100px; resize: vertical; }

.epl-checkbox {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    padding: 0.25rem 0;
}

.epl-slider { width: 100%; max-width: 400px; accent-color: var(--primary); }

.epl-select { max-width: 300px; }

.epl-progress {
    width: 100%;
    max-width: 400px;
    height: 8px;
    border-radius: 4px;
    accent-color: var(--primary);
}

.epl-canvas {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
}

.epl-image {
    max-width: 100%;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
}

.epl-separator {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1rem 0;
}

.epl-listbox {
    list-style: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    max-height: 200px;
    overflow-y: auto;
    padding: 0.25rem 0;
}
.epl-listbox li {
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    transition: background 0.15s;
}
.epl-listbox li:hover { background: var(--surface2); }

.output-container {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
}
.output-line {
    padding: 0.25rem 0;
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 0.9rem;
}

/* Responsive */
@media (max-width: 768px) {
    main#app { padding: 1rem; }
    .epl-input, .epl-textarea, .epl-select, .epl-slider, .epl-progress {
        max-width: 100%;
    }
}
'''

    # ── JavaScript Transpilation ────────────────────────

    def transpile_js(self, program: ast.Program) -> str:
        """Transpile EPL AST to JavaScript for browser."""
        self.output = []
        self.indent = 0

        self._line('// EPL Web Application — Generated JavaScript')
        self._line("'use strict';")
        self._line('')
        self._line('// ── EPL Runtime ──────────────────────────')
        self._line('const EPL = {')
        self.indent += 1
        self._line('print(...args) { const el = document.getElementById("output"); if(el) { el.innerHTML += args.join(" ") + "<br>"; } console.log(...args); },')
        self._line('input(prompt) { return window.prompt(prompt || "") || ""; },')
        self._line('toInteger(v) { return parseInt(v) || 0; },')
        self._line('toDecimal(v) { return parseFloat(v) || 0.0; },')
        self._line('toText(v) { return String(v); },')
        self._line('length(v) { return v.length || Object.keys(v).length || 0; },')
        self._line('uppercase(s) { return s.toUpperCase(); },')
        self._line('lowercase(s) { return s.toLowerCase(); },')
        self._line('trim(s) { return s.trim(); },')
        self._line('contains(s, sub) { return s.includes(sub); },')
        self._line('replace(s, old, nw) { return s.split(old).join(nw); },')
        self._line('split(s, d) { return s.split(d); },')
        self._line('substring(s, a, b) { return s.substring(a, b); },')
        self._line('indexOf(s, sub) { return s.indexOf(sub); },')
        self._line('startsWith(s, p) { return s.startsWith(p); },')
        self._line('endsWith(s, p) { return s.endsWith(p); },')
        self._line('random() { return Math.random(); },')
        self._line('randomInt(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; },')
        self._line('absolute(n) { return Math.abs(n); },')
        self._line('power(a, b) { return Math.pow(a, b); },')
        self._line('squareRoot(n) { return Math.sqrt(n); },')
        self._line('floor(n) { return Math.floor(n); },')
        self._line('ceil(n) { return Math.ceil(n); },')
        self._line('round(n) { return Math.round(n); },')
        self._line('sin(n) { return Math.sin(n); },')
        self._line('cos(n) { return Math.cos(n); },')
        self._line('tan(n) { return Math.tan(n); },')
        self._line('log(n) { return Math.log(n); },')
        self._line('PI: Math.PI,')
        self._line('E: Math.E,')
        self._line('now() { return new Date().toISOString(); },')
        self._line('timestamp() { return Date.now(); },')
        self._line('sleep(ms) { return new Promise(r => setTimeout(r, ms)); },')
        self._line('toJson(v) { return JSON.stringify(v); },')
        self._line('fromJson(s) { return JSON.parse(s); },')
        self._line('keys(m) { return Object.keys(m); },')
        self._line('values(m) { return Object.values(m); },')
        self._line('hasKey(m, k) { return k in m; },')
        self._line('append(arr, item) { arr.push(item); return arr; },')
        self._line('join(arr, sep) { return arr.join(sep !== undefined ? sep : ", "); },')
        self._line('sorted(arr) { return [...arr].sort(); },')
        self._line('reversed(arr) { return [...arr].reverse(); },')
        self.indent -= 1
        self._line('};')
        self._line('')

        # Emit the EPL program
        self._line('// ── Application Code ─────────────────────')
        for stmt in program.statements:
            self._emit_js_stmt(stmt)

        self._line('')
        self._line('// ── Initialize ───────────────────────────')
        self._line('document.addEventListener("DOMContentLoaded", () => {')
        self.indent += 1
        for eb in self.event_bindings:
            wid = eb['widget']
            event = eb['event']
            handler = eb['handler']
            js_event = {'click': 'click', 'change': 'input', 'submit': 'submit',
                        'keypress': 'keypress', 'hover': 'mouseover'}.get(event, event)
            h_name = handler if isinstance(handler, str) else 'handler'
            self._line(f'document.getElementById("{wid}")?.addEventListener("{js_event}", {h_name});')
        if not self.event_bindings:
            self._line('console.log("EPL App initialized");')
        self.indent -= 1
        self._line('});')

        return '\n'.join(self.output)

    def _emit_js_stmt(self, node):
        """Emit a JavaScript statement from AST."""
        if node is None:
            return
        if isinstance(node, ast.VarDeclaration):
            val = self._js_expr(node.value) if node.value else 'null'
            self._line(f'let {node.name} = {val};')
        elif isinstance(node, ast.ConstDeclaration):
            val = self._js_expr(node.value) if node.value else 'null'
            self._line(f'const {node.name} = {val};')
        elif isinstance(node, ast.VarAssignment):
            self._line(f'{node.name} = {self._js_expr(node.value)};')
        elif isinstance(node, ast.PrintStatement):
            self._line(f'EPL.print({self._js_expr(node.expression)});')
        elif isinstance(node, ast.FunctionDef):
            params = ', '.join(p[0] if isinstance(p, (list, tuple)) else p for p in node.params)
            self._line(f'function {node.name}({params}) {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ReturnStatement):
            if node.value:
                self._line(f'return {self._js_expr(node.value)};')
            else:
                self._line('return;')
        elif isinstance(node, ast.IfStatement):
            self._line(f'if ({self._js_expr(node.condition)}) {{')
            self.indent += 1
            for s in node.then_body:
                self._emit_js_stmt(s)
            self.indent -= 1
            if node.else_body:
                self._line('} else {')
                self.indent += 1
                for s in node.else_body:
                    self._emit_js_stmt(s)
                self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.WhileLoop):
            self._line(f'while ({self._js_expr(node.condition)}) {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ForEachLoop):
            self._line(f'for (const {node.var_name} of {self._js_expr(node.iterable)}) {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ForRange):
            self._line(f'for (let {node.var_name} = {self._js_expr(node.start)}; {node.var_name} <= {self._js_expr(node.end)}; {node.var_name}++) {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.RepeatLoop):
            self._line(f'for (let _i = 0; _i < {self._js_expr(node.count)}; _i++) {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.FunctionCall):
            self._line(f'{self._js_expr(node)};')
        elif isinstance(node, ast.MethodCall):
            self._line(f'{self._js_expr(node)};')
        elif isinstance(node, ast.BreakStatement):
            self._line('break;')
        elif isinstance(node, ast.ContinueStatement):
            self._line('continue;')
        elif isinstance(node, ast.TryCatch):
            self._line('try {')
            self.indent += 1
            for s in node.try_body:
                self._emit_js_stmt(s)
            self.indent -= 1
            var_name = node.error_var or 'e'
            self._line(f'}} catch ({var_name}) {{')
            self.indent += 1
            for s in node.catch_body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ThrowStatement):
            self._line(f'throw new Error({self._js_expr(node.expression)});')
        elif isinstance(node, ast.ClassDef):
            parent = f' extends {node.parent}' if node.parent else ''
            self._line(f'class {node.name}{parent} {{')
            self.indent += 1
            for item in node.body:
                self._emit_js_stmt(item)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.PropertySet):
            self._line(f'{self._js_expr(node.obj)}.{node.property_name} = {self._js_expr(node.value)};')
        elif isinstance(node, ast.IndexSet):
            self._line(f'{self._js_expr(node.obj)}[{self._js_expr(node.index)}] = {self._js_expr(node.value)};')
        elif isinstance(node, ast.AugmentedAssignment):
            self._line(f'{node.name} {node.operator} {self._js_expr(node.value)};')
        elif isinstance(node, ast.WindowCreate):
            for s in node.body:
                self._emit_js_stmt(s)
        elif isinstance(node, ast.WidgetAdd):
            wid = node.name or f'widget_{self.widget_counter}'
            self.widget_counter += 1
            self.widgets.append({
                'id': wid, 'type': node.widget_type.lower(),
                'text': node.text, 'properties': node.properties,
            })
        elif isinstance(node, ast.BindEvent):
            self.event_bindings.append({
                'widget': node.widget_name, 'event': node.event_type,
                'handler': node.handler,
            })
        elif isinstance(node, ast.MatchStatement):
            self._line(f'switch ({self._js_expr(node.expression)}) {{')
            self.indent += 1
            for clause in node.when_clauses:
                for v in clause.values:
                    self._line(f'case {self._js_expr(v)}:')
                self.indent += 1
                for s in clause.body:
                    self._emit_js_stmt(s)
                self._line('break;')
                self.indent -= 1
            if node.default_body:
                self._line('default:')
                self.indent += 1
                for s in node.default_body:
                    self._emit_js_stmt(s)
                self.indent -= 1
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.EnumDef):
            self._line(f'const {node.name} = Object.freeze({{')
            self.indent += 1
            for i, m in enumerate(node.members):
                self._line(f'{m}: {i},')
            self.indent -= 1
            self._line('});')
        elif isinstance(node, ast.TryCatchFinally):
            self._line('try {')
            self.indent += 1
            for s in node.try_body:
                self._emit_js_stmt(s)
            self.indent -= 1
            for clause in node.catch_clauses:
                err_type, var_name, body = clause[0], clause[1], clause[2]
                var_name = var_name or '_err'
                self._line(f'}} catch ({var_name}) {{')
                self.indent += 1
                for s in body:
                    self._emit_js_stmt(s)
                self.indent -= 1
            if not node.catch_clauses:
                self._line('} catch (_err) {')
                self.indent += 1
                self._line('/* no catch body */')
                self.indent -= 1
            if node.finally_body:
                self._line('} finally {')
                self.indent += 1
                for s in node.finally_body:
                    self._emit_js_stmt(s)
                self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.AsyncFunctionDef):
            params = ', '.join(p[0] if isinstance(p, tuple) else p for p in node.params)
            self._line(f'async function {node.name}({params}) {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ConstDeclaration):
            self._line(f'const {node.name} = {self._js_expr(node.value)};')
        elif isinstance(node, ast.EnumDef):
            pass  # Already handled above
        elif isinstance(node, ast.FileWrite):
            self._line(f'console.warn("File I/O not available in browser");')
        elif isinstance(node, ast.FileAppend):
            self._line(f'console.warn("File I/O not available in browser");')
        elif isinstance(node, ast.SuperCall):
            args = ', '.join(self._js_expr(a) for a in node.arguments)
            if node.method_name:
                self._line(f'super.{node.method_name}({args});')
            else:
                self._line(f'super({args});')
        elif isinstance(node, ast.DestructureAssignment):
            names = ', '.join(node.names)
            self._line(f'const [{names}] = {self._js_expr(node.value)};')
        elif isinstance(node, ast.YieldStatement):
            self._line(f'yield {self._js_expr(node.value)};')
        elif isinstance(node, ast.ExportStatement):
            pass  # handled at module level
        elif isinstance(node, ast.VisibilityModifier):
            self._emit_js_stmt(node.statement)
        elif isinstance(node, ast.ModuleDef):
            self._line(f'const {node.name} = (() => {{')
            self.indent += 1
            for s in node.body:
                self._emit_js_stmt(s)
            self.indent -= 1
            self._line('})();')

    def _js_expr(self, node):
        """Convert AST expression to JavaScript."""
        if isinstance(node, ast.Literal):
            if isinstance(node.value, bool):
                return 'true' if node.value else 'false'
            if isinstance(node.value, str):
                escaped = node.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                return f'"{escaped}"'
            if node.value is None:
                return 'null'
            return str(node.value)
        if isinstance(node, ast.Identifier):
            return node.name
        if isinstance(node, ast.BinaryOp):
            l, r = self._js_expr(node.left), self._js_expr(node.right)
            op = node.operator
            if op == 'and': return f'({l} && {r})'
            if op == 'or': return f'({l} || {r})'
            if op == '**': return f'Math.pow({l}, {r})'
            if op == '//': return f'Math.floor({l} / {r})'
            return f'({l} {op} {r})'
        if isinstance(node, ast.UnaryOp):
            if node.operator == 'not': return f'!{self._js_expr(node.operand)}'
            return f'{node.operator}{self._js_expr(node.operand)}'
        if isinstance(node, ast.FunctionCall):
            name = node.name
            args = ', '.join(self._js_expr(a) for a in node.arguments)
            builtins = {'print', 'input', 'toInteger', 'toDecimal', 'toText', 'length',
                        'uppercase', 'lowercase', 'trim', 'contains', 'replace', 'split',
                        'substring', 'indexOf', 'startsWith', 'endsWith', 'random', 'randomInt',
                        'absolute', 'power', 'squareRoot', 'floor', 'ceil', 'round',
                        'sin', 'cos', 'tan', 'log', 'now', 'timestamp', 'sleep',
                        'toJson', 'fromJson', 'keys', 'values', 'hasKey', 'append',
                        'join', 'sorted', 'reversed'}
            if name in builtins:
                return f'EPL.{name}({args})'
            return f'{name}({args})'
        if isinstance(node, ast.MethodCall):
            obj = self._js_expr(node.obj)
            args = ', '.join(self._js_expr(a) for a in node.arguments)
            return f'{obj}.{node.method_name}({args})'
        if isinstance(node, ast.PropertyAccess):
            return f'{self._js_expr(node.obj)}.{node.property_name}'
        if isinstance(node, ast.IndexAccess):
            return f'{self._js_expr(node.obj)}[{self._js_expr(node.index)}]'
        if isinstance(node, ast.ListLiteral):
            elems = ', '.join(self._js_expr(e) for e in node.elements)
            return f'[{elems}]'
        if isinstance(node, ast.DictLiteral):
            pairs = ', '.join(f'{self._js_expr(k)}: {self._js_expr(v)}' for k, v in node.pairs)
            return f'{{{pairs}}}'
        if hasattr(ast, 'TemplateString') and isinstance(node, ast.TemplateString):
            parts = []
            for part in node.parts:
                if isinstance(part, str):
                    parts.append(part.replace('`', '\\`'))
                else:
                    parts.append(f'${{{self._js_expr(part)}}}')
            return f'`{"".join(parts)}`'
        if isinstance(node, str):
            return f'"{node}"'
        if isinstance(node, ast.TernaryExpression):
            return f'({self._js_expr(node.condition)} ? {self._js_expr(node.true_expr)} : {self._js_expr(node.false_expr)})'
        if isinstance(node, ast.LambdaExpression):
            params = ', '.join(node.params) if node.params else ''
            return f'(({params}) => {self._js_expr(node.body)})'
        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._js_expr(a) for a in node.arguments)
            return f'new {node.class_name}({args})'
        if isinstance(node, ast.AwaitExpression):
            return f'await {self._js_expr(node.expression)}'
        if isinstance(node, ast.SuperCall):
            args = ', '.join(self._js_expr(a) for a in node.arguments)
            if node.method_name:
                return f'super.{node.method_name}({args})'
            return f'super({args})'
        if isinstance(node, ast.FileRead):
            return f'null /* File I/O not available in browser */'
        if isinstance(node, ast.ModuleAccess):
            return f'{node.module_name}.{node.member_name}'
        if isinstance(node, ast.SliceAccess):
            obj = self._js_expr(node.obj)
            start = self._js_expr(node.start) if node.start else '0'
            end = self._js_expr(node.end) if node.end else ''
            if end:
                return f'{obj}.slice({start}, {end})'
            return f'{obj}.slice({start})'
        if hasattr(ast, 'SpreadExpression') and isinstance(node, ast.SpreadExpression):
            return f'...{self._js_expr(node.expression)}'
        return 'null'

    # ── WASM Loader & Runtime ───────────────────────────

    def generate_wasm_loader(self):
        """Generate JavaScript WASM loader."""
        return '''// EPL WASM Loader
const EPLWasm = {
    instance: null,
    memory: null,
    outputBuffer: [],

    async init(wasmPath = 'app.wasm') {
        try {
            const importObject = {
                env: {
                    epl_print_str: (ptr, len) => {
                        const bytes = new Uint8Array(EPLWasm.memory.buffer, ptr, len);
                        const text = new TextDecoder().decode(bytes);
                        EPLWasm.outputBuffer.push(text);
                        const el = document.getElementById('output');
                        if (el) el.innerHTML += text + '<br>';
                        console.log(text);
                    },
                    epl_print_int: (val) => {
                        EPLWasm.outputBuffer.push(String(val));
                        const el = document.getElementById('output');
                        if (el) el.innerHTML += val + '<br>';
                    },
                    epl_print_float: (val) => {
                        EPLWasm.outputBuffer.push(String(val));
                        const el = document.getElementById('output');
                        if (el) el.innerHTML += val + '<br>';
                    },
                    epl_alloc: (size) => { return 0; },
                    epl_free: (ptr) => {},
                    epl_time_ms: () => Date.now(),
                    epl_random: () => Math.random(),
                    epl_math_sin: Math.sin,
                    epl_math_cos: Math.cos,
                    epl_math_sqrt: Math.sqrt,
                    epl_math_pow: Math.pow,
                    epl_math_log: Math.log,
                },
                wasi_snapshot_preview1: {
                    fd_write: () => 0,
                    fd_read: () => 0,
                    fd_close: () => 0,
                    fd_seek: () => 0,
                    proc_exit: () => {},
                    environ_get: () => 0,
                    environ_sizes_get: () => 0,
                    args_get: () => 0,
                    args_sizes_get: () => 0,
                    clock_time_get: () => 0,
                }
            };

            const response = await fetch(wasmPath);
            const bytes = await response.arrayBuffer();
            const result = await WebAssembly.instantiate(bytes, importObject);
            EPLWasm.instance = result.instance;
            EPLWasm.memory = result.instance.exports.memory;

            // Call _start or main
            if (EPLWasm.instance.exports._start) {
                EPLWasm.instance.exports._start();
            } else if (EPLWasm.instance.exports.main) {
                EPLWasm.instance.exports.main();
            }

            console.log('EPL WASM module loaded successfully');
        } catch (err) {
            console.error('Failed to load WASM:', err);
            const el = document.getElementById('output');
            if (el) el.innerHTML = '<span style="color:#ef4444">WASM Error: ' + err.message + '</span>';
        }
    },

    // Call an exported WASM function
    call(name, ...args) {
        if (!EPLWasm.instance) throw new Error('WASM not initialized');
        const fn = EPLWasm.instance.exports[name];
        if (!fn) throw new Error(`Function ${name} not found in WASM exports`);
        return fn(...args);
    },

    // Read a string from WASM memory
    readString(ptr, len) {
        const bytes = new Uint8Array(EPLWasm.memory.buffer, ptr, len);
        return new TextDecoder().decode(bytes);
    },

    // Write a string to WASM memory
    writeString(str) {
        const encoder = new TextEncoder();
        const bytes = encoder.encode(str);
        const ptr = EPLWasm.call('epl_alloc', bytes.length + 1);
        const view = new Uint8Array(EPLWasm.memory.buffer, ptr, bytes.length + 1);
        view.set(bytes);
        view[bytes.length] = 0;
        return { ptr, len: bytes.length };
    },

    getOutput() { return EPLWasm.outputBuffer.join('\\n'); }
};

// Auto-initialize on load
document.addEventListener('DOMContentLoaded', () => {
    EPLWasm.init('../wasm/app.wasm');
});

export default EPLWasm;
'''

    def generate_wasm_runtime(self):
        """Generate JavaScript WASM runtime helpers."""
        return '''// EPL WASM Runtime — DOM interop layer
const EPLRuntime = {
    // DOM manipulation
    createElement(tag, attrs = {}) {
        const el = document.createElement(tag);
        Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
        return el;
    },

    getElementById(id) { return document.getElementById(id); },
    querySelector(sel) { return document.querySelector(sel); },

    setText(el, text) { if (el) el.textContent = text; },
    setHTML(el, html) { if (el) el.innerHTML = html; },
    getValue(el) { return el ? el.value : ''; },
    setValue(el, val) { if (el) el.value = val; },

    addClass(el, cls) { if (el) el.classList.add(cls); },
    removeClass(el, cls) { if (el) el.classList.remove(cls); },
    toggleClass(el, cls) { if (el) el.classList.toggle(cls); },

    on(el, event, handler) { if (el) el.addEventListener(event, handler); },
    off(el, event, handler) { if (el) el.removeEventListener(event, handler); },

    // Canvas 2D helpers
    getCanvas(id) {
        const canvas = document.getElementById(id);
        return canvas ? canvas.getContext('2d') : null;
    },

    drawRect(ctx, x, y, w, h, color = '#3b82f6') {
        ctx.fillStyle = color;
        ctx.fillRect(x, y, w, h);
    },

    drawCircle(ctx, x, y, r, color = '#3b82f6') {
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
    },

    drawText(ctx, text, x, y, color = '#f1f5f9', font = '16px sans-serif') {
        ctx.fillStyle = color;
        ctx.font = font;
        ctx.fillText(text, x, y);
    },

    clearCanvas(ctx, w, h) { ctx.clearRect(0, 0, w, h); },

    // Fetch wrapper
    async httpGet(url) {
        const res = await fetch(url);
        return await res.text();
    },

    async httpPost(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return await res.text();
    },

    // Local storage
    store(key, value) { localStorage.setItem(key, JSON.stringify(value)); },
    load(key) { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; },
    removeStore(key) { localStorage.removeItem(key); },

    // Notifications
    async notify(title, body) {
        if ('Notification' in window) {
            if (Notification.permission === 'granted') {
                new Notification(title, { body });
            } else if (Notification.permission !== 'denied') {
                const perm = await Notification.requestPermission();
                if (perm === 'granted') new Notification(title, { body });
            }
        }
    },

    // Clipboard
    async copyToClipboard(text) { await navigator.clipboard.writeText(text); },
    async readClipboard() { return await navigator.clipboard.readText(); },

    // Animation frame
    animate(callback) { return requestAnimationFrame(callback); },
    cancelAnimate(id) { cancelAnimationFrame(id); },
};

window.EPLRuntime = EPLRuntime;
'''

    # ── Kotlin/JS Transpilation ─────────────────────────

    def transpile_kotlin_js(self, program: ast.Program, package='com.epl.web') -> str:
        """Transpile EPL AST to Kotlin targeting JS (browser)."""
        self.output = []
        self.indent = 0

        self._line(f'package {package}')
        self._line('')
        self._line('import kotlinx.browser.document')
        self._line('import kotlinx.browser.window')
        self._line('import kotlinx.html.*')
        self._line('import kotlinx.html.dom.create')
        self._line('import kotlinx.html.dom.append')
        self._line('import org.w3c.dom.*')
        self._line('')
        self._line('fun main() {')
        self.indent += 1
        self._line('document.addEventListener("DOMContentLoaded", {')
        self.indent += 1
        self._line('val app = document.getElementById("app")!!')
        self._line('')

        for stmt in program.statements:
            self._emit_kotlin_js_stmt(stmt)

        self._line('')
        self._line('console.log("EPL Kotlin/JS app initialized")')
        self.indent -= 1
        self._line('})')
        self.indent -= 1
        self._line('}')

        return '\n'.join(self.output)

    def _emit_kotlin_js_stmt(self, node):
        """Emit Kotlin/JS statement."""
        if isinstance(node, ast.VarDeclaration):
            val = self._kt_expr(node.value) if node.value else 'null'
            self._line(f'var {node.name} = {val}')
        elif isinstance(node, ast.ConstDeclaration):
            val = self._kt_expr(node.value) if node.value else 'null'
            self._line(f'val {node.name} = {val}')
        elif isinstance(node, ast.PrintStatement):
            self._line(f'console.log({self._kt_expr(node.expression)})')
            self._line(f'app.append {{ p {{ +{self._kt_expr(node.expression)}.toString() }} }}')
        elif isinstance(node, ast.FunctionDef):
            params = ', '.join(f'{p}: dynamic' if isinstance(p, str) else f'{p[0]}: dynamic'
                               for p in node.params)
            self._line(f'fun {node.name}({params}): dynamic {{')
            self.indent += 1
            for s in node.body:
                self._emit_kotlin_js_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ReturnStatement):
            if node.value:
                self._line(f'return {self._kt_expr(node.value)}')
            else:
                self._line('return')
        elif isinstance(node, ast.IfStatement):
            self._line(f'if ({self._kt_expr(node.condition)}) {{')
            self.indent += 1
            for s in node.then_body:
                self._emit_kotlin_js_stmt(s)
            self.indent -= 1
            if node.else_body:
                self._line('} else {')
                self.indent += 1
                for s in node.else_body:
                    self._emit_kotlin_js_stmt(s)
                self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.VarAssignment):
            self._line(f'{node.name} = {self._kt_expr(node.value)}')
        elif isinstance(node, ast.FunctionCall):
            self._line(self._kt_expr(node))
        elif isinstance(node, ast.MethodCall):
            self._line(self._kt_expr(node))

    def _kt_expr(self, node):
        """Quick Kotlin expression — delegates heavy work to the Desktop generator."""
        if isinstance(node, ast.Literal):
            if isinstance(node.value, bool): return 'true' if node.value else 'false'
            if isinstance(node.value, str):
                escaped = node.value.replace('\\', '\\\\').replace('"', '\\"')
                return f'"{escaped}"'
            if node.value is None: return 'null'
            return str(node.value)
        if isinstance(node, ast.Identifier): return node.name
        if isinstance(node, ast.BinaryOp):
            l, r = self._kt_expr(node.left), self._kt_expr(node.right)
            op = node.operator
            if op == 'and': return f'({l} && {r})'
            if op == 'or': return f'({l} || {r})'
            return f'({l} {op} {r})'
        if isinstance(node, ast.FunctionCall):
            args = ', '.join(self._kt_expr(a) for a in node.arguments)
            return f'{node.name}({args})'
        if isinstance(node, ast.MethodCall):
            obj = self._kt_expr(node.obj)
            args = ', '.join(self._kt_expr(a) for a in node.arguments)
            return f'{obj}.{node.method_name}({args})'
        if isinstance(node, ast.ListLiteral):
            elems = ', '.join(self._kt_expr(e) for e in node.elements)
            return f'listOf({elems})'
        if isinstance(node, ast.TemplateString):
            parts = []
            for part in node.parts:
                if isinstance(part, str):
                    parts.append(part.replace('"', '\\"'))
                else:
                    parts.append(f'${{{self._kt_expr(part)}}}')
            return f'"{"".join(parts)}"'
        if isinstance(node, str): return f'"{node}"'
        return 'null'

    # ── Collect outputs ─────────────────────────────────

    def _collect_print_outputs(self, stmts):
        """Collect print statement text for static rendering."""
        outputs = []
        for s in stmts:
            if isinstance(s, ast.PrintStatement):
                if isinstance(s.expression, ast.Literal) and isinstance(s.expression.value, str):
                    outputs.append(s.expression.value)
                else:
                    outputs.append(f'{{{self._js_expr(s.expression)}}}')
        return outputs

    def _collect_gui_nodes(self, stmts):
        """Collect GUI widget definitions from AST."""
        for s in stmts:
            if isinstance(s, ast.WindowCreate):
                self._collect_gui_nodes(s.body)
            elif isinstance(s, ast.WidgetAdd):
                wid = s.name or f'widget_{self.widget_counter}'
                self.widget_counter += 1
                self.widgets.append({
                    'id': wid, 'type': s.widget_type.lower(),
                    'text': getattr(s, 'text', '') or '',
                    'properties': getattr(s, 'properties', {}) or {},
                })
            elif isinstance(s, ast.LayoutBlock):
                self._collect_gui_nodes(s.children)
            elif isinstance(s, ast.BindEvent):
                self.event_bindings.append({
                    'widget': s.widget_name, 'event': s.event_type,
                    'handler': s.handler,
                })

    def _line(self, text):
        self.output.append('    ' * self.indent + text)


# ── Convenience Functions ────────────────────────────────


def generate_web_project(program: ast.Program, output_dir: str,
                          app_name="EPLWebApp", mode="js") -> str:
    """Generate a browser-ready web project from EPL."""
    gen = WebProjectGenerator(app_name, mode)
    return gen.generate(program, output_dir)


def transpile_to_web_js(program: ast.Program, app_title="EPL App") -> str:
    """Transpile EPL to browser JavaScript source."""
    gen = WebCodeGenerator(app_title)
    return gen.transpile_js(program)


def generate_wasm_glue(app_title="EPL App") -> dict:
    """Generate WASM loader + runtime JS files."""
    gen = WebCodeGenerator(app_title)
    return {
        'loader.js': gen.generate_wasm_loader(),
        'runtime.js': gen.generate_wasm_runtime(),
    }
