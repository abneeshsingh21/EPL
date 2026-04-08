"""
EPL Interpreter (v0.3 Complete)
Full interpreter with: variables, functions, classes, OOP, built-ins,
string/list methods, file I/O, string templates, try/catch, break/continue,
match/when, dictionaries, index access, for-range, import, python bridge,
wait, exit, constants, assert.
"""

import random as _random
import re as _re
import time as _time
import sys as _sys
import os as _os
import importlib as _importlib
import subprocess as _subprocess
import concurrent.futures as _futures
import threading as _threading
import functools as _functools

from epl import ast_nodes as ast
from epl.environment import Environment
from epl.errors import (
    RuntimeError as EPLRuntimeError,
    TypeError as EPLTypeError,
    NameError as EPLNameError,
    EPLError,
    _did_you_mean,
)
from epl.stdlib import STDLIB_FUNCTIONS, call_stdlib

# Builtins disabled in safe/sandbox mode
_UNSAFE_BUILTINS = frozenset({
    'exec', 'exec_output', 'file_write', 'file_delete', 'file_append',
    'dir_delete', 'dir_create', 'chdir', 'env_set', 'env_get',
    'download', 'http_get', 'http_post',
})


# ─── Signals ─────────────────────────────────────────────

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class BreakSignal(Exception):
    pass

class ContinueSignal(Exception):
    pass

class ExitSignal(Exception):
    pass


# ─── Async Runtime ────────────────────────────────────────

import asyncio as _asyncio
import threading as _threading

_thread_pool = _futures.ThreadPoolExecutor(max_workers=16)

# Dedicated event loop running in a background thread for true async I/O
_async_loop = None
_async_loop_thread = None
_async_loop_lock = _threading.Lock()


def _get_async_loop():
    """Get or create the shared asyncio event loop (runs in background thread)."""
    global _async_loop, _async_loop_thread
    with _async_loop_lock:
        if _async_loop is None or not _async_loop.is_running():
            _async_loop = _asyncio.new_event_loop()

            def _run_loop():
                _asyncio.set_event_loop(_async_loop)
                _async_loop.run_forever()

            _async_loop_thread = _threading.Thread(
                target=_run_loop, daemon=True, name='epl-async-loop'
            )
            _async_loop_thread.start()
    return _async_loop


class EPLFuture:
    """Wraps a concurrent.futures.Future or asyncio.Future for EPL async/await."""
    def __init__(self, future, name='<async>'):
        self.future = future
        self.name = name

    def result(self, timeout=None):
        if isinstance(self.future, _asyncio.Task):
            loop = _get_async_loop()
            concurrent_future = _asyncio.run_coroutine_threadsafe(
                self._await_task(), loop
            )
            return concurrent_future.result(timeout=timeout)
        return self.future.result(timeout=timeout)

    async def _await_task(self):
        return await self.future

    def is_done(self):
        if isinstance(self.future, _asyncio.Task):
            return self.future.done()
        return self.future.done()

    def __repr__(self):
        return f"<future:{self.name}>"


class EPLGenerator:
    """
    A generator that produces values via yield.
    Uses a background thread with synchronization events to implement
    cooperative suspend/resume at yield points.
    """
    _active_generators = []
    _gen_lock = _threading.Lock()

    def __init__(self, interpreter, body, env, name='<generator>'):
        self.interpreter = interpreter
        self.body = body
        self.env = env
        self.name = name
        self._exhausted = False
        self._value_ready = _threading.Event()
        self._resume = _threading.Event()
        self._current_value = None
        self._error = None
        self._thread = None
        self._started = False
        self._closed = False
        with EPLGenerator._gen_lock:
            EPLGenerator._active_generators.append(self)

    def _run_body(self):
        """Execute the generator body in a background thread, pausing at yields."""
        # Store the generator reference in the environment so _exec_yield can find it
        self.env.define_variable('__generator__', self)
        try:
            self.interpreter._exec_block(self.body, self.env)
        except ReturnSignal:
            pass
        except _GeneratorClose:
            pass
        except Exception as e:
            if not isinstance(e, self.interpreter._YieldSignal):
                self._error = e
        finally:
            self._exhausted = True
            self._value_ready.set()

    def yield_value(self, value):
        """Called from _exec_yield when inside a generator context."""
        if self._closed:
            raise _GeneratorClose()
        self._current_value = value
        self._value_ready.set()
        self._resume.wait()
        self._resume.clear()
        if self._closed:
            raise _GeneratorClose()

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        """Get next yielded value."""
        if self._exhausted:
            raise StopIteration

        if not self._started:
            self._started = True
            self._thread = _threading.Thread(target=self._run_body, daemon=True)
            self._thread.start()
        else:
            self._resume.set()

        self._value_ready.wait(timeout=30)
        self._value_ready.clear()

        if self._error:
            raise self._error
        if self._exhausted:
            raise StopIteration

        return self._current_value

    def close(self):
        """Explicitly close this generator and clean up its thread."""
        if self._closed or self._exhausted:
            return
        self._closed = True
        self._resume.set()  # unblock the thread so it can exit
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._exhausted = True
        self._remove_from_active()

    def _remove_from_active(self):
        with EPLGenerator._gen_lock:
            try:
                EPLGenerator._active_generators.remove(self)
            except ValueError:
                pass

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        self.close()

    def to_list(self):
        """Collect all yielded values into a list."""
        result = []
        for val in self:
            result.append(val)
        self._remove_from_active()
        return result

    @classmethod
    def cleanup_all(cls):
        """Close all active generators. Called during interpreter shutdown."""
        with cls._gen_lock:
            gens = list(cls._active_generators)
            cls._active_generators.clear()
        for g in gens:
            g.close()

    def __repr__(self):
        return f"<generator:{self.name}>"


class _GeneratorClose(BaseException):
    """Signal to terminate a generator thread cleanly."""
    pass


class RouteResponseSignal(Exception):
    """Internal signal used by the web runtime to short-circuit route execution."""

    def __init__(self, response_type, payload):
        self.response_type = response_type
        self.payload = payload


# ─── OOP Runtime ─────────────────────────────────────────

class EPLClass:
    def __init__(self, name, defaults, methods, parent=None, visibility_map=None):
        self.name = name
        self.defaults = defaults
        self.methods = methods
        self.parent = parent
        self.visibility_map = visibility_map or {}  # {member_name: 'public'|'private'|'protected'}

    def get_visibility(self, member_name):
        """Get the visibility of a member, checking parent classes if needed."""
        if member_name in self.visibility_map:
            return self.visibility_map[member_name]
        if self.parent and isinstance(self.parent, EPLClass):
            return self.parent.get_visibility(member_name)
        return 'public'  # default is public

    def __repr__(self):
        return f"<class {self.name}>"


class EPLInstance:
    def __init__(self, klass):
        self.klass = klass
        self.properties = {}
        self._collect_defaults(klass)

    def _collect_defaults(self, klass):
        if klass.parent:
            self._collect_defaults(klass.parent)
        self.properties.update(klass.defaults)

    def get_method(self, name):
        klass = self.klass
        while klass:
            if name in klass.methods:
                return klass.methods[name]
            klass = klass.parent
        return None

    def __repr__(self):
        return f"<{self.klass.name} instance>"


# ─── Dictionary Runtime ──────────────────────────────────

class EPLDict:
    def __init__(self, data=None):
        self.data = data or {}

    def __repr__(self):
        return str(self.data)


# ─── Python Bridge Wrapper ───────────────────────────────

class PythonModule:
    """Wraps a Python module/class/namespace for use in EPL with deep attribute chaining."""
    def __init__(self, module, name):
        self.module = module
        self.name = name

    def get_attr(self, attr_name):
        """Get attribute, wrapping sub-modules and classes for chaining.
        Raises AttributeError for missing attributes instead of returning None."""
        if not hasattr(self.module, attr_name):
            raise AttributeError(
                f'{self.name} has no attribute "{attr_name}".'
            )
        attr = getattr(self.module, attr_name)
        # Wrap sub-modules and classes so chaining works: mod.sub.func()
        if isinstance(attr, type) or (hasattr(attr, '__module__') and hasattr(attr, '__dict__') and not callable(attr)):
            return PythonModule(attr, f"{self.name}.{attr_name}")
        return attr

    def __repr__(self):
        return f"<python module {self.name}>"


class EPLLambda:
    """Runtime representation of a lambda expression."""
    def __init__(self, params, body_node, closure_env):
        self.params = params
        self.body_node = body_node
        self.closure_env = closure_env

    def __repr__(self):
        return f"<lambda({', '.join(self.params)})>"


# ─── Deprecation Registry ────────────────────────────────

# Maps deprecated function name → (replacement, version_removed, message)
DEPRECATED_FUNCTIONS = {
    # Example entries — add real deprecations here as functions are superseded:
    # 'old_func': ('new_func', '6.0', 'Use new_func() instead.'),
}

# Track which deprecation warnings have already been emitted this session
_deprecation_warned = set()


def _check_deprecation(name: str, line: int = None):
    """Emit a deprecation warning if `name` is deprecated. Warns once per name per session."""
    if name not in DEPRECATED_FUNCTIONS:
        return
    if name in _deprecation_warned:
        return
    _deprecation_warned.add(name)
    replacement, version_removed, message = DEPRECATED_FUNCTIONS[name]
    loc = f" (line {line})" if line else ""
    import sys
    print(
        f"  DeprecationWarning{loc}: '{name}()' is deprecated and will be removed in v{version_removed}. {message}",
        file=sys.stderr,
    )


def reset_deprecation_warnings():
    """Reset the set of already-warned deprecations (for testing)."""
    _deprecation_warned.clear()


# ─── Built-in Functions ──────────────────────────────────

BUILTINS = {
    'length', 'type_of',
    'to_integer', 'to_text', 'to_decimal', 'to_boolean',
    'absolute', 'round', 'max', 'min', 'random', 'random_seed',
    'uppercase', 'lowercase',
    # v0.6: Math
    'sqrt', 'power', 'floor', 'ceil', 'log', 'sin', 'cos', 'tan',
    # v0.6: Collections
    'range', 'sum', 'sorted', 'reversed', 'keys', 'values',
    # v0.6: Type checking
    'is_integer', 'is_decimal', 'is_text', 'is_boolean',
    'is_list', 'is_map', 'is_nothing', 'is_number',
    # v0.6: Utility
    'json_parse', 'json_stringify', 'char_code', 'from_char_code',
    'timestamp', 'typeof',
    # v5.0: C FFI
    'ffi_open', 'ffi_call', 'ffi_close', 'ffi_find', 'ffi_types',
} | STDLIB_FUNCTIONS  # Merge standard library functions


_TEMPLATE_RE = _re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)')

# Module-level operator dispatch tables (avoid re-creating per call)
_OP_DUNDER = {
    '+': '__add__', '-': '__sub__', '*': '__mul__', '/': '__div__',
    '%': '__mod__', '**': '__pow__', '//': '__floordiv__',
    '==': '__eq__', '!=': '__ne__', '<': '__lt__', '>': '__gt__',
    '<=': '__le__', '>=': '__ge__',
}
_OP_REFLECTED = {
    '+': '__radd__', '-': '__rsub__', '*': '__rmul__', '/': '__rdiv__',
}


class Interpreter:
    """Executes an EPL AST."""

    MAX_LOOP_ITERATIONS = 10_000_000  # configurable per interpreter instance
    MAX_CALL_DEPTH = 500  # Maximum function call recursion depth
    MAX_OUTPUT_LINES = 100_000  # maximum output lines before truncation
    MAX_INSTRUCTIONS = 50_000_000  # maximum executed statements (0 = unlimited)
    EXECUTION_TIMEOUT = 0  # maximum execution time in seconds (0 = unlimited)

    def __init__(self, safe_mode=False, block_scoping=False,
                 max_instructions=0, execution_timeout=0, max_output_lines=0,
                 debug_interactive=True):
        self.global_env = Environment(name="global")
        self.output_lines = []
        self._constants = set()  # track constant names
        self._imported_files = set()  # prevent circular imports
        self._template_cache = {}  # cache parsed template expressions
        self._ast_cache = {}  # cache parsed ASTs for imports (path → Program)
        self._call_depth = 0  # recursion guard
        self.safe_mode = safe_mode  # restrict dangerous builtins
        self.block_scoping = block_scoping  # if True, if/while/for/repeat create child scopes
        self._debug_interactive = debug_interactive  # allow Breakpoint to enter interactive REPL
        # Resource limits
        self._instruction_count = 0
        self._max_instructions = max_instructions or (self.MAX_INSTRUCTIONS if safe_mode else 0)
        self._max_output_lines = max_output_lines or (self.MAX_OUTPUT_LINES if safe_mode else 0)
        self._execution_timeout = execution_timeout or (self.EXECUTION_TIMEOUT if safe_mode else 0)
        self._start_time = 0.0
        self._stmt_dispatch = self._build_stmt_dispatch()
        self._expr_dispatch = self._build_expr_dispatch()
        self._yield_cache = {}  # cache _func_contains_yield results
        self._route_response_enabled = False

    def _build_stmt_dispatch(self):
        """Build O(1) dispatch table for statement execution."""
        return {
            ast.VarDeclaration: self._exec_var_declaration,
            ast.VarAssignment: self._exec_var_assignment,
            ast.PrintStatement: self._exec_print,
            ast.InputStatement: self._exec_input,
            ast.IfStatement: self._exec_if,
            ast.WhileLoop: self._exec_while,
            ast.RepeatLoop: self._exec_repeat,
            ast.ForEachLoop: self._exec_for_each,
            ast.ForRange: self._exec_for_range,
            ast.FunctionDef: self._exec_function_def,
            ast.FunctionCall: self._exec_function_call,
            ast.ReturnStatement: self._exec_return,
            ast.FileWrite: self._exec_file_write,
            ast.FileAppend: self._exec_file_append,
            ast.ClassDef: self._exec_class_def,
            ast.PropertySet: self._exec_property_set,
            ast.IndexSet: self._exec_index_set,
            ast.TryCatch: self._exec_try_catch,
            ast.TryCatchFinally: self._exec_try_catch_finally,
            ast.MatchStatement: self._exec_match,
            ast.ImportStatement: self._exec_import,
            ast.UseStatement: self._exec_use,
            ast.WaitStatement: self._exec_wait,
            ast.ConstDeclaration: self._exec_const,
            ast.AssertStatement: self._exec_assert,
            ast.AugmentedAssignment: self._exec_augmented_assignment,
            ast.EnumDef: self._exec_enum,
            ast.ThrowStatement: self._exec_throw,
            ast.WebApp: self._exec_webapp,
            ast.Route: self._exec_route,
            ast.StartServer: self._exec_start_server,
            ast.WindowCreate: self._exec_window_create,
            ast.WidgetAdd: self._exec_widget_add,
            ast.LayoutBlock: self._exec_layout_block,
            ast.BindEvent: self._exec_bind_event,
            ast.DialogShow: self._exec_dialog_show,
            ast.MenuDef: self._exec_menu_def,
            ast.CanvasDraw: self._exec_canvas_draw,
            ast.AsyncFunctionDef: self._exec_async_function_def,
            ast.SuperCall: self._exec_super_call,
            ast.AwaitExpression: self._eval_await,
            ast.InterfaceDefNode: self._exec_interface_def,
            ast.ModuleDef: self._exec_module_def,
            ast.ModuleAccess: self._exec_module_access,
            ast.YieldStatement: self._exec_yield,
            ast.DestructureAssignment: self._exec_destructure,
            ast.GenericClassDef: self._exec_generic_class_def,
            ast.SpawnStatement: self._exec_spawn,
            ast.ParallelForEach: self._exec_parallel_for_each,
            ast.BreakpointStatement: self._exec_breakpoint,
            ast.ExternalFunctionDef: self._exec_external_function_def,
            ast.LoadLibrary: self._exec_load_library,
        }

    def _build_expr_dispatch(self):
        """Build O(1) dispatch table for expression evaluation."""
        return {
            ast.BinaryOp: self._eval_binary,
            ast.UnaryOp: self._eval_unary,
            ast.FunctionCall: self._exec_function_call,
            ast.ListLiteral: lambda n, e: [self._eval(el, e) for el in n.elements],
            ast.MethodCall: self._eval_method_call,
            ast.PropertyAccess: self._eval_property_access,
            ast.NewInstance: self._eval_new_instance,
            ast.FileRead: self._eval_file_read,
            ast.DictLiteral: self._eval_dict_literal,
            ast.IndexAccess: self._eval_index_access,
            ast.LambdaExpression: lambda n, e: EPLLambda(n.params, n.body, e),
            ast.TernaryExpression: self._eval_ternary,
            ast.SliceAccess: self._eval_slice_access,
            ast.AwaitExpression: self._eval_await,
            ast.SuperCall: self._exec_super_call,
            ast.ModuleAccess: self._exec_module_access,
            ast.SpreadExpression: lambda n, e: self._eval(n.expression, e),
        }

    def _eval_ternary(self, node, env):
        condition = self._eval(node.condition, env)
        if self._is_truthy(condition):
            return self._eval(node.true_expr, env)
        else:
            return self._eval(node.false_expr, env)

    def execute(self, program: ast.Program):
        self._start_time = _time.time()
        self._instruction_count = 0
        try:
            self._exec_block(program.statements, self.global_env)
        except ExitSignal:
            pass

    def close(self):
        """Clean up resources (thread pool, event loop, caches)."""
        _thread_pool.shutdown(wait=False)
        global _async_loop
        if _async_loop is not None and _async_loop.is_running():
            _async_loop.call_soon_threadsafe(_async_loop.stop)
            _async_loop = None
        self._template_cache.clear()

    def _exec_block(self, statements: list, env: Environment):
        for stmt in statements:
            if stmt is not None:
                self._exec_statement(stmt, env)

    def _exec_statement(self, node, env: Environment):
        # Resource limit checks
        if self._max_instructions > 0:
            self._instruction_count += 1
            if self._instruction_count > self._max_instructions:
                raise EPLRuntimeError(
                    f'Execution limit exceeded: {self._max_instructions} statements. '
                    'Program may contain an infinite loop.',
                    getattr(node, 'line', None))
        if self._execution_timeout > 0 and (self._instruction_count & 0x3FF) == 0:
            if _time.time() - self._start_time > self._execution_timeout:
                raise EPLRuntimeError(
                    f'Execution timeout: exceeded {self._execution_timeout}s limit.',
                    getattr(node, 'line', None))
        # O(1) dispatch table lookup
        handler = self._stmt_dispatch.get(type(node))
        if handler is not None:
            return handler(node, env)

        # Special cases requiring non-standard handling
        if isinstance(node, ast.MethodCall):
            self._eval_method_call(node, env)
            return
        if isinstance(node, ast.PropertyAccess):
            return
        if isinstance(node, ast.BreakStatement):
            raise BreakSignal()
        if isinstance(node, ast.ContinueStatement):
            raise ContinueSignal()
        if isinstance(node, ast.ExitStatement):
            raise ExitSignal()

        if isinstance(node, ast.SendResponse):
            if self._route_response_enabled:
                raise RouteResponseSignal(node.response_type, node.data)
            return

        if isinstance(node, ast.FetchStatement):
            if self._route_response_enabled:
                raise RouteResponseSignal('fetch', node.collection)
            return

        # No-ops by design (handled in specific contexts)
        if isinstance(node, (ast.PageDef, ast.ScriptBlock,
                             ast.StoreStatement, ast.DeleteStatement,
                             ast.HtmlElement, ast.ExportStatement, ast.AbstractMethodDef)):
            return

        if isinstance(node, ast.VisibilityModifier):
            return self._exec_statement(node.statement, env)
        if isinstance(node, ast.StaticMethodDef):
            return self._exec_function_def(node, env)

        raise EPLRuntimeError(f"Unknown statement: {type(node).__name__}", getattr(node, 'line', None))

    # ─── String Template ──────────────────────────────────

    def _resolve_template(self, text: str, env: Environment) -> str:
        if '$' not in text:
            return text
        def replacer(match):
            # ${expression} group
            expr_text = match.group(1)
            # $variable group
            var_name = match.group(2)

            if expr_text is not None:
                # Evaluate ${expression} by parsing (cached) and interpreting
                try:
                    expr_node = self._parse_template_expr(expr_text)
                    value = self._eval(expr_node, env)
                    return self._format_value(value)
                except Exception:
                    return match.group(0)  # leave as-is on error
            elif var_name is not None:
                if env.has_variable(var_name):
                    return self._format_value(env.get_variable(var_name))
            return match.group(0)
        return _TEMPLATE_RE.sub(replacer, text)

    def _parse_template_expr(self, expr_text: str):
        """Parse a template expression string, caching the AST node."""
        if expr_text in self._template_cache:
            return self._template_cache[expr_text]
        from epl.lexer import Lexer
        from epl.parser import Parser
        lexer = Lexer(expr_text)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        expr_node = parser._parse_expression()
        self._template_cache[expr_text] = expr_node
        return expr_node

    # ─── Variables ────────────────────────────────────────

    def _exec_var_declaration(self, node: ast.VarDeclaration, env: Environment):
        if node.name in self._constants:
            raise EPLRuntimeError(f'Cannot change constant "{node.name}".', node.line)
        value = self._eval(node.value, env)
        if node.var_type:
            value = self._coerce_type(value, node.var_type, node.line)
        env.define_variable(node.name, value, node.var_type)

    def _exec_var_assignment(self, node: ast.VarAssignment, env: Environment):
        if node.name in self._constants:
            raise EPLRuntimeError(f'Cannot change constant "{node.name}".', node.line)
        value = self._eval(node.value, env)
        try:
            env.set_variable(node.name, value)
        except EPLNameError as e:
            hint = _did_you_mean(node.name, list(env.get_all_names()))
            raise EPLNameError(str(e.message) + hint, node.line)

    # ─── Print ────────────────────────────────────────────

    def _exec_print(self, node: ast.PrintStatement, env: Environment):
        value = self._eval(node.expression, env)
        output = self._format_value(value)
        if self._max_output_lines > 0 and len(self.output_lines) >= self._max_output_lines:
            raise EPLRuntimeError(
                f'Output limit exceeded: {self._max_output_lines} lines. '
                'Program may be producing excessive output.',
                node.line)
        print(output)
        self.output_lines.append(output)

    # ─── Input ────────────────────────────────────────────

    def _exec_input(self, node: ast.InputStatement, env: Environment):
        prompt = node.prompt or ""
        user_input = input(prompt)
        if env.has_variable(node.variable_name):
            existing = env.get_variable(node.variable_name)
            if isinstance(existing, int):
                try:
                    user_input = int(user_input)
                except ValueError:
                    raise EPLRuntimeError(f'Expected integer.', node.line)
            elif isinstance(existing, float):
                try:
                    user_input = float(user_input)
                except ValueError:
                    raise EPLRuntimeError(f'Expected decimal.', node.line)
        env.set_variable(node.variable_name, user_input)

    # ─── Control Flow ─────────────────────────────────────

    def _exec_if(self, node: ast.IfStatement, env: Environment):
        if self._is_truthy(self._eval(node.condition, env)):
            block_env = env.create_child(name="if-block") if self.block_scoping else env
            self._exec_block(node.then_body, block_env)
        elif node.else_body:
            block_env = env.create_child(name="else-block") if self.block_scoping else env
            self._exec_block(node.else_body, block_env)

    def _exec_while(self, node: ast.WhileLoop, env: Environment):
        limit = self.MAX_LOOP_ITERATIONS
        count = 0
        loop_env = env.create_child(name="while-block") if self.block_scoping else env
        while self._is_truthy(self._eval(node.condition, loop_env)):
            try:
                self._exec_block(node.body, loop_env)
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            count += 1
            if count > limit:
                raise EPLRuntimeError(
                    f"Loop exceeded maximum iterations ({limit}). "
                    f"Set interpreter.MAX_LOOP_ITERATIONS to increase.",
                    node.line)

    def _exec_repeat(self, node: ast.RepeatLoop, env: Environment):
        count = self._eval(node.count, env)
        if not isinstance(count, int):
            raise EPLTypeError(f"Repeat count must be integer.", node.line)
        if count < 0:
            raise EPLRuntimeError(f"Repeat count cannot be negative (got {count}).", node.line)
        loop_env = env.create_child(name="repeat-block") if self.block_scoping else env
        for _ in range(count):
            try:
                self._exec_block(node.body, loop_env)
            except BreakSignal:
                break
            except ContinueSignal:
                pass

    def _exec_for_each(self, node: ast.ForEachLoop, env: Environment):
        iterable = self._eval(node.iterable, env)
        if isinstance(iterable, EPLDict):
            iterable = list(iterable.data.keys())
        elif isinstance(iterable, EPLGenerator):
            iterable = iterable.to_list()
        elif not isinstance(iterable, (list, str)):
            raise EPLTypeError(f"For each requires list, text, map, or generator.", node.line)
        loop_env = env.create_child(name="for-each-block") if self.block_scoping else env
        var_name = node.var_name
        first = True
        for item in iterable:
            if first:
                loop_env.define_variable(var_name, item)
                first = False
            else:
                loop_env.variables[var_name]["value"] = item
            try:
                self._exec_block(node.body, loop_env)
            except BreakSignal:
                break
            except ContinueSignal:
                pass

    def _exec_for_range(self, node: ast.ForRange, env: Environment):
        start = self._eval(node.start, env)
        end = self._eval(node.end, env)
        if not isinstance(start, int) or not isinstance(end, int):
            raise EPLTypeError("For range requires integer values.", node.line)
        step = 1
        if node.step is not None:
            step = self._eval(node.step, env)
            if not isinstance(step, int) or step == 0:
                raise EPLTypeError("For range step must be a non-zero integer.", node.line)
        loop_env = env.create_child(name="for-range-block") if self.block_scoping else env
        var_name = node.var_name
        first = True
        if step > 0:
            i = start
            while i <= end:
                if first:
                    loop_env.define_variable(var_name, i)
                    first = False
                else:
                    loop_env.variables[var_name]["value"] = i
                try:
                    self._exec_block(node.body, loop_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    pass
                i += step
        else:
            i = start
            while i >= end:
                if first:
                    loop_env.define_variable(var_name, i)
                    first = False
                else:
                    loop_env.variables[var_name]["value"] = i
                try:
                    self._exec_block(node.body, loop_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    pass
                i += step

    # ─── Functions ────────────────────────────────────────

    def _exec_function_def(self, node: ast.FunctionDef, env: Environment):
        env.define_function(node.name, node)

    def _exec_function_call(self, node: ast.FunctionCall, env: Environment):
        # Check for built-ins
        if node.name in BUILTINS:
            arg_values = [self._eval(arg, env) for arg in node.arguments]
            return self._call_builtin(node.name, arg_values, node.line, env)

        # Check for Python module function call (handled via identifier)
        try:
            func_def = env.get_function(node.name)
        except EPLNameError:
            # Maybe it's a variable holding a callable (lambda, python func, async dict, etc.)
            if env.has_variable(node.name):
                val = env.get_variable(node.name)
                if (isinstance(val, EPLLambda) or callable(val)
                        or isinstance(val, ast.FunctionDef)
                        or (isinstance(val, dict) and val.get('is_async'))):
                    arg_values = [self._eval(arg, env) for arg in node.arguments]
                    return self._call_callable(val, arg_values, env, node.line)
            hint = _did_you_mean(node.name, list(env.get_all_names()))
            raise EPLNameError(f'Function "{node.name}" has not been defined.{hint}', node.line)

        arg_values = [self._eval(arg, env) for arg in node.arguments]

        # Generator detection: if the function contains yield, return a generator
        if self._func_contains_yield(func_def):
            func_env = env.create_child(name=f"generator:{node.name}")
            regular_params = func_def.params
            rest_param = None
            if func_def.params and isinstance(func_def.params[-1], ast.RestParameter):
                regular_params = func_def.params[:-1]
                rest_param = func_def.params[-1]
            for i, param in enumerate(regular_params):
                param_name = param[0]
                param_type = param[1] if len(param) > 1 else None
                default_expr = param[2] if len(param) > 2 else None
                if i < len(arg_values):
                    value = arg_values[i]
                elif default_expr is not None:
                    value = self._eval(default_expr, env)
                else:
                    value = None
                if param_type:
                    value = self._coerce_type(value, param_type, node.line)
                func_env.define_variable(param_name, value, param_type)
            if rest_param:
                rest_values = list(arg_values[len(regular_params):])
                func_env.define_variable(rest_param.name, rest_values)
            return EPLGenerator(self, func_def.body, func_env, node.name)

        # Separate rest parameter from regular params
        regular_params = func_def.params
        rest_param = None
        if func_def.params and isinstance(func_def.params[-1], ast.RestParameter):
            regular_params = func_def.params[:-1]
            rest_param = func_def.params[-1]

        # Count required params (those without defaults)
        required = sum(1 for p in regular_params if (p[2] if len(p) > 2 else None) is None)
        if rest_param:
            if len(arg_values) < required:
                raise EPLRuntimeError(
                    f'Function "{node.name}" expects at least {required} argument(s), '
                    f'but got {len(arg_values)}.', node.line)
        else:
            if len(arg_values) < required or len(arg_values) > len(regular_params):
                raise EPLRuntimeError(
                    f'Function "{node.name}" expects {required}-{len(regular_params)} argument(s), '
                    f'but got {len(arg_values)}.', node.line)

        func_env = env.create_child(name=f"function:{node.name}")

        for i, param in enumerate(regular_params):
            param_name = param[0]
            param_type = param[1] if len(param) > 1 else None
            default_expr = param[2] if len(param) > 2 else None
            if i < len(arg_values):
                value = arg_values[i]
            elif default_expr is not None:
                value = self._eval(default_expr, env)
            else:
                value = None
            if param_type:
                value = self._coerce_type(value, param_type, node.line)
            func_env.define_variable(param_name, value, param_type)
        # Bind rest parameter
        if rest_param:
            rest_values = list(arg_values[len(regular_params):])
            func_env.define_variable(rest_param.name, rest_values)

        self._call_depth += 1
        if self._call_depth > self.MAX_CALL_DEPTH:
            raise EPLRuntimeError(
                f'Maximum recursion depth ({self.MAX_CALL_DEPTH}) exceeded in function "{node.name}".', node.line)
        try:
            self._exec_block(func_def.body, func_env)
        except ReturnSignal as ret:
            return ret.value
        except EPLError as e:
            e.add_frame(node.name, node.line)
            raise
        finally:
            self._call_depth -= 1

        return None

    def _exec_return(self, node: ast.ReturnStatement, env: Environment):
        value = None
        if node.value:
            value = self._eval(node.value, env)
        raise ReturnSignal(value)

    # ─── Built-in Functions ───────────────────────────────

    def _call_builtin(self, name, args, line, env=None):
        _check_deprecation(name, line)
        if name == 'length':
            if len(args) != 1:
                raise EPLRuntimeError('length() takes 1 argument.', line)
            val = args[0]
            if isinstance(val, (str, list)):
                return len(val)
            if isinstance(val, EPLDict):
                return len(val.data)
            raise EPLTypeError(f'length() expects text, list, or map.', line)

        if name == 'type_of':
            return self._type_name(args[0]) if len(args) == 1 else None

        if name == 'typeof':
            return self._type_name(args[0]) if len(args) == 1 else None

        if name == 'to_integer':
            try: return int(args[0])
            except (ValueError, TypeError): raise EPLRuntimeError(f'Cannot convert to integer.', line)

        if name == 'to_decimal':
            try: return float(args[0])
            except (ValueError, TypeError): raise EPLRuntimeError(f'Cannot convert to decimal.', line)

        if name == 'to_text':
            return self._format_value(args[0]) if len(args) == 1 else ""

        if name == 'to_boolean':
            return self._is_truthy(args[0]) if len(args) == 1 else False

        if name == 'absolute':
            if isinstance(args[0], (int, float)):
                return abs(args[0])
            raise EPLTypeError('absolute() expects a number.', line)

        if name == 'round':
            if not isinstance(args[0], (int, float)):
                raise EPLTypeError('round() expects a number.', line)
            if len(args) == 2:
                return round(args[0], int(args[1]))
            return round(args[0])

        if name == 'max':
            if len(args) == 1 and isinstance(args[0], list):
                if not args[0]:
                    raise EPLRuntimeError('max() called on empty list.', line)
                return max(args[0])
            if not args:
                raise EPLRuntimeError('max() requires at least 1 argument.', line)
            return max(args)

        if name == 'min':
            if len(args) == 1 and isinstance(args[0], list):
                if not args[0]:
                    raise EPLRuntimeError('min() called on empty list.', line)
                return min(args[0])
            if not args:
                raise EPLRuntimeError('min() requires at least 1 argument.', line)
            return min(args)

        if name == 'random':
            if len(args) == 2:
                return _random.randint(int(args[0]), int(args[1]))
            raise EPLRuntimeError('random() takes 2 arguments (min, max).', line)

        if name == 'random_seed':
            if len(args) != 1:
                raise EPLRuntimeError('random_seed() takes 1 argument (seed value).', line)
            _random.seed(int(args[0]))
            return None

        if name == 'uppercase':
            return args[0].upper() if isinstance(args[0], str) else str(args[0]).upper()

        if name == 'lowercase':
            return args[0].lower() if isinstance(args[0], str) else str(args[0]).lower()

        # ── v0.6: Math builtins ──
        import math as _math

        if name == 'sqrt':
            if len(args) != 1: raise EPLRuntimeError('sqrt() takes 1 argument.', line)
            if not isinstance(args[0], (int, float)):
                raise EPLTypeError('sqrt() expects a number.', line)
            if args[0] < 0:
                raise EPLRuntimeError('sqrt() cannot take a negative number.', line)
            return _math.sqrt(args[0])

        if name == 'power':
            if len(args) != 2: raise EPLRuntimeError('power() takes 2 arguments.', line)
            result = args[0] ** args[1]
            return int(result) if isinstance(args[0], int) and isinstance(args[1], int) and args[1] >= 0 else result

        if name == 'floor':
            if len(args) != 1: raise EPLRuntimeError('floor() takes 1 argument.', line)
            return _math.floor(args[0])

        if name == 'ceil':
            if len(args) != 1: raise EPLRuntimeError('ceil() takes 1 argument.', line)
            return _math.ceil(args[0])

        if name == 'log':
            if len(args) < 1 or len(args) > 2:
                raise EPLRuntimeError('log() takes 1-2 arguments.', line)
            if not isinstance(args[0], (int, float)):
                raise EPLTypeError('log() expects a number.', line)
            if args[0] <= 0:
                raise EPLRuntimeError('log() requires a positive number.', line)
            if len(args) == 1: return _math.log(args[0])
            return _math.log(args[0], args[1])

        if name == 'sin':
            return _math.sin(args[0]) if len(args) == 1 else None

        if name == 'cos':
            return _math.cos(args[0]) if len(args) == 1 else None

        if name == 'tan':
            return _math.tan(args[0]) if len(args) == 1 else None

        # ── v0.6: Collections ──

        if name == 'range':
            if len(args) == 1: return list(range(int(args[0])))
            if len(args) == 2: return list(range(int(args[0]), int(args[1])))
            if len(args) == 3: return list(range(int(args[0]), int(args[1]), int(args[2])))
            raise EPLRuntimeError('range() takes 1-3 arguments.', line)

        if name == 'sum':
            if len(args) == 1 and isinstance(args[0], list):
                items = args[0]
            else:
                items = args
            if not all(isinstance(x, (int, float)) for x in items):
                raise EPLTypeError('sum() requires all numeric elements.', line)
            return sum(items)

        if name == 'sorted':
            if len(args) == 1 and isinstance(args[0], list):
                lst = args[0]
                if lst and not all(isinstance(x, type(lst[0])) for x in lst):
                    raise EPLTypeError('sorted() requires all elements to be the same type.', line)
                return sorted(lst)
            raise EPLTypeError('sorted() expects a list.', line)

        if name == 'reversed':
            if len(args) == 1:
                if isinstance(args[0], list):
                    return list(reversed(args[0]))
                if isinstance(args[0], str):
                    return args[0][::-1]
            raise EPLTypeError('reversed() expects a list or text.', line)

        if name == 'keys':
            if len(args) == 1 and isinstance(args[0], EPLDict):
                return list(args[0].data.keys())
            raise EPLTypeError('keys() expects a map.', line)

        if name == 'values':
            if len(args) == 1 and isinstance(args[0], EPLDict):
                return list(args[0].data.values())
            raise EPLTypeError('values() expects a map.', line)

        # ── v0.6: Type checking ──

        if name == 'is_integer': return isinstance(args[0], int) and not isinstance(args[0], bool) if args else False
        if name == 'is_decimal': return isinstance(args[0], float) if args else False
        if name == 'is_text': return isinstance(args[0], str) if args else False
        if name == 'is_boolean': return isinstance(args[0], bool) if args else False
        if name == 'is_list': return isinstance(args[0], list) if args else False
        if name == 'is_map': return isinstance(args[0], EPLDict) if args else False
        if name == 'is_nothing': return args[0] is None if args else False
        if name == 'is_number': return isinstance(args[0], (int, float)) and not isinstance(args[0], bool) if args else False

        # ── v0.6: Utility ──

        if name == 'json_parse':
            import json as _json
            if len(args) != 1: raise EPLRuntimeError('json_parse() takes 1 argument.', line)
            try:
                result = _json.loads(args[0])
                return self._python_to_epl(result)
            except Exception as e:
                raise EPLRuntimeError(f'json_parse error: {e}', line)

        if name == 'json_stringify':
            import json as _json
            if len(args) != 1: raise EPLRuntimeError('json_stringify() takes 1 argument.', line)
            try:
                return _json.dumps(self._epl_to_python(args[0]))
            except Exception as e:
                raise EPLRuntimeError(f'json_stringify error: {e}', line)

        if name == 'char_code':
            if len(args) == 1 and isinstance(args[0], str) and len(args[0]) == 1:
                return ord(args[0])
            raise EPLRuntimeError('char_code() takes 1 single-character text argument.', line)

        if name == 'from_char_code':
            if len(args) == 1 and isinstance(args[0], int):
                return chr(args[0])
            raise EPLRuntimeError('from_char_code() takes 1 integer argument.', line)

        if name == 'timestamp':
            return _time.time()

        # ── C FFI builtins ──
        if name in ('ffi_open', 'ffi_call', 'ffi_close', 'ffi_find', 'ffi_types'):
            if self.safe_mode:
                raise EPLRuntimeError(
                    f"'{name}' is not available in safe mode (--sandbox).", line
                )
            from epl.ffi import ffi_open, ffi_call, ffi_close, ffi_find, ffi_types
            _ffi = {'ffi_open': ffi_open, 'ffi_call': ffi_call,
                    'ffi_close': ffi_close, 'ffi_find': ffi_find,
                    'ffi_types': ffi_types}
            # Validate minimum argument counts
            _min_args = {'ffi_open': 1, 'ffi_call': 2, 'ffi_close': 1, 'ffi_find': 1, 'ffi_types': 0}
            required = _min_args[name]
            if len(args) < required:
                raise EPLRuntimeError(
                    f"'{name}' requires at least {required} argument(s), got {len(args)}.", line
                )
            return _ffi[name](*args)

        # ── Delegate to stdlib ──
        if name in STDLIB_FUNCTIONS:
            if self.safe_mode and name in _UNSAFE_BUILTINS:
                raise EPLRuntimeError(
                    f"'{name}' is not available in safe mode (--sandbox).", line
                )
            return call_stdlib(name, args, line)

        raise EPLRuntimeError(f'Unknown built-in: {name}', line)

    # ─── v0.6: JSON helpers ──────────────────────────────

    def _python_to_epl(self, val):
        """Convert Python JSON-parsed value to EPL types."""
        if isinstance(val, dict):
            return EPLDict({str(k): self._python_to_epl(v) for k, v in val.items()})
        if isinstance(val, list):
            return [self._python_to_epl(v) for v in val]
        return val

    def _epl_to_python(self, val):
        """Convert EPL value to Python JSON-serializable type."""
        if isinstance(val, EPLDict):
            return {k: self._epl_to_python(v) for k, v in val.data.items()}
        if isinstance(val, list):
            return [self._epl_to_python(v) for v in val]
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float, str)):
            return val
        if val is None:
            return None
        return str(val)

    # ─── File I/O ─────────────────────────────────────────

    def _exec_file_write(self, node: ast.FileWrite, env: Environment):
        if self.safe_mode:
            raise EPLRuntimeError('File write is not allowed in safe mode.', node.line)
        content = self._format_value(self._eval(node.content, env))
        filepath = self._eval(node.filepath, env)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError as e:
            raise EPLRuntimeError(f'Cannot write to file: {e}', node.line)

    def _exec_file_append(self, node: ast.FileAppend, env: Environment):
        if self.safe_mode:
            raise EPLRuntimeError('File append is not allowed in safe mode.', node.line)
        content = self._format_value(self._eval(node.content, env))
        filepath = self._eval(node.filepath, env)
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(content + "\n")
        except OSError as e:
            raise EPLRuntimeError(f'Cannot append to file: {e}', node.line)

    def _eval_file_read(self, node: ast.FileRead, env: Environment):
        filepath = self._eval(node.filepath, env)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except OSError as e:
            raise EPLRuntimeError(f'Cannot read file: {e}', node.line)

    # ─── Classes & OOP ───────────────────────────────────

    def _exec_class_def(self, node: ast.ClassDef, env: Environment):
        defaults = {}
        methods = {}
        static_methods = {}
        visibility_map = {}
        for item in node.body:
            if isinstance(item, ast.VarDeclaration):
                defaults[item.name] = self._eval(item.value, env)
            elif isinstance(item, ast.FunctionDef):
                methods[item.name] = item
            elif isinstance(item, ast.StaticMethodDef):
                static_methods[item.name] = item
            elif isinstance(item, ast.VisibilityModifier):
                inner = item.statement
                vis = item.visibility.lower()
                if isinstance(inner, ast.FunctionDef):
                    methods[inner.name] = inner
                    visibility_map[inner.name] = vis
                elif isinstance(inner, ast.VarDeclaration):
                    defaults[inner.name] = self._eval(inner.value, env)
                    visibility_map[inner.name] = vis
            elif isinstance(item, ast.AbstractMethodDef):
                # Store abstract marker
                methods[item.name] = item

        parent = None
        if node.parent:
            try:
                parent = env.get_variable(node.parent)
            except EPLNameError:
                hint = _did_you_mean(node.parent, list(env.get_all_names()))
                raise EPLNameError(f'Parent class "{node.parent}" not found.{hint}', node.line)
            if not isinstance(parent, EPLClass):
                raise EPLTypeError(f'"{node.parent}" is not a class.', node.line)

        klass = EPLClass(node.name, defaults, methods, parent=parent, visibility_map=visibility_map)
        klass.static_methods = static_methods

        # v4.0: Validate interface implementations
        if hasattr(node, 'implements') and node.implements:
            for iface_name in node.implements:
                self._validate_interface_impl(klass, iface_name, env, node.line)

        env.define_variable(node.name, klass)

    def _exec_generic_class_def(self, node: ast.GenericClassDef, env: Environment):
        """Execute a generic class definition using type erasure.
        
        Type params are recorded on the class for documentation/introspection
        but not enforced at runtime — EPL uses structural typing.
        """
        defaults = {}
        methods = {}
        static_methods = {}
        visibility_map = {}
        for item in node.body:
            if isinstance(item, ast.VarDeclaration):
                defaults[item.name] = self._eval(item.value, env)
            elif isinstance(item, ast.FunctionDef):
                methods[item.name] = item
            elif isinstance(item, ast.StaticMethodDef):
                static_methods[item.name] = item
            elif isinstance(item, ast.VisibilityModifier):
                inner = item.statement
                vis = item.visibility.lower()
                if isinstance(inner, ast.FunctionDef):
                    methods[inner.name] = inner
                    visibility_map[inner.name] = vis
                elif isinstance(inner, ast.VarDeclaration):
                    defaults[inner.name] = self._eval(inner.value, env)
                    visibility_map[inner.name] = vis
            elif isinstance(item, ast.AbstractMethodDef):
                methods[item.name] = item

        parent = None
        if node.parent:
            try:
                parent = env.get_variable(node.parent)
            except EPLNameError:
                hint = _did_you_mean(node.parent, list(env.get_all_names()))
                raise EPLNameError(f'Parent class "{node.parent}" not found.{hint}', node.line)
            if not isinstance(parent, EPLClass):
                raise EPLTypeError(f'"{node.parent}" is not a class.', node.line)

        klass = EPLClass(node.name, defaults, methods, parent=parent, visibility_map=visibility_map)
        klass.static_methods = static_methods
        klass.type_params = node.type_params  # store for introspection

        if hasattr(node, 'implements') and node.implements:
            for iface_name in node.implements:
                self._validate_interface_impl(klass, iface_name, env, node.line)

        env.define_variable(node.name, klass)

    # ─── v5.1: Production Power Features ───────────────────

    def _exec_spawn(self, node: ast.SpawnStatement, env: Environment):
        """Spawn a function call on a background thread, store future in variable."""
        expr = node.expression
        # Build a callable that evaluates the expression in a child env
        def _task():
            child_env = env.create_child()
            return self._eval(expr, child_env)
        future = _thread_pool.submit(_task)
        epl_future = EPLFuture(future, name=node.var_name)
        env.define_variable(node.var_name, epl_future)

    def _exec_parallel_for_each(self, node: ast.ParallelForEach, env: Environment):
        """Execute loop body concurrently across items using thread pool."""
        items = self._eval(node.iterable, env)
        if not isinstance(items, list):
            raise EPLTypeError('Parallel For Each requires a list.', node.line)
        max_w = node.max_workers or min(len(items), 16)
        results = [None] * len(items)
        errors = []
        def _run_item(idx, item):
            try:
                child_env = env.create_child()
                child_env.define_variable(node.var_name, item)
                self._exec_block(node.body, child_env)
            except Exception as e:
                errors.append((idx, e))
        with _futures.ThreadPoolExecutor(max_workers=max_w) as pool:
            futures = {pool.submit(_run_item, i, itm): i for i, itm in enumerate(items)}
            for f in _futures.as_completed(futures):
                f.result()  # propagate exceptions
        if errors:
            idx, err = errors[0]
            raise EPLRuntimeError(f'Parallel For Each error at item {idx}: {err}', node.line)

    def _exec_breakpoint(self, node: ast.BreakpointStatement, env: Environment):
        """Programmatic breakpoint — pauses execution for interactive inspection."""
        should_break = True
        if node.condition is not None:
            should_break = bool(self._eval(node.condition, env))
        if should_break:
            print(f"\n*** BREAKPOINT hit at line {node.line} ***")
            print(f"Variables: {sorted(env.get_all_names())}")
            # If interactive mode enabled and sys.stdin is a TTY, drop into interactive mode
            if self._debug_interactive and _sys.stdin.isatty():
                while True:
                    try:
                        cmd = input("(epl-debug) ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break
                    if cmd in ('c', 'continue', ''):
                        break
                    elif cmd in ('q', 'quit'):
                        raise ExitSignal()
                    elif cmd == 'locals':
                        for name in sorted(env.get_all_names()):
                            print(f"  {name} = {env.get_variable(name)}")
                    elif cmd.startswith('p '):
                        try:
                            from epl.lexer import Lexer as _Lex
                            from epl.parser import Parser as _Par
                            expr_src = cmd[2:]
                            tokens = _Lex(expr_src).tokenize()
                            expr_ast = _Par(tokens).parse().statements
                            if expr_ast:
                                val = self._eval(expr_ast[0], env) if hasattr(expr_ast[0], 'value') else self._exec_statement(expr_ast[0], env)
                                print(f"  = {val}")
                        except Exception as e:
                            print(f"  Error: {e}")
                    else:
                        print("  Commands: c(ontinue), q(uit), locals, p <expr>")

    # ─── v5.2: Triple Ecosystem — C FFI Language Syntax ────────────────

    def _exec_load_library(self, node: ast.LoadLibrary, env: Environment):
        """Load library \"path\" as name — loads a shared library into a variable."""
        if self.safe_mode:
            raise EPLRuntimeError('"Load library" is not allowed in safe mode (--sandbox).', node.line)
        from epl.ffi import ffi_open
        lib = ffi_open(node.path)
        env.define_variable(node.alias, lib)

    def _exec_external_function_def(self, node: ast.ExternalFunctionDef, env: Environment):
        """External function declaration — registers a callable that invokes C FFI."""
        if self.safe_mode:
            raise EPLRuntimeError('"External function" is not allowed in safe mode (--sandbox).', node.line)
        from epl.ffi import ffi_open, ffi_call

        # Capture the C library path and function signature
        lib_path = node.library
        c_func_name = node.name
        param_types = node.param_types
        ret_type = node.return_type

        # Cache the library handle for reuse
        cache_key = f'__ffi_lib_{lib_path}'
        lib = env.get_variable(cache_key) if cache_key in env.get_all_names() else None
        if lib is None:
            lib = ffi_open(lib_path)
            env.define_variable(cache_key, lib)

        # Create a callable wrapper
        def ffi_wrapper(*args):
            return ffi_call(lib, c_func_name, ret_type, list(args), param_types)

        # Register under the alias or function name
        epl_name = node.alias or node.name
        env.define_variable(epl_name, ffi_wrapper)

    def _eval_new_instance(self, node: ast.NewInstance, env: Environment):
        try:
            klass = env.get_variable(node.class_name)
        except EPLNameError:
            hint = _did_you_mean(node.class_name, list(env.get_all_names()))
            raise EPLNameError(f'Class "{node.class_name}" not found.{hint}', node.line)
        if not isinstance(klass, EPLClass):
            raise EPLTypeError(f'"{node.class_name}" is not a class.', node.line)
        instance = EPLInstance(klass)
        # Call constructor (init method) if it exists
        init_method = instance.get_method('init')
        if init_method is not None:
            args = [self._eval(a, env) for a in node.arguments]
            self._call_instance_method(instance, 'init', args, env, node.line)
        elif node.arguments:
            raise EPLRuntimeError(
                f'Class "{node.class_name}" has no init() constructor but was given arguments.', node.line)
        return instance

    def _exec_property_set(self, node: ast.PropertySet, env: Environment):
        obj = self._eval(node.obj, env)
        value = self._eval(node.value, env)
        if isinstance(obj, EPLInstance):
            self._check_member_access(obj.klass, node.property_name, env, node.line)
            obj.properties[node.property_name] = value
        elif isinstance(obj, EPLDict):
            obj.data[node.property_name] = value
        elif isinstance(obj, PythonModule):
            setattr(obj.module, node.property_name, value)
        else:
            raise EPLTypeError(f'Cannot set property on {self._type_name(obj)}.', node.line)

    # ─── Index Access ─────────────────────────────────────

    def _exec_index_set(self, node: ast.IndexSet, env: Environment):
        obj = self._eval(node.obj, env)
        index = self._eval(node.index, env)
        value = self._eval(node.value, env)
        if isinstance(obj, list):
            if not isinstance(index, int):
                raise EPLTypeError('List index must be integer.', node.line)
            if index < 0 or index >= len(obj):
                raise EPLRuntimeError(f'Index {index} out of range (list has {len(obj)} items).', node.line)
            obj[index] = value
        elif isinstance(obj, EPLDict):
            obj.data[str(index)] = value
        else:
            raise EPLTypeError(f'Cannot index into {self._type_name(obj)}.', node.line)

    def _eval_index_access(self, node: ast.IndexAccess, env: Environment):
        obj = self._eval(node.obj, env)
        index = self._eval(node.index, env)
        if isinstance(obj, list):
            if not isinstance(index, int):
                raise EPLTypeError('List index must be integer.', node.line)
            if index < 0 or index >= len(obj):
                raise EPLRuntimeError(f'Index {index} out of range (list has {len(obj)} items).', node.line)
            return obj[index]
        elif isinstance(obj, str):
            if not isinstance(index, int):
                raise EPLTypeError('Text index must be integer.', node.line)
            if index < 0 or index >= len(obj):
                raise EPLRuntimeError(f'Index {index} out of range.', node.line)
            return obj[index]
        elif isinstance(obj, EPLDict):
            key = str(index)
            if key in obj.data:
                return obj.data[key]
            raise EPLRuntimeError(f'Key "{key}" not found in map.', node.line)
        else:
            raise EPLTypeError(f'Cannot index into {self._type_name(obj)}.', node.line)

    # ─── Try/Catch ────────────────────────────────────────

    def _exec_try_catch(self, node: ast.TryCatch, env: Environment):
        caught = False
        try:
            self._exec_block(node.try_body, env)
        except EPLError as e:
            caught = True
            env.define_variable(node.error_var, e.user_message)
            self._exec_block(node.catch_body, env)
        except Exception as e:
            caught = True
            env.define_variable(node.error_var, str(e))
            self._exec_block(node.catch_body, env)
        finally:
            if hasattr(node, 'finally_body') and node.finally_body:
                self._exec_block(node.finally_body, env)

    def _exec_try_catch_finally(self, node: ast.TryCatchFinally, env: Environment):
        """Execute Try with multiple catch clauses and finally."""
        try:
            self._exec_block(node.try_body, env)
        except EPLError as e:
            handled = False
            for error_type, error_var, catch_body in node.catch_clauses:
                if error_type is None or self._error_matches(e, error_type):
                    env.define_variable(error_var, e.user_message)
                    self._exec_block(catch_body, env)
                    handled = True
                    break
            if not handled:
                raise
        finally:
            if node.finally_body:
                self._exec_block(node.finally_body, env)

    def _error_matches(self, error, type_name):
        """Check if an error matches a named type."""
        from epl.errors import ERROR_CLASSES
        cls = ERROR_CLASSES.get(type_name)
        if cls:
            return isinstance(error, cls)
        return type(error).__name__ == type_name or type_name == 'Error'

    # ─── Match/When ───────────────────────────────────────

    def _exec_match(self, node: ast.MatchStatement, env: Environment):
        match_value = self._eval(node.expression, env)
        for clause in node.when_clauses:
            for val_expr in clause.values:
                if match_value == self._eval(val_expr, env):
                    block_env = env.create_child(name="match-block") if self.block_scoping else env
                    self._exec_block(clause.body, block_env)
                    return
        if node.default_body:
            block_env = env.create_child(name="match-default") if self.block_scoping else env
            self._exec_block(node.default_body, block_env)

    # ─── Import EPL Module ────────────────────────────────

    # Standard library directory: epl/stdlib/
    _STDLIB_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'stdlib')

    def _resolve_import_path(self, filepath, node_line):
        """Resolve an import filepath to an absolute path, or raise EPLRuntimeError."""
        abs_path = _os.path.abspath(filepath)

        # Try direct file path
        if _os.path.exists(abs_path):
            return abs_path

        # Try with .epl extension
        if not filepath.endswith('.epl'):
            epl_path = _os.path.abspath(filepath + '.epl')
            if _os.path.exists(epl_path):
                return epl_path

        # Try relative to current file directory
        if hasattr(self, '_current_file') and self._current_file:
            current_dir = _os.path.dirname(self._current_file)
            rel_path = _os.path.join(current_dir, filepath)
            if _os.path.exists(rel_path):
                return _os.path.abspath(rel_path)
            if not filepath.endswith('.epl'):
                rel_epl = _os.path.join(current_dir, filepath + '.epl')
                if _os.path.exists(rel_epl):
                    return _os.path.abspath(rel_epl)

        # Try EPL standard library (epl/stdlib/<name>.epl)
        stdlib_name = filepath.replace('.epl', '') if filepath.endswith('.epl') else filepath
        stdlib_path = _os.path.join(self._STDLIB_DIR, stdlib_name + '.epl')
        if _os.path.exists(stdlib_path):
            return _os.path.abspath(stdlib_path)

        # Try package manager resolution
        try:
            from epl.package_manager import find_package_module
            pkg_path = find_package_module(filepath)
            if pkg_path and _os.path.exists(pkg_path):
                return pkg_path
        except ImportError:
            pass

        # Auto-install: if a matching package exists in the registry, install it
        try:
            from epl.package_manager import auto_install_package
            auto_path = auto_install_package(filepath)
            if auto_path and _os.path.exists(auto_path):
                return auto_path
        except ImportError:
            pass

        raise EPLRuntimeError(
            f'Cannot find module "{filepath}". '
            f'Searched: local files, stdlib, epl_modules/, ~/.epl/packages/. '
            f'Install with: epl install {filepath}',
            node_line
        )

    def _exec_import(self, node: ast.ImportStatement, env: Environment):
        filepath = node.filepath
        abs_path = self._resolve_import_path(filepath, node.line)

        # Sandbox: restrict imports to current directory tree
        if self.safe_mode:
            cwd = _os.path.abspath('.')
            if not _os.path.abspath(abs_path).startswith(cwd):
                raise EPLRuntimeError(
                    'Import from outside working directory is not allowed in safe mode.', node.line)

        if abs_path in self._imported_files and not node.alias:
            return  # already imported, skip (unless aliased - need the env)

        self._imported_files.add(abs_path)

        if node.alias:
            # Aliased import: Import "math" as Math → execute in sub-env, expose as namespace
            self._import_as_module(abs_path, node.alias, env, node.line)
        else:
            # Plain import: merge all definitions into current env
            self._import_and_exec(abs_path, env, node.line)

    def _parse_file(self, abs_path, line):
        """Read, lex, parse a file — with AST caching."""
        if abs_path in self._ast_cache:
            return self._ast_cache[abs_path]
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                source = f.read()
        except OSError as e:
            raise EPLRuntimeError(f'Cannot read file "{abs_path}": {e}', line)
        from epl.lexer import Lexer
        from epl.parser import Parser
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        self._ast_cache[abs_path] = program
        return program

    def _import_and_exec(self, abs_path, env, line):
        """Read, parse, and execute an EPL file."""
        program = self._parse_file(abs_path, line)

        old_file = getattr(self, '_current_file', None)
        self._current_file = abs_path

        # Execute in global env so all definitions are available
        self._exec_block(program.statements, env)
        self._current_file = old_file

    def _import_as_module(self, abs_path, alias, env, line):
        """Import a file as a named module (Import "x" as X → X::func)."""
        program = self._parse_file(abs_path, line)

        old_file = getattr(self, '_current_file', None)
        self._current_file = abs_path

        # Execute in a child environment to capture definitions
        module_env = Environment(parent=env, name=alias)
        self._exec_block(program.statements, module_env)
        self._current_file = old_file

        # Register as a module namespace accessible via Alias::member
        env.register_module(alias, module_env)

        # Also expose as a variable dict so Module::member and Module.member work
        mod_dict = {'__is_module__': True, '__name__': alias}
        for name, val in module_env.variables.items():
            mod_dict[name] = val
        for name, func in module_env.functions.items():
            mod_dict[name] = func
        env.define_variable(alias, mod_dict)

    # ─── Use Python Library ───────────────────────────────

    # Allowlist of known-safe packages that can be auto-installed
    _SAFE_AUTO_INSTALL = frozenset({
        # --- Web Frameworks & HTTP ---
        'flask', 'fastapi', 'django', 'bottle', 'tornado', 'sanic',
        'starlette', 'uvicorn', 'gunicorn', 'hypercorn', 'waitress',
        'requests', 'httpx', 'aiohttp', 'urllib3', 'httplib2',
        # --- Data & Science ---
        'numpy', 'pandas', 'scipy', 'sympy', 'statsmodels',
        'scikit-learn', 'joblib', 'xgboost', 'lightgbm',
        # --- ML & AI ---
        'tensorflow', 'torch', 'keras', 'transformers', 'diffusers',
        'openai', 'langchain', 'huggingface-hub', 'onnx', 'onnxruntime',
        # --- Visualization ---
        'matplotlib', 'seaborn', 'plotly', 'bokeh', 'altair', 'dash',
        # --- Database ---
        'sqlalchemy', 'peewee', 'pymongo', 'redis', 'psycopg2',
        'mysql-connector-python', 'pymysql', 'aiosqlite', 'databases',
        # --- Image & Media ---
        'pillow', 'opencv-python', 'imageio', 'scikit-image',
        # --- CLI & Terminal ---
        'rich', 'click', 'typer', 'colorama', 'tqdm', 'prompt-toolkit',
        # --- Serialization & Parsing ---
        'pyyaml', 'toml', 'tomli', 'lxml', 'beautifulsoup4', 'html5lib',
        'msgpack', 'protobuf', 'orjson', 'ujson',
        # --- Testing ---
        'pytest', 'hypothesis', 'faker', 'factory-boy', 'coverage',
        # --- Dev Tools ---
        'black', 'ruff', 'mypy', 'pylint', 'isort', 'autopep8',
        # --- Crypto & Security ---
        'cryptography', 'bcrypt', 'passlib', 'pyjwt', 'jwt',
        'pynacl', 'paramiko', 'certifi',
        # --- Cloud & DevOps ---
        'boto3', 'google-cloud-storage', 'azure-storage-blob',
        'docker', 'fabric', 'ansible',
        # --- Async & Networking ---
        'celery', 'kombu', 'websockets', 'python-socketio', 'grpcio',
        # --- Templating & Docs ---
        'jinja2', 'mako', 'markdown', 'sphinx', 'mkdocs',
        # --- Office & Files ---
        'openpyxl', 'xlsxwriter', 'python-docx', 'reportlab',
        'python-pptx', 'pypdf2', 'tabulate',
        # --- Env & Config ---
        'python-dotenv', 'pydantic', 'pydantic-settings', 'dynaconf',
        # --- GUI & Desktop ---
        'toga', 'briefcase', 'tkinter', 'pyqt5', 'pyside6', 'kivy',
        'dearpygui', 'wxpython', 'flet',
        # --- Game Dev ---
        'pygame', 'pyglet', 'arcade', 'ursina', 'panda3d',
        # --- Networking & Email ---
        'dnspython', 'scapy', 'netifaces', 'pyopenssl',
        # --- Data Validation ---
        'marshmallow', 'cerberus', 'voluptuous', 'attrs',
        # --- Scheduling ---
        'schedule', 'apscheduler', 'rq',
    })

    def _project_lookup_paths(self):
        """Candidate paths for resolving the active project's manifest."""
        paths = []
        current_file = getattr(self, '_current_file', None)
        if current_file:
            paths.append(_os.path.dirname(_os.path.abspath(current_file)))
        paths.append(_os.getcwd())

        ordered = []
        seen = set()
        for path in paths:
            path = _os.path.abspath(path)
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        return ordered

    def _resolve_declared_python_requirement(self, library_name):
        """Resolve a project-declared pip requirement for a Python bridge import."""
        try:
            from epl.package_manager import resolve_python_dependency
        except ImportError:
            return None

        for path in self._project_lookup_paths():
            requirement = resolve_python_dependency(library_name, path)
            if requirement:
                return requirement
        return None

    def _exec_use(self, node: ast.UseStatement, env: Environment):
        # Sandbox: block all Python FFI access in safe mode
        if self.safe_mode:
            raise EPLRuntimeError(
                '"Use python" is not allowed in safe mode (--sandbox). '
                'Python FFI provides unrestricted system access.', node.line)
        try:
            module = _importlib.import_module(node.library)
        except ImportError:
            pkg_name = node.library.split(".")[0]
            declared_requirement = self._resolve_declared_python_requirement(node.library)
            install_target = declared_requirement or pkg_name
            allowlisted = pkg_name.lower() in self._SAFE_AUTO_INSTALL

            if not declared_requirement and not allowlisted:
                raise EPLRuntimeError(
                    f'Python library "{node.library}" is not installed. '
                    f'Add it to [python-dependencies] in epl.toml or run '
                    f'"epl pyinstall {pkg_name}" (optionally with a pip requirement).',
                    node.line
                )

            if declared_requirement:
                print(f'[EPL] Python dependency "{node.library}" not found. Installing declared requirement: {install_target}')
            else:
                print(f'[EPL] Package "{pkg_name}" not found. Auto-installing (allowlisted)...')
            try:
                verbose = _os.environ.get('EPL_VERBOSE')
                _subprocess.check_call(
                    [_sys.executable, '-m', 'pip', 'install', install_target],
                    stdout=None if verbose else _subprocess.DEVNULL,
                    stderr=None if verbose else _subprocess.DEVNULL,
                )
                module = _importlib.import_module(node.library)
                print(f'[EPL] Successfully installed and loaded "{node.library}".')
            except _subprocess.CalledProcessError:
                raise EPLRuntimeError(
                    f'Python library "{node.library}" not found and auto-install failed. '
                    f'Install manually with: pip install {install_target}',
                    node.line
                )
            except ImportError:
                raise EPLRuntimeError(
                    f'Package "{install_target}" was installed but "{node.library}" could not be imported. '
                    f'Check the correct import name or update [python-dependencies].',
                    node.line
                )
        wrapped = PythonModule(module, node.library)
        env.define_variable(node.alias, wrapped)

    # ─── Wait ─────────────────────────────────────────────

    def _exec_wait(self, node: ast.WaitStatement, env: Environment):
        duration = self._eval(node.duration, env)
        if not isinstance(duration, (int, float)):
            raise EPLTypeError('Wait duration must be a number.', node.line)
        _time.sleep(duration)

    # ─── Constant ─────────────────────────────────────────

    def _exec_const(self, node: ast.ConstDeclaration, env: Environment):
        if node.name in self._constants:
            raise EPLRuntimeError(f'Constant "{node.name}" already defined.', node.line)
        value = self._eval(node.value, env)
        env.define_variable(node.name, value)
        self._constants.add(node.name)

    # ─── Assert ───────────────────────────────────────────

    def _exec_assert(self, node: ast.AssertStatement, env: Environment):
        result = self._eval(node.expression, env)
        if not self._is_truthy(result):
            raise EPLRuntimeError(f'Assertion failed on line {node.line}.', node.line)

    # ─── v0.6: Augmented Assignment ──────────────────────

    def _exec_augmented_assignment(self, node: ast.AugmentedAssignment, env: Environment):
        if node.name in self._constants:
            raise EPLRuntimeError(f'Cannot change constant "{node.name}".', node.line)
        try:
            current = env.get_variable(node.name)
        except EPLNameError:
            hint = _did_you_mean(node.name, list(env.get_all_names()))
            raise EPLNameError(f'Variable "{node.name}" has not been created yet.{hint}', node.line)
        rhs = self._eval(node.value, env)
        op = node.operator
        if op == '+=':
            if isinstance(current, str) or isinstance(rhs, str):
                result = str(self._format_value(current)) + str(self._format_value(rhs))
            elif isinstance(current, list):
                current.append(rhs)
                return
            else:
                self._ensure_numeric(current, rhs, '+=', node.line)
                result = current + rhs
        elif op == '-=':
            self._ensure_numeric(current, rhs, '-=', node.line)
            result = current - rhs
        elif op == '*=':
            self._ensure_numeric(current, rhs, '*=', node.line)
            result = current * rhs
        elif op == '/=':
            self._ensure_numeric(current, rhs, '/=', node.line)
            if rhs == 0:
                raise EPLRuntimeError("Cannot divide by zero.", node.line)
            result = current / rhs
            if isinstance(current, int) and isinstance(rhs, int) and current % rhs == 0:
                result = int(result)
        elif op == '%=':
            self._ensure_numeric(current, rhs, '%=', node.line)
            if rhs == 0:
                raise EPLRuntimeError("Cannot modulo by zero.", node.line)
            result = current % rhs
        else:
            raise EPLRuntimeError(f"Unknown operator: {op}", node.line)
        env.set_variable(node.name, result)

    # ─── v0.6: Enum ──────────────────────────────────────

    def _exec_enum(self, node: ast.EnumDef, env: Environment):
        data = {}
        for i, member in enumerate(node.members):
            data[member] = i
        env.define_variable(node.name, EPLDict(data))

    # ─── v0.6: Throw ─────────────────────────────────────

    def _exec_throw(self, node: ast.ThrowStatement, env: Environment):
        value = self._eval(node.value if hasattr(node, 'value') else node.expression, env)
        raise EPLRuntimeError(str(self._format_value(value)), node.line)

    # ─── v0.6: Slice Access ──────────────────────────────

    def _eval_slice_access(self, node: ast.SliceAccess, env: Environment):
        obj = self._eval(node.obj, env)
        start = self._eval(node.start, env) if node.start else None
        end = self._eval(node.end, env) if node.end else None
        step = self._eval(node.step, env) if node.step else None

        # Handle None markers from parser (Literal(None))
        if start is None:
            start_idx = None
        else:
            start_idx = int(start)
        if end is None:
            end_idx = None
        else:
            end_idx = int(end)
        if step is None:
            step_idx = None
        else:
            step_idx = int(step)

        if isinstance(obj, (list, str)):
            return obj[start_idx:end_idx:step_idx]
        raise EPLTypeError(f"Cannot slice {self._type_name(obj)}.", getattr(node, 'line', 0))

    # ─── v0.6: Callable Helper ───────────────────────────

    def _call_callable(self, func, args, env, line):
        """Call a FunctionDef, EPLLambda, async dict, builtin name, or Python callable."""
        # Async function dict
        if isinstance(func, dict) and func.get('is_async'):
            return self._call_async_function(func, args, env, line)

        if isinstance(func, ast.FunctionDef):
            # Check if this is a generator function (contains yield)
            if self._func_contains_yield(func):
                return self._call_generator_function(func, args, env, line)
            
            # Separate rest parameter from regular params
            regular_params = func.params
            rest_param = None
            if func.params and isinstance(func.params[-1], ast.RestParameter):
                regular_params = func.params[:-1]
                rest_param = func.params[-1]
            
            required = sum(1 for p in regular_params if (p[2] if len(p) > 2 else None) is None)
            if rest_param:
                if len(args) < required:
                    raise EPLRuntimeError(
                        f'Function expects at least {required} argument(s), but got {len(args)}.', line)
            else:
                if len(args) < required or len(args) > len(regular_params):
                    raise EPLRuntimeError(
                        f'Function expects {required}-{len(regular_params)} argument(s), but got {len(args)}.', line)
            func_env = env.create_child(name="function:anonymous")
            for i, param in enumerate(regular_params):
                param_name = param[0]
                param_type = param[1] if len(param) > 1 else None
                default_expr = param[2] if len(param) > 2 else None
                if i < len(args):
                    value = args[i]
                elif default_expr is not None:
                    value = self._eval(default_expr, env)
                else:
                    value = None
                if param_type:
                    value = self._coerce_type(value, param_type, line)
                func_env.define_variable(param_name, value, param_type)
            # Bind rest parameter
            if rest_param:
                rest_values = list(args[len(regular_params):])
                func_env.define_variable(rest_param.name, rest_values)
            self._call_depth += 1
            if self._call_depth > self.MAX_CALL_DEPTH:
                raise EPLRuntimeError(
                    f'Maximum recursion depth ({self.MAX_CALL_DEPTH}) exceeded.', line)
            try:
                self._exec_block(func.body, func_env)
            except ReturnSignal as ret:
                return ret.value
            finally:
                self._call_depth -= 1
            return None

        if isinstance(func, EPLLambda):
            if len(args) != len(func.params):
                raise EPLRuntimeError(
                    f'Lambda expects {len(func.params)} argument(s), but got {len(args)}.', line)
            lambda_env = func.closure_env.create_child(name="lambda")
            for i, param_name in enumerate(func.params):
                lambda_env.define_variable(param_name, args[i])
            return self._eval(func.body_node, lambda_env)

        if isinstance(func, str) and func in BUILTINS:
            return self._call_builtin(func, args, line)

        if callable(func):
            try:
                result = func(*[self._unwrap_python_argument(arg) for arg in args])
                return self._wrap_python_result(result)
            except TypeError as e:
                raise EPLRuntimeError(f'Argument error: {e}', line)
            except Exception as e:
                raise EPLRuntimeError(f'Python error: {e}', line)

        raise EPLTypeError(f'Cannot call {self._type_name(func)}.', line)

    # ─── Expression Evaluation ────────────────────────────

    def _eval(self, node, env: Environment):
        # Fast path: Literal and Identifier are the most common nodes
        if isinstance(node, ast.Literal):
            if isinstance(node.value, str):
                return self._resolve_template(node.value, env)
            return node.value

        if isinstance(node, ast.Identifier):
            try:
                return env.get_variable(node.name)
            except EPLNameError:
                # v0.6: Check if it's a function name (for higher-order functions)
                try:
                    return env.get_function(node.name)
                except EPLNameError:
                    pass
                # Check builtins
                if node.name in BUILTINS:
                    return node.name  # return name as string for builtin reference
                hint = _did_you_mean(node.name, list(env.get_all_names()) + list(BUILTINS))
                raise EPLNameError(f'Variable "{node.name}" has not been created yet.{hint}', node.line)

        # O(1) dispatch table for all other expression types
        handler = self._expr_dispatch.get(type(node))
        if handler is not None:
            return handler(node, env)

        raise EPLRuntimeError(f"Cannot evaluate: {type(node).__name__}", getattr(node, 'line', None))

    # ─── Dict Literal ─────────────────────────────────────

    def _eval_dict_literal(self, node: ast.DictLiteral, env: Environment):
        data = {}
        for key_name, value_node in node.pairs:
            data[key_name] = self._eval(value_node, env)
        return EPLDict(data)

    # ─── Method Call ──────────────────────────────────────

    def _eval_method_call(self, node: ast.MethodCall, env: Environment):
        obj = self._eval(node.obj, env)
        args = [self._eval(a, env) for a in node.arguments]
        method = node.method_name
        line = node.line

        if isinstance(obj, str):
            return self._call_string_method(obj, method, args, line, env)
        if isinstance(obj, list):
            return self._call_list_method(obj, method, args, line, env)
        if isinstance(obj, EPLInstance):
            return self._call_instance_method(obj, method, args, env, line)
        if isinstance(obj, EPLDict):
            return self._call_dict_method(obj, method, args, line, env)
        if isinstance(obj, dict) and obj.get('__is_module__'):
            # Module dot-access: Math.factorial(5)
            member = obj.get(method)
            if member is None:
                raise EPLRuntimeError(
                    f'Module "{obj.get("__name__", "?")}" has no member "{method}".', line)
            if hasattr(member, 'body'):
                call_env = env.create_child(f"{obj.get('__name__', '?')}.{method}")
                # Register all module functions so recursive/cross calls work
                for mname, mval in obj.items():
                    if mname.startswith('__'):
                        continue
                    if hasattr(mval, 'body'):
                        call_env.define_function(mname, mval)
                    else:
                        call_env.define_variable(mname, mval)
                params = member.params if hasattr(member, 'params') else []
                for i, param in enumerate(params):
                    p_name = param[0] if isinstance(param, (tuple, list)) else getattr(param, 'name', str(param))
                    p_type = param[1] if isinstance(param, (tuple, list)) and len(param) > 1 else None
                    val = args[i] if i < len(args) else None
                    if p_type:
                        val = self._coerce_type(val, p_type, line)
                    call_env.define_variable(p_name, val, p_type)
                try:
                    self._exec_block(member.body, call_env)
                except ReturnSignal as ret:
                    return ret.value
                return None
            if callable(member):
                return member(*args)
            return member
        if isinstance(obj, PythonModule):
            return self._call_python_method(obj, method, args, line)

        # v4.0: Static method call on class object: ClassName.staticMethod(args)
        if isinstance(obj, EPLClass):
            if hasattr(obj, 'static_methods') and method in obj.static_methods:
                func_node = obj.static_methods[method]
                call_env = env.create_child(f"{obj.name}.{method}")
                params = func_node.params if hasattr(func_node, 'params') else []
                for i, param in enumerate(params):
                    p_name = param[0] if isinstance(param, (tuple, list)) else getattr(param, 'name', str(param))
                    p_type = param[1] if isinstance(param, (tuple, list)) and len(param) > 1 else None
                    val = args[i] if i < len(args) else None
                    if p_type:
                        val = self._coerce_type(val, p_type, node.line)
                    call_env.define_variable(p_name, val, p_type)
                result = None
                try:
                    self._exec_block(func_node.body, call_env)
                except ReturnSignal as ret:
                    result = ret.value
                return result
            raise EPLRuntimeError(f'Class "{obj.name}" has no static method "{method}".', line)

        raise EPLTypeError(f'Cannot call method on {self._type_name(obj)}.', line)

    def _call_string_method(self, s, method, args, line, env=None):
        if method == 'uppercase': return s.upper()
        if method == 'lowercase': return s.lower()
        if method == 'trim': return s.strip()
        if method == 'contains': return str(args[0]) in s if args else False
        if method == 'replace': return s.replace(str(args[0]), str(args[1])) if len(args) == 2 else s
        if method == 'split': return s.split(str(args[0])) if args else s.split()
        if method == 'starts_with': return s.startswith(str(args[0])) if args else False
        if method == 'ends_with': return s.endswith(str(args[0])) if args else False
        if method == 'substring':
            if len(args) == 1: return s[int(args[0]):]
            if len(args) == 2: return s[int(args[0]):int(args[1])]
        # v0.6: New string methods
        if method == 'find':
            return s.find(str(args[0])) if args else -1
        if method == 'index_of':
            return s.find(str(args[0])) if args else -1
        if method == 'count':
            return s.count(str(args[0])) if args else 0
        if method == 'repeat':
            return s * int(args[0]) if args else s
        if method == 'reverse':
            return s[::-1]
        if method == 'pad_left':
            width = int(args[0]) if args else 0
            fill = str(args[1]) if len(args) > 1 else ' '
            return s.rjust(width, fill[0]) if fill else s.rjust(width)
        if method == 'pad_right':
            width = int(args[0]) if args else 0
            fill = str(args[1]) if len(args) > 1 else ' '
            return s.ljust(width, fill[0]) if fill else s.ljust(width)
        if method == 'is_number':
            try:
                float(s)
                return True
            except ValueError:
                return False
        if method == 'is_alpha':
            return s.isalpha()
        if method == 'is_empty':
            return len(s) == 0
        if method == 'char_at':
            idx = int(args[0]) if args else 0
            if 0 <= idx < len(s): return s[idx]
            raise EPLRuntimeError(f'Index {idx} out of range.', line)
        if method == 'to_list':
            return list(s)
        if method == 'to_integer':
            try: return int(s)
            except (ValueError, TypeError): raise EPLRuntimeError(f'Cannot convert text to integer.', line)
        if method == 'to_decimal':
            try: return float(s)
            except (ValueError, TypeError): raise EPLRuntimeError(f'Cannot convert text to decimal.', line)
        if method == 'format':
            # Simple positional format: "Hello {} and {}".format(a, b)
            result = s
            for a in args:
                result = result.replace('{}', self._format_value(a), 1)
            return result
        raise EPLRuntimeError(f'Text has no method "{method}".', line)

    def _call_list_method(self, lst, method, args, line, env=None):
        if method == 'add': lst.append(args[0]); return None
        if method == 'remove':
            if args[0] in lst: lst.remove(args[0])
            return None
        if method == 'contains': return args[0] in lst if args else False
        if method == 'sort': lst.sort(); return None
        if method == 'reverse': lst.reverse(); return None
        if method == 'join':
            sep = str(args[0]) if args else ""
            return sep.join(self._format_value(v) for v in lst)
        if method == 'pop': return lst.pop() if lst else None
        if method == 'clear': lst.clear(); return None
        # v0.6: New list methods
        if method == 'map' and args and env:
            func = args[0]
            return [self._call_callable(func, [item], env, line) for item in lst]
        if method == 'filter' and args and env:
            func = args[0]
            return [item for item in lst if self._is_truthy(self._call_callable(func, [item], env, line))]
        if method == 'reduce' and args and env:
            func = args[0]
            if not lst and len(args) <= 1:
                raise EPLRuntimeError('reduce() called on empty list with no initial value.', line)
            acc = args[1] if len(args) > 1 else lst[0]
            items = lst if len(args) > 1 else lst[1:]
            for item in items:
                acc = self._call_callable(func, [acc, item], env, line)
            return acc
        if method == 'find' and args and env:
            func = args[0]
            for item in lst:
                if self._is_truthy(self._call_callable(func, [item], env, line)):
                    return item
            return None
        if method == 'index_of':
            if args and args[0] in lst:
                return lst.index(args[0])
            return -1
        if method == 'count':
            return lst.count(args[0]) if args else len(lst)
        if method == 'slice':
            start = int(args[0]) if len(args) >= 1 else 0
            end = int(args[1]) if len(args) >= 2 else len(lst)
            return lst[start:end]
        if method == 'flatten':
            result = []
            for item in lst:
                if isinstance(item, list):
                    result.extend(item)
                else:
                    result.append(item)
            return result
        if method == 'unique':
            seen = set()
            result = []
            for item in lst:
                key = item if isinstance(item, (int, float, str, bool, type(None))) else id(item)
                if key not in seen:
                    seen.add(key)
                    result.append(item)
            return result
        if method == 'every' and args and env:
            func = args[0]
            return all(self._is_truthy(self._call_callable(func, [item], env, line)) for item in lst)
        if method == 'some' and args and env:
            func = args[0]
            return any(self._is_truthy(self._call_callable(func, [item], env, line)) for item in lst)
        if method == 'sum':
            return sum(lst)
        if method == 'min':
            return min(lst) if lst else None
        if method == 'max':
            return max(lst) if lst else None
        if method == 'first':
            return lst[0] if lst else None
        if method == 'last':
            return lst[-1] if lst else None
        if method == 'insert':
            if len(args) == 2:
                lst.insert(int(args[0]), args[1])
            return None
        if method == 'copy':
            return lst.copy()
        raise EPLRuntimeError(f'List has no method "{method}".', line)

    def _call_dict_method(self, d, method, args, line, env=None):
        if method == 'keys': return list(d.data.keys())
        if method == 'values': return list(d.data.values())
        if method == 'has': return str(args[0]) in d.data if args else False
        if method == 'remove':
            key = str(args[0]) if args else ""
            if key in d.data: del d.data[key]
            return None
        # v0.6: New map methods
        if method == 'entries':
            return [[k, v] for k, v in d.data.items()]
        if method == 'merge':
            if args and isinstance(args[0], EPLDict):
                merged = EPLDict(dict(d.data))
                merged.data.update(args[0].data)
                return merged
            raise EPLTypeError('merge() expects a map argument.', line)
        if method == 'get':
            key = str(args[0]) if args else ""
            default = args[1] if len(args) > 1 else None
            return d.data.get(key, default)
        if method == 'set':
            if len(args) == 2:
                d.data[str(args[0])] = args[1]
            return None
        if method == 'clear':
            d.data.clear()
            return None
        if method == 'copy':
            return EPLDict(dict(d.data))
        raise EPLRuntimeError(f'Map has no method "{method}".', line)

    def _call_python_method(self, py_mod, method, args, line):
        """Call a function or access attribute on a Python module."""
        if not hasattr(py_mod.module, method):
            raise EPLRuntimeError(f'Python module "{py_mod.name}" has no function "{method}".', line)
        attr = getattr(py_mod.module, method)
        if callable(attr):
            try:
                result = attr(*[self._unwrap_python_argument(arg) for arg in args])
                return self._wrap_python_result(result)
            except TypeError as e:
                raise EPLRuntimeError(
                    f'{py_mod.name}.{method}() argument error: {e}', line)
            except Exception as e:
                raise EPLRuntimeError(f'Python error in {py_mod.name}.{method}(): {e}', line)
        return self._wrap_python_result(attr)

    def _wrap_python_result(self, value, _seen=None):
        """Convert Python-native types to EPL-compatible types.
        Uses a seen-set to prevent infinite recursion on circular references."""
        if value is None or isinstance(value, (int, float, bool, str)):
            return value
        # Guard against circular references
        if _seen is None:
            _seen = set()
        obj_id = id(value)
        if obj_id in _seen:
            return f'<circular ref {type(value).__name__}>'
        _seen.add(obj_id)
        try:
            if isinstance(value, dict):
                return EPLDict({k: self._wrap_python_result(v, _seen) for k, v in value.items()})
            if isinstance(value, (list, tuple)):
                return [self._wrap_python_result(item, _seen) for item in value]
            if isinstance(value, set):
                return [self._wrap_python_result(item, _seen) for item in value]
            if isinstance(value, bytes):
                return value.decode('utf-8', errors='replace')
            # Wrap complex objects (numpy arrays, class instances, etc.) as PythonModule for chaining
            type_name = type(value).__name__
            if hasattr(value, '__iter__') and not isinstance(value, str):
                try:
                    return [self._wrap_python_result(item, _seen) for item in value]
                except (TypeError, StopIteration):
                    pass
            # Return as PythonModule wrapper so methods can still be called
            if hasattr(value, '__dict__') or hasattr(value, '__class__'):
                return PythonModule(value, type_name)
            return value
        finally:
            _seen.discard(obj_id)

    def _unwrap_python_argument(self, value, _seen=None):
        """Convert EPL runtime values back into plain Python objects for Python calls."""
        if value is None or isinstance(value, (int, float, bool, str)):
            return value
        if isinstance(value, PythonModule):
            return value.module

        if _seen is None:
            _seen = set()
        obj_id = id(value)
        if obj_id in _seen:
            return None
        _seen.add(obj_id)

        try:
            if isinstance(value, EPLDict):
                return {
                    key: self._unwrap_python_argument(item, _seen)
                    for key, item in value.data.items()
                }
            if isinstance(value, dict):
                if value.get('__is_module__'):
                    return {
                        key: self._unwrap_python_argument(item, _seen)
                        for key, item in value.items()
                        if not key.startswith('__')
                    }
                if 'value' in value and 'type' in value and len(value) == 2:
                    return self._unwrap_python_argument(value['value'], _seen)
                return {
                    key: self._unwrap_python_argument(item, _seen)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [self._unwrap_python_argument(item, _seen) for item in value]
            if isinstance(value, tuple):
                return tuple(self._unwrap_python_argument(item, _seen) for item in value)
            if isinstance(value, set):
                return {self._unwrap_python_argument(item, _seen) for item in value}
            return value
        finally:
            _seen.discard(obj_id)

    def _call_instance_method(self, instance, method_name, args, env, line):
        func_def = instance.get_method(method_name)
        if not func_def:
            raise EPLRuntimeError(f'{instance.klass.name} has no method "{method_name}".', line)

        self._check_member_access(instance.klass, method_name, env, line)

        required = sum(1 for p in func_def.params if (p[2] if len(p) > 2 else None) is None)
        if len(args) < required or len(args) > len(func_def.params):
            raise EPLRuntimeError(
                f'Method "{method_name}" expects {required}-{len(func_def.params)} argument(s), '
                f'but got {len(args)}.', line)

        method_env = env.create_child(name=f"method:{instance.klass.name}.{method_name}")
        method_env.define_variable("this", instance)
        for prop_name, prop_val in instance.properties.items():
            method_env.define_variable(prop_name, prop_val)

        for i, param in enumerate(func_def.params):
            param_name = param[0]
            param_type = param[1] if len(param) > 1 else None
            default_expr = param[2] if len(param) > 2 else None
            if i < len(args):
                value = args[i]
            elif default_expr is not None:
                value = self._eval(default_expr, env)
            else:
                value = None
            if param_type:
                value = self._coerce_type(value, param_type, line)
            method_env.define_variable(param_name, value, param_type)

        try:
            self._exec_block(func_def.body, method_env)
        except ReturnSignal as ret:
            for prop_name in instance.properties:
                if method_env.has_variable(prop_name):
                    instance.properties[prop_name] = method_env.get_variable(prop_name)
            return ret.value
        except EPLError as e:
            e.add_frame(f"{instance.klass.name}.{method_name}", line)
            raise

        for prop_name in instance.properties:
            if method_env.has_variable(prop_name):
                instance.properties[prop_name] = method_env.get_variable(prop_name)

        return None

    # ─── Property Access ──────────────────────────────────

    def _get_caller_class_name(self, env: Environment):
        """Walk up the environment chain to find if we're inside a class method."""
        e = env
        while e:
            if e.name.startswith("method:"):
                # Format: "method:ClassName.methodName"
                return e.name.split(":")[1].split(".")[0]
            e = e.parent
        return None

    def _check_member_access(self, klass, member_name, env, line):
        """Enforce visibility: private=same class only, protected=same class or subclass."""
        vis = klass.get_visibility(member_name)
        if vis == 'public':
            return
        caller_class = self._get_caller_class_name(env)
        if vis == 'private':
            if caller_class != klass.name:
                raise EPLRuntimeError(
                    f'Cannot access private member "{member_name}" of {klass.name} from outside the class.', line)
        elif vis == 'protected':
            if caller_class is None:
                raise EPLRuntimeError(
                    f'Cannot access protected member "{member_name}" of {klass.name} from outside a class.', line)
            # Check if caller is the same class or a subclass
            caller_klass = None
            try:
                caller_klass = env.get_variable(caller_class)
            except Exception:
                pass
            if caller_class != klass.name and not self._is_subclass_of(caller_klass, klass):
                raise EPLRuntimeError(
                    f'Cannot access protected member "{member_name}" of {klass.name} from {caller_class}.', line)

    def _is_subclass_of(self, child_klass, parent_klass):
        """Check if child_klass inherits from parent_klass."""
        if not isinstance(child_klass, EPLClass) or not isinstance(parent_klass, EPLClass):
            return False
        k = child_klass.parent
        while k:
            if k.name == parent_klass.name:
                return True
            k = k.parent
        return False

    def _eval_property_access(self, node: ast.PropertyAccess, env: Environment):
        obj = self._eval(node.obj, env)
        prop = node.property_name

        if prop == 'length':
            if isinstance(obj, (str, list)): return len(obj)
            if isinstance(obj, EPLDict): return len(obj.data)

        if isinstance(obj, str):
            if prop == 'uppercase': return obj.upper()
            if prop == 'lowercase': return obj.lower()
            if prop == 'trim': return obj.strip()
            raise EPLRuntimeError(f'Text has no property "{prop}".', node.line)

        if isinstance(obj, EPLInstance):
            if prop in obj.properties:
                self._check_member_access(obj.klass, prop, env, node.line)
                return obj.properties[prop]
            raise EPLRuntimeError(f'{obj.klass.name} has no property "{prop}".', node.line)

        if isinstance(obj, EPLDict):
            if prop in obj.data: return obj.data[prop]
            raise EPLRuntimeError(f'Map has no key "{prop}".', node.line)

        if isinstance(obj, dict) and obj.get('__is_module__'):
            member = obj.get(prop)
            if member is not None:
                # Unwrap constants (stored as {'value': x, 'type': y})
                if isinstance(member, dict) and 'value' in member and 'type' in member and len(member) == 2:
                    return member['value']
                return member
            raise EPLRuntimeError(
                f'Module "{obj.get("__name__", "?")}" has no member "{prop}".', node.line)

        if isinstance(obj, PythonModule):
            if hasattr(obj.module, prop):
                attr = getattr(obj.module, prop)
                if callable(attr):
                    return attr  # return callable for later use
                # Wrap sub-modules, classes, and complex objects for chaining
                if isinstance(attr, type) or (hasattr(attr, '__dict__') and not isinstance(attr, (int, float, str, bool))):
                    return PythonModule(attr, f"{obj.name}.{prop}")
                return self._wrap_python_result(attr)
            raise EPLRuntimeError(f'Python module "{obj.name}" has no attribute "{prop}".', node.line)

        raise EPLTypeError(f'{self._type_name(obj)} has no property "{prop}".', node.line)

    # ─── Binary & Unary ──────────────────────────────────

    def _eval_binary(self, node: ast.BinaryOp, env: Environment):
        op = node.operator

        # Short-circuit: evaluate left first for and/or
        if op == 'and':
            left = self._eval(node.left, env)
            if not self._is_truthy(left):
                return False
            right = self._eval(node.right, env)
            return self._is_truthy(right)
        if op == 'or':
            left = self._eval(node.left, env)
            if self._is_truthy(left):
                return True
            right = self._eval(node.right, env)
            return self._is_truthy(right)

        left = self._eval(node.left, env)
        right = self._eval(node.right, env)

        # Operator overloading: check for dunder methods on class instances
        if isinstance(left, EPLInstance) and op in _OP_DUNDER:
            method = left.get_method(_OP_DUNDER[op])
            if method:
                return self._call_instance_method(left, _OP_DUNDER[op], [right], env, node.line)
        if isinstance(right, EPLInstance) and op in _OP_DUNDER:
            if op in _OP_REFLECTED:
                method = right.get_method(_OP_REFLECTED[op])
                if method:
                    return self._call_instance_method(right, _OP_REFLECTED[op], [left], env, node.line)

        if op == '+':
            if isinstance(left, str) or isinstance(right, str):
                return str(self._format_value(left)) + str(self._format_value(right))
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                result = left + right
                return int(result) if isinstance(left, int) and isinstance(right, int) else result
            raise EPLTypeError(f"Cannot add {self._type_name(left)} and {self._type_name(right)}.", node.line)

        if op == '-':
            self._ensure_numeric(left, right, '-', node.line)
            result = left - right
            return int(result) if isinstance(left, int) and isinstance(right, int) else result

        if op == '*':
            if isinstance(left, str) and isinstance(right, int): return left * right
            if isinstance(left, int) and isinstance(right, str): return right * left
            self._ensure_numeric(left, right, '*', node.line)
            result = left * right
            return int(result) if isinstance(left, int) and isinstance(right, int) else result

        if op == '/':
            self._ensure_numeric(left, right, '/', node.line)
            if right == 0:
                raise EPLRuntimeError("Cannot divide by zero.", node.line)
            result = left / right
            if isinstance(left, int) and isinstance(right, int) and left % right == 0:
                return int(result)
            return result

        if op == '%':
            self._ensure_numeric(left, right, '%', node.line)
            if right == 0:
                raise EPLRuntimeError("Cannot modulo by zero.", node.line)
            return left % right

        if op == '**':
            self._ensure_numeric(left, right, '**', node.line)
            if isinstance(right, int) and right > 10000:
                raise EPLRuntimeError(f'Exponent too large ({right}). Maximum is 10000.', node.line)
            result = left ** right
            return int(result) if isinstance(left, int) and isinstance(right, int) and right >= 0 else result

        if op == '//':
            self._ensure_numeric(left, right, '//', node.line)
            if right == 0:
                raise EPLRuntimeError("Cannot divide by zero.", node.line)
            return left // right

        if op == '>': self._ensure_comparable(left, right, node.line); return left > right
        if op == '<': self._ensure_comparable(left, right, node.line); return left < right
        if op == '>=': self._ensure_comparable(left, right, node.line); return left >= right
        if op == '<=': self._ensure_comparable(left, right, node.line); return left <= right
        if op == '==': return left == right
        if op == '!=': return left != right

        raise EPLRuntimeError(f"Unknown operator: {op}", node.line)

    def _eval_unary(self, node: ast.UnaryOp, env: Environment):
        operand = self._eval(node.operand, env)
        if node.operator == 'not':
            return not self._is_truthy(operand)
        if node.operator == '-':
            if not isinstance(operand, (int, float)):
                raise EPLTypeError(f"Cannot negate {self._type_name(operand)}.", getattr(node, 'line', None))
            return -operand
        raise EPLRuntimeError(f"Unknown operator: {node.operator}", getattr(node, 'line', None))

    # ─── Helpers ──────────────────────────────────────────

    def _is_truthy(self, value) -> bool:
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, int): return value != 0
        if isinstance(value, float): return value != 0.0
        if isinstance(value, str): return len(value) > 0
        if isinstance(value, list): return len(value) > 0
        return True

    def _type_name(self, value) -> str:
        if isinstance(value, bool): return "boolean"
        if isinstance(value, int): return "integer"
        if isinstance(value, float): return "decimal"
        if isinstance(value, str): return "text"
        if isinstance(value, list): return "list"
        if isinstance(value, EPLDict): return "map"
        if isinstance(value, EPLClass): return "class"
        if isinstance(value, EPLInstance): return value.klass.name
        if isinstance(value, PythonModule): return "python module"
        if isinstance(value, EPLLambda): return "lambda"
        if isinstance(value, ast.FunctionDef): return "function"
        if isinstance(value, EPLFuture): return "future"
        if isinstance(value, EPLGenerator): return "generator"
        if isinstance(value, dict) and value.get('is_async'): return "async function"
        if value is None: return "nothing"
        return "unknown"

    def _format_value(self, value) -> str:
        if value is None: return "nothing"
        if isinstance(value, bool): return "true" if value else "false"
        if isinstance(value, list):
            return "[" + ", ".join(self._format_value(v) for v in value) + "]"
        if isinstance(value, EPLDict):
            pairs = [f"{k}: {self._format_value(v)}" for k, v in value.data.items()]
            return "{" + ", ".join(pairs) + "}"
        if isinstance(value, EPLInstance):
            str_method = value.get_method('__str__')
            if str_method:
                try:
                    return str(self._call_instance_method(value, '__str__', [], Environment(name="__str__"), 0))
                except Exception:
                    pass
            return f"<{value.klass.name} instance>"
        if isinstance(value, EPLClass): return f"<class {value.name}>"
        if isinstance(value, PythonModule): return f"<python module {value.name}>"
        if isinstance(value, EPLLambda): return repr(value)
        if isinstance(value, ast.FunctionDef): return f"<function {value.name}>"
        if isinstance(value, EPLFuture): return repr(value)
        return str(value)

    def _coerce_type(self, value, target_type, line):
        actual = self._type_name(value)
        if target_type == "integer":
            if isinstance(value, int) and not isinstance(value, bool): return value
            if isinstance(value, float) and value == int(value): return int(value)
            raise EPLTypeError(f"Expected integer, got {actual}.", line)
        if target_type == "decimal":
            if isinstance(value, (int, float)) and not isinstance(value, bool): return float(value)
            raise EPLTypeError(f"Expected decimal, got {actual}.", line)
        if target_type == "text":
            if isinstance(value, str): return value
            raise EPLTypeError(f"Expected text, got {actual}.", line)
        if target_type == "boolean":
            if isinstance(value, bool): return value
            raise EPLTypeError(f"Expected boolean, got {actual}.", line)
        if target_type == "list":
            if isinstance(value, list): return value
            raise EPLTypeError(f"Expected list, got {actual}.", line)
        return value

    def _ensure_numeric(self, left, right, op, line):
        if not isinstance(left, (int, float)) or isinstance(left, bool):
            raise EPLTypeError(f"Cannot use '{op}' with {self._type_name(left)}.", line)
        if not isinstance(right, (int, float)) or isinstance(right, bool):
            raise EPLTypeError(f"Cannot use '{op}' with {self._type_name(right)}.", line)

    def _ensure_comparable(self, left, right, line):
        if type(left) != type(right):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return
            raise EPLTypeError(f"Cannot compare {self._type_name(left)} with {self._type_name(right)}.", line)

    # ─── v0.5: Web Framework ─────────────────────────────

    def _exec_webapp(self, node: ast.WebApp, env: Environment):
        """Create WebApp called myApp"""
        from epl.web import EPLWebApp
        app = EPLWebApp(node.name)
        env.define_variable(node.name, app)
        self._web_app = app

    def _exec_route(self, node: ast.Route, env: Environment):
        """Route "/path" shows/responds with ... End"""
        # Find the active web app in the environment
        app = self._find_webapp(env)
        if app is None:
            raise EPLRuntimeError("No WebApp created. Use: Create WebApp called myApp", node.line)
        app.add_route(node.path, node.response_type, node.body)

    def _exec_start_server(self, node: ast.StartServer, env: Environment):
        """Start myApp on port 3000"""
        from epl.web import start_server
        app = env.get_variable(node.app_name)
        if app is None:
            raise EPLRuntimeError(f"WebApp '{node.app_name}' not found.", node.line)
        port = self._eval(node.port, env) if not isinstance(node.port, int) else node.port
        port = int(port)
        start_server(app, port, interpreter=self)

    def _find_webapp(self, env):
        """Find the first EPLWebApp in the environment."""
        from epl.web import EPLWebApp
        # Search all variables in the environment chain
        current = env
        while current:
            for name, info in current.variables.items():
                val = info['value'] if isinstance(info, dict) else info
                if isinstance(val, EPLWebApp):
                    return val
            current = getattr(current, 'parent', None)
        return None

    # ─── v1.4: GUI Framework ─────────────────────────────

    def _get_gui_window(self):
        """Get or lazily import the GUI module and current window."""
        try:
            from epl.gui import get_window, create_window, gui_available
            if not gui_available():
                raise EPLRuntimeError("GUI is not available (tkinter not installed).")
            return get_window, create_window
        except ImportError:
            raise EPLRuntimeError("GUI module not available.")

    def _exec_window_create(self, node: ast.WindowCreate, env: Environment):
        """Window "My App" ... End"""
        get_window, create_window = self._get_gui_window()
        title = self._eval(node.title, env) if node.title else "EPL Application"
        title = str(title)
        width = int(self._eval(node.width, env)) if node.width else 800
        height = int(self._eval(node.height, env)) if node.height else 600
        win = create_window(title, width, height)
        env.define_variable('_epl_window', win)
        # Execute body (widget definitions, etc.)
        for stmt in node.body:
            self._exec_statement(stmt, env)
        # Start the GUI event loop
        win.run()

    def _exec_widget_add(self, node: ast.WidgetAdd, env: Environment):
        """Add a widget to the current window."""
        from epl.gui import get_window
        win = get_window()
        if win is None:
            raise EPLRuntimeError("No window created. Use: Window \"Title\" ... End", node.line)
        text_val = self._eval(node.text, env) if node.text else ""
        name = node.name or f"_widget_{id(node)}"
        # Evaluate properties
        props = {}
        for k, v in node.properties.items():
            props[k] = self._eval(v, env) if hasattr(v, 'line') else v

        wtype = node.widget_type.lower()
        if wtype == 'button':
            action_fn = None
            if node.action:
                action_val = self._eval(node.action, env)
                if callable(action_val):
                    action_fn = action_val
                elif isinstance(action_val, str):
                    # Look up function by name
                    fn = env.get_variable(action_val)
                    if fn and callable(fn):
                        action_fn = fn
                    else:
                        action_fn = lambda av=action_val, e=env: self._call_epl_function(av, [], e)
                elif isinstance(action_val, EPLLambda):
                    action_fn = lambda lam=action_val, e=env: self._call_lambda(lam, [], e)
            win.add_button(str(text_val), name, action_fn)
        elif wtype == 'label':
            win.add_label(str(text_val), name)
        elif wtype == 'input':
            placeholder = str(props.get('placeholder', ''))
            win.add_input(name, placeholder)
        elif wtype == 'textarea':
            win.add_text_area(name)
        elif wtype == 'checkbox':
            win.add_checkbox(str(text_val), name)
        elif wtype == 'dropdown':
            options = text_val if isinstance(text_val, list) else [str(text_val)]
            win.add_dropdown(options, name)
        elif wtype == 'canvas':
            w = int(props.get('width', 400))
            h = int(props.get('height', 300))
            win.add_canvas(name, w, h)
        elif wtype == 'slider':
            from_val = int(text_val) if text_val else 0
            to_val = int(props.get('max', 100))
            win.add_input(name, f"Slider {from_val}-{to_val}")
        elif wtype == 'progress':
            val = int(text_val) if text_val else 0
            win.add_label(f"[{'#' * (val // 10)}{' ' * (10 - val // 10)}] {val}%", name)
        elif wtype == 'image':
            try:
                win.add_image(str(text_val), name)
            except Exception:
                win.add_label(f"[Image: {text_val}]", name)
        elif wtype == 'listbox':
            items = text_val if isinstance(text_val, list) else []
            win.add_listbox(items, name)
        else:
            win.add_label(str(text_val), name)

        # Store widget name in env
        if node.name:
            env.define_variable(node.name, name)

    def _exec_layout_block(self, node: ast.LayoutBlock, env: Environment):
        """Row/Column layout container."""
        from epl.gui import get_window
        win = get_window()
        if win is None:
            raise EPLRuntimeError("No window created.", node.line)
        if node.direction == 'row':
            frame = win.add_row()
        else:
            frame = win.add_column()
        for child in node.children:
            self._exec_statement(child, env)

    def _exec_bind_event(self, node: ast.BindEvent, env: Environment):
        """Bind widgetName "click" to handler"""
        from epl.gui import get_window
        win = get_window()
        if win is None:
            raise EPLRuntimeError("No window created.", node.line)
        event_type = self._eval(node.event_type, env) if hasattr(node.event_type, 'line') else str(node.event_type)
        handler_val = self._eval(node.handler, env)
        callback = None
        if isinstance(handler_val, EPLLambda):
            callback = lambda e=None, lam=handler_val, ev=env: self._call_lambda(lam, [], ev)
        elif callable(handler_val):
            callback = handler_val
        elif isinstance(handler_val, str):
            fn = env.get_variable(handler_val)
            if fn:
                callback = lambda e=None, f=fn, ev=env: self._call_epl_function(f, [], ev)
        if callback:
            win.on_event(node.widget_name, str(event_type), callback)

    def _exec_dialog_show(self, node: ast.DialogShow, env: Environment):
        """Show dialog."""
        from epl.gui import get_window
        win = get_window()
        if win is None:
            raise EPLRuntimeError("No window created.", node.line)
        msg = str(self._eval(node.message, env))
        dtype = node.dialog_type.lower()
        if dtype == 'error':
            win.show_error(msg)
        elif dtype in ('yesno', 'confirm'):
            result = win.ask_yes_no(msg)
            return result
        elif dtype == 'input':
            result = win.ask_text(msg)
            return result
        else:
            win.show_message(msg)

    def _exec_menu_def(self, node: ast.MenuDef, env: Environment):
        """Define menu."""
        from epl.gui import get_window
        win = get_window()
        if win is None:
            raise EPLRuntimeError("No window created.", node.line)
        # Menu items are button-like statements
        menu_items = []
        for item in node.items:
            if isinstance(item, ast.WidgetAdd) and item.widget_type == 'button':
                text_val = self._eval(item.text, env) if item.text else "Item"
                action = None
                if item.action:
                    action = self._eval(item.action, env)
                menu_items.append((str(text_val), action))
        menu_def = {node.label: menu_items}
        win.add_menu(menu_def)

    def _exec_canvas_draw(self, node: ast.CanvasDraw, env: Environment):
        """Draw on canvas."""
        from epl.gui import get_window
        win = get_window()
        if win is None:
            raise EPLRuntimeError("No window created.", node.line)
        props = {}
        for k, v in node.properties.items():
            props[k] = self._eval(v, env) if hasattr(v, 'line') else v
        x = int(props.get('x', 0))
        y = int(props.get('y', 0))
        color = str(props.get('color', 'white'))
        shape = node.shape
        if shape == 'rect':
            w = int(props.get('width', 50))
            h = int(props.get('height', 50))
            win.draw_rect(node.canvas_name, x, y, w, h, color)
        elif shape == 'circle':
            r = int(props.get('radius', 25))
            win.draw_circle(node.canvas_name, x, y, r, color)
        elif shape == 'line':
            x2 = int(props.get('x2', x + 50))
            y2 = int(props.get('y2', y + 50))
            win.draw_line(node.canvas_name, x, y, x2, y2, color)
        elif shape in ('text', 'string'):
            txt = str(props.get('value', ''))
            win.draw_text(node.canvas_name, x, y, txt, color)

    def _call_epl_function(self, func_name, args, env):
        """Helper to call an EPL function by name from event handlers."""
        fn = env.get_variable(func_name) if isinstance(func_name, str) else func_name
        if fn is None:
            return
        if isinstance(fn, dict) and 'body' in fn:
            child = env.create_child(f"call_{func_name}")
            params = fn.get('params', [])
            for i, (pname, ptype, pdefault) in enumerate(params):
                if i < len(args):
                    child.define_variable(pname, args[i])
                elif pdefault is not None:
                    child.define_variable(pname, self._eval(pdefault, env))
            try:
                self._exec_block(fn['body'], child)
            except ReturnSignal as r:
                return r.value
        elif callable(fn):
            return fn(*args)

    def _call_lambda(self, lam, args, env):
        """Helper to call an EPL lambda from event handlers."""
        child = lam.closure_env.create_child("lambda_call")
        for i, p in enumerate(lam.params):
            child.define_variable(p, args[i] if i < len(args) else None)
        return self._eval(lam.body_node, child)

    # ─── v1.4: Async / Super ─────────────────────────────

    def _exec_async_function_def(self, node: ast.AsyncFunctionDef, env: Environment):
        """Register async function. When called, it runs in thread pool and returns EPLFuture."""
        func_info = {
            'name': node.name,
            'params': node.params,
            'return_type': node.return_type,
            'body': node.body,
            'closure_env': env,
            'is_async': True,
        }
        env.define_variable(node.name, func_info)

    def _eval_await(self, node: ast.AwaitExpression, env: Environment):
        """Await an EPLFuture or evaluate expression that returns a future."""
        val = self._eval(node.expression, env)
        if isinstance(val, EPLFuture):
            try:
                return val.result(timeout=60)
            except _futures.TimeoutError:
                raise EPLRuntimeError(f"Await timed out for {val.name}.", node.line)
            except Exception as e:
                raise EPLRuntimeError(f"Async error in {val.name}: {e}", node.line)
        # If it's not a future, just return the value (already resolved)
        return val

    def _call_async_function(self, func_info, args, env, line):
        """Execute an async function dict in the thread pool, return EPLFuture."""
        params = func_info['params']
        body = func_info['body']
        closure_env = func_info.get('closure_env', env)
        name = func_info.get('name', '<async>')

        required = sum(1 for p in params if (p[2] if len(p) > 2 else None) is None)
        if len(args) < required or len(args) > len(params):
            raise EPLRuntimeError(
                f'Async function "{name}" expects {required}-{len(params)} argument(s), '
                f'but got {len(args)}.', line)

        def run_async():
            func_env = closure_env.create_child(name=f"async:{name}")
            for i, param in enumerate(params):
                param_name = param[0]
                param_type = param[1] if len(param) > 1 else None
                default_expr = param[2] if len(param) > 2 else None
                if i < len(args):
                    value = args[i]
                elif default_expr is not None:
                    value = self._eval(default_expr, closure_env)
                else:
                    value = None
                if param_type:
                    value = self._coerce_type(value, param_type, line)
                func_env.define_variable(param_name, value, param_type)
            try:
                self._exec_block(body, func_env)
            except ReturnSignal as ret:
                return ret.value
            return None

        future = _thread_pool.submit(run_async)
        return EPLFuture(future, name)

    def _exec_super_call(self, node: ast.SuperCall, env: Environment):
        """Call parent class method or parent constructor."""
        # Find 'this' in env
        this = env.get_variable('this')
        if this is None or not isinstance(this, EPLInstance):
            raise EPLRuntimeError("Super can only be used inside a class method.", node.line)
        parent = this.klass.parent
        if parent is None:
            raise EPLRuntimeError(f"Class {this.klass.name} has no parent class.", node.line)
        if node.method_name:
            method = parent.methods.get(node.method_name)
            if method is None:
                raise EPLRuntimeError(f"Parent class {parent.name} has no method '{node.method_name}'.", node.line)
            args = [self._eval(a, env) for a in node.arguments]
            child = env.create_child(f"super.{node.method_name}")
            child.define_variable('this', this)
            # Copy instance properties into method env
            for prop_name, prop_val in this.properties.items():
                child.define_variable(prop_name, prop_val)
            params = method.params if hasattr(method, 'params') else []
            for i, p in enumerate(params):
                pname = p[0] if isinstance(p, tuple) else p
                if i < len(args):
                    child.define_variable(pname, args[i])
            try:
                self._exec_block(method.body if hasattr(method, 'body') else method['body'], child)
            except ReturnSignal as r:
                # Sync properties back
                for prop_name in this.properties:
                    if child.has_variable(prop_name):
                        this.properties[prop_name] = child.get_variable(prop_name)
                return r.value
            # Sync properties back
            for prop_name in this.properties:
                if child.has_variable(prop_name):
                    this.properties[prop_name] = child.get_variable(prop_name)
        else:
            # Super() - call parent constructor (init method or copy defaults)
            args = [self._eval(a, env) for a in node.arguments]
            init_method = parent.methods.get('init')
            if init_method:
                self._call_instance_method(this, 'init', args, env, node.line)
            else:
                for prop_name, prop_val in parent.defaults.items():
                    this.properties[prop_name] = prop_val

    # ═══════════════════════════════════════════════════════
    #  v4.0: Interface System
    # ═══════════════════════════════════════════════════════

    def _exec_interface_def(self, node, env: Environment):
        """Register an interface definition in the environment."""
        iface = {
            '__is_interface__': True,
            'name': node.name,
            'methods': node.methods,  # list of (name, params, return_type)
            'extends': node.extends,
        }
        env.define_variable(node.name, iface)

    def _validate_interface_impl(self, klass, iface_name, env, line):
        """Validate that a class implements all methods of an interface."""
        try:
            iface = env.get_variable(iface_name)
        except Exception:
            raise EPLRuntimeError(f'Interface "{iface_name}" not found.', line)

        if not isinstance(iface, dict) or not iface.get('__is_interface__'):
            raise EPLRuntimeError(f'"{iface_name}" is not an interface.', line)

        for method_name, params, return_type in iface.get('methods', []):
            if method_name not in klass.methods:
                raise EPLRuntimeError(
                    f'Class "{klass.name}" does not implement method "{method_name}" '
                    f'required by interface "{iface_name}".', line)

        # Check parent interfaces recursively
        for parent_iface in iface.get('extends', []):
            self._validate_interface_impl(klass, parent_iface, env, line)

    # ═══════════════════════════════════════════════════════
    #  v4.0: Module System
    # ═══════════════════════════════════════════════════════

    def _exec_module_def(self, node, env: Environment):
        """Execute a module definition and register its namespace."""
        mod_env = env.create_child(f"module:{node.name}")

        # Execute module body in isolated scope
        self._exec_block(node.body, mod_env)

        # Build module namespace object
        module_ns = {'__is_module__': True, 'name': node.name}

        # If exports list is empty, export everything
        if node.exports:
            export_names = set(node.exports)
        else:
            export_names = set(mod_env.variables.keys()) | set(mod_env.functions.keys())

        for name in export_names:
            if mod_env.has_variable(name):
                module_ns[name] = mod_env.get_variable(name)
            if mod_env.has_function(name):
                module_ns[name] = mod_env.get_function(name)

        env.define_variable(node.name, module_ns)

    def _exec_module_access(self, node, env: Environment):
        """Handle Module::member access."""
        try:
            mod = env.get_variable(node.module_name)
        except Exception:
            raise EPLRuntimeError(f'Module "{node.module_name}" not found.', node.line)

        if not isinstance(mod, dict) or not mod.get('__is_module__'):
            raise EPLRuntimeError(f'"{node.module_name}" is not a module.', node.line)

        member = mod.get(node.member_name)
        if member is None:
            raise EPLRuntimeError(
                f'Module "{node.module_name}" has no member "{node.member_name}".', node.line)

        # Unwrap constants (stored as {'value': x, 'type': y})
        if (isinstance(member, dict) and 'value' in member and 'type' in member
                and len(member) == 2 and node.arguments is None):
            return member['value']

        if node.arguments is not None:
            # It's a function call
            if callable(member):
                return member(*[self._eval(a, env) for a in node.arguments])
            elif hasattr(member, 'body'):
                # It's a FunctionDef AST node — execute directly
                func_node = member
                call_env = env.create_child(f"{node.module_name}::{node.member_name}")
                # Register all module functions so recursive/cross calls work
                for mname, mval in mod.items():
                    if mname.startswith('__'):
                        continue
                    if hasattr(mval, 'body'):
                        call_env.define_function(mname, mval)
                    else:
                        call_env.define_variable(mname, mval)
                args = [self._eval(a, env) for a in node.arguments]
                params = func_node.params if hasattr(func_node, 'params') else []
                for i, param in enumerate(params):
                    p_name = param[0] if isinstance(param, (tuple, list)) else getattr(param, 'name', str(param))
                    p_type = param[1] if isinstance(param, (tuple, list)) and len(param) > 1 else None
                    val = args[i] if i < len(args) else None
                    if p_type:
                        val = self._coerce_type(val, p_type, node.line)
                    call_env.define_variable(p_name, val, p_type)
                result = None
                try:
                    self._exec_block(func_node.body, call_env)
                except ReturnSignal as ret:
                    result = ret.value
                return result

        return member

    # ═══════════════════════════════════════════════════════
    #  v4.0 → v6.0: Generator/Yield Support (full protocol)
    # ═══════════════════════════════════════════════════════

    class _YieldSignal(Exception):
        """Internal signal for yielded values."""
        def __init__(self, value):
            self.value = value

    def _exec_yield(self, node, env: Environment):
        """Yield a value from a generator function."""
        value = self._eval(node.value, env) if node.value else None
        # Check if we're inside a generator context (thread-based)
        gen = self._find_generator(env)
        if gen is not None:
            gen.yield_value(value)
            return
        raise self._YieldSignal(value)

    def _find_generator(self, env):
        """Walk up the environment chain looking for __generator__ variable."""
        current = env
        while current is not None:
            try:
                val = current.get_variable('__generator__')
                if isinstance(val, EPLGenerator):
                    return val
            except Exception:
                pass
            current = getattr(current, 'parent', None)
        return None

    def _call_generator_function(self, func, args, env, line):
        """Call a function that contains yield — returns an EPLGenerator."""
        func_env = env.create_child(name=f"generator:{func.name}")
        for i, param in enumerate(func.params):
            param_name = param[0]
            param_type = param[1] if len(param) > 1 else None
            default_expr = param[2] if len(param) > 2 else None
            if i < len(args):
                value = args[i]
            elif default_expr is not None:
                value = self._eval(default_expr, env)
            else:
                value = None
            if param_type:
                value = self._coerce_type(value, param_type, line)
            func_env.define_variable(param_name, value, param_type)

        return EPLGenerator(self, func.body, func_env, func.name)

    def _func_contains_yield(self, func):
        """Check if a FunctionDef body contains any YieldStatement (cached)."""
        if not isinstance(func, ast.FunctionDef):
            return False
        func_id = id(func)
        if func_id in self._yield_cache:
            return self._yield_cache[func_id]
        result = self._body_has_yield(func.body)
        self._yield_cache[func_id] = result
        return result

    def _body_has_yield(self, stmts):
        """Recursively check if statements contain yield."""
        for s in stmts:
            if isinstance(s, ast.YieldStatement):
                return True
            for attr in ('body', 'then_body', 'else_body', 'try_body', 'catch_body'):
                child = getattr(s, attr, None)
                if isinstance(child, list) and self._body_has_yield(child):
                    return True
        return False

    # ═══════════════════════════════════════════════════════
    #  v4.0: Destructuring Assignment
    # ═══════════════════════════════════════════════════════

    def _exec_destructure(self, node, env: Environment):
        """Create [a, b, c] equal to someList"""
        value = self._eval(node.value, env)
        if not isinstance(value, list):
            raise EPLRuntimeError('Destructuring requires a list value.', node.line)
        if len(node.names) > len(value):
            raise EPLRuntimeError(
                f'Not enough values to unpack: expected {len(node.names)}, got {len(value)}.', node.line)
        for i, name in enumerate(node.names):
            env.define_variable(name, value[i])

