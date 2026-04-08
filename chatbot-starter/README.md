# chatbot-starter

Chatbot starter using EPL's web runtime plus the built-in AI bridge, with a graceful fallback when no model backend is configured.

## Template

- `chatbot`

## Getting Started

```bash
cd chatbot-starter
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
