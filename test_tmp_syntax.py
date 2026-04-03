"""Test EPL syntax to verify correct forms."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter

def run_epl(source):
    l = Lexer(source)
    t = l.tokenize()
    p = Parser(t)
    prog = p.parse()
    i = Interpreter()
    i.execute(prog)
    return i.output_lines

# Test string uppercase
print("Test 1:", run_epl('s = "hello"\nPrint s.uppercase'))

# Test class with method
print("Test 2:", run_epl('Class Dog\n    name = "Rex"\n    Function bark\n        Print "Woof!"\n    End\nEnd\nd = new Dog\nd.bark()'))

# Test function with return
print("Test 3:", run_epl('Function greet takes name\n    Return "Hello, " + name\nEnd\nresult = call greet with "EPL"\nPrint result'))

# Test for each
print("Test 4:", run_epl('total = 0\nFor each i in range(1, 5)\n    total = total + i\nEnd\nPrint total'))
