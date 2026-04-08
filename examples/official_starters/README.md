# EPL Official Starters

Three production-ready reference applications demonstrating EPL's native capabilities.

---

## 1. `auth_api/` — JWT Authentication API

A full auth backend with user registration, login, and token generation.

```bash
epl serve auth_api/main.epl
curl http://localhost:8080/api/health
curl -X POST http://localhost:8080/api/register -d '{"username":"alice","password":"secret123"}' -H 'Content-Type: application/json'
curl -X POST http://localhost:8080/api/login    -d '{"username":"alice","password":"secret123"}' -H 'Content-Type: application/json'
```

**Key patterns demonstrated:**
- `Import "epl-db"` for SQLite ORM
- `auth_hash_password / auth_verify_password / auth_generate_token`
- Nested `If` guards with clean error propagation
- HTTP status codes on routes (`Send json res with status 400`)

---

## 2. `chatbot/` — AI Chatbot with Fallback

A full-stack AI chatbot app with graceful degradation when no backend is running.

```bash
# Optional: start Ollama first
ollama serve

epl serve chatbot/main.epl
curl -X POST http://localhost:8080/api/chat -d '{"message":"Explain closures"}' -H 'Content-Type: application/json'
```

**Key patterns demonstrated:**
- `Use python "epl.ai" as ai` for AI backend connection
- `Try / Catch` fallback when backend is unavailable
- Structured `Map` response objects

---

## 3. `creative_frontend/` — Server-Rendered UI Showcase

A beautiful multi-page server-rendered frontend built entirely from EPL's native `Create WebApp` DSL.

```bash
epl serve creative_frontend/main.epl
# Open http://localhost:8080 in your browser
```

**Key patterns demonstrated:**
- `Route "/" shows Page...` server-rendered HTML pages
- `For Each item in list` dynamic rendering
- Multiple routes (/, /examples, /api/*)
- Mixed UI + JSON API from a single app

---

## Running All Three

```bash
# Auth API on port 8080 (default)
epl serve auth_api/main.epl

# Chatbot on port 8081
epl serve chatbot/main.epl --port 8081

# Creative frontend on port 8082
epl serve creative_frontend/main.epl --port 8082
```
