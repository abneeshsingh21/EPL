from epl.lexer import Lexer
from epl.parser import Parser

lexer = Lexer('label = "big"\n')
tokens = lexer.tokenize()

parser = Parser(tokens)

try:
    stmt = parser._parse_statement()
    print("Parsed Statement:", stmt)
except Exception as e:
    print(f"ERROR: {e}")
