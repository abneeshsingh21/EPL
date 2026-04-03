from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter

def test_code(label, src):
    try:
        lexer = Lexer(src)
        tokens = lexer.tokenize()
        program = Parser(tokens).parse()
        interp = Interpreter()
        interp.execute(program)
        print(f"{label}: {interp.output_lines}")
    except Exception as e:
        print(f"{label}: ERROR - {e}")

# Generators: test if _call_callable path works for generators
# The issue is _exec_function_call doesn't detect yield
# But _call_callable does. Let's see if we can trigger _call_callable

# Test: Pass generator func as value, then call it
test_code("gen via variable call", """Function gen
    Yields 1
    Yields 2
End

Create f = gen
""")

# What if the generator is called via parentheses expression?
test_code("gen expr call", """Function gen
    Yields 1
    Yields 2
End

Create g = gen()
Print Call typeof with g
""")

# Method call on instance that returns value
test_code("instance method call expr", """Class Calc
    val = 0

    Function get_double takes nothing
        Return val * 2
    End
End

Create c = new Calc
c.val = 21
Print c.get_double()""")

# Module with constant
test_code("Module constant", """Module Config
    Create PI = 3.14
End
Print Config::PI""")

# Module multiple members
test_code("Module multi", """Module Utils
    Function add takes x and y
        Return x + y
    End
    Function mul takes x and y
        Return x * y
    End
End
Print Utils::add(3, 4)
Print Utils::mul(3, 4)""")

# Test: __add__ operator only using other param (no this needed)
test_code("__add__ use other.val", """Class Num
    val = 0

    Function __add__ takes other
        Return val + other.val
    End
End

Create n1 = new Num
n1.val = 5
Create n2 = new Num
n2.val = 10
Print n1 + n2""")

# Test: Hash md5
test_code("hash_md5", """Create h = Call hash_md5 with "hello"
Print Call length with h""")

# Test: to_boolean
test_code("to_boolean 1", """Print Call to_boolean with 1""")
test_code("to_boolean 0", """Print Call to_boolean with 0""")

# Test: Break in while
test_code("while break", """Create i = 0
While true
    If i == 3 then
        Break
    End if
    Print i
    i += 1
End while""")

# Test what syntax class needs for Function with no args
test_code("method no parens", """Class Dog
    name = "Rex"

    Function speak
        Print name
    End
End

Create d = new Dog
d.speak()""")
