# EPL Support Matrix

This document defines the production support boundary for EPL.

## Python

Compatibility target:

- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

Current CI gate:

- Python 3.9
- Python 3.11
- Python 3.12

Cross-platform release smoke:

- Python 3.11 on Ubuntu
- Python 3.11 on Windows
- Python 3.11 on macOS

Release gate:

- Python 3.11 is the primary release validation environment

## Operating Systems

CI-gated:

- Ubuntu `latest`
- Windows `latest`
- macOS release smoke

## Optional Dependencies

Base install:

- `pip install eplang`
- supports interpreter, CLI, package manager, docs/lint/test workflows, and Python bridge

Native compilation:

- `pip install "eplang[llvm]"`
- requires `llvmlite`
- requires a system C compiler/linker such as `clang` or `gcc`

AI tooling:

- `pip install "eplang[ai]"`

Production serving:

- `pip install "eplang[server]"`
- Waitress for cross-platform WSGI serving
- Gunicorn for Linux/macOS WSGI serving
- Uvicorn and Hypercorn for ASGI serving
- generated `deploy/asgi.py` / `deploy/wsgi.py` entrypoints for external production hosts

Redis-backed features:

- `pip install "eplang[redis]"`

## Runtime Targets

Production-ready and CI-backed:

- interpreter / CLI workflows
- package manager and manifest workflows
- maintained reference backend API and fullstack web app route smoke tests
- reference fullstack app CLI `serve`, deploy-generation, and generated Docker Compose deployment validation
- deployed backend/fullstack monitoring through the reference-app monitor workflow when URLs are configured
- Android reference project generation plus standard Gradle wrapper, lint, unit-test, debug, and release build validation
- desktop project generation and Gradle compile/test validation

Supported with extra toolchain requirements:

- native build via LLVM + system compiler
- standalone packaging workflows

Not yet release-gated:

- large-scale Android device/emulator validation
- long-running production web load benchmarks

## Stability Contract

- `epl/cli.py` is the authoritative CLI implementation
- `main.py` is the source checkout wrapper over the same command surface
- `epl.toml` is the primary manifest format
- `epl.json` is legacy compatibility only
