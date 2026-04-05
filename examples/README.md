# EPL Examples

Real-world examples demonstrating EPL's capabilities.

## 🌐 hello_web — Web Server

Minimal production-ready web server with HTML pages and JSON APIs.

```bash
epl serve examples/hello_web/main.epl
# Production server starts on http://localhost:8000

epl serve examples/hello_web/main.epl --dev
# Development mode with hot-reload
```

**Features:** HTML pages, JSON API, health checks, production server (waitress/gunicorn)

## 📝 todo_api — REST API

Full RESTful TODO API with SQLite database, CRUD operations, and auto-documentation.

```bash
epl serve examples/todo_api/main.epl

# Test the API:
curl http://localhost:8000/api/todos
curl -X POST http://localhost:8000/api/todos -d '{"title":"Buy groceries"}'
curl -X PUT http://localhost:8000/api/todos/1 -d '{"completed": 1}'
curl -X DELETE http://localhost:8000/api/todos/1
```

**Features:** SQLite, CRUD, parameterized queries, API documentation page

## 🧮 calculator — CLI App

Interactive command-line calculator with history, math functions, and a REPL.

```bash
epl run examples/calculator/main.epl
```

**Features:** REPL loop, expression evaluation, history, error handling
