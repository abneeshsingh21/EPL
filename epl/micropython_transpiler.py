"""
EPL MicroPython Transpiler (Phase 5.3)
======================================
Transpiles EPL AST → MicroPython code for embedded/IoT targets.
Supports ESP32 and Raspberry Pi Pico (RPi Pico).

Usage:
    python main.py micropython <file.epl> [--target esp32|pico]

Output: Standalone MicroPython .py file that runs on the target board.
Upload with: mpremote cp <output>.py :main.py
"""

from epl import ast_nodes as ast


# ─── Platform-specific headers ────────────────────────────

_HEADERS = {
    'esp32': '''\
# EPL → MicroPython (ESP32)
# Upload: mpremote cp {filename} :main.py
import machine
import time
import gc
''',
    'pico': '''\
# EPL → MicroPython (Raspberry Pi Pico)
# Upload: mpremote cp {filename} :main.py
import machine
import time
import gc
''',
}

_GPIO_HELPERS = '''\
# ─── EPL GPIO helpers ────────────────────────────────
def pin_setup(num, mode="out"):
    m = machine.Pin.OUT if mode == "out" else machine.Pin.IN
    return machine.Pin(num, m)

def pin_on(p):
    p.value(1)

def pin_off(p):
    p.value(0)

def pin_read(p):
    return p.value()

def analog_read(pin_num):
    adc = machine.ADC(machine.Pin(pin_num))
    return adc.read_u16()

def pwm_write(pin_num, duty, freq=1000):
    p = machine.PWM(machine.Pin(pin_num), freq=freq)
    p.duty_u16(duty)
    return p

def wait(ms):
    time.sleep_ms(int(ms))

'''


class MicroPythonTranspiler:
    """Transpiles an EPL AST to MicroPython source code."""

    def __init__(self, target='esp32'):
        self.target = target
        self.indent = 0
        self.output = []
        self.functions_defined = set()
        self.uses_gpio = False
        self.uses_wifi = False
        self.uses_i2c = False

    def transpile(self, program):
        """Transpile a full EPL program to MicroPython."""
        filename = 'main.py'
        header = _HEADERS.get(self.target, _HEADERS['esp32']).format(filename=filename)

        # First pass: scan for hardware usage
        self._scan_hardware(program.statements)

        # Build output
        self.output.append(header)

        if self.uses_gpio:
            self.output.append(_GPIO_HELPERS)

        if self.uses_wifi:
            self.output.append(self._wifi_helper())

        if self.uses_i2c:
            self.output.append(self._i2c_helper())

        # Compile statements
        for stmt in program.statements:
            self._compile_stmt(stmt)

        # Add gc collection at end for memory management (in try-finally)
        self.output.append('\ntry:')
        self.output.append('    gc.collect()')
        self.output.append('except Exception:')
        self.output.append('    gc.collect()')

        return '\n'.join(self.output)

    def _scan_hardware(self, stmts):
        """Scan for hardware-related function calls using AST inspection."""
        gpio_names = {'pin_setup', 'pin_on', 'pin_off', 'analog_read', 'pwm_write', 'pin_read'}
        wifi_names = {'wifi_connect'}
        i2c_names = {'i2c_setup', 'i2c_scan', 'i2c_write', 'i2c_read'}
        self._scan_nodes(stmts, gpio_names, wifi_names, i2c_names)

    def _scan_nodes(self, nodes, gpio_names, wifi_names, i2c_names):
        """Recursively scan AST nodes for hardware function calls."""
        for node in nodes:
            if isinstance(node, ast.FunctionCall):
                name = node.name if isinstance(node.name, str) else getattr(node.name, 'name', '')
                if name in gpio_names:
                    self.uses_gpio = True
                elif name in wifi_names:
                    self.uses_wifi = True
                elif name in i2c_names:
                    self.uses_i2c = True
            # Recurse into child bodies
            for attr in ('then_body', 'else_body', 'body', 'try_body', 'catch_body'):
                child = getattr(node, attr, None)
                if isinstance(child, list):
                    self._scan_nodes(child, gpio_names, wifi_names, i2c_names)

    def _wifi_helper(self):
        if self.target == 'pico':
            return '''\
import network
def wifi_connect(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        time.sleep_ms(100)
    return wlan.ifconfig()[0]

'''
        return '''\
import network
def wifi_connect(ssid, password):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.connect(ssid, password)
    while not sta.isconnected():
        time.sleep_ms(100)
    return sta.ifconfig()[0]

'''

    def _i2c_helper(self):
        if self.target == 'pico':
            return '''\
def i2c_setup(sda=0, scl=1, freq=400000):
    return machine.I2C(0, sda=machine.Pin(sda), scl=machine.Pin(scl), freq=freq)

def i2c_scan(bus):
    return bus.scan()

def i2c_write(bus, addr, data):
    bus.writeto(addr, bytes(data) if isinstance(data, list) else data)

def i2c_read(bus, addr, n):
    return list(bus.readfrom(addr, n))

'''
        return '''\
def i2c_setup(sda=21, scl=22, freq=400000):
    return machine.I2C(0, sda=machine.Pin(sda), scl=machine.Pin(scl), freq=freq)

def i2c_scan(bus):
    return bus.scan()

def i2c_write(bus, addr, data):
    bus.writeto(addr, bytes(data) if isinstance(data, list) else data)

def i2c_read(bus, addr, n):
    return list(bus.readfrom(addr, n))

'''

    def _line(self, code):
        self.output.append('    ' * self.indent + code)

    def _compile_stmt(self, node):
        if isinstance(node, ast.PrintStatement):
            self._line(f'print({self._expr(node.expression)})')

        elif isinstance(node, ast.VarDeclaration):
            self._line(f'{self._safe_name(node.name)} = {self._expr(node.value)}')

        elif isinstance(node, ast.VarAssignment):
            self._line(f'{self._safe_name(node.name)} = {self._expr(node.value)}')

        elif isinstance(node, ast.ConstDeclaration):
            self._line(f'{self._safe_name(node.name)} = {self._expr(node.value)}')

        elif isinstance(node, ast.AugmentedAssignment):
            op_map = {'Plus': '+=', 'Minus': '-=', 'Multiply': '*=', 'Divide': '/=', 'Modulo': '%='}
            op = op_map.get(str(node.operator), '+=')
            self._line(f'{self._safe_name(node.name)} {op} {self._expr(node.value)}')

        elif isinstance(node, ast.IfStatement):
            self._line(f'if {self._expr(node.condition)}:')
            self.indent += 1
            for s in node.then_body:
                self._compile_stmt(s)
            if not node.then_body:
                self._line('pass')
            self.indent -= 1
            if node.else_body:
                self._line('else:')
                self.indent += 1
                for s in node.else_body:
                    self._compile_stmt(s)
                if not node.else_body:
                    self._line('pass')
                self.indent -= 1

        elif isinstance(node, ast.WhileLoop):
            self._line(f'while {self._expr(node.condition)}:')
            self.indent += 1
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1

        elif isinstance(node, ast.RepeatLoop):
            self._line(f'for __i in range({self._expr(node.count)}):')
            self.indent += 1
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1

        elif isinstance(node, ast.ForEachLoop):
            self._line(f'for {self._safe_name(node.var_name)} in {self._expr(node.iterable)}:')
            self.indent += 1
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1

        elif isinstance(node, ast.ForRange):
            var = self._safe_name(node.var_name)
            start = self._expr(node.start)
            end = self._expr(node.end)
            step = self._expr(node.step) if node.step else '1'
            self._line(f'for {var} in range({start}, {end} + 1, {step}):')
            self.indent += 1
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1

        elif isinstance(node, ast.FunctionDef):
            params = ', '.join(self._safe_name(p[0] if isinstance(p, tuple) else p) for p in node.params)
            self._line(f'def {self._safe_name(node.name)}({params}):')
            self.indent += 1
            self.functions_defined.add(node.name)
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1
            self._line('')

        elif isinstance(node, ast.FunctionCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            self._line(f'{self._func_name(node.name)}({args})')

        elif isinstance(node, ast.ReturnStatement):
            if node.value:
                self._line(f'return {self._expr(node.value)}')
            else:
                self._line('return')

        elif isinstance(node, ast.BreakStatement):
            self._line('break')

        elif isinstance(node, ast.ContinueStatement):
            self._line('continue')

        elif isinstance(node, ast.ClassDef):
            parent = getattr(node, 'parent', None)
            ext = f'({parent})' if parent else ''
            self._line(f'class {node.name}{ext}:')
            self.indent += 1
            has_content = False
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    params = ['self'] + [p[0] if isinstance(p, tuple) else p for p in item.params]
                    self._line(f'def {item.name}({", ".join(params)}):')
                    self.indent += 1
                    for s in item.body:
                        self._compile_stmt(s)
                    if not item.body:
                        self._line('pass')
                    self.indent -= 1
                    has_content = True
                elif isinstance(item, ast.VarDeclaration):
                    self._line(f'{item.name} = {self._expr(item.value)}')
                    has_content = True
            if not has_content:
                self._line('pass')
            self.indent -= 1
            self._line('')

        elif isinstance(node, ast.TryCatch):
            self._line('try:')
            self.indent += 1
            for s in node.try_body:
                self._compile_stmt(s)
            if not node.try_body:
                self._line('pass')
            self.indent -= 1
            var = getattr(node, 'catch_var', None) or getattr(node, 'error_var', 'e')
            self._line(f'except Exception as {var}:')
            self.indent += 1
            catch_body = getattr(node, 'catch_body', [])
            for s in catch_body:
                self._compile_stmt(s)
            if not catch_body:
                self._line('pass')
            self.indent -= 1

        elif isinstance(node, ast.ThrowStatement):
            self._line(f'raise Exception({self._expr(node.expression)})')

        elif isinstance(node, ast.WaitStatement):
            if node.duration:
                self._line(f'time.sleep_ms(int({self._expr(node.duration)} * 1000))')

        elif isinstance(node, ast.PropertySet):
            self._line(f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)}')

        elif isinstance(node, ast.IndexSet):
            self._line(f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)}')

        elif isinstance(node, ast.MethodCall):
            obj = self._expr(node.obj)
            args = ', '.join(self._expr(a) for a in node.arguments)
            self._line(f'{obj}.{node.method_name}({args})')

        elif isinstance(node, ast.ImportStatement):
            self._line(f'# import: {node.filepath}')

        elif isinstance(node, ast.ExitStatement):
            self._line('raise SystemExit')

        elif isinstance(node, ast.AssertStatement):
            self._line(f'assert {self._expr(node.expression)}')

        # ─── v7.4 Missing handlers ────────────────────────
        elif isinstance(node, ast.MatchStatement):
            expr = self._expr(node.expression)
            first = True
            for clause in node.when_clauses:
                vals = ' or '.join(f'{expr} == {self._expr(v)}' for v in clause.values)
                kw = 'if' if first else 'elif'
                self._line(f'{kw} {vals}:')
                self.indent += 1
                for s in clause.body:
                    self._compile_stmt(s)
                if not clause.body:
                    self._line('pass')
                self.indent -= 1
                first = False
            if node.default_body:
                self._line('else:')
                self.indent += 1
                for s in node.default_body:
                    self._compile_stmt(s)
                self.indent -= 1

        elif isinstance(node, ast.EnumDef):
            self._line(f'class {node.name}:')
            self.indent += 1
            for i, member in enumerate(node.members):
                self._line(f'{member} = {i}')
            if not node.members:
                self._line('pass')
            self.indent -= 1
            self._line('')

        elif isinstance(node, ast.TryCatchFinally):
            self._line('try:')
            self.indent += 1
            for s in node.try_body:
                self._compile_stmt(s)
            if not node.try_body:
                self._line('pass')
            self.indent -= 1
            for err_type, err_var, body in node.catch_clauses:
                exc = err_type if err_type else 'Exception'
                var = err_var if err_var else 'e'
                self._line(f'except {exc} as {var}:')
                self.indent += 1
                for s in body:
                    self._compile_stmt(s)
                if not body:
                    self._line('pass')
                self.indent -= 1
            if node.finally_body:
                self._line('finally:')
                self.indent += 1
                for s in node.finally_body:
                    self._compile_stmt(s)
                self.indent -= 1

        elif isinstance(node, ast.FileWrite):
            self._line(f'with open({self._expr(node.filepath)}, "w") as _f:')
            self.indent += 1
            self._line(f'_f.write(str({self._expr(node.content)}))')
            self.indent -= 1

        elif isinstance(node, ast.FileAppend):
            self._line(f'with open({self._expr(node.filepath)}, "a") as _f:')
            self.indent += 1
            self._line(f'_f.write(str({self._expr(node.content)}) + "\\n")')
            self.indent -= 1

        elif isinstance(node, ast.AsyncFunctionDef):
            # MicroPython has limited async — emit as uasyncio coroutine
            params = ', '.join(self._safe_name(p[0] if isinstance(p, tuple) else p) for p in node.params)
            self._line(f'async def {self._safe_name(node.name)}({params}):')
            self.indent += 1
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1
            self._line('')

        elif isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                self._line(f'super().{node.method_name}({args})')
            else:
                self._line(f'super().__init__({args})')

        elif isinstance(node, ast.DestructureAssignment):
            names = ', '.join(self._safe_name(n) for n in node.names)
            self._line(f'{names} = {self._expr(node.value)}')

        elif isinstance(node, ast.YieldStatement):
            val = f' {self._expr(node.value)}' if node.value else ''
            self._line(f'yield{val}')

        elif isinstance(node, ast.ModuleDef):
            self._line(f'# Module: {node.name}')
            for s in node.body:
                self._compile_stmt(s)

        elif isinstance(node, ast.VisibilityModifier):
            self._compile_stmt(node.statement)

        elif isinstance(node, ast.StaticMethodDef):
            params = ', '.join(self._safe_name(p[0] if isinstance(p, tuple) else p) for p in node.params)
            self._line('@staticmethod')
            self._line(f'def {self._safe_name(node.name)}({params}):')
            self.indent += 1
            for s in node.body:
                self._compile_stmt(s)
            if not node.body:
                self._line('pass')
            self.indent -= 1
            self._line('')

        elif isinstance(node, ast.ExportStatement):
            self._line(f'# export: {node.name}')

        else:
            # Try to compile as expression
            try:
                self._line(self._expr(node))
            except Exception:
                self._line(f'# unsupported: {type(node).__name__}')

    def _expr(self, node):
        if node is None:
            return 'None'

        if isinstance(node, ast.Literal):
            v = node.value
            if v is None:
                return 'None'
            if isinstance(v, bool):
                return 'True' if v else 'False'
            if isinstance(v, str):
                return repr(v)
            return str(v)

        if isinstance(node, ast.Identifier):
            return self._safe_name(node.name)

        if isinstance(node, ast.BinaryOp):
            l = self._expr(node.left)
            r = self._expr(node.right)
            op_map = {
                'Plus': '+', 'Minus': '-', 'Multiply': '*', 'Divide': '/',
                'Modulo': '%', 'Power': '**', 'FloorDivide': '//',
                'Equals': '==', 'NotEquals': '!=', 'Is': '==', 'IsNot': '!=',
                'LessThan': '<', 'GreaterThan': '>',
                'LessThanOrEqual': '<=', 'GreaterThanOrEqual': '>=',
                'And': 'and', 'Or': 'or',
            }
            op = op_map.get(str(node.operator), '+')
            return f'({l} {op} {r})'

        if isinstance(node, ast.UnaryOp):
            operand = self._expr(node.operand)
            if str(node.operator) in ('Not', 'NOT', 'not', '!'):
                return f'(not {operand})'
            return f'(-{operand})'

        if isinstance(node, ast.FunctionCall):
            name = node.name if isinstance(node.name, str) else node.name.name
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{self._func_name(name)}({args})'

        if isinstance(node, ast.MethodCall):
            obj = self._expr(node.obj)
            args = ', '.join(self._expr(a) for a in node.arguments)
            m = node.method_name
            return f'{obj}.{m}({args})'

        if isinstance(node, ast.PropertyAccess):
            return f'{self._expr(node.obj)}.{node.property_name}'

        if isinstance(node, ast.IndexAccess):
            return f'{self._expr(node.obj)}[{self._expr(node.index)}]'

        if isinstance(node, ast.ListLiteral):
            elems = ', '.join(self._expr(e) for e in node.elements)
            return f'[{elems}]'

        if isinstance(node, ast.DictLiteral):
            pairs = ', '.join(f'{self._expr(k)}: {self._expr(v)}' for k, v in node.pairs)
            return '{' + pairs + '}'

        if isinstance(node, ast.TernaryExpression):
            return f'({self._expr(node.true_expr)} if {self._expr(node.condition)} else {self._expr(node.false_expr)})'

        if isinstance(node, ast.LambdaExpression):
            params = ', '.join(p if isinstance(p, str) else p[0] for p in node.params)
            return f'lambda {params}: {self._expr(node.body)}'

        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{node.class_name}({args})'

        if isinstance(node, ast.SliceAccess):
            obj = self._expr(node.obj)
            s = self._expr(node.start) if node.start else ''
            e = self._expr(node.end) if node.end else ''
            return f'{obj}[{s}:{e}]'

        if isinstance(node, ast.FileRead):
            return f'open({self._expr(node.filepath)}).read()'

        if isinstance(node, ast.AwaitExpression):
            return f'await {self._expr(node.expression)}'

        if isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                return f'super().{node.method_name}({args})'
            return f'super().__init__({args})'

        if isinstance(node, ast.ModuleAccess):
            if node.arguments is not None:
                args = ', '.join(self._expr(a) for a in node.arguments)
                return f'{node.module_name}.{node.member_name}({args})'
            return f'{node.module_name}.{node.member_name}'

        if hasattr(ast, 'SpreadExpression') and isinstance(node, ast.SpreadExpression):
            return f'*{self._expr(node.expression)}'

        return repr(node)

    def _func_name(self, name):
        """Map EPL builtin function names to MicroPython equivalents."""
        mapping = {
            'length': 'len', 'append': 'list.append', 'to_text': 'str',
            'to_integer': 'int', 'to_decimal': 'float', 'to_boolean': 'bool',
            'uppercase': 'str.upper', 'lowercase': 'str.lower',
            'type_of': 'type', 'absolute': 'abs', 'power': 'pow',
            'random': '__import__("random").random',
            'sqrt': '__import__("math").sqrt',
            'floor': '__import__("math").floor',
            'ceil': '__import__("math").ceil',
            'keys': 'list',  # keys(d) → list(d.keys())
            'values': 'list',
            'contains': 'lambda haystack, needle: needle in haystack',
            'join': 'lambda lst, sep: sep.join(str(x) for x in lst)',
            'split': 'lambda s, d: s.split(d)',
            'replace': 'lambda s, old, new: s.replace(old, new)',
            'sorted': 'sorted', 'reversed': 'list(reversed',
            'range': 'range', 'sum': 'sum', 'min': 'min', 'max': 'max',
            'round': 'round', 'print': 'print',
            'pin_setup': 'pin_setup', 'pin_on': 'pin_on', 'pin_off': 'pin_off',
            'pin_read': 'pin_read', 'analog_read': 'analog_read',
            'pwm_write': 'pwm_write', 'wait': 'wait',
            'wifi_connect': 'wifi_connect',
            'i2c_setup': 'i2c_setup', 'i2c_scan': 'i2c_scan',
            'i2c_write': 'i2c_write', 'i2c_read': 'i2c_read',
            'time_now': 'time.ticks_ms',
        }
        return mapping.get(name, self._safe_name(name))

    def _safe_name(self, name):
        """Ensure name is valid Python identifier."""
        if isinstance(name, str):
            name = name.replace(' ', '_').replace('-', '_')
            if name in ('class', 'def', 'return', 'import', 'from', 'as',
                        'if', 'else', 'elif', 'while', 'for', 'in',
                        'try', 'except', 'finally', 'raise', 'with',
                        'pass', 'break', 'continue', 'and', 'or', 'not',
                        'True', 'False', 'None', 'is', 'lambda', 'del',
                        'global', 'nonlocal', 'assert', 'yield', 'async', 'await'):
                return name + '_'
        return name


def transpile_to_micropython(program, target='esp32'):
    """Transpile an EPL AST to MicroPython source code."""
    transpiler = MicroPythonTranspiler(target=target)
    return transpiler.transpile(program)
