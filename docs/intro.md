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

EPL is a **production-grade programming language** where code reads like English sentences. It compiles to native executables via LLVM, runs on a bytecode VM, and transpiles to JavaScript, Python, Kotlin, and Swift.

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
Build production web servers with routing, middleware, CORS, sessions, WebSocket, and database integration — served via Waitress/Gunicorn.
</div>

<div class="card" markdown>
### ⚙️ LLVM Compiler
Compile EPL to native executables and WebAssembly. Get near-C performance for compute-heavy workloads.
</div>

<div class="card" markdown>
### 📱 Android & Mobile
Transpile to Kotlin and generate full Android Studio projects. Build APKs directly from the CLI.
</div>

<div class="card" markdown>
### 🗄️ Database & ORM
SQLite, PostgreSQL, MySQL with a full ORM — models, migrations, relationships, query builder, and transactions.
</div>

<div class="card" markdown>
### 🤖 ML & Data Science
Built-in wrappers for scikit-learn, PyTorch, TensorFlow, Pandas, and NumPy — train models in English.
</div>

<div class="card" markdown>
### 🎮 Game Development
Create 2D games with Pygame-powered sprites, collision detection, scenes, and animations.
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

## 725 Built-in Functions

EPL ships with **725 production-ready functions** across 33 domains:

| Domain | Functions | Highlights |
| ------ | --------- | ---------- |
| Web Server | 37 | Routes, middleware, templates, sessions |
| Database | 45 | SQLite/PostgreSQL/MySQL, ORM, migrations |
| HTTP Client | 8 | GET/POST/PUT/DELETE with auto-JSON |
| Crypto | 26 | AES, SHA, bcrypt, JWT, HMAC |
| File System | 33 | Read/write, glob, walk, binary I/O |
| Networking | 49 | TCP/UDP, DNS, WebSocket, HTTP server |
| ML/AI | 35 | Regression, classification, neural nets |
| Data Science | 47 | DataFrames, plotting, statistics |
| Concurrency | 98 | Threads, channels, mutexes, barriers |
| GUI | 37 | Windows, buttons, menus, canvas |
| Game Dev | 39 | Sprites, collision, scenes, animation |
| Mobile | 22 | Android/iOS scaffolding |

[Full Standard Library Reference →](stdlib-reference.md)
