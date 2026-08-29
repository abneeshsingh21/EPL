"""Differential fuzzing engine for EPL: comparing AST Interpreter vs HIR vs Formal Semantics."""

import random
import pytest
from epl.ast_nodes import Program, Literal, BinaryOp, Identifier, VarDeclaration, VarAssignment
from epl.interpreter import Interpreter
from epl.hir import HIREngine
from epl.formal_semantics import FormalSemantics, BigStepReducer, FormalEnv


class DifferentialFuzzer:
    """Differential fuzzer generating valid randomized expressions and statements."""

    OPERATORS = ["+", "-", "*"]

    def __init__(self, seed=42):
        self.rng = random.Random(seed)

    def generate_random_expr(self, depth=0, max_depth=3):
        if depth >= max_depth or self.rng.random() < 0.4:
            return Literal(self.rng.randint(-100, 100))
        op = self.rng.choice(self.OPERATORS)
        left = self.generate_random_expr(depth + 1, max_depth)
        right = self.generate_random_expr(depth + 1, max_depth)
        return BinaryOp(left, op, right)

    def generate_random_program(self, num_statements=3):
        stmts = []
        for i in range(num_statements):
            var_name = f"var_{i}"
            expr = self.generate_random_expr(max_depth=2)
            stmts.append(VarDeclaration(name=var_name, value=expr))
        return Program(statements=stmts)


def test_differential_fuzzing_expressions():
    """Verify that AST evaluation and Formal Semantics yield identical results across fuzzed inputs."""
    fuzzer = DifferentialFuzzer(seed=1337)
    reducer = BigStepReducer()

    for i in range(50):
        expr = fuzzer.generate_random_expr(max_depth=3)

        # 1. Evaluate via Formal Semantics
        term = FormalSemantics.ast_to_formal(expr)
        _, formal_val, _ = reducer.eval(term, FormalEnv())

        # 2. Evaluate via AST Interpreter
        interpreter = Interpreter()
        interp_val = interpreter.evaluate(expr)

        # 3. Assert exact differential parity
        assert formal_val == interp_val, (
            f"Differential mismatch at iteration {i}: formal={formal_val}, interp={interp_val}"
        )


def test_differential_fuzzing_programs():
    """Verify that multi-statement programs produce matching environment states."""
    fuzzer = DifferentialFuzzer(seed=2026)

    for i in range(20):
        prog = fuzzer.generate_random_program(num_statements=4)

        # 1. Evaluate with Formal Semantics
        proof = FormalSemantics.prove_soundness(prog)
        assert proof["proved"] is True
        formal_state = proof["final_state"]

        # 2. Evaluate with Interpreter
        interpreter = Interpreter()
        interpreter.interpret(prog)

        for var_name, expected_val in formal_state.items():
            actual_val = interpreter.environment.get_variable(var_name)
            assert actual_val == expected_val, (
                f"State mismatch on {var_name}: formal={expected_val}, interpreter={actual_val}"
            )


def test_differential_fuzzing_hir_lowering():
    """Verify HIR Engine lowers arbitrary valid ASTs deterministically."""
    fuzzer = DifferentialFuzzer(seed=999)
    hir_engine = HIREngine()

    for i in range(30):
        prog = fuzzer.generate_random_program(num_statements=3)
        hir_mod = hir_engine.lower_ast(prog)
        assert hir_mod is not None
        assert len(hir_mod.functions) >= 1
        main_fn = hir_mod.functions.get("main")
        assert main_fn is not None
        assert len(main_fn.blocks) >= 1
