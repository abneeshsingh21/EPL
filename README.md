<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/branding/banner_dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/branding/banner_light.svg">
  <img alt="EPL — English Programming Language" src="assets/branding/banner_light.svg" width="100%">
</picture>
</p>

<p align="center">
<strong>Write code the way you think. In plain English.</strong>
</p>

<p align="center">
<a href="https://pypi.org/project/eplang/"><img src="https://img.shields.io/pypi/v/eplang?color=0969da&label=PyPI&logo=pypi&logoColor=white&style=flat-square" alt="PyPI" /></a>
<a href="https://pypi.org/project/eplang/"><img src="https://img.shields.io/pypi/dm/eplang?color=0969da&label=Downloads&style=flat-square" alt="Downloads" /></a>
<a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.9–3.13-0969da?style=flat-square&logo=python&logoColor=white" alt="Python" /></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-2ea44f?style=flat-square" alt="License" /></a>
</p>

<p align="center">
<a href="https://marketplace.visualstudio.com/publishers/epl-lang"><img src="https://img.shields.io/badge/VS%20Code-Marketplace-007ACC?style=flat-square&logo=visual-studio-code&logoColor=white" alt="VS Code" /></a>
<a href="https://github.com/abneeshsingh21/EPL/stargazers"><img src="https://img.shields.io/github/stars/abneeshsingh21/EPL?style=flat-square&logo=github&color=e3b341" alt="Stars" /></a>
<a href="https://github.com/sponsors/abneeshsingh21"><img src="https://img.shields.io/badge/Sponsor-❤-ea4aaa?style=flat-square&logo=github-sponsors" alt="Sponsor" /></a>
</p>

<br/>

<p align="center">
EPL is a <strong>fully-featured programming language</strong> where every keyword is natural English.<br/>
Build web apps, REST APIs, mobile apps, AI pipelines, and cloud-native services —<br/>
in a syntax anyone can read, write, and maintain.
</p>

<br/>

<p align="center">
<a href="https://abneeshsingh21.github.io/EPL/"><strong>Documentation</strong></a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://abneeshsingh21.github.io/EPL/playground"><strong>Playground</strong></a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://marketplace.visualstudio.com/publishers/epl-lang"><strong>VS Code</strong></a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://abneeshsingh21.github.io/epl-packages-index/"><strong>Packages</strong></a>
</p>

<br/>

---

```epl
Note: A production-grade REST API — readable by anyone

Create WebApp called app

Route "/api/users" responds with
    users = [Map with name = "Alice" and role = "admin", Map with name = "Bob" and role = "user"]
    Send json Map with data = users and count = length(users) and status = "ok"
End

Route "/health" responds with
    Send json Map with status = "healthy" and version = "10.1.0"
End
```

> **No semicolons. No curly braces. No cryptic symbols. Just English.**

---

## Get Started

```bash
pip install eplang
```

```bash
echo 'Say "Hello from EPL!"' > hello.epl
epl hello.epl
```

<details>
<summary><strong>Project Templates</strong></summary>

```bash
epl new myapp --template web        # Web app with routing
epl new authapp --template auth     # Auth API with JWT
epl new botapp --template chatbot   # AI chatbot
epl new studio --template frontend  # Creative frontend
```
</details>

<details>
<summary><strong>Production Deployment</strong></summary>

```bash
pip install "eplang[server]"
epl serve app.epl                    # Dev server
epl deploy k8s app.epl --image myapp:1.0 --tls  # Kubernetes
epl deploy aws app.epl               # AWS ECS
```

EPL supports WSGI (Waitress, Gunicorn) and ASGI (Uvicorn, Hypercorn) deployment through generated adapters and the `epl serve` runtime.
</details>

<details>
<summary><strong>Security & CSP</strong></summary>

The web DSL renders structure, styling (`Style`/`Stylesheet`), head/SEO (`Head`), and interactivity (`On click/hover/reveal`) as **native, server-rendered** output — no client-side injection. Event handlers compile to a generated `<script>` (never inline `on*` attributes).

For imperative cases the DSL doesn't model — canvas, `requestAnimationFrame` loops, third-party widgets — `Script`, `Raw HTML`, and `Stylesheet` are the **sanctioned escape hatches**. Their bodies are emitted verbatim, with breakout guards on `Stylesheet`.

```bash
epl serve app.epl --csp   # Strict Content-Security-Policy with per-response nonce
```
</details>

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
                                    (x86-64 verified)
```

### Compilation Targets

| Target | Command | Output |
|:-------|:--------|:-------|
| Bytecode VM | `epl run app.epl` | Stack-based VM *(default)* |
| Interpreter | `epl run --interpret app.epl` | Tree-walk |
| Native Binary | `epl build app.epl` | LLVM → `.exe` / ELF |
| WebAssembly | `epl wasm app.epl` | `.wasm` module |
| JavaScript | `epl js app.epl` | Browser / Node.js |
| Kotlin | `epl kotlin app.epl` | JVM / Android |
| Python | `epl python app.epl` | `.py` transpile |

> The interpreter and bytecode VM are held to **byte-for-byte output parity** by `tests/parity_check.py`.

---

## Ecosystem

### 22 Official Packages

| Category | Packages | Description |
|:---------|:---------|:------------|
| **Web & API** | `epl-web` · `epl-http` | HTTP router, WebSocket, REST client, middleware |
| **Data & DB** | `epl-db` · `epl-dataframe` · `epl-collections` | SQLite ORM, DataFrame ops, typed collections |
| **AI & ML** | `epl-learn` · `epl-array` · `epl-plot` | Scikit-learn bindings, NumPy arrays, Matplotlib |
| **Math & Science** | `epl-math` · `epl-science` · `epl-algo` | Number theory, SciPy, graph algorithms |
| **Security** | `epl-auth` · `epl-crypto` · `epl-validator` | JWT auth, hashing/encryption, validation |
| **Infrastructure** | `epl-cloud` · `epl-cache` · `epl-email` | AWS/GCP/Azure, Redis caching, SMTP |
| **Language** | `epl-string` · `epl-datetime` · `epl-functional` · `epl-struct` | String utils, date ops, FP, typed records |
| **Testing** | `epl-test` | Unit testing framework |

```bash
epl install epl-auth         # Install a package
epl install epl-math         # Packages resolve from the official registry
```

> [Browse all packages →](https://abneeshsingh21.github.io/epl-packages-index/)

### 21 Standard Library Modules

Built-in, no installation required: `math` · `string` · `http` · `json` · `crypto` · `datetime` · `regex` · `io` · `os` · `sql` · `net` · `html` · `web` · `websocket` · `collections` · `encoding` · `functional` · `auth` · `template` · `testing`

### NPM Bridge

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

**Web Applications & APIs**
```epl
Create WebApp called app

Route "/api/users" responds with
    users = query(db, "SELECT * FROM users")
    Send json Map with data = users
End
```

**AI & Machine Learning**
```epl
Import "epl.ai" As ai
messages = [Map with role = "user" and content = "Explain EPL"]
response = ai.chat(messages)
Say response
```

**Database Applications**
```epl
Import "epl-db"
db = open("app.db")
create_table(db, "tasks", Map with title = "TEXT" and done = "INT")
insert(db, "tasks", Map with title = "Ship EPL" and done = 0)
```

</td>
<td width="50%">

**Android Apps**
```bash
epl android app.epl
# → Full Android Studio project with Kotlin
```
> Compiler-verified: builds an installable debug APK via `gradlew assembleDebug`.

**iOS Apps** *(experimental)*
```bash
epl ios app.epl
# → Xcode project with SwiftUI views
```

**Desktop Apps**
```bash
epl desktop app.epl
# → Compose Multiplatform desktop app
```

**Native Executables**
```bash
epl build app.epl
# → LLVM-compiled native binary
```
> Compiles type-annotated programs and infers types for untyped functions that resolve to a single concrete type. Dynamic/polymorphic functions are safely refused.

**Kubernetes**
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
|:---------|:------------|
| **Language** | OOP, generics, async/await, pattern matching, lambdas & closures, generators, enums, decorators, type inference |
| **Type System** | Static checker (`epl check`), gradual typing, generic constraints, whole-program inference for native builds |
| **Performance** | Bytecode VM with constant folding, LLVM native compilation, dead code elimination, tail-call optimization |
| **Web** | HTTP/WebSocket router, WSGI/ASGI adapters, middleware pipeline, sessions, templates, static files |
| **Database** | SQLite ORM, Redis, PostgreSQL — `Store`/`Fetch`/`Delete` English APIs |
| **Security** | Sandboxed FFI, pickle allowlist, recursion/scope-depth limits, input validation |
| **Tooling** | LSP server, REPL, debugger, formatter, linter, test runner, code coverage |
| **Targets** | Interpreter, VM, LLVM native, JS, Kotlin, Python, WASM, MicroPython — **8 backends** |
| **Packaging** | SemVer registry, lockfiles, checksums, dependency resolution, PyPI bridge |
| **AI** | Built-in `ai` module, Error Explainer v2.0 (55+ offline patterns), auto-fix, dual-model copilot |
| **DevOps** | K8s manifests, AWS/GCP/Azure deploy, Prometheus metrics, health endpoints, structured logging |
| **Interop** | JS/TS bridge (NPM), Python bridge (PyPI), persistent Node.js subprocess |
| **Stdlib** | **725+ built-in functions** — HTTP, DB, Math, Crypto, File I/O, JSON, Regex, DateTime, HTML |

---

## Comparison

| | EPL | Python | JavaScript | Go | Java |
|:--|:---:|:------:|:----------:|:---:|:----:|
| Natural-language syntax | ✅ | — | — | — | — |
| Learning curve | Minutes | Days | Days | Weeks | Weeks |
| Built-in web framework | ✅ | — | — | — | — |
| Built-in AI module | ✅ | — | — | — | — |
| Package manager | ✅ | pip | npm | go mod | Maven |
| Native compilation | ✅ † | — | — | ✅ | JIT |
| WASM target | 🧪 ‡ | — | ✅ | ✅ | — |
| Mobile transpiler | ✅ · 🧪 ‡ | — | RN | — | ✅ |
| LSP / IDE support | ✅ | ✅ | ✅ | ✅ | ✅ |
| Type checking | Gradual | mypy | TS | ✅ | ✅ |

<sup>† Type-annotated + inferred single-type functions (v10.1.0). Dynamic functions safely refused. &nbsp; ‡ Experimental / not yet CI-verified.</sup>

---

## CLI

<details>
<summary><strong>Full command reference</strong></summary>

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
</details>

---

## VS Code Extension

The official extension provides a first-class development experience:

- **Syntax Highlighting** — Full TextMate grammar for `.epl` files
- **Real-time Diagnostics** — Type errors, unused variables, parse errors
- **IntelliSense** — Autocomplete for keywords, builtins, and imports
- **Hover Docs** — Inline documentation for all 725+ built-in functions
- **Error Diagnostics** — Rust-style context windows with `--fix` auto-correction
- **Keybindings** — `Ctrl+Shift+R` to run, `Ctrl+Shift+K` to type-check

[Install from the VS Code Marketplace →](https://marketplace.visualstudio.com/publishers/epl-lang)

---

## Documentation

| Resource | Link |
|:---------|:-----|
| Getting Started | [docs/getting-started.md](docs/getting-started.md) |
| Language Specification | [docs/language-spec.md](docs/language-spec.md) |
| Tutorials | [docs/tutorials.md](docs/tutorials.md) |
| Package Manager | [docs/package-manager.md](docs/package-manager.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Publishing Packages | [docs/publishing.md](docs/publishing.md) |
| Full Site | [abneeshsingh21.github.io/EPL](https://abneeshsingh21.github.io/EPL/) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

---

## Contributing

EPL maintains enterprise-grade quality: every change is gated by Ruff lint + formatting, whole-tree `mypy`, an enforced coverage floor, dependency-review, and the **full** test suite (2,100+ tests) across Linux/Windows/macOS × Python 3.9–3.12. Releases publish to PyPI via OIDC trusted publishing.

```bash
git clone https://github.com/abneeshsingh21/EPL.git
cd EPL
pip install -e ".[dev,cloud]"
ruff format .
pytest tests/ -x --tb=short -q
```

Before contributing, please read:
[CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [CLA.md](CLA.md)

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the full list.

---

## Roadmap

- [x] Core language — interpreter, bytecode VM, LLVM native compiler
- [x] Web framework — HTTP/WebSocket router, WSGI/ASGI, middleware
- [x] Package manager — SemVer, lockfiles, checksums, dependency resolution
- [x] Developer tooling — LSP server, debugger, REPL, formatter, linter
- [x] Mobile targets — Android (Kotlin) · iOS (SwiftUI, experimental)
- [x] Desktop target — Compose Multiplatform
- [x] Cloud deploy — AWS ECS, GCP Cloud Run, Azure, Kubernetes
- [x] JS/TS bridge — Full NPM interop
- [x] AI integration — Built-in module, Error Explainer v2.0, copilot
- [x] Observability — Health checks, Prometheus metrics, structured logging
- [x] PyPI distribution — `pip install eplang`
- [x] VS Code extension — Syntax, diagnostics, IntelliSense
- [x] Documentation site and browser playground
- [x] 22 official packages
- [x] LSP v2 (semantic tokens, rename & references)
- [ ] WebSocket real-time collaboration
- [ ] GPU compute target (CUDA/ROCm via LLVM)

---

## Community

[GitHub Discussions](https://github.com/abneeshsingh21/EPL/discussions) · [Issue Tracker](https://github.com/abneeshsingh21/EPL/issues) · [Package Registry](https://abneeshsingh21.github.io/epl-packages-index/)

---

## Sponsor

EPL is built and maintained by [Abneesh Singh](https://github.com/abneeshsingh21) as an independent open-source project. If EPL is useful to you — in education, prototyping, or production — consider sponsoring its development:

<p align="center">
<a href="https://github.com/sponsors/abneeshsingh21"><strong>❤️ Sponsor on GitHub</strong></a>
</p>

Your sponsorship directly funds: new language features, official packages, documentation, VS Code extension updates, and security patches.

---

## License

Copyright © 2024–2026 **Abneesh Singh** (<contact@eplang.me>)

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution requirements.

> "EPL" and "English Programming Language" are trademarks of Abneesh Singh.

---

<p align="center">
<strong>⭐ Star this repo if EPL resonates with you</strong>
<br/><br/>
Made with precision by <a href="https://github.com/abneeshsingh21">Abneesh Singh</a>
</p>
