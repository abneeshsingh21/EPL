"""Regression tests for the ``python_call`` builtin and Python-result conversion.

Covers two fixes that revived the official Python-backed packages (epl-array,
epl-math, epl-stats, ...), which all reach their backends through
``python_call(module, function, *args)``:

1. ``python_call`` is a callable builtin in the interpreter (previously the
   ``_python_call`` machinery existed but no name was bound to it, so every
   package call raised "not defined"). It is blocked under ``--sandbox`` and
   the bytecode VM refuses it at compile time so ``epl run`` falls back to the
   interpreter cleanly instead of silently returning null.
2. ``wrap_python_result`` converts NumPy-style scalars/arrays to native EPL
   numbers/lists instead of opaque ``<python module int64>`` wrappers.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.interpreter import EPLDict, Interpreter
from epl.lexer import Lexer
from epl.parser import Parser
from epl.python_bridge import PythonModule, wrap_python_result


def _run(source: str, **kwargs):
    interp = Interpreter(**kwargs)
    program = Parser(Lexer(source).tokenize()).parse()
    interp.execute(program)
    return interp.output_lines


class _FakeNumpyScalar:
    """Duck-typed stand-in for a NumPy 0-d scalar (np.int64), no numpy needed."""

    def __init__(self, value):
        self._value = value
        self.dtype = 'int64'
        self.ndim = 0
        self.shape = ()

    def item(self):
        return self._value

    def tolist(self):  # numpy scalars expose this too
        return self._value


class _FakeNumpyArray:
    """Duck-typed stand-in for an N-d NumPy array."""

    def __init__(self, data):
        self._data = data
        self.dtype = 'float64'
        self.ndim = 1
        self.shape = (len(data),)

    def __iter__(self):
        # An array is iterable — the wrapper must prefer tolist() over this.
        return iter(self._data)

    def tolist(self):
        return list(self._data)


class PythonCallBuiltinTests(unittest.TestCase):
    def test_python_call_is_callable(self):
        """python_call reaches a stdlib backend and returns a native value."""
        out = _run('Create r equal to python_call("math", "sqrt", 16)\nSay r\n')
        self.assertEqual(out[-1], '4.0')

    def test_python_call_blocked_in_safe_mode(self):
        """Under --sandbox, python_call is refused (it executes Python)."""
        with self.assertRaises(Exception) as ctx:
            _run('Create r equal to python_call("math", "sqrt", 16)\n', safe_mode=True)
        self.assertIn('safe mode', str(ctx.exception).lower())

    def test_python_call_requires_module_and_function(self):
        """A bare python_call with too few args is a clear error, not a crash."""
        with self.assertRaises(Exception) as ctx:
            _run('Create r equal to python_call("math")\n')
        self.assertIn('module', str(ctx.exception).lower())

    def test_vm_refuses_python_call(self):
        """The bytecode VM rejects python_call so epl run falls back to interp."""
        from epl.vm import VMError, compile_to_bytecode

        with self.assertRaises(VMError):
            compile_to_bytecode('Create r equal to python_call("math", "sqrt", 16)\n')


class PythonResultConversionTests(unittest.TestCase):
    def test_numpy_scalar_unwraps_to_native(self):
        result = wrap_python_result(
            _FakeNumpyScalar(15), epl_dict_type=EPLDict, python_module_type=PythonModule
        )
        self.assertEqual(result, 15)
        self.assertNotIsInstance(result, PythonModule)

    def test_numpy_array_unwraps_to_native_list(self):
        result = wrap_python_result(
            _FakeNumpyArray([1.0, 2.0, 3.0]),
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )
        self.assertEqual(result, [1.0, 2.0, 3.0])
        self.assertTrue(all(not isinstance(x, PythonModule) for x in result))

    def test_nested_array_of_scalars_unwraps(self):
        """A list carrying numpy scalars (the element-wise path) stays native."""
        result = wrap_python_result(
            [_FakeNumpyScalar(1), _FakeNumpyScalar(2)],
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )
        self.assertEqual(result, [1, 2])

    def test_plain_values_unchanged(self):
        for value in (None, True, 3, 4.5, 'hi'):
            self.assertEqual(
                wrap_python_result(value, epl_dict_type=EPLDict, python_module_type=PythonModule),
                value,
            )


if __name__ == '__main__':
    unittest.main()
