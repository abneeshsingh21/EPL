# Changelog — EPL for Visual Studio Code

All notable changes to the EPL VS Code extension are documented here.
The extension version tracks the extension itself; language features are
provided by the `eplang` Language Server (the `epl` CLI on your PATH).

## [2.6.0] — 2026-06-14

### Added

- **Embedded language highlighting inside strings.** EPL web apps embed large
  blocks of HTML/CSS/JS in triple-quoted strings (`""" … """`) and SQL in query
  strings — previously these rendered as one flat color. Now:
  - Triple-quoted strings are highlighted as **HTML**, which transitively colors
    embedded `<style>` (CSS) and `<script>` (JS) — so full HTML templates and
    `<style>`-wrapped CSS light up completely.
  - Double-quoted strings that begin with a SQL keyword (`SELECT`, `CREATE`,
    `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, …) are highlighted as **SQL**.
  - Uses VS Code's built-in `text.html.basic` and `source.sql` grammars — no
    extra dependencies.

### Fixed

- **The packaged extension was missing its `vscode-languageclient` runtime
  dependency** (the `.vsix` shipped only 13 files), so the Language Server —
  including diagnostics, completions, hover, and semantic tokens — silently
  failed to start once installed from the marketplace. The dependency is now
  bundled correctly (verified with `vsce ls`).

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
