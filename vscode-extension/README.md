<div align="center">

# EPL for Visual Studio Code

**Full IDE support for the English Programming Language**

[![Version](https://img.shields.io/badge/VS%20Code-Marketplace-007ACC?style=flat-square&logo=visual-studio-code&logoColor=white)](https://marketplace.visualstudio.com/publishers/epl-lang)
[![EPL](https://img.shields.io/badge/EPL-v9.1.0-3572A5?style=flat-square)](https://pypi.org/project/eplang/)

</div>

---

## Features

| Feature | Description |
|---------|-------------|
| 🎨 **Syntax Highlighting** | Full tokenization of EPL keywords, strings, numbers, and comments |
| 🔍 **Real-time Diagnostics** | Error detection powered by EPL's Language Server Protocol |
| 💡 **Code Completion** | 725+ stdlib function signatures with documentation |
| 📖 **Hover Documentation** | Function signatures, parameter types, and descriptions on hover |
| ▶️ **Run from Editor** | Execute `.epl` files directly with `Ctrl+Shift+R` |
| ⚡ **Bytecode VM Backend** | Run with the bytecode VM (`epl vm`) — full interpreter parity since v9.1.0 |
| 🔧 **Type Checking** | Static type analysis via `epl check` |
| 📐 **Formatting** | Auto-format EPL source files |
| 🧪 **Linting** | Code quality analysis |
| 📊 **Profiling** | Performance profiling from the editor |
| 👀 **Watch Mode** | Re-run on save, with configurable per-run timeout |
| 🩺 **Doctor** | Environment health check (`epl doctor`) |

## Prerequisites

```bash
pip install eplang
```

The extension requires the `epl` CLI on your system `PATH`. If it's not found automatically, set `epl.lsp.path` in VS Code settings.

---

## Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `EPL: Run Current File` | `Ctrl+Shift+R` | Run the active `.epl` file in the terminal |
| `EPL: Run Current File with Bytecode VM` | — | Execute via the bytecode VM (`epl vm`) |
| `EPL: Type Check Current File` | `Ctrl+Shift+K` | Run EPL's static type checker |
| `EPL: Format Current File` | — | Format using the EPL formatter |
| `EPL: Build Current File` | — | Compile to native executable |
| `EPL: Lint Current File` | — | Lint for code quality issues |
| `EPL: Profile Current File` | — | Profile execution performance |
| `EPL: Watch Current File` | — | Re-run on save |
| `EPL: Serve Current File` | — | Start production web server |
| `EPL: Deploy Current File` | — | Generate deployment configs (k8s/aws/gcp/azure/docker) |
| `EPL: Fix Errors with AI` | — | Use the AI explainer to suggest fixes |
| `EPL: Run Doctor` | — | Environment health check |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `epl.lsp.enabled` | `true` | Enable the Language Server for diagnostics and completions |
| `epl.lsp.path` | `"epl"` | Path to the `epl` CLI binary |
| `epl.strictMode` | `false` | Enable strict type checking mode |
| `epl.serve.port` | `8000` | Default port for `epl serve` |
| `epl.serve.observability` | `false` | Auto-attach `/_health`, `/_ready`, `/_metrics` endpoints |
| `epl.watch.timeout` | `""` | Per-run timeout for `epl watch` (seconds, or `none`). Empty = use CLI default (uncapped since v9.0.0). |

---

## Architecture

```
VS Code Extension (TypeScript)
        │
        ▼
  LSP Client (vscode-languageclient)
        │
        ▼ stdin/stdout
  EPL Language Server (Python)
  └── epl/lsp_server.py
      ├── Diagnostics (real-time error detection)
      ├── Completions (keyword + stdlib suggestions)
      ├── Hover (function signatures + docs)
      └── Formatting (epl/formatter.py)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `epl` command not found | Install EPL: `pip install eplang`, then restart VS Code |
| LSP not starting | Check `epl.lsp.path` setting; verify `epl lsp` runs in terminal |
| No syntax highlighting | Ensure file extension is `.epl` |
| Diagnostics not updating | Restart the Language Server: `Ctrl+Shift+P` → "Developer: Restart Extension Host" |

---

## Building from Source

```bash
cd vscode-extension
npm install
npx @vscode/vsce package
```

This creates a `.vsix` file you can install via `Extensions: Install from VSIX...` in VS Code.

---

<div align="center">

**[Report an Issue](https://github.com/abneeshsingh21/EPL/issues)** · **[EPL Documentation](https://abneeshsingh21.github.io/EPL/)**

</div>
