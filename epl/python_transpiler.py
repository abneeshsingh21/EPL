"""
EPL-to-Python Transpiler
========================
Transpiles EPL AST to clean, idiomatic Python 3 code.
Usage:  epl export python myprogram.epl
"""

from epl import ast_nodes as ast
import re as _re

# ── Public API ───────────────────────────────────────────

def transpile_to_python(program: ast.Program) -> str:
    """Transpile an EPL Program AST to Python 3 source code."""
    return PythonTranspiler().transpile(program)


# ── Transpiler ───────────────────────────────────────────

class PythonTranspiler:
    def __init__(self):
        self.indent = 0
        self.output: list[str] = []
        self.imports: set[str] = set()       # 'import X' lines
        self.from_imports: dict[str, set] = {}  # 'from X import Y'
        self.in_class = False
        self.class_properties: set[str] = set()
        self.user_functions: set[str] = set()

    # ── Main entry ─────────────────────────────────────

    def transpile(self, program: ast.Program) -> str:
        # Pre-scan for function names
        for stmt in program.statements:
            if isinstance(stmt, ast.FunctionDef):
                self.user_functions.add(stmt.name)
            elif isinstance(stmt, ast.AsyncFunctionDef):
                self.user_functions.add(stmt.name)

        for stmt in program.statements:
            self._emit_stmt(stmt)

        header = []
        header.append('#!/usr/bin/env python3')
        header.append('"""Auto-generated from EPL source."""')
        header.append('')
        for mod in sorted(self.imports):
            header.append(mod)
        for mod, names in sorted(self.from_imports.items()):
            header.append(f'from {mod} import {", ".join(sorted(names))}')
        if self.imports or self.from_imports:
            header.append('')
        header.append('')
        return '\n'.join(header) + '\n'.join(self.output) + '\n'

    # ── Helpers ────────────────────────────────────────

    def _line(self, text: str):
        self.output.append('    ' * self.indent + text)

    def _blank(self):
        self.output.append('')

    def _add_import(self, module: str):
        self.imports.add(f'import {module}')

    def _add_from_import(self, module: str, name: str):
        self.from_imports.setdefault(module, set()).add(name)

    def _py_string(self, s) -> str:
        s = str(s)
        # Check for template patterns $var or ${expr}
        tmpl = _re.search(r'\$\{[^}]+\}|\$[A-Za-z_]\w*', s)
        if tmpl:
            # Convert to f-string
            result = s
            result = _re.sub(r'\$\{([^}]+)\}', r'{\1}', result)
            result = _re.sub(r'\$([A-Za-z_]\w*)', r'{\1}', result)
            esc = result.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
            return f"f'{esc}'"
        esc = s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f"'{esc}'"

    # ── Statement dispatch ─────────────────────────────

    def _emit_stmt(self, node):
        if node is None:
            return
        if isinstance(node, ast.VarDeclaration):
            self._emit_var_decl(node)
        elif isinstance(node, ast.VarAssignment):
            self._emit_var_assign(node)
        elif isinstance(node, ast.PrintStatement):
            self._emit_print(node)
        elif isinstance(node, ast.InputStatement):
            self._emit_input(node)
        elif isinstance(node, ast.IfStatement):
            self._emit_if(node)
        elif isinstance(node, ast.WhileLoop):
            self._emit_while(node)
        elif isinstance(node, ast.RepeatLoop):
            self._emit_repeat(node)
        elif isinstance(node, ast.ForRange):
            self._emit_for_range(node)
        elif isinstance(node, ast.ForEachLoop):
            self._emit_for_each(node)
        elif isinstance(node, ast.AsyncFunctionDef):
            self._emit_async_function(node)
        elif isinstance(node, ast.FunctionDef):
            self._emit_function(node)
        elif isinstance(node, ast.FunctionCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.ReturnStatement):
            self._emit_return(node)
        elif isinstance(node, ast.BreakStatement):
            self._line('break')
        elif isinstance(node, ast.ContinueStatement):
            self._line('continue')
        elif isinstance(node, ast.ClassDef):
            self._emit_class(node)
        elif isinstance(node, ast.MatchStatement):
            self._emit_match(node)
        elif isinstance(node, ast.TryCatch):
            self._emit_try_catch(node)
        elif isinstance(node, ast.TryCatchFinally):
            self._emit_try_catch_finally(node)
        elif isinstance(node, ast.MethodCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.PropertySet):
            self._emit_prop_set(node)
        elif isinstance(node, ast.IndexSet):
            self._emit_index_set(node)
        elif isinstance(node, ast.AugmentedAssignment):
            self._emit_aug_assign(node)
        elif isinstance(node, ast.ThrowStatement):
            self._emit_throw(node)
        elif isinstance(node, ast.FileWrite):
            self._emit_file_write(node)
        elif isinstance(node, ast.FileAppend):
            self._emit_file_append(node)
        elif isinstance(node, ast.ConstDeclaration):
            self._emit_const(node)
        elif isinstance(node, ast.AssertStatement):
            self._emit_assert(node)
        elif isinstance(node, ast.ExitStatement):
            self._add_import('sys')
            self._line('sys.exit(0)')
        elif isinstance(node, ast.WaitStatement):
            self._emit_wait(node)
        elif isinstance(node, ast.EnumDef):
            self._emit_enum(node)
        elif isinstance(node, ast.ImportStatement):
            self._emit_import(node)
        elif isinstance(node, ast.UseStatement):
            self._emit_use(node)
        elif isinstance(node, ast.SuperCall):
            self._emit_super_call(node)
        elif isinstance(node, ast.InterfaceDefNode):
            self._emit_interface(node)
        elif isinstance(node, ast.ModuleDef):
            self._emit_module(node)
        elif isinstance(node, ast.ExportStatement):
            self._line(f'# export: {node.name}')
        elif isinstance(node, ast.VisibilityModifier):
            self._line(f'# {node.visibility}')
            self._emit_stmt(node.statement)
        elif isinstance(node, ast.StaticMethodDef):
            self._emit_static_method(node)
        elif isinstance(node, ast.YieldStatement):
            val = f' {self._expr(node.value)}' if node.value else ''
            self._line(f'yield{val}')
        elif isinstance(node, ast.DestructureAssignment):
            names = ', '.join(node.names)
            self._line(f'{names} = {self._expr(node.value)}')
        elif isinstance(node, ast.ModuleAccess):
            self._line(f'{self._expr(node)}')
        else:
            self._line(f'# Unsupported: {type(node).__name__}')

    # ── Statement emitters ─────────────────────────────

    def _emit_var_decl(self, node):
        self._line(f'{node.name} = {self._expr(node.value)}')

    def _emit_var_assign(self, node):
        if self.in_class and node.name in self.class_properties:
            self._line(f'self.{node.name} = {self._expr(node.value)}')
        else:
            self._line(f'{node.name} = {self._expr(node.value)}')

    def _emit_print(self, node):
        self._line(f'print({self._expr(node.expression)})')

    def _emit_input(self, node):
        prompt = self._expr(node.prompt) if node.prompt else "''"
        self._line(f'{node.variable_name} = input({prompt})')

    def _emit_if(self, node):
        self._line(f'if {self._expr(node.condition)}:')
        self.indent += 1
        for s in node.then_body:
            self._emit_stmt(s)
        if not node.then_body:
            self._line('pass')
        self.indent -= 1
        if node.else_body:
            # Check for elif pattern (else_body is single IfStatement)
            if len(node.else_body) == 1 and isinstance(node.else_body[0], ast.IfStatement):
                self._line(f'elif {self._expr(node.else_body[0].condition)}:')
                self.indent += 1
                for s in node.else_body[0].then_body:
                    self._emit_stmt(s)
                if not node.else_body[0].then_body:
                    self._line('pass')
                self.indent -= 1
                if node.else_body[0].else_body:
                    self._emit_else(node.else_body[0].else_body)
            else:
                self._emit_else(node.else_body)

    def _emit_else(self, else_body):
        if len(else_body) == 1 and isinstance(else_body[0], ast.IfStatement):
            self._line(f'elif {self._expr(else_body[0].condition)}:')
            self.indent += 1
            for s in else_body[0].then_body:
                self._emit_stmt(s)
            if not else_body[0].then_body:
                self._line('pass')
            self.indent -= 1
            if else_body[0].else_body:
                self._emit_else(else_body[0].else_body)
        else:
            self._line('else:')
            self.indent += 1
            for s in else_body:
                self._emit_stmt(s)
            if not else_body:
                self._line('pass')
            self.indent -= 1

    def _emit_while(self, node):
        self._line(f'while {self._expr(node.condition)}:')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_repeat(self, node):
        self._line(f'for _ in range({self._expr(node.count)}):')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_for_range(self, node):
        start = self._expr(node.start)
        end = self._expr(node.end)
        step = ''
        if hasattr(node, 'step') and node.step is not None:
            step = f', {self._expr(node.step)}'
        self._line(f'for {node.var_name} in range({start}, {end} + 1{step}):')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_for_each(self, node):
        self._line(f'for {node.var_name} in {self._expr(node.iterable)}:')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_function(self, node):
        self._blank()
        params = ', '.join(self._format_param(p) for p in node.params)
        if self.in_class:
            params = f'self, {params}' if params else 'self'
        ret = f' -> {self._py_type(node.return_type)}' if node.return_type else ''
        self._line(f'def {node.name}({params}){ret}:')
        self.indent += 1
        if node.body:
            for s in node.body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_async_function(self, node):
        self._add_import('asyncio')
        self._blank()
        params = ', '.join(self._format_param(p) for p in node.params)
        ret = f' -> {self._py_type(node.return_type)}' if node.return_type else ''
        self._line(f'async def {node.name}({params}){ret}:')
        self.indent += 1
        if node.body:
            for s in node.body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_return(self, node):
        if node.value:
            self._line(f'return {self._expr(node.value)}')
        else:
            self._line('return')

    def _emit_class(self, node):
        self._blank()
        parent = f'({node.parent})' if node.parent else ''
        self._line(f'class {node.name}{parent}:')
        self.indent += 1
        old_in_class = self.in_class
        old_props = self.class_properties.copy()
        self.in_class = True
        self.class_properties = set()

        # Separate fields from methods
        fields = []
        methods = []
        for item in node.body:
            if isinstance(item, (ast.VarDeclaration, ast.VarAssignment)):
                fields.append(item)
                self.class_properties.add(item.name)
            else:
                methods.append(item)

        # Generate __init__ from fields
        if fields:
            self._line('def __init__(self):')
            self.indent += 1
            if node.parent:
                self._line(f'super().__init__()')
            for f in fields:
                self._line(f'self.{f.name} = {self._expr(f.value)}')
            self.indent -= 1
            self._blank()

        for m in methods:
            self._emit_stmt(m)

        if not fields and not methods:
            self._line('pass')

        self.in_class = old_in_class
        self.class_properties = old_props
        self.indent -= 1
        self._blank()

    def _emit_match(self, node):
        expr = self._expr(node.expression)
        self._line(f'match {expr}:')
        self.indent += 1
        for clause in node.when_clauses:
            vals = ' | '.join(self._expr(v) for v in clause.values)
            self._line(f'case {vals}:')
            self.indent += 1
            for s in clause.body:
                self._emit_stmt(s)
            if not clause.body:
                self._line('pass')
            self.indent -= 1
        if node.default_body:
            self._line('case _:')
            self.indent += 1
            for s in node.default_body:
                self._emit_stmt(s)
            self.indent -= 1
        self.indent -= 1

    def _emit_try_catch(self, node):
        self._line('try:')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        if not node.try_body:
            self._line('pass')
        self.indent -= 1
        err_var = node.error_var or 'e'
        self._line(f'except Exception as {err_var}:')
        self.indent += 1
        if node.catch_body:
            for s in node.catch_body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        if hasattr(node, 'finally_body') and node.finally_body:
            self._line('finally:')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1

    def _emit_try_catch_finally(self, node):
        self._line('try:')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        if not node.try_body:
            self._line('pass')
        self.indent -= 1
        for err_type, err_var, body in node.catch_clauses:
            exc_type = err_type if err_type else 'Exception'
            var = err_var if err_var else 'e'
            self._line(f'except {exc_type} as {var}:')
            self.indent += 1
            if body:
                for s in body:
                    self._emit_stmt(s)
            else:
                self._line('pass')
            self.indent -= 1
        if node.finally_body:
            self._line('finally:')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1

    def _emit_prop_set(self, node):
        if self.in_class:
            self._line(f'self.{node.property_name} = {self._expr(node.value)}')
        else:
            self._line(f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)}')

    def _emit_index_set(self, node):
        self._line(f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)}')

    def _emit_aug_assign(self, node):
        if self.in_class and node.name in self.class_properties:
            self._line(f'self.{node.name} {node.operator} {self._expr(node.value)}')
        else:
            self._line(f'{node.name} {node.operator} {self._expr(node.value)}')

    def _emit_throw(self, node):
        self._line(f'raise Exception({self._expr(node.expression)})')

    def _emit_file_write(self, node):
        self._line(f'with open({self._expr(node.filepath)}, "w") as _f:')
        self.indent += 1
        self._line(f'_f.write(str({self._expr(node.content)}))')
        self.indent -= 1

    def _emit_file_append(self, node):
        self._line(f'with open({self._expr(node.filepath)}, "a") as _f:')
        self.indent += 1
        self._line(f'_f.write(str({self._expr(node.content)}) + "\\n")')
        self.indent -= 1

    def _emit_const(self, node):
        self._line(f'{node.name.upper()} = {self._expr(node.value)}  # constant')

    def _emit_assert(self, node):
        self._line(f'assert {self._expr(node.expression)}')

    def _emit_wait(self, node):
        self._add_import('time')
        self._line(f'time.sleep({self._expr(node.duration)})')

    def _emit_enum(self, node):
        self._add_from_import('enum', 'Enum')
        self._blank()
        self._line(f'class {node.name}(Enum):')
        self.indent += 1
        for i, member in enumerate(node.members):
            self._line(f'{member} = {i}')
        if not node.members:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_import(self, node):
        mod = node.filepath.replace('.epl', '').replace('/', '.').replace('\\', '.')
        if hasattr(node, 'alias') and node.alias:
            self._line(f'import {mod} as {node.alias}')
        else:
            self._line(f'import {mod}')

    def _emit_use(self, node):
        if node.alias:
            self._line(f'import {node.library} as {node.alias}')
        else:
            self._line(f'import {node.library}')

    def _emit_super_call(self, node):
        args = ', '.join(self._expr(a) for a in node.arguments)
        if node.method_name:
            self._line(f'super().{node.method_name}({args})')
        else:
            self._line(f'super().__init__({args})')

    def _emit_interface(self, node):
        self._add_from_import('abc', 'ABC')
        self._add_from_import('abc', 'abstractmethod')
        self._blank()
        extends = f'({", ".join(node.extends)}, ABC)' if node.extends else '(ABC)'
        self._line(f'class {node.name}{extends}:')
        self.indent += 1
        if node.methods:
            for m in node.methods:
                self._line('@abstractmethod')
                params = ', '.join(['self'] + [p[0] for p in m.params])
                self._line(f'def {m.name}({params}):')
                self.indent += 1
                self._line('pass')
                self.indent -= 1
                self._blank()
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_module(self, node):
        self._line(f'# Module: {node.name}')
        for s in node.body:
            self._emit_stmt(s)

    def _emit_static_method(self, node):
        self._line('@staticmethod')
        params = ', '.join(self._format_param(p) for p in node.params)
        self._line(f'def {node.name}({params}):')
        self.indent += 1
        if node.body:
            for s in node.body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    # ── Expression rendering ───────────────────────────

    def _expr(self, node) -> str:
        if node is None:
            return 'None'
        if isinstance(node, ast.Literal):
            return self._expr_literal(node)
        if isinstance(node, ast.Identifier):
            if self.in_class and node.name in self.class_properties:
                return f'self.{node.name}'
            return node.name
        if isinstance(node, ast.BinaryOp):
            return self._expr_binary(node)
        if isinstance(node, ast.UnaryOp):
            return self._expr_unary(node)
        if isinstance(node, ast.FunctionCall):
            return self._expr_call(node)
        if isinstance(node, ast.PropertyAccess):
            return f'{self._expr(node.obj)}.{node.property_name}'
        if isinstance(node, ast.MethodCall):
            return self._expr_method(node)
        if isinstance(node, ast.IndexAccess):
            return f'{self._expr(node.obj)}[{self._expr(node.index)}]'
        if isinstance(node, ast.SliceAccess):
            return self._expr_slice(node)
        if isinstance(node, ast.ListLiteral):
            elems = ', '.join(self._expr(e) for e in node.elements)
            return f'[{elems}]'
        if isinstance(node, ast.DictLiteral):
            pairs = []
            for k, v in node.pairs:
                if isinstance(k, str):
                    pairs.append(f'{self._py_string(k)}: {self._expr(v)}')
                else:
                    pairs.append(f'{self._expr(k)}: {self._expr(v)}')
            return '{' + ', '.join(pairs) + '}'
        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{node.class_name}({args})'
        if isinstance(node, ast.LambdaExpression):
            params = ', '.join(node.params)
            return f'lambda {params}: {self._expr(node.body)}'
        if isinstance(node, ast.TernaryExpression):
            return f'({self._expr(node.true_expr)} if {self._expr(node.condition)} else {self._expr(node.false_expr)})'
        if isinstance(node, ast.AwaitExpression):
            return f'await {self._expr(node.expression)}'
        if isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                return f'super().{node.method_name}({args})'
            return f'super().__init__({args})'
        if isinstance(node, ast.FileRead):
            return f'open({self._expr(node.filepath)}).read()'
        if isinstance(node, ast.ModuleAccess):
            if node.arguments is not None:
                args = ', '.join(self._expr(a) for a in node.arguments)
                return f'{node.module_name}.{node.member_name}({args})'
            return f'{node.module_name}.{node.member_name}'
        if hasattr(ast, 'SpreadExpression') and isinstance(node, ast.SpreadExpression):
            return f'*{self._expr(node.expression)}'
        if hasattr(ast, 'ChainedComparison') and isinstance(node, ast.ChainedComparison):
            parts = []
            for i, op in enumerate(node.operators):
                parts.append(self._expr(node.operands[i]))
                parts.append(self._map_op(op))
            parts.append(self._expr(node.operands[-1]))
            return ' '.join(parts)
        return f'None  # Unsupported: {type(node).__name__}'

    def _expr_literal(self, node) -> str:
        v = node.value
        if v is True:
            return 'True'
        if v is False:
            return 'False'
        if v is None:
            return 'None'
        if isinstance(v, str):
            return self._py_string(v)
        return repr(v)

    def _expr_binary(self, node) -> str:
        left = self._expr(node.left)
        right = self._expr(node.right)
        op = self._map_op(node.operator)
        # String concatenation: EPL uses + for strings too
        if op == '//':
            return f'({left} // {right})'
        if op == '**':
            return f'({left} ** {right})'
        return f'({left} {op} {right})'

    def _map_op(self, op: str) -> str:
        return {
            'and': 'and', 'or': 'or', 'not': 'not',
            '==': '==', '!=': '!=', '<': '<', '>': '>', '<=': '<=', '>=': '>=',
            '+': '+', '-': '-', '*': '*', '/': '/', '//': '//', '%': '%', '**': '**',
            '&': '&', '|': '|', '^': '^',
        }.get(op, op)

    def _expr_unary(self, node) -> str:
        op = 'not ' if node.operator == 'not' else node.operator
        return f'({op}{self._expr(node.operand)})'

    def _expr_call(self, node) -> str:
        args = ', '.join(self._expr(a) for a in node.arguments)
        # Map EPL builtins to Python equivalents
        name = node.name
        builtin_map = {
            'length': 'len', 'to_text': 'str', 'to_number': 'float',
            'to_integer': 'int', 'to_decimal': 'float', 'type_of': 'type',
            'round_number': 'round', 'absolute': 'abs', 'power': 'pow',
            'square_root': 'math.sqrt', 'minimum': 'min', 'maximum': 'max',
            'random_number': 'random.random', 'random_integer': 'random.randint',
            'sorted': 'sorted', 'reversed': 'list(reversed',
            'range': 'range', 'enumerate': 'enumerate', 'zip': 'zip',
            'map': 'list(map', 'filter': 'list(filter',
            'sum': 'sum', 'join': "', '.join",
            'upper': 'str.upper', 'lower': 'str.lower',
            'trim': 'str.strip', 'split': 'str.split',
            'replace': 'str.replace', 'contains': 'operator.contains',
            'starts_with': 'str.startswith', 'ends_with': 'str.endswith',
            'floor': 'math.floor', 'ceil': 'math.ceil',
            'log': 'math.log', 'sin': 'math.sin', 'cos': 'math.cos',
            'keys': 'dict.keys', 'values': 'dict.values',
        }
        if name in builtin_map:
            py_name = builtin_map[name]
            if name in ('square_root', 'floor', 'ceil', 'log', 'sin', 'cos'):
                self._add_import('math')
            if name in ('random_number', 'random_integer'):
                self._add_import('random')
            if py_name.endswith('('):
                # Wrapping functions like list(map(...))
                return f'{py_name}{args})'
            return f'{py_name}({args})'
        return f'{name}({args})'

    def _expr_method(self, node) -> str:
        obj = self._expr(node.obj)
        args = ', '.join(self._expr(a) for a in node.arguments)
        method = node.method_name
        # Map EPL method names to Python
        method_map = {
            'push': 'append', 'remove_at': 'pop',
            'upper': 'upper', 'lower': 'lower', 'trim': 'strip',
            'split': 'split', 'join': 'join', 'replace': 'replace',
            'starts_with': 'startswith', 'ends_with': 'endswith',
            'contains': '__contains__', 'index_of': 'index',
            'reverse': 'reverse', 'sort': 'sort',
            'keys': 'keys', 'values': 'values', 'items': 'items',
            'get': 'get', 'has_key': '__contains__',
        }
        py_method = method_map.get(method, method)
        if args:
            return f'{obj}.{py_method}({args})'
        return f'{obj}.{py_method}()'

    def _expr_slice(self, node) -> str:
        obj = self._expr(node.obj)
        start = self._expr(node.start) if node.start else ''
        end = self._expr(node.end) if node.end else ''
        step = ''
        if hasattr(node, 'step') and node.step:
            step = f':{self._expr(node.step)}'
        return f'{obj}[{start}:{end}{step}]'

    # ── Param / type helpers ───────────────────────────

    def _format_param(self, p) -> str:
        name = p[0]
        ptype = p[1] if len(p) > 1 else None
        default = p[2] if len(p) > 2 else None
        result = name
        if ptype:
            result += f': {self._py_type(ptype)}'
        if default is not None:
            result += f' = {self._expr(default)}'
        return result

    def _py_type(self, epl_type) -> str:
        if not epl_type:
            return ''
        type_map = {
            'integer': 'int', 'decimal': 'float', 'text': 'str',
            'boolean': 'bool', 'list': 'list', 'map': 'dict',
            'any': 'Any', 'void': 'None',
            'number': 'float', 'string': 'str',
        }
        return type_map.get(epl_type.lower(), epl_type)
