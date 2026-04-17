import os
import re
from epl.lexer import Lexer
from epl.parser import Parser

def check_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    blocks = re.findall(r'```epl\n(.*?)\n```', text, re.DOTALL)
    
    errors = []
    for i, block in enumerate(blocks):
        if "Note: [Parser Error]" in block:
            continue
            
        try:
            lexer = Lexer(block)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            parser.parse()
        except Exception as e:
            errors.append((i+1, block, str(e)))
            
    if errors:
        print(f"\n=======================")
        print(f"File: {filepath} ({len(errors)} errors)")
        print(f"=======================\n")
        for idx, block, err in errors:
            print(f"--- Block {idx} ---")
            print(block)
            print(f"ERROR: {err}\n")

for root, _, files in os.walk("docs"):
    for file in files:
        if file.endswith(".md"):
            check_file(os.path.join(root, file))

for root, _, files in os.walk("examples"):
    for file in files:
        if file.endswith(".md"):
            check_file(os.path.join(root, file))
