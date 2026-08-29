"""
Unit and Integration Tests for Phase 4: NaN-Boxed Value Engine,
Inline Caching (MIC / PIC), and Ahead-of-Time Bytecode Verifier.
"""

import unittest
from epl.nanbox import NaNBoxEngine, ValueType, val_encode, val_decode
from epl.inline_cache import MethodCallSite, PropertyAccessSite, CacheState
from epl.bytecode_verifier import BytecodeVerifier
from epl.vm import Instruction, Op, compile_to_bytecode


class TestNaNBoxEngine(unittest.TestCase):
    """Test 64-bit IEEE 754 NaN-boxing encoding and decoding."""

    def setUp(self):
        self.engine = NaNBoxEngine()

    def test_integer_roundtrip(self):
        test_ints = [0, 1, -1, 42, -100, 2147483647, -2147483648]
        for val in test_ints:
            word = self.engine.encode_int(val)
            self.assertTrue(self.engine.is_int(word))
            self.assertEqual(self.engine.get_type(word), ValueType.INT)
            self.assertEqual(self.engine.decode_int(word), val)
            self.assertEqual(self.engine.decode(word), val)

    def test_float_roundtrip(self):
        test_floats = [0.0, -0.0, 3.1415926535, -273.15, 1e15, 2.71828]
        for val in test_floats:
            word = self.engine.encode_float(val)
            self.assertTrue(self.engine.is_float(word))
            self.assertEqual(self.engine.get_type(word), ValueType.FLOAT)
            self.assertAlmostEqual(self.engine.decode_float(word), val, places=7)

    def test_boolean_roundtrip(self):
        true_w = self.engine.encode_bool(True)
        false_w = self.engine.encode_bool(False)

        self.assertTrue(self.engine.is_bool(true_w))
        self.assertTrue(self.engine.is_bool(false_w))
        self.assertEqual(self.engine.decode_bool(true_w), True)
        self.assertEqual(self.engine.decode_bool(false_w), False)

    def test_none_roundtrip(self):
        none_w = self.engine.encode_none()
        self.assertTrue(self.engine.is_none(none_w))
        self.assertIsNone(self.engine.decode(none_w))

    def test_heap_references(self):
        s = "Hello EPL NaN-Box"
        s_w = self.engine.encode(s)
        self.assertTrue(self.engine.is_string(s_w))
        self.assertEqual(self.engine.decode(s_w), s)

        lst = [10, 20, 30]
        l_w = self.engine.encode(lst)
        self.assertTrue(self.engine.is_list(l_w))
        self.assertEqual(self.engine.decode(l_w), lst)

        mp = {"status": "ok", "code": 200}
        m_w = self.engine.encode(mp)
        self.assertTrue(self.engine.is_map(m_w))
        self.assertEqual(self.engine.decode(m_w), mp)


class TestInlineCaching(unittest.TestCase):
    """Test Monomorphic, Polymorphic, and Megamorphic Inline Caching."""

    class Alpha:
        def compute(self, x):
            return x * 2

    class Beta:
        def compute(self, x):
            return x * 3

    class Gamma:
        def compute(self, x):
            return x * 4

    def test_method_call_site_lifecycle(self):
        site = MethodCallSite("compute")
        self.assertEqual(site.state, CacheState.UNINITIALIZED)

        def fallback(rec, mname):
            return getattr(rec, mname)

        a = self.Alpha()
        res1 = site.resolve_and_call(a, [10], fallback)
        self.assertEqual(res1, 20)
        self.assertEqual(site.state, CacheState.MONOMORPHIC)
        self.assertEqual(site.hit_count, 1)

        # Monomorphic hit
        res2 = site.resolve_and_call(a, [5], fallback)
        self.assertEqual(res2, 10)
        self.assertEqual(site.state, CacheState.MONOMORPHIC)
        self.assertEqual(site.hit_count, 2)

        # Transition to Polymorphic
        b = self.Beta()
        res3 = site.resolve_and_call(b, [10], fallback)
        self.assertEqual(res3, 30)
        self.assertEqual(site.state, CacheState.POLYMORPHIC)

        # Polymorphic hit on Alpha
        res4 = site.resolve_and_call(a, [2], fallback)
        self.assertEqual(res4, 4)
        self.assertEqual(site.hit_count, 3)

    def test_property_access_site(self):
        site = PropertyAccessSite("name")
        self.assertEqual(site.state, CacheState.UNINITIALIZED)

        class Item:
            def __init__(self, name):
                self.name = name

        def fallback(rec, prop):
            return getattr(rec, prop)

        it1 = Item("First")
        self.assertEqual(site.get_property(it1, fallback), "First")
        self.assertEqual(site.state, CacheState.MONOMORPHIC)

        it2 = Item("Second")
        self.assertEqual(site.get_property(it2, fallback), "Second")
        self.assertEqual(site.hit_count, 2)


class TestBytecodeVerifier(unittest.TestCase):
    """Test AOT Bytecode Safety and Abstract Interpretation Verifier."""

    def test_valid_program_bytecode(self):
        code = """
        Create num1 = 5
        Create num2 = 10
        Create total = num1 + num2
        If total > 10 then
            Print "Greater"
        Else
            Print "Smaller"
        End If
        """
        compiled = compile_to_bytecode(code)
        valid, errors = BytecodeVerifier.verify(compiled)
        self.assertTrue(valid, errors)

    def test_stack_underflow_detection(self):
        bad_bytecode = [
            Instruction(Op.ADD, None, 1),  # Stack is empty, requires 2
            Instruction(Op.HALT, None, 2),
        ]
        compiled = {"code": bad_bytecode, "constants": [], "functions": {}}
        valid, errors = BytecodeVerifier.verify(compiled)
        self.assertFalse(valid)
        self.assertTrue(any("Stack underflow" in e for e in errors))

    def test_constant_out_of_bounds_detection(self):
        bad_bytecode = [
            Instruction(Op.LOAD_CONST, 999, 1),  # Index 999 does not exist
            Instruction(Op.HALT, None, 2),
        ]
        compiled = {"code": bad_bytecode, "constants": ["only_one"], "functions": {}}
        valid, errors = BytecodeVerifier.verify(compiled)
        self.assertFalse(valid)
        self.assertTrue(any("Constant index out of bounds" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
