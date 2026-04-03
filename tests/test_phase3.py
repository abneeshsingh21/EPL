"""
EPL Phase 3 Test Suite — Developer Experience Features
Tests for: Python transpiler, playground, notebook, block editor, copilot
"""

import sys
import os
import json
import io
import threading
from functools import wraps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl import ast_nodes as ast


# ── Helpers ──────────────────────────────────────────────

def _parse(source):
    return Parser(Lexer(source).tokenize()).parse()


class _TrackerState:
    current = None
    total_pass = 0
    total_fail = 0


def _start_tracker():
    _TrackerState.current = {
        "passed": 0,
        "failed": 0,
        "failures": [],
    }


def _finish_tracker():
    tracker = _TrackerState.current
    _TrackerState.current = None
    if tracker is None:
        return
    _TrackerState.total_pass += tracker["passed"]
    _TrackerState.total_fail += tracker["failed"]
    if tracker["failures"]:
        raise AssertionError("\n".join(tracker["failures"]))


def _tracked_test(fn):
    @wraps(fn)
    def wrapper():
        _start_tracker()
        try:
            fn()
        finally:
            _finish_tracker()

    return wrapper

def check(name, condition, detail=""):
    tracker = _TrackerState.current
    if tracker is None:
        raise RuntimeError("check() called outside an active test tracker.")
    if condition:
        print(f"  PASS: {name}")
        tracker["passed"] += 1
    else:
        print(f"  FAIL: {name} {detail}")
        tracker["failed"] += 1
        tracker["failures"].append(f"{name}: {detail}" if detail else name)


# ══════════════════════════════════════════════════════════
# 3.2  Python Transpiler Tests
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_python_transpiler():
    print("\n=== 3.2 Python Transpiler ===")
    from epl.python_transpiler import transpile_to_python, PythonTranspiler

    # T1: Module loads
    check("Python transpiler imports", True)

    # T2: Hello world
    code = 'display "Hello, World!"'
    py = transpile_to_python(_parse(code))
    check("Hello world", "print('Hello, World!')" in py, f"got: {py}")

    # T3: Variable declaration
    code = 'set x to 42'
    py = transpile_to_python(_parse(code))
    check("Variable decl", "x = 42" in py)

    # T4: If/else
    code = '''set x to 5
if x > 3 then
    display "big"
otherwise
    display "small"
end'''
    py = transpile_to_python(_parse(code))
    check("If/else", "if " in py and "else:" in py)

    # T5: While loop
    code = '''set i to 0
while i < 5
    display i
    set i to i + 1
end'''
    py = transpile_to_python(_parse(code))
    check("While loop", "while " in py)

    # T6: For range
    code = '''for i from 1 to 10
    display i
end'''
    py = transpile_to_python(_parse(code))
    check("For range", "for i in range(1, 10 + 1):" in py)

    # T7: For each
    code = '''set items to [1, 2, 3]
for each x in items
    display x
end'''
    py = transpile_to_python(_parse(code))
    check("For each", "for x in " in py)

    # T8: Function def
    code = '''function add takes a and b
    return a + b
end'''
    py = transpile_to_python(_parse(code))
    check("Function def", "def add(a, b):" in py and "return" in py)

    # T9: Class
    code = '''class Dog
    set name to "Rex"
    function bark
        display "Woof!"
    end
end'''
    py = transpile_to_python(_parse(code))
    check("Class def", "class Dog:" in py and "def __init__(self):" in py and "def bark(self):" in py)

    # T10: Repeat
    code = '''repeat 3 times
    display "hi"
end'''
    py = transpile_to_python(_parse(code))
    check("Repeat loop", "for _ in range(3):" in py)

    # T11: Try/catch
    code = '''try
    set x to 1 / 0
catch error
    display error
end'''
    py = transpile_to_python(_parse(code))
    check("Try/catch", "try:" in py and "except Exception" in py)

    # T12: List literal
    code = 'set items to [1, 2, 3]'
    py = transpile_to_python(_parse(code))
    check("List literal", "items = [1, 2, 3]" in py)

    # T13: Dict literal
    code = 'set person to map with name = "Alice" and age = 30'
    py = transpile_to_python(_parse(code))
    check("Dict literal", "'name': 'Alice'" in py and "'age': 30" in py)

    # T14: Lambda
    code = 'set double to lambda x -> x * 2'
    py = transpile_to_python(_parse(code))
    check("Lambda", "lambda x:" in py)

    # T15: Assert
    code = 'assert 1 + 1 == 2'
    py = transpile_to_python(_parse(code))
    check("Assert", "assert " in py)

    # T16: Wait
    code = 'wait 2 seconds'
    py = transpile_to_python(_parse(code))
    check("Wait/sleep", "time.sleep" in py and "import time" in py)

    # T17: Const
    code = 'constant PI = 3.14'
    py = transpile_to_python(_parse(code))
    check("Constant", "PI = 3.14" in py)

    # T18: Match/case
    code = '''match day
    when "Monday"
        display "work"
    when "Saturday"
        display "weekend"
    default
        display "other"
end'''
    py = transpile_to_python(_parse(code))
    check("Match/case", "match day:" in py and "case" in py)

    # T19: Augmented assignment
    code = '''set x to 5
set x to x + 3'''
    py = transpile_to_python(_parse(code))
    check("Augmented assign", "x = " in py)

    # T20: f-string template
    code = 'display "Hello ${name}!"'
    py = transpile_to_python(_parse(code))
    check("Template string", "f'" in py and "{name}" in py)

    # T21: Enum
    code = 'enum Color as RED, GREEN, BLUE'
    py = transpile_to_python(_parse(code))
    check("Enum", "class Color(Enum):" in py and "from enum import Enum" in py)

    # T22: Use statement
    code = 'use python "math" as math'
    py = transpile_to_python(_parse(code))
    check("Use statement", "import math" in py)

    # T23: PythonTranspiler class exists
    t = PythonTranspiler()
    check("Class instantiation", t.indent == 0 and isinstance(t.output, list))

    # T24: Empty program
    py = transpile_to_python(_parse(''))
    check("Empty program", "#!/usr/bin/env python3" in py)

    # T25: Break/continue
    code = '''while true
    break
end'''
    py = transpile_to_python(_parse(code))
    check("Break statement", "break" in py)


# ══════════════════════════════════════════════════════════
# 3.1  Web Playground Tests (unit-level)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_playground():
    print("\n=== 3.1 Web Playground ===")
    from epl.playground import _execute_epl, _transpile_epl, _get_examples, _PLAYGROUND_HTML

    # T26: Module loads
    check("Playground imports", True)

    # T27: Execute simple code
    result = _execute_epl('display "hello"')
    check("Execute hello", result['output'].strip() == "hello" and result['error'] is None,
          f"got: {result}")

    # T28: Execute with error
    result = _execute_epl('set x to 1 / 0')
    check("Execute error", result['error'] is not None)

    # T29: Execute timeout (infinite loop)
    result = _execute_epl('while true\n    set x to 1\nend')
    check("Execute timeout", "timed out" in str(result.get('error', '')).lower() or result['output'] == '',
          f"got: {result}")

    # T30: Transpile to Python
    result = _transpile_epl('display "hi"', 'python')
    check("Transpile to Python", result.get('code') and "print" in result['code'])

    # T31: Transpile to JavaScript
    result = _transpile_epl('display "hi"', 'javascript')
    check("Transpile to JS", result.get('code') and "console.log" in result['code'])

    # T32: Transpile unknown target
    result = _transpile_epl('display "hi"', 'rust')
    check("Transpile unknown", result.get('error') is not None)

    # T33: Examples list
    examples = _get_examples()
    check("Examples list", len(examples) >= 5 and all('name' in e and 'code' in e for e in examples))

    # T34: HTML template exists
    check("HTML template", len(_PLAYGROUND_HTML) > 1000 and '<html' in _PLAYGROUND_HTML)

    # T35: Empty code
    result = _execute_epl('')
    check("Empty code execute", True)  # Should not crash


# ══════════════════════════════════════════════════════════
# 3.3  EPL Notebook Tests (unit-level)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_notebook():
    print("\n=== 3.3 EPL Notebook ===")
    from epl.notebook import _execute_epl as nb_execute, _new_id, _NOTEBOOK_HTML

    # T36: Module loads
    check("Notebook imports", True)

    # T37: Execute cell
    result = nb_execute('display "notebook"')
    check("Execute cell", result['output'].strip() == "notebook")

    # T38: Error in cell
    result = nb_execute('display x')
    check("Cell error handling", result.get('error') is not None or 'x' in result.get('output', ''))

    # T39: ID generation
    ids = {_new_id() for _ in range(100)}
    check("Unique IDs", len(ids) == 100)

    # T40: HTML template
    check("Notebook HTML", len(_NOTEBOOK_HTML) > 1000 and 'EPL Notebook' in _NOTEBOOK_HTML)


# ══════════════════════════════════════════════════════════
# 3.4  Visual Block Editor Tests (unit-level)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_block_editor():
    print("\n=== 3.4 Visual Block Editor ===")
    from epl.block_editor import _execute_epl as blk_execute, _BLOCK_EDITOR_HTML

    # T41: Module loads
    check("Block editor imports", True)

    # T42: Execute from blocks
    result = blk_execute('display "blocks"')
    check("Block execute", result['output'].strip() == "blocks")

    # T43: HTML template
    check("Block editor HTML", len(_BLOCK_EDITOR_HTML) > 1000 and 'Block Editor' in _BLOCK_EDITOR_HTML)

    # T44: Block categories in HTML
    check("Block categories",
          'cat-output' in _BLOCK_EDITOR_HTML and
          'cat-variable' in _BLOCK_EDITOR_HTML and
          'cat-control' in _BLOCK_EDITOR_HTML and
          'cat-function' in _BLOCK_EDITOR_HTML)


# ══════════════════════════════════════════════════════════
# 3.5  EPL AI Copilot Tests
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_copilot():
    print("\n=== 3.5 EPL AI Copilot ===")
    from epl.copilot import generate_from_description, _COPILOT_HTML

    # T45: Module loads
    check("Copilot imports", True)

    # T46: Hello world
    code = generate_from_description("hello world")
    check("Gen hello world", 'display "Hello, World!"' in code)

    # T47: Calculator
    code = generate_from_description("calculator")
    check("Gen calculator", 'function add' in code and 'function divide' in code)

    # T48: Fibonacci
    code = generate_from_description("fibonacci 15")
    check("Gen fibonacci", 'function fibonacci' in code and '15' in code)

    # T49: Fizzbuzz
    code = generate_from_description("fizzbuzz")
    check("Gen fizzbuzz", 'FizzBuzz' in code and 'Fizz' in code and 'Buzz' in code)

    # T50: Sort
    code = generate_from_description("sort a list of numbers")
    check("Gen sort", 'function' in code.lower() and 'sort' in code.lower())

    # T51: Guessing game
    code = generate_from_description("number guessing game")
    check("Gen guessing game", 'random' in code.lower() and 'guess' in code.lower())

    # T52: Prime numbers
    code = generate_from_description("prime numbers up to 30")
    check("Gen primes", 'isPrime' in code and '30' in code)

    # T53: Class generation
    code = generate_from_description("class Animal")
    check("Gen class", 'class Animal' in code)

    # T54: String operations
    code = generate_from_description("reverse a string")
    check("Gen string reverse", 'reverse' in code.lower())

    # T55: Star pattern
    code = generate_from_description("star pattern triangle")
    check("Gen pattern", '*' in code)

    # T56: Todo list
    code = generate_from_description("todo list app")
    check("Gen todo", 'todo' in code.lower())

    # T57: File operations
    code = generate_from_description("read and write files")
    check("Gen file ops", 'write' in code.lower() and 'read' in code.lower())

    # T58: Dictionary
    code = generate_from_description("dictionary operations")
    check("Gen dictionary", 'keys' in code.lower() or 'dict' in code.lower())

    # T59: Error handling
    code = generate_from_description("try catch error handling")
    check("Gen error handling", 'try' in code and 'catch' in code)

    # T60: Math
    code = generate_from_description("math operations square root")
    check("Gen math", 'sqrt' in code)

    # T61: Timer
    code = generate_from_description("countdown timer 5")
    check("Gen timer", 'wait' in code and '5' in code)

    # T62: Loop
    code = generate_from_description("loop 20 times")
    check("Gen loop", 'for' in code and '20' in code)

    # T63: Factorial
    code = generate_from_description("factorial")
    check("Gen factorial", 'factorial' in code)

    # T64: Search
    code = generate_from_description("binary search")
    check("Gen search", 'search' in code.lower())

    # T65: Web/API
    code = generate_from_description("web app with api")
    check("Gen web app", 'Route' in code or 'route' in code)

    # T66: Fallback for unknown
    code = generate_from_description("quantum teleportation simulation")
    check("Gen fallback", 'display' in code and len(code) > 50)

    # T67: Number extraction
    code = generate_from_description("fibonacci 25")
    check("Number extraction", '25' in code)

    # T68: HTML template
    check("Copilot HTML", len(_COPILOT_HTML) > 1000 and 'EPL AI Copilot' in _COPILOT_HTML)

    # T69: Person class
    code = generate_from_description("create a person class")
    check("Gen Person class", 'class Person' in code)

    # T70: Car class
    code = generate_from_description("class car with speed")
    check("Gen Car class", 'class Car' in code)


# ══════════════════════════════════════════════════════════
# Integration: Python transpiler round-trip
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_transpiler_integration():
    print("\n=== Integration: Transpiler Round-Trip ===")
    from epl.python_transpiler import transpile_to_python

    # T71: Complex program
    code = '''set name to "Alice"
set age to 25
if age > 18 then
    display name + " is an adult"
otherwise
    display name + " is a minor"
end

function greet takes person
    return "Hello, " + person
end

display greet(name)

set scores to [95, 87, 72]
for each score in scores
    display "Score: " + score
end

try
    set result to 10 / 0
catch error
    display "Error: " + error
end'''
    py = transpile_to_python(_parse(code))
    check("Complex program transpiles",
          "def greet" in py and "for score in" in py and "try:" in py and "except" in py)

    # T72: Shebang line
    check("Has shebang", py.startswith("#!/usr/bin/env python3"))

    # T73: Auto-generated comment
    check("Has auto-gen comment", "Auto-generated from EPL" in py)

    # T74: Proper indentation
    lines = py.split('\n')
    indented_lines = [l for l in lines if l.startswith('    ')]
    check("Has indented lines", len(indented_lines) > 3)

    # T75: Nested if/elif/else
    code = '''set x to 5
if x > 10 then
    display "big"
otherwise if x > 3 then
    display "medium"
otherwise
    display "small"
end'''
    py = transpile_to_python(_parse(code))
    check("Elif chain", "elif" in py)

    # T76: Class with methods and self
    code = '''class Cat
    set name to "Whiskers"
    function meow
        display name + " says meow"
    end
end'''
    py = transpile_to_python(_parse(code))
    check("Class self in methods", "def meow(self):" in py and "self.name" in py)


# ══════════════════════════════════════════════════════════
# CLI Integration Tests
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_cli_dispatch():
    print("\n=== CLI Integration ===")
    import importlib

    # T77: main.py parse check
    main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        main_src = f.read()

    check("CLI: python command", "command == 'python'" in main_src)
    check("CLI: playground command", "command == 'playground'" in main_src)
    check("CLI: notebook command", "command == 'notebook'" in main_src)
    check("CLI: blocks command", "command == 'blocks'" in main_src)
    check("CLI: copilot command", "command == 'copilot'" in main_src)

    # T82: Help text
    check("Help: python", "Transpile to Python" in main_src)
    check("Help: playground", "Web Playground" in main_src)
    check("Help: notebook", "Notebook" in main_src)
    check("Help: blocks", "Block Editor" in main_src)
    check("Help: copilot", "Copilot" in main_src)


# ══════════════════════════════════════════════════════════
# Parse-Validation: Copilot output must be valid EPL
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_copilot_parse_validation():
    """Ensure generated EPL code actually parses without errors."""
    print("\n=== Copilot Parse Validation ===")
    from epl.copilot import generate_from_description
    from epl.lexer import Lexer
    from epl.parser import Parser

    prompts = [
        ("hello world", "hello"),
        ("calculator with add subtract", "calculator"),
        ("fibonacci 10", "fibonacci"),
        ("fizzbuzz", "fizzbuzz"),
        ("number guessing game", "guess game"),
        ("prime numbers up to 20", "primes"),
        ("class Animal", "class"),
        ("reverse a string", "string reverse"),
        ("star pattern triangle", "star pattern"),
        ("todo list app", "todo app"),
        ("read and write files", "file ops"),
        ("dictionary operations", "dictionary"),
        ("try catch error handling", "error handling"),
        ("math operations square root", "math ops"),
        ("countdown timer 3", "timer"),
        ("loop 5 times", "loop"),
        ("factorial", "factorial"),
        ("binary search", "search"),
        ("web app with api", "web app"),
        ("sort a list of numbers", "sort"),
        ("quantum teleportation simulation", "fallback"),
    ]

    for prompt, label in prompts:
        code = generate_from_description(prompt)
        try:
            Parser(Lexer(code).tokenize()).parse()
            check(f"Parse: {label}", True)
        except Exception as e:
            check(f"Parse: {label} -> {str(e)[:60]}", False)


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("EPL Phase 3 Test Suite")
    print("=" * 50)

    test_functions = [
        test_python_transpiler,
        test_playground,
        test_notebook,
        test_block_editor,
        test_copilot,
        test_copilot_parse_validation,
        test_transpiler_integration,
        test_cli_dispatch,
    ]
    failed_sections = 0

    for fn in test_functions:
        try:
            fn()
        except AssertionError as exc:
            failed_sections += 1
            print(str(exc))

    print("\n" + "=" * 50)
    print(
        f"Phase 3 Results: {_TrackerState.total_pass} passed, "
        f"{_TrackerState.total_fail} failed "
        f"(total {_TrackerState.total_pass + _TrackerState.total_fail})"
    )
    if failed_sections > 0:
        sys.exit(1)
    else:
        print("All Phase 3 tests PASSED!")


