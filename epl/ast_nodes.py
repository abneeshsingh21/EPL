"""
EPL AST Node Definitions (v5.0)
Defines all Abstract Syntax Tree node types for EPL.
Includes Visitor pattern support — adding a new AST node only requires:
  1. Define the class here (inherits ASTNode, gets accept() automatically)
  2. Optionally add a visit_NodeName method to your visitor subclass
"""


class ASTNode:
    """Base class for all AST nodes."""

    def accept(self, visitor):
        """Double-dispatch to visitor.visit_<ClassName>(self).
        Falls back to visitor.generic_visit(self) if no specific method exists."""
        method_name = f"visit_{type(self).__name__}"
        method = getattr(visitor, method_name, None)
        if method is not None:
            return method(self)
        return visitor.generic_visit(self)


class ASTVisitor:
    """Base visitor class for the EPL AST.

    Subclass and override visit_<NodeName> methods for nodes you care about.
    Unhandled nodes fall through to generic_visit(), which by default visits
    all child nodes (depth-first traversal).

    Example:
        class PrintCounter(ASTVisitor):
            def __init__(self):
                self.count = 0
            def visit_PrintStatement(self, node):
                self.count += 1
    """

    def generic_visit(self, node):
        """Default handler: recursively visit child nodes that are ASTNode instances."""
        for attr in vars(node).values():
            if isinstance(attr, ASTNode):
                attr.accept(self)
            elif isinstance(attr, list):
                for item in attr:
                    if isinstance(item, ASTNode):
                        item.accept(self)

    def visit(self, node):
        """Entry point — dispatch to the node's accept method."""
        if node is not None:
            return node.accept(self)


class StrictASTVisitor(ASTVisitor):
    """Strict visitor that raises on any unhandled AST node.

    Use this as the base class for transpiler backends to guarantee
    that every AST node is explicitly handled. If a new node type is
    added to ast_nodes.py and a transpiler doesn't implement a visitor
    for it, compilation will fail immediately with a clear error instead
    of silently omitting code.
    """

    def generic_visit(self, node):
        raise NotImplementedError(
            f"{type(self).__name__} does not handle AST node: {type(node).__name__}. "
            f"Add a visit_{type(node).__name__} method to fix this."
        )



# ─── Program ──────────────────────────────────────────────

class Program(ASTNode):
    def __init__(self, statements: list):
        self.statements = statements

    def __repr__(self):
        return f"Program({len(self.statements)} statements)"


# ─── Variable Operations ─────────────────────────────────

class VarDeclaration(ASTNode):
    def __init__(self, name: str, value, var_type: str = None, line: int = 0):
        self.name = name
        self.value = value
        self.var_type = var_type
        self.line = line

    def __repr__(self):
        return f"VarDeclaration({self.name})"


class VarAssignment(ASTNode):
    def __init__(self, name: str, value, line: int = 0):
        self.name = name
        self.value = value
        self.line = line

    def __repr__(self):
        return f"VarAssignment({self.name})"


# ─── I/O ──────────────────────────────────────────────────

class PrintStatement(ASTNode):
    def __init__(self, expression, line: int = 0):
        self.expression = expression
        self.line = line


class InputStatement(ASTNode):
    def __init__(self, variable_name: str, prompt=None, line: int = 0):
        self.variable_name = variable_name
        self.prompt = prompt
        self.line = line


# ─── Control Flow ─────────────────────────────────────────

class IfStatement(ASTNode):
    def __init__(self, condition, then_body: list, else_body: list = None, line: int = 0):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body or []
        self.line = line


# ─── Loops ────────────────────────────────────────────────

class WhileLoop(ASTNode):
    def __init__(self, condition, body: list, line: int = 0):
        self.condition = condition
        self.body = body
        self.line = line


class RepeatLoop(ASTNode):
    def __init__(self, count, body: list, line: int = 0):
        self.count = count
        self.body = body
        self.line = line


class ForEachLoop(ASTNode):
    def __init__(self, var_name: str, iterable, body: list, line: int = 0):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body
        self.line = line


# ─── Functions ────────────────────────────────────────────

class FunctionDef(ASTNode):
    def __init__(self, name: str, params: list, return_type: str, body: list, line: int = 0):
        self.name = name
        # params: list of (name, type, default_expr) 3-tuples or (name, type) 2-tuples
        # Normalize to 3-tuples for consistency
        self.params = [
            p if isinstance(p, RestParameter) else
            (p[0], p[1] if len(p) > 1 else None, p[2] if len(p) > 2 else None)
            if isinstance(p, tuple) else (p, None, None)
            for p in params
        ]
        self.return_type = return_type
        self.body = body
        self.line = line


class FunctionCall(ASTNode):
    def __init__(self, name: str, arguments: list, line: int = 0):
        self.name = name
        self.arguments = arguments
        self.line = line


class ReturnStatement(ASTNode):
    def __init__(self, value=None, line: int = 0):
        self.value = value
        self.line = line


# ─── Expressions ──────────────────────────────────────────

class BinaryOp(ASTNode):
    def __init__(self, left, operator: str, right, line: int = 0):
        self.left = left
        self.operator = operator
        self.right = right
        self.line = line


class UnaryOp(ASTNode):
    def __init__(self, operator: str, operand, line: int = 0):
        self.operator = operator
        self.operand = operand
        self.line = line


class Literal(ASTNode):
    def __init__(self, value, line: int = 0):
        self.value = value
        self.line = line


class Identifier(ASTNode):
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line


class ListLiteral(ASTNode):
    def __init__(self, elements: list, line: int = 0):
        self.elements = elements
        self.line = line


# ─── v0.2: Dot Notation (Methods & Properties) ───────────

class MethodCall(ASTNode):
    """obj.method(args)  /  name.uppercase  /  items.add(5)"""
    def __init__(self, obj, method_name: str, arguments: list = None, line: int = 0):
        self.obj = obj          # Expression that produces the object
        self.method_name = method_name
        self.arguments = arguments or []
        self.line = line

    def __repr__(self):
        return f"MethodCall(.{self.method_name}, args={len(self.arguments)})"


class PropertyAccess(ASTNode):
    """obj.property — read a property from an object or value."""
    def __init__(self, obj, property_name: str, line: int = 0):
        self.obj = obj
        self.property_name = property_name
        self.line = line

    def __repr__(self):
        return f"PropertyAccess(.{self.property_name})"


class PropertySet(ASTNode):
    """obj.property = value — set a property on an object."""
    def __init__(self, obj, property_name: str, value, line: int = 0):
        self.obj = obj
        self.property_name = property_name
        self.value = value
        self.line = line

    def __repr__(self):
        return f"PropertySet(.{self.property_name})"


# ─── v0.2: File I/O ──────────────────────────────────────

class FileWrite(ASTNode):
    """Write "content" to file "path" """
    def __init__(self, content, filepath, line: int = 0):
        self.content = content
        self.filepath = filepath
        self.line = line


class FileRead(ASTNode):
    """Read file "path" — returns file content as text."""
    def __init__(self, filepath, line: int = 0):
        self.filepath = filepath
        self.line = line


class FileAppend(ASTNode):
    """Append "content" to file "path" """
    def __init__(self, content, filepath, line: int = 0):
        self.content = content
        self.filepath = filepath
        self.line = line


# ─── v0.2: Classes & OOP ─────────────────────────────────

class ClassDef(ASTNode):
    """Class Animal ... End"""
    def __init__(self, name: str, body: list, parent: str = None, implements: list = None, line: int = 0):
        self.name = name
        self.body = body         # list of VarDeclaration / FunctionDef
        self.parent = parent     # inheritance (future)
        self.implements = implements or []  # list of interface names
        self.line = line

    def __repr__(self):
        return f"ClassDef({self.name})"


class NewInstance(ASTNode):
    """new ClassName — creates an instance of a class."""
    def __init__(self, class_name: str, arguments: list = None, line: int = 0):
        self.class_name = class_name
        self.arguments = arguments or []
        self.line = line

    def __repr__(self):
        return f"NewInstance({self.class_name})"


# ─── v0.3: Try/Catch ─────────────────────────────────────

class TryCatch(ASTNode):
    """Try ... Catch error ... Finally ... End"""
    def __init__(self, try_body: list, error_var: str, catch_body: list, finally_body: list = None, line: int = 0):
        self.try_body = try_body
        self.error_var = error_var
        self.catch_body = catch_body
        self.finally_body = finally_body or []
        self.line = line


# ─── v0.3: Break / Continue ──────────────────────────────

class BreakStatement(ASTNode):
    def __init__(self, line: int = 0):
        self.line = line


class ContinueStatement(ASTNode):
    def __init__(self, line: int = 0):
        self.line = line


# ─── v0.3: Match/When ────────────────────────────────────

class WhenClause(ASTNode):
    """Single When clause inside a Match."""
    def __init__(self, values: list, body: list, line: int = 0):
        self.values = values      # list of expressions to match against
        self.body = body
        self.line = line


class MatchStatement(ASTNode):
    """Match expr ... When "value" ... Default ... End"""
    def __init__(self, expression, when_clauses: list, default_body: list = None, line: int = 0):
        self.expression = expression
        self.when_clauses = when_clauses
        self.default_body = default_body or []
        self.line = line


# ─── v0.3: Dictionary Literal ────────────────────────────

class DictLiteral(ASTNode):
    """Map with key = value and key2 = value2"""
    def __init__(self, pairs: list, line: int = 0):
        self.pairs = pairs   # list of (key_name: str, value: ASTNode)
        self.line = line

    def __repr__(self):
        return f"DictLiteral({len(self.pairs)} pairs)"


# ─── v0.3: Index Access ──────────────────────────────────

class IndexAccess(ASTNode):
    """items[0] — read element by index."""
    def __init__(self, obj, index, line: int = 0):
        self.obj = obj
        self.index = index
        self.line = line


class IndexSet(ASTNode):
    """items[0] = value — set element by index."""
    def __init__(self, obj, index, value, line: int = 0):
        self.obj = obj
        self.index = index
        self.value = value
        self.line = line


# ─── v0.3: For Range Loop ────────────────────────────────

class ForRange(ASTNode):
    """For i from 1 to 10 ... End  or  For i from 1 to 10 step 2 ... End"""
    def __init__(self, var_name: str, start, end, body: list, line: int = 0, step=None):
        self.var_name = var_name
        self.start = start
        self.end = end
        self.body = body
        self.line = line
        self.step = step


# ─── v0.3: Import / Use ──────────────────────────────────

class ImportStatement(ASTNode):
    """Import \"file.epl\"  or  Import \"math\" as Math"""
    def __init__(self, filepath: str, line: int = 0, alias: str = None):
        self.filepath = filepath
        self.line = line
        self.alias = alias


class UseStatement(ASTNode):
    """Use python \"library\" as alias"""
    def __init__(self, library: str, alias: str = None, line: int = 0):
        self.library = library
        self.alias = alias
        self.line = line


# ─── v0.3: Wait / Exit / Constant / Assert ───────────────

class WaitStatement(ASTNode):
    """Wait 2 seconds"""
    def __init__(self, duration, line: int = 0):
        self.duration = duration
        self.line = line


class ExitStatement(ASTNode):
    """Exit"""
    def __init__(self, line: int = 0):
        self.line = line


class ConstDeclaration(ASTNode):
    """Constant PI = 3.14"""
    def __init__(self, name: str, value, line: int = 0):
        self.name = name
        self.value = value
        self.line = line


class AssertStatement(ASTNode):
    """Assert expression"""
    def __init__(self, expression, line: int = 0):
        self.expression = expression
        self.line = line


# ─── v0.5: Web Framework ─────────────────────────────────

class WebApp(ASTNode):
    """Create WebApp called myApp"""
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line


class Route(ASTNode):
    """Route "/path" shows ... End  or  Route "/api" responds with ... End"""
    def __init__(self, path: str, response_type: str, body: list, line: int = 0):
        self.path = path
        self.response_type = response_type  # 'page' or 'json'
        self.body = body
        self.line = line


class StartServer(ASTNode):
    """Start myApp on port 3000"""
    def __init__(self, app_name: str, port, line: int = 0):
        self.app_name = app_name
        self.port = port
        self.line = line


class PageDef(ASTNode):
    """Page "title" ... End"""
    def __init__(self, title: str, elements: list, line: int = 0):
        self.title = title
        self.elements = elements
        self.line = line


class HtmlElement(ASTNode):
    """Heading "text", Text "text", Button "text" does action, etc."""
    def __init__(self, tag: str, content=None, attributes: dict = None, children: list = None, line: int = 0):
        self.tag = tag              # 'heading', 'text', 'button', 'input', etc.
        self.content = content      # text content or expression
        self.attributes = attributes or {}
        self.children = children or []
        self.line = line

    def __repr__(self):
        return f"HtmlElement({self.tag})"


class SendResponse(ASTNode):
    """Send json <expr>  or  Send text <expr>"""
    def __init__(self, response_type: str, data, line: int = 0):
        self.response_type = response_type  # 'json' or 'text'
        self.data = data
        self.line = line


class ScriptBlock(ASTNode):
    """Script ... End — client-side JavaScript"""
    def __init__(self, code: str, line: int = 0):
        self.code = code
        self.line = line


class StoreStatement(ASTNode):
    """Store form "field" in "collection"  or  Store value in "collection" """
    def __init__(self, collection: str, field_name: str = None, value=None, line: int = 0):
        self.collection = collection
        self.field_name = field_name
        self.value = value
        self.line = line


class FetchStatement(ASTNode):
    """Fetch "collection" — returns list of stored items"""
    def __init__(self, collection: str, line: int = 0):
        self.collection = collection
        self.line = line


class DeleteStatement(ASTNode):
    """Delete from "collection" at index"""
    def __init__(self, collection: str, index=None, line: int = 0):
        self.collection = collection
        self.index = index
        self.line = line


# ─── v0.6: Power Features ────────────────────────────────

class LambdaExpression(ASTNode):
    """lambda x, y -> x + y"""
    def __init__(self, params: list, body, line: int = 0):
        self.params = params
        self.body = body
        self.line = line


class AugmentedAssignment(ASTNode):
    """x += 1, x -= 1, x *= 2, x /= 2, x %= 3"""
    def __init__(self, name: str, operator: str, value, line: int = 0):
        self.name = name
        self.operator = operator
        self.value = value
        self.line = line


class SliceAccess(ASTNode):
    """list[start:end] or list[start:end:step]"""
    def __init__(self, obj, start, end, step=None, line: int = 0):
        self.obj = obj
        self.start = start
        self.end = end
        self.step = step
        self.line = line


class TernaryExpression(ASTNode):
    """true_expr if condition otherwise false_expr"""
    def __init__(self, true_expr, condition, false_expr, line: int = 0):
        self.true_expr = true_expr
        self.condition = condition
        self.false_expr = false_expr
        self.line = line


class EnumDef(ASTNode):
    """Define enum Color as Red, Green, Blue End"""
    def __init__(self, name: str, members: list, line: int = 0):
        self.name = name
        self.members = members
        self.line = line


class ThrowStatement(ASTNode):
    """Throw "error message" """
    def __init__(self, expression, line: int = 0):
        self.expression = expression
        self.line = line


# ─── v1.4: GUI Framework ─────────────────────────────────

class WindowCreate(ASTNode):
    """Window "title" [width x height] ... End"""
    def __init__(self, title, width=None, height=None, body=None, line: int = 0):
        self.title = title
        self.width = width
        self.height = height
        self.body = body or []
        self.line = line

class WidgetAdd(ASTNode):
    """Button "text" called btnName does action / Label "text" called lblName / etc."""
    def __init__(self, widget_type: str, text=None, name: str = None, action=None, properties: dict = None, line: int = 0):
        self.widget_type = widget_type  # 'button', 'label', 'input', 'textarea', 'checkbox', 'dropdown', 'slider', 'progress', 'canvas', 'image', 'listbox', 'tab', 'tree'
        self.text = text
        self.name = name
        self.action = action  # function name or lambda for event
        self.properties = properties or {}
        self.line = line

class LayoutBlock(ASTNode):
    """Row ... End / Column ... End"""
    def __init__(self, direction: str, children: list, line: int = 0):
        self.direction = direction  # 'row' or 'column'
        self.children = children
        self.line = line

class BindEvent(ASTNode):
    """Bind widgetName "click" to handlerFunc"""
    def __init__(self, widget_name: str, event_type: str, handler, line: int = 0):
        self.widget_name = widget_name
        self.event_type = event_type
        self.handler = handler
        self.line = line

class DialogShow(ASTNode):
    """Dialog "message" type "info" / Dialog "question" type "yesno" """
    def __init__(self, message, dialog_type: str = 'info', title=None, line: int = 0):
        self.message = message
        self.dialog_type = dialog_type
        self.title = title
        self.line = line

class MenuDef(ASTNode):
    """Menu "File" with items ... End"""
    def __init__(self, label: str, items: list, line: int = 0):
        self.label = label
        self.items = items  # list of (label, action) tuples
        self.line = line

class CanvasDraw(ASTNode):
    """Canvas draw rect/circle/line/text with properties"""
    def __init__(self, canvas_name: str, shape: str, properties: dict = None, line: int = 0):
        self.canvas_name = canvas_name
        self.shape = shape
        self.properties = properties or {}
        self.line = line


# ─── v1.4: Async/Await ───────────────────────────────────

class AsyncFunctionDef(ASTNode):
    """Async Function name takes params ... End"""
    def __init__(self, name: str, params: list, return_type: str, body: list, line: int = 0):
        self.name = name
        self.params = [(p[0], p[1], p[2] if len(p) > 2 else None) if isinstance(p, tuple) else (p, None, None) for p in params]
        self.return_type = return_type
        self.body = body
        self.line = line

class AwaitExpression(ASTNode):
    """Await someAsyncFunc()"""
    def __init__(self, expression, line: int = 0):
        self.expression = expression
        self.line = line

class SuperCall(ASTNode):
    """Super.method(args) or Super(args) for constructor"""
    def __init__(self, method_name: str = None, arguments: list = None, line: int = 0):
        self.method_name = method_name
        self.arguments = arguments or []
        self.line = line


# ─── v4.0: Production Features ────────────────────────────

class TryCatchFinally(ASTNode):
    """Try ... Catch [ErrorType] error ... Finally ... End"""
    def __init__(self, try_body: list, catch_clauses: list, finally_body: list = None, line: int = 0):
        # catch_clauses: list of (error_type: str|None, error_var: str, body: list)
        self.try_body = try_body
        self.catch_clauses = catch_clauses
        self.finally_body = finally_body or []
        self.line = line


class InterfaceDefNode(ASTNode):
    """Interface Printable ... End"""
    def __init__(self, name: str, methods: list, extends: list = None, line: int = 0):
        # methods: list of (name, params, return_type) — signatures only
        self.name = name
        self.methods = methods
        self.extends = extends or []
        self.line = line


class ImplementsClause(ASTNode):
    """Used in ClassDef to track implemented interfaces."""
    def __init__(self, interface_names: list, line: int = 0):
        self.interface_names = interface_names
        self.line = line


class ModuleDef(ASTNode):
    """Module MathUtils ... End"""
    def __init__(self, name: str, body: list, exports: list = None, line: int = 0):
        self.name = name
        self.body = body
        self.exports = exports or []  # list of exported names
        self.line = line


class ModuleAccess(ASTNode):
    """Module::function() or Module::variable"""
    def __init__(self, module_name: str, member_name: str, arguments: list = None, line: int = 0):
        self.module_name = module_name
        self.member_name = member_name
        self.arguments = arguments  # None = variable access, list = function call
        self.line = line


class ExportStatement(ASTNode):
    """Export functionName / Export variableName"""
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line


class TypeAnnotation(ASTNode):
    """Type annotation AST node: integer, text, List<integer>, Map<text, integer>, T?, A | B"""
    def __init__(self, base_type: str, params: list = None, is_optional: bool = False,
                 union_members: list = None, line: int = 0):
        self.base_type = base_type
        self.params = params or []          # generic params [TypeAnnotation]
        self.is_optional = is_optional
        self.union_members = union_members  # list of TypeAnnotation for union
        self.line = line


class GenericClassDef(ASTNode):
    """Class Stack<T> ... End"""
    def __init__(self, name: str, type_params: list, body: list, parent: str = None,
                 implements: list = None, line: int = 0):
        self.name = name
        self.type_params = type_params  # ['T', 'K', 'V', ...]
        self.body = body
        self.parent = parent
        self.implements = implements or []
        self.line = line


class AbstractMethodDef(ASTNode):
    """Abstract method signature in a class (no body)."""
    def __init__(self, name: str, params: list, return_type: str = None, line: int = 0):
        self.name = name
        self.params = [(p[0], p[1], p[2] if len(p) > 2 else None) if isinstance(p, tuple) else (p, None, None) for p in params]
        self.return_type = return_type
        self.line = line


class StaticMethodDef(ASTNode):
    """Static Function in a class — called on class, not instance."""
    def __init__(self, name: str, params: list, return_type: str, body: list, line: int = 0):
        self.name = name
        self.params = [(p[0], p[1], p[2] if len(p) > 2 else None) if isinstance(p, tuple) else (p, None, None) for p in params]
        self.return_type = return_type
        self.body = body
        self.line = line


class VisibilityModifier(ASTNode):
    """Wraps a statement with an access modifier: Public/Private/Protected."""
    def __init__(self, visibility: str, statement, line: int = 0):
        self.visibility = visibility  # 'public', 'private', 'protected'
        self.statement = statement
        self.line = line


class YieldStatement(ASTNode):
    """Yields value — for generator functions."""
    def __init__(self, value=None, line: int = 0):
        self.value = value
        self.line = line


class DestructureAssignment(ASTNode):
    """Create [a, b, c] equal to someList"""
    def __init__(self, names: list, value, line: int = 0):
        self.names = names
        self.value = value
        self.line = line


class SpreadExpression(ASTNode):
    """...list — spread list elements."""
    def __init__(self, expression, line: int = 0):
        self.expression = expression
        self.line = line


class RestParameter:
    """Marker for rest/varargs parameter in function definition."""
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line


class ChainedComparison(ASTNode):
    """a < b < c — chained comparisons."""
    def __init__(self, operands: list, operators: list, line: int = 0):
        self.operands = operands
        self.operators = operators
        self.line = line


# ─── v5.1: Production Power Features ─────────────────────

class SpawnStatement(ASTNode):
    """Spawn task_name calling func(args)
    Launches a function call on a background thread, returns a future."""
    def __init__(self, var_name: str, expression, line: int = 0):
        self.var_name = var_name
        self.expression = expression  # FunctionCall to run in background
        self.line = line


class ParallelForEach(ASTNode):
    """Parallel For Each item in collection ... End
    Executes loop body concurrently across items."""
    def __init__(self, var_name: str, iterable, body: list, max_workers: int = None, line: int = 0):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body
        self.max_workers = max_workers
        self.line = line


class BreakpointStatement(ASTNode):
    """Breakpoint — programmatic debugger breakpoint."""
    def __init__(self, condition=None, line: int = 0):
        self.condition = condition  # optional conditional expression
        self.line = line


# ─── v5.2: Triple Ecosystem (Python Bridge + C FFI + Stdlib) ─────────────────

class ExternalFunctionDef(ASTNode):
    """External function declaration for C FFI.
    Syntax: External function sqrt from "libm" takes (double) returns double
    """
    def __init__(self, name: str, library: str, param_types: list,
                 return_type: str, alias: str = None, line: int = 0):
        self.name = name
        self.library = library
        self.param_types = param_types  # list of C type strings
        self.return_type = return_type  # C type string
        self.alias = alias  # optional EPL alias name
        self.line = line


class LoadLibrary(ASTNode):
    """Load a shared library for C FFI.
    Syntax: Load library "path" as name
    """
    def __init__(self, path: str, alias: str, line: int = 0):
        self.path = path
        self.alias = alias
        self.line = line

