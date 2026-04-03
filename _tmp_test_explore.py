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

# Test 1: __str__ without this
test_code("__str__ without this", """Class Greeting
    msg = "hi"

    Function __str__ takes nothing
        Return msg
    End
End

Create g = new Greeting
g.msg = "Hello World"
Print g""")

# Test 2: __str__ with this
test_code("__str__ with this", """Class Greeting
    msg = "hi"

    Function __str__ takes nothing
        Return this.msg
    End
End

Create g = new Greeting
g.msg = "Hello World"
Print g""")

# Test 3: Module::function with Call
test_code("Module::func with Call", """Module Math
    Function square takes x
        Return x * x
    End
End
Print Call Math::square with 5""")

# Test 4: Module::func with parentheses
test_code("Module::func with parens", """Module Math
    Function square takes x
        Return x * x
    End
End
Print Math::square(5)""")

# Test 5: List add via +=
test_code("List += append", """Create list named nums equal to [].
nums += 1
nums += 2
nums += 3
For each n in nums
    Print n
End for.""")

# Test 6: length via Call
test_code("length via Call", """Function echo takes rest items
    Print Call length with items
End
Call echo""")

# Test 7: Operator __eq__ without reserved word 'a'
test_code("__eq__ test", """Class Num
    val = 0

    Function __eq__ takes other
        Return val == other.val
    End
End

Create x1 = new Num
x1.val = 5
Create x2 = new Num
x2.val = 5
If x1 == x2 then
    Print "equal"
End if.""")

# Test 8: for-each with generator via _call_callable path
test_code("Generator via variable", """Function gen
    Yields 1
    Yields 2
    Yields 3
End

Create myFunc = gen
""")

# Test 9: Module variable access
test_code("Module var access", """Module Config
    Create version = "1.0"
End
Print Config::version""")
