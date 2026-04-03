# EPL Reference Apps

These reference projects are the maintained proof points for EPL's platform claims.

They are intended to stay buildable or executable, documented, and covered by CI smoke tests.

## Maintained Apps

### Backend API

Path: `apps/reference-backend-api`

Purpose:
- validate EPL WebApp route handling for JSON APIs
- validate SQLite-backed request handling
- provide a minimal backend service example

Validation:
- `python -m pytest tests/test_reference_apps.py -q`
- optional deployed-service monitoring via `python scripts/monitor_reference_apps.py --backend-url <url>`

### Fullstack Web App

Path: `apps/reference-fullstack-web`

Purpose:
- validate server-rendered page output
- validate JSON API routes and persistence
- validate manifest-driven `epl serve` startup
- validate production deploy artifact generation
- validate generated WSGI and ASGI adapters against real routes
- validate generated Docker Compose deployment boot against real routes in CI
- provide a minimal fullstack EPL web application

Validation:
- `python -m pytest tests/test_reference_apps.py -q`
- `EPL_RUN_DOCKER_DEPLOY_TESTS=1 python -m pytest tests/test_reference_apps.py -q`
- optional deployed-service monitoring via `python scripts/monitor_reference_apps.py --fullstack-url <url>`

### Android App Generator Input

Path: `apps/reference-android`

Purpose:
- validate Android project generation from EPL source
- keep standard Gradle wrapper, manifest, and Kotlin project output under test
- validate real Android lint, unit-test, debug, and release build tasks in the Android CI job

Validation:
- `python -m pytest tests/test_reference_apps.py -q`
- `EPL_RUN_ANDROID_BUILD_TESTS=1 python -m pytest tests/test_reference_apps.py -q`

### Desktop App Generator Input

Path: `apps/reference-desktop`

Purpose:
- validate desktop project generation from EPL source
- keep generated Kotlin/Gradle layout under test
- validate a real Gradle desktop compile/test run in CI

Validation:
- `python -m pytest tests/test_reference_apps.py -q`
- `EPL_RUN_DESKTOP_BUILD_TESTS=1 python -m pytest tests/test_reference_apps.py -q`

### Reusable Library Package

Path: `packages/reference-hello-lib`

Purpose:
- validate package manifest, packing, and install flow
- provide a reference EPL library/package layout

Validation:
- `python -m pytest tests/test_reference_apps.py -q`

## CI Contract

The following checks are expected to stay green:

- `python -m pytest tests/test_reference_apps.py -q`
- `python -m pytest tests/test_legacy_harness_smoke.py -q`
- generated `deploy/wsgi.py` and `deploy/asgi.py` must boot the maintained fullstack app in CI
- dedicated Docker CI job with `EPL_RUN_DOCKER_DEPLOY_TESTS=1`
- dedicated Android CI job with `EPL_RUN_ANDROID_BUILD_TESTS=1`
- dedicated desktop CI job with `EPL_RUN_DESKTOP_BUILD_TESTS=1`
- scheduled/manual monitoring workflow in `.github/workflows/reference-app-monitor.yml` for deployed backend/fullstack URLs

## Operational Monitoring

For deployed reference services, use:

- `python scripts/monitor_reference_apps.py --backend-url <url> --fullstack-url <url>`

The monitoring workflow reads these GitHub secrets when configured:

- `EPL_REFERENCE_BACKEND_URL`
- `EPL_REFERENCE_FULLSTACK_URL`

The monitor checks:

- backend `/_health`
- backend `/api/health`
- fullstack `/_health`
- fullstack `/`
- fullstack `/api/login`
- fullstack `/api/notes`

## Usage Notes

- These projects are reference targets, not one-off demos.
- If EPL behavior changes, update the app sources, README guidance, and CI tests together.
- New platform claims should land with a maintained reference app or package where practical.
