# Web Development with EPL

Build web apps with EPL's native `Create WebApp` runtime. This is the authoritative served web path used by `epl serve`, deploy generation, and the maintained starter templates.

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
```

```bash
epl serve app.epl
epl serve app.epl --port 3000
epl serve app.epl --dev
```

## Starter Templates

```bash
epl new mysite --template web
epl new myapi --template api
epl new myauth --template auth
epl new mybot --template chatbot
epl new myui --template frontend
epl new myapp --template fullstack
```

## Native Route Syntax

### Page route

```epl
Route "/" shows
    Page "Welcome"
        Heading "Welcome"
        Text "Server-rendered EPL page."
        Link "Users API" to "/api/users"
    End
End
```

### JSON route

```epl
Route "/api/users" responds with
    Create users equal to ["Alice", "Bob"]
    Send json Map with users = users and count = length(users)
End
```

## Request Context Variables

Inside native WebApp routes, EPL now exposes request context variables directly:

- `request_data`: POST/PUT/DELETE body as a map
- `request_params`: merged query parameters and path parameters
- `request_headers`: request headers as a map
- `request_method`: HTTP verb
- `request_path`: normalized path
- `request`: combined request object map
- `session_id`: current session identifier when present

Example:

```epl
Route "/users/:name" responds with
    Create name equal to request_params.name
    Create role equal to request_data.get("role")
    Send json Map with name = name and role = role and path = request_path
End
```

## Dynamic Route State

You can define variables before `Send json` and reuse them in page text with `$variable` templates.

```epl
Route "/hello/:name" shows
    Create title equal to "Welcome, " + request_params.name

    Page "$title"
        Heading "$title"
        Text "Served with method $request_method"
    End
End
```

## Database Integration

Use the supported `epl-db` facade for application data:

```epl
Import "epl-db"

Create db equal to open(":memory:")
Call create_table(db, "notes", Map with
    id = "INTEGER PRIMARY KEY AUTOINCREMENT"
    and title = "TEXT NOT NULL"
)

Route "/api/notes" responds with
    Send json Map with notes = query(db, "SELECT id, title FROM notes ORDER BY id")
End
```

## Authentication Helpers

EPL exposes auth helpers directly in the runtime:

```epl
Create hash equal to auth_hash_password("secret")
Create ok equal to auth_verify_password("secret", hash)
Create token equal to auth_generate_token(32)
```

The `auth` starter template combines these helpers with `epl-db` and request context bindings for login/register APIs.

## Chatbot and AI Apps

For chatbot-style apps, use the native WebApp DSL for HTTP routes and the Python bridge for model access:

```epl
Use python "epl.ai" as ai

Route "/api/chat" responds with
    Create messages equal to [Map with role = "user" and content = request_data.get("message")]
    Send json Map with reply = ai.chat(messages)
End
```

If no local/cloud model backend is configured, wrap the call in `Try` / `Catch` and return a fallback response. The `chatbot` starter template does this for you.

## Supported Facade Package

If you prefer helper wrappers around the lower-level request/response builtins, install:

```bash
epl install epl-web
```

`epl-web` is a supported helper facade. The native `Create WebApp` DSL remains the authoritative served runtime.

## Deployment

```bash
epl deploy docker
epl deploy nginx
epl deploy systemd
epl deploy all
```

Generated deployment artifacts are validated in CI through Docker Compose, WSGI, and ASGI reference app smoke tests.
