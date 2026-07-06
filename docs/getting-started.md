# Getting Started with EPL

> **EPL — English Programming Language**  
> Write code the way you think. In plain English.

---

## 1. Install EPL

EPL runs on Python 3.9+. Install it with pip:

```bash
pip install eplang
```

Verify the installation:

```bash
epl --version
```

---

## 2. Your First Program

Create a file called `hello.epl`:

```epl
Say "Hello, World!"
```

Run it:

```bash
epl hello.epl
```

Output:

```text
Hello, World!
```

---

## 3. Core Language Concepts

### Variables

```epl
name = "Alice"
age = 25
Say "Hello, " + name
Say "You are " + age + " years old"
```

### Conditionals

```epl
score = 85

If score is greater than 90 then
    Say "Grade: A"
Otherwise
    Say "Grade: B"
End
```

### Loops

```epl
Note: Count from 1 to 5
Repeat 5 times
    Say "Counting..."
End

Note: Loop over a list
fruits = ["apple", "banana", "mango"]
For Each fruit in fruits
    Say fruit
End
```

### Functions

```epl
Function greet takes name
    Return "Hello, " + name + "!"
End

Say greet("World")
```

### Classes

```epl
Class Animal
    name = "Unknown"

    Function speak
        Say name + " makes a sound"
    End
End

dog = New Animal()
dog.name = "Rex"
dog.speak()
```

### Using the Standard Library

Hundreds of helpers are built in and always available. Six modules also ship as importable wrappers: `json`, `encoding`, `net`, `os`, `regex`, and `sql`. A bare `Import` brings their functions in as plain names; an aliased import namespaces them:

```epl
Import "encoding"
Say to_base64("hi")          Note: prints aGk=

Import "regex" as RE
Say RE.test("[0-9]+", "abc123")   Note: prints true (the string contains digits)

Note: `json` is a reserved word, so import it with an alias for member access.
Import "json" as J
Say J.stringify(Map with ok = true and count = 3)
```

See the [standard library reference](stdlib-reference.md) for the full module APIs.

---

## 4. Use the Interactive REPL

The REPL lets you type and execute EPL code line by line:

```bash
epl repl
```

Useful REPL commands:

- `.vars` — show all defined variables
- `.help` — show available commands
- `.exit` — quit

---

## 5. Create a Web Server

```epl
Create WebApp called app

Route "/" shows
    Page "Welcome"
        Heading "Welcome to my EPL web app!"
        Text "This page is served by the native EPL web runtime."
    End
End

Route "/hello" responds with
    Send json Map with message = "Hello from EPL!"
End
```

Run it:

```bash
epl serve myapp.epl
```

---

## 6. Create a New Project

```bash
epl new myproject --template web
cd myproject
epl serve
```

---

## 7. CLI Quick Reference

```bash
epl <file.epl>           # Run a program
epl repl                 # Interactive REPL
epl new <name>           # Create new project
epl serve <file.epl>     # Start web server
epl build <file.epl>     # Compile to native binary
epl check <file.epl>     # Static type checking
epl fmt <file.epl>       # Format source code
epl install <package>    # Install a package
```

---

## 8. Try It in Your Browser

No installation needed — try EPL instantly at:

👉 **[EPL Online Playground](https://abneeshsingh21.github.io/EPL/playground.html)**

The browser playground assistant can be routed through:

- a secure proxy (`/chat` or a Cloudflare Worker URL)
- Groq directly with your own key
- Gemini directly with your own key

For the full local playground server with isolated execution and the native `/api/assist` route:

```bash
epl playground
```

---

## 9. JavaScript/TypeScript Bridge

Access the NPM ecosystem directly from EPL:

```bash
epl jsinstall lodash
epl jsinstall axios
```

```epl
Use javascript "lodash" as lodash
Use javascript "axios" as axios

Say lodash.capitalize("hello from epl")
```

Manage JS dependencies:
```bash
epl jsdeps            # List installed JS packages
epl jsremove lodash   # Remove a package
```

---

## 10. Deploy to Production

### Kubernetes
```bash
epl deploy k8s myapp/main.epl --image myapp:1.0 --host myapp.example.com --tls
```

### Cloud Providers
```bash
epl deploy aws myapp/main.epl --image myapp:latest --region us-east-1
epl deploy gcp myapp/main.epl --image myapp:latest --region us-central1
epl deploy azure myapp/main.epl --image myapp:latest --region eastus
```

---

## 11. Observability

Add health checks, metrics, and structured logging to any web app:

```epl
Create WebApp called app

Import "epl.observability" As obs
obs.attach(app)

Note: This auto-adds:
Note:   /_health  — JSON health status
Note:   /_ready   — readiness probe
Note:   /_metrics — Prometheus-format metrics
```

---

## 12. Next Steps

| Resource | Link |
| -------- | ---- |
| Official Book (PDF) | [epl_book.pdf](epl_book.pdf) |
| Language Reference | [language-reference.md](language-reference.md) |
| Tutorials | [tutorials.md](tutorials.md) |
| Architecture | [architecture.md](architecture.md) |
| Package Manager | [package-manager.md](package-manager.md) |
| Changelog | [CHANGELOG.md](https://github.com/abneeshsingh21/EPL/blob/main/CHANGELOG.md) |

---

## 13. Get Help

- 🐛 **Bug?** [Open an issue](https://github.com/abneeshsingh21/EPL/issues)
- 💡 **Feature request?** [Request here](https://github.com/abneeshsingh21/EPL/issues/new?template=feature_request.yml)
- ⭐ **Love EPL?** Star the repo on [GitHub](https://github.com/abneeshsingh21/EPL)!
