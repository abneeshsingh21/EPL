"""
Unit and Integration Tests for Production-Grade EPL-HIR (SSA Form v2.0)
Tests SSA generation, Dominator Trees, Optimization Passes (CSE, LICM, CFG Simplifier, DCE),
AST lowering coverage, and SSA In-Memory Interpreter execution.
"""

import unittest
from epl.hir import (
    compile_to_hir,
    ASTToHIR,
    HIRVerifier,
    HIRPassManager,
    ConstantFoldingPass,
    CopyPropagationPass,
    CommonSubexpressionEliminationPass,
    LoopInvariantCodeMotionPass,
    CFGSimplifierPass,
    DeadCodeEliminationPass,
    HIRInterpreter,
    HIRFunction,
    BasicBlock,
    HIRBranch,
    HIRJump,
    HIRReturn,
    HIRConstInst,
    HIRAssign,
    HIRBinaryOp,
    HIRConstant,
    SSAVar,
    T_INT,
    T_BOOL,
    T_STRING,
    T_ANY,
)
from epl.lexer import Lexer
from epl.parser import Parser


class TestHIRGeneration(unittest.TestCase):
    """Test lowering from EPL source AST to SSA EPL-HIR."""

    def _parse(self, code: str):
        tokens = Lexer(code).tokenize()
        return Parser(tokens).parse()

    def test_basic_arithmetic_hir(self):
        code = """
        Create num1 = 10
        Create num2 = 20
        Create num3 = num1 + num2
        Print num3
        """
        hir = compile_to_hir(code, module_name="test_math")
        self.assertIn("main", hir.functions)
        main_fn = hir.functions["main"]
        self.assertIn("entry", main_fn.blocks)
        entry = main_fn.blocks["entry"]
        self.assertTrue(entry.is_terminated())
        valid, errors = HIRVerifier.verify(hir)
        self.assertTrue(valid, errors)

    def test_if_else_phi_generation(self):
        code = """
        Create score = 85
        Create grade = "F"
        If score >= 80 then
            Set grade to "A"
        Else
            Set grade to "B"
        End If
        Print grade
        """
        hir = compile_to_hir(code, module_name="test_if")
        main_fn = hir.functions["main"]
        self.assertTrue(len(main_fn.blocks) >= 4)
        valid, errors = HIRVerifier.verify(hir)
        self.assertTrue(valid, errors)

    def test_while_loop_cfg(self):
        code = """
        Create count = 0
        While count < 5
            Print count
            Set count to count + 1
        End While
        """
        hir = compile_to_hir(code, module_name="test_while")
        main_fn = hir.functions["main"]
        block_names = list(main_fn.blocks.keys())
        self.assertTrue(any("while_hdr" in b for b in block_names))
        self.assertTrue(any("while_body" in b for b in block_names))
        self.assertTrue(any("while_exit" in b for b in block_names))
        valid, errors = HIRVerifier.verify(hir)
        self.assertTrue(valid, errors)

    def test_function_def_lowering(self):
        code = """
        Function add_two(x, y)
            Return x + y
        End Function

        Create result = add_two(5, 7)
        Print result
        """
        hir = compile_to_hir(code, module_name="test_func")
        self.assertIn("add_two", hir.functions)
        self.assertIn("main", hir.functions)
        add_fn = hir.functions["add_two"]
        self.assertEqual(len(add_fn.params), 2)
        valid, errors = HIRVerifier.verify(hir)
        self.assertTrue(valid, errors)

    def test_match_case_lowering(self):
        code = """
        Create status_code = 200
        Match status_code
            When 200
                Print "OK"
            When 404
                Print "Not Found"
            Default
                Print "Unknown"
        End
        """
        hir = compile_to_hir(code, module_name="test_match")
        valid, errors = HIRVerifier.verify(hir)
        self.assertTrue(valid, errors)


class TestHIROptimizations(unittest.TestCase):
    """Test SSA optimization passes individually."""

    def _parse(self, code: str):
        tokens = Lexer(code).tokenize()
        return Parser(tokens).parse()

    def test_constant_folding_and_algebraic_identities(self):
        code = """
        Create folded = 100 + 250
        Create alg1 = folded + 0
        Create alg2 = alg1 * 1
        Print alg2
        """
        ast_tree = self._parse(code)
        lowering = ASTToHIR("test_cf")
        hir_mod = lowering.lower(ast_tree)

        cf_pass = ConstantFoldingPass()
        changed = cf_pass.run_on_function(hir_mod.functions["main"])
        self.assertTrue(changed)

        entry_insts = hir_mod.functions["main"].blocks["entry"].instructions
        has_folded_const = any(
            isinstance(inst, HIRConstInst) and inst.constant.value == 350
            for inst in entry_insts
        )
        self.assertTrue(has_folded_const)

    def test_common_subexpression_elimination(self):
        code = """
        Create val1 = 10
        Create val2 = 20
        Create sum1 = val1 + val2
        Create sum2 = val1 + val2
        Print sum1
        Print sum2
        """
        ast_tree = self._parse(code)
        lowering = ASTToHIR("test_cse")
        hir_mod = lowering.lower(ast_tree)

        cse = CommonSubexpressionEliminationPass()
        changed = cse.run_on_function(hir_mod.functions["main"])
        self.assertTrue(changed)

    def test_dead_code_elimination(self):
        code = """
        Create unused_a = 999
        Create unused_b = unused_a * 2
        Create active = 42
        Print active
        """
        ast_tree = self._parse(code)
        lowering = ASTToHIR("test_dce")
        hir_mod = lowering.lower(ast_tree)

        dce_pass = DeadCodeEliminationPass()
        dce_pass.run_on_function(hir_mod.functions["main"])

        entry_insts = hir_mod.functions["main"].blocks["entry"].instructions
        inst_str = str(entry_insts)
        self.assertNotIn("unused_b", inst_str)

    def test_cfg_simplifier_branch_folding(self):
        func = HIRFunction(name="branch_fold", params=[], return_type=T_INT)
        b_entry = BasicBlock("entry")
        b_true = BasicBlock("b_true")
        b_false = BasicBlock("b_false")

        b_entry.set_terminator(HIRBranch(HIRConstant(True, T_BOOL), "b_true", "b_false"))
        b_true.set_terminator(HIRReturn(HIRConstant(1, T_INT)))
        b_false.set_terminator(HIRReturn(HIRConstant(0, T_INT)))

        func.add_block(b_entry)
        func.add_block(b_true)
        func.add_block(b_false)

        simplifier = CFGSimplifierPass()
        changed = simplifier.run_on_function(func)
        self.assertTrue(changed)
        self.assertTrue(isinstance(b_entry.terminator, HIRJump))
        self.assertEqual(b_entry.terminator.target, "b_true")


class TestDominatorAnalysis(unittest.TestCase):
    """Test dominator tree calculation and strict dominance properties."""

    def test_dominator_tree_computation(self):
        func = HIRFunction(name="dom_test", params=[], return_type=T_INT)
        b0 = BasicBlock("entry")
        b1 = BasicBlock("b1")
        b2 = BasicBlock("b2")
        b3 = BasicBlock("b3")

        b0.set_terminator(HIRBranch(HIRConstant(True, T_BOOL), "b1", "b2"))
        b1.set_terminator(HIRJump("b3"))
        b2.set_terminator(HIRJump("b3"))
        b3.set_terminator(HIRReturn(None))

        func.add_block(b0)
        func.add_block(b1)
        func.add_block(b2)
        func.add_block(b3)

        dt = func.compute_dominators()
        self.assertTrue(dt.dominates("entry", "b1"))
        self.assertTrue(dt.dominates("entry", "b2"))
        self.assertTrue(dt.dominates("entry", "b3"))
        self.assertFalse(dt.dominates("b1", "b3"))
        self.assertFalse(dt.dominates("b2", "b3"))


class TestHIRInterpreter(unittest.TestCase):
    """Test SSA in-memory virtual machine interpreter."""

    def test_execute_arithmetic_hir(self):
        code = """
        Create num1 = 15
        Create num2 = 25
        Create result = num1 + num2
        Print result
        """
        hir = compile_to_hir(code, module_name="test_interp")
        interp = HIRInterpreter(hir)
        interp.execute_function("main", [])
        self.assertIn("40", interp.stdout)

    def test_execute_function_call_hir(self):
        code = """
        Function multiply(val_a, val_b)
            Return val_a * val_b
        End Function

        Create res = multiply(6, 7)
        Print res
        """
        hir = compile_to_hir(code, module_name="test_interp_call")
        interp = HIRInterpreter(hir)
        interp.execute_function("main", [])
        self.assertIn("42", interp.stdout)

    def test_execute_while_loop_hir(self):
        code = """
        Create sum_val = 0
        Create idx = 1
        While idx <= 5
            Set sum_val to sum_val + idx
            Set idx to idx + 1
        End While
        Print sum_val
        """
        tokens = Lexer(code).tokenize()
        ast_tree = Parser(tokens).parse()
        lowering = ASTToHIR("test_interp_while")
        hir = lowering.lower(ast_tree)
        interp = HIRInterpreter(hir)
        interp.execute_function("main", [])
        self.assertIn("15", interp.stdout)


    def test_copy_propagation_pass(self):
        func = HIRFunction(name="copy_prop", params=[], return_type=T_INT)
        b0 = BasicBlock("entry")
        v1 = SSAVar("x", 1, T_INT)
        v2 = SSAVar("y", 1, T_INT)
        v3 = SSAVar("z", 1, T_INT)

        b0.add_instruction(HIRConstInst(v1, HIRConstant(10, T_INT)))
        b0.add_instruction(HIRAssign(v2, v1))  # y = x
        b0.add_instruction(HIRBinaryOp(v3, "+", v2, HIRConstant(5, T_INT)))  # z = y + 5 -> z = x + 5
        b0.set_terminator(HIRReturn(v3))
        func.add_block(b0)

        cp = CopyPropagationPass()
        changed = cp.run_on_function(func)
        self.assertTrue(changed)
        # Check that v3 uses v1 instead of v2
        bin_inst = b0.instructions[2]
        self.assertEqual(bin_inst.left, v1)

    def test_export_dot_format(self):
        code = """
        Create score = 90
        If score > 50 then
            Print "Pass"
        Else
            Print "Fail"
        End If
        """
        hir = compile_to_hir(code, module_name="test_dot")
        dot_str = hir.export_dot()
        self.assertIn("digraph HIR", dot_str)
        self.assertIn("cluster_main", dot_str)
        self.assertIn("entry", dot_str)

    def test_break_and_continue_loop_lowering(self):
        code = """
        Create i = 0
        While i < 10
            Set i to i + 1
            If i == 5 then
                Break
            End If
        End While
        Print i
        """
        tokens = Lexer(code).tokenize()
        ast_tree = Parser(tokens).parse()
        lowering = ASTToHIR("test_break")
        hir = lowering.lower(ast_tree)
        valid, errors = HIRVerifier.verify(hir)
        self.assertTrue(valid, errors)

        interp = HIRInterpreter(hir)
        interp.execute_function("main", [])
        self.assertIn("5", interp.stdout)


if __name__ == "__main__":
    unittest.main()
