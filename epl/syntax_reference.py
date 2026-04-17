"""Authoritative EPL syntax reference derived from parser-supported forms."""

from __future__ import annotations

from copy import deepcopy


_SYNTAX_SECTIONS = [
    {
        "id": "comments",
        "title": "Comments",
        "summary": "Single-line comments use the Note: prefix or #.",
        "examples": [
            'Note: This line is ignored',
            '# This line is also ignored',
        ],
    },
    {
        "id": "variables",
        "title": "Variables And Constants",
        "summary": "Use Create, Set, shorthand assignment, Remember, or Constant.",
        "examples": [
            'Create name = "Ada"',
            'Create count as 3',
            'Set count to count + 1',
            'total = 10',
            'Remember welcome as "Hello"',
            'Constant PI = 3.14159',
            'Increase count by 1',
            'Decrease count by 1',
        ],
    },
    {
        "id": "output_input",
        "title": "Output And Input",
        "summary": "Say, Display, Print, Show, Ask, and Input are valid I/O forms.",
        "examples": [
            'Say "Hello"',
            'Display "Total: " + total',
            'Ask "What is your name?" and store in name',
            'Input age with prompt "Age: "',
        ],
    },
    {
        "id": "control_flow",
        "title": "Control Flow",
        "summary": "If/Otherwise, While, Repeat, For, and Match/When all close with End.",
        "examples": [
            'If score >= 90 Then\n    Say "A"\nOtherwise\n    Say "B"\nEnd',
            'While retries > 0\n    Set retries to retries - 1\nEnd',
            'Repeat 3 times\n    Say "Tick"\nEnd',
            'For each item in items\n    Say item\nEnd',
            'For i from 1 to 10 step 2\n    Say i\nEnd',
            'Match grade\n    When "A"\n        Say "Excellent"\n    When "B" or "C"\n        Say "Good"\n    Default\n        Say "Try harder"\nEnd',
        ],
    },
    {
        "id": "functions",
        "title": "Functions And Lambdas",
        "summary": "Functions support English and parenthesized forms. Lambdas use arrow syntax.",
        "examples": [
            'Function greet takes name\n    Return "Hello, " + name\nEnd',
            'Function add(a, b)\n    Return a + b\nEnd',
            'Define Function buildApi with host and port\n    Return host + ":" + port\nEnd',
            'Call greet with "Ada"',
            'greet("Ada")',
            'Create square = lambda x -> x * x',
        ],
    },
    {
        "id": "collections",
        "title": "Collections",
        "summary": "Lists use brackets and maps use Map with key = value pairs.",
        "examples": [
            'Create items = [1, 2, 3]',
            'Create user = Map with name = "Ada" and role = "admin"',
            'Say items[0]',
            'Say user.name',
            'Add "orange" to items',
            'Say length(items)',
            'Say keys(user)',
        ],
    },
    {
        "id": "error_handling",
        "title": "Error Handling",
        "summary": "Try/Catch/Finally for errors, Throw to raise, Assert for checks.",
        "examples": [
            'Try\n    Set result to 10 / 0\nCatch error\n    Say "Error: " + error\nEnd',
            'Throw "Something went wrong"',
            'Assert count > 0',
        ],
    },
    {
        "id": "file_io",
        "title": "File I/O",
        "summary": "Write, Read, and Append for file operations.",
        "examples": [
            'Write "Hello" to file "output.txt"',
            'Set data to Read file "output.txt"',
            'Append "more" to file "output.txt"',
        ],
    },
    {
        "id": "imports",
        "title": "Imports And Python Bridge",
        "summary": "Import EPL modules with Import and Python modules with Use python.",
        "examples": [
            'Import "helpers.epl" as Helpers',
            'Import "epl-db"',
            'Use python "json" as json_mod',
            'Create payload = json_mod.loads("{\\"ok\\": true}")',
        ],
    },
    {
        "id": "oop",
        "title": "Classes And Objects",
        "summary": "Classes use Class ... End and instances use new ClassName().",
        "examples": [
            'Class User\n    Set name to "Anonymous"\n    Function greet\n        Return "Hello, " + name\n    End\nEnd',
            'Create user = new User()',
            'user.name = "Ada"',
            'Say user.greet()',
        ],
    },
    {
        "id": "enums_ternary",
        "title": "Enums And Ternary",
        "summary": "Enums define named constants. Ternary provides inline conditionals.",
        "examples": [
            'Enum Color Red, Green, Blue',
            'Set picked to Color.Red',
            'Set label = "big" if x > 10 otherwise "small"',
        ],
    },
    {
        "id": "web",
        "title": "Web Apps",
        "summary": "Native web apps use Create WebApp, Route, Page, Send json, and Start.",
        "examples": [
            'Create WebApp called myApp',
            'Route "/" shows\n    Store form "task" in "tasks"\n    Page "Home"\n        Heading "Welcome"\n        Text "Built with EPL"\n        Say items from "tasks" delete "/delete"\n    End\nEnd',
            'Route "/api/health" responds with\n    Send json Map with status = "ok"\nEnd',
            'Route "/api/tasks" responds with\n    Fetch "tasks"\nEnd',
            'Start myApp on port 8080',
        ],
    },
    {
        "id": "async",
        "title": "Async And Parallel",
        "summary": "Async, Await, Spawn, and Parallel are available for concurrent work.",
        "examples": [
            'Async Function fetchData takes url\n    Return url\nEnd',
            'Create result = Await fetchData("https://example.com")',
            'Spawn worker Call process with job',
            'Parallel For each item in items\n    Say item\nEnd',
        ],
    },
    {
        "id": "gui",
        "title": "GUI",
        "summary": "Desktop-style UI uses Window, layout blocks, and widgets.",
        "examples": [
            'Window "Demo" 800 by 600\n    Column\n        Label "Hello"\n        TextBox "name" placeholder "Enter your name"\n        Button "Save" does saveName\n    End\nEnd',
        ],
    },
    {
        "id": "misc",
        "title": "Miscellaneous",
        "summary": "Wait, Exit, and built-in functions.",
        "examples": [
            'Wait 2 seconds',
            'Exit',
            'Say length(items)',
            'Say type_of(42)',
            'Say to_text(100)',
        ],
    },
]


def get_syntax_sections():
    """Return structured syntax sections for UIs and assistants."""
    return deepcopy(_SYNTAX_SECTIONS)


def get_syntax_text() -> str:
    """Return a concise text guide for prompt construction and assistance."""
    lines = [
        "Authoritative EPL syntax reference:",
        "Use only parser-supported forms like the examples below.",
    ]
    for section in _SYNTAX_SECTIONS:
        lines.append("")
        lines.append(f"{section['title']}: {section['summary']}")
        for example in section["examples"]:
            lines.append(example)
    return "\n".join(lines)
