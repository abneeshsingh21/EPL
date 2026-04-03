# Reference Backend API

Production-facing EPL reference backend API.

## Run

```bash
epl install
epl serve src/main.epl --port 8000
```

## Endpoints

- `GET /api/health`
- `GET /api/todos`
- `POST /api/todos`

## Validation

This project is exercised in CI by `tests/test_reference_apps.py` using EPL's `web_test_client`.
