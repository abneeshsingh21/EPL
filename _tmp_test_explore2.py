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

# Test: __add__ that doesn't use this - just adds the arg to something
test_code("__add__ simple return", """Class Num
    val = 0

    Function __add__ takes other
        Return other.val + 100
    End
End

Create x1 = new Num
x1.val = 5
Create x2 = new Num
x2.val = 10
Create x3 = x1 + x2
Print x3""")

# Test: __add__ that returns a new instance using val (no this)
test_code("__add__ with val no this", """Class Num
    val = 0

    Function __add__ takes other
        Create r = new Num
        r.val = val + other.val
        Return r
    End
End

Create x1 = new Num
x1.val = 5
Create x2 = new Num
x2.val = 10
Create x3 = x1 + x2
Print x3.val""")

# Test: can we test method via .method() call?
test_code("method call", """Class Num
    val = 0

    Function show
        Print val
    End
End

Create x1 = new Num
x1.val = 42
x1.show()""")

# Test: for-each loop uses generator.to_list()
# generators only work via _call_callable
# What if we use direct call syntax?
test_code("generator parens call", """Function gen
    Yields 10
    Yields 20
End

For each x in gen()
    Print x
End for.""")

# Test what += does on integer for rest param test
test_code("total += in loop", """Function sum_all takes rest numbers
    Create total = 0
    For each n in numbers
        total += n
    End for
    Return total
End
Print Call sum_all with 1 and 2 and 3""")
