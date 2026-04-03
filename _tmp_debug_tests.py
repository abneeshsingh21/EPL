from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter

def run(src):
    try:
        l = Lexer(src)
        t = l.tokenize()
        p = Parser(t)
        prog = p.parse()
        i = Interpreter()
        i.execute(prog)
        return i.output_lines
    except Exception as e:
        return f'ERROR: {type(e).__name__}: {e}'

# Test __add__ without this - using val property
print('T1:', run(
    'Class Vector\n'
    '    x = 0\n'
    '    y = 0\n'
    '\n'
    '    Function __add__ takes other\n'
    '        Create result = new Vector\n'
    '        result.x = other.x\n'
    '        result.y = other.y\n'
    '        Return result\n'
    '    End\n'
    'End\n'
    '\n'
    'Create v1 = new Vector\n'
    'v1.x = 1\n'
    'v1.y = 2\n'
    'Create v2 = new Vector\n'
    'v2.x = 3\n'
    'v2.y = 4\n'
    'Create v3 = v1 + v2\n'
    'Print v3.x\n'
    'Print v3.y'
))

# Test typeof lambda
print('T1b:', run(
    'Create f = Lambda x -> x * 2\n'
    'Print Call typeof with f.'
))

# Test typeof on function name in Call
print('T1c:', run(
    'Function my_func takes x\n'
    '    Return x\n'
    'End\n'
    'Create result = Call typeof with "test".\n'
    'Print result.'
))

# Test __sub__ without this
print('T2:', run(
    'Class Num\n'
    '    val = 0\n'
    '\n'
    '    Function __sub__ takes other\n'
    '        Return other.val\n'
    '    End\n'
    'End\n'
    '\n'
    'Create x1 = new Num\n'
    'x1.val = 10\n'
    'Create x2 = new Num\n'
    'x2.val = 3\n'
    'Print x1 - x2'
))

# Test __mul__ without this
print('T3:', run(
    'Class Num\n'
    '    val = 0\n'
    '\n'
    '    Function __mul__ takes other\n'
    '        Return other.val\n'
    '    End\n'
    'End\n'
    '\n'
    'Create x1 = new Num\n'
    'x1.val = 5\n'
    'Create x2 = new Num\n'
    'x2.val = 4\n'
    'Print x1 * x2'
))

# Test __eq__ without this, avoiding reserved 'a'
print('T4:', run(
    'Class Num\n'
    '    val = 0\n'
    '\n'
    '    Function __eq__ takes other\n'
    '        Return true\n'
    '    End\n'
    'End\n'
    '\n'
    'Create x1 = new Num\n'
    'x1.val = 5\n'
    'Create x2 = new Num\n'
    'x2.val = 5\n'
    'If x1 == x2 then\n'
    '    Print "equal"\n'
    'End if.'
))

# Test __str__ returning literal
print('T5:', run(
    'Class Greeting\n'
    '    msg = "hi"\n'
    '\n'
    '    Function __str__\n'
    '        Return "Hello World"\n'
    '    End\n'
    'End\n'
    '\n'
    'Create g = new Greeting\n'
    'Print g.'
))

# Test module with parens syntax
print('T6:', run(
    'Module MathUtils\n'
    '    Function square takes x\n'
    '        Return x * x\n'
    '    End\n'
    'End\n'
    'Print MathUtils::square(5).'
))

# Test module multiple funcs with parens syntax
print('T7:', run(
    'Module StringUtils\n'
    '    Function exclaim takes s\n'
    '        Return s + "!"\n'
    '    End\n'
    '    Function question takes s\n'
    '        Return s + "?"\n'
    '    End\n'
    'End\n'
    'Print StringUtils::exclaim("Hello").\n'
    'Print StringUtils::question("Really").'
))

# Test generators - list-based approach
print('T8:', run(
    'Function count_up takes limit\n'
    '    Create list named result equal to [].\n'
    '    Create i = 0\n'
    '    While i < limit\n'
    '        Add i to result.\n'
    '        i = i + 1\n'
    '    End while\n'
    '    Return result\n'
    'End\n'
    '\n'
    'Create items = Call count_up with 3\n'
    'For each x in items\n'
    '    Print x\n'
    'End for.'
))

# Test typeof on lambda
print('T9:', run(
    'Create f = Lambda x then x * 2\n'
    'Print Call typeof with f.'
))

# Test typeof on function
print('T10:', run(
    'Function my_func\n'
    '    Return 1\n'
    'End\n'
    'Print Call typeof with my_func.'
))
