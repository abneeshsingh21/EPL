# epl-web

Supported EPL web facade package.

## Install

```bash
epl install epl-web
```

## Use

```epl
Import "epl-web"

Create app equal to create_app("demo")
Call get_route(app, "/", given req return html_response("<h1>Hello from EPL Web</h1>", 200))
Call get_route(app, "/api/health", given req return json_response(Map with status = "ok", 200))
Call start_app(app, 8080)
```

## Included Surface

- app lifecycle helpers
- route registration helpers
- request helpers
- response helpers
- session helpers
- test client helpers

## Notes

- `epl-web` is a supported helper facade.
- `epl serve` and `epl new --template web|api|auth|chatbot|frontend|fullstack` use EPL's native `Create WebApp` DSL as the authoritative served runtime.
