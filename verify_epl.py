import os
from epl.lexer import Lexer
from epl.parser import Parser

errors = []
for root, _, files in os.walk("examples"):
    for file in files:
        if file.endswith(".epl"):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
            try:
                lexer = Lexer(code)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                parser.parse()
            except Exception as e:
                errors.append((filepath, str(e)))

for filepath, err in errors:
    print(f"File: {filepath}")
    print(f"ERROR: {err}\n")
