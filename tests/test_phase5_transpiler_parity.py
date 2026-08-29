"""Tests for Phase 5 (Deep): HIR-Based Transpilation & Semantic Parity."""

import pytest
from epl.ast_nodes import Program, Literal, BinaryOp, Identifier, VarDeclaration, VarAssignment
from epl.hir import HIREngine
from epl.hir_transpiler import HIRToPython, HIRToJavaScript, HIRToKotlin, HIRTranspilerManager
from epl.semantic_parity import (
    UnicodeParity,
    IntegerParity,
    ClosureParity,
    SemanticParitySuite,
    ClosureCell,
)


class TestSemanticParity:
    """Test suite for cross-platform semantic parity."""

    def test_unicode_scalar_indexing_and_slicing(self):
        # Emoji and multi-byte unicode characters: "A", "👋", "🚀", "Z"
        text = "A👋🚀Z"
        scalars = UnicodeParity.unicode_scalars(text)
        assert len(scalars) == 4
        assert scalars[0] == "A"
        assert scalars[1] == "👋"
        assert scalars[2] == "🚀"
        assert scalars[3] == "Z"

        assert UnicodeParity.scalar_slice(text, 1, 3) == "👋🚀"
        assert UnicodeParity.scalar_slice(text, 0, 2) == "A👋"
        assert UnicodeParity.scalar_slice(text, 2, None) == "🚀Z"

    def test_unicode_boundary_validation(self):
        valid_utf8 = "Hello 🌍!".encode("utf-8")
        assert UnicodeParity.validate_utf8_boundaries(valid_utf8) is True

    def test_integer_64bit_overflow_normalization(self):
        max_int64 = 9223372036854775808 - 1
        overflowed = IntegerParity.normalize_int64(max_int64 + 1, signed=True)
        assert overflowed == -9223372036854775808

        max_uint64 = 18446744073709551615
        overflowed_u = IntegerParity.normalize_int64(max_uint64 + 1, signed=False)
        assert overflowed_u == 0

    def test_integer_arithmetic_overflow_checked(self):
        max_int64 = 9223372036854775807
        result, did_overflow = IntegerParity.checked_add(max_int64, 1)
        assert did_overflow is True
        assert result == -9223372036854775808

        result, did_overflow = IntegerParity.checked_mul(max_int64, 2)
        assert did_overflow is True

    def test_bigint_emulation(self):
        huge = 10**30
        res = IntegerParity.bigint_op(huge, huge, "+")
        assert res == 2 * 10**30

    def test_closure_loop_variable_capture(self):
        captured_funcs = []
        for i in range(5):
            cell = ClosureParity.create_binding_cell(i)
            captured_funcs.append(lambda c=cell: c.get())

        results = [fn() for fn in captured_funcs]
        assert results == [0, 1, 2, 3, 4]

    def test_closure_cell_mutation(self):
        cell = ClosureCell(10)
        assert cell.get() == 10
        cell.set(20)
        assert cell.get() == 20

    def test_semantic_parity_suite_run(self):
        suite = SemanticParitySuite()
        res = suite.run_all()
        assert res["unicode_parity"] is True
        assert res["integer_parity"] is True
        assert res["closure_parity"] is True


class TestHIRTranspiler:
    """Test suite for direct SSA CFG lowering backends."""

    def test_hir_to_python_lowering(self):
        ast_prog = Program(
            statements=[
                VarDeclaration(
                    name="x",
                    value=BinaryOp(Literal(10), "+", Literal(20)),
                )
            ]
        )
        hir_engine = HIREngine()
        hir_mod = hir_engine.lower_ast(ast_prog)

        transpiler = HIRToPython(hir_mod)
        py_code = transpiler.transpile()
        assert "def main():" in py_code
        assert "_v" in py_code or "_x" in py_code
        assert "+" in py_code

    def test_hir_to_javascript_lowering(self):
        ast_prog = Program(
            statements=[
                VarDeclaration(
                    name="val",
                    value=BinaryOp(Literal(5), "*", Literal(6)),
                )
            ]
        )
        hir_engine = HIREngine()
        hir_mod = hir_engine.lower_ast(ast_prog)

        transpiler = HIRToJavaScript(hir_mod)
        js_code = transpiler.transpile()
        assert "function main()" in js_code
        assert "_val" in js_code or "_block" in js_code

    def test_hir_to_kotlin_lowering(self):
        ast_prog = Program(
            statements=[
                VarDeclaration(
                    name="k",
                    value=BinaryOp(Literal(100), "-", Literal(50)),
                )
            ]
        )
        hir_engine = HIREngine()
        hir_mod = hir_engine.lower_ast(ast_prog)

        transpiler = HIRToKotlin(hir_mod)
        kt_code = transpiler.transpile()
        assert "fun main()" in kt_code
        assert "package me.eplang.generated" in kt_code

    def test_hir_transpiler_manager_all_targets(self):
        ast_prog = Program(
            statements=[
                VarDeclaration(
                    name="total",
                    value=BinaryOp(Literal(1), "+", Literal(2)),
                )
            ]
        )
        manager = HIRTranspilerManager()
        results = manager.transpile_all(ast_prog)

        assert "python" in results
        assert "javascript" in results
        assert "kotlin" in results
        assert len(results["python"]) > 0
        assert len(results["javascript"]) > 0
        assert len(results["kotlin"]) > 0
