# EPL Troubleshooting

This guide covers the most common problems when using EPL in development, CI, and deployment workflows.

## CLI and Project Setup

### `epl run` or `epl build` cannot find the entry file

Check:

- the project has `epl.toml`
- `[project].entry` points to a real file
- the command is being run from the project root

Recommended fix:

```bash
epl new myapp --template cli
cd myapp
epl run
```

### `epl install --frozen` fails

Causes:

- `epl.lock` is missing
- the lockfile is stale relative to the manifest
- a GitHub dependency is not pinned correctly in the lock data

Recommended fix:

1. run `epl install`
2. verify dependencies in `epl.toml`
3. regenerate and commit `epl.lock`
4. rerun `epl install --frozen`

## Formatting and Tooling

### `epl fmt --check` fails in CI

This means at least one `.epl` file would be reformatted.

Recommended fix:

```bash
epl fmt src --in-place
```

Then rerun:

```bash
epl fmt src --check
```

### LSP diagnostics feel stale while typing

The language server now debounces rapid document changes and flushes pending analysis when completion, hover, or symbol requests arrive.

If behavior still feels stale:

- wait for the current file to settle briefly
- restart the editor language server
- verify the file parses outside the editor with `epl lint`

## Web and Deployment

### `epl serve` starts but routes do not respond

Check:

- the entry file actually creates an EPL WebApp
- the process is running from the project root
- the app exposes `/_health`

Recommended fix:

```bash
epl serve --port 8080
```

Then validate:

```bash
curl http://127.0.0.1:8080/_health
```

### Generated Docker deployment does not boot

Check:

- Docker is installed and running
- the project was generated with `epl deploy all`
- the compose file points at the generated `deploy/Dockerfile`

Recommended validation path:

```bash
docker compose -f deploy/docker-compose.yml config
docker compose -f deploy/docker-compose.yml up -d --build
```

### Deployed reference apps are not being monitored

The repo now includes `.github/workflows/reference-app-monitor.yml`.

To activate it, configure:

- `EPL_REFERENCE_BACKEND_URL`
- `EPL_REFERENCE_FULLSTACK_URL`

You can also trigger the workflow manually and pass `backend_url` /
`fullstack_url` as dispatch inputs for one-off checks.

You can also run monitoring locally:

```bash
python scripts/monitor_reference_apps.py --backend-url https://backend.example --fullstack-url https://app.example
```

## Android and Desktop

### Android Gradle build fails locally

Check:

- `ANDROID_SDK_ROOT` or `ANDROID_HOME` is set
- Java 17 is installed
- required SDK packages are installed

Reference validation tasks:

- `lintDebug`
- `testDebugUnitTest`
- `assembleDebug`
- `assembleRelease`

### Desktop Gradle build fails locally

Check:

- Java 21 is installed
- the generated `gradlew` wrapper is executable on Unix

Reference validation tasks:

- `compileKotlin`
- `test`

## Native Build

### `epl build` fails for native compilation

Check:

- `llvmlite` is installed
- a system compiler is available
- the release environment has the required LLVM/native toolchain

On Linux, validate with the same environment used in release smoke where possible.

## Package Ecosystem

### `epl search` / `epl update` / `epl audit` output looks inconsistent

Check:

- the project manifest is valid
- the lockfile is current
- official bundled packages are not being shadowed by stale local package state

If the project state is unclear:

1. inspect `epl.toml`
2. inspect `epl.lock`
3. rerun `epl install`
4. rerun `epl audit`

## When To Escalate

Capture these before reporting an issue:

- EPL version from `epl --version`
- operating system and Python version
- exact command run
- minimal EPL file or project reproducing the problem
- full traceback or CLI output
