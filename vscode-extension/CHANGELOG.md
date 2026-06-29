# Changelog — EPL for Visual Studio Code

All notable changes to the EPL VS Code extension are documented here.
The extension version tracks the extension itself; language features are
provided by the `eplang` Language Server (the `epl` CLI on your PATH).

## [2.9.0] — 2026-06-30

Tracks `eplang` **10.1.0** (VM closures, native type inference, CI/supply-chain
hardening).

### Fixed

- **Unified bare constants are now highlighted.** EPL 10.1.0 made the bare
  word constants resolve identically across the interpreter, bytecode VM, and
  native build. The TextMate grammar's constant groups had drifted behind the
  language, so several were rendered as plain identifiers:
  - `on` / `off` are now colored as boolean constants alongside
    `true` / `false` / `yes` / `no`.
  - `none` is now colored as a null constant alongside `nothing` / `null`.
  - the mathematical constants `pi`, `euler`, and `infinity` are now
    highlighted (previously uncolored).

  Genuinely ambiguous English words (`the`, `a`, `of`, `at`, `than`, `type`,
  `file`, …) are still intentionally left uncolored — highlighting them as
  keywords would regress EPL's prose-like source.

### Notes

- The 10.1.0 engine work — real closures / capturing lambdas on the bytecode
  VM and whole-program type inference in the native build — introduces no new
  surface syntax, so no grammar change was required for those features. The
  LSP-driven completions, diagnostics, hover, rename, and find-references all
  track whichever `eplang` CLI is on your PATH automatically.

## [2.8.0] — 2026-06-23

Tracks `eplang` **9.8.0** (interpreter ↔ bytecode-VM backend parity).

### Fixed

- **String interpolation is now highlighted with the correct syntax.** The
  TextMate grammar matched the old `{expr}` form, but EPL interpolation is
  `$name` and `${expr}` (the syntax now implemented identically across the
  interpreter, bytecode VM, and LLVM compiler in 9.8.0). Both forms are now
  colored — `$name` as a variable, and `${ … }` with distinct delimiter and
  expression scopes — so a literal `$` that isn't a template (e.g. a password
  like `aB3$xK9!`) is left alone, matching the language's own rules.

### Added

- **Native web-DSL route keywords** — `shows`, `responds`, `called`, `does`,
  `render`, `apply`, and `action` are now highlighted, completing coverage of
  the native web DSL introduced in 9.7.0 (`Route "/" shows`,
  `Route "/api" responds with`, `Create WebApp called app`,
  `Button "…" does handler`).
- **String-interpolation snippets** — `printf` (`$name`) and `interp`
  (`${expr}`) scaffold interpolated strings.

### Changed

- Disambiguated a duplicate `test` snippet prefix (the test-function snippet is
  now `testfn`), so each snippet prefix is unique.

## [2.7.0] — 2026-06-16

Tracks `eplang` **9.7.0** (native web DSL, Phases 1–6).

### Added

- **Native web-DSL grammar tokens** — structural and `<head>` elements of the
  new native web DSL are now highlighted: `Stylesheet`, `Head`, `Div`,
  `Section`, `Nav`, `Header`, `Footer`, `Span`, `Article`, `Aside`, `Main`,
  `Container`, `Select`; head metadata `Description`, `Keywords`, `Author`,
  `ThemeColor`, `Canonical`, `Favicon`, `Font`, `OpenGraph`, `Twitter`, `Meta`;
  and event keywords `On`, `Toggle`, `Navigate`, `Scroll`, `Run`.

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
