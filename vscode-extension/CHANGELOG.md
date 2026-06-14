# Changelog — EPL for Visual Studio Code

All notable changes to the EPL VS Code extension are documented here.
The extension version tracks the extension itself; language features are
provided by the `eplang` Language Server (the `epl` CLI on your PATH).

## [2.5.0] — 2026-06-14

Surfaces the **Language Server Protocol v2** capabilities shipped in `eplang`
9.6.0. The extension negotiates these automatically from the server, but this
release wires up the editor-side configuration so they render correctly out of
the box.

### Added

- **Semantic highlighting** — declared `editor.semanticHighlighting.enabled`
  for `[epl]` via `configurationDefaults`, plus a `semanticTokenScopes` map for
  the server's 9 token types (`keyword`, `variable`, `function`, `class`,
  `type`, `number`, `string`, `comment`, `operator`) so every theme colors them
  consistently. Highlighting is lexer-driven: an English word like `Print` is
  colored as a keyword only where it actually is one — never inside a string or
  comment.
- **Token-aware rename** (`F2`) and **find-references** — now advertised as
  supported features. These match only real identifier tokens, so renaming
  `count` never rewrites the word inside a printed string.

### Changed

- Updated the marketplace description and feature list to reflect semantic
  highlighting and token-aware refactoring.
- Best experience with `eplang >= 9.6.0` (the extension still runs against older
  servers; the new features activate when the installed server provides them).

## [2.4.0]

- Run/Build/Check/Format/Lint/Profile/Watch/Serve/Deploy/Fix/Doctor commands.
- LSP client for diagnostics, completions, hover, and signature help.
- Bytecode VM run command.
- TextMate grammar, snippets, file icons, and `epl fix` integration.
