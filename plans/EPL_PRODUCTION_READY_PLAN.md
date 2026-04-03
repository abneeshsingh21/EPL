# EPL 90-Day Production Hardening Plan

> Goal: move EPL from platform proof to a credible production platform.
>
> Principle: no new language syntax in this window. The work is about reproducibility, trust, operational maturity, and developer experience.

---

## Current Repo Facts

The repo is no longer in the early “can it generate apps?” phase.

- Default pytest suite is healthy and collected by one path.
- Android generation is backed by real Gradle build validation.
- Desktop generation is backed by real build validation.
- Fullstack deployment is backed by generated Docker Compose smoke validation.
- The main remaining production gaps are reproducible installs, cross-platform release proof, package trust, supported first-party libraries, and live operational proof.

The repo also still has a few important hard facts that define the next work:

- Lockfile format is still `v2` and does not fully pin Python bridge or GitHub dependencies.
- Coverage gate is still `60%` in `pyproject.toml`.
- The main CI matrix is still Linux + Windows only.
- Package trust workflows exist in partial form, but they are not yet strict enough for deterministic production installs.

---

## Execution Priorities

The next work shifts from “can EPL generate apps?” to “can EPL be trusted in real production operations?”

Priority order for this 90-day window:

1. Reproducible installs across EPL, Python bridge, and GitHub dependencies.
2. Cross-platform release proof on Linux, Windows, and macOS.
3. Supported first-party libraries for common production use.
4. Package trust hardening with checksums, commit pinning, and lockfile verification.
5. Developer experience improvements in errors, LSP, debugger, formatter, and templates.
6. Operational proof through maintained deployed reference apps.
7. Platform contract hardening in compatibility, support, and release documentation.

This window does not include:

- new language syntax
- deep subsystem extraction before supported facades prove useful
- signature infrastructure as a first step
- public LTS guarantees
- a full CLI surface freeze

---

## Tranche 1: Reproducible Installs and Release Proof

### Goal

Make `epl install` deterministic when a lockfile is present and prove the packaged toolchain works from clean wheel installs on all major OS targets.

### Work

- Upgrade the lockfile in `epl/package_manager.py` from `v2` to `v3`.
- Add `python_packages` with exact resolved versions and integrity hashes.
- Add `github_packages` pinned by commit SHA and archive/package integrity hashes.
- Add `epl install --frozen` in `epl/cli.py` and enforce lockfile-only installs in that mode.
- Make lockfile output deterministic:
  - stable key order
  - stable package order
  - no timestamps in the semantic diff surface
- Add macOS release proof in `.github/workflows/ci.yml`.
- Add a clean-room wheel install job that runs CLI smoke from the installed wheel.
- Keep LLVM native build smoke Linux-only inside the release workflow.

### Acceptance

- `epl lock` writes lockfile `v3`.
- `epl install --frozen` succeeds only when the lockfile fully covers project dependencies.
- EPL, Python bridge, and GitHub dependencies are all represented in the lockfile.
- Linux, Windows, and macOS all pass the release-smoke workflow.

---

## Tranche 2: Package Trust and Update UX

### Goal

Turn package management from “it works” into “it is safe enough to trust.”

### Work

- Normalize `search`, `outdated`, `update`, and `audit` behavior in `epl/cli.py` and `epl/package_manager.py`.
- Back `epl search` with `epl/package_index.py` instead of relying only on local/bundled data.
- Add SHA-256 verification for registry, GitHub, and direct URL installs before extraction.
- Require GitHub packages to lock to commit SHA for frozen installs.
- Reject floating GitHub installs in frozen mode.

### Explicit Deferral

- Do not build full package-signing infrastructure in this window.
- Use checksums, commit pinning, and lockfile verification first.

### Acceptance

- `epl search`, `epl outdated`, `epl update`, and `epl audit` produce stable, test-covered output.
- Frozen installs refuse ambiguous GitHub dependencies.
- Downloaded archives are verified before extraction.

---

## Tranche 3: Supported First-Party Libraries

### Goal

Give production users supported building blocks instead of forcing them to depend on internal runtime structure.

### Work

- Create supported facade packages first:
  - `epl-web`
  - `epl-db`
  - `epl-test`
- Keep these thin over current internals at first.
- Add docs, examples, and CI validation for each package.
- Update `epl new --template` to generate projects that depend on these supported packages.

### Explicit Deferral

- Do not start with a deep extraction of all web, database, and test internals.
- Prove the supported package layer first.

### Acceptance

- `epl install epl-web`, `epl install epl-db`, and `epl install epl-test` work in clean sample projects.
- New project templates use supported packages rather than undocumented internal behavior.

---

## Tranche 4: DX and Operational Proof

### Goal

Make EPL easier to use correctly and prove that real EPL services stay healthy outside CI.

### Work

- Improve interpreter and VM stack traces with source context first.
- Harden LSP change handling, parser recovery, and long-analysis timeouts.
- Add formatter `--check` and idempotency tests.
- Deploy and monitor:
  - the reference backend API
  - the reference fullstack web app
- Keep Android internal testing optional in this window if deployed backend/fullstack proof is still being established.
- Defer public registry deployment until package trust hardening and deployed-app monitoring are stable.

### Acceptance

- Stack traces show actionable source context in interpreter and VM paths.
- LSP survives rapid edit sequences without crashing.
- At least one backend service and one fullstack EPL app are deployed and monitored.

---

## 90-Day Validation Gates

The plan is on track when all of the following are true:

- `python -m pytest -q --cov=epl --cov-fail-under=80`
- `python -m pytest tests/test_reference_apps.py -q`
- `python -m pytest tests/test_release_packaging.py -q`
- `python -m pytest tests/test_cli_production.py -q`
- lockfile tests cover EPL, Python bridge, and GitHub frozen installs
- release-smoke CI is green on Linux, Windows, and macOS
- Android and desktop reference build jobs remain green
- fullstack Docker deploy smoke remains green

---

## Scope Guardrails

This plan is intentionally narrow.

Do now:

- reproducible installs
- release proof
- package trust
- supported facade libraries
- developer ergonomics
- deployed operational proof

Do later:

- package signatures
- deep subsystem extraction
- public registry hard launch
- benchmark hard fail thresholds in CI
- LTS promises
- full v7.x CLI freeze
