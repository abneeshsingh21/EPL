"""Pytest coverage for LLVM GC integration."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from epl.compiler import Compiler
from epl.lexer import Lexer
from epl.parser import Parser


def compile_epl(src):
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    compiler = Compiler()
    return compiler.compile(program)


def test_gc_runtime_functions_are_declared_and_shutdown_called():
    ir = compile_epl("x = 10\nPrint x\n")
    required = [
        "epl_gc_collect_if_needed",
        "epl_gc_shutdown",
        "epl_gc_root_push",
        "epl_gc_root_pop",
        "epl_gc_new_list",
        "epl_gc_new_map",
        "epl_gc_new_object",
        "epl_gc_new_string",
        "epl_gc_collect",
    ]
    for function_name in required:
        assert function_name in ir, function_name
    assert "epl_gc_shutdown" in ir and "call void" in ir


def test_gc_list_allocation_uses_gc_runtime():
    ir = compile_epl("items = [1, 2, 3]\n")
    assert "epl_gc_new_list" in ir
    assert "epl_gc_root_push" in ir
    assert 'call i8* @"epl_list_new"' not in ir


def test_gc_map_and_object_allocations_use_gc_runtime():
    map_ir = compile_epl('p = Map with name = "test" and age = 20\n')
    assert "epl_gc_new_map" in map_ir
    assert "epl_gc_root_push" in map_ir

    object_ir = compile_epl('Class Dog\n    name = "Rex"\nEnd\nd = new Dog\n')
    assert "epl_gc_new_object" in object_ir
    assert "epl_gc_root_push" in object_ir


def test_gc_loop_safepoints_are_inserted():
    repeat_ir = compile_epl("Repeat 5 times\n    Print 1\nEnd\n")
    while_ir = compile_epl("x = 1\nWhile x < 10\n    x = x + 1\nEnd\n")
    for_ir = compile_epl("For i from 1 to 10\n    Print i\nEnd\n")
    foreach_ir = compile_epl("items = [1,2,3]\nFor each item in items\n    Print item\nEnd\n")

    for ir in (repeat_ir, while_ir, for_ir, foreach_ir):
        assert "epl_gc_collect_if_needed" in ir


def test_gc_function_root_management_is_present():
    ir = compile_epl("Function greet takes n\n    items = [1,2]\n    Return items\nEnd\n")
    assert "epl_gc_root_push" in ir
    assert "epl_gc_root_pop" in ir


def test_gc_complex_programs_use_allocations_and_safepoints():
    loop_ir = compile_epl("items = [1,2,3]\nFor i from 1 to 5\n    items = [i, i+1]\nEnd\n")
    assert "epl_gc_new_list" in loop_ir
    assert "epl_gc_collect_if_needed" in loop_ir
    assert "epl_gc_root_push" in loop_ir

    mixed_ir = compile_epl('Class Cat\n    name = "Whiskers"\nEnd\ncats = [1,2,3]\nc = new Cat\n')
    assert "epl_gc_new_list" in mixed_ir
    assert "epl_gc_new_object" in mixed_ir
