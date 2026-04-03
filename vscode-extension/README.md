# EPL — English Programming Language
# VS Code Extension

Provides full IDE support for the EPL programming language.

## Features

- **Syntax Highlighting** — EPL keywords, strings, numbers, comments
- **Diagnostics** — Real-time error detection via EPL's Language Server
- **Code Completion** — Keyword and function suggestions
- **Hover Documentation** — See function signatures and descriptions
- **Run from Editor** — `Ctrl+Shift+R` to run current file
- **Type Checking** — Run `epl check` from the command palette
- **Formatting** — Format EPL source files

## Prerequisites

Install EPL first:

```bash
pip install epl-lang
```

## Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `EPL: Run Current File` | `Ctrl+Shift+R` | Run the current `.epl` file |
| `EPL: Type Check Current File` | — | Run type checker on current file |
| `EPL: Format Current File` | — | Format using EPL formatter |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `epl.lsp.enabled` | `true` | Enable the Language Server |
| `epl.lsp.path` | `"epl"` | Path to the `epl` CLI binary |
| `epl.strictMode` | `false` | Enable strict type checking |

## Building

```bash
cd vscode-extension
npm install
npx @vscode/vsce package
```

This creates `epl-lang-1.0.0.vsix` which can be installed in VS Code.
