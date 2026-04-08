# auth-starter

Auth/API starter using the native WebApp DSL, request context bindings, and the supported `epl-db` package.

## Template

- `auth`

## Getting Started

```bash
cd auth-starter
epl install
epl serve
epl test tests/
```

## Project Workflows

```bash
# Sync manifest-managed dependencies
epl install

# Add a Python package for `Use python`
epl pyinstall requests

# Add a GitHub EPL package dependency
epl gitinstall owner/repo alias

# Clone, pull, or push GitHub projects
epl github clone owner/repo
epl github pull
epl github push . -m "Update project"
```
