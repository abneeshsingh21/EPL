# EPL Production Roadmap

This document defines the path from a working language project to a production-grade platform.

It does not assume "feature complete" means "production ready". The bar is higher:

- deterministic behavior
- stable install and release flows
- clear compatibility rules
- validated real-world targets
- maintainable tooling and docs
- security and operational discipline

## Target Definition

EPL should become:

- production-usable for CLI tools, automation, libraries, internal services, and selected web apps
- credible for Android, desktop, and packaged app generation where the generated output is tested and documented
- predictable to upgrade, with stable CLI/config behavior and deprecation paths

EPL is not at Java/Python/C++/Node ecosystem parity today. That is a longer-term ecosystem problem, not a single refactor. The near-term goal is a production-grade EPL platform with clear support boundaries.

## Phase 1: Core Reliability

Goal: make the language core predictable and testable.

Work:

- unify parser, interpreter, VM, and compiler behavior on shared fixture suites
- convert legacy script-style test runners into structured pytest/unittest coverage
- add golden tests for syntax errors, runtime errors, type errors, and diagnostics
- remove hidden behavioral drift between `main.py` and `python -m epl`
- add regression suites for imports, modules, packages, stdlib loading, and manifests

Exit criteria:

- structured test suite is the primary test surface
- target coverage includes parser, interpreter, VM, compiler, package manager, CLI, and web/runtime features
- no import-time script runners are required for CI correctness
- deterministic pass/fail behavior across supported Python versions

## Phase 2: Release and Install Hardening

Goal: make EPL installable, releasable, and reproducible.

Work:

- keep `python -m build`, wheel, sdist, and standalone bundle paths healthy
- verify installed wheel behavior in a clean virtual environment
- add smoke tests for `pip install`, `epl --version`, `epl new`, `epl run`, and `epl build`
- define release artifact checksums and reproducible build expectations where feasible
- harden package-data handling for stdlib/runtime assets

Exit criteria:

- clean-room install works from wheel and sdist
- release CI publishes validated artifacts only
- bundle/install docs are accurate and tested

## Phase 3: Platform Contract Cleanup

Goal: freeze the public behavior surface.

Work:

- unify `epl/cli.py` and `main.py` behind one authoritative command implementation
- standardize command names, flags, exit codes, and error formatting
- finish migration rules for `epl.toml` and legacy `epl.json`
- define a public compatibility contract for manifests, CLI commands, and package layout
- reduce monolithic modules where practical to lower change risk

Exit criteria:

- one authoritative CLI implementation
- one manifest story
- documented command and config compatibility policy

## Phase 4: Real Application Validation

Goal: prove EPL against real target workloads instead of toy examples.

Reference apps to maintain:

- backend API service
- fullstack web app with auth, templates or frontend integration, persistence, and deployment docs
- Android sample app with buildable project output
- desktop sample app
- reusable library/package with publish/install/update flow

Each app must have:

- source in-repo
- CI validation
- documented run/build/deploy steps
- smoke or integration tests

Exit criteria:

- EPL can build and run these reference apps reliably from clean setup
- web, package, and app-generation claims are backed by tested examples

## Phase 5: Tooling and Developer Experience

Goal: make EPL maintainable for users, not just for the author.

Work:

- finish docs alignment across README, spec, references, tutorials, and examples
- strengthen formatter, linter, debugger, and LSP behavior with regression tests
- add migration guides, troubleshooting docs, and release notes discipline
- improve package-manager UX around search, install, lockfiles, validation, and publishing

Exit criteria:

- docs match reality
- supported workflows are discoverable and reproducible
- editor and debugging workflows are stable enough for day-to-day use

## Phase 6: Production Governance

Goal: make EPL operable as a maintained platform.

Work:

- define versioning and deprecation policy
- add security reporting and dependency review discipline
- define support matrix: Python versions, OS targets, optional dependencies
- add performance baselines for interpreter, VM, compiler, package operations, and web serving
- publish release checklist and "production-ready" criteria

Exit criteria:

- releases have explicit gates
- deprecations are versioned and documented
- support boundaries are clear

## Immediate Tranche

Execute next:

1. Convert more legacy test scripts into structured pytest/unittest modules.
2. Continue CLI unification so `main.py` becomes a thin wrapper only.
3. Add clean-environment install smoke tests in CI.
4. Build one real reference backend/web app and one Android validation app.
5. Close the remaining doc drift around old version labels and stale capability claims.

## Production Bar

EPL should be called production-grade only when all of the following are true:

- release artifacts install cleanly and reproducibly
- core language behavior is covered by structured automated tests
- public CLI and manifest behavior is stable and documented
- major advertised targets are validated by real maintained sample apps
- security, upgrade, and compatibility policies exist and are followed
