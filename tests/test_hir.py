"""
Unit and Integration Tests for EPL High-Level Intermediate Representation (EPL-HIR)
Tests SSA generation, basic block CFG construction, optimization passes, and verification.
"""

import unittest
from epl.hir import (
    compile_to_hir,
    ASTToHIR,
    HIRVerifier,
    HIRPassManager,
    ConstantFoldingPass,
    DeadCodeEliminationPass,
    HIRFunction,
    BasicBlock,
    HIRBranch,
    HIRJump,
    HIRReturn,
    HIRConstInst,
    HIRConstant,
    SSAVar,
    T_INT,
    T_BOOL,
    T_STRING,
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
        # Must have entry, if_then, if_else, if_merge blocks
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

    def test_constant_folding_pass(self):
        code = """
        Create total = 100 + 250
        Print total
        """
        ast_tree = self._parse(code)
        lowering = ASTToHIR("test_cf")
        hir_mod = lowering.lower(ast_tree)

        cf_pass = ConstantFoldingPass()
        changed = cf_pass.run_on_function(hir_mod.functions["main"])
        self.assertTrue(changed)

        # Verify that total is folded directly to constant 350
        entry_insts = hir_mod.functions["main"].blocks["entry"].instructions
        has_folded_const = any(
            isinstance(inst, HIRConstInst) and inst.constant.value == 350
            for inst in entry_insts
        )
        self.assertTrue(has_folded_const)

    def test_dead_code_elimination_pass(self):
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

        # unused_b computation must be eliminated
        entry_insts = hir_mod.functions["main"].blocks["entry"].instructions
        inst_str = str(entry_insts)
        self.assertNotIn("unused_b", inst_str)

    def test_hir_verifier_catches_unterminated_block(self):
        func = HIRFunction(name="broken", params=[], return_type=T_INT)
        b = BasicBlock("entry")
        # Do not set terminator
        func.add_block(b)
        from epl.hir import HIRModule
        mod = HIRModule(name="bad_mod", functions={"broken": func})
        valid, errors = HIRVerifier.verify(mod)
        self.assertFalse(valid)
        self.assertTrue(any("lacks a terminator" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
