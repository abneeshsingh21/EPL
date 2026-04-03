# EPL Versioning Policy

EPL uses Semantic Versioning for the public platform surface.

## Version Meaning

- major: breaking language, CLI, manifest, or public API changes
- minor: backward-compatible features, new commands, new stdlib/module capabilities
- patch: backward-compatible fixes, security fixes, packaging fixes, documentation fixes

## Public Surface Covered By SemVer

- CLI command names, primary flags, and exit-code behavior
- `epl.toml` manifest structure
- package manager workflows
- Python package import surface under `epl`
- maintained reference-app workflows documented in the repo

## Deprecation Rules

- deprecations must be documented in `CHANGELOG.md`
- deprecated CLI commands or manifest fields must keep working for at least one minor release unless there is a security reason to remove them earlier
- the warning message must include the replacement command or field
- removal happens only in a major release unless an emergency security fix requires otherwise

## Compatibility Rules

- `epl.toml` is the canonical manifest
- `epl.json` support is legacy compatibility and may be removed only in a future major release after documented notice
- `main.py` should not expose behavior that differs from `python -m epl` / `epl`
- stable commands keep their documented names, primary flags, and basic exit-code behavior through `7.x`
- beta commands may change within `7.x`, but changes must still be documented in release notes and help output
- experimental commands may change or be removed faster, but should not silently change without documentation

## Command Stability Labels

Stable commands:

- `run`, `new`, `build`, `test`, `repl`
- `install`, `uninstall`, `packages`, `search`, `lock`, `update`, `outdated`, `audit`
- `gitinstall`, `gitremove`, `gitdeps`, `pyinstall`, `pyremove`, `pydeps`, `github`
- `serve`, `deploy`, `check`, `fmt`, `lint`, `docs`, `version`, `debug`
- `js`, `node`, `kotlin`, `python`, `android`, `desktop`, `web`, `gui`, `ir`, `vm`
- `benchmark`, `profile`, `bench`, `lsp`
- `resolve`, `workspace`, `ci`, `sync-index`

Beta commands:

- `wasm`
- `micropython`
- `playground`
- `notebook`
- `blocks`
- `copilot`
- `ai`
- `gen`
- `explain`

Experimental commands:

- `cloud`
- `train`
- `model`

## Release Discipline

- patch releases should not change the intended behavior of stable commands without a documented bug-fix rationale
- minor releases can add new commands and capabilities, but existing documented workflows must remain compatible
- major releases must ship migration guidance for removed or changed behavior
