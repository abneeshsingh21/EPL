<div align="center">

# 🌐 EPL — English Programming Language

### Write code the way you think. In plain English.

<br/>

[![PyPI](https://img.shields.io/pypi/v/eplang?color=3572A5&label=PyPI&logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/eplang/)
[![Downloads](https://img.shields.io/pypi/dm/eplang?color=3572A5&label=Downloads&style=flat-square)](https://pypi.org/project/eplang/)
[![Python](https://img.shields.io/badge/Python-3.9%E2%80%933.13-3572A5?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-2ea44f?style=flat-square)](LICENSE)
[![VS Code](https://img.shields.io/badge/VS%20Code-Marketplace-007ACC?style=flat-square&logo=visual-studio-code&logoColor=white)](https://marketplace.visualstudio.com/publishers/epl-lang)
[![Stars](https://img.shields.io/github/stars/abneeshsingh21/EPL?style=flat-square&logo=github&color=e3b341)](https://github.com/abneeshsingh21/EPL/stargazers)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-ea4aaa?style=flat-square&logo=github-sponsors)](https://github.com/sponsors/abneeshsingh21)

<br/>

EPL is a **fully-featured programming language** where every keyword is natural English.  
Build web apps, REST APIs, mobile apps, AI pipelines, and cloud-native services — in a syntax anyone can read, write, and maintain.

<br/>

```
pip install eplang
```

<br/>

[Documentation](https://abneeshsingh21.github.io/EPL/) · [Playground](https://abneeshsingh21.github.io/EPL/playground) · [VS Code Extension](https://marketplace.visualstudio.com/publishers/epl-lang) · [Package Registry](https://abneeshsingh21.github.io/epl-packages-index/)

</div>

<br/>

---

## Overview

EPL (English Programming Language) eliminates the gap between pseudocode and executable code. Its syntax reads like structured English, while its runtime delivers the performance and tooling expected from a modern language — bytecode VM, LLVM native compilation, WASM targets, and a 22-package official ecosystem.

```epl
Note: A production-grade REST API in EPL

Create WebApp called app

Route "/api/users" responds with
    users = [Map with name = "Alice" and role = "admin", Map with name = "Bob" and role = "user"]
    Send json Map with data = users and count = length(users) and status = "ok"
End

Route "/health" responds with
    Send json Map with status = "healthy" and version = "9.7.0"
End
```

**No semicolons. No curly braces. No cryptic symbols. Just English.**

---

## Quick Start

### Install

```bash
pip install eplang
```

### Run

```bash
echo 'Say "Hello from EPL!"' > hello.epl
epl hello.epl
```

### REPL

```bash
epl repl
```

### Scaffold a Project

```bash
epl new myapp --template web        # Web app with routing
epl new authapp --template auth     # Auth API with JWT
epl new botapp --template chatbot   # AI chatbot
epl new studio --template frontend  # Creative frontend
```

### Production Deployment

```bash
pip install "eplang[server]"
epl serve app.epl                    # Dev server
epl deploy k8s app.epl --image myapp:1.0 --tls  # Kubernetes
epl deploy aws app.epl               # AWS ECS
```

EPL supports WSGI (Waitress, Gunicorn) and ASGI (Uvicorn, Hypercorn) deployment through generated adapters and the `epl serve` runtime.

### Security, CSP & the escape hatch

The web DSL renders structure, styling (`Style`/`Stylesheet`), head/SEO (`Head`), and interactivity (`On click/hover/reveal`) as **native, server-rendered** output — no client-side injection. Event handlers compile to a generated `<script>` (never inline `on*` attributes).

For the imperative cases the DSL doesn't model — a canvas particle engine, custom `requestAnimationFrame` loops, third-party widgets — `Script`, `Raw HTML`, and `Stylesheet` are the **sanctioned, author-responsible escape hatches** (the canvas particle engine on the EPL site itself lives in a `Script` block by design). Their bodies are emitted verbatim, with breakout guards on `Stylesheet`.

Run under a strict Content-Security-Policy with `--csp`:

```bash
epl serve app.epl --csp
```

This generates a fresh per-response nonce, tags every generated `<script>` with it, and sends `Content-Security-Policy: … script-src 'self' 'nonce-…' …` — so the generated JS runs under a strict policy with no `'unsafe-inline'` for scripts. (Programmatic equivalent: `configure_page(csp=True)`.)

---

## Language at a Glance

<table>
<tr>
<td width="50%">

**Variables & Control Flow**
```epl
name = "Abneesh"
age = 20
scores = [95, 87, 92]

If age is greater than 18 then
    Say "Welcome, " + name
Otherwise
    Say "Access denied"
End

For Each score in scores
    Say score
End

Repeat 3 times
    Say "Iteration complete"
End
```

</td>
<td width="50%">

**Functions & OOP**
```epl
Function fibonacci takes n
    If n is less than 2 then
        Return n
    End
    Return fibonacci(n - 1) + fibonacci(n - 2)
End

Class User has name, email, role
    Method display
        Say "User: " + this.name
    End
End

user = new User("Ada", "ada@epl.dev", "admin")
user.display()
```

</td>
</tr>
</table>

---

## Architecture

EPL is a multi-backend language with a unified frontend:

```
                    ┌──────────────┐
   .epl source  ──▶│    Lexer      │
                    │    Parser     │
                    │    AST        │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
     ┌──────────────┐ ┌──────────┐  ┌─────────────┐
     │  Interpreter │ │ Bytecode │  │    LLVM      │
     │  (Tree-walk) │ │ VM       │  │  (Native)    │
     └──────────────┘ └──────────┘  └─────────────┘
              │            │                │
              ▼            ▼                ▼
         Python host   Stack VM       .exe / .o
                                    (x86, ARM, WASM)
```

### Compilation Targets

| Target | Command | Output |
|--------|---------|--------|
| Interpreter | `epl run app.epl` | Direct execution |
| Bytecode VM | `epl vm app.epl` | Stack-based VM |
| Native Binary | `epl build app.epl` | LLVM → `.exe` / ELF |
| WebAssembly | `epl wasm app.epl` | `.wasm` module |
| JavaScript | `epl js app.epl` | Browser/Node.js |
| Kotlin | `epl kotlin app.epl` | JVM / Android |
| Python | `epl python app.epl` | `.py` transpile |

---

## Ecosystem

### Official Package Registry — 22 Packages

EPL ships with a curated package ecosystem covering web, data, AI, security, and infrastructure:

<table>
<tr><th>Category</th><th>Packages</th><th>Description</th></tr>
<tr><td><b>Web & API</b></td><td><code>epl-web</code> · <code>epl-http</code></td><td>HTTP router, WebSocket, REST client, middleware</td></tr>
<tr><td><b>Data & DB</b></td><td><code>epl-db</code> · <code>epl-dataframe</code> · <code>epl-collections</code></td><td>SQLite ORM, DataFrame ops, typed collections</td></tr>
<tr><td><b>AI & ML</b></td><td><code>epl-learn</code> · <code>epl-array</code> · <code>epl-plot</code></td><td>Scikit-learn bindings, NumPy arrays, Matplotlib charts</td></tr>
<tr><td><b>Math & Science</b></td><td><code>epl-math</code> · <code>epl-science</code> · <code>epl-algo</code></td><td>Number theory, SciPy integration, graph algorithms</td></tr>
<tr><td><b>Security</b></td><td><code>epl-auth</code> · <code>epl-crypto</code> · <code>epl-validator</code></td><td>JWT auth, hashing/encryption, input validation</td></tr>
<tr><td><b>Infrastructure</b></td><td><code>epl-cloud</code> · <code>epl-cache</code> · <code>epl-email</code></td><td>AWS/GCP/Azure, Redis caching, SMTP</td></tr>
<tr><td><b>Language</b></td><td><code>epl-string</code> · <code>epl-datetime</code> · <code>epl-functional</code> · <code>epl-struct</code></td><td>String utils, date ops, FP patterns, typed records</td></tr>
<tr><td><b>Testing</b></td><td><code>epl-test</code></td><td>Unit testing framework with assertions</td></tr>
</table>

```bash
epl install epl-auth         # Install a package
epl install epl-math         # Packages resolve from the official registry
```

Browse all packages at the [EPL Package Registry →](https://abneeshsingh21.github.io/epl-packages-index/)

### Standard Library — 21 Modules

Built-in modules available without installation: `math`, `string`, `http`, `json`, `crypto`, `datetime`, `regex`, `io`, `os`, `sql`, `net`, `html`, `web`, `websocket`, `collections`, `encoding`, `functional`, `auth`, `template`, `testing`, `sql`.

### JavaScript/TypeScript Bridge

Access the entire NPM ecosystem from EPL:

```epl
Use javascript "lodash" as _
Use javascript "axios" as axios

result = _.chunk([1, 2, 3, 4, 5, 6], 2)
response = axios.get("https://api.example.com/data")
Say response.data
```

---

## What Can You Build

<table>
<tr>
<td width="50%">

**🌐 Web Applications & APIs**
```epl
Create WebApp called app

Route "/api/users" responds with
    users = query(db, "SELECT * FROM users")
    Send json Map with data = users
End
```

**🤖 AI & Machine Learning**
```epl
Import "epl.ai" As ai
messages = [Map with role = "user" and content = "Explain EPL"]
response = ai.chat(messages)
Say response
```

**🗄️ Database Applications**
```epl
Import "epl-db"
db = open("app.db")
create_table(db, "tasks", Map with title = "TEXT" and done = "INT")
insert(db, "tasks", Map with title = "Ship EPL" and done = 0)
```

</td>
<td width="50%">

**📱 Android Apps**
```bash
epl android app.epl
# → Full Android Studio project with Kotlin
```

**🍎 iOS Apps**
```bash
epl ios app.epl
# → Xcode project with SwiftUI views
```

**🖥️ Desktop Apps**
```bash
epl desktop app.epl
# → Compose Multiplatform desktop app
```

**⚡ Native Executables**
```bash
epl build app.epl
# → LLVM-compiled native binary
```

**☸️ Kubernetes Deployment**
```bash
epl deploy k8s app.epl \
  --image myapp:1.0 \
  --host app.example.com --tls
```

</td>
</tr>
</table>

---

## Feature Matrix

| Category | Capabilities |
|----------|-------------|
| **Language** | OOP, generics, async/await, pattern matching, lambdas, generators, enums, decorators, type inference |
| **Type System** | Static type checker (`epl check`), gradual typing, generic constraints |
| **Performance** | Bytecode VM with constant folding, LLVM native compilation, dead code elimination, tail-call optimization |
| **Web** | HTTP/WebSocket router, WSGI/ASGI adapters, middleware pipeline, sessions, templates, static files |
| **Database** | SQLite ORM, Redis, PostgreSQL — `Store`/`Fetch`/`Delete` English APIs |
| **Security** | Sandboxed FFI, pickle allowlist, recursion/scope-depth limits, input validation |
| **Tooling** | LSP server, REPL, debugger, formatter (`epl fmt`), linter (`epl lint`), test runner, code coverage |
| **Targets** | Interpreter, VM, LLVM native, JS, Kotlin, Python, WASM, MicroPython — 8 compilation backends |
| **Packaging** | SemVer registry, lockfiles, checksums, dependency resolution, PyPI bridge |
| **AI** | Built-in `ai` module, Error Explainer v2.0 with 55+ offline patterns (`epl fix`), auto-fix (`--fix`), dual-model copilot |
| **DevOps** | K8s manifests, AWS/GCP/Azure deploy, Prometheus metrics, health endpoints, structured logging |
| **Interop** | JS/TS bridge for NPM, Python bridge for PyPI, persistent Node.js subprocess |
| **Stdlib** | 725+ built-in functions: HTTP, DB, Math, Crypto, File I/O, JSON, Regex, DateTime, HTML |

---

## CLI Reference

```
Usage: epl <command> [options]

Core
  epl run <file>              Run an EPL program
  epl repl                    Interactive REPL
  epl new <name> [--template] Scaffold a new project
  epl serve <file>            Start web server (dev mode)

Build & Compile
  epl build <file>            Compile to native executable (LLVM)
  epl wasm <file>             Compile to WebAssembly
  epl js <file>               Transpile to JavaScript
  epl python <file>           Transpile to Python
  epl kotlin <file>           Transpile to Kotlin

Platform Targets
  epl android <file>          Generate Android Studio project
  epl ios <file>              Generate Xcode / SwiftUI project
  epl desktop <file>          Generate Compose Multiplatform app
  epl web <file>              Generate WASM/JS web app

Quality & Tooling
  epl check [file]            Static type checking
  epl fmt <file>              Format source code
  epl lint [file]             Lint source code
  epl test [dir]              Run test suite
  epl fix <file>              Error diagnostics (offline, 55+ patterns)
  epl fix <file> --fix        Auto-apply suggested corrections

Deploy
  epl deploy k8s <file>       Generate Kubernetes manifests
  epl deploy aws <file>       Deploy to AWS ECS
  epl deploy gcp <file>       Deploy to GCP Cloud Run
  epl deploy azure <file>     Deploy to Azure Container Apps

Packages
  epl install <package>       Install a package
  epl upgrade                 Upgrade EPL to latest version

Tools
  epl playground              Browser-based playground
  epl copilot                 AI code assistant
```

---

## Comparison

| Capability | EPL | Python | JavaScript | Go | Java |
|-----------|-----|--------|------------|-----|------|
| Natural-language syntax | ✅ | — | — | — | — |
| Learning curve | Minutes | Days | Days | Weeks | Weeks |
| Built-in web framework | ✅ | — | — | — | — |
| Built-in AI module | ✅ | — | — | — | — |
| Package manager | ✅ | pip | npm | go mod | Maven |
| Native compilation | ✅ LLVM | — | — | ✅ | ✅ JIT |
| WASM target | ✅ | — | ✅ | ✅ | — |
| Mobile transpiler | ✅ Android + iOS | — | React Native | — | ✅ |
| LSP / IDE support | ✅ | ✅ | ✅ | ✅ | ✅ |
| Type checking | ✅ Gradual | ✅ mypy | ✅ TS | ✅ | ✅ |

---

## VS Code Extension

The official EPL extension provides a first-class development experience:

- **Syntax Highlighting** — Full TextMate grammar for `.epl` files
- **Real-time Diagnostics** — Type errors, unused variables, parse errors
- **IntelliSense** — Autocomplete for keywords, builtins, and imports
- **Hover Documentation** — Inline docs for all 725+ built-in functions
- **Error Diagnostics** — `epl fix` with Rust-style context window and `--fix` auto-correction
- **Run & Check** — `Ctrl+Shift+R` to run, `Ctrl+Shift+K` to type-check

Install from the [VS Code Marketplace →](https://marketplace.visualstudio.com/publishers/epl-lang)

---

## Documentation

| Resource | Link |
|----------|------|
| Getting Started | [docs/getting-started.md](docs/getting-started.md) |
| Language Specification | [docs/language-spec.md](docs/language-spec.md) |
| Tutorials | [docs/tutorials.md](docs/tutorials.md) |
| Package Manager Guide | [docs/package-manager.md](docs/package-manager.md) |
| Architecture Overview | [docs/architecture.md](docs/architecture.md) |
| Publishing Packages | [docs/publishing.md](docs/publishing.md) |
| Full Documentation Site | [abneeshsingh21.github.io/EPL](https://abneeshsingh21.github.io/EPL/) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

---

## Contributing

We welcome contributions from the community. EPL maintains enterprise-grade code quality standards: every change is gated by a blocking CI pipeline — whole-tree `mypy` type-checking, Ruff lint + formatting, and the full test suite (1,700+ tests).

```bash
git clone https://github.com/abneeshsingh21/EPL.git
cd EPL
pip install -e ".[dev,cloud]"
ruff format .
pytest tests/ -x --tb=short -q
```

Before contributing, please read:
- [CONTRIBUTING.md](CONTRIBUTING.md) — Development workflow and testing requirements
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Community standards
- [CLA.md](CLA.md) — Contributor License Agreement

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the full list of contributors.

---

## Roadmap

- [x] Core language — interpreter, bytecode VM, LLVM native compiler
- [x] Web framework — HTTP/WebSocket router, WSGI/ASGI, middleware
- [x] Package manager — SemVer, lockfiles, checksums, dependency resolution
- [x] Developer tooling — LSP server, debugger, REPL, formatter, linter
- [x] Mobile targets — Android (Kotlin) and iOS (SwiftUI) transpilers
- [x] Desktop target — Compose Multiplatform app generation
- [x] Cloud deploy — AWS ECS, GCP Cloud Run, Azure, Kubernetes
- [x] JavaScript/TypeScript bridge — Full NPM ecosystem interop
- [x] AI integration — Built-in module, Error Explainer v2.0 (55+ offline patterns, auto-fix), copilot
- [x] Observability — Health checks, Prometheus metrics, structured logging
- [x] PyPI distribution — `pip install eplang`
- [x] VS Code extension — Syntax, diagnostics, IntelliSense
- [x] Official documentation site and browser playground
- [x] 22 official packages across web, data, AI, security, and infrastructure
- [x] Language server protocol v2 (semantic tokens, token-aware rename & references)
- [ ] WebSocket real-time collaboration
- [ ] GPU compute target (CUDA/ROCm via LLVM)

---

## Community

- [GitHub Discussions](https://github.com/abneeshsingh21/EPL/discussions) — Questions, ideas, and project showcase
- [Issue Tracker](https://github.com/abneeshsingh21/EPL/issues) — Bug reports and feature requests
- [Package Registry](https://abneeshsingh21.github.io/epl-packages-index/) — Browse and publish EPL packages

---

## Sponsor

EPL is built and maintained by [Abneesh Singh](https://github.com/abneeshsingh21) as an independent open-source project. If EPL is useful to you — in education, prototyping, or production — consider sponsoring its development:

<div align="center">

**[❤️ Sponsor on GitHub](https://github.com/sponsors/abneeshsingh21)**

</div>

Your sponsorship directly funds: new language features, official packages, documentation, VS Code extension updates, and security patches.

---

## License

Copyright © 2024–2026 **Abneesh Singh** (<singhabneesh250@gmail.com>)

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution requirements.

> "EPL" and "English Programming Language" are trademarks of Abneesh Singh.

---

<div align="center">

**⭐ If EPL resonates with you, consider starring the repository.**

Made with precision by [Abneesh Singh](https://github.com/abneeshsingh21)

</div>
