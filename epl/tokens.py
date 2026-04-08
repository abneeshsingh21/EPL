"""
EPL Token Definitions
Defines all token types and the Token class used by the lexer.
"""

from enum import Enum, auto


class TokenType(Enum):
    # --- Literals ---
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    BOOLEAN_TRUE = auto()
    BOOLEAN_FALSE = auto()
    NOTHING = auto()

    # --- Keywords: Variable Operations ---
    CREATE = auto()
    SET = auto()
    TO = auto()
    EQUAL = auto()
    NAMED = auto()
    VARIABLE = auto()
    OF = auto()
    TYPE = auto()
    AS = auto()
    REMEMBER = auto()       # v0.7: English alias for Create

    # --- Keywords: Type Names ---
    TYPE_INTEGER = auto()
    TYPE_DECIMAL = auto()
    TYPE_TEXT = auto()
    TYPE_BOOLEAN = auto()
    TYPE_LIST = auto()

    # --- Keywords: I/O ---
    PRINT = auto()
    INPUT = auto()
    DISPLAY = auto()
    SHOW = auto()
    SAY = auto()            # v0.7: English alias for Print
    ASK = auto()            # v0.7: English alias for Input

    # --- Keywords: Control Flow ---
    IF = auto()
    THEN = auto()
    OTHERWISE = auto()
    END = auto()

    # --- Keywords: Loops ---
    REPEAT = auto()
    TIMES = auto()
    WHILE = auto()
    FOR = auto()
    EACH = auto()
    IN = auto()
    FROM = auto()
    BY = auto()

    # --- Keywords: Functions ---
    DEFINE = auto()
    FUNCTION = auto()
    CALL = auto()
    WITH = auto()
    RETURN = auto()
    RETURNS = auto()
    TAKES = auto()
    THAT = auto()
    A = auto()
    AN = auto()
    THE = auto()

    # --- Keywords: Classes & OOP ---
    CLASS = auto()
    NEW = auto()
    THIS = auto()

    # --- Keywords: File I/O ---
    WRITE = auto()
    READ = auto()
    APPEND = auto()
    FILE = auto()

    # --- Keywords: v0.3 ---
    TRY = auto()
    CATCH = auto()
    BREAK = auto()
    CONTINUE = auto()
    MATCH = auto()
    WHEN = auto()
    DEFAULT = auto()
    EXTENDS = auto()
    MAP = auto()
    IMPORT = auto()
    USE = auto()
    PYTHON = auto()
    CONSTANT = auto()
    ASSERT = auto()
    WAIT = auto()
    SECONDS = auto()
    EXIT_KW = auto()
    NOTEBLOCK = auto()

    # --- Keywords: v0.5 Web Framework ---
    ROUTE = auto()
    WEBAPP = auto()
    START = auto()
    PAGE = auto()
    HEADING = auto()
    SUBHEADING = auto()
    LINK = auto()
    IMAGE = auto()
    BUTTON = auto()
    FORM = auto()
    SEND = auto()
    JSON = auto()
    PORT = auto()
    DOES = auto()
    SCRIPT = auto()
    RESPONDS = auto()
    SHOWS = auto()
    ON = auto()
    CALLED = auto()
    ACTION = auto()
    PLACEHOLDER = auto()
    STORE = auto()
    FETCH = auto()
    DELETE_KW = auto()
    REDIRECT = auto()
    AT = auto()

    # --- v0.6: Power Features ---
    OP_POWER = auto()           # **
    OP_FLOOR_DIV = auto()       # //
    OP_PLUS_ASSIGN = auto()     # +=
    OP_MINUS_ASSIGN = auto()    # -=
    OP_MUL_ASSIGN = auto()      # *=
    OP_DIV_ASSIGN = auto()      # /=
    OP_MOD_ASSIGN = auto()      # %=
    ARROW = auto()              # ->
    LAMBDA = auto()
    ENUM = auto()
    STEP = auto()
    THROW = auto()
    TYPEOF = auto()

    # --- v0.7: English Simplicity ---
    RAISED = auto()             # "raised to" = power
    BETWEEN = auto()            # "is between X and Y"
    ADD_KW = auto()             # "Add X to list"
    SORT_KW = auto()            # "Sort list"
    REVERSE_KW = auto()         # "Reverse list"

    # --- v0.7.1: Simplified Operators ---
    MOD_KW = auto()             # "mod" = %
    EQUALS_KW = auto()          # "equals" = ==
    NOT_EQUALS = auto()         # "not equals" = !=
    DOES_NOT_EQUAL = auto()     # "does not equal" = !=
    AT_LEAST = auto()           # "at least" / "is at least" = >=
    AT_MOST = auto()            # "at most" / "is at most" = <=
    MULTIPLY_KW = auto()        # "Multiply X by Y" = *=
    DIVIDE_KW = auto()          # "Divide X by Y" = /=
    GIVEN = auto()              # "given x return expr" = lambda

    # --- v1.4: GUI Framework ---
    WINDOW = auto()             # "Window"
    WIDGET = auto()             # widget identifier
    CANVAS_KW = auto()          # "Canvas"
    DIALOG = auto()             # "Dialog"
    LAYOUT = auto()             # "Layout"
    ROW = auto()                # "Row"
    COLUMN = auto()             # "Column"
    MENU_KW = auto()            # "Menu"
    BIND = auto()               # "Bind"
    LABEL = auto()              # "Label"
    TEXTBOX = auto()            # "TextBox"
    CHECKBOX_KW = auto()        # "Checkbox"
    DROPDOWN_KW = auto()        # "Dropdown"
    SLIDER_KW = auto()          # "Slider"
    PROGRESS_KW = auto()        # "Progress"
    TEXTAREA_KW = auto()        # "TextArea"
    TAB = auto()                # "Tab"
    TREE = auto()               # "Tree"

    # --- v1.4: Async/Await ---
    ASYNC = auto()              # "async"
    AWAIT = auto()              # "await"
    SUPER = auto()              # "super"

    # --- v4.0: Production Features ---
    INTERFACE = auto()          # "Interface"
    IMPLEMENTS = auto()         # "implements"
    ABSTRACT = auto()           # "abstract"
    FINALLY = auto()            # "Finally"
    MODULE = auto()             # "Module"
    EXPORT = auto()             # "Export"
    PRIVATE = auto()            # "Private"
    PUBLIC = auto()             # "Public"
    PROTECTED = auto()          # "Protected"
    STATIC = auto()             # "Static"
    LBRACE = auto()             # {
    RBRACE = auto()             # }
    PIPE = auto()               # |  (union types)
    QUESTION = auto()           # ?  (optional types)
    LANGLE = auto()             # <  (generics)
    RANGLE = auto()             # >  (generics)
    DOUBLE_COLON = auto()       # :: (namespace access)
    YIELDS = auto()             # "Yields"
    GENERIC = auto()            # "Generic"
    WHERE = auto()              # "Where"
    OVERRIDE = auto()           # "Override"
    REST = auto()               # "rest" (varargs)

    # --- v5.1: Production Power Features ---
    SPAWN = auto()              # "Spawn"
    PARALLEL = auto()           # "Parallel"
    BREAKPOINT_KW = auto()      # "Breakpoint"

    # --- v5.2: Triple Ecosystem (Python Bridge + C FFI + Stdlib) ---
    EXTERNAL = auto()           # "External"
    LIBRARY = auto()            # "Library"

    # --- Keywords: Logical ---
    AND = auto()
    OR = auto()
    NOT = auto()

    # --- Keywords: English Comparison Phrases ---
    IS = auto()
    GREATER = auto()
    LESS = auto()
    THAN = auto()
    NOT_KW = auto()

    # --- Keywords: Math English ---
    PLUS = auto()
    MINUS = auto()
    INCREASE = auto()
    DECREASE = auto()

    # --- Symbolic Operators ---
    OP_PLUS = auto()        # +
    OP_MINUS = auto()       # -
    OP_MULTIPLY = auto()    # *
    OP_DIVIDE = auto()      # /
    OP_MODULO = auto()      # %
    OP_ASSIGN = auto()      # =

    # --- Comparison Operators ---
    OP_EQUAL = auto()       # ==
    OP_NOT_EQUAL = auto()   # !=
    OP_GREATER = auto()     # >
    OP_LESS = auto()        # <
    OP_GREATER_EQ = auto()  # >=
    OP_LESS_EQ = auto()     # <=

    # --- Delimiters ---
    DOT = auto()            # .
    COMMA = auto()          # ,
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    COLON = auto()          # :

    # --- Special ---
    NEWLINE = auto()
    EOF = auto()
    COMMENT = auto()

    # --- Compound Keywords (resolved by lexer) ---
    IS_GREATER_THAN = auto()
    IS_LESS_THAN = auto()
    IS_EQUAL_TO = auto()
    IS_NOT_EQUAL_TO = auto()
    IS_GREATER_THAN_OR_EQUAL_TO = auto()
    IS_LESS_THAN_OR_EQUAL_TO = auto()
    END_IF = auto()
    END_WHILE = auto()
    END_REPEAT = auto()
    END_FOR = auto()
    END_FUNCTION = auto()


class Token:
    """Represents a single token produced by the lexer."""

    def __init__(self, token_type: TokenType, value, line: int, column: int):
        self.type = token_type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line})"

    def __eq__(self, other):
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value
        return False


# Mapping of single-word keywords (case-insensitive) to token types
KEYWORDS = {
    "create": TokenType.CREATE,
    "set": TokenType.SET,
    "to": TokenType.TO,
    "equal": TokenType.EQUAL,
    "named": TokenType.NAMED,
    "variable": TokenType.VARIABLE,
    "of": TokenType.OF,
    "type": TokenType.TYPE,
    "as": TokenType.AS,
    "integer": TokenType.TYPE_INTEGER,
    "decimal": TokenType.TYPE_DECIMAL,
    "text": TokenType.TYPE_TEXT,
    "boolean": TokenType.TYPE_BOOLEAN,
    "list": TokenType.TYPE_LIST,
    "print": TokenType.PRINT,
    "input": TokenType.INPUT,
    "display": TokenType.DISPLAY,
    "show": TokenType.SHOW,
    "if": TokenType.IF,
    "then": TokenType.THEN,
    "otherwise": TokenType.OTHERWISE,
    "end": TokenType.END,
    "repeat": TokenType.REPEAT,
    "times": TokenType.TIMES,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "each": TokenType.EACH,
    "in": TokenType.IN,
    "from": TokenType.FROM,
    "by": TokenType.BY,
    "define": TokenType.DEFINE,
    "function": TokenType.FUNCTION,
    "call": TokenType.CALL,
    "with": TokenType.WITH,
    "return": TokenType.RETURN,
    "returns": TokenType.RETURNS,
    "takes": TokenType.TAKES,
    "that": TokenType.THAT,
    "a": TokenType.A,
    "an": TokenType.AN,
    "the": TokenType.THE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "is": TokenType.IS,
    "greater": TokenType.GREATER,
    "less": TokenType.LESS,
    "than": TokenType.THAN,
    "plus": TokenType.PLUS,
    "minus": TokenType.MINUS,
    "increase": TokenType.INCREASE,
    "decrease": TokenType.DECREASE,
    "true": TokenType.BOOLEAN_TRUE,
    "false": TokenType.BOOLEAN_FALSE,
    "nothing": TokenType.NOTHING,
    "class": TokenType.CLASS,
    "new": TokenType.NEW,
    "this": TokenType.THIS,
    "write": TokenType.WRITE,
    "read": TokenType.READ,
    "append": TokenType.APPEND,
    "file": TokenType.FILE,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "match": TokenType.MATCH,
    "when": TokenType.WHEN,
    "default": TokenType.DEFAULT,
    "extends": TokenType.EXTENDS,
    "map": TokenType.MAP,
    "import": TokenType.IMPORT,
    "use": TokenType.USE,
    "python": TokenType.PYTHON,
    "constant": TokenType.CONSTANT,
    "assert": TokenType.ASSERT,
    "wait": TokenType.WAIT,
    "seconds": TokenType.SECONDS,
    "exit": TokenType.EXIT_KW,
    "comment": TokenType.COMMENT,
    "noteblock": TokenType.NOTEBLOCK,
    "route": TokenType.ROUTE,
    "webapp": TokenType.WEBAPP,
    "start": TokenType.START,
    "page": TokenType.PAGE,
    "heading": TokenType.HEADING,
    "subheading": TokenType.SUBHEADING,
    "link": TokenType.LINK,
    "image": TokenType.IMAGE,
    "button": TokenType.BUTTON,
    "form": TokenType.FORM,
    "send": TokenType.SEND,
    "json": TokenType.JSON,
    "port": TokenType.PORT,
    "does": TokenType.DOES,
    "script": TokenType.SCRIPT,
    "responds": TokenType.RESPONDS,
    "shows": TokenType.SHOWS,
    "on": TokenType.ON,
    "called": TokenType.CALLED,
    "action": TokenType.ACTION,
    "placeholder": TokenType.PLACEHOLDER,
    "store": TokenType.STORE,
    "fetch": TokenType.FETCH,
    "delete": TokenType.DELETE_KW,
    "redirect": TokenType.REDIRECT,
    "at": TokenType.AT,
    "say": TokenType.SAY,
    "ask": TokenType.ASK,
    "remember": TokenType.REMEMBER,
    "raised": TokenType.RAISED,
    "between": TokenType.BETWEEN,
    "add": TokenType.ADD_KW,
    "sort": TokenType.SORT_KW,
    "reverse": TokenType.REVERSE_KW,
    "mod": TokenType.MOD_KW,
    "equals": TokenType.EQUALS_KW,
    "multiply": TokenType.MULTIPLY_KW,
    "divide": TokenType.DIVIDE_KW,
    "given": TokenType.GIVEN,
    "yes": TokenType.BOOLEAN_TRUE,
    "no": TokenType.BOOLEAN_FALSE,
    "lambda": TokenType.LAMBDA,
    "enum": TokenType.ENUM,
    "step": TokenType.STEP,
    "throw": TokenType.THROW,
    "typeof": TokenType.TYPEOF,
    "window": TokenType.WINDOW,
    "canvas": TokenType.CANVAS_KW,
    "dialog": TokenType.DIALOG,
    "layout": TokenType.LAYOUT,
    "row": TokenType.ROW,
    "column": TokenType.COLUMN,
    "bind": TokenType.BIND,
    "label": TokenType.LABEL,
    "textbox": TokenType.TEXTBOX,
    "checkbox": TokenType.CHECKBOX_KW,
    "dropdown": TokenType.DROPDOWN_KW,
    "slider": TokenType.SLIDER_KW,
    "progress": TokenType.PROGRESS_KW,
    "textarea": TokenType.TEXTAREA_KW,
    "tab": TokenType.TAB,
    "tree": TokenType.TREE,
    "async": TokenType.ASYNC,
    "await": TokenType.AWAIT,
    "super": TokenType.SUPER,
    "menu": TokenType.MENU_KW,
    # v4.0: Production keywords
    "interface": TokenType.INTERFACE,
    "implements": TokenType.IMPLEMENTS,
    "abstract": TokenType.ABSTRACT,
    "finally": TokenType.FINALLY,
    "module": TokenType.MODULE,
    "export": TokenType.EXPORT,
    "private": TokenType.PRIVATE,
    "public": TokenType.PUBLIC,
    "protected": TokenType.PROTECTED,
    "static": TokenType.STATIC,
    "yields": TokenType.YIELDS,
    "generic": TokenType.GENERIC,
    "where": TokenType.WHERE,
    "override": TokenType.OVERRIDE,
    "rest": TokenType.REST,
    # v5.1: Production Power keywords
    "spawn": TokenType.SPAWN,
    "parallel": TokenType.PARALLEL,
    "breakpoint": TokenType.BREAKPOINT_KW,
    # v5.2: Triple Ecosystem keywords
    "external": TokenType.EXTERNAL,
    "library": TokenType.LIBRARY,
}

# Multi-word keyword phrases (checked in order, longest first)
MULTI_WORD_KEYWORDS = [
    (["is", "greater", "than", "or", "equal", "to"], TokenType.IS_GREATER_THAN_OR_EQUAL_TO),
    (["is", "less", "than", "or", "equal", "to"], TokenType.IS_LESS_THAN_OR_EQUAL_TO),
    (["is", "not", "equal", "to"], TokenType.IS_NOT_EQUAL_TO),
    (["is", "greater", "than"], TokenType.IS_GREATER_THAN),
    (["is", "less", "than"], TokenType.IS_LESS_THAN),
    (["is", "equal", "to"], TokenType.IS_EQUAL_TO),
    (["end", "function"], TokenType.END_FUNCTION),
    (["end", "repeat"], TokenType.END_REPEAT),
    (["end", "while"], TokenType.END_WHILE),
    (["end", "for"], TokenType.END_FOR),
    (["end", "if"], TokenType.END_IF),
    # v0.7: English power keyword
    (["raised", "to"], TokenType.OP_POWER),
    # v0.7.1: Simplified comparison phrases
    (["is", "at", "least"], TokenType.AT_LEAST),
    (["is", "at", "most"], TokenType.AT_MOST),
    (["does", "not", "equal"], TokenType.DOES_NOT_EQUAL),
    (["not", "equals"], TokenType.NOT_EQUALS),
    (["at", "least"], TokenType.AT_LEAST),
    (["at", "most"], TokenType.AT_MOST),
]
