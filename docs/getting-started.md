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
Create name equal to "Alice"
Create age equal to 25
Say "Hello, " + name
Say "You are " + age + " years old"
```

### Conditionals

```epl
Create score equal to 85

If score is greater than 90 then
    Say "Grade: A"
Otherwise
    Say "Grade: B"
End If
```

### Loops

```epl
Note: Count from 1 to 5
Repeat 5 times
    Say "Counting..."
End Repeat

Note: Loop over a list
Create fruits equal to ["apple", "banana", "mango"]
For Each fruit in fruits
    Say fruit
End For
```

### Functions

```epl
Define Function greet Takes name
    Return "Hello, " + name + "!"
End Function

Say greet("World")
```

### Classes

```epl
Class Animal
    Define Function Begin Takes name
        Set this.name equal to name
    End Function

    Define Function speak
        Say this.name + " makes a sound"
    End Function
End Class

Create dog equal to New Animal("Rex")
Call dog.speak()
```

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
Start server on port 8080
    Route GET "/"
        Send "Welcome to my EPL web app!"
    End Route

    Route GET "/hello"
        Send "Hello from EPL!"
    End Route
End Server
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

---

## 9. Next Steps

| Resource | Link |
| -------- | ---- |
| Official Book (PDF) | [epl_book.pdf](epl_book.pdf) |
| Language Reference | [language-reference.md](language-reference.md) |
| Tutorials | [tutorials.md](tutorials.md) |
| Architecture | [architecture.md](architecture.md) |
| Package Manager | [package-manager.md](package-manager.md) |
| Changelog | [../CHANGELOG.md](../CHANGELOG.md) |

---

## 10. Get Help

- 🐛 **Bug?** [Open an issue](https://github.com/abneeshsingh21/EPL/issues)
- 💡 **Feature request?** [Request here](https://github.com/abneeshsingh21/EPL/issues/new?template=feature_request.yml)
- ⭐ **Love EPL?** Star the repo on [GitHub](https://github.com/abneeshsingh21/EPL)!
