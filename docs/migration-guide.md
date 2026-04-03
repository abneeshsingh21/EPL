# EPL Migration Guide

This guide covers the practical migration path from older EPL projects to the current v7 workflow.

## High-Impact Changes

- `epl.toml` is the primary manifest format.
- `epl.json` remains legacy compatibility only.
- `python -m epl` and `main.py` now share the same authoritative CLI surface.
- package workflows are lockfile-aware and support `epl install --frozen`.
- supported bundled packages now include `epl-web`, `epl-db`, and `epl-test`.

## Manifest Migration

Move older projects to `epl.toml` when possible.

Recommended fields:

```toml
[project]
name = "my-app"
version = "0.1.0"
entry = "src/main.epl"

[dependencies]
epl-web = "^1.0.0"
```

If a project still has `epl.json`, EPL will continue to read it for compatibility, but new projects and new docs should use `epl.toml`.

## CLI Migration

Prefer these commands:

- `python -m epl run`
- `python -m epl build`
- `python -m epl serve`
- `python -m epl install`
- `python -m epl fmt --check`

If older scripts call `python main.py`, they still work from source checkout, but the shared `epl` CLI is the stable contract to target.

## Package Workflow Migration

For reproducible installs:

1. run `epl install`
2. commit `epl.lock`
3. use `epl install --frozen` in CI and release automation

If you use Python bridge dependencies or GitHub packages, make sure they are declared in `epl.toml` so the lockfile can pin them.

## Web and App Templates

New projects should start from templates instead of handwritten skeletons:

- `epl new myapp --template web`
- `epl new myapp --template api`
- `epl new mylib --template lib`
- `epl new mytool --template cli`

These templates align with the supported packages and current docs.

## Android and Desktop Projects

Generated Android projects now use the standard vendored Gradle wrapper.
Generated desktop projects also use the standard Gradle flow.

Use:

- Android: `./gradlew lintDebug testDebugUnitTest assembleDebug assembleRelease`
- Desktop: `./gradlew compileKotlin test`

## Release Migration

For releases, prefer this baseline:

- `python -m pytest -q`
- `python -m build --wheel --sdist`
- clean-room wheel smoke
- reference app smoke tests
- `epl install --frozen`

## When To Keep Legacy Behavior

Legacy behavior is acceptable only for:

- source-checkout compatibility wrappers
- older manifests you have not migrated yet
- historical test fixtures that intentionally cover backward compatibility

Do not use legacy behavior as the default in new docs, new templates, or new CI.
