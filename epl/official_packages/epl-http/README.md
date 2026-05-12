# epl-http

HTTP client for EPL — make API calls, fetch data, send webhooks in plain English.

## Installation

```
epl install epl-http
```

## Quick Start

```epl
Import "epl-http"

Set response to http_get("https://api.example.com/users")
If response_is_ok(response) then
    Set users to response_json(response)
    Say "Found " + length(users) + " users"
End
```

## Features

- **GET, POST, PUT, PATCH, DELETE** — All HTTP methods
- **Headers & Auth** — Bearer tokens, Basic auth, custom headers
- **JSON** — Auto-parse responses, build request bodies
- **File transfers** — Upload and download files
- **Webhooks** — Send event notifications
- **URL builder** — Construct URLs with query parameters
- **Polling** — Poll endpoints at intervals

## API Reference

| Function | Description |
|----------|-------------|
| `http_get(url)` | GET request |
| `http_post(url, data)` | POST with JSON body |
| `http_put(url, data)` | PUT request |
| `http_patch(url, data)` | PATCH request |
| `http_delete(url)` | DELETE request |
| `http_with_bearer_token(url, token)` | Authenticated GET |
| `http_with_basic_auth(url, user, pass)` | Basic auth GET |
| `response_json(response)` | Parse JSON response |
| `response_status(response)` | Get status code |
| `response_is_ok(response)` | Check if 2xx |
| `download_file(url, path)` | Download file |
| `upload_file(url, path, field)` | Upload file |
| `send_webhook(url, event, data)` | Send webhook |
| `build_url(base, path, params)` | Build URL |
