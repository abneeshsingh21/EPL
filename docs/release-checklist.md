# EPL Release Checklist

Use this checklist before publishing a new EPL release.

## Version and Docs

- update version in the authoritative source
- update `CHANGELOG.md`
- verify README/docs/examples match the release behavior
- verify deprecations and removals are documented

## Test Gates

- `python -m pytest -q`
- `python tests/test_package_manager.py`
- `python tests/test_package_ux.py`
- `python -m pytest tests/test_cli_production.py -q`
- `python -m pytest tests/test_reference_apps.py -q`
- `python -m pytest tests/test_legacy_harness_smoke.py -q`
- `python scripts/check_benchmark_thresholds.py --json`
- `python -m pytest --collect-only -q`

Reference platform gates:

- fullstack reference app boots through `python -m epl serve` and serves the expected routes
- fullstack reference app generates deploy artifacts through `python -m epl deploy all`
- fullstack reference app passes `EPL_RUN_DOCKER_DEPLOY_TESTS=1 python -m pytest tests/test_reference_apps.py -q` through the generated Docker Compose deployment in the Docker CI environment
- Android reference app passes `EPL_RUN_ANDROID_BUILD_TESTS=1 python -m pytest tests/test_reference_apps.py -q` with lint, unit tests, debug build, and release build in the Android SDK/JDK CI environment
- desktop reference app passes `EPL_RUN_DESKTOP_BUILD_TESTS=1 python -m pytest tests/test_reference_apps.py -q` in the JDK CI environment
- if deployed reference app URLs are configured, `.github/workflows/reference-app-monitor.yml` is green on its scheduled run, and `python scripts/monitor_reference_apps.py --backend-url <url> --fullstack-url <url>` succeeds locally
- manual operational checks can use the workflow_dispatch inputs `backend_url` and `fullstack_url` without changing repo secrets

## Build and Install Gates

- `python -m build --wheel --sdist`
- clean-room wheel install succeeds
- `epl --version`
- `epl new`
- `epl run`
- `epl install`
- Python dependency bridge smoke passes
- GitHub project workflow smoke passes
- reference fullstack deploy generation smoke passes

Native build gate:

- run in the Linux release environment with compiler + LLVM dependencies available
- `epl build` succeeds on the generated sample project

## Artifact Checks

- wheel contains runtime assets and stdlib package data
- sdist contains runtime assets and release tooling files
- standalone bundle spec includes required runtime assets

## Manual Review

- verify support matrix changes, if any
- review security-impacting changes
- confirm reference app docs still match the generated/tested behavior
- confirm CI is green on the release commit
