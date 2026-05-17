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
    users = ["Alice", "Bob"]
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
    name = request_params.name
    role = request_data.get("role")
    Send json Map with name = name and role = role and path = request_path
End
```

## Dynamic Route State

You can define variables before `Send json` and reuse them in page text with `$variable` templates.

```epl
Route "/hello/:name" shows
    title = "Welcome, " + request_params.name

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

db = open(":memory:")
create_table(db, "notes", Map with id = "INTEGER PRIMARY KEY AUTOINCREMENT" and title = "TEXT NOT NULL")

Route "/api/notes" responds with
    Send json Map with notes = query(db, "SELECT id, title FROM notes ORDER BY id")
End
```

## Authentication Helpers

EPL exposes auth helpers directly in the runtime:

```epl
hash = auth_hash_password("secret")
ok = auth_verify_password("secret", hash)
token = auth_generate_token(32)
```

The `auth` starter template combines these helpers with `epl-db` and request context bindings for login/register APIs.

## Chatbot and AI Apps

For chatbot-style apps, use the native WebApp DSL for HTTP routes and the Python bridge for model access:

```epl
Import "epl.ai" As ai

Route "/api/chat" responds with
    messages = [Map with role = "user" and content = request_data.get("message")]
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

## Adding Observability

Attach health checks, readiness probes, and Prometheus metrics to any web app:

```epl
Create WebApp called app

Import "epl.observability" As obs
obs.attach(app)

Route "/" shows
    Page "Home"
        Heading "My App"
    End
End

Start app on port 8000
```

This auto-registers:
- `/_health` — JSON health status (uptime, app name, version)
- `/_ready` — Readiness probe (toggleable via `obs.set_ready(true/false, "reason")`)
- `/_metrics` — Prometheus-format metrics (request count, error count, latency histogram, in-flight requests)

Use `obs.start_request()` and `obs.record_request(duration, error)` for per-route tracking.

## Deployment

### Local Deployment

```bash
epl deploy docker
epl deploy nginx
epl deploy systemd
epl deploy all
```

### Kubernetes

```bash
epl deploy k8s myapp.epl --app-name my-service --image my-registry/my-service:1.0 --port 8000 --host my-service.example.com --tls --replicas 3
```

Generates: Namespace, ConfigMap, Deployment (with resource limits and health probes), Service, Ingress (with TLS), and HorizontalPodAutoscaler.

### Cloud Providers

```bash
epl deploy aws myapp.epl --image my-service:latest --region us-east-1 --port 8000
epl deploy gcp myapp.epl --image my-service:latest --region us-central1 --port 8000
epl deploy azure myapp.epl --image my-service:latest --region eastus --port 8000
```

### Cloudflare Workers

EPL supports edge deployment via Cloudflare Workers. See `wrangler.jsonc` for configuration.

Generated deployment artifacts are validated in CI through Docker Compose, WSGI, and ASGI reference app smoke tests.
