# Deploying EPL Servers

This guide covers running every deployable EPL server in production. All
servers follow two enterprise principles:

1. **Secure by default** — they bind to `127.0.0.1` (localhost only) unless you
   explicitly opt into a public bind. Nothing is exposed to the network until
   you say so.
2. **Deploy anywhere** — bind address, port, and worker count are all
   resolvable from environment variables, so the same artifact runs unchanged
   on Cloud Run, Heroku, Azure App Service, Kubernetes, bare metal, or your
   laptop. Cloud platforms that inject `PORT` work with zero config.

---

## Quick reference

| Server | Command | Default bind | Health check | Public-bind opt-in |
|--------|---------|--------------|--------------|--------------------|
| **Web app** (your EPL site/API) | `epl serve app.epl` | `127.0.0.1:3000` (dev) / `0.0.0.0:8000` (prod runtime) | `GET /_health` | `EPL_WEB_HOST=0.0.0.0` or `--host` |
| **Package registry** | `epl registry start` | `127.0.0.1:4873` | `GET /health` | `EPL_REGISTRY_HOST=0.0.0.0` or `--host` |
| **Playground** | `epl playground` | `127.0.0.1:8080` | `GET /health` | `EPL_PLAYGROUND_HOST=0.0.0.0` or `--host` |
| **MCP HTTP server** | `python -m epl.mcp_http_server` | `0.0.0.0:8000` | `GET /health` | (already public; set CORS) |

---

## Environment variables

### Web application (`epl serve`, `epl.web`, `epl.deploy.serve`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `EPL_WEB_HOST` / `EPL_HOST` | Bind address | `127.0.0.1` (dev), `0.0.0.0` (prod runtime) |
| `EPL_WEB_PORT` | Listen port (explicit override) | `3000` (dev) / `8000` (prod) |
| `PORT` | Listen port (platform-injected; Cloud Run/Heroku/Azure) | — |
| `EPL_WEB_WORKERS` | Worker/thread count | `32` (dev), `4` (prod) |
| `WEB_CONCURRENCY` | Worker count (platform standard, gunicorn artifacts) | — |

**Precedence (highest first):** `EPL_WEB_*` → `PORT` / `WEB_CONCURRENCY` →
value in source / CLI flag. Explicit EPL variables always win over the generic
platform variables, so you can pin a value even on a platform that injects
`PORT`.

> The same precedence applies to the generated `gunicorn_conf.py`, so a
> containerized app rebinds at **runtime** from `PORT`/`EPL_PORT` without
> rebuilding the image.

### Package registry (`epl registry start`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `EPL_REGISTRY_HOST` | Bind address | `127.0.0.1` |
| `EPL_REGISTRY_PORT` / `PORT` | Listen port | `4873` |

CLI flags `--host` and `--port` override the environment. Binding to
`0.0.0.0` prints a security warning to stderr — only do it behind a trusted
network boundary or reverse proxy, and configure publish auth tokens.

### Playground (`epl playground`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `EPL_PLAYGROUND_HOST` | Bind address | `127.0.0.1` |
| `PORT` / `WEBSITES_PORT` | Listen port (Azure App Service injects these) | `8080` |

### MCP HTTP server (`python -m epl.mcp_http_server`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `PORT` | Listen port | `8000` |
| `EPL_MCP_CORS_ORIGIN` | Allowed CORS origin for browser clients | `null` (no cross-origin) |

Set `EPL_MCP_CORS_ORIGIN=https://your-frontend.example.com` in production. Do
**not** use `*` — pin it to your exact origin.

### Application secrets (`.env`)

`epl run` and `epl serve` auto-load a `.env` file from the program's directory
and the current working directory, so your app reads secrets via
`env_get("NAME")` with no manual `export`. Real environment variables (those
injected by your platform/orchestrator) always take precedence over `.env`, so
the same code runs in dev and prod unchanged.

| Variable | Purpose | Default |
|----------|---------|---------|
| `EPL_NO_DOTENV` | Set to disable `.env` auto-loading | (unset = enabled) |

- Commit a `.env.example` (blank values); add `.env` to `.gitignore`.
- In production, prefer real env vars / a secret manager over shipping a `.env`.
- `.env` is **not** loaded under `--sandbox`.

---

## Deployment recipes

### Local development

```bash
epl serve app.epl --dev            # threaded dev server, hot-reload, 127.0.0.1:3000
```

### Production (single host)

```bash
# Bind publicly, let the runtime pick the best server (gunicorn/waitress/uvicorn)
EPL_WEB_HOST=0.0.0.0 EPL_WEB_PORT=8000 EPL_WEB_WORKERS=8 epl serve app.epl
```

### Docker / generated artifacts

```bash
epl deploy app.epl --output ./deploy     # generates Dockerfile, gunicorn_conf.py, compose, etc.
cd deploy && docker compose up --build
```

The generated container reads `PORT` / `EPL_PORT` and `WEB_CONCURRENCY` /
`EPL_WORKERS` at runtime. Override without rebuilding:

```bash
docker run -e PORT=8080 -e WEB_CONCURRENCY=8 my-epl-app
```

### Cloud Run / Heroku / Azure App Service

These platforms inject `PORT` automatically — no configuration needed. The app
binds to it on boot. For Azure App Service, `WEBSITES_PORT` is also honored by
the playground.

```bash
# Cloud Run: PORT is injected; just deploy. Bind is public inside the sandbox.
gcloud run deploy --source .
```

### Kubernetes

Set the port via env and probe the health endpoint:

```yaml
env:
  - name: EPL_WEB_HOST
    value: "0.0.0.0"
  - name: PORT
    value: "8080"
livenessProbe:
  httpGet:
    path: /_health
    port: 8080
readinessProbe:
  httpGet:
    path: /_health
    port: 8080
```

See `examples/k8s_deploy/` for a full manifest.

---

## Health checks

Every production HTTP server exposes a zero-work liveness endpoint suitable for
load balancers and orchestrators:

| Server | Path | Response |
|--------|------|----------|
| Web app | `GET /_health` | `{"status": "healthy", ...}` |
| Registry | `GET /health` | `{"status": "ok", "service": "epl-registry", ...}` |
| Playground | `GET /health` or `/_health` | `{"status": "ok", "service": "epl-playground"}` |
| MCP HTTP | `GET /health` | `{"status": "ok", ...}` |

With observability enabled (`epl serve --observability`), the web app also
exposes `/_ready` (readiness) and `/_metrics` (Prometheus).

---

## Security checklist

- [ ] Bind to `127.0.0.1` unless the server must be reachable externally; put a
      reverse proxy (nginx/Caddy) in front when it must.
- [ ] Terminate TLS at the proxy, or pass `--ssl-cert`/`--ssl-key` to the app.
- [ ] For the registry, set publish auth tokens before binding publicly.
- [ ] For the MCP server, pin `EPL_MCP_CORS_ORIGIN` to your exact frontend
      origin (never `*`).
- [ ] Run containers as the provided non-root `epl` user (the generated
      Dockerfile already does this).
- [ ] Wire the health endpoint into your liveness/readiness probes.
