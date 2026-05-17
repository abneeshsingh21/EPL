---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# EPL — English Programming Language

<p class="subtitle">Write code the way you think. In plain English.</p>

<div class="badges">
  <a href="https://pypi.org/project/eplang/"><img src="https://img.shields.io/pypi/v/eplang?style=flat-square&color=blue" alt="PyPI"></a>
  <a href="https://github.com/abneeshsingh21/EPL"><img src="https://img.shields.io/github/stars/abneeshsingh21/EPL?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/abneeshsingh21/EPL/blob/main/LICENSE"><img src="https://img.shields.io/github/license/abneeshsingh21/EPL?style=flat-square" alt="License"></a>
</div>

<div class="install-cmd">
pip install eplang
</div>

</div>

---

## What is EPL?

EPL is an English-like programming language with its strongest coverage around interpreter/CLI workflows, package management, and maintained reference-app validation. Native compilation, transpilers, AI/data helpers, and generated platform targets are available, but their support level varies by toolchain and is defined by the [support matrix](support-matrix.md).

```epl
Say "Hello, World!"

name = "Alice"
If name == "Alice" then
    Say "Welcome back, Alice!"
End
```

---

## ⚡ Key Features

<div class="grid-cards" markdown>

<div class="card" markdown>
### 🌐 Web Framework
Build routed web apps and maintained reference services. Production hosting uses the optional server extras and generated WSGI/ASGI entrypoints documented in the support matrix.
</div>

<div class="card" markdown>
### ⚙️ LLVM Compiler
Compile EPL to native executables when `llvmlite` and a system compiler are available. Native builds are validated as an extra toolchain path, not the default install contract.
</div>

<div class="card" markdown>
### 📱 Android & Mobile
Generate Android Studio projects and Kotlin output. The maintained Android reference app is CI-validated; broader mobile targets require additional validation.
</div>

<div class="card" markdown>
### 🗄️ Database & ORM
SQLite workflows are bundled and documented. Additional database and ORM-style helpers exist, but non-SQLite production deployments should be validated in your own environment.
</div>

<div class="card" markdown>
### 🤖 ML & Data Science
Python-bridge integrations are available when the required dependencies are installed. These integrations are useful, but they are not part of the core release gate.
</div>

<div class="card" markdown>
### 🎮 Game Development
Game and graphics helpers exist for experimentation and targeted projects, but they sit outside the current production support boundary.
</div>

</div>

---

## Quick Example: REST API

```epl
Create WebApp called app

db = db_open("todos.db")
db_create_table(db, "todos", Map with id = "INTEGER PRIMARY KEY AUTOINCREMENT" and title = "TEXT NOT NULL" and done = "INTEGER DEFAULT 0")

Route "/api/todos" responds with
    todos = db_query(db, "SELECT * FROM todos")
    Return Map with success = True and data = todos
End

Route "/api/todos" responds with
    body = request_body()
    db_execute(db, "INSERT INTO todos (title) VALUES (?)", [body.get("title")])
    Return Map with success = True
End

app.start(8000)
```

```bash
epl serve todo.epl
# Production server starts on http://localhost:8000
```

---

## 🚀 Get Started

1. **[Install EPL](getting-started.md)** — `pip install eplang`
2. **[Try the Playground](playground.md)** — No install needed
3. **[Read the Tutorials](tutorials.md)** — Step-by-step guides
4. **[Browse Examples](examples.md)** — Real-world projects
5. **[Language Reference](language-reference.md)** — Full syntax docs

---

## Hundreds of Built-in and Packaged Functions

EPL ships a broad set of built-in and packaged functions across web, data, crypto, file I/O, networking, concurrency, GUI, and tooling domains.

Exact counts evolve over time. Use the [Full Standard Library Reference →](stdlib-reference.md) as the source of truth for the currently shipped surface.
