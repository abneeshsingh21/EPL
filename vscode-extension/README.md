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
| 💡 **Code Completion** | 90+ stdlib function signatures with documentation |
| 📖 **Hover Documentation** | Function signatures, parameter types, and descriptions on hover |
| ▶️ **Run from Editor** | Execute `.epl` files directly with `Ctrl+Shift+R` |
| 🔧 **Type Checking** | Static type analysis via `epl check` |
| 📐 **Formatting** | Auto-format EPL source files |
| 🧪 **Linting** | Code quality analysis |
| 📊 **Profiling** | Performance profiling from the editor |

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
| `EPL: Type Check Current File` | — | Run EPL's static type checker |
| `EPL: Format Current File` | — | Format using the EPL formatter |
| `EPL: Build Current File` | — | Compile to bytecode or native |
| `EPL: Lint Current File` | — | Lint for code quality issues |
| `EPL: Profile Current File` | — | Profile execution performance |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `epl.lsp.enabled` | `true` | Enable the Language Server for diagnostics and completions |
| `epl.lsp.path` | `"epl"` | Path to the `epl` CLI binary |
| `epl.strictMode` | `false` | Enable strict type checking mode |

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
