"""
EPL Kotlin Code Generator (v3.0)
Transpiles EPL AST to Kotlin source code targeting Android/JVM.
Supports: variables, functions, classes, loops, conditions, string/list methods,
collections, lambdas, enums, Android Activity generation, GUI widget generation,
event binding, dynamic layouts, navigation, Jetpack Compose, symbol table with
type tracking, visibility modifiers, companion objects, and coroutines.
"""

import os
import shutil
from pathlib import Path
from epl import ast_nodes as ast


ANDROID_GRADLE_WRAPPER_VERSION = "8.2.1"
ANDROID_GRADLE_PLUGIN_VERSION = "8.2.0"
ANDROID_KOTLIN_VERSION = "1.9.22"
ANDROID_TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "android"


class SymbolTable:
    """Scoped symbol table for tracking variable/function/class types."""

    def __init__(self, parent=None):
        self.parent = parent
        self.symbols = {}      # name -> kotlin type string
        self.functions = {}    # name -> {'params': [...], 'return': str}
        self.classes = {}      # name -> {'properties': {name: type}, 'methods': {name: sig}, 'parent': str|None}

    def define(self, name, kt_type):
        self.symbols[name] = kt_type

    def lookup(self, name):
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def define_function(self, name, params, return_type):
        self.functions[name] = {'params': params, 'return': return_type}

    def lookup_function(self, name):
        if name in self.functions:
            return self.functions[name]
        if self.parent:
            return self.parent.lookup_function(name)
        return None

    def define_class(self, name, info):
        self.classes[name] = info

    def lookup_class(self, name):
        if name in self.classes:
            return self.classes[name]
        if self.parent:
            return self.parent.lookup_class(name)
        return None

    def child(self):
        return SymbolTable(parent=self)


class KotlinGenerator:
    """Transpiles EPL AST to Kotlin source code with type-aware symbol table."""

    def __init__(self, package_name="com.epl.app"):
        self.package = package_name
        self.indent = 0
        self.output = []
        self.in_class = None
        self.class_properties = {}  # name -> kotlin type (upgraded from set)
        self.imports = set()
        self.widgets = []       # collected GUI widgets for layout XML generation
        self.event_bindings = []  # collected event bindings
        self.widget_counter = 0
        self.symbols = SymbolTable()  # root symbol table

    # ─── Public API ──────────────────────────────────────

    def generate(self, program: ast.Program) -> str:
        """Generate Kotlin source from EPL AST."""
        self.output = []
        self.imports = set()
        self.symbols = SymbolTable()
        stmts = program.statements

        # Pre-pass: register all top-level symbols
        self._register_symbols(stmts)

        # Separate top-level constructs
        classes = [s for s in stmts if isinstance(s, ast.ClassDef)]
        functions = [s for s in stmts if isinstance(s, ast.FunctionDef)]
        enums = [s for s in stmts if isinstance(s, ast.EnumDef)]
        other = [s for s in stmts if not isinstance(s, (ast.ClassDef, ast.FunctionDef, ast.EnumDef))]

        for e in enums: self._emit_enum(e)
        for c in classes: self._emit_class(c)
        for f in functions: self._emit_function(f)

        if other:
            self._line('fun main() {')
            self.indent += 1
            for s in other: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')

        header = f'package {self.package}\n\n'
        if self.imports:
            header += '\n'.join(f'import {i}' for i in sorted(self.imports)) + '\n\n'
        return header + '\n'.join(self.output)

    def _register_symbols(self, stmts):
        """Pre-pass: register functions, classes, enums for type lookups."""
        for s in stmts:
            if isinstance(s, ast.FunctionDef):
                ret = self._infer_return_type(s)
                param_types = [(p[0], self._infer_param_type(p)) for p in s.params]
                self.symbols.define_function(s.name, param_types, ret)
            elif isinstance(s, ast.ClassDef):
                props = {}
                methods = {}
                for item in s.body:
                    if isinstance(item, ast.VarDeclaration):
                        props[item.name] = self._infer_kotlin_type(item.value)
                    elif isinstance(item, ast.FunctionDef) and item.name != 'init':
                        methods[item.name] = self._infer_return_type(item)
                self.symbols.define_class(s.name, {
                    'properties': props, 'methods': methods,
                    'parent': s.parent
                })
            elif isinstance(s, ast.EnumDef):
                self.symbols.define(s.name, s.name)
            elif isinstance(s, ast.VarDeclaration):
                self.symbols.define(s.name, self._infer_kotlin_type(s.value))
            elif isinstance(s, ast.ConstDeclaration):
                self.symbols.define(s.name, self._infer_kotlin_type(s.value))

    def generate_android_activity(self, program: ast.Program, activity_name="MainActivity") -> str:
        """Generate an Android Activity from EPL AST with dynamic UI."""
        self.output = []
        self.widgets = []
        self.event_bindings = []
        self.imports = {'android.os.Bundle', 'androidx.appcompat.app.AppCompatActivity',
                        'android.widget.*', 'android.view.View', 'android.widget.Toast',
                        'android.view.ViewGroup', 'android.widget.LinearLayout',
                        'android.widget.ScrollView'}

        # First pass: collect GUI nodes for layout XML
        self._collect_gui_nodes(program.statements)

        self._line(f'class {activity_name} : AppCompatActivity() {{')
        self.indent += 1
        
        # Declare widget member variables
        for w in self.widgets:
            widget_class = self._android_widget_class(w['type'])
            self._line(f'private lateinit var {w["id"]}: {widget_class}')
        self._line('')

        self._line('override fun onCreate(savedInstanceState: Bundle?) {')
        self.indent += 1
        self._line('super.onCreate(savedInstanceState)')
        
        if self.widgets:
            # Use programmatic layout for dynamic widgets
            self._line('val scrollView = ScrollView(this)')
            self._line('val mainLayout = LinearLayout(this).apply {')
            self.indent += 1
            self._line('orientation = LinearLayout.VERTICAL')
            self._line('setPadding(32, 32, 32, 32)')
            self.indent -= 1
            self._line('}')
            self._line('')
            self._emit_android_widgets()
            self._line('')
            self._emit_event_bindings()
            self._line('')
            self._line('scrollView.addView(mainLayout)')
            self._line('setContentView(scrollView)')
        else:
            self._line('setContentView(R.layout.activity_main)')
            self._line('')

        # Emit non-GUI statements
        for s in program.statements:
            if not self._is_gui_node(s):
                self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

        # Generate helper methods for event handlers
        self._emit_handler_methods(program.statements)

        self.indent -= 1
        self._line('}')

        header = f'package {self.package}\n\n'
        header += '\n'.join(f'import {i}' for i in sorted(self.imports)) + '\n\n'
        return header + '\n'.join(self.output)

    def generate_compose_activity(self, program: ast.Program, activity_name="MainActivity") -> str:
        """Generate a Jetpack Compose Activity from EPL AST."""
        self.output = []
        self.widgets = []
        self.event_bindings = []
        self.imports = {
            'android.os.Bundle',
            'androidx.activity.ComponentActivity',
            'androidx.activity.compose.setContent',
            'androidx.compose.foundation.layout.*',
            'androidx.compose.material3.*',
            'androidx.compose.runtime.*',
            'androidx.compose.ui.Modifier',
            'androidx.compose.ui.unit.dp',
            'androidx.compose.ui.Alignment',
        }

        self._collect_gui_nodes(program.statements)

        self._line(f'class {activity_name} : ComponentActivity() {{')
        self.indent += 1
        self._line('override fun onCreate(savedInstanceState: Bundle?) {')
        self.indent += 1
        self._line('super.onCreate(savedInstanceState)')
        self._line('setContent {')
        self.indent += 1
        self._line('MaterialTheme {')
        self.indent += 1
        self._line('Surface(')
        self.indent += 1
        self._line('modifier = Modifier.fillMaxSize(),')
        self._line('color = MaterialTheme.colorScheme.background')
        self.indent -= 1
        self._line(') {')
        self.indent += 1
        self._line('AppContent()')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')
        self._line('')

        # Generate composable functions
        self._line('@Composable')
        self._line('fun AppContent() {')
        self.indent += 1

        if self.widgets:
            self._line('Column(')
            self.indent += 1
            self._line('modifier = Modifier')
            self.indent += 1
            self._line('.fillMaxSize()')
            self._line('.padding(16.dp),')
            self.indent -= 1
            self._line('verticalArrangement = Arrangement.spacedBy(8.dp)')
            self.indent -= 1
            self._line(') {')
            self.indent += 1
            for w in self.widgets:
                self._emit_compose_widget(w)
            self.indent -= 1
            self._line('}')
        else:
            # No widgets — emit non-GUI content
            self._line('Column(')
            self.indent += 1
            self._line('modifier = Modifier.fillMaxSize().padding(16.dp),')
            self._line('verticalArrangement = Arrangement.Center,')
            self._line('horizontalAlignment = Alignment.CenterHorizontally')
            self.indent -= 1
            self._line(') {')
            self.indent += 1
            for s in program.statements:
                if isinstance(s, ast.PrintStatement):
                    self._line(f'Text(text = {self._expr(s.expression)})')
                elif not self._is_gui_node(s):
                    self._emit_stmt(s)
            self.indent -= 1
            self._line('}')

        self.indent -= 1
        self._line('}')

        # Emit helper functions from the program
        for s in program.statements:
            if isinstance(s, ast.FunctionDef):
                self._line('')
                self._emit_function(s)

        header = f'package {self.package}\n\n'
        header += '\n'.join(f'import {i}' for i in sorted(self.imports)) + '\n\n'
        return header + '\n'.join(self.output)

    def _emit_compose_widget(self, w):
        """Emit a Compose widget from collected widget info."""
        wtype = w['type']
        text = w.get('text')
        props = w.get('properties', {})

        if wtype == 'button':
            handler = w.get('action')
            handler_str = f'{{ {self._expr(handler).strip(chr(34))}() }}' if handler else '{}'
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or "Button"}"'
            self._line(f'Button(onClick = {handler_str}) {{')
            self.indent += 1
            self._line(f'Text({text_str})')
            self.indent -= 1
            self._line('}')
        elif wtype == 'label':
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or ""}"'
            fs = props.get('fontSize')
            if fs:
                self.imports.add('androidx.compose.ui.unit.sp')
                self._line(f'Text(text = {text_str}, fontSize = {fs}.sp)')
            else:
                self._line(f'Text(text = {text_str})')
        elif wtype in ('input', 'textarea'):
            var_name = w.get('id', 'textField')
            placeholder = props.get('placeholder', '')
            self._line(f'var {var_name}Value by remember {{ mutableStateOf("") }}')
            if wtype == 'textarea':
                self._line(f'OutlinedTextField(')
            else:
                self._line(f'TextField(')
            self.indent += 1
            self._line(f'value = {var_name}Value,')
            self._line(f'onValueChange = {{ {var_name}Value = it }},')
            if placeholder:
                self._line(f'label = {{ Text("{placeholder}") }},')
            self._line('modifier = Modifier.fillMaxWidth()')
            self.indent -= 1
            self._line(')')
        elif wtype == 'checkbox':
            var_name = w.get('id', 'checkbox')
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or "Check"}"'
            self._line(f'var {var_name}Checked by remember {{ mutableStateOf(false) }}')
            self._line('Row(verticalAlignment = Alignment.CenterVertically) {')
            self.indent += 1
            self._line(f'Checkbox(checked = {var_name}Checked, onCheckedChange = {{ {var_name}Checked = it }})')
            self._line(f'Text({text_str})')
            self.indent -= 1
            self._line('}')
        elif wtype == 'slider':
            var_name = w.get('id', 'slider')
            max_val = props.get('max', 100)
            self._line(f'var {var_name}Value by remember {{ mutableStateOf(0f) }}')
            self._line(f'Slider(value = {var_name}Value, onValueChange = {{ {var_name}Value = it }}, valueRange = 0f..{max_val}f)')
        elif wtype == 'progress':
            self._line('LinearProgressIndicator(modifier = Modifier.fillMaxWidth())')
        elif wtype == 'image':
            self.imports.add('androidx.compose.foundation.Image')
            self.imports.add('androidx.compose.ui.res.painterResource')
            self._line('// Image placeholder — replace R.drawable.placeholder with actual resource')
            self._line('// Image(painter = painterResource(R.drawable.placeholder), contentDescription = null)')
        else:
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or wtype}"'
            self._line(f'Text(text = {text_str})')

    def _is_gui_node(self, node):
        """Check if a node is a GUI-related AST node."""
        return isinstance(node, (ast.WindowCreate, ast.WidgetAdd, ast.LayoutBlock,
                                 ast.BindEvent, ast.DialogShow, ast.MenuDef, ast.CanvasDraw))

    def _collect_gui_nodes(self, stmts):
        """First pass: collect all widgets and event bindings."""
        for s in stmts:
            if isinstance(s, ast.WindowCreate):
                self._collect_gui_nodes(s.body)
            elif isinstance(s, ast.WidgetAdd):
                wid = s.name or f'widget_{self.widget_counter}'
                self.widget_counter += 1
                self.widgets.append({
                    'id': wid,
                    'type': s.widget_type.lower(),
                    'text': s.text,
                    'properties': s.properties,
                    'action': s.action,
                })
            elif isinstance(s, ast.LayoutBlock):
                self._collect_gui_nodes(s.children)
            elif isinstance(s, ast.BindEvent):
                self.event_bindings.append({
                    'widget': s.widget_name,
                    'event': s.event_type,
                    'handler': s.handler,
                })

    def _android_widget_class(self, wtype):
        """Map EPL widget type to Android widget class."""
        mapping = {
            'button': 'Button', 'label': 'TextView', 'input': 'EditText',
            'textarea': 'EditText', 'checkbox': 'CheckBox', 'dropdown': 'Spinner',
            'slider': 'SeekBar', 'progress': 'ProgressBar', 'image': 'ImageView',
            'listbox': 'ListView', 'canvas': 'View',
        }
        return mapping.get(wtype, 'TextView')

    def _emit_android_widgets(self):
        """Generate Kotlin code to programmatically create and add widgets."""
        for w in self.widgets:
            wclass = self._android_widget_class(w['type'])
            wid = w['id']
            self._line(f'{wid} = {wclass}(this).apply {{')
            self.indent += 1
            
            # Set layout params
            self._line('layoutParams = LinearLayout.LayoutParams(')
            self.indent += 1
            self._line('LinearLayout.LayoutParams.MATCH_PARENT,')
            self._line('LinearLayout.LayoutParams.WRAP_CONTENT')
            self.indent -= 1
            self._line(').apply { setMargins(0, 8, 0, 8) }')

            # Set text for text-based widgets
            if w['text'] and w['type'] in ('button', 'label', 'checkbox'):
                text_val = self._expr(w['text']) if hasattr(w['text'], 'line') else f'"{w["text"]}"'
                self._line(f'text = {text_val}')
            elif w['type'] == 'input':
                hint = w['properties'].get('placeholder', '')
                hint_val = self._expr(hint) if hasattr(hint, 'line') else f'"{hint}"'
                self._line(f'hint = {hint_val}')
                if w['type'] == 'textarea':
                    self._line('minLines = 4')
                    self._line('gravity = android.view.Gravity.TOP')
            elif w['type'] == 'textarea':
                self._line('minLines = 4')
                self._line('gravity = android.view.Gravity.TOP')

            # Widget-specific setup
            if w['type'] == 'slider':
                max_val = w['properties'].get('max', 100)
                self.imports.add('android.widget.SeekBar')
                self._line(f'max = {max_val}')
            elif w['type'] == 'progress':
                self.imports.add('android.widget.ProgressBar')
                self._line('isIndeterminate = false')
            elif w['type'] == 'image':
                self.imports.add('android.widget.ImageView')
                self._line('scaleType = ImageView.ScaleType.FIT_CENTER')
            elif w['type'] == 'dropdown':
                self.imports.add('android.widget.ArrayAdapter')
                self.imports.add('android.widget.Spinner')

            # Set additional properties
            for k, v in w['properties'].items():
                if k == 'width':
                    pass  # handled by layoutParams
                elif k == 'height':
                    pass
                elif k == 'color':
                    val = self._expr(v) if hasattr(v, 'line') else f'"{v}"'
                    self._line(f'// color = {val}')
                elif k == 'fontSize':
                    val = self._expr(v) if hasattr(v, 'line') else str(v)
                    self._line(f'textSize = {val}f')

            self.indent -= 1
            self._line('}')

            # Add click handler inline if action specified
            if w['action'] and w['type'] == 'button':
                action_name = self._expr(w['action']) if hasattr(w['action'], 'line') else str(w['action'])
                self._line(f'{wid}.setOnClickListener {{ {action_name.strip(chr(34))}() }}')

            self._line(f'mainLayout.addView({wid})')
            self._line('')

    def _emit_event_bindings(self):
        """Generate event binding code."""
        for binding in self.event_bindings:
            widget = binding['widget']
            event = binding['event']
            handler_expr = self._expr(binding['handler']) if hasattr(binding['handler'], 'line') else str(binding['handler'])
            handler_name = handler_expr.strip('"')
            
            if event in ('click', 'onClick'):
                self._line(f'{widget}.setOnClickListener {{ {handler_name}() }}')
            elif event in ('change', 'onTextChanged'):
                self.imports.add('android.text.TextWatcher')
                self.imports.add('android.text.Editable')
                self._line(f'{widget}.addTextChangedListener(object : TextWatcher {{')
                self.indent += 1
                self._line('override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}')
                self._line('override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {')
                self.indent += 1
                self._line(f'{handler_name}()')
                self.indent -= 1
                self._line('}')
                self._line('override fun afterTextChanged(s: Editable?) {}')
                self.indent -= 1
                self._line('})')
            elif event in ('longClick', 'onLongClick'):
                self._line(f'{widget}.setOnLongClickListener {{ {handler_name}(); true }}')

    def _emit_handler_methods(self, stmts):
        """Generate handler methods at class level from FunctionDef nodes."""
        for s in stmts:
            if isinstance(s, ast.FunctionDef):
                self._line('')
                self._emit_function(s)
            elif isinstance(s, ast.WindowCreate):
                self._emit_handler_methods(s.body)

    # ─── Helper ──────────────────────────────────────────

    def _line(self, text):
        self.output.append('    ' * self.indent + text)

    # ─── Statement Dispatch ──────────────────────────────

    def _emit_stmt(self, node):
        if node is None: return
        if isinstance(node, ast.VarDeclaration): self._emit_var_decl(node)
        elif isinstance(node, ast.VarAssignment): self._emit_var_assign(node)
        elif isinstance(node, ast.PrintStatement): self._emit_print(node)
        elif isinstance(node, ast.IfStatement): self._emit_if(node)
        elif isinstance(node, ast.WhileLoop): self._emit_while(node)
        elif isinstance(node, ast.RepeatLoop): self._emit_repeat(node)
        elif isinstance(node, ast.ForRange): self._emit_for_range(node)
        elif isinstance(node, ast.ForEachLoop): self._emit_for_each(node)
        elif isinstance(node, ast.FunctionDef): self._emit_function(node)
        elif isinstance(node, ast.FunctionCall): self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.ReturnStatement): self._emit_return(node)
        elif isinstance(node, ast.BreakStatement): self._line('break')
        elif isinstance(node, ast.ContinueStatement): self._line('continue')
        elif isinstance(node, ast.ClassDef): self._emit_class(node)
        elif isinstance(node, ast.MatchStatement): self._emit_match(node)
        elif isinstance(node, ast.TryCatch): self._emit_try_catch(node)
        elif isinstance(node, ast.MethodCall): self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.PropertySet): self._line(f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)}')
        elif isinstance(node, ast.IndexSet): self._line(f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)}')
        elif isinstance(node, ast.AugmentedAssignment): self._line(f'{node.name} {node.operator} {self._expr(node.value)}')
        elif isinstance(node, ast.ThrowStatement): self._line(f'throw Exception({self._expr(node.expression)})')
        elif isinstance(node, ast.ConstDeclaration):
            kt_type = self._infer_kotlin_type(node.value)
            self.symbols.define(node.name, kt_type)
            self._line(f'val {node.name}: {kt_type} = {self._expr(node.value)}')
        elif isinstance(node, ast.EnumDef): self._emit_enum(node)
        elif isinstance(node, ast.InputStatement): self._emit_input(node)
        elif isinstance(node, ast.ExitStatement):
            self.imports.add('kotlin.system.exitProcess')
            self._line('exitProcess(0)')
        elif isinstance(node, ast.AssertStatement): self._line(f'assert({self._expr(node.expression)})')
        # GUI nodes - emit as comments in non-Android context
        elif isinstance(node, ast.WindowCreate): self._emit_window_comment(node)
        elif isinstance(node, ast.WidgetAdd): pass  # handled by Android activity generator
        elif isinstance(node, ast.LayoutBlock): pass
        elif isinstance(node, ast.BindEvent): pass
        elif isinstance(node, ast.DialogShow): self._emit_dialog(node)
        elif isinstance(node, ast.CanvasDraw): pass
        elif isinstance(node, ast.AsyncFunctionDef): self._emit_async_function(node)
        elif isinstance(node, ast.SuperCall): self._emit_super_call(node)
        # v4 AST node support
        elif isinstance(node, ast.InterfaceDefNode): self._emit_interface(node)
        elif isinstance(node, ast.ModuleDef): self._emit_module(node)
        elif isinstance(node, ast.TryCatchFinally): self._emit_try_catch_finally(node)
        elif isinstance(node, ast.ExportStatement): self._emit_stmt(node.statement)
        elif isinstance(node, ast.VisibilityModifier): self._emit_visibility(node)
        elif isinstance(node, ast.StaticMethodDef): self._emit_static_method(node)
        elif isinstance(node, ast.AbstractMethodDef): self._emit_abstract_method(node)
        elif isinstance(node, ast.YieldStatement): self._emit_yield(node)
        elif isinstance(node, ast.DestructureAssignment): self._emit_destructure(node)
        elif isinstance(node, ast.ModuleAccess): self._line(f'{self._expr(node)}')

    # ─── v4 Statements ──────────────────────────────────

    def _emit_interface(self, node):
        self._line(f'interface {node.name} {{')
        self.indent += 1
        for sig in node.methods:
            if isinstance(sig, (list, tuple)):
                name = sig[0]
                params_list = sig[1] if len(sig) > 1 else []
                ret = sig[2] if len(sig) > 2 else None
            else:
                name = sig.get('name', 'unknown')
                params_list = sig.get('params', [])
                ret = sig.get('return_type', None)
            params = ', '.join(f'{p[0]}: {self._infer_param_type(p)}' for p in params_list)
            ret_type = self._infer_param_type(('', ret)) if ret else 'Any'
            self._line(f'fun {name}({params}): {ret_type}')
        self.indent -= 1
        self._line('}')

    def _emit_module(self, node):
        self._line(f'object {node.name} {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_try_catch_finally(self, node):
        self._line('try {')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        self.indent -= 1
        for clause in node.catch_clauses:
            var_name = clause.get('var', 'e')
            err_type = clause.get('type', 'Exception')
            self._line(f'}} catch ({var_name}: {err_type}) {{')
            self.indent += 1
            for s in clause.get('body', []):
                self._emit_stmt(s)
            self.indent -= 1
        if not node.catch_clauses:
            self._line('} catch (e: Exception) {')
            self.indent += 1
            self._line('// no catch body')
            self.indent -= 1
        if node.finally_body:
            self._line('} finally {')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    def _emit_visibility(self, node):
        vis = node.visibility.lower()  # public/private/protected
        kt_vis = {'public': 'public', 'private': 'private', 'protected': 'protected'}.get(vis, '')
        # Store visibility to prepend to next emitted line
        prev_len = len(self.output)
        self._emit_stmt(node.statement)
        # Prepend visibility to the first line emitted by inner statement
        if kt_vis and len(self.output) > prev_len:
            line = self.output[prev_len]
            stripped = line.lstrip()
            indent_str = line[:len(line) - len(stripped)]
            # Don't double up visibility keywords
            if not stripped.startswith(('private ', 'protected ', 'public ')):
                self.output[prev_len] = f'{indent_str}{kt_vis} {stripped}'

    def _emit_static_method(self, node):
        params = ', '.join(f'{p[0]}: {self._infer_param_type(p)}' for p in node.params)
        ret_type = self._infer_return_type(node)
        # Static methods are emitted inside companion object by _emit_class
        self._line(f'fun {node.name}({params}): {ret_type} {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not any(isinstance(s, ast.ReturnStatement) for s in node.body):
            self._line('return Unit')
        self.indent -= 1
        self._line('}')

    def _emit_abstract_method(self, node):
        params = ', '.join(f'{p[0]}: {self._infer_param_type(p)}' for p in node.params)
        ret_type = self._infer_return_type(node)
        self._line(f'abstract fun {node.name}({params}): {ret_type}')

    def _emit_yield(self, node):
        self.imports.add('kotlinx.coroutines.flow.*')
        if node.value:
            self._line(f'emit({self._expr(node.value)})')
        else:
            self._line('yield()')

    def _emit_destructure(self, node):
        names = ', '.join(node.targets)
        self._line(f'val ({names}) = {self._expr(node.value)}')

    # ─── Statements ──────────────────────────────────────

    def _emit_var_decl(self, node):
        kt_type = self._infer_kotlin_type(node.value)
        self.symbols.define(node.name, kt_type)
        self._line(f'var {node.name}: {kt_type} = {self._expr(node.value)}')

    def _emit_var_assign(self, node):
        prefix = 'this.' if (self.in_class and node.name in self.class_properties) else ''
        self._line(f'{prefix}{node.name} = {self._expr(node.value)}')

    def _emit_print(self, node):
        self._line(f'println({self._expr(node.expression)})')

    def _emit_input(self, node):
        if node.prompt:
            self._line(f'print({self._expr(node.prompt)})')
        self._line(f'var {node.variable_name} = readLine() ?: ""')

    def _emit_if(self, node):
        self._line(f'if ({self._expr(node.condition)}) {{')
        self.indent += 1
        for s in node.then_body: self._emit_stmt(s)
        self.indent -= 1
        if node.else_body:
            self._line('} else {')
            self.indent += 1
            for s in node.else_body: self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    def _emit_while(self, node):
        self._line(f'while ({self._expr(node.condition)}) {{')
        self.indent += 1
        for s in node.body: self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_repeat(self, node):
        self._line(f'repeat({self._expr(node.count)}) {{')
        self.indent += 1
        for s in node.body: self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_for_range(self, node):
        start = self._expr(node.start)
        end = self._expr(node.end)
        step = self._expr(node.step) if node.step else None
        if step:
            try:
                step_val = int(step)
                if step_val < 0:
                    abs_step = abs(step_val)
                    if abs_step == 1:
                        self._line(f'for ({node.var_name} in {start} downTo {end}) {{')
                    else:
                        self._line(f'for ({node.var_name} in {start} downTo {end} step {abs_step}) {{')
                elif step_val != 1:
                    self._line(f'for ({node.var_name} in {start}..{end} step {step}) {{')
                else:
                    self._line(f'for ({node.var_name} in {start}..{end}) {{')
            except (ValueError, TypeError):
                self._line(f'for ({node.var_name} in {start}..{end} step {step}) {{')
        else:
            self._line(f'for ({node.var_name} in {start}..{end}) {{')
        self.indent += 1
        for s in node.body: self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_for_each(self, node):
        self._line(f'for ({node.var_name} in {self._expr(node.iterable)}) {{')
        self.indent += 1
        for s in node.body: self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_function(self, node):
        # Filter out 'self' param (not needed in Kotlin)
        real_params = [p for p in node.params if p[0] != 'self']
        params = ', '.join(self._format_param(p) for p in real_params)
        ret_type = self._infer_return_type(node)
        # Register in symbol table
        param_types = [(p[0], self._infer_param_type(p)) for p in real_params]
        self.symbols.define_function(node.name, param_types, ret_type)
        self._line(f'fun {node.name}({params}): {ret_type} {{')
        self.indent += 1
        prev_symbols = self.symbols
        self.symbols = self.symbols.child()
        for p in real_params:
            self.symbols.define(p[0], self._infer_param_type(p))
        for s in node.body: self._emit_stmt(s)
        if ret_type == 'Unit' and not any(isinstance(s, ast.ReturnStatement) for s in node.body):
            pass  # Unit doesn't need explicit return
        elif not any(isinstance(s, ast.ReturnStatement) for s in node.body):
            self._line('return Unit')
        self.symbols = prev_symbols
        self.indent -= 1
        self._line('}')

    def _emit_class_method(self, node):
        """Emit a method inside a class, with this. prefixing for properties."""
        real_params = [p for p in node.params if p[0] != 'self']
        params = ', '.join(self._format_param(p) for p in real_params)
        ret_type = self._infer_return_type(node)
        modifier = 'open ' if self.in_class else ''
        self._line(f'{modifier}fun {node.name}({params}): {ret_type} {{')
        self.indent += 1
        prev_symbols = self.symbols
        self.symbols = self.symbols.child()
        for p in real_params:
            self.symbols.define(p[0], self._infer_param_type(p))
        for s in node.body: self._emit_stmt(s)
        if ret_type == 'Unit' and not any(isinstance(s, ast.ReturnStatement) for s in node.body):
            pass
        elif not any(isinstance(s, ast.ReturnStatement) for s in node.body):
            self._line('return Unit')
        self.symbols = prev_symbols
        self.indent -= 1
        self._line('}')

    def _infer_kotlin_type(self, node) -> str:
        """Infer Kotlin type from an AST value node using symbol table."""
        if node is None: return 'Any?'
        if isinstance(node, ast.Literal):
            if isinstance(node.value, bool): return 'Boolean'
            if isinstance(node.value, int): return 'Int'
            if isinstance(node.value, float): return 'Double'
            if isinstance(node.value, str): return 'String'
            if node.value is None: return 'Any?'
        if isinstance(node, ast.ListLiteral):
            if node.elements:
                elem_type = self._infer_kotlin_type(node.elements[0])
                if all(self._infer_kotlin_type(e) == elem_type for e in node.elements):
                    return f'MutableList<{elem_type}>'
            return 'MutableList<Any>'
        if isinstance(node, ast.DictLiteral):
            if node.pairs:
                key_type = self._infer_kotlin_type(ast.Literal(node.pairs[0][0], 0) if isinstance(node.pairs[0][0], (int, float, str, bool)) else node.pairs[0][0])
                val_type = self._infer_kotlin_type(node.pairs[0][1])
                return f'MutableMap<{key_type}, {val_type}>'
            return 'MutableMap<String, Any>'
        if isinstance(node, ast.Identifier):
            looked = self.symbols.lookup(node.name)
            if looked: return looked
            if self.in_class and node.name in self.class_properties:
                return self.class_properties[node.name]
        if isinstance(node, ast.BinaryOp):
            lt = self._infer_kotlin_type(node.left)
            rt = self._infer_kotlin_type(node.right)
            if node.operator == '+' and (lt == 'String' or rt == 'String'):
                return 'String'
            if node.operator in ('==', '!=', '<', '>', '<=', '>=', 'and', 'or'):
                return 'Boolean'
            if node.operator in ('+', '-', '*', '%'):
                if lt == 'Double' or rt == 'Double': return 'Double'
                if lt == 'Int' and rt == 'Int': return 'Int'
            if node.operator == '/': return 'Double'
            if node.operator == '//': return 'Int'
            if node.operator == '**': return 'Double'
        if isinstance(node, ast.UnaryOp):
            if node.operator == 'not': return 'Boolean'
            return self._infer_kotlin_type(node.operand)
        if isinstance(node, ast.FunctionCall):
            fn_info = self.symbols.lookup_function(node.name)
            if fn_info: return fn_info['return']
            # Built-in return types
            builtin_types = {
                'length': 'Int', 'to_integer': 'Int', 'to_text': 'String',
                'to_decimal': 'Double', 'uppercase': 'String', 'lowercase': 'String',
                'sqrt': 'Double', 'power': 'Double', 'floor': 'Int', 'ceil': 'Int',
                'absolute': 'Int', 'max': 'Int', 'min': 'Int',
                'random': 'Double', 'log': 'Double', 'sin': 'Double', 'cos': 'Double',
                'type_of': 'String', 'is_integer': 'Boolean', 'is_decimal': 'Boolean',
                'is_text': 'Boolean', 'is_boolean': 'Boolean', 'is_list': 'Boolean',
                'is_nothing': 'Boolean', 'is_number': 'Boolean',
            }
            return builtin_types.get(node.name, 'Any')
        if isinstance(node, ast.TernaryExpression):
            tt = self._infer_kotlin_type(node.true_expr)
            ft = self._infer_kotlin_type(node.false_expr)
            if tt == ft: return tt
        if isinstance(node, ast.NewInstance):
            return node.class_name
        if isinstance(node, ast.LambdaExpression):
            ret_type = self._infer_kotlin_type(node.body)
            params_part = ', '.join(['Any'] * len(node.params)) if node.params else ''
            return f'({params_part}) -> {ret_type}'
        if isinstance(node, ast.MethodCall):
            method_ret = {
                'length': 'Int', 'size': 'Int', 'contains': 'Boolean',
                'starts_with': 'Boolean', 'ends_with': 'Boolean',
                'index_of': 'Int', 'find': 'Any?', 'count': 'Int',
                'upper': 'String', 'uppercase': 'String',
                'lower': 'String', 'lowercase': 'String',
                'trim': 'String', 'replace': 'String', 'substring': 'String',
                'split': 'MutableList<String>', 'join': 'String',
                'sort': 'MutableList<Any>', 'sorted': 'MutableList<Any>',
                'reverse': 'MutableList<Any>', 'reversed': 'MutableList<Any>',
                'add': 'Unit', 'push': 'Unit', 'remove': 'Unit',
                'repeat': 'String',
            }
            return method_ret.get(node.method_name, 'Any')
        if isinstance(node, ast.IndexAccess):
            obj_type = self._infer_kotlin_type(node.obj)
            if obj_type == 'String': return 'Char'
            if obj_type.startswith('MutableList<'):
                inner = obj_type[len('MutableList<'):-1]
                return inner
            if obj_type.startswith('MutableMap<'):
                parts = obj_type[len('MutableMap<'):-1].split(', ', 1)
                if len(parts) == 2: return parts[1]
        if isinstance(node, ast.PropertyAccess):
            cls_info = self.symbols.lookup_class(self._infer_kotlin_type(node.obj) if hasattr(node.obj, 'name') else '')
            if cls_info and node.property_name in cls_info.get('properties', {}):
                return cls_info['properties'][node.property_name]
        return 'Any'

    def _infer_param_type(self, param) -> str:
        """Infer Kotlin type for a function parameter."""
        if len(param) > 1 and param[1]:
            type_map = {'integer': 'Int', 'int': 'Int', 'decimal': 'Double',
                       'float': 'Double', 'text': 'String', 'string': 'String',
                       'boolean': 'Boolean', 'bool': 'Boolean', 'list': 'MutableList<Any>',
                       'map': 'MutableMap<String, Any>'}
            return type_map.get(str(param[1]).lower(), 'Any')
        return 'Any'

    def _format_param(self, p) -> str:
        """Format a parameter with type and optional default value."""
        kt_type = self._infer_param_type(p)
        if len(p) > 2 and p[2] is not None:
            return f'{p[0]}: {kt_type} = {self._expr(p[2])}'
        return f'{p[0]}: {kt_type}'

    def _infer_return_type(self, node) -> str:
        """Infer return type from function body by scanning all return paths."""
        # Check explicit return type annotation
        if hasattr(node, 'return_type') and node.return_type:
            type_map = {'integer': 'Int', 'int': 'Int', 'decimal': 'Double',
                       'float': 'Double', 'text': 'String', 'string': 'String',
                       'boolean': 'Boolean', 'bool': 'Boolean', 'list': 'MutableList<Any>',
                       'nothing': 'Unit'}
            return type_map.get(str(node.return_type).lower(), 'Any')

        return_types = set()
        self._collect_return_types(node.body, return_types)
        if not return_types:
            return 'Unit'
        # Remove Unit from mixed returns
        non_unit = return_types - {'Unit'}
        if len(non_unit) == 1:
            return non_unit.pop()
        if len(non_unit) == 0:
            return 'Unit'
        # Multiple return types — find common supertype
        if non_unit <= {'Int', 'Double'}:
            return 'Double'
        return 'Any'

    def _collect_return_types(self, stmts, types):
        """Recursively collect return types from statement list."""
        for s in stmts:
            if isinstance(s, ast.ReturnStatement):
                if s.value:
                    types.add(self._infer_kotlin_type(s.value))
                else:
                    types.add('Unit')
            elif isinstance(s, ast.IfStatement):
                self._collect_return_types(s.then_body, types)
                if s.else_body:
                    self._collect_return_types(s.else_body, types)
            elif isinstance(s, ast.WhileLoop):
                self._collect_return_types(s.body, types)
            elif isinstance(s, ast.ForRange):
                self._collect_return_types(s.body, types)
            elif isinstance(s, ast.ForEachLoop):
                self._collect_return_types(s.body, types)
            elif isinstance(s, ast.TryCatch):
                self._collect_return_types(s.try_body, types)
                self._collect_return_types(s.catch_body, types)

    def _emit_return(self, node):
        if node.value:
            self._line(f'return {self._expr(node.value)}')
        else:
            self._line('return')

    def _emit_class(self, node):
        prev_class = self.in_class
        prev_props = self.class_properties.copy()
        prev_symbols = self.symbols
        self.in_class = node.name
        self.class_properties = {}  # name -> kotlin type
        self.symbols = self.symbols.child()  # new scope for class

        # Collect and categorize body items
        properties = []
        init_method = None
        methods = []
        static_methods = []
        abstract_methods = []
        const_declarations = []
        for item in node.body:
            if isinstance(item, ast.VarDeclaration):
                properties.append(item)
                kt_type = self._infer_kotlin_type(item.value)
                self.class_properties[item.name] = kt_type
                self.symbols.define(item.name, kt_type)
            elif isinstance(item, ast.ConstDeclaration):
                const_declarations.append(item)
            elif isinstance(item, ast.FunctionDef):
                if item.name == 'init':
                    init_method = item
                else:
                    methods.append(item)
            elif isinstance(item, ast.StaticMethodDef):
                static_methods.append(item)
            elif isinstance(item, ast.AbstractMethodDef):
                abstract_methods.append(item)
            elif isinstance(item, ast.VisibilityModifier):
                inner = item.statement
                if isinstance(inner, ast.VarDeclaration):
                    properties.append(inner)
                    kt_type = self._infer_kotlin_type(inner.value)
                    self.class_properties[inner.name] = kt_type
                    self.symbols.define(inner.name, kt_type)
                elif isinstance(inner, ast.FunctionDef):
                    methods.append(inner)
                elif isinstance(inner, ast.StaticMethodDef):
                    static_methods.append(inner)

        parent = f' : {node.parent}()' if node.parent else ''
        implements = getattr(node, 'implements', None) or []
        if implements:
            ifaces = ', '.join(implements)
            if parent:
                parent = f'{parent}, {ifaces}'
            else:
                parent = f' : {ifaces}'

        modifier = 'abstract ' if abstract_methods else 'open '
        self._line(f'{modifier}class {node.name}{parent} {{')
        self.indent += 1

        # Emit properties
        for prop in properties:
            val_str = self._expr(prop.value)
            kt_type = self.class_properties.get(prop.name, 'Any')
            self._line(f'var {prop.name}: {kt_type} = {val_str}')

        # Constants
        for c in const_declarations:
            kt_type = self._infer_kotlin_type(c.value)
            self._line(f'val {c.name}: {kt_type} = {self._expr(c.value)}')

        # Emit init using Kotlin init {} block
        if init_method:
            self._line('')
            # Filter out 'self' from init params
            init_params = [p for p in init_method.params if p[0] != 'self']
            if init_params:
                # Use a factory create() since Kotlin init{} can't take params directly
                params = ', '.join(f'{p[0]}: {self._infer_param_type(p)}' for p in init_params)
                self._line(f'fun initialize({params}) {{')
                self.indent += 1
                for s in init_method.body:
                    self._emit_stmt(s)
                self.indent -= 1
                self._line('}')
            else:
                # No-arg init → use Kotlin init {} block
                self._line('init {')
                self.indent += 1
                for s in init_method.body:
                    self._emit_stmt(s)
                self.indent -= 1
                self._line('}')

        # Abstract method declarations
        for am in abstract_methods:
            self._line('')
            self._emit_abstract_method(am)

        # Instance methods
        for m in methods:
            self._line('')
            self._emit_class_method(m)

        # Companion object for static methods + factory
        has_companion = static_methods or (init_method and [p for p in init_method.params if p[0] != 'self'])
        if has_companion:
            self._line('')
            self._line('companion object {')
            self.indent += 1
            # Factory method
            if init_method:
                init_params = [p for p in init_method.params if p[0] != 'self']
                if init_params:
                    params_sig = ', '.join(f'{p[0]}: {self._infer_param_type(p)}' for p in init_params)
                    args_pass = ', '.join(p[0] for p in init_params)
                    self._line(f'fun create({params_sig}): {node.name} {{')
                    self.indent += 1
                    self._line(f'val instance = {node.name}()')
                    self._line(f'instance.initialize({args_pass})')
                    self._line('return instance')
                    self.indent -= 1
                    self._line('}')
            for sm in static_methods:
                self._line('')
                self._emit_static_method(sm)
            self.indent -= 1
            self._line('}')

        self.indent -= 1
        self._line('}')
        self.in_class = prev_class
        self.class_properties = prev_props
        self.symbols = prev_symbols

    def _emit_enum(self, node):
        self._line(f'enum class {node.name} {{')
        self.indent += 1
        self._line(', '.join(node.members))
        self.indent -= 1
        self._line('}')

    def _emit_match(self, node):
        self._line(f'when ({self._expr(node.expression)}) {{')
        self.indent += 1
        for clause in node.when_clauses:
            vals = ', '.join(self._expr(v) for v in clause.values)
            self._line(f'{vals} -> {{')
            self.indent += 1
            for s in clause.body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        if node.default_body:
            self._line('else -> {')
            self.indent += 1
            for s in node.default_body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        self.indent -= 1
        self._line('}')

    def _emit_try_catch(self, node):
        self._line('try {')
        self.indent += 1
        for s in node.try_body: self._emit_stmt(s)
        self.indent -= 1
        self._line(f'}} catch ({node.error_var or "e"}: Exception) {{')
        self.indent += 1
        for s in node.catch_body: self._emit_stmt(s)
        self.indent -= 1
        if hasattr(node, 'finally_body') and node.finally_body:
            self._line('} finally {')
            self.indent += 1
            for s in node.finally_body: self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    def _emit_window_comment(self, node):
        """Emit Window as a comment in non-Android context."""
        title = self._expr(node.title) if node.title else '"App"'
        self._line(f'// Window: {title}')
        for s in node.body:
            self._emit_stmt(s)

    def _emit_dialog(self, node):
        """Emit dialog show as Android AlertDialog."""
        self.imports.add('androidx.appcompat.app.AlertDialog')
        msg = self._expr(node.message)
        dtype = node.dialog_type.lower()
        if dtype == 'error':
            self._line(f'AlertDialog.Builder(this).setTitle("Error").setMessage({msg}).setPositiveButton("OK", null).show()')
        elif dtype in ('yesno', 'confirm'):
            self._line(f'AlertDialog.Builder(this).setMessage({msg})')
            self.indent += 1
            self._line('.setPositiveButton("Yes") { _, _ -> /* yes handler */ }')
            self._line('.setNegativeButton("No") { _, _ -> /* no handler */ }')
            self._line('.show()')
            self.indent -= 1
        elif dtype == 'input':
            self.imports.add('android.widget.EditText')
            self._line(f'val dialogInput = EditText(this)')
            self._line(f'AlertDialog.Builder(this).setTitle({msg}).setView(dialogInput)')
            self.indent += 1
            self._line('.setPositiveButton("OK") { _, _ -> val text = dialogInput.text.toString() }')
            self._line('.show()')
            self.indent -= 1
        else:
            self._line(f'Toast.makeText(this, {msg}, Toast.LENGTH_LONG).show()')

    def _emit_async_function(self, node):
        """Emit async function as Kotlin coroutine."""
        self.imports.add('kotlinx.coroutines.*')
        real_params = [p for p in node.params if p[0] != 'self']
        params = ', '.join(self._format_param(p) for p in real_params)
        ret_type = self._infer_return_type(node)
        # Register in symbol table before body (supports recursion)
        param_types = [(p[0], self._infer_param_type(p)) for p in real_params]
        self.symbols.define_function(node.name, param_types, ret_type)
        self._line(f'suspend fun {node.name}({params}): {ret_type} {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if ret_type == 'Unit' and not any(isinstance(s, ast.ReturnStatement) for s in node.body):
            pass  # Unit return doesn't need explicit return
        self.indent -= 1
        self._line('}')
    def _emit_super_call(self, node):
        """Emit super method call."""
        args = ', '.join(self._expr(a) for a in node.arguments)
        if node.method_name:
            self._line(f'super.{node.method_name}({args})')
        else:
            self._line(f'super({args})')

    # ─── Expressions ─────────────────────────────────────

    def _expr(self, node) -> str:
        if node is None: return 'null'
        if isinstance(node, ast.Literal): return self._expr_literal(node)
        if isinstance(node, ast.Identifier):
            name = node.name
            if self.in_class and name in self.class_properties:
                return f'this.{name}'
            return name
        if isinstance(node, ast.BinaryOp): return self._expr_binary(node)
        if isinstance(node, ast.UnaryOp): return self._expr_unary(node)
        if isinstance(node, ast.FunctionCall): return self._expr_call(node)
        if isinstance(node, ast.PropertyAccess): return f'{self._expr(node.obj)}.{node.property_name}'
        if isinstance(node, ast.MethodCall): return self._expr_method(node)
        if isinstance(node, ast.IndexAccess): return f'{self._expr(node.obj)}[{self._expr(node.index)}]'
        if isinstance(node, ast.ListLiteral): return f'mutableListOf({", ".join(self._expr(e) for e in node.elements)})'
        if isinstance(node, ast.DictLiteral): return self._expr_dict(node)
        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.arguments:
                cls_info = self.symbols.lookup_class(node.class_name)
                if cls_info:
                    return f'{node.class_name}.create({args})'
                return f'{node.class_name}({args})'
            return f'{node.class_name}()'
        if isinstance(node, ast.LambdaExpression):
            param_str = ', '.join(node.params) if node.params else ''
            body_str = self._expr(node.body)
            return f'{{ {param_str} -> {body_str} }}' if param_str else f'{{ {body_str} }}'
        if isinstance(node, ast.TernaryExpression):
            return f'if ({self._expr(node.condition)}) {self._expr(node.true_expr)} else {self._expr(node.false_expr)}'
        if isinstance(node, ast.ModuleAccess): return f'{node.module_name}.{node.member_name}'
        # v4 expression types
        if isinstance(node, ast.AwaitExpression):
            return self._expr(node.expression)
        if isinstance(node, ast.SpreadExpression):
            return f'*{self._expr(node.expression)}.toTypedArray()'
        if isinstance(node, ast.ChainedComparison):
            parts = []
            for i in range(len(node.operators)):
                left = self._expr(node.operands[i])
                right = self._expr(node.operands[i + 1])
                parts.append(f'({left} {node.operators[i]} {right})')
            return ' && '.join(parts)
        if isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                return f'super.{node.method_name}({args})'
            return f'super({args})'
        if isinstance(node, str):
            return f'"{node}"'
        # Fallback with type info comment
        return f'null /* unhandled: {type(node).__name__} */'

    def _expr_literal(self, node):
        if isinstance(node.value, bool): return 'true' if node.value else 'false'
        if isinstance(node.value, str):
            escaped = node.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
            return f'"{escaped}"'
        if node.value is None: return 'null'
        if isinstance(node.value, float): return str(node.value)
        return str(node.value)

    def _expr_binary(self, node):
        l, r = self._expr(node.left), self._expr(node.right)
        op = node.operator
        m = {'and': '&&', 'or': '||', '**': '', '//': ''}
        if op == '**':
            self.imports.add('kotlin.math.pow')
            return f'{l}.toDouble().pow({r}.toDouble())'
        if op == '//':
            self.imports.add('kotlin.math.floor')
            return f'floor({l}.toDouble() / {r}.toDouble()).toInt()'
        return f'({l} {m.get(op, op)} {r})'

    def _expr_unary(self, node):
        if node.operator == 'not': return f'!{self._expr(node.operand)}'
        return f'{node.operator}{self._expr(node.operand)}'

    def _expr_call(self, node):
        args = ', '.join(self._expr(a) for a in node.arguments)
        m = {
            'length': lambda: f'{self._expr(node.arguments[0])}.length',
            'to_integer': lambda: f'{self._expr(node.arguments[0])}.toString().toInt()',
            'to_text': lambda: f'{self._expr(node.arguments[0])}.toString()',
            'to_decimal': lambda: f'{self._expr(node.arguments[0])}.toString().toDouble()',
            'uppercase': lambda: f'{self._expr(node.arguments[0])}.uppercase()',
            'lowercase': lambda: f'{self._expr(node.arguments[0])}.lowercase()',
            'sqrt': lambda: f'kotlin.math.sqrt({args}.toDouble())',
            'power': lambda: f'{self._expr(node.arguments[0])}.toDouble().pow({self._expr(node.arguments[1])}.toDouble())',
            'floor': lambda: f'kotlin.math.floor({args}.toDouble()).toInt()',
            'ceil': lambda: f'kotlin.math.ceil({args}.toDouble()).toInt()',
            'absolute': lambda: f'kotlin.math.abs({args})',
            'max': lambda: f'maxOf({args})',
            'min': lambda: f'minOf({args})',
            'random': lambda: f'kotlin.random.Random.nextDouble()',
            'log': lambda: f'kotlin.math.ln({args}.toDouble())',
            'sin': lambda: f'kotlin.math.sin({args}.toDouble())',
            'cos': lambda: f'kotlin.math.cos({args}.toDouble())',
        }
        if node.name in m:
            if node.name == 'power':
                self.imports.add('kotlin.math.pow')
            return m[node.name]()
        return f'{node.name}({args})'

    def _expr_method(self, node):
        obj = self._expr(node.obj)
        args = ', '.join(self._expr(a) for a in node.arguments)
        m = node.method_name
        km = {
            'add': 'add', 'push': 'add', 'remove': 'removeAt',
            'upper': 'uppercase', 'uppercase': 'uppercase',
            'lower': 'lowercase', 'lowercase': 'lowercase',
            'trim': 'trim', 'contains': 'contains', 'replace': 'replace',
            'starts_with': 'startsWith', 'ends_with': 'endsWith',
            'split': 'split', 'reverse': 'reversed', 'sort': 'sorted',
            'substring': 'substring', 'length': 'length',
            'join': 'joinToString', 'index_of': 'indexOf',
            'find': 'find', 'repeat': 'repeat',
        }
        if m == 'length': return f'{obj}.size'
        return f'{obj}.{km.get(m, m)}({args})'

    def _expr_dict(self, node):
        def key_expr(k):
            if isinstance(k, str):
                escaped = k.replace('\\', '\\\\').replace('"', '\\"')
                return f'"{escaped}"'
            if hasattr(k, 'line'):  # AST node
                return self._expr(k)
            return str(k)
        pairs = ', '.join(f'{key_expr(k)} to {self._expr(v)}' for k, v in node.pairs)
        return f'mutableMapOf({pairs})'


class AndroidProjectGenerator:
    """Generates a complete Android project structure from EPL source."""

    GRADLE_WRAPPER_VERSION = ANDROID_GRADLE_WRAPPER_VERSION
    ANDROID_PLUGIN_VERSION = ANDROID_GRADLE_PLUGIN_VERSION
    KOTLIN_VERSION = ANDROID_KOTLIN_VERSION

    def __init__(self, app_name="EPLApp", package_name="com.epl.app"):
        self.app_name = app_name
        self.package = package_name
        self.package_path = package_name.replace('.', '/')

    def generate(self, program: ast.Program, output_dir: str, use_compose=False):
        """Generate a complete Android project with dynamic UI from EPL."""
        os.makedirs(output_dir, exist_ok=True)

        gen = KotlinGenerator(self.package)

        if use_compose:
            activity_code = gen.generate_compose_activity(program)
        else:
            activity_code = gen.generate_android_activity(program)
        main_code = gen.generate(program)

        # Create project structure
        dirs = [
            f'{output_dir}/app/src/main/java/{self.package_path}',
            f'{output_dir}/app/src/main/java/{self.package_path}/ui',
            f'{output_dir}/app/src/main/java/{self.package_path}/data',
            f'{output_dir}/app/src/main/java/{self.package_path}/data/local',
            f'{output_dir}/app/src/main/java/{self.package_path}/data/remote',
            f'{output_dir}/app/src/main/java/{self.package_path}/data/model',
            f'{output_dir}/app/src/main/java/{self.package_path}/di',
            f'{output_dir}/app/src/main/res/layout',
            f'{output_dir}/app/src/main/res/navigation',
            f'{output_dir}/app/src/main/res/values',
            f'{output_dir}/app/src/main/res/values-night',
            f'{output_dir}/app/src/main/res/drawable',
            f'{output_dir}/app/src/main/res/mipmap-anydpi-v26',
            f'{output_dir}/app/src/main/res/mipmap-hdpi',
            f'{output_dir}/app/src/main/res/mipmap-mdpi',
            f'{output_dir}/app/src/main/res/mipmap-xhdpi',
            f'{output_dir}/app/src/main/res/mipmap-xxhdpi',
            f'{output_dir}/app/src/main/res/xml',
            f'{output_dir}/app/src/main/res/menu',
            f'{output_dir}/app/src/test/java/{self.package_path}',
            f'{output_dir}/app/src/androidTest/java/{self.package_path}',
            f'{output_dir}/gradle/wrapper',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        # Write main files
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/MainActivity.kt', activity_code)
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/EPLRuntime.kt', self._epl_runtime_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/EPLApplication.kt', self._application_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/DetailActivity.kt', self._detail_activity_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/SettingsActivity.kt', self._settings_activity_kt())
        # Data layer: Room + Retrofit
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/data/Repository.kt', self._repository_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/data/model/EPLEntity.kt', self._room_entity_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/data/local/EPLDao.kt', self._room_dao_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/data/local/EPLDatabase.kt', self._room_database_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/data/remote/ApiService.kt', self._retrofit_api_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/data/remote/RetrofitClient.kt', self._retrofit_client_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/di/ServiceLocator.kt', self._service_locator_kt())
        # UI layer
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/ui/MainViewModel.kt', self._viewmodel_kt())
        self._write(f'{output_dir}/app/src/main/java/{self.package_path}/ui/ItemAdapter.kt', self._adapter_kt())
        # Resources
        self._write(f'{output_dir}/app/src/main/AndroidManifest.xml', self._manifest())
        self._write(f'{output_dir}/app/src/main/res/layout/activity_main.xml', self._layout_from_widgets(gen.widgets))
        self._write(f'{output_dir}/app/src/main/res/layout/activity_detail.xml', self._detail_layout())
        self._write(f'{output_dir}/app/src/main/res/layout/activity_settings.xml', self._settings_layout())
        self._write(f'{output_dir}/app/src/main/res/layout/item_list.xml', self._item_layout())
        self._write(f'{output_dir}/app/src/main/res/menu/main_menu.xml', self._main_menu())
        self._write(f'{output_dir}/app/src/main/res/navigation/nav_graph.xml', self._nav_graph())
        self._write(f'{output_dir}/app/src/main/res/values/strings.xml', self._strings())
        self._write(f'{output_dir}/app/src/main/res/values/themes.xml', self._themes())
        self._write(f'{output_dir}/app/src/main/res/values/colors.xml', self._colors())
        self._write(f'{output_dir}/app/src/main/res/values/dimens.xml', self._dimens())
        self._write(f'{output_dir}/app/src/main/res/values-night/themes.xml', self._themes_night())
        self._write(f'{output_dir}/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml', self._adaptive_icon())
        self._write(f'{output_dir}/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml', self._adaptive_icon_round())
        self._write(f'{output_dir}/app/src/main/res/drawable/ic_launcher_foreground.xml', self._icon_foreground())
        self._write(f'{output_dir}/app/src/main/res/drawable/ic_launcher_background.xml', self._icon_background())
        self._write(f'{output_dir}/app/build.gradle.kts', self._app_gradle(use_compose=use_compose))
        self._write(f'{output_dir}/build.gradle.kts', self._root_gradle())
        self._write(f'{output_dir}/settings.gradle.kts', self._settings())
        self._write(f'{output_dir}/gradle.properties', self._gradle_props())
        self._copy_gradle_wrapper_assets(output_dir)
        self._write(f'{output_dir}/gradle/wrapper/gradle-wrapper.properties', self._gradle_wrapper_props())
        self._write(f'{output_dir}/app/proguard-rules.pro', self._proguard_rules())
        self._write(f'{output_dir}/.gitignore', self._gitignore())
        self._write(f'{output_dir}/local.properties', self._local_properties())
        self._write(f'{output_dir}/README.md', self._readme())
        # Test files
        self._write(f'{output_dir}/app/src/test/java/{self.package_path}/EPLRuntimeTest.kt', self._unit_test_kt())
        self._write(f'{output_dir}/app/src/androidTest/java/{self.package_path}/MainActivityTest.kt', self._instrumented_test_kt())

        # Make gradlew executable on Unix
        try:
            os.chmod(f'{output_dir}/gradlew', 0o755)
        except Exception:
            pass

        return output_dir

    def _write(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _copy_gradle_wrapper_assets(self, output_dir):
        output_root = Path(output_dir)
        assets = (
            ("gradlew", "gradlew"),
            ("gradlew.bat", "gradlew.bat"),
            ("gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.jar"),
        )
        for source_rel, dest_rel in assets:
            source = ANDROID_TEMPLATE_ROOT / source_rel
            destination = output_root / dest_rel
            if not source.exists():
                raise FileNotFoundError(f"Missing Android wrapper asset: {source}")
            shutil.copyfile(source, destination)

    def _manifest(self):
        return f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.EPLApp"
        android:name="{self.package}.EPLApplication">
        <activity
            android:name="{self.package}.MainActivity"
            android:exported="true"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <activity
            android:name="{self.package}.DetailActivity"
            android:parentActivityName="{self.package}.MainActivity" />
        <activity
            android:name="{self.package}.SettingsActivity"
            android:parentActivityName="{self.package}.MainActivity"
            android:label="@string/settings" />
    </application>
</manifest>'''

    def _layout_from_widgets(self, widgets):
        """Generate dynamic layout XML from collected GUI widgets."""
        if not widgets:
            return self._layout_default()
        
        xml_widgets = []
        for w in widgets:
            xml_widgets.append(self._widget_to_xml(w))
        
        widget_xml = '\n\n'.join(xml_widgets)
        return f'''<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
<LinearLayout
    android:id="@+id/mainLayout"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:padding="16dp">

{widget_xml}

</LinearLayout>
</ScrollView>'''

    def _widget_to_xml(self, w):
        """Convert a widget dict to Android XML element."""
        wtype = w['type']
        wid = w['id']
        
        type_map = {
            'button': 'Button',
            'label': 'TextView',
            'input': 'EditText',
            'textarea': 'EditText',
            'checkbox': 'CheckBox',
            'dropdown': 'Spinner',
            'slider': 'SeekBar',
            'progress': 'ProgressBar',
            'image': 'ImageView',
        }
        xml_type = type_map.get(wtype, 'TextView')
        
        text_attr = ''
        if w.get('text') and wtype in ('button', 'label', 'checkbox'):
            text_val = w['text'].value if hasattr(w['text'], 'value') else str(w['text'])
            text_attr = f'\n        android:text="{text_val}"'
        
        hint_attr = ''
        if wtype == 'input':
            placeholder = w['properties'].get('placeholder', 'Enter text...')
            if hasattr(placeholder, 'value'):
                placeholder = placeholder.value
            hint_attr = f'\n        android:hint="{placeholder}"'
        
        extra = ''
        if wtype == 'textarea':
            extra = '\n        android:minLines="4"\n        android:gravity="top"'
        elif wtype == 'image':
            extra = '\n        android:scaleType="fitCenter"\n        android:adjustViewBounds="true"'
        
        return f'''    <{xml_type}
        android:id="@+id/{wid}"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"{text_attr}{hint_attr}{extra}
        android:layout_marginBottom="8dp" />'''

    def _layout_default(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp"
    android:gravity="center_horizontal">

    <TextView
        android:id="@+id/titleText"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="EPL App"
        android:textSize="24sp"
        android:textStyle="bold"
        android:layout_marginBottom="16dp" />

    <EditText
        android:id="@+id/inputField"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="Enter text..."
        android:layout_marginBottom="8dp" />

    <Button
        android:id="@+id/actionButton"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Submit"
        android:layout_marginBottom="16dp" />

    <TextView
        android:id="@+id/outputText"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text=""
        android:textSize="16sp" />

</LinearLayout>'''

    def _strings(self):
        return f'''<resources>
    <string name="app_name">{self.app_name}</string>
    <string name="settings">Settings</string>
    <string name="about">About</string>
    <string name="submit">Submit</string>
    <string name="cancel">Cancel</string>
    <string name="ok">OK</string>
    <string name="loading">Loading…</string>
    <string name="error_network">Network error. Please check your connection.</string>
    <string name="error_generic">Something went wrong.</string>
    <string name="empty_state">No data available.</string>
</resources>'''

    def _themes(self):
        return '''<resources>
    <style name="Theme.EPLApp" parent="Theme.MaterialComponents.DayNight.DarkActionBar">
        <item name="colorPrimary">@color/primary</item>
        <item name="colorPrimaryVariant">@color/primary_dark</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorSecondary">@color/accent</item>
        <item name="colorOnSecondary">@color/white</item>
    </style>
</resources>'''

    def _themes_night(self):
        return '''<resources>
    <style name="Theme.EPLApp" parent="Theme.MaterialComponents.DayNight.DarkActionBar">
        <item name="colorPrimary">@color/primary_night</item>
        <item name="colorPrimaryVariant">@color/primary_dark_night</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorSecondary">@color/accent_night</item>
        <item name="colorOnSecondary">@color/white</item>
        <item name="android:statusBarColor">@color/primary_dark_night</item>
        <item name="android:navigationBarColor">@color/background_dark</item>
    </style>
</resources>'''

    def _colors(self):
        return '''<resources>
    <color name="primary">#3b82f6</color>
    <color name="primary_dark">#1e40af</color>
    <color name="accent">#8b5cf6</color>
    <color name="white">#FFFFFF</color>
    <color name="black">#000000</color>
    <color name="background_light">#FAFAFA</color>
    <color name="surface_light">#FFFFFF</color>
    <color name="on_surface_light">#212121</color>
    <!-- Dark theme colors -->
    <color name="primary_night">#60a5fa</color>
    <color name="primary_dark_night">#1e3a5f</color>
    <color name="accent_night">#a78bfa</color>
    <color name="background_dark">#121212</color>
    <color name="surface_dark">#1E1E1E</color>
    <color name="on_surface_dark">#E0E0E0</color>
</resources>'''

    def _app_gradle(self, use_compose=False):
        compose_plugin = '\n    id("org.jetbrains.kotlin.plugin.compose")' if use_compose else ''
        compose_build_features = '''
    buildFeatures {
        compose = true
        viewBinding = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }''' if use_compose else '''
    buildFeatures {
        viewBinding = true
    }'''
        compose_deps = '''
    // Jetpack Compose
    implementation(platform("androidx.compose:compose-bom:2024.02.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.runtime:runtime-livedata")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.navigation:navigation-compose:2.7.6")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
''' if use_compose else ''
        return f'''plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.kapt"){compose_plugin}
}}

android {{
    namespace = "{self.package}"
    compileSdk = 34

    defaultConfig {{
        applicationId = "{self.package}"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }}

    buildTypes {{
        release {{
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }}
        debug {{
            isMinifyEnabled = false
            isDebuggable = true
        }}
    }}
    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }}
    kotlinOptions {{
        jvmTarget = "1.8"
    }}{compose_build_features}
}}

dependencies {{
    // Core Android
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")

    // Architecture Components
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.7.0")
    implementation("androidx.activity:activity-ktx:1.8.2")
    implementation("androidx.fragment:fragment-ktx:1.6.2")

    // Navigation
    implementation("androidx.navigation:navigation-fragment-ktx:2.7.6")
    implementation("androidx.navigation:navigation-ui-ktx:2.7.6")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Networking (Retrofit + OkHttp)
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // JSON
    implementation("com.google.code.gson:gson:2.10.1")

    // Image loading
    implementation("io.coil-kt:coil:2.5.0")

    // RecyclerView
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")

    // Room Database
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    kapt("androidx.room:room-compiler:2.6.1")

    // Preferences
    implementation("androidx.preference:preference-ktx:1.2.1")

    // Testing
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.test:runner:1.5.2")
    androidTestImplementation("androidx.test:rules:1.5.0")
}}'''

    def _root_gradle(self):
        return f'''plugins {{
    id("com.android.application") version "{self.ANDROID_PLUGIN_VERSION}" apply false
    id("org.jetbrains.kotlin.android") version "{self.KOTLIN_VERSION}" apply false
    id("org.jetbrains.kotlin.kapt") version "{self.KOTLIN_VERSION}" apply false
}}'''

    def _settings(self):
        return f'''pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}
rootProject.name = "{self.app_name}"
include(":app")'''

    def _gradle_props(self):
        return '''android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true'''

    def _gradlew_unix(self):
        return (ANDROID_TEMPLATE_ROOT / "gradlew").read_text(encoding="utf-8")

    def _gradlew_bat(self):
        return (ANDROID_TEMPLATE_ROOT / "gradlew.bat").read_text(encoding="utf-8")

    def _gradle_wrapper_props(self):
        return f'''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{self.GRADLE_WRAPPER_VERSION}-bin.zip
networkTimeout=120000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists'''

    def _readme(self):
        return f'''# {self.app_name}

Generated by EPL (Easy Programming Language) Kotlin Generator v2.0

## Build Instructions

1. Install Android Studio or Android SDK
2. Open this project in Android Studio
3. Or build from command line with the standard Gradle wrapper:
   ```
   ./gradlew lintDebug testDebugUnitTest assembleDebug assembleRelease
   ```
   On Windows use:
   ```
   gradlew.bat lintDebug testDebugUnitTest assembleDebug assembleRelease
   ```
4. Install on device:
   ```
   ./gradlew installDebug
   ```

## Package
`{self.package}`

## Requirements
- Android SDK 34
- Kotlin {self.KOTLIN_VERSION}
- Gradle {self.GRADLE_WRAPPER_VERSION}
- Minimum Android API 24 (Android 7.0)

## Project Structure
```
app/
├── src/main/
│   ├── java/{self.package_path}/
│   │   ├── MainActivity.kt     # Main activity with UI
│   │   └── EPLRuntime.kt       # EPL runtime helpers
│   ├── res/
│   │   ├── layout/              # XML layouts
│   │   ├── values/              # Strings, colors, themes
│   │   └── values-night/        # Dark theme
│   └── AndroidManifest.xml
├── build.gradle.kts             # App-level build config
└── proguard-rules.pro           # ProGuard rules
build.gradle.kts                 # Root build config
settings.gradle.kts              # Project settings
gradle.properties                # Gradle config
'''

    def _proguard_rules(self):
        return '''# EPL Generated App ProGuard Rules
# Keep EPL runtime classes
-keep class ''' + self.package + '''.** { *; }

# Keep Material Components
-keep class com.google.android.material.** { *; }

# General Android rules
-keepclassmembers class * implements android.os.Parcelable {
    static ** CREATOR;
}
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
}
'''

    def _gitignore(self):
        return '''*.iml
.gradle
/local.properties
/.idea
.DS_Store
/build
/captures
.externalNativeBuild
.cxx
local.properties
/app/build
'''

    def _epl_runtime_kt(self):
        return f'''package {self.package}

/**
 * EPL Runtime Support for Android
 * Generated by EPL Kotlin Generator v2.0
 */
object EPLRuntime {{
    private val variables = mutableMapOf<String, Any?>()
    
    fun setVar(name: String, value: Any?) {{
        variables[name] = value
    }}
    
    fun getVar(name: String): Any? = variables[name]
    
    fun toText(value: Any?): String = when (value) {{
        null -> "nothing"
        is Boolean -> if (value) "true" else "false"
        is Double -> if (value == value.toLong().toDouble()) value.toLong().toString() else value.toString()
        else -> value.toString()
    }}
    
    fun toInteger(value: Any?): Long = when (value) {{
        is Number -> value.toLong()
        is String -> value.toLongOrNull() ?: 0L
        is Boolean -> if (value) 1L else 0L
        else -> 0L
    }}
    
    fun toDecimal(value: Any?): Double = when (value) {{
        is Number -> value.toDouble()
        is String -> value.toDoubleOrNull() ?: 0.0
        is Boolean -> if (value) 1.0 else 0.0
        else -> 0.0
    }}
    
    fun typeOf(value: Any?): String = when (value) {{
        null -> "Nothing"
        is Long, is Int -> "Integer"
        is Double, is Float -> "Decimal"
        is String -> "String"
        is Boolean -> "Boolean"
        is List<*> -> "List"
        is Map<*, *> -> "Map"
        else -> value::class.simpleName ?: "Unknown"
    }}
    
    fun length(value: Any?): Int = when (value) {{
        is String -> value.length
        is List<*> -> value.size
        is Map<*, *> -> value.size
        else -> 0
    }}
    
    // Math helpers
    fun power(base: Double, exp: Double): Double = Math.pow(base, exp)
    fun sqrt(x: Double): Double = Math.sqrt(x)
    fun abs(x: Double): Double = Math.abs(x)
    fun floor(x: Double): Double = Math.floor(x)
    fun ceil(x: Double): Double = Math.ceil(x)
    fun round(x: Double): Long = Math.round(x)
    fun random(): Double = Math.random()
    fun randomInt(min: Int, max: Int): Int = (min..max).random()
    fun max(a: Double, b: Double): Double = maxOf(a, b)
    fun min(a: Double, b: Double): Double = minOf(a, b)
    
    // String helpers
    fun uppercase(s: String): String = s.uppercase()
    fun lowercase(s: String): String = s.lowercase()
    fun trim(s: String): String = s.trim()
    fun split(s: String, delim: String): List<String> = s.split(delim)
    fun join(list: List<*>, sep: String): String = list.joinToString(sep)
    fun replace(s: String, old: String, new: String): String = s.replace(old, new)
    fun contains(s: String, sub: String): Boolean = s.contains(sub)
    fun startsWith(s: String, prefix: String): Boolean = s.startsWith(prefix)
    fun endsWith(s: String, suffix: String): Boolean = s.endsWith(suffix)
    fun substring(s: String, start: Int, end: Int): String = s.substring(start, minOf(end, s.length))
}}
'''

    def _application_kt(self):
        return f'''package {self.package}

import android.app.Application

class EPLApplication : Application() {{
    override fun onCreate() {{
        super.onCreate()
        instance = this
    }}

    companion object {{
        lateinit var instance: EPLApplication
            private set
    }}
}}
'''

    def _detail_activity_kt(self):
        return f'''package {self.package}

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import {self.package}.databinding.ActivityDetailBinding

class DetailActivity : AppCompatActivity() {{
    private lateinit var binding: ActivityDetailBinding

    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        binding = ActivityDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val title = intent.getStringExtra("title") ?: "Detail"
        val content = intent.getStringExtra("content") ?: ""
        supportActionBar?.title = title
        binding.detailContent.text = content
    }}

    override fun onSupportNavigateUp(): Boolean {{
        onBackPressedDispatcher.onBackPressed()
        return true
    }}
}}
'''

    def _settings_activity_kt(self):
        return f'''package {self.package}

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import {self.package}.databinding.ActivitySettingsBinding

class SettingsActivity : AppCompatActivity() {{
    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = getString(R.string.settings)
    }}

    override fun onSupportNavigateUp(): Boolean {{
        onBackPressedDispatcher.onBackPressed()
        return true
    }}
}}
'''

    def _repository_kt(self):
        return f'''package {self.package}.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Repository pattern for data access.
 * Generated by EPL Android Generator.
 */
class Repository {{
    private val items = mutableListOf<Map<String, Any?>>()

    suspend fun getItems(): List<Map<String, Any?>> = withContext(Dispatchers.IO) {{
        items.toList()
    }}

    suspend fun addItem(item: Map<String, Any?>) = withContext(Dispatchers.IO) {{
        items.add(item)
    }}

    suspend fun removeItem(index: Int) = withContext(Dispatchers.IO) {{
        if (index in items.indices) items.removeAt(index)
    }}

    suspend fun updateItem(index: Int, item: Map<String, Any?>) = withContext(Dispatchers.IO) {{
        if (index in items.indices) items[index] = item
    }}

    companion object {{
        @Volatile private var instance: Repository? = null
        fun getInstance(): Repository = instance ?: synchronized(this) {{
            instance ?: Repository().also {{ instance = it }}
        }}
    }}
}}
'''

    def _room_entity_kt(self):
        return f'''package {self.package}.data.model

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "epl_items")
data class EPLEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String = "",
    val content: String = "",
    val category: String = "",
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)
'''

    def _room_dao_kt(self):
        return f'''package {self.package}.data.local

import androidx.room.*
import {self.package}.data.model.EPLEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface EPLDao {{
    @Query("SELECT * FROM epl_items ORDER BY createdAt DESC")
    fun getAllItems(): Flow<List<EPLEntity>>

    @Query("SELECT * FROM epl_items WHERE id = :id")
    suspend fun getItemById(id: Long): EPLEntity?

    @Query("SELECT * FROM epl_items WHERE category = :category ORDER BY createdAt DESC")
    fun getItemsByCategory(category: String): Flow<List<EPLEntity>>

    @Query("SELECT * FROM epl_items WHERE title LIKE '%' || :query || '%' OR content LIKE '%' || :query || '%'")
    fun searchItems(query: String): Flow<List<EPLEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(item: EPLEntity): Long

    @Update
    suspend fun update(item: EPLEntity)

    @Delete
    suspend fun delete(item: EPLEntity)

    @Query("DELETE FROM epl_items")
    suspend fun deleteAll()

    @Query("SELECT COUNT(*) FROM epl_items")
    suspend fun getCount(): Int
}}
'''

    def _room_database_kt(self):
        return f'''package {self.package}.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import {self.package}.data.model.EPLEntity

@Database(entities = [EPLEntity::class], version = 1, exportSchema = false)
abstract class EPLDatabase : RoomDatabase() {{
    abstract fun eplDao(): EPLDao

    companion object {{
        @Volatile private var INSTANCE: EPLDatabase? = null

        fun getInstance(context: Context): EPLDatabase {{
            return INSTANCE ?: synchronized(this) {{
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    EPLDatabase::class.java,
                    "epl_database"
                ).fallbackToDestructiveMigration().build()
                INSTANCE = instance
                instance
            }}
        }}
    }}
}}
'''

    def _retrofit_api_kt(self):
        return f'''package {self.package}.data.remote

import retrofit2.Response
import retrofit2.http.*

/**
 * Retrofit API service interface.
 * Customize endpoints for your backend.
 */
interface ApiService {{
    @GET("items")
    suspend fun getItems(): Response<List<Map<String, Any?>>>

    @GET("items/{{id}}")
    suspend fun getItem(@Path("id") id: String): Response<Map<String, Any?>>

    @POST("items")
    suspend fun createItem(@Body item: Map<String, Any?>): Response<Map<String, Any?>>

    @PUT("items/{{id}}")
    suspend fun updateItem(@Path("id") id: String, @Body item: Map<String, Any?>): Response<Map<String, Any?>>

    @DELETE("items/{{id}}")
    suspend fun deleteItem(@Path("id") id: String): Response<Unit>

    @GET("search")
    suspend fun search(@Query("q") query: String): Response<List<Map<String, Any?>>>
}}
'''

    def _retrofit_client_kt(self):
        return f'''package {self.package}.data.remote

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {{
    private const val BASE_URL = "https://api.example.com/v1/"
    private const val TIMEOUT = 30L

    private val loggingInterceptor = HttpLoggingInterceptor().apply {{
        level = HttpLoggingInterceptor.Level.BODY
    }}

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT, TimeUnit.SECONDS)
        .addInterceptor(loggingInterceptor)
        .addInterceptor {{ chain ->
            val request = chain.request().newBuilder()
                .addHeader("Accept", "application/json")
                .addHeader("Content-Type", "application/json")
                .build()
            chain.proceed(request)
        }}
        .build()

    val apiService: ApiService by lazy {{
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }}
}}
'''

    def _service_locator_kt(self):
        return f'''package {self.package}.di

import android.content.Context
import {self.package}.data.Repository
import {self.package}.data.local.EPLDatabase
import {self.package}.data.remote.RetrofitClient

/**
 * Simple service locator for dependency injection.
 * Replace with Hilt/Dagger for larger projects.
 */
object ServiceLocator {{
    @Volatile private var database: EPLDatabase? = null
    @Volatile private var repository: Repository? = null

    fun provideDatabase(context: Context): EPLDatabase {{
        return database ?: synchronized(this) {{
            EPLDatabase.getInstance(context).also {{ database = it }}
        }}
    }}

    fun provideRepository(): Repository {{
        return repository ?: synchronized(this) {{
            Repository.getInstance().also {{ repository = it }}
        }}
    }}

    fun provideApiService() = RetrofitClient.apiService
}}
'''

    def _nav_graph(self):
        return f'''<?xml version="1.0" encoding="utf-8"?>
<navigation xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:id="@+id/nav_graph"
    app:startDestination="@id/mainFragment">

    <fragment
        android:id="@+id/mainFragment"
        android:name="{self.package}.ui.MainFragment"
        android:label="Home"
        tools:layout="@layout/activity_main">
        <action
            android:id="@+id/action_main_to_detail"
            app:destination="@id/detailFragment"
            app:enterAnim="@anim/nav_default_enter_anim"
            app:exitAnim="@anim/nav_default_exit_anim"
            app:popEnterAnim="@anim/nav_default_pop_enter_anim"
            app:popExitAnim="@anim/nav_default_pop_exit_anim" />
        <action
            android:id="@+id/action_main_to_settings"
            app:destination="@id/settingsFragment" />
    </fragment>

    <fragment
        android:id="@+id/detailFragment"
        android:name="{self.package}.ui.DetailFragment"
        android:label="Detail"
        tools:layout="@layout/activity_detail">
        <argument
            android:name="itemId"
            app:argType="long"
            android:defaultValue="0L" />
    </fragment>

    <fragment
        android:id="@+id/settingsFragment"
        android:name="{self.package}.ui.SettingsFragment"
        android:label="Settings"
        tools:layout="@layout/activity_settings" />
</navigation>'''

    def _viewmodel_kt(self):
        return f'''package {self.package}.ui

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import {self.package}.data.Repository
import kotlinx.coroutines.launch

class MainViewModel : ViewModel() {{
    private val repository = Repository.getInstance()

    private val _items = MutableLiveData<List<Map<String, Any?>>>(emptyList())
    val items: LiveData<List<Map<String, Any?>>> = _items

    private val _loading = MutableLiveData(false)
    val loading: LiveData<Boolean> = _loading

    private val _error = MutableLiveData<String?>()
    val error: LiveData<String?> = _error

    fun loadItems() {{
        viewModelScope.launch {{
            _loading.value = true
            try {{
                _items.value = repository.getItems()
                _error.value = null
            }} catch (e: Exception) {{
                _error.value = e.message
            }} finally {{
                _loading.value = false
            }}
        }}
    }}

    fun addItem(item: Map<String, Any?>) {{
        viewModelScope.launch {{
            repository.addItem(item)
            loadItems()
        }}
    }}
}}
'''

    def _adapter_kt(self):
        return f'''package {self.package}.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import {self.package}.databinding.ItemListBinding

class ItemAdapter(
    private val onItemClick: (Map<String, Any?>, Int) -> Unit = {{ _, _ -> }}
) : ListAdapter<Map<String, Any?>, ItemAdapter.ViewHolder>(DiffCallback()) {{

    inner class ViewHolder(val binding: ItemListBinding) : RecyclerView.ViewHolder(binding.root) {{
        fun bind(item: Map<String, Any?>, position: Int) {{
            binding.itemTitle.text = item["title"]?.toString() ?: "Item ${{position + 1}}"
            binding.itemSubtitle.text = item["subtitle"]?.toString() ?: ""
            binding.root.setOnClickListener {{ onItemClick(item, position) }}
        }}
    }}

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {{
        val binding = ItemListBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }}

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {{
        holder.bind(getItem(position), position)
    }}

    class DiffCallback : DiffUtil.ItemCallback<Map<String, Any?>>() {{
        override fun areItemsTheSame(a: Map<String, Any?>, b: Map<String, Any?>): Boolean {{
            val aId = a["id"]?.toString()
            val bId = b["id"]?.toString()
            return if (aId != null && bId != null) {{
                aId == bId
            }} else {{
                stableFingerprint(a) == stableFingerprint(b)
            }}
        }}

        override fun areContentsTheSame(a: Map<String, Any?>, b: Map<String, Any?>): Boolean {{
            return stableFingerprint(a) == stableFingerprint(b)
        }}

        private fun stableFingerprint(item: Map<String, Any?>): String {{
            return item.toSortedMap().entries.joinToString("|") {{ (key, value) ->
                "${{key}}=${{fingerprintValue(value)}}"
            }}
        }}

        private fun fingerprintValue(value: Any?): String {{
            return when (value) {{
                null -> "null"
                is Map<*, *> -> value.entries
                    .sortedBy {{ it.key?.toString().orEmpty() }}
                    .joinToString(prefix = "{{", postfix = "}}") {{ entry ->
                        "${{entry.key}}=${{fingerprintValue(entry.value)}}"
                    }}
                is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") {{
                    fingerprintValue(it)
                }}
                is Array<*> -> value.joinToString(prefix = "[", postfix = "]") {{
                    fingerprintValue(it)
                }}
                else -> value.toString()
            }}
        }}
    }}
}}
'''

    def _detail_layout(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical"
        android:padding="@dimen/screen_padding">

        <TextView
            android:id="@+id/detailContent"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:textSize="16sp"
            android:lineSpacingExtra="4dp" />
    </LinearLayout>
</ScrollView>'''

    def _settings_layout(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="@dimen/screen_padding">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/settings"
        android:textSize="20sp"
        android:textStyle="bold"
        android:layout_marginBottom="16dp" />

    <com.google.android.material.switchmaterial.SwitchMaterial
        android:id="@+id/darkModeSwitch"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Dark Mode"
        android:layout_marginBottom="8dp" />

    <com.google.android.material.switchmaterial.SwitchMaterial
        android:id="@+id/notificationsSwitch"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Notifications"
        android:checked="true" />
</LinearLayout>'''

    def _item_layout(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<com.google.android.material.card.MaterialCardView
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:layout_marginHorizontal="@dimen/item_margin"
    android:layout_marginVertical="4dp"
    app:cardElevation="2dp"
    app:cardCornerRadius="8dp">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical"
        android:padding="16dp">

        <TextView
            android:id="@+id/itemTitle"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:textSize="16sp"
            android:textStyle="bold" />

        <TextView
            android:id="@+id/itemSubtitle"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:textSize="14sp"
            android:textColor="?android:textColorSecondary"
            android:layout_marginTop="4dp" />
    </LinearLayout>
</com.google.android.material.card.MaterialCardView>'''

    def _main_menu(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<menu xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto">
    <item
        android:id="@+id/action_settings"
        android:title="@string/settings"
        app:showAsAction="never" />
    <item
        android:id="@+id/action_about"
        android:title="@string/about"
        app:showAsAction="never" />
</menu>'''

    def _dimens(self):
        return '''<resources>
    <dimen name="screen_padding">16dp</dimen>
    <dimen name="item_margin">8dp</dimen>
    <dimen name="text_title">24sp</dimen>
    <dimen name="text_body">16sp</dimen>
    <dimen name="text_caption">12sp</dimen>
    <dimen name="corner_radius">8dp</dimen>
    <dimen name="elevation_card">2dp</dimen>
</resources>'''

    def _adaptive_icon(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background"/>
    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
</adaptive-icon>'''

    def _adaptive_icon_round(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background"/>
    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
</adaptive-icon>'''

    def _icon_foreground(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M54,30 L54,78 M38,54 L54,30 L70,54"
        android:strokeWidth="4"
        android:strokeColor="#FFFFFF"/>
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M36,40 L36,68 M42,40 L42,68 M36,54 L42,54"
        android:strokeWidth="3"
        android:strokeColor="#FFFFFF"/>
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M66,40 L66,68 M72,40 L72,68"
        android:strokeWidth="3"
        android:strokeColor="#FFFFFF"/>
</vector>'''

    def _icon_background(self):
        return '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#3b82f6"
        android:pathData="M0,0h108v108h-108z"/>
</vector>'''

    def _local_properties(self):
        return '''# This file should NOT be checked into version control.
# Set sdk.dir to point to your Android SDK installation.
# sdk.dir=/path/to/android/sdk
'''

    def _unit_test_kt(self):
        return f'''package {self.package}

import org.junit.Assert.*
import org.junit.Test

class EPLRuntimeTest {{
    @Test
    fun testToText() {{
        assertEquals("42", EPLRuntime.toText(42))
        assertEquals("hello", EPLRuntime.toText("hello"))
        assertEquals("true", EPLRuntime.toText(true))
        assertEquals("nothing", EPLRuntime.toText(null))
    }}

    @Test
    fun testToInteger() {{
        assertEquals(42L, EPLRuntime.toInteger(42))
        assertEquals(42L, EPLRuntime.toInteger("42"))
        assertEquals(1L, EPLRuntime.toInteger(true))
        assertEquals(0L, EPLRuntime.toInteger(null))
    }}

    @Test
    fun testTypeOf() {{
        assertEquals("Integer", EPLRuntime.typeOf(42L))
        assertEquals("String", EPLRuntime.typeOf("hello"))
        assertEquals("Boolean", EPLRuntime.typeOf(true))
        assertEquals("Nothing", EPLRuntime.typeOf(null))
    }}

    @Test
    fun testLength() {{
        assertEquals(5, EPLRuntime.length("hello"))
        assertEquals(3, EPLRuntime.length(listOf(1, 2, 3)))
        assertEquals(0, EPLRuntime.length(null))
    }}

    @Test
    fun testMath() {{
        assertEquals(8.0, EPLRuntime.power(2.0, 3.0), 0.001)
        assertEquals(5.0, EPLRuntime.sqrt(25.0), 0.001)
        assertEquals(3.0, EPLRuntime.floor(3.7), 0.001)
        assertEquals(4.0, EPLRuntime.ceil(3.2), 0.001)
    }}

    @Test
    fun testStringHelpers() {{
        assertEquals("HELLO", EPLRuntime.uppercase("hello"))
        assertEquals("hello", EPLRuntime.lowercase("HELLO"))
        assertEquals("hello", EPLRuntime.trim("  hello  "))
        assertTrue(EPLRuntime.contains("hello world", "world"))
        assertTrue(EPLRuntime.startsWith("hello", "hel"))
        assertTrue(EPLRuntime.endsWith("hello", "llo"))
    }}
}}
'''

    def _instrumented_test_kt(self):
        return f'''package {self.package}

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.ext.junit.rules.ActivityScenarioRule
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withId

@RunWith(AndroidJUnit4::class)
class MainActivityTest {{
    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    @Test
    fun activityLaunches() {{
        // Verify the activity launches without crashing
        activityRule.scenario.onActivity {{ activity ->
            assert(activity != null)
        }}
    }}
}}
'''


def transpile_to_kotlin(program: ast.Program, package="com.epl.app") -> str:
    """Convenience: transpile EPL AST to Kotlin."""
    return KotlinGenerator(package).generate(program)


def generate_android_project(program: ast.Program, output_dir: str,
                              app_name="EPLApp", package="com.epl.app"):
    """Convenience: generate a full Android project from EPL."""
    gen = AndroidProjectGenerator(app_name, package)
    return gen.generate(program, output_dir)
