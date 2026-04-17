import re
from epl.lexer import Lexer
from epl.parser import Parser
from epl.errors import ParserError

code2 = """
Say "EPL Calculator v1.0"
running = true
history = []

Repeat 3 times
    Say "Loop"
End

While running == true
    Ask "calc> " as user_input
    If user_input == "quit" Then
        running = false
    Otherwise If user_input == "history" Then
        For each entry in history
            Say entry
        End
    Otherwise
        result = evaluate(user_input)
        Say "= " + to_string(result)
    End
End
"""

try:
    lexer = Lexer(code2)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.parse()
    print("Code 2 parses OK!")
except Exception as e:
    print(f"Error Code 2: {e}")
