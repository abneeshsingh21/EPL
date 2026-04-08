<div align="center">

# 🌐 EPL — English Programming Language

### *Write code the way you think. In plain English.*

[![PyPI version](https://img.shields.io/pypi/v/eplang?color=blue&label=pip%20install%20eplang&style=for-the-badge)](https://pypi.org/project/eplang/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![VS Code](https://img.shields.io/badge/VS%20Code-Extension-007ACC?style=for-the-badge&logo=visual-studio-code)](https://marketplace.visualstudio.com/publishers/epl-lang)
[![GitHub Stars](https://img.shields.io/github/stars/abneeshsingh21/EPL?style=for-the-badge&logo=github)](https://github.com/abneeshsingh21/EPL/stargazers)

<br/>

> **EPL is a fully-featured, production-ready programming language where every keyword is natural English.**
> Build web apps, APIs, Android apps, desktop tools, AI pipelines — all in a syntax anyone can read.

<br/>

```
pip install eplang
```

</div>

---

## ✨ What does EPL look like?

```epl
Note: Hello World
Say "Hello, World!"

Note: Variables
Create name equal to "Abneesh"
Create age equal to 20

Note: Conditionals
If age is greater than 18 then
    Say "Welcome, " + name
Otherwise
    Say "Access denied"
End

Note: Functions
Define Function greet Takes person
    Return "Hello, " + person + "!"
End

Say greet("World")

Note: Loops
Repeat 5 times
    Say "EPL is awesome!"
End

Note: Lists
Create fruits equal to ["apple", "banana", "mango"]
For Each fruit in fruits
    Say fruit
End

Note: Web Server
Create WebApp called app

Route "/" shows
    Page "Welcome"
        Heading "Welcome to EPL"
        Text "This page is served by the native EPL web runtime."
    End
End

Route "/api/health" responds with
    Send json Map with status = "ok"
End
```

**No semicolons. No curly braces. No cryptic symbols. Just English.**

---

## 🚀 Quick Start

### Install

```bash
pip install eplang
```

### Run your first program

```bash
echo 'Say "Hello from EPL!"' > hello.epl
epl hello.epl
```

### Start the interactive REPL

```bash
epl repl
```

### Create a full project

```bash
epl new myapp --template web
epl new authapp --template auth
epl new botapp --template chatbot
epl new studio --template frontend
cd myapp
epl serve
```

---

## 🆚 EPL vs Other Languages

| Feature | EPL | Python | JavaScript | Java |
|---------|-----|--------|------------|------|
| Syntax readability | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Learning curve | Minutes | Days | Days | Weeks |
| Web framework built-in | ✅ | ❌ | ❌ | ❌ |
| Android transpiler | ✅ | ❌ | ❌ | ✅ |
| WASM compilation | ✅ | ❌ | ✅ | ❌ |
| Native compiler (LLVM) | ✅ | ❌ | ❌ | ✅ |
| Package manager | ✅ | pip | npm | Maven |
| LSP / IDE support | ✅ | ✅ | ✅ | ✅ |
| AI assistant built-in | ✅ | ❌ | ❌ | ❌ |

---

## 🏗️ What Can You Build?

### 🌐 Web Applications
```epl
Create WebApp called apiApp

Route "/api/users" responds with
    Create users equal to ["Alice", "Bob"]
    Send json Map with users = users and count = length(users)
End
```

### 🤖 AI & Machine Learning
```epl
Use python "epl.ai" as ai

Create messages equal to [Map with role = "user" and content = "Explain quantum computing simply"]
Create response equal to ai.chat(messages)
Say response
```

### 🗄️ Database Apps
```epl
Import "epl-db"

Create db equal to open("myapp.db")
Call create_table(db, "users", Map with name = "TEXT" and email = "TEXT")
Call insert(db, "users", Map with name = "Ada" and email = "ada@example.com")
Say query(db, "SELECT * FROM users")
```

### 📱 Android Apps (Kotlin transpile)
```bash
epl android myapp/main.epl   # Generates full Android Studio project
```

### 🍎 iOS Apps (SwiftUI project generation)
```bash
epl ios myapp/main.epl       # Generates Xcode / SwiftUI project
```

### 🖥️ Desktop Apps
```bash
epl desktop myapp/main.epl   # Generates Compose Multiplatform desktop app
```

### ⚡ Native Executables
```bash
epl build myapp/main.epl     # Compiles via LLVM to native .exe / binary
```

---

## 📦 CLI Reference

```bash
epl run <file.epl>        # Run a program
epl repl                  # Interactive REPL
epl new <name>            # Create new project
epl build <file.epl>      # Compile to native executable
epl wasm <file.epl>       # Compile to WebAssembly
epl serve <file.epl>      # Start web server
epl test [dir]            # Run test suite
epl check [file]          # Static type checking
epl fmt <file>            # Format source code
epl lint [file]           # Lint source code
epl android <file.epl>    # Generate Android project
epl ios <file.epl>        # Generate iOS project
epl desktop <file.epl>    # Generate desktop app
epl install <package>     # Install a package
epl upgrade               # Update EPL
```

---

## 🔋 Feature Highlights

| Category | Features |
|----------|----------|
| **Language** | OOP, async/await, generics, pattern matching, lambdas, generators |
| **Performance** | Bytecode VM, LLVM native compiler, constant folding, dead code elimination |
| **Web** | HTTP router, WebSocket, WSGI/ASGI, middleware, sessions, templates |
| **Database** | SQLite ORM, Redis, PostgreSQL, Store/Fetch/Delete English APIs |
| **Security** | Safe FFI sandbox, pickle allowlist, recursion limits, scope depth limits |
| **Tooling** | LSP server, debugger, REPL, test framework, code coverage, formatter |
| **Targets** | Interpreter, VM, LLVM native, JavaScript, Node.js, Kotlin, Python, WASM, MicroPython |
| **Packaging** | SemVer package manager, lockfiles, checksums, PyPI integration |
| **AI** | Built-in `ai` module, code generation, explanation via Groq/OpenAI |
| **Standard Library** | 300+ functions across HTTP, DB, Math, Crypto, File I/O, JSON, Regex, Date |

---

## 📚 Documentation

| Resource | Link |
|----------|------|
| Official Book (PDF)| [docs/epl_book.pdf](docs/epl_book.pdf) |
| Language Reference | [docs/language-reference.md](docs/language-reference.md) |
| Getting Started | [docs/getting-started.md](docs/getting-started.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Package Manager | [docs/package-manager.md](docs/package-manager.md) |
| Tutorials | [docs/tutorials.md](docs/tutorials.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

---

## 🛠️ VS Code Extension

Install the EPL extension for:
- ✅ Syntax highlighting for `.epl` files
- ✅ Real-time diagnostics (type errors, unused variables)
- ✅ Auto-completions and hover docs
- ✅ Run files with `Ctrl+Shift+R`
- ✅ Type check with `Ctrl+Shift+K`

**Install:** Search `EPL` in VS Code Extensions, or visit the [Marketplace](https://marketplace.visualstudio.com/publishers/epl-lang).

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/abneeshsingh21/EPL.git
cd EPL
pip install -e ".[dev]"
python -m pytest tests/
```

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the list of contributors.

---

## 🗺️ Roadmap

- [x] Core language (interpreter + VM + LLVM)
- [x] Web framework, ORM, async I/O
- [x] Package manager with lockfiles
- [x] LSP server, debugger, REPL
- [x] Android & Desktop transpilers
- [x] PyPI release (`pip install eplang`)
- [x] VS Code extension
- [x] Official documentation website
- [x] Online playground (try EPL in browser)
- [ ] Community package registry
- [ ] iOS transpiler
- [ ] EPL Notebook (Jupyter-style)

---

## 📄 License

Copyright © 2024–2026 **Abneesh Singh** (<singhabneesh250@gmail.com>)

Licensed under the MIT License with attribution requirements. See [LICENSE](LICENSE) for details.

> "EPL" and "English Programming Language" are trademarks of Abneesh Singh.

---

<div align="center">

**⭐ Star this repo if EPL excites you!**

Made with ❤️ by [Abneesh Singh](https://github.com/abneeshsingh21)

</div>
