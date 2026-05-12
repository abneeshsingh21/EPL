# 🌐 EPL Online Playground

Try EPL directly in your browser — no installation required.

<iframe src="playground.html" width="100%" height="700" frameborder="0" style="border-radius: 12px; border: 1px solid var(--md-default-fg-color--lightest);"></iframe>

!!! tip "Can't see the playground?"
    Open it directly: [playground.html](https://abneeshsingh21.github.io/EPL/playground.html)

## Assistant Routing

The browser playground loads the published `eplang` runtime in Pyodide, runs parser-backed AST diagnostics, and supports explicit assistant routing:

- `Secure Proxy` for a same-origin `/chat` endpoint or a Cloudflare Worker URL
- `Groq API` for direct browser requests with your own Groq key
- `Gemini API` for direct browser requests with your own Gemini key

The page no longer uses an anonymous third-party fallback. You decide exactly where assistant traffic goes. For public deployments, prefer Secure Proxy mode so private Groq/Gemini keys are not stored in a public browser page.

For the full local playground server with isolated code execution and `/api/assist`, run:

```bash
epl playground
```

## Example Snippets

Try pasting these into the playground:

### Hello World
```epl
Say "Hello from EPL!"
```

### Variables & Math
```epl
x = 10
y = 20
Say "Sum: " + to_string(x + y)
```

### Functions
```epl
Function factorial takes n
    If n is less than 2 then
        Return 1
    End
    Return n * factorial(n - 1)
End

Say "10! = " + to_string(factorial(10))
```

### Lists & Loops
```epl
names = ["Alice", "Bob", "Charlie"]
For Each name in names
    Say "Hello, " + name + "!"
End
```

### Web App with Observability
```epl
Create WebApp called app

Import "epl.observability" As obs
obs.attach(app)

Route "/" shows
    Page "EPL App"
        Heading "Hello from EPL!"
        Text "Monitoring: /_health | /_ready | /_metrics"
    End
End

Start app on port 8000
```

### JavaScript Bridge
```epl
Use javascript "lodash" as _
Say _.capitalize("hello from epl")
Say _.shuffle([1, 2, 3, 4, 5])
```

### 3D Scene
```epl
Scene "demo" 800 by 600
    Box "cube" at 0 1 0 size 2 2 2 color "#ff4500"
    Light "sun" at 5 10 5
    Camera at 0 5 10 look 0 0 0
End
```

## Features

- **AST-Aware Analysis** — Real-time error detection with gutter markers
- **AI Copilot** — Multi-provider support (Secure Proxy, Groq, Gemini) with code injection
- **Thinking Mode** — Complex queries show reasoning process before generating code
- **Full EPL Support** — All language features including web apps, 3D/canvas, style/layout, and JS bridge
