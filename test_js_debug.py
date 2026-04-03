import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from epl.lexer import Lexer
from epl.parser import Parser
from epl.js_transpiler import transpile_to_js

def to_js(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse()
    return transpile_to_js(program)

# repeat_loop
r = to_js('Repeat 5 times\n  Print "hi"\nEnd')
print('REPEAT OUTPUT:')
print(repr(r))
print('Has for let _i:', 'for (let _i = 0;' in r)
print()

# list_sort
s = to_js('items = [3, 1, 2]\nitems.sort()')
print('SORT OUTPUT:')
print(repr(s))
print('Has .sort():', '.sort()' in s)
