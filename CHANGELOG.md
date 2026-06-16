<div align="center">

# Changelog

All notable changes to the **English Programming Language (EPL)** are documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/).

</div>

---

## [9.7.0] — 2026-06-16

**Native web DSL** — a six-phase effort to make EPL's web layer express
styling, structure, head/SEO, and interactivity as *first-class language
features* instead of raw CSS/JS/meta injected through the `Script` escape hatch.
The flagship site (`landing_page/src/main.epl`) is migrated onto the new
features as proof: it now authors structure, content, styling (page-scoped
`Stylesheet`), and head/SEO natively, leaving only genuinely imperative motion
JS (a canvas particle engine, scroll/tilt) in the sanctioned hatch. Every phase
stays mypy-clean and ruff-clean and ships regression tests; the native event
and CSP layers are additionally **verified in a real browser** (puppeteer),
including under a strict CSP with an enforced negative control.

### Added

- **Structure (Phase 1):** `List`/`Raw HTML`/`Script` and structural/layout tags
  now nest correctly inside `Div`/`Section`/etc. (a parser whitelist bug);
  inline `style "…"`; safe attributes (`aria-*`, `data-*`, `role`, `target`,
  `rel`, `title`, …); `Link`/`Button` accept `class`/`id`/`style`/attrs. Inline
  `on*` handlers are rejected at parse time.
- **Native CSS (Phase 2):** `Style` blocks gain nested rules — `On hover`/`On
  focus-visible` → `:pseudo-class`, `On before`/`after`/… → `::pseudo-element`,
  `On mobile|tablet|desktop` and `On screen below|above "Npx"` → `@media`,
  `Select "sel"` → descendant — plus a first-class `Stylesheet … End` raw-CSS
  block, all server-rendered into `<head>` with a `</style>`/`<script>` breakout
  guard.
- **Semantic head / SEO (Phase 3):** top-level `Head … End` block + per-`Page`
  overrides — `Description`, `Keywords`, `Author`, `ThemeColor`, `Canonical`,
  `Favicon` (auto `type`), `Font "…" weights "…"` (Google Fonts, preconnect
  once), generic `Link`, `OpenGraph`, `Twitter`, `Meta` — server-rendered so
  metadata is visible to crawlers/social scrapers without JS.
- **Native interactivity (Phase 4):** element-level `On click/hover/reveal`
  blocks and inline `on … toggles/adds/navigates/…` sugar compile to
  **generated, CSP-safe JS** (`addEventListener`/`IntersectionObserver`, never
  inline `on*`). Verbs: `Add`/`Remove`/`Toggle class [on "#sel"]`, `Navigate
  to`, `Scroll to`, and a `Run "fn"` bridge to `Script`-defined code.
- **Strict CSP (Phase 5):** opt-in via `epl serve --csp` (or
  `configure_page(csp=True)`) — a per-response nonce is added to every generated
  `<script>` and the `Content-Security-Policy` header becomes `script-src 'self'
  'nonce-…'`, so the generated JS runs under a strict policy with no
  `'unsafe-inline'` for scripts.
- **Page-scoped CSS (Phase 6):** a `Stylesheet`/`Style` block nested inside a
  `Page` renders only on that route (after site-wide CSS), enabling distinct
  per-route stylesheets without shipping every route's CSS on every page.

### Changed

- `landing_page/src/main.epl` — SEO/meta/favicon/fonts migrated from
  `createElement('meta'/'link')` injection to a native `Head` block + per-page
  directives; per-route CSS migrated from `createElement('style')` injection to
  page-scoped `Stylesheet` blocks. Server-rendered, isolated per route, browser-
  verified pixel-identical with KYC content intact.

### Fixed

- Production `epl serve` (`deploy.py` WSGI adapter) was rendering pages with **no
  custom styles/components/animations** — `Style`/`Stylesheet` CSS silently never
  reached served pages in production mode. Now threaded through.
- `web.py` route resolution (`_resolve_page_def`/`_resolve_page_element`) dropped
  newly-added `PageDef`/`HtmlElement` fields (head directives, events, page-scoped
  stylesheets) when cloning nodes for a request, so those features vanished on
  resolved routes. All clone sites now carry every field.

---

## [9.6.0] — 2026-06-13

Language Server Protocol **v2** plus a static-analysis bug-fix batch. EPL's
vision is that anyone can *read, write, and maintain* code in plain English;
this release strengthens the "maintain" leg with editor-grade semantic
highlighting and safe, token-aware refactoring, and hardens the runtime by
running the repo's own toolchain — **mypy** (configured but, until now, never
actually enforced), **ruff** (bugbear/pyflakes rule sets), and `compileall` —
across all ~89K LOC of `epl/` and fixing every verified finding. It also turns
the previously-ignored lint and type-check CI gates into real, ratcheting gates.
Each bug fix ships with a regression test that fails on the old code. Full suite:
**1,719 passed, 5 skipped, 0 failed**.

### Added

- `lsp_server.py` — **Semantic tokens** (`textDocument/semanticTokens/full`).
  The server now publishes a stable 9-type legend (`keyword`, `variable`,
  `function`, `class`, `type`, `number`, `string`, `comment`, `operator`) and
  emits LSP delta-encoded tokens for the whole document. Highlighting is driven
  by the **lexer**, not regex, so an English word like `Print` is colored as a
  keyword only where it is actually a keyword — never inside a string or
  comment. Comments (`# …` and `Note: …`) and string literals are recovered
  from a raw source scan because the lexer discards/unquotes them.
- VS Code extension consumes the legend automatically via
  `vscode-languageclient` 9.x — no client changes required.

### Changed

- `lsp_server.py` — **Find-references and rename are now token-aware.**
  `get_references()` and `get_rename_edits()` match only `IDENTIFIER` tokens, so
  occurrences inside string literals, comments, and keywords are no longer
  returned. This makes workspace-wide rename safe (renaming `count` no longer
  rewrites the word `count` inside a printed string). A word-boundary text scan
  is retained as a fallback for documents that fail to lex.
- LSP server version reported in `initialize` bumped to **2.1.0**.

### Fixed

- `stdlib.py` — **`thread_run` raised `NameError` on every call.** It did
  `return tid` with `tid` undefined; now returns the started `Thread` object so
  callers can `join()` it.
- `vm.py` — **`random` and `random_int` builtins crashed at runtime.** A local
  `def _random(...)` shadowed `import random as _random`, so `random` recursed
  into itself and `random_int` called `.randint` on a function object
  (`AttributeError`). The module import is now aliased `_random_mod`.
- `vm.py` — removed duplicate dict keys `is_none` (defined at two sites) and
  `sorted`; hardened `_sort` with an empty-args guard so the surviving `sort`/
  `sorted` entries behave identically.
- `type_system.py` / `type_checker.py` — **the type checker was silently inert on
  `If`, ternary, and `Match` nodes.** It referenced AST attributes that do not
  exist (`true_body`/`false_body` → `then_body`/`else_body`; `clauses` →
  `when_clauses`; `true_value`/`false_value` → `true_expr`/`false_expr`;
  `node.object` → `node.obj`), raising `AttributeError` that the diagnostics path
  swallowed via a broad `except`. The checker now actually walks these nodes;
  ternary type inference works (e.g. `1 if c otherwise 2` → `integer`). Match
  `default_body` is now type-checked too.
- `parser.py` — parameter-ordering error called non-existent `self._error(...)`
  (`AttributeError`); now raises `ParserError` with a line number like every
  other parser error.
- `interpreter.py` — `EPLClass` now initializes `static_methods` and
  `type_params` in `__init__` so every construction path exposes them (no more
  `AttributeError` on lookup before the class-def executor runs).
- `doc_linter.py` — fixed a loop-variable closure-capture bug (B023): the
  synthesized match object now binds `fname`/`norm_params` by value.
- `official_packages/epl-http` — removed a dead, buggy `get()` that made **two**
  HTTP requests and returned a malformed response, shadowed by the correct one.
- `official_packages/epl-science` — `hasattr(x, "__call__")` → `callable(x)`.
- `ios_gen.py`, `publisher.py` — removed two useless `if/else` branches whose
  arms were identical (RUF034).
- `interpreter.py` — removed a dead `results` accumulator in parallel for-each.
- `packager.py` — native packaging called `compiler.emit_object(path)` which does
  not exist (`AttributeError`); now writes the bytes returned by
  `compile_to_object()` to the `.o` file.
- `type_checker.py` / `type_system.py` — **the type checker crashed on every
  variadic function.** `node.params` can contain a `RestParameter` node, but the
  checker did `p[0]`/`len(p)` on it (`TypeError`, swallowed) in three passes
  (declaration collection, class-method scan, body check). A `_param_name_type()`
  helper now centralizes the guard; `type_system` no longer mis-registers a rest
  param under its `repr`.
- Made return/parameter annotations honest across `lexer.py`, `parser.py`,
  `errors.py`, `environment.py`, `type_checker.py`, `type_system.py` (`Optional`
  where `None` is actually returned) — clears the way for the strict type gate.

### Hardening & CI

- **The lint and type-check CI gates were theater — now they're real.** `mypy epl/`
  exited 1 (191 errors) and `ruff format --check` flagged 48 files, so both gates
  had been effectively red-and-ignored.
- `ruff` (pyproject) — un-ignored **B004, B023, F601, F811** and enforce **RUF034**.
  Each caught a real bug in this release and is now held at **zero violations**, so
  the bug class cannot silently regrow. Configured `ruff check` is fully green.
- `ci.yml` + `pyproject.toml` — **whole-tree `mypy epl/` is now BLOCKING with an
  empty debt ledger.** Type errors were driven from **191 → 0**: *all 75 modules*
  under `epl/` (excluding `official_packages`) type-check clean, with full
  import-following. The work was done as a ratchet — a `[[tool.mypy.overrides]]`
  exemption list that only ever shrank — and that list is now empty, so there are
  no per-module exemptions left. A new type error fails CI.
- Cleaning the tree to zero surfaced honest fixes and several **real latent bugs**:
  the REPL `.vars`/`.type` commands referenced a non-existent Environment API
  (`.env`/`.values`/`.set` vs the real `.global_env`/`.variables`/`define_variable`)
  and would have crashed in production; `_exec_use`/`_exec_use_js` could bind a
  variable literally named `None`; `parallel_each` re-raised a possibly-`None`
  `future.exception()`; networking socket ops on a closed connection raised raw
  `AttributeError` instead of a clear `ConnectionError` (new `_require_socket()`
  guard); `send()` returned `sendall() or len(data)` though `sendall` returns
  `None`. Plus container annotations, honest `Optional`/union signatures, and two
  file-handle/loop-variable shadows in `packager`.
- **34 broad silent `except` swallows** instrumented with
  `_debug_log.suppressed(site)` — failures are now observable under `EPL_DEBUG`
  with zero behavior change by default.
- **Exception chaining (B904) enforced tree-wide** and removed from the ignore
  list. All 116 re-raise sites now chain explicitly: `from e` where the cause is
  bound and useful (42 + infra sites), `from None` for the 51 EPL-domain
  translations in `interpreter`/`stdlib` (so Python internals like `int()`'s
  `ValueError` don't leak into plain-English EPL errors).
- Applied `ruff format` repo-wide (canonical single-quote style); 48 files brought
  into conformance so the format gate passes.

### Tests

- New `tests/test_lsp_semantic_tokens.py` (12 cases): legend stability, capability
  advertisement, delta-encoding validity, per-kind classification, the
  keyword-inside-string guarantee, token-aware references/rename, and graceful
  degradation on unlexable source.
- New `tests/test_static_analysis_fixes.py` (13 cases), including anti-regression
  guards that assert the type checker **actually visits** If/ternary/Match bodies
  and survives variadic params — so a future swallowed-exception regression can't
  hide — plus a guard that `_debug_log.suppressed()` stays silent unless `EPL_DEBUG`
  is set.
- De-brittled `tests/test_phase4_security.py::test_mcp_cors_default` to be
  quote-style-agnostic (the formatter's single-quote canonicalization must not mask
  the real check: CORS default is `null`, never `*`).
- Updated `tests/test_phase5_tooling.py` to assert the corrected token-aware
  reference semantics and the new server version.

Full suite: **1,719 passed, 5 skipped, 0 failed.**

---

## [9.5.0] — 2026-06-13

Post-release stabilization of the v9.4.0 line. A community bug report (12 issues,
46 failing tests on a fresh checkout) was triaged, fixed end-to-end, and locked in
with a dedicated verification suite. The full test suite now reports **1,693 passed,
5 skipped, 0 failed**.

### Security

- `web.py` — **BUG-01 / BUG-02: web servers no longer bind to `0.0.0.0` by default.**
  `start_server()` and `AsyncEPLServer` now accept a `host` parameter that defaults to
  `127.0.0.1` (localhost only) and print an explicit warning when a caller opts into
  `0.0.0.0`. Previously every `epl serve` web app was reachable from the entire network
  regardless of the documented `--host` default. The dedicated deployment entry point
  `start_production_server()` continues to default to `0.0.0.0` by design.
- `web.py` — **BUG-06: open-redirect hardening.** `_validate_redirect()` is now applied
  to *every* `REDIRECT:` URL construction path (`_execute_action` and `_build_page_sync`),
  closing a bypass where unvalidated redirect targets could reach the response.
- `web.py` — **BUG-12: ETag generation moved from MD5 to SHA-256** (truncated to 32 chars),
  bringing it in line with the v9.4.0 hardening that deprecated MD5 elsewhere in the stack.

### Fixed

- `main.py` — **BUG-04: restored the root `main.py` CLI re-exporter.** It re-exports
  `compile_file`, `CROSS_TARGETS`, and the other CLI symbols, fixing 15+ import-time test
  failures across `test_phase1_native.py`, `test_phase6.py`, `test_tier4.py`, and `test_phase7.py`.
- `stdlib.py` — **BUG-05: web route argument validation now runs *before* Flask instantiation**,
  so invalid route definitions raise a clear error instead of failing deep inside Flask.
- `web.py` — **BUG-07: fixed a race condition on the active-connection counter** in
  `AsyncEPLServer` by guarding `_active_connections` with an `asyncio.Lock`.
- `web.py` — **BUG-09 / BUG-10: removed deprecated `datetime.utcnow()` /
  `datetime.utcfromtimestamp()`** in favor of timezone-aware `datetime.now(timezone.utc)` /
  `datetime.fromtimestamp(ts, timezone.utc)`. Prevents breakage on Python 3.15 where the
  legacy APIs are removed.
- `web.py` — **BUG-11: instrumented 6 remaining silent `except` blocks** with
  `_debug_suppressed()` so swallowed exceptions are observable under debug logging.
- `test_phase1_native.py` — **BUG-03: forced `encoding='utf-8'`** on `runtime.c` reads,
  fixing `cp1252` decode crashes on Windows.
- `test_webapp.py` — **BUG-08: raised the test server startup timeout** (15s → 30s, poll
  0.1s → 0.3s) to remove a flaky timeout on slower machines.
- Resolved backwards-compatibility regressions introduced while fixing the above, restoring
  the v9.4.0 public API surface.

### Tests

- Added `tests/test_bug_fixes.py` — a **51-test verification suite** covering BUG-01 through
  BUG-12 with independent assertions plus cross-cutting integration checks.
- Full suite green on a clean checkout: **1,693 passed, 5 skipped, 0 failed** (previously
  1,594 passed / 46 failed / 7 skipped in the community report).

---

## [9.4.0] — 2026-06-05

Multi-phase enterprise-grade remediation against the v9.3.0 audit findings.
All 6 phases ship in this release.

### Phase 6 — Error Explainer v2.0 (Enterprise-Grade Diagnostics)

**Fixed**
- `error_explainer.py` — No longer calls cloud AI API by default. The `_offer_ai_explanation` and `epl fix` functions previously passed `ai=True` unconditionally, causing "Groq API error (401): Invalid API Key" for every user without a configured key. Now runs 100% offline with zero API calls. AI analysis is opt-in via `--ai-errors` flag.
- `error_explainer.py` — `_get_ai_explanation` now filters raw API error strings (401, 403, "Invalid API Key") so they never leak to the terminal even if AI is enabled.

**Enhanced**
- `error_explainer.py` — Upgraded from v1.0 (27 patterns) to v2.0 with 55+ offline patterns covering: type assignment mismatches, overflow, file I/O, method not found, missing `Then`/`Takes`, iterator exhaustion, read-only properties, map key types, `=` vs `==` in conditions, missing quotes, curly braces, semicolons, C++/Java/Ruby output syntax, parentheses in conditions, unterminated strings, unexpected EOF, and more.
- `error_explainer.py` — **Context window**: shows 2 lines above and below the error with line numbers and Rust-style `>` pointer arrows highlighting the exact error line.
- `error_explainer.py` — **"Did you mean?"** fuzzy matching now covers EPL keywords (not just variables/functions). Catches typos like `Funtion` → `Function`, `Whille` → `While`.
- `error_explainer.py` — **Error code documentation links**: each explanation now includes a `https://epl-lang.org/errors/EXXXX` link in the footer.
- `error_explainer.py` — **Category badges**: output header shows `[E0400] [TYPE]` or `[E0500] [NAME]` for quick identification.
- `cli.py` — **Auto-fix**: `epl fix <file.epl> --fix` automatically writes the corrected code back to the file, preserving indentation. Shows old/new diff in the terminal.
- `vscode-extension/package.json` — Renamed "EPL: Fix Errors with AI" to "EPL: Fix Errors" with `$(zap)` icon. No misleading AI branding for an offline tool.


### Phase 5 — CI/CD hardening + dependency fixes

**Fixed**
- `pyproject.toml` — Added `[project.dependencies]` with `flask>=3.0,<4.0` and `requests>=2.31,<3.0`. Both were previously undeclared: `flask` is imported unconditionally in `mcp_http_server.py`; `requests` is a hard requirement of the bundled `epl-http` package. Consumers who `pip install eplang` now receive both transitively without needing extras.
- `pyproject.toml` — Added upper-bound version caps to all optional dependencies. Open-ended `>=X.Y` specifiers previously risked silent breakage if a major-version bump introduced breaking changes. All entries in `llvm`, `ai`, `secure`, `server`, `redis`, `repl`, `cloud`, `all` extras now carry `<NEXT_MAJOR` caps.
- `pyproject.toml` — Added `mypy>=1.8,<2.0` to the `[dev]` optional extra, so `pip install eplang[dev]` installs the type checker alongside pytest/ruff/coverage.
- `.github/workflows/ci.yml` — Test matrix widened from `['3.11', '3.12']` to `['3.9', '3.10', '3.11', '3.12']`, matching the `requires-python = ">=3.9"` claim. macOS excludes 3.9/3.10 to keep runner costs reasonable.
- `.github/workflows/ci.yml` — Added `typecheck` job: installs `.[dev]` and runs `mypy epl/ --ignore-missing-imports --exclude epl/official_packages`. mypy was configured in `pyproject.toml` but had no CI step to enforce it.
- `.github/workflows/ci.yml` — Added `test_phase3_reliability.py`, `test_phase4_security.py`, and `test_security_hardening.py` to the stable test suite whitelist and the coverage step. These files existed but were omitted from the explicit pytest invocation, meaning security and reliability tests never ran in CI.

**Tests**
- 52 new tests in `tests/test_phase5_cicd.py` — static analysis of `pyproject.toml` and `ci.yml` covering: runtime dep declaration, lower/upper bounds on all extras, mypy in dev extra, Python 3.9/3.10/3.11/3.12 matrix, typecheck job wiring, and security test file inclusion.

### Phase 4 — Official package security

**Security**
- `epl-crypto` — Removed insecure XOR-based fallback from `aes_encrypt` / `aes_decrypt`. When the `cryptography` package is absent, both functions now raise a clear `ImportError` with an install hint instead of silently falling back to a trivially-broken XOR cipher. Added `_require_cryptography(fn_name)` helper used by both functions.
- `epl-validator` — `sanitize_sql()` previously escaped only `'` and `"`. Extended to a full 12-character-class sanitizer: `\`, `'`, `"`, `` ` ``, `;`, `--`, `#`, `%`, `_`, NUL, `\n`, `\r`. Backslash is processed first to prevent double-escaping. Includes `WARNING` docstring reminding callers to prefer parameterised queries.
- `epl-validator` — `matches_pattern()` and `validate()` schema pattern fields previously used bare `re.match()`, allowing a crafted pattern to hang the process via catastrophic backtracking (ReDoS). Both now route through `_safe_match()`, which executes the match in a daemon thread and raises `ValueError` if it does not complete within 1 second.
- `epl-auth` — `md5()` now emits a `DeprecationWarning` on every call, steering users toward `sha256()` or `hash_password()`. The digest return value is unchanged for checksum / legacy compatibility.
- `epl-auth` — Session dict (`_sessions`) previously grew without bound. Added a background daemon thread (`_evict_expired`) that sweeps expired sessions every 5 minutes. All session and rate-limit dict mutations are now protected by `_sessions_lock` / `_rate_limits_lock` (thread-safety gap closed). `check_rate_limit` uses a local `bucket` copy to avoid holding the lock during list comprehension iteration.
- `mcp_http_server.py` — `CORS_ORIGIN` default changed from `"*"` (allows any origin) to `"null"` (blocks all cross-origin browser requests). Operators set `EPL_MCP_CORS_ORIGIN=https://their-app.example.com` to allow a specific origin. Module docstring updated with guidance and a NEVER-use-`*`-for-authenticated-endpoints warning.

**Tests**
- 75 new tests in `tests/test_phase4_security.py` covering: XOR removal (simulate absent lib, verify `ImportError`), AES round-trip + fresh-nonce, SQL escaping for all 12 character classes + backslash-first ordering, ReDoS timeout, `_safe_match` invalid-regex handling, schema pattern integration, MD5 `DeprecationWarning` presence + content, session eviction on `validate_session` and via background timer, 50-thread concurrent session creation, 20-thread rate-limit fairness (exactly 10 allowed / 10 blocked), JWT round-trip + bad-secret + expiry, CORS default string + env-override.

### Phase 1 — Critical language pipeline fixes

**Fixed**
- `vm.py` — Float zero (`0.0`) is now caught by the division guard alongside integer zero; previously `10.0 / 0.0` silently produced `inf` instead of a runtime error.
- `vm.py` — List index-set (`obj[i] = val`) now raises a clean `VMError` on out-of-range indices instead of propagating a raw Python `IndexError`.
- `lexer.py` — Triple-quote boundary check corrected (off-by-one that could read one byte past the source buffer on a 2-char source ending in `"`).
- `lexer.py` — Hex (`\xNN`) and Unicode (`\uXXXX`) escape sequences now guard against reading past end-of-source before slicing, raising a clean `LexerError` instead of silently accepting a truncated escape.
- `parser.py` — Rest-parameter error path now raises `ParserError(msg, line)` directly instead of calling the non-existent `self._error()` method, which previously caused an `AttributeError` crash on malformed rest parameters.
- `python_transpiler.py` — Range loops (`for x from A to B`) were emitting one extra iteration when no step was specified. The `end + 1` expression is now correctly parenthesised for both step and no-step paths.
- `type_checker.py` — `_check_call` now reads `node.arguments` (the correct AST attribute) instead of `node.args`, so type inference for function calls no longer silently receives an empty argument list.
- `type_system.py` — `TypeScope.resolve_type_name` accepts a `_seen` guard set and breaks circular alias chains (`type A = B; type B = A`) by returning `EPLType(PRIMITIVE, 'any')` instead of recursing infinitely.

### Phase 2 — Security

**Security**
- `web.py` — Open redirect at 7 locations: all redirect targets now pass through `_validate_redirect()`, which allows only relative paths and rejects absolute URLs and protocol-relative `//host` forms. Attackers can no longer craft `?next=https://evil.com` payloads that redirect users off-site after login/logout.
- `web.py` — Static file path traversal: changed from `os.path.normpath` + bare `startswith` to `os.path.realpath` + `startswith(root + os.sep)`, so symlinks pointing outside the static root are also blocked.
- `web.py` — CSP header tightened: removed `script-src 'unsafe-inline'`; added `object-src 'none'` and `base-uri 'self'` to close dangling-markup and base-tag injection vectors.
- `html_gen.py` — Button `onclick` regex replaced: `[^)]*` (accepted arbitrary JS) with an explicit allowlist `[a-zA-Z0-9_,\s\'\".\-]*` that only allows safe argument characters.
- `html_gen.py` — `$items{collection}` store template now HTML-escapes every item value via `html.escape()` before rendering, closing the stored-XSS vector where attacker-controlled collection values were injected verbatim.

### Phase 3 — Concurrency, resource leaks, and atomicity

**Fixed**
- `bytecode_cache.py` — `save()` now writes to a `.eplc.tmp` sibling and renames it into place atomically. A crash or OOM mid-write previously left a truncated `.eplc` that caused a silent full re-parse on every subsequent run. The temp file is cleaned up on any exception before re-raising.
- `async_io.py` — `EPLInterval.stop()` now cancels the underlying asyncio `Future` immediately via `task.cancel()` in addition to setting `_running = False`. Previously, a sleeping interval task would not wake until the current sleep elapsed, leaving a thread alive for up to `interval` seconds after `stop()`.
- `concurrency.py` — `EPLRWLock` rewritten to eliminate a deadlock window. The previous implementation exited the `Condition` context (releasing `_lock`) and then immediately called `self._lock.acquire()` bare — another thread could win that acquire in the gap, breaking write exclusion. The new design uses three separate primitives: `_write_lock` (serialises writers and gates new readers), `_drain_event` (signals when active reader count hits zero), and `_state_lock` (guards the reader/writer counters).
- `hot_reload.py` — `_restart_pending` plain `bool` replaced with `threading.Event` (`_restart_event`). A plain bool has no memory-barrier guarantee outside CPython's GIL and is not safe to set from one thread and read from another in general. `Event.set()` / `Event.wait()` / `Event.is_set()` are explicitly thread-safe.
- `hot_reload.py` — New `_kill_process(proc, timeout)` helper escalates SIGTERM → SIGKILL after `timeout` seconds. The previous `proc.terminate(); proc.wait(timeout=5)` could hang indefinitely if the child ignored SIGTERM. All termination paths (`run_with_reload`, `stop`, `KeyboardInterrupt`) now use this helper.

**Tests**
- 30 new tests in `tests/test_phase3_reliability.py` covering: atomic write crash safety (mid-write OSError simulation), interval stop cancellation and idempotency, RWLock concurrent readers (peak count), writer exclusion, no-deadlock under mixed contention, `_kill_process` SIGTERM→SIGKILL escalation, and `HotReloader` event thread-visibility.

---

## [9.3.0] — 2026-06-01

Multi-phase enterprise-grade enhancement program. All phases bundled into a single release. Sections below correspond to phases completed before publish.

### Phase 2 — Exception hygiene

**Added**
- `epl/_debug_log.py` — `suppressed(where)` helper. Records swallowed exceptions to stderr when `EPL_DEBUG=1` is set, silent otherwise. Set `EPL_DEBUG_TRACE=1` for full tracebacks. Zero dependencies on the rest of the package — safe to import from any module.

**Changed**
- 34 previously-silent `except Exception: pass` / `return None` blocks now instrumented across `epl/stdlib.py` (15), `epl/web.py` (10), `epl/runtime_support.py` (4), `epl/cli.py` (3), `epl/interpreter.py` (2). Production behaviour is unchanged (still swallows by default); diagnostic visibility is one env var away.

**Tests**
- 12 new tests in `tests/test_debug_log.py` covering env-var parsing, truthy/falsy values, silent-by-default behaviour, and the "called outside an except block" safety case.

### Phase 3 — Raw HTML escape hatch

**Added**
- `Raw HTML "<...>"` keyword for emitting arbitrary HTML inside `Page` blocks. Unblocks every tag the EPL parser does not natively support (`<table>`, `<video>`, `<audio>`, `<details>`, `<select>`, `<textarea>`, `<dialog>`, etc.) without forcing a parser change for each new element. The author is responsible for safety; never pass user input here without sanitisation.
- `examples/raw_html_demo.epl` showcasing the new keyword.

**Tests**
- 7 new tests in `tests/test_raw_html.py` covering verbatim emission, attribute preservation, coexistence with built-in elements, and the regression case (`html`/`raw` still usable as identifiers).

### Phase 4 — Theme system (light / dark / auto)

**Added**
- `configure_page(theme=...)` accepts `'light'`, `'dark'`, or `'auto'` (default). The previous behaviour hardcoded `<meta name="color-scheme" content="dark">` + a Darkreader lock on every page, ignoring user OS preference and breaking light-mode embeds.
- Built-in CSS variable palette injected into the rendered `<head>`: `--bg`, `--fg`, `--muted`, `--accent`, `--surface`, `--border`, `--danger`. Apps that reference these tokens (the parser/StyledElement layer already does) get a coherent palette per theme for free.
- `'auto'` emits both palettes and switches via `@media (prefers-color-scheme: dark)` so the OS picks.

**Changed**
- Page `<head>` no longer hardcodes dark mode. Default is `'auto'` — apps that want the v9.2.0 always-dark behaviour call `configure_page(theme='dark')`.

**Tests**
- 7 new tests in `tests/test_theme.py` covering each theme value, palette completeness, the media-query branch in `auto`, invalid values, and reset semantics.

### Phase 5 — SQL injection hardening

**Security fix.** `real_db_update` and `real_db_delete` previously interpolated dict-WHERE column names directly into SQL without validation, and accepted bare string WHERE clauses with no params. A caller passing `{"id = 1 OR 1=1 --": x}` as a WHERE map could rewrite or delete every row in a table. Both vectors are now closed.

**Added**
- Module-level `_SQL_IDENT_RE` and `_assert_sql_identifier(name, kind)` helper in `epl/stdlib.py` — a single source of truth replacing seven copy-pasted in-function regex compilations. New SQL-emitting endpoints now have one obvious thing to call.

**Changed (breaking only for previously-exploitable code paths)**
- `real_db_update(db, table, set_map, where_map)` — every key in `where_map` is now validated as a SQL identifier before interpolation.
- `real_db_delete(db, table, where_map)` — same validation applied.
- `real_db_update` / `real_db_delete` with a **string** WHERE clause now require an explicit `params` tuple. The string-only form (which executed user input verbatim) raises with a fix hint.

**Tests**
- 24 new tests in `tests/test_sql_injection.py`:
  - 17 unit tests for `_assert_sql_identifier` covering valid identifiers, nine injection patterns (statement breakage, predicate injection, quote breaks, etc.), non-string inputs, and `kind` reporting.
  - 7 integration tests through the public `call_stdlib('real_db_update'|'real_db_delete', ...)` dispatcher proving each historical exploit attempt now raises **and that no rows were mutated**, plus regression tests that the legitimate dict-WHERE and parameterised string-WHERE paths still work.

### Phase 6 — Command injection hardening (pip/npm flag-injection)

**Security fix.** Although `shell=True` was already eliminated in 9.2.0, the package-manager and interpreter still passed manifest/lockfile values into `pip install` and `npm install` as positional argv. `pip` and `npm` both parse flags from positional arguments — so a malicious manifest entry like `evil = "--extra-index-url https://evil.com/pypi"` or `version = "* --before-script=evil.sh"` would, before this release, silently install from an attacker-controlled source or run an attacker-chosen script. All four call sites are now closed.

**Added**
- `_normalize_python_requirement` (existing helper) now refuses any requirement that **starts with `-` or contains a whitespace-separated flag token**, and refuses `pkg @ url`-style URL/path install specs. Power users wanting URL installs call pip directly.
- New `_validate_npm_version_spec(version)` in `epl/package_manager.py` — same flag-injection check for npm version specs read from `[js-dependencies]`.
- **Defense in depth:** every `pip install`/`npm install` invocation now uses the `--` end-of-options separator so that even if validation were bypassed, the package manager would treat the requirement as positional rather than a flag.

**Changed (breaking only for previously-exploitable code paths)**
- `install_python_package`, `install_python_dependencies`, the lockfile install loop, **and the auto-install path in `epl/interpreter.py`** all now route through `_normalize_python_requirement` and emit `pip install --  <req>`.
- `install_js_package` and `install_js_dependencies` now validate both the package name (already protected) and the version spec, and emit `npm install --  <target>`.

**Tests**
- 26 new tests in `tests/test_command_injection.py`:
  - 12 unit tests for `_normalize_python_requirement` covering clean specifiers, six flag-injection payloads, and three URL/path-spec payloads.
  - 12 unit tests for `_validate_npm_version_spec` covering valid semvers, five flag-injection payloads, and the non-string case.
  - 2 end-to-end tests proving that a poisoned `epl.toml` is refused at the boundary and **the `subprocess` is never invoked**.
- 3 existing tests updated to assert the new `--`-separated argv shape.

### Phase 7 — `epl watch` no longer kills long-running programs

**Bug fix.** The dev-mode watcher hard-capped every re-run at **60 seconds**, killing servers, bots, REPLs and any genuinely long-running EPL program the moment they crossed the minute mark. The cap is now removed by default and the watcher exposes a `--timeout=` flag for the rare case where a hard cap is wanted.

**Changed**
- `epl.watcher._execute(...)` `timeout` parameter now defaults to **`None`** (no cap). The previous 60-second default is gone.
- `epl watch` accepts a new `--timeout=SECS` flag. Accepted values: a positive number (seconds), or one of `none`/`off`/`0`/`disable` to explicitly disable the cap.
- Help text for `epl watch` now documents the flag.

**Tests**
- 8 new tests in `tests/test_watcher.py`:
  - 3 `TestWatcherTimeout` cases verifying `_execute` forwards `timeout` to `subprocess.run` verbatim, defaults to `None`, and handles `TimeoutExpired` cleanly without raising.
  - 5 `TestWatcherCliTimeoutParsing` cases verifying CLI flag parsing — integer, decimal, the four disable-sentinels, default (no flag), and the invalid-value error path.

---

## [9.2.0] — 2026-06-01

Phase 1 of the enterprise-grade enhancement program: privacy & secrets hygiene. No breaking changes — every behaviour shift is the safer default, with the old behaviour available behind an opt-in.

### Added
- **OS keyring storage for cloud AI API keys.** Keys configured via `configure_cloud(...)` now go into the OS keychain (Windows Credential Manager, macOS Keychain, Secret Service / KWallet on Linux) under service `epl-lang`, user `cloud_api_key`. The on-disk `ai_config.json` no longer contains plaintext secrets when a keyring backend is available. Requires the optional `keyring` package — install via `pip install eplang[secure]` or it ships with `eplang[all]`.
- **Automatic migration of legacy plaintext API keys.** Pre-9.2.0 configs with `api_key` in `ai_config.json` are moved into the keyring on first read, and the field is scrubbed from the JSON file. No user action required.
- **`html_gen.configure_page(footer=..., fonts=...)`.** Page-level rendering controls for the web framework.
- **System-font default for web pages.** New pages render with the platform's native font stack — no third-party CDN fetch, faster first paint, works offline. The legacy Inter-from-Google-Fonts behaviour is one setting away: `configure_page(fonts='cdn')`.

### Changed
- **Hardcoded `Powered by EPL v1.0` footer is gone.** Pages now omit `<footer>` entirely by default. Apps wanting branding set it explicitly: `configure_page(footer='© 2026 ACME Corp')`. Footer text is HTML-escaped to prevent XSS via injected content.
- **JSON-fallback path retained.** When no keyring backend is available (e.g. headless Linux CI without `libsecret`), `configure_cloud` falls back to writing the key into `ai_config.json` with `chmod 0600` — same as pre-9.2.0. Behaviour is logged in the saved file (no `api_key` field == keyring used).

### Security
- **Plaintext API keys no longer touch disk on systems with a working keyring backend.** Closes the gap flagged in the prior security audit where Gemini/Groq keys lived in cleartext JSON.
- **Footer XSS hardening.** User-provided footer text is HTML-entity-escaped (previously the hardcoded string had no escape path because there was no user input — the new control plane needs it).

### Tests
- 14 new tests across `tests/test_ai_keyring.py` and `tests/test_html_gen_config.py` covering: keyring present, keyring absent, legacy migration, keyring read failure, `clear_cloud` wipe, footer XSS, font opt-in, invalid font value rejection. Full suite remains green: 1518 passed, 5 skipped.

### Packaging
- `pyproject.toml` declares `keyring>=24.0.0` as the new `[secure]` optional dep and includes it in `[all]`.

### Migration notes
- **No code change required for existing users.** Re-run any command that reads cloud config (`epl ai status`, etc.) and the migration happens transparently.
- Apps that relied on the visible `Powered by EPL v1.0` footer must opt back in: `from epl import html_gen; html_gen.configure_page(footer='Powered by EPL v9.2')`.

---

## VS Code Extension [2.2.0] — 2026-06-01

Brings the VS Code extension up to v9.x parity with the language runtime. No breaking changes.

### Added
- **`EPL: Run Current File with Bytecode VM` command.** Executes the active file via `epl vm`, the bytecode VM that reached full interpreter parity in EPL v9.1.0. Surfaced alongside the existing `EPL: Run Current File` command in the command palette.
- **`epl.watch.timeout` setting.** Plumbs the v9.0.0 `--timeout=<seconds|none>` flag into the `EPL: Watch Current File` command. Empty (default) preserves the new uncapped-by-default behaviour; set a number for a per-run cap, or `none` to be explicit.

### Changed
- **README updated for v9.x.** Feature matrix now shows the correct stdlib function count (725+ — was 90+), advertises the bytecode VM backend, and documents the previously-hidden `epl.serve.port`, `epl.serve.observability`, and new `epl.watch.timeout` settings.
- **Stale internal version refs corrected.** Header comment dropped the hard-coded `v2.1.0` tag. PyPI update-checker code comment example bumped from `v7.6.0` → `v9.1.0` so future readers don't mistake it for a current claim.

### Migration notes
- No user action required. Existing keybindings, settings, and the LSP wire format are unchanged.

---

## [9.1.0] — 2026-06-01

VM parity release. The bytecode VM (`epl run --vm`) now matches the tree-walking interpreter on every documented divergence, and the source distribution ships the runtime assets the wheel already includes.

### Fixed
- **Recursive function calls now produce correct results in the VM.** The compiler pre-registers a function's own name before compiling its body, so a recursive call resolves to `Op.CALL` instead of falling through to `Op.CALL_BUILTIN`. `factorial(5)` now returns `120` (was `24`) and `fib(10)` returns `55` (was `6`).
- **`JUMP_IF_FALSE` / `JUMP_IF_TRUE` always pop their condition.** Previously the truthy branch left the value on the stack, corrupting subsequent operations. This single bug was the root cause behind four documented divergences: `continue` inside loops, FizzBuzz chained `Otherwise If`, list-comprehension-style mutation, and (via stack corruption inside recursive frames) Fibonacci/factorial.
- **`Try` / `Catch` now intercepts VM-level runtime errors.** `VMError` (e.g. division by zero, unknown class) routes through the active `try_stack` and lands the error message in the catch binding, matching interpreter semantics. Previously only Python-native exceptions were caught and any runtime error escaped the handler.
- **Class construction now works end-to-end.** `Op.NEW_INSTANCE` unpacks the `(class_name, arg_count)` tuple emitted by the compiler, looks up the class by string name (was failing with `Unknown class: ('Dog', 0)`), and delegates to `_call_constructor` so constructor arguments are passed correctly.
- **Class property defaults are now preserved in the VM.** `VarDeclaration` defaults inside a class body (e.g. `name = "Rex"`) are evaluated at compile time from the AST `Literal` value instead of being silently stored as `None`.
- **`epl/models/Modelfile` is now included in the source distribution.** A `global-exclude Modelfile` rule in `MANIFEST.in` was overriding the package-data inclusion in `pyproject.toml`, so `pip install` from sdist was shipping an incomplete `epl.models` package. Top-level `main.py` is also now explicitly included.

### Changed
- **`tests/test_consistency.py` reorganised.** The five `KNOWN_DIVERGENCE_CASES` and two `KNOWN_BACKEND_GAP_CASES` previously documenting VM divergences have all been promoted to `PARITY_CASES`; both buckets are now empty/removed. The full parity suite — 52 cases — runs against both backends with no expected failures.
- **`tests/test_release_packaging.py` no longer requires a top-level `bundle.py`.** The file was moved to `scripts/bundle.py` in an earlier refactor and `scripts/` is not shipped to end users; the test contract has been updated to reflect that.

### Migration notes
- No source changes required. Programs that previously produced incorrect output under `epl run --vm` (recursion, `continue`, `try`/`catch`, classes) will now match interpreter output. If you had workarounds in place that relied on the buggy VM behaviour, remove them.

---

## [9.0.0] — 2026-05-30

Enterprise hardening release. A focused security & robustness sweep across the interpreter, standard library, database layer, AI cloud integration, file watcher, and CLI. No new language features — every change makes existing surface area safer, more predictable, or easier to operate.

### Security
- **SQL injection — defense-in-depth across all database surfaces.** Stdlib `db_update`, `db_delete`, `db_count`, and `db_table_info` now reject table and column names that are not valid SQL identifiers (`^[A-Za-z_][A-Za-z0-9_]*$`) before any query is built. The same validation extends to `QueryBuilder` (`select`, `where_eq`, `where_like`, `where_in`, `where_gt`, `where_lt`, `where_between`, `where_null`, `where_not_null`, `order_by`, `group_by`, `join`, `left_join`) in `epl/database.py` and to `insert`, `insert_many`, `update`, `delete`, `find_by_id`, and `count` in `epl/database_real.py`. Numeric `LIMIT`/`OFFSET` values are coerced through `int()` so non-numeric strings fail loudly instead of being spliced into SQL. `ORDER BY` direction is restricted to `ASC`/`DESC`. Identifiers are now consistently double-quoted in emitted SQL.
- **Command injection — `exec_async` no longer uses `shell=True`.** Accepts either a list of argv tokens or a single command string that is parsed with `shlex.split` (POSIX rules on Unix, Windows rules on NT). `kill_process` and `env_delete` have been added to the interpreter sandbox alongside the existing `exec`/`file_*`/`env_set` denylist so untrusted scripts cannot escape it.
- **`epl doctor` no longer spawns subprocesses through the shell on Windows.** Commands run as explicit argv with `shell=False`; `shutil.which` resolves `.cmd`/`.bat` shims (npm, etc.) safely.
- **AI cloud config moved out of the package directory.** API keys are now stored in a per-user XDG-aware location — `%APPDATA%\epl\ai_config.json` on Windows, `$XDG_CONFIG_HOME/epl/ai_config.json` (default `~/.config/epl/ai_config.json`) on POSIX — and chmod'd to `0600` on POSIX. Existing `epl/.ai_config.json` files are migrated automatically on first read. Gemini requests now send the API key via the `x-goog-api-key` header instead of as a URL query parameter, keeping it out of proxy logs and shell history.

### Fixed
- **Generators no longer return stale values on timeout.** `EPLGenerator` previously waited 30s for the next yielded value and silently returned the previous value if the body was wedged. It now raises `EPLRuntimeError` with the generator name, the timeout it hit, and guidance to set `EPL_GENERATOR_TIMEOUT`. The timeout is configurable via `EPL_GENERATOR_TIMEOUT=<seconds|none|off>` for long-running computations.
- **`epl watch` no longer kills long-running programs at 60s.** The hard-coded subprocess cap is gone; runs are uncapped by default. Pass `--timeout=<seconds>` (or `--timeout=none`) to opt back into a cap. The watch dispatcher now also warns when an unknown `--flag` is passed instead of silently ignoring it.
- **CLI error reporting is now consistent across `main.py`.** All command dispatchers route through `_cli_error_report` / `_cli_error_exit` helpers, which print a one-line summary by default and a full traceback when `EPL_DEBUG=1` is set or `--debug` is passed anywhere on the command line. ~25 ad-hoc `except Exception:` blocks were collapsed into this single path.

### Changed
- **AI config loading is now cached.** `_load_config()` no longer hits disk on every prompt; `configure_cloud()` / `clear_cloud()` invalidate the cache as expected.
- **`requirements.txt` rewritten for clarity.** Required runtime dependencies (`gunicorn`, `flask`) are separated from optional extras (encryption, PostgreSQL, MySQL, LLVM, Redis, mobile, ML, dev tooling), each commented with its purpose. Pure-standard-library features are no longer listed as commented-out requirements.

### Added
- **`tests/test_security_hardening.py`** — covers stdlib SQL identifier validation, sandbox additions, shell-less `exec_async`, AI config path & permissions, and Gemini header auth.
- **`tests/test_correctness_hardening.py`** — covers generator yield-timeout behavior and watcher `--timeout` plumbing.
- **`tests/test_database_hardening.py`** (16 tests) — covers `QueryBuilder` and `database_real` identifier quoting, rejection of injection attempts in every column/table/order-by/limit slot, and the `IN ()` degenerate-case shortcut.

### Migration notes
- **AI config:** First run of `epl ai …` after upgrade migrates `epl/.ai_config.json` to the per-user location automatically. If you have keys checked into a fork, rotate them — file location change does not remediate prior exposure.
- **`exec_async`:** Scripts that relied on shell features (pipes, redirects, `&&`) in `exec_async` need to either pass an argv list, switch to `exec`/`exec_output` (which retain their previous semantics), or explicitly invoke a shell (`exec_async(["bash", "-c", "..."])`).
- **`epl watch`:** Workflows that depended on the implicit 60s kill should now pass `--timeout=60` explicitly.
- **Generators:** Code that swallowed the previous silent-timeout behavior must now catch `EPLRuntimeError` or extend the timeout via `EPL_GENERATOR_TIMEOUT`.

---

## [8.0.0] — 2026-05-26

### Added
- **`epl watch`** — File watcher with auto-reload for development (PR #47 by @imkoushal)
  - Watches `.epl` files for changes and auto-reruns the program
  - Zero external dependencies (polling-based using `os.stat`)
  - `--test` flag to re-run tests instead of the program
  - `--clear` flag to clear screen before each re-run
  - `--debounce=MS` to customize debounce interval (default: 300ms)
  - 19 unit tests (all passing)
- **`epl doctor`** — Environment health checker (PR #48 by @imkoushal)
  - 11 diagnostic checks: Python version, EPL installation, Node.js/npm, Git, pip, platform, disk space, terminal encoding, project structure, dependencies
  - Color-coded output with actionable fix hints
  - `--json` flag for CI/automation integration
  - 27 unit tests (all passing)
- **Enterprise Discord AI Agent Enhancements** (`examples/discord_agent/`)
  - FAQ auto-reply engine — instant responses without LLM for common questions
  - XP / Leveling system — users earn XP per message, level up through 7 ranks (Newcomer → EPL Legend)
  - Support ticket system — `!ticket` command with automated tracking and founder alerts
  - Anti-raid protection — detects mass joins (10+ in 60s) and alerts `#bot-control`
  - Auto-moderation — instant deletion of invite links, mass mentions, and spam
  - Auto-welcome — rich embed welcome messages with EPL code examples for new members
  - Server milestone celebrations — automated announcements at 10, 25, 50, 100, 250, 500, 1000 members
  - Corrected EPL code knowledge — bot now generates syntactically correct EPL with proper string quoting
  - Concise responses — short questions get short answers, no more walls of text

### Changed
- **VS Code Extension v2.1.0** — Added `epl.watch` and `epl.doctor` commands, enhanced TextMate grammar with missing keywords from lexer/parser (Generic, Where, Yields, Spawn, Parallel, Lambda, Breakpoint, Declare, Let), improved method call highlighting, and new `has` keyword support for class properties
- Version bump to `8.0.0` for PyPI distribution

---

## [7.8.2] — 2026-05-24

### Added
- **Enterprise Discord Agent** — Added a 100% EPL native AI Community Manager for Discord (`examples/discord_agent/`) with advanced spam defense, server-aware routing, and terminal-free background execution scripts.

---

## [7.8.1] — 2026-05-23
- **TaskFlow Pro Max** — Completely overhauled the `taskflow_saas` example with a high-energy, unapologetic Neo-Brutalist UI architecture.
  - Implemented solid box-shadow physics and mechanical hover/active states.
  - Migrated from generic glassmorphism to strict geometric brutalism (0px border radius, sharp contrast, Acid Green accents).

### Fixed
- **Form Parsing Robustness** — Resolved parsing issues in EPL's web backend where empty optional form fields caused exceptions, by enforcing the safe `web_request_param()` pattern.
- **Avatar Letter Fix** — Fixed standard library `uppercase` usage for avatar initialization in session cookies.

---

## [7.6.0] — 2026-05-19

### Added
- **Enterprise Documentation Overhaul** — All project documentation updated to enterprise-grade quality with consistent branding, comprehensive contributor guides, and professional formatting
- **Formal Grammar Specification v7.6** — Updated EBNF grammar to cover JS/TS bridge syntax, Generic types, 3D/Canvas blocks, and all v7.x additions

### Changed
- **CI/CD Pipeline Stabilization** — Achieved 100% green build across the full test matrix (Ubuntu, macOS, Windows × Python 3.11, 3.12)
  - Replaced unstable `import main` with `importlib.util` dynamic path loading
  - Added `pytest.importorskip` guards for optional dependencies (`llvmlite`)
  - Fixed `memory_usage` stdlib test for Windows CI compatibility (`>= 0` vs `> 0`)
  - Switched to explicit stable test file list (61 files) with `shell: bash` for cross-platform line continuation
  - Added `pytest-cov` to CI dependencies for coverage reporting
- **Test Harness Hardening** — Decoupled CI tests from local-only development files (`main.py`) using `@skipUnless` decorators and conditional imports

### Infrastructure
- Version bump to `7.6.0` for PyPI distribution
- Coverage threshold override (`--cov-fail-under=0`) for CI subset runs

## [7.5.2] — 2026-05-12

### Added
- **JavaScript/TypeScript Bridge** — New `Use javascript "library"` / `Use typescript "library"` syntax for accessing the NPM ecosystem from EPL
  - `epl/js_bridge/` — Persistent Node.js subprocess bridge with JSON-RPC protocol over stdin/stdout
  - `JSModule` wrapper class in `interpreter.py` — enables `module.method()` and `module.property` access
  - NPM auto-install for allowlisted packages via `package_manager.py` integration
  - `epl jsinstall <pkg>` / `epl jsremove <pkg>` / `epl jsdeps` — CLI commands for npm dependency management
  - JS transpiler support — `UseJSStatement` emits proper ESM `import` or CommonJS `require`
  - Error explainer patterns for Node.js-not-installed, missing modules, and bridge crashes
  - 34 unit tests covering parser, AST, serialization, transpiler, and Node.js integration
- **Observability Module** (`epl/observability.py`) — Production-grade health checks (`/_health`), readiness probes (`/_ready`), Prometheus-format metrics (`/_metrics`), and structured JSON logging with thread-safe request tracking
- **Kubernetes Manifest Generator** (`epl/k8s_gen.py`) — Generate Namespace, ConfigMap, Deployment, Service, Ingress, and HorizontalPodAutoscaler YAML from CLI with strict input validation
- **Cloud Deploy** (`epl/cloud_deploy.py`) — One-command deployment config generation for AWS ECS/ECR, GCP Cloud Run, and Azure Container Apps with Docker image handling
- **Style/Layout Generation** — CSS style blocks, responsive layout containers, and cross-platform styling with XSS-hardened output
- **3D/Canvas Support** — `Scene` blocks for WebGL 3D rendering and `Canvas` draw commands (rect, circle, line, text, path) with batched rendering
- **Cross-Platform Generation** — iOS (SwiftUI), Desktop (Compose Multiplatform), and Web/WASM target generators
- **Cloudflare Workers Configuration** — Edge deployment support via `wrangler.jsonc`

### Security
- **Input Validation** — Strict regex validation for all user inputs (app_name, image, region, account_id, port, service_type, hostname) in `k8s_gen.py` and `cloud_deploy.py` to prevent shell/YAML injection
- **Thread Safety** — Added `_readiness_lock` for concurrent readiness access in observability module
- **XSS Hardening** — HTML sanitization in style/layout and canvas output generation
- **CSS Injection Prevention** — Strict validation of CSS property values in style blocks

## [7.5.1] — 2026-05-11

### Added (PR Integrations)
- **AI Error Explainer** (PR #3 by @imkoushal) — `epl fix <file>` command with 27-pattern error analysis, "Did you mean?" suggestions, Python/JS foreign keyword detection, and optional AI-powered deep analysis via Ollama/cloud backends.
- **`--ai-errors` CLI flag** — Enable error explainer diagnostics during normal `epl run` execution.
- **`to_context_dict()`** on `EPLError` — Structured error context with surrounding source lines for AI consumption.
- **AWS Cloud Backend** (PR #4 by @D1v3shh) — `cloud_*` stdlib functions for S3 (upload/download/list/read/write/delete/exists/buckets), Lambda (invoke), and SQS (send/receive/delete) with lazy-loaded boto3, thread-safe client caching, and `pip install "eplang[cloud]"` optional dependency.
- **`epl-cloud` Official Package** — Registry entry, EPL source, examples, and `epl.toml` manifest.
- **44 new tests** covering error explainer patterns and cloud backend operations.

### Fixed
- **VS Code Terminal Command Injection** — Replaced unsafe string interpolation in `extension.js` with a safe `buildEplCommand()` builder that properly quotes file paths for both PowerShell and Unix shells.
- **Syntax Reference Ternary Example** — Corrected `Set label = "big" if ...` to the canonical parser form `Set result to "big" if x > 10 otherwise "small"`.
- **Playground Thinking-Block Rendering** — AI "Thinking Process" blocks are now extracted before markdown escaping and re-injected as styled HTML, preventing display corruption.

### Changed
- **Test Modernization** — Migrated CLI dispatcher tests from `main.py` file reads to direct `epl.cli.cli_main` source introspection, aligning with the authoritative CLI architecture.
- **Landing Page Version** — Updated `docs/index.html` badge to `EPL v7.5.1 IS LIVE!`.
- **Extension Version Logging** — `extension.js` now reads version dynamically from `package.json` instead of a hardcoded string.

## [7.5.0] — 2026-04-28

### Added
- **Scientific Packages** — Merged PR #2 adding `epl-science`, `epl-plot`, `epl-learn`, `epl-dataframe`, and `epl-array` official packages with Python bridge backends.
- **`Use` Syntax** — `Use python "json" as json_mod` for importing Python modules directly into EPL scope.
- **Official `.epl` File Icon** — VS Code extension now contributes a dedicated file icon for `.epl` files in the explorer.
- **Lint, Profile, and Build Commands** — `epl.lintFile`, `epl.profileFile`, and `epl.compileFile` commands added to the VS Code extension with editor title bar integration.
- **`.vscodeignore`** — Marketplace package now excludes `node_modules`, `.vsix` artifacts, and large PDFs.

### Fixed
- **`epl.run` Not Found** — Commands are now registered before the LSP client starts, preventing the "command not found" error when the Language Server fails.
- **Duplicate Dict Keys** — Removed duplicate keys in `epl/errors.py`.
- **Deprecated `asyncio` Calls** — Updated to modern `asyncio` API patterns.

### Changed
- **AI Provider Hardening** — Strengthened cloud AI provider configuration and error handling.
- **Extension Icon** — Updated to the new premium `epl_logo_minimal.png` design.

## [7.4.3] — 2026-04-17

### Added
- **Browser AST-Aware Copilot** — The web playground now features a live AST analysis engine powered by Pyodide, securely linked to an Edge AI backend for syntax-specific debugging.
- **Dynamic AI Thinking Mode** — Copilot natively evaluates complex architectural requests using a multi-step semantic logic sequence.
- **Strict Grammar SSOT** — Single Source of Truth enforced across CLI and Edge workers to accurately identify Enums, Ternaries, Error Handling, and File I/O naturally.
- **Root Repository Restructuring** — Purged thousands of lines of dev scratchpads and leaked release artifacts to enforce an industry-standard project structure.
- **Kubernetes Manifest Generator** — `epl deploy k8s` generates production-ready
  Kubernetes manifests: Namespace, ConfigMap, Deployment (with liveness/readiness
  probes, non-root security context, resource limits), Service, Ingress (with
  optional TLS), and HorizontalPodAutoscaler.
  - CLI: `epl deploy k8s --image myapp:1.0 --host myapp.example.com --tls`
  - All manifests written to `./k8s/` by default
- **Bug fix** — Fixed `tests/test_llvm.py` crashing on Python 3.13 when
  `llvmlite` is not installed.

## [7.3.2] — 2026-04-06

### Fixed
- **REPL Python 3.9–11 Compatibility** — Fixed f-string syntax error (`{'━' * 55}` nested quotes) in `epl/repl.py` that crashed on Python 3.9, 3.10, and 3.11. Now uses a pre-computed variable compatible with all supported Python versions.

## [7.3.1] — 2026-04-06

### Added
- **REPL Modernization** — Replaced basic interactive shell with a rich `prompt_toolkit` interface providing real-time syntax highlighting, ghost-text auto-suggestions from history, and robust multi-line continuation tracking.
- **Stdlib Domain Modules** — Architected safe, lazy-loaded domain modules (`epl/stdlib_modules/web.py`, `.db.py`, `.concurrency.py`, `.math.py`, `.collections.py`) as clean import facades directly on top of the `stdlib` monolithic core. Allows `Import "web" from stdlib` with full API isolation.
- **New Examples** — Added high-quality demo applications: `examples/todo_app/` (SQLite ORM + REST API), `examples/cli_calculator.epl` (CLI parsing and functions), and `examples/guessing_game.epl` (Randomness, loops, and IO).
- **First-party Modularization** — Scaffolded the `epl-auth` boilerplate to test dependencies and package repository concepts.

## [7.2.0] — 2026-04-06

### Added
- **Documentation Website** — Full MkDocs Material docs at [abneeshsingh21.github.io/EPL](https://abneeshsingh21.github.io/EPL)
  - Getting started guide, language reference, stdlib reference
  - Web, Database, and Android development guides
  - Examples gallery with real-world projects
  - Online playground integration
- **LSP Autocomplete Expansion** — 90+ new stdlib function signatures for IDE autocomplete, hover docs, and signature help (database, web, crypto, concurrency, GUI, game dev, ML)
- **Project Templates** — `epl new --template android` and `epl new --template fullstack` (7 templates total)
- **Error Diagnostics** — 19 new error hint patterns for common mistakes (type coercion, database, web server, block matching)
- **CI/CD** — GitHub Actions for automated testing (3 OSes × 3 Python versions) and docs auto-deploy

## [7.1.0] — 2026-04-06

### Added
- **Production Server Defaults** — `epl serve` now defaults to waitress/gunicorn/uvicorn
  - `--dev` flag for development mode with hot-reload
  - `--engine` flag for manual server selection
  - Auto-install of waitress if no production server found
- **Android Build Pipeline** — `epl android --build` compiles APKs via Gradle
  - Auto-detection of ANDROID_HOME across Windows/Linux/macOS
  - `--name` flag for custom app display name
- **Stdlib Modularization** — Domain registry mapping 725 functions to 33 domains
  - `epl/stdlib_modules/` package with lookup utilities
  - 100% coverage of all stdlib functions
- **Example Projects** — `examples/hello_web`, `examples/todo_api`, `examples/calculator`

## [7.0.1] — 2026-04-05

### Added
- LLVM compiler backend with native executable output
- Bytecode VM for faster interpretation
- Package manager with `epl.toml` manifest
- Web framework with WSGI/ASGI adapters
- ORM with models, migrations, relationships
- Concurrency primitives (threads, channels, mutexes, barriers)
- Desktop GUI via tkinter
- Game development via Pygame
- Data science via Pandas/NumPy
- Machine Learning via scikit-learn/PyTorch
- Android project generation via Kotlin transpilation
- iOS project generation via Swift transpilation

## [1.0.0] — 2024

### Initial Release
- EPL language interpreter with tree-walking evaluation
- English-like syntax for variables, functions, classes, modules
- 725 standard library functions
- VS Code extension with LSP support
- Interactive REPL
- Code formatter and type checker
