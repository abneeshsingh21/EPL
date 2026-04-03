# EPL VS Code Extension

Full language support for **EPL (Easy Programming Language)** in Visual Studio Code.

## Features

- **Syntax Highlighting** — Full TextMate grammar for all EPL keywords, builtins, strings, numbers, and operators
- **IntelliSense** — Code completions for built-in functions, keywords, and your own variables/functions
- **Error Diagnostics** — Real-time error checking as you type (via the EPL Language Server)
- **Hover Information** — Hover over any built-in function to see its signature and documentation
- **Go to Definition** — Jump to function/class definitions (Ctrl+Click or F12)
- **Document Symbols** — See all functions, classes, and variables in Outline view (Ctrl+Shift+O)
- **Code Formatting** — Auto-format your EPL files (Shift+Alt+F)
- **Code Snippets** — 25+ snippets for common patterns (if, for, function, class, try, routes, etc.)
- **Run / Compile** — Run, compile (LLVM), transpile (JS/Kotlin), or generate Android projects directly from the editor

## Commands

| Command | Keybinding | Description |
|---------|-----------|-------------|
| EPL: Run Current File | `Ctrl+Shift+R` | Run the active .epl file |
| EPL: Compile Current File | — | Compile to native executable via LLVM |
| EPL: Transpile to JavaScript | — | Generate .js file |
| EPL: Transpile to Kotlin | — | Generate .kt file |
| EPL: Generate Android Project | — | Scaffold a full Android Studio project |
| EPL: Start Web Server | — | Start the EPL web server |
| EPL: Restart Language Server | — | Restart the LSP for fresh diagnostics |

## Installation

### From VSIX (recommended)
1. Run `vsce package` in this directory to create `epl-language-3.0.0.vsix`
2. In VS Code: Extensions → `...` menu → Install from VSIX
3. Select the `.vsix` file

### From Source
1. Copy this folder to `~/.vscode/extensions/epl-language`
2. Restart VS Code

## Requirements

- Python 3.8+ with EPL installed (for LSP features)
- GCC (for `compile` command)
- Android SDK (for `Generate Android Project` command)

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `epl.pythonPath` | `python` | Path to Python executable |
| `epl.lsp.enabled` | `true` | Enable Language Server |
| `epl.lsp.maxProblems` | `100` | Max diagnostics to show |
| `epl.trace.server` | `off` | LSP communication tracing |
