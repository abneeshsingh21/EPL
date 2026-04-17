import re
from epl.lexer import Lexer
from epl.parser import Parser
from epl.errors import ParserError

code = """
Create WebApp called app
db = db_open("todos.db")
db_create_table(db, "todos", Map with id = "INTEGER PRIMARY KEY AUTOINCREMENT" and title = "TEXT NOT NULL" and completed = "INTEGER DEFAULT 0")

Route "/api/todos" responds with
    todos = db_query(db, "SELECT * FROM todos ORDER BY id DESC")
    Return Map with success = "True" and data = todos
End

Route "/api/todos" responds with
    body = request_body()
    db_execute(db, "INSERT INTO todos (title) VALUES (?)", [body.get("title")])
    Return Map with success = "True" and message = "Created"
End

app.start(8000)
"""

try:
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.parse()
    print("Code 1 parses OK!")
except Exception as e:
    print(f"Error Code 1: {e}")

code2 = """
Say "EPL Calculator v1.0"
running = true
history = []

Repeat 3 times
    Say "Loop"
End

While running == true
    input = Ask "calc> "
    If input == "quit" Then
        running = false
    Otherwise If input == "history" Then
        For each entry in history
            Say entry
        End
    Otherwise
        result = evaluate(input)
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
