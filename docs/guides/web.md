# Web Guide

Build web apps with EPL's native `Create WebApp` runtime. This is the authoritative served web path used by `epl serve`, deployment generation, and maintained starter templates.

---

## Quick Start

```epl
Create WebApp called app

Route "/" shows
    Page "Hello EPL"
        Heading "Hello from EPL"
        Text "This page is served by the native EPL web runtime."
        Link "Health API" to "/api/health"
    End
End

Route "/api/health" responds with
    Send json Map with status = "ok" and service = "demo"
End

Start app on port 8000
```

```bash
epl serve app.epl
epl serve app.epl --port 3000
epl serve app.epl --dev
```

When `epl serve` hosts the file, the CLI can control the port. `Start app on port ...` is useful in direct-run standalone programs.

---

## Starter Templates

```bash
epl new mysite --template web
epl new myapi --template api
epl new myauth --template auth
epl new mybot --template chatbot
epl new myui --template frontend
epl new myapp --template fullstack
```

Review generated starters before production deployment. They are scaffolds, not a substitute for your security and operations policy.

---

## Native Route Syntax

Page route:

```epl
Route "/" shows
    Page "Welcome"
        Heading "Welcome"
        Text "Server-rendered EPL page."
        Link "Users API" to "/api/users"
    End
End
```

JSON route:

```epl
Route "/api/users" responds with
    users = ["Alice", "Bob"]
    Send json Map with users = users and count = length(users)
End
```

Path parameters — both the colon form (`:name`) and the brace form (`{name}`)
are supported and equivalent:

```epl
Route "/users/:name" responds with
    Send json Map with name = name
End

Route "/users/{id}" responds with
    Send json Map with id = id
End
```

Each captured parameter is available three ways inside the route body: as a
**bare variable** (`name`, `id`), via `request_params.name`, and via
`web_request_param("name")`. The bare-variable form matches the syntax used
throughout the example apps.

### Redirects

Issue an HTTP redirect with either the standalone statement or the `Send` alias:

```epl
Route "/old" responds with
    Send redirect "/new"
End

Route "/save" shows
    Redirect to "/"
End
```

---

## Request Context Variables

Inside native WebApp routes, EPL exposes:

| Variable | Description |
| --- | --- |
| `request_data` | Parsed body map for JSON/form requests |
| `request_params` | Merged path and query parameters |
| `request_headers` | Request headers map |
| `request_method` | HTTP method |
| `request_path` | Normalized request path |
| `request` | Combined request object |
| `session_id` | Current session identifier when present |

Example:

```epl
Route "/users/:name" responds with
    name = request_params.name
    role = request_data.get("role", "guest")
    Send json Map with name = name and role = role and path = request_path
End
```

---

## Dynamic Route State

Variables defined before `Page` or `Send json` can be used inside the route.

```epl
Route "/hello/:name" shows
    title = "Welcome, " + request_params.name

    Page "$title"
        Heading "$title"
        Text "Served with method $request_method"
    End
End
```

---

## Page Elements

```epl
Page "Dashboard"
    Heading "Dashboard"
    Subheading "Today"
    Text "Status: $status"
    Link "Home" to "/"
    Button "Refresh" class "primary"
    Div class "panel"
        Text "Nested content"
    End
End
```

Supported HTML DSL areas include headings, text, links, images, buttons, forms, structural elements, styles, event helpers, and raw HTML. Use `Raw HTML` only for trusted static markup.

```epl
Page "Trusted Markup"
    Raw HTML "<strong>Trusted static markup</strong>"
End
```

Never pass user-controlled input into `Raw HTML`.

### Forms and inputs

`Input` is **positional** (`Input "field_name"`), and `Form` takes an `action`
(method defaults to `POST`):

```epl
Page "Add Task"
    Form action "/add"
        Input "title" placeholder "What needs doing?"
        Button "Save"
    End
End
```

This renders `<form method="POST" action="/add">` with a text `<input name="title">`.

### Stylesheet (raw CSS)

`Stylesheet ... End` is a **raw-CSS block** — its body is literal CSS injected
verbatim into the page `<head>` (not a container for nested `Style` selectors):

```epl
Page "Styled"
    Stylesheet
        .card { border-radius: 12px; padding: 16px; }
        .card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.1); }
    End
    Div class "card"
        Text "Hover me"
    End
End
```

---

## Database Integration

Use built-in SQLite helpers directly for the stable path.

```epl
Create WebApp called app

db = db_open("notes.db")
db_execute(db, "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)")

Route "/api/notes" responds with
    notes = db_query(db, "SELECT id, title FROM notes ORDER BY id")
    Send json Map with ok = True and notes = notes
End
```

`db_query` always returns a **list of row maps**. For a single value (e.g. a
`count(*)` or a lookup by id), use `db_query_one`, which returns the first row
map (or null), so property access works directly:

```epl
row = db_query_one(db, "SELECT count(*) as count FROM notes")
total = row.count

Route "/api/notes/create" responds with
    title = trim(request_data.get("title", ""))

    If length(title) == 0 Then
        Send json Map with ok = False and error = "Title is required"
    Otherwise
        db_execute(db, "INSERT INTO notes (title) VALUES (?)", [title])
        Send json Map with ok = True
    End
End
```

`db_create_table` accepts standard column constraints (`INTEGER PRIMARY KEY`, `TEXT NOT NULL`, `VARCHAR(255)`, …), so it is fine for most tables. For foreign keys, indexes, and `DEFAULT`/`CHECK` clauses, use versioned SQL migrations through `db_execute`. See the [database guide](database.md) for the full boundary.

---

## Authentication Helpers

EPL exposes auth helpers directly in the runtime:

```epl
password_hash = auth_hash_password("secret-password")
ok = auth_verify_password("secret-password", password_hash)
token = auth_generate_token(32)
```

JWT pattern:

```epl
secret = env_get("JWT_SECRET", "")
payload = Map with user_id = 123 and role = "admin"
token = auth_jwt_create(payload, secret, 3600)
verified = auth_jwt_verify(token, secret)
```

Production requirements:

- keep secrets out of source
- require TLS at the proxy/load balancer
- set secure cookie/session policy
- rate-limit login and token endpoints
- log security events without logging passwords or tokens

---

## Chatbot And AI Apps

Use the native WebApp DSL for HTTP routes and the Python bridge or AI module for model access.

```epl
Import "epl.ai" as ai

Route "/api/chat" responds with
    message = request_data.get("message", "")
    messages = [Map with role = "user" and content = message]

    Try
        reply = ai.chat(messages)
        Send json Map with ok = True and reply = reply
    Catch error
        Send json Map with ok = False and error = "AI backend unavailable"
    End
End
```

Production AI routes need timeouts, request limits, audit logs, and explicit fallback behavior.

---

## WebSocket Helpers

```epl
server = ws_server_create(8090)

Function connected takes client_id
    Say "Connected: " + client_id
End

Function received takes client_id, message
    ws_broadcast(server, client_id + ": " + message)
End

ws_on_connect(server, connected)
ws_on_message(server, received)
ws_server_start(server)
```

Validate WebSocket behavior through your reverse proxy and load balancer before production use.

---

## Observability

```epl
Create WebApp called app

Import "epl.observability" as obs
obs.attach(app)

Route "/" shows
    Page "Home"
        Heading "My App"
    End
End

Start app on port 8000
```

When the observability module is available, it can register:

- `/_health`
- `/_ready`
- `/_metrics`

Use route-level timing and structured logs for production workflows.

---

## Deployment

Local generation:

```bash
epl deploy docker
epl deploy nginx
epl deploy systemd
epl deploy all
```

Kubernetes:

```bash
epl deploy k8s myapp.epl --app-name my-service --image my-registry/my-service:1.0 --port 8000 --host my-service.example.com --tls --replicas 3
```

Cloud providers:

```bash
epl deploy aws myapp.epl --image my-service:latest --region us-east-1 --port 8000
epl deploy gcp myapp.epl --image my-service:latest --region us-central1 --port 8000
epl deploy azure myapp.epl --image my-service:latest --region eastus --port 8000
```

Generated deployment artifacts should be reviewed against your organization's runtime, secret, ingress, logging, and rollout policies.

---

## Enterprise Web Checklist

- Validate all request data before use.
- Use `Send json` for API responses.
- Avoid raw exception messages in user-facing responses.
- Keep secrets in environment variables or a secret manager.
- Use parameterized SQL for every database value.
- Review proxy trust, forwarded headers, TLS, and rate-limiting behavior.
- Test `GET`, `POST`, `HEAD`, `OPTIONS`, and error paths for every public route.
- Add health, readiness, and metrics endpoints for deployed services.
- Run smoke tests against the exact WSGI/ASGI/deployment entrypoint you ship.
