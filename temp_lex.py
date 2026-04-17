from epl.lexer import Lexer
lexer = Lexer('label = "big"')
tokens = lexer.tokenize()
for t in tokens:
    print(t)
