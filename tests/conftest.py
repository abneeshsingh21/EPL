"""Pytest configuration for mixed test styles in the EPL repository.

The repo currently contains both pytest/unittest suites and older script-style
regression runners that execute at import time. Pytest should collect only the
declaration-style modules and leave the script runners to the direct `python
tests/...` invocations used by CI.
"""

from __future__ import annotations

import ast
from pathlib import Path


_DECLARATIVE_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)


def _is_docstring(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_constant_assignment(node: ast.AST) -> bool:
    """Allow simple module-level constants such as ROOT or REPO_ROOT."""
    if not isinstance(node, ast.Assign) or not node.targets:
        return False
    for target in node.targets:
        if not isinstance(target, ast.Name) or not target.id.isupper():
            return False
    return True


def _is_pytest_control_assignment(node: ast.AST) -> bool:
    """Allow pytest collection hints such as helper.__test__ = False."""
    if not isinstance(node, ast.Assign) or not node.targets:
        return False
    for target in node.targets:
        if not (
            isinstance(target, ast.Attribute)
            and target.attr == "__test__"
            and isinstance(target.value, ast.Name)
        ):
            return False
    return True


def _is_pytest_metadata_assignment(node: ast.AST) -> bool:
    """Allow common pytest module metadata such as `pytestmark = ...`."""
    if not isinstance(node, ast.Assign) or not node.targets:
        return False
    for target in node.targets:
        if not isinstance(target, ast.Name) or target.id not in {"pytestmark"}:
            return False
    return True


def _is_script_style_test(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        return False

    if _has_legacy_test_helpers(tree):
        return True

    for node in tree.body:
        if (
            _is_docstring(node)
            or isinstance(node, _DECLARATIVE_NODES)
            or _is_path_bootstrap(node)
            or _is_constant_assignment(node)
            or _is_pytest_control_assignment(node)
            or _is_pytest_metadata_assignment(node)
            or _is_main_guard(node)
        ):
            continue
        return True
    return False


def _is_path_bootstrap(node: ast.AST) -> bool:
    """Allow the common test bootstrap call: sys.path.insert(...)."""
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "insert"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "path"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "sys"
    )


def _has_legacy_test_helpers(tree: ast.Module) -> bool:
    """Detect old direct-run harnesses that should not be imported by pytest."""
    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    legacy_helpers = {"test", "test_error", "test_no_error", "test_parse", "test_ast_node"}
    legacy_entrypoints = {"main", "run_tests"}
    return bool(function_names & legacy_entrypoints) and bool(function_names & legacy_helpers)


def _is_main_guard(node: ast.AST) -> bool:
    """Allow `if __name__ == "__main__": ...` blocks in declarative test modules."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def pytest_ignore_collect(collection_path, config):
    path = Path(str(collection_path))
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return False
    return _is_script_style_test(path)
