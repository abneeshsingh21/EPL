# Build a REST API in Plain English

This guide builds a working JSON REST API in EPL — a programming language whose
keywords are ordinary English. If you can read a sentence, you can read this API.
Every snippet below is runnable; copy it, run it, and hit it with `curl`.

**Install:** `pip install eplang` · **Try in the browser (no install):**
[EPL Playground](https://abneeshsingh21.github.io/EPL/playground)

---

## The smallest possible API

Create a file `api.epl`:

```epl
Create WebApp called app

Route "/api/greeting" responds with
    Send json Map with message = "Hello from EPL" and status = "ok"
End

Start app on port 8000
```

Run it:

```bash
epl serve api.epl
```

Then in another terminal:

```bash
curl http://127.0.0.1:8000/api/greeting
```

```json
{
  "message": "Hello from EPL",
  "status": "ok"
}
```

That's a complete HTTP JSON endpoint. No framework to install, no boilerplate,
no decorators — `Create WebApp`, `Route ... responds with`, `Send json`.

---

## Returning a list of records

A `Map` is EPL's key–value object (like a JSON object / Python dict). A list of
maps is a JSON array of objects:

```epl
Create WebApp called app

Route "/api/users" responds with
    users = [Map with name = "Ada" and role = "admin", Map with name = "Bob" and role = "user"]
    Send json Map with data = users and count = length(users)
End

Start app on port 8000
```

```bash
curl http://127.0.0.1:8000/api/users
```

```json
{
  "data": [
    { "name": "Ada", "role": "admin" },
    { "name": "Bob", "role": "user" }
  ],
  "count": 2
}
```

`length(users)` is a built-in — no import required.

---

## Multiple routes and a health check

Real services expose several endpoints. Add as many `Route` blocks as you need:

```epl
Create WebApp called app

Route "/api/greeting" responds with
    Send json Map with message = "Hello from EPL" and status = "ok"
End

Route "/api/users" responds with
    users = [Map with name = "Ada" and role = "admin", Map with name = "Bob" and role = "user"]
    Send json Map with data = users and count = length(users)
End

Route "/health" responds with
    Send json Map with status = "healthy"
End

Start app on port 8000
```

A `/health` endpoint that returns `{"status": "healthy"}` is exactly what a load
balancer or Kubernetes liveness probe expects.

---

## How this compares

The same greeting endpoint in three languages:

=== "EPL"

    ```epl
    Route "/api/greeting" responds with
        Send json Map with message = "Hello from EPL" and status = "ok"
    End
    ```

=== "Python (Flask)"

    ```python
    @app.route("/api/greeting")
    def greeting():
        return {"message": "Hello", "status": "ok"}
    ```

=== "JavaScript (Express)"

    ```javascript
    app.get("/api/greeting", (req, res) => {
      res.json({ message: "Hello", status: "ok" });
    });
    ```

EPL reads as instructions, not symbols — which is the point. It's approachable for
beginners and non-native English speakers learning to program, while still running
on a real toolchain (interpreter, bytecode VM, and native compiler).

---

## Going to production

`epl serve` is the development server. For production, EPL generates WSGI/ASGI
adapters and deployment manifests:

```bash
pip install "eplang[server]"
epl serve api.epl --csp        # strict Content-Security-Policy
epl deploy k8s api.epl --image myapi:1.0 --tls
```

See the [Web Guide](web.md) for routing, sessions, templates, and the security
model, and [Deployment](../package-manager.md) for packaging.

---

## Next steps

- [Todo app with SQLite](database.md) — persist data, not just return it
- [Web Guide](web.md) — pages, forms, sessions, static files
- [Try it live in the browser](https://abneeshsingh21.github.io/EPL/playground)
- [Star EPL on GitHub](https://github.com/abneeshsingh21/EPL) if this was useful
