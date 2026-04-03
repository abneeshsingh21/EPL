"""Pytest coverage for the EPL LLVM compiler IR generation."""

from __future__ import annotations

import importlib.util

import pytest


HAS_LLVM = importlib.util.find_spec("llvmlite") is not None
pytestmark = pytest.mark.skipif(not HAS_LLVM, reason="llvmlite is not installed")


def compile_to_ir(src: str) -> str:
    from epl.compiler import Compiler
    from epl.lexer import Lexer
    from epl.parser import Parser

    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse()
    compiler = Compiler()
    compiler.compile(program)
    return str(compiler.module)


def test_compiler_basic_ir_and_prints():
    ir = compile_to_ir("Print 42")
    assert len(ir) > 0
    assert 'define i32 @"main"()' in ir
    assert "printf" in ir
    assert "Hello" in compile_to_ir('Print "Hello"')
    assert "printf" in compile_to_ir("Print 3.14")


def test_compiler_variables_and_arithmetic():
    assert "alloca i64" in compile_to_ir("x = 42\nPrint x")
    assert "alloca i8*" in compile_to_ir('name = "Alice"\nPrint name')
    assert "store" in compile_to_ir("x = 1\nSet x to 2")
    assert "double" in compile_to_ir("pi = 3.14")

    assert "add" in compile_to_ir("Print 3 + 4")
    assert "sub" in compile_to_ir("Print 10 - 5")
    assert "mul" in compile_to_ir("Print 6 * 7")
    assert "sdiv" in compile_to_ir("Print 10 / 2")
    assert "srem" in compile_to_ir("Print 10 % 3")
    assert "epl_power" in compile_to_ir("Print 2 ** 3")
    assert "epl_floor" in compile_to_ir("Print 7 // 2")


def test_compiler_comparisons_conditionals_and_loops():
    assert "icmp sgt" in compile_to_ir("Print 5 > 3")
    assert "icmp slt" in compile_to_ir("Print 3 < 5")
    assert "icmp eq" in compile_to_ir("Print 5 == 5")
    assert "icmp ne" in compile_to_ir("Print 5 != 3")

    assert "br i1" in compile_to_ir('If 5 > 3 then\n  Print "yes"\nEnd')
    assert compile_to_ir('If 1 > 2 then\n  Print "a"\nOtherwise\n  Print "b"\nEnd').count("br ") >= 2
    assert "br i1" in compile_to_ir("x = 0\nWhile x < 5\n  Print x\n  x += 1\nEnd")
    assert "br i1" in compile_to_ir('Repeat 3 times\n  Print "hi"\nEnd')
    assert "br i1" in compile_to_ir("For i from 1 to 5\n  Print i\nEnd")
    assert "epl_list_new" in compile_to_ir("items = [1, 2, 3]\nFor each x in items\n  Print x\nEnd")


def test_compiler_functions_strings_and_lists():
    assert "define" in compile_to_ir('Function greet\n  Print "hi"\nEnd')
    assert "epl_add" in compile_to_ir("Function add takes a and b\n  Return a + b\nEnd")
    assert "call" in compile_to_ir('Function greet\n  Print "hi"\nEnd\nCall greet')

    assert "strcat" in compile_to_ir('Print "Hello" + " World"')
    assert "epl_string_upper" in compile_to_ir('x = "hello"\nPrint x.upper()')
    assert "epl_string_lower" in compile_to_ir('x = "HELLO"\nPrint x.lower()')
    assert "epl_string_trim" in compile_to_ir('x = "  hi  "\nPrint x.trim()')

    assert "epl_list_new" in compile_to_ir("items = [1, 2, 3]")
    assert "epl_list_push" in compile_to_ir("items = [1, 2]\nitems.add(3)")
    assert "epl_list_length" in compile_to_ir("items = [1, 2]\nPrint length(items)")


def test_compiler_builtins_and_core_language_features():
    assert "epl_sqrt" in compile_to_ir("Print sqrt(16)")
    assert "epl_floor" in compile_to_ir("Print floor(3.7)")
    assert "epl_ceil" in compile_to_ir("Print ceil(3.2)")
    assert compile_to_ir("Print absolute(-5)")
    assert compile_to_ir("Enum Color as RED, GREEN, BLUE")

    ir = compile_to_ir('Try\n  Print 42\nCatch e\n  Print "error"\nEnd')
    assert "try" in ir.lower()
    assert "catch" in ir.lower()
    assert "try_end" in ir.lower()

    assert "exit" in compile_to_ir('Throw "oops"')
    assert compile_to_ir('x = 2\nMatch x\n  When 1\n    Print "one"\n  When 2\n    Print "two"\nEnd')
    ternary_ir = compile_to_ir("x = 10\ny = 1 if x > 5 otherwise 0\nPrint y")
    assert "select" in ternary_ir or "phi" in ternary_ir
    assert compile_to_ir("double = lambda x -> x * 2")
    assert "epl_list_slice" in compile_to_ir("items = [1, 2, 3, 4, 5]\ny = items[1:3]")
    assert compile_to_ir('Write "hello" to file "test.txt"')


def test_compiler_classes_modules_and_advanced_methods():
    assert "epl_object_new" in compile_to_ir(
        'Class Animal\n  name = "unknown"\n  Function speak\n    Print "..."\n  End\nEnd\na = new Animal()'
    )
    assert "call" in compile_to_ir('Class Dog\n  Function bark\n    Print "woof"\n  End\nEnd\nd = new Dog()\nd.bark()')
    assert compile_to_ir(
        'Class Animal\n  name = "a"\n  Function speak\n    Print "..."\n  End\nEnd\n'
        'Class Dog extends Animal\n  Function speak\n    Print "woof"\n  End\nEnd\nd = new Dog()'
    )
    assert "epl_object_set" in compile_to_ir('Class Box\n  value = 0\nEnd\nb = new Box()\nb.value = 42')
    assert "epl_object_get" in compile_to_ir('Class Box\n  value = 0\nEnd\nb = new Box()\nPrint b.value')
    assert "epl_map_new" in compile_to_ir("d = Map with a = 1 and b = 2")
    assert "epl_Math_square" in compile_to_ir(
        "Module Math\n  Function square takes x\n    Return x * x\n  End\nEnd\nPrint Math::square(5)"
    )
    assert "epl_string_index" in compile_to_ir('s = "abc"\nFor each ch in s\n  Print ch\nEnd')
    assert "epl_fetch" in compile_to_ir("Async Function fetch_data\n  Return 42\nEnd\nPrint fetch_data()")
    assert "epl_string_contains" in compile_to_ir('s = "hello world"\nPrint s.contains("world")')
    assert "epl_string_replace" in compile_to_ir('s = "hello"\nPrint s.replace("he", "HE")')
    assert "epl_string_starts_with" in compile_to_ir('s = "hello"\nPrint s.starts_with("he")')
    assert "epl_string_ends_with" in compile_to_ir('s = "hello"\nPrint s.ends_with("lo")')
    assert "epl_string_reverse" in compile_to_ir('s = "hello"\nPrint s.reverse()')
    assert "epl_string_split" in compile_to_ir('s = "a,b,c"\nPrint s.split(",")')
    assert "epl_string_substring" in compile_to_ir('s = "hello"\nPrint s.substring(0, 3)')
    assert "epl_string_length" in compile_to_ir('s = "hello"\nPrint s.length()')
    assert "epl_list_remove" in compile_to_ir("items = [1, 2, 3]\nitems.remove(1)")
    assert "epl_list_contains" in compile_to_ir("items = [1, 2, 3]\nr = items.contains(2)\nPrint r")
    assert "epl_list_set_int" in compile_to_ir("items = [1, 2, 3]\nitems[0] = 99")


def test_compiler_numeric_boolean_and_extended_builtins():
    assert "fadd" in compile_to_ir("Print 1.5 + 2.5")
    assert "fsub" in compile_to_ir("Print 5.0 - 2.0")
    assert "fmul" in compile_to_ir("Print 2.0 * 3.0")
    assert "fdiv" in compile_to_ir("Print 10.0 / 3.0")
    assert "fcmp ogt" in compile_to_ir("Print 3.14 > 2.71")

    assert compile_to_ir("x = true\nPrint x")
    assert compile_to_ir("x = false\nPrint x")
    assert compile_to_ir("x = not true\nPrint x")

    assert "epl_string_to_int" in compile_to_ir('Print to_integer("42")')
    assert "epl_int_to_string" in compile_to_ir("Print to_text(42)")
    assert compile_to_ir("Print to_decimal(42)")

    assert "epl_log" in compile_to_ir("Print log(100)")
    assert "epl_sin" in compile_to_ir("Print sin(0)")
    assert "epl_cos" in compile_to_ir("Print cos(0)")
    assert compile_to_ir("Print max(3, 7)")
    assert compile_to_ir("Print min(3, 7)")
    assert compile_to_ir("Print round(3.7)")
    assert compile_to_ir('Print char_code("A")')
    assert compile_to_ir("Print from_char_code(65)")


def test_compiler_memory_management_try_finally_and_recursion():
    assert "epl_arena_reset" in compile_to_ir('Print "hello"')
    assert "epl_try_begin" in compile_to_ir('Try\n  Print "try"\nCatch e\n  Print e\nFinally\n  Print "done"\nEnd')
    assert "epl_fib" in compile_to_ir(
        "Function fib takes n\n  If n <= 1 then\n    Return n\n  End\n  Return fib(n - 1) + fib(n - 2)\nEnd\nPrint fib(10)"
    )
    assert compile_to_ir(
        "Function double takes x\n  Return x * 2\nEnd\nFunction square takes x\n  Return x * x\nEnd\nPrint double(square(3))"
    )


def test_compiler_can_emit_object_code():
    import llvmlite.binding as llvm

    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    ir_code = compile_to_ir("Print 42")
    module = llvm.parse_assembly(ir_code)
    module.verify()
    target = llvm.targets.Target.from_default_triple()
    target_machine = target.create_target_machine(opt=2, reloc="pic", codemodel="default")
    obj = target_machine.emit_object(module)
    assert len(obj) > 0
