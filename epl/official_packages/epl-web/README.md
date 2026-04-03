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
Call get_route(app, "/", Function()
    Return html_response("<h1>Hello from EPL Web</h1>", 200)
End)
Call start_app(app, 8080)
```

## Included Surface

- app lifecycle helpers
- route registration helpers
- request helpers
- response helpers
- session helpers
- test client helpers
