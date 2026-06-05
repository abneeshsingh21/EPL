<div align="center">

# Contributing to EPL

Thank you for your interest in contributing to the **English Programming Language**! 🎉

Every contribution — from bug reports to documentation fixes to new features — helps make EPL better for everyone.

</div>

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Contributor License Agreement](#contributor-license-agreement)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Documentation](#documentation)
- [Release Process](#release-process)

---

## Code of Conduct

This project is governed by the [EPL Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold a welcoming, inclusive, and harassment-free environment for everyone.

## Contributor License Agreement

Before your first Pull Request can be merged, you **must** sign the [Contributor License Agreement](CLA.md). A bot will automatically prompt you when you open your PR.

---

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.9 – 3.13 | Runtime and development |
| **Git** | 2.30+ | Version control |
| **Node.js** | 18+ | JS bridge and VS Code extension (optional) |
| **Ruff** | Latest | Linting and formatting |

### Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/EPL.git
cd EPL

# 2. Install in development mode with all extras
pip install -e ".[dev,cloud]"

# 3. Verify your setup
python -m pytest tests/test_framework.py -q
epl --version
```

> **Tip**: Use a virtual environment (`python -m venv .venv`) to isolate your development dependencies.

---

## Architecture Overview

Understanding EPL's architecture helps you contribute effectively:

```
Source Code (.epl)
       │
       ▼
   ┌────────┐     ┌────────┐     ┌─────────────┐
   │ Lexer  │ ──▶ │ Parser │ ──▶ │     AST     │
   └────────┘     └────────┘     └──────┬──────┘
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  │                     │                     │
                  ▼                     ▼                     ▼
          ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
          │ Interpreter  │    │  Bytecode VM │    │  LLVM Compiler   │
          │ (tree-walk)  │    │  (epl/vm.py) │    │ (epl/compiler.py)│
          └──────────────┘    └──────────────┘    └──────────────────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
  ┌────────┐ ┌────────┐ ┌──────────┐
  │  Web   │ │  GUI   │ │  Stdlib  │
  │ Server │ │Desktop │ │ (725 fn) │
  └────────┘ └────────┘ └──────────┘
```

| Directory | Purpose |
|-----------|---------|
| `epl/` | Core language implementation (lexer, parser, interpreter, VM, compiler) |
| `epl/stdlib.py` | 725 standard library functions |
| `epl/web.py` | WSGI/ASGI web framework |
| `epl/lsp_server.py` | Language Server Protocol implementation |
| `epl/js_bridge/` | Node.js interop bridge |
| `epl/official_packages/` | First-party package library |
| `tests/` | Test suite (90+ test files, 1642+ tests) |
| `vscode-extension/` | VS Code extension with LSP client |
| `docs/` | MkDocs Material documentation site |
| `examples/` | Example programs and starter templates |

---

## Making Changes

### Branch Naming

```
feature/add-regex-support
fix/windows-path-handling
docs/update-stdlib-reference
ci/add-macos-arm64-runner
refactor/parser-error-recovery
```

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `ci` | CI/CD pipeline changes |
| `refactor` | Code restructuring (no behavior change) |
| `test` | Adding or updating tests |
| `perf` | Performance improvement |
| `chore` | Maintenance tasks |

**Examples:**
```
feat(parser): add pattern matching with guard clauses
fix(web): resolve race condition in ASGI request handler
docs(stdlib): document all crypto functions
ci: add Python 3.13 to test matrix
```

---

## Coding Standards

### Formatting (Ruff)

EPL enforces strict formatting via **Ruff**. Before every commit:

```bash
# Format all Python files
ruff format .

# Lint and auto-fix
ruff check --fix .
```

> **CI will reject PRs that fail Ruff checks.** Configure your editor to format-on-save.

### Code Style Principles

- **Self-documenting code** — Prefer clear variable names over comments
- **No dead code** — Remove unused imports, variables, and functions
- **Type hints** — Use type annotations for all public function signatures
- **Docstrings** — All public modules, classes, and functions require docstrings

---

## Testing Requirements

### Running Tests

```bash
# Full stable test suite
python -m pytest tests/ --tb=short -q

# Specific test file
python -m pytest tests/test_interpreter_comprehensive.py -v

# With coverage
python -m pytest tests/ --cov=epl --cov-report=term-missing
```

### Test Standards

- **New features must include tests** — PRs without tests will be requested to add them
- **Minimum coverage** — Don't decrease overall coverage
- **Cross-platform** — Tests must pass on Ubuntu, macOS, and Windows
- **No flaky tests** — Tests must be deterministic; use `pytest.mark.xfail` for known env-dependent issues

### CI Matrix

Every PR is tested across:

| OS | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
|----|:-----------:|:-----------:|:-----------:|:-----------:|:-----------:|
| Ubuntu | ✅ | ✅ | ✅ | ✅ | ✅ |
| macOS | ✅ | ✅ | ✅ | ✅ | ✅ |
| Windows | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Pull Request Process

### Before Opening a PR

- [ ] Code is formatted with `ruff format .`
- [ ] All lint checks pass: `ruff check .`
- [ ] All tests pass: `python -m pytest tests/ -q`
- [ ] New features have corresponding tests
- [ ] `CHANGELOG.md` is updated under the `[Unreleased]` section

### PR Checklist

When you open your PR, the template will guide you through:

1. **Description** — What does this PR do and why?
2. **Testing** — How was it tested? What's the test output?
3. **Breaking changes** — Does this change any existing behavior?
4. **CLA** — Sign the CLA when the bot prompts you

### Review Process

1. A maintainer will review within **48 hours**
2. Address all review comments
3. Once approved, a maintainer will merge your PR
4. Your contribution will be credited in `CONTRIBUTORS.md`

---

## Documentation

### Updating Docs

Documentation lives in `docs/` and is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To preview locally:

```bash
pip install mkdocs-material
mkdocs serve
```

### Documentation Standards

- Use **clear, concise language** — EPL's audience includes beginners
- Include **runnable code examples** for every feature
- Keep the **language reference** in sync with parser changes
- Add entries to `docs/stdlib-reference.md` for new stdlib functions

---

## Release Process

Releases are managed by the core team. The process:

1. Version bump in `epl/__init__.py`
2. Update `CHANGELOG.md` with release date
3. Create a signed Git tag: `git tag -s v9.4.0`
4. Build and publish to PyPI: `python -m build && twine upload dist/*`
5. Update documentation site

---

<div align="center">

**Questions?** Open a [Discussion](https://github.com/abneeshsingh21/EPL/discussions) or reach out to the maintainers.

**Thank you for helping build the future of English Programming!** 🚀

</div>
