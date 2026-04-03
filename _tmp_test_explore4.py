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

# Can we call init with new Classname(args)?
test_code("new Point(3,7)", """Class Point
    x = 0
    y = 0

    Function init takes px and py
        x = px
        y = py
    End
End

Create p = new Point(3, 7)
Print p.x
Print p.y""")

# Test: method call with this and property access via _call_instance_method
test_code("method using this via dot call", """Class Dog
    name = "Rex"

    Function get_name takes nothing
        Return this.name
    End
End

Create d = new Dog
d.name = "Buddy"
Print d.get_name()""")

# Test __add__ via _call_instance_method (dot call)
test_code("__add__ via dot method", """Class Num
    val = 0

    Function add_to takes other
        Create r = new Num
        r.val = this.val + other.val
        Return r
    End
End

Create x1 = new Num
x1.val = 5
Create x2 = new Num
x2.val = 10
Create x3 = x1.add_to(x2)
Print x3.val""")

# Test accessing instance method name without this - just bare property
test_code("method bare property", """Class Dog
    name = "Rex"

    Function get_name takes nothing
        Return name
    End
End

Create d = new Dog
d.name = "Buddy"
Print d.get_name()""")

# Can we use += on properties?
test_code("property +=", """Class Counter
    count = 0

    Function inc takes nothing
        count += 1
    End
End

Create c = new Counter
c.inc()
c.inc()
c.inc()
Print c.count""")

# Test: __eq__ via method call (not operator)
test_code("__eq__ via method", """Class Num
    val = 0

    Function equals takes other
        If val == other.val then
            Return true
        End if
        Return false
    End
End

Create x1 = new Num
x1.val = 5
Create x2 = new Num
x2.val = 5
Print x1.equals(x2)""")
