# EPL Examples

These examples are written for EPL v9.7.0 and use the current parser-backed syntax. For release-gated support claims, use `docs/support-matrix.md`, `docs/reference-apps.md`, and the tests as the final source of truth.

---

## Hello CLI

```epl
Say "Hello from EPL"

Ask "What is your name? " store in name
Say "Welcome, $name"
```

```bash
epl run hello.epl
```

---

## Calculator

```epl
Function add takes a, b
    Return a + b
End

Function multiply takes a, b
    Return a * b
End

running = True

While running
    Ask "command (add/mul/quit): " store in command

    If command == "quit" Then
        running = False
    Otherwise If command == "add" Then
        Ask "a: " store in a_text
        Ask "b: " store in b_text
        Say add(to_integer(a_text), to_integer(b_text))
    Otherwise If command == "mul" Then
        Ask "a: " store in a_text
        Ask "b: " store in b_text
        Say multiply(to_integer(a_text), to_integer(b_text))
    Otherwise
        Say "Unknown command"
    End
End
```

---

## Hello Web

A minimal native WebApp with a page route and JSON health route.

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
    Send json Map with status = "ok" and version = "9.7.0"
End

Start app on port 8000
```

```bash
epl serve app.epl --port 8000
```

---

## TODO API With SQLite

Production-oriented pattern: use raw `CREATE TABLE` migrations through `db_execute`, and use parameter placeholders for external values.

```epl
Create WebApp called app

db = db_open("todos.db")
db_execute(db, "CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0)")

Route "/api/todos" responds with
    todos = db_query(db, "SELECT id, title, completed FROM todos ORDER BY id DESC")
    Send json Map with success = True and data = todos
End

Route "/api/todos/create" responds with
    title = request_data.get("title", "")

    If length(trim(title)) == 0 Then
        Send json Map with success = False and error = "Title is required"
    Otherwise
        db_execute(db, "INSERT INTO todos (title) VALUES (?)", [title])
        Send json Map with success = True and message = "Created"
    End
End
```

```bash
epl serve todo_api.epl --port 8000
curl http://localhost:8000/api/todos
curl -X POST http://localhost:8000/api/todos/create -H "Content-Type: application/json" -d "{\"title\":\"Buy groceries\"}"
```

---

## Auth API Building Blocks

```epl
Create WebApp called app

db = db_open("auth.db")
db_execute(db, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)")

Route "/api/register" responds with
    username = trim(request_data.get("username", ""))
    password = request_data.get("password", "")

    If length(username) < 3 Then
        Send json Map with ok = False and error = "Username must be at least 3 characters"
    Otherwise If length(password) < 8 Then
        Send json Map with ok = False and error = "Password must be at least 8 characters"
    Otherwise
        password_hash = auth_hash_password(password)

        Try
            db_execute(db, "INSERT INTO users (username, password_hash) VALUES (?, ?)", [username, password_hash])
            Send json Map with ok = True
        Catch error
            Send json Map with ok = False and error = "Username already exists"
        End
    End
End
```

For production, store JWT secrets in environment variables or a secret manager, not in source code.

---

## JSON And HTTP

```epl
raw = "{\"name\":\"EPL\",\"version\":\"9.7.0\"}"
data = json_parse(raw)

Say data.name
Say json_stringify(Map with ok = True and language = data.name)

response = http_get("https://example.com")
Say response.status
```

Network helpers can be disabled in sandbox mode. Wrap external calls in `Try`/`Catch`.

---

## Python Bridge

```epl
Note: `json` is a reserved token, so alias the Python module to a non-reserved name.
Use python "json" as pyjson

payload = pyjson.loads("{\"ok\": true}")
Say payload.get("ok")

Note: For timestamps, prefer EPL's native now() over the Python datetime bridge.
Say now()
```

Declare third-party Python dependencies in `epl.toml`:

```toml
[python-dependencies]
requests = "*"
yaml = "pyyaml>=6"
```

---

## JavaScript Bridge

```epl
Use javascript "lodash" as lodash

name = lodash.capitalize("english programming language")
Say name
```

Install dependencies with:

```bash
epl jsinstall lodash
```

---

## Data Analysis

Data science helpers depend on optional Python packages such as pandas and matplotlib.

```epl
df = ds_read_csv("sales.csv")
Say ds_shape(df)
Say ds_describe(df)

total = ds_sum(df, "revenue")
Say "Total revenue: $" + to_text(total)

ds_bar_chart(df, "month", "revenue")
ds_save_plot("revenue_chart.png")
```

Use this path only after validating optional dependencies in the target environment.

---

## Machine Learning

Machine learning helpers depend on optional ML packages. Treat them as integration helpers and pin dependencies in your project.

```epl
data = ml_load_data("iris")
split = ml_split(data, 0.8)

model = ml_random_forest(get(split, "train"))
ml_train(model)

accuracy = ml_accuracy(model, get(split, "test"))
Say "Accuracy: " + to_text(accuracy * 100) + "%"

ml_save_model(model, "iris_model.pkl")
```

---

## WebSocket Server

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

Validate WebSocket behavior behind your production proxy/load balancer.

---

## Kubernetes Deployment

Generate deployment manifests:

```bash
epl deploy k8s myapp.epl --app-name my-service --image my-registry/my-service:1.2.0 --port 8000 --host my-service.example.com --tls --replicas 3
```

Generated manifests should be reviewed against your cluster policy, secrets model, ingress controller, and rollout process before production use.

---

## Observability

```epl
Create WebApp called app

Import "epl.observability" as obs
obs.attach(app)

Route "/api/data" responds with
    obs.start_request()
    Send json Map with result = "ok"
    obs.record_request(0.042, Nothing)
End

Start app on port 8000
```

This exposes health, readiness, and metrics endpoints when the observability module is available.

---

## Style, 3D, Canvas, And Game APIs

EPL includes parser and runtime surfaces for UI style/layout, 3D/canvas, and game/data helpers, but these areas evolve faster than the core language. For enterprise-facing documentation:

- prefer maintained examples under `examples/` and `apps/reference-*`
- require parser and runtime tests for any snippet you publish
- pin optional dependencies
- document fallback behavior explicitly

---

## More Examples

Use the local examples directory as the first source:

```bash
examples/
apps/reference-backend-api/
apps/reference-fullstack-web/
apps/reference-android/
```
