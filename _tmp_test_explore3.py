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

# Test: Method with no-arg (like show) via explicit method call
test_code("explicit method call", """Class Dog
    name = "Rex"

    Function speak takes nothing
        Print name
    End
End

Create d = new Dog
d.speak()""")

# Test: method call with dot syntax
test_code("dot method call", """Class Dog
    name = "Rex"

    Function speak
        Print name
    End
End

Create d = new Dog
d.name = "Buddy"
d.speak()""")

# Test: __add__ that uses other only  
test_code("__add__ other only", """Class Wrapper
    val = 0

    Function __add__ takes other
        Return other
    End
End

Create w1 = new Wrapper
w1.val = 5
Create w2 = new Wrapper
w2.val = 10
Create w3 = w1 + w2
Print w3.val""")

# Test: Class init method
test_code("Class with init", """Class Point
    x = 0
    y = 0

    Function init takes px and py
        x = px
        y = py
    End
End

Create p = new Point with 3 and 7
Print p.x
Print p.y""")

# Test: generator with parentheses syntax as expression
test_code("for-each generator parens", """Function make_gen takes n
    Create i = 0
    While i < n
        Yields i
        i += 1
    End while
End

For each x in make_gen(3)
    Print x
End for.""")

# Test: module function with parens  
test_code("Module parens call", """Module Math
    Function square takes x
        Return x * x
    End
End
Print Math::square(5)""")

# Test: module function via Print expression
test_code("Module in print expr", """Module Utils
    Function double takes x
        Return x * 2
    End
End
Create result = Utils::double(7)
Print result""")
