# Reference Fullstack Web

Production-facing EPL fullstack web sample with:

- server-rendered HTML
- login-style API endpoint
- SQLite-backed data
- JSON API endpoint

## Run

```bash
epl install
epl serve src/main.epl --port 8000 --store sqlite --session sqlite
```

## Routes

- `GET /`
- `GET /api/login`
- `GET /api/notes`

## Deployment

```bash
epl deploy all
```

CI validates the route flow through EPL's built-in web test client.

Additional CI contract:

- boots the app through `python -m epl serve` from the project directory
- verifies the real HTTP routes over a subprocess server
- verifies `python -m epl deploy all` generates production deployment artifacts
- verifies generated `deploy/wsgi.py` and `deploy/asgi.py` serve the real app routes
- verifies the generated Docker Compose deploy bundle can be built, booted, and served in CI
