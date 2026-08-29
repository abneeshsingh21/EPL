# EPL Platform Production Governance

**EPL — English Programming Language Platform Governance & Operational Policy**

This document formalizes the decision-making process, technical steering, release qualification gates, deprecation lifecycle, and platform maintenance standards for the EPL ecosystem.

---

## 1. Technical Steering & Leadership

EPL is developed as an open platform guided by a clear technical governance structure:

- **Benevolent Dictator / Project Lead**: Sets long-term vision, final release sign-offs, and architectural direction.
- **Core Maintainers**: Responsible for subsystem integrity (Compiler, Virtual Machine, Runtime Stdlib, Web Framework, Tooling & LSP, Security).
- **Contributors**: Propose bug fixes, documentation improvements, RFCs, and optimizations.

---

## 2. Language Evolution & RFC Process

Language design modifications follow a structured Request for Comments (RFC) lifecycle to protect backwards compatibility and avoid churn:

1. **Idea / Draft**: Community discussion via GitHub Discussions or Issue Tracker.
2. **RFC Proposal**: Formal document specifying syntax additions, AST changes, HIR lowering rules, VM bytecode impact, stdlib bindings, and test fixtures.
3. **Core Review**: Review by core maintainers focusing on:
   - Grammatical unambiguousness (English natural language parser clarity)
   - Compatibility with existing programs and target transpilers (JS, WASM, Kotlin, Native LLVM)
   - Performance and runtime complexity
4. **Acceptance & Implementation**: Feature flag or standard release integration.

---

## 3. Versioning & Deprecation Policy

EPL strictly follows [Semantic Versioning 2.0.0 (SemVer)](https://semver.org/):

- **Major Releases (`X.0.0`)**: Breaking grammatical changes, incompatible bytecode formats, or removals of previously deprecated APIs.
- **Minor Releases (`X.Y.0`)**: Backwards-compatible features, new stdlib modules, compiler optimizations, tooling enhancements.
- **Patch Releases (`X.Y.Z`)**: Backwards-compatible bug and security fixes.

### Deprecation Lifecycle
- An API or syntax feature marked as deprecated triggers a compiler/runtime warning for at least **one full minor release cycle** before removal.
- All deprecations are recorded in `CHANGELOG.md` with explicit migration instructions.

---

## 4. Production Release Gates (Release Qualification)

Every release must satisfy non-negotiable automated quality gates before artifact publishing:

1. **Test Verification**:
   - `pytest`: 100% pass rate across all unit, integration, and fuzz test suites.
   - Built-in test runner (`tests/run_tests.py`): 100% pass rate.
   - Headless CI execution: Parameter validation on Linux without graphical display requirements.
2. **Performance Regression Baseline**:
   - Benchmarks must execute within defined threshold margins (`benchmarks/thresholds.py` and `benchmarks/thresholds.json`).
3. **Reproducible Builds & Packaging**:
   - Wheel (`.whl`) and Source Distribution (`.tar.gz`) builds install cleanly in clean-room environments.
   - Release archive checksums (SHA-256) are generated and verified.
4. **Security Audit**:
   - Manifest path sanitization and locked dependency SHA-256 verification.
   - No untrusted shell execution.

---

## 5. Security & Vulnerability Operations

Security vulnerabilities are prioritized according to the response matrix defined in `SECURITY.md`. Critical vulnerabilities receive immediate patch triage and out-of-band point releases.
