# Contributing to EPL

Thank you for your interest in contributing to EPL! This guide will help you get started.

## Getting Started

### Prerequisites

- Python 3.11+
- Git

### Setup

```bash
git clone https://github.com/your-org/epl.git
cd epl
pip install -r requirements.txt
```

### Running Tests

```bash
# Core regression tests (271 tests)
python -m pytest tests/test_epl.py -v

# v4 feature tests (44 tests)
python tests/run_tests.py

# LLVM compiler tests (26 tests)
python -m pytest tests/test_llvm.py -v

# Kotlin transpiler tests (30 tests)
python -m pytest tests/test_kotlin.py -v

# Bytecode VM tests (43 tests)
python -m pytest tests/test_vm.py -v

# Package manager tests (91 tests)
python -m pytest tests/test_package_manager.py -v

# Stability tests (42 tests)
python -m pytest tests/test_stability.py -v

# Run everything
python -m pytest tests/ -v && python tests/run_tests.py
```

All 547+ tests must pass before submitting a PR.

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Include:
   - EPL version (`python main.py --version`)
   - Python version
   - OS
   - Minimal `.epl` file that reproduces the bug
   - Expected vs actual behavior
   - Full error traceback

### Suggesting Features

Open an issue with:
- A clear description of the feature
- Example EPL code showing the proposed syntax
- Rationale — why this improves the language

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for any new functionality
5. Ensure all tests pass
6. Submit a pull request

## Code Guidelines

### Project Structure

- `epl/` — All EPL modules (lexer, parser, interpreter, compiler, etc.)
- `tests/` — Test suites (pytest-based)
- `examples/` — Example EPL programs
- `docs/` — Documentation

### Style

- Follow existing code style in each file
- Use type hints for function signatures
- Keep functions focused — one responsibility per function
- Use descriptive variable names

### Commit Messages

Use clear, descriptive commit messages:

```
Add support for pattern matching in VM backend

- Implement MATCH/WHEN opcodes in bytecode compiler
- Add VM dispatch for match/case evaluation
- Add 5 tests for pattern matching
```

### Testing Requirements

- Every new feature must have tests
- Bug fixes should include a regression test
- Tests go in the appropriate suite:
  - Interpreter features → `tests/test_epl.py`
  - VM features → `tests/test_vm.py`
  - Compiler features → `tests/test_llvm.py`
  - Package manager → `tests/test_package_manager.py`
  - Edge cases / stability → `tests/test_stability.py`

### Adding a New Built-in Function

1. Add the implementation in `epl/interpreter.py` inside `_call_builtin()`
2. Add VM support in `epl/vm.py` inside `_exec_call_builtin()`
3. Add compiler support in `epl/compiler.py` if applicable
4. Add stdlib documentation in `epl/stdlib.py`
5. Add tests in the appropriate test file
6. Update `docs/language-reference.md`

### Adding a New AST Node

1. Define the node class in `epl/ast_nodes.py`
2. Add parsing in `epl/parser.py`
3. Add interpretation in `epl/interpreter.py`
4. Add VM compilation in `epl/vm.py` (BytecodeCompiler + VM)
5. Add Kotlin transpilation in `epl/kotlin_gen.py` if needed
6. Add LLVM compilation in `epl/compiler.py` if needed
7. Add tests covering the new syntax

## Architecture Overview

See [docs/architecture.md](docs/architecture.md) for the full technical overview.

The core pipeline: **Source → Lexer → Parser → AST → Backend**

Backends:
- **Interpreter** — Tree-walking, full feature support
- **VM** — Bytecode compilation + stack-based execution (10-50x faster)
- **LLVM Compiler** — Native executables
- **Kotlin Transpiler** — Android apps via Jetpack Compose

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
