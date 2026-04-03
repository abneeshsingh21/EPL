"""Quick check: test EPL syntax forms used in copilot/playground templates."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from epl.lexer import Lexer
from epl.parser import Parser

tests = [
    ('ask store-in', 'ask "What?" store in answer'),
    ('to_number', 'set x to to_number("42")'),
    ('add to list', 'set f to ["a"]\nadd "b" to f'),
    ('write to file', 'write "hello" to file "out.txt"'),
    ('read file', 'set d to read file "out.txt"'),
    ('append to file', 'append "more" to file "out.txt"'),
    ('list remove method', 'set items to [1,2,3]\ncall items.remove(2)'),
    ('map with', 'set p to map with name = "Alice" and age = 30'),
    ('function takes', 'function add takes a and b\n    return a + b\nend'),
    ('function no-args', 'function greet\n    display "hi"\nend'),
    ('while no-do', 'set i to 0\nwhile i < 5\n    set i to i + 1\nend'),
    ('new no-parens', 'class Dog\n    set name to "Rex"\nend\nset d to new Dog'),
    ('constant =', 'constant PI = 3.14'),
    ('enum as', 'enum Color as RED, GREEN, BLUE'),
    ('match when', 'set x to 1\nmatch x\n    when 1\n        display "one"\n    default\n        display "other"\nend'),
    ('wait seconds', 'wait 2 seconds'),
    ('webapp create', 'Create WebApp called myApp'),
    ('route shows', 'Create WebApp called myApp\nRoute "/" shows\n    Page "Home"\n        Heading "Hello"\n    End\nEnd'),
    ('route responds with', 'Create WebApp called myApp\nRoute "/api" responds with\n    Send json Map with msg = "hi"\nEnd'),
]

ok = fail = 0
for name, code in tests:
    try:
        p = Parser(Lexer(code).tokenize()).parse()
        print(f'  OK:   {name}')
        ok += 1
    except Exception as e:
        print(f'  FAIL: {name} -> {str(e)[:100]}')
        fail += 1

print(f'\nSyntax check: {ok} OK, {fail} FAIL')
