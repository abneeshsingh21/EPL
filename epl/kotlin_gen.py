"""
EPL Kotlin Code Generator (v3.0)
Transpiles EPL AST to Kotlin source code targeting Android/JVM.
Supports: variables, functions, classes, loops, conditions, string/list methods,
collections, lambdas, enums, Android Activity generation, GUI widget generation,
event binding, dynamic layouts, navigation, Jetpack Compose, symbol table with
type tracking, visibility modifiers, companion objects, and coroutines.
"""

import os
import re
import shutil
from pathlib import Path

from epl import _debug_log
from epl import ast_nodes as ast

ANDROID_GRADLE_WRAPPER_VERSION = '8.2.1'
ANDROID_GRADLE_PLUGIN_VERSION = '8.2.0'
ANDROID_KOTLIN_VERSION = '1.9.22'
ANDROID_TEMPLATE_ROOT = Path(__file__).resolve().parent / 'templates' / 'android'


class SymbolTable:
    """Scoped symbol table for tracking variable/function/class types."""

    def __init__(self, parent=None):
        self.parent = parent
        self.symbols = {}  # name -> kotlin type string
        self.functions = {}  # name -> {'params': [...], 'return': str}
        self.classes = {}  # name -> {'properties': {name: type}, 'methods': {name: sig}, 'parent': str|None}
        self.declared = (
            set()
        )  # names actually emitted as `var` (distinct from pre-registered types)

    def define(self, name, kt_type):
        self.symbols[name] = kt_type

    def mark_declared(self, name):
        self.declared.add(name)

    def is_declared(self, name):
        if name in self.declared:
            return True
        return self.parent.is_declared(name) if self.parent else False

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

    def __init__(self, package_name='com.epl.app'):
        self.package = package_name
        self.indent = 0
        self.output = []
        self.in_class = None
        self.class_properties = {}  # name -> kotlin type (upgraded from set)
        self._current_ret_type = None  # enclosing function's Kotlin return type
        self.imports = set()
        self.widgets = []  # collected GUI widgets for layout XML generation
        self.event_bindings = []  # collected event bindings
        self.widget_counter = 0
        self.symbols = SymbolTable()  # root symbol table

    # ─── Public API ──────────────────────────────────────

    def generate(self, program: ast.Program, include_runtime=False) -> str:
        """Generate Kotlin source from EPL AST.

        include_runtime appends the EPLRuntime shim so the output is a single
        self-contained, compilable file (the plain `epl kotlin` transpile). The
        Android project path leaves it False: that project bundles its own
        EPLRuntime.kt, so appending here would duplicate the object.
        """
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
        # Top-level constants must live at file scope: inlined stdlib functions
        # (also emitted at file scope) close over them, so a constant buried inside
        # `fun main()` would be an unresolved reference from those functions.
        consts = [s for s in stmts if isinstance(s, ast.ConstDeclaration)]
        other = [
            s
            for s in stmts
            if not isinstance(s, (ast.ClassDef, ast.FunctionDef, ast.EnumDef, ast.ConstDeclaration))
        ]

        for e in enums:
            self._emit_enum(e)
        for c in consts:
            self._emit_stmt(c)
        for c in classes:
            self._emit_class(c)
        for f in functions:
            self._emit_function(f)

        if other:
            self._line('fun main() {')
            self.indent += 1
            self._declare_hoisted(other)
            for s in other:
                self._emit_stmt(s)
            self.indent -= 1
            self._line('}')

        header = f'package {self.package}\n\n'
        if self.imports:
            header += '\n'.join(f'import {i}' for i in sorted(self.imports)) + '\n\n'
        body = header + '\n'.join(self.output)
        if include_runtime:
            body += self._console_runtime_suffix(body)
        return body

    def _console_runtime_suffix(self, body):
        """Append the EPLRuntime shim for the console/JVM target when referenced.

        The Android target bundles EPLRuntime as its own project file; a plain
        `epl kotlin` transpile is a single self-contained source, so the runtime
        the generated code calls into must travel with it. Emitted only when the
        body actually references EPLRuntime/JsonMini, so trivial programs stay lean.
        The shim carries its own `package` line, which we drop — the file already
        declares one — keeping a single package declaration.
        """
        if 'EPLRuntime' not in body:
            return ''
        from epl.kotlin_runtime import console_runtime

        shim = console_runtime(self.package)
        _, _, after = shim.partition('\n\n')
        return '\n\n' + after

    def _register_symbols(self, stmts):
        """Pre-pass: register functions, classes, enums for type lookups."""
        for s in stmts:
            if isinstance(s, ast.FunctionDef):
                ret = self._infer_return_type(s)
                plain, _ = self._split_rest(s.params)
                param_types = [(p[0], self._infer_param_type(p)) for p in plain]
                self.symbols.define_function(s.name, param_types, ret)
            elif isinstance(s, ast.ClassDef):
                props = {}
                methods = {}
                for item in s.body:
                    if isinstance(item, ast.VarDeclaration):
                        props[item.name] = self._infer_kotlin_type(item.value)
                    elif isinstance(item, ast.FunctionDef) and item.name != 'init':
                        methods[item.name] = self._infer_return_type(item)
                self.symbols.define_class(
                    s.name, {'properties': props, 'methods': methods, 'parent': s.parent}
                )
            elif isinstance(s, ast.EnumDef):
                self.symbols.define(s.name, s.name)
            elif isinstance(s, ast.VarDeclaration):
                self.symbols.define(s.name, self._infer_kotlin_type(s.value))
            elif isinstance(s, ast.ConstDeclaration):
                self.symbols.define(s.name, self._infer_kotlin_type(s.value))

    def generate_android_activity(self, program: ast.Program, activity_name='MainActivity') -> str:
        """Generate an Android Activity from EPL AST with dynamic UI."""
        self.output = []
        self.widgets = []
        self.event_bindings = []
        self.imports = {
            'android.os.Bundle',
            'androidx.appcompat.app.AppCompatActivity',
            'android.widget.*',
            'android.view.View',
            'android.widget.Toast',
            'android.view.ViewGroup',
            'android.widget.LinearLayout',
            'android.widget.ScrollView',
        }

        # First pass: collect GUI nodes for layout XML
        self._register_symbols(program.statements)
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
            # Logic + local functions BEFORE event bindings so handlers are in scope
            self._emit_program_logic(program.statements)
            self._line('')
            self._emit_event_bindings()
            self._line('')
            self._line('scrollView.addView(mainLayout)')
            self._line('setContentView(scrollView)')
        else:
            self._line('setContentView(R.layout.activity_main)')
            self._line('')
            self._emit_program_logic(program.statements)

        self.indent -= 1
        self._line('}')

        self.indent -= 1
        self._line('}')

        # File-level enum definitions (hoisted out of the activity — Kotlin has
        # no local enum classes).
        for s in program.statements:
            if isinstance(s, ast.EnumDef):
                self._line('')
                self._emit_enum(s)

        header = f'package {self.package}\n\n'
        header += '\n'.join(f'import {i}' for i in sorted(self.imports)) + '\n\n'
        return header + '\n'.join(self.output)

    def generate_compose_activity(self, program: ast.Program, activity_name='MainActivity') -> str:
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

        if wtype == 'heading':
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or ""}"'
            tag = props.get('tag', 'heading')
            self.imports.add('androidx.compose.ui.text.font.FontWeight')
            if tag in ('h1', 'heading'):
                self._line(
                    f'Text(text = {text_str}, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)'
                )
            elif tag == 'h2':
                self._line(
                    f'Text(text = {text_str}, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)'
                )
            else:
                self._line(
                    f'Text(text = {text_str}, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)'
                )
        elif wtype == 'link':
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or "Link"}"'
            href = props.get('href', props.get('to', ''))
            self.imports.add('androidx.compose.ui.text.style.TextDecoration')
            self._line(
                f'Text(text = {text_str}, color = MaterialTheme.colorScheme.primary, textDecoration = TextDecoration.Underline)'
            )
        elif wtype == 'button':
            handler = w.get('action')
            handler_str = f'{{ {self._expr(handler).strip(chr(34))}() }}' if handler else '{}'
            text_str = (
                self._expr(text) if text and hasattr(text, 'line') else f'"{text or "Button"}"'
            )
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
                self._line('OutlinedTextField(')
            else:
                self._line('TextField(')
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
            text_str = (
                self._expr(text) if text and hasattr(text, 'line') else f'"{text or "Check"}"'
            )
            self._line(f'var {var_name}Checked by remember {{ mutableStateOf(false) }}')
            self._line('Row(verticalAlignment = Alignment.CenterVertically) {')
            self.indent += 1
            self._line(
                f'Checkbox(checked = {var_name}Checked, onCheckedChange = {{ {var_name}Checked = it }})'
            )
            self._line(f'Text({text_str})')
            self.indent -= 1
            self._line('}')
        elif wtype == 'slider':
            var_name = w.get('id', 'slider')
            max_val = props.get('max', 100)
            self._line(f'var {var_name}Value by remember {{ mutableStateOf(0f) }}')
            self._line(
                f'Slider(value = {var_name}Value, onValueChange = {{ {var_name}Value = it }}, valueRange = 0f..{max_val}f)'
            )
        elif wtype == 'progress':
            self._line('LinearProgressIndicator(modifier = Modifier.fillMaxWidth())')
        elif wtype == 'image':
            self.imports.add('androidx.compose.foundation.Image')
            self.imports.add('androidx.compose.ui.res.painterResource')
            self._line('// Image placeholder — replace R.drawable.placeholder with actual resource')
            self._line(
                '// Image(painter = painterResource(R.drawable.placeholder), contentDescription = null)'
            )
        else:
            text_str = self._expr(text) if text and hasattr(text, 'line') else f'"{text or wtype}"'
            self._line(f'Text(text = {text_str})')

    def _is_gui_node(self, node):
        """Check if a node is a GUI-related AST node."""
        return isinstance(
            node,
            (
                ast.WindowCreate,
                ast.WidgetAdd,
                ast.LayoutBlock,
                ast.BindEvent,
                ast.DialogShow,
                ast.MenuDef,
                ast.CanvasDraw,
                ast.PageDef,
                ast.HtmlElement,
                # v6.0: Style & Layout nodes
                ast.StyleDef,
                ast.StyledElement,
                ast.LayoutContainer,
                ast.ComponentDef,
                ast.ComponentUse,
                ast.AnimateDef,
                ast.ResponsiveBlock,
                ast.TransitionDef,
                # v6.1: 3D & Canvas
                ast.Scene3D,
                ast.DrawCommand,
            ),
        )

    def _collect_gui_nodes(self, stmts):
        """First pass: collect all widgets and event bindings."""
        for s in stmts:
            if isinstance(s, ast.WindowCreate):
                self._collect_gui_nodes(s.body)
            elif isinstance(s, ast.PageDef):
                self._collect_page_elements(s)
            elif isinstance(s, ast.WidgetAdd):
                wid = s.name or f'widget_{self.widget_counter}'
                self.widget_counter += 1
                self.widgets.append(
                    {
                        'id': wid,
                        'type': s.widget_type.lower(),
                        'text': s.text,
                        'properties': s.properties,
                        'action': s.action,
                    }
                )
            elif isinstance(s, ast.LayoutBlock):
                self._collect_gui_nodes(s.children)
            elif isinstance(s, ast.BindEvent):
                self.event_bindings.append(
                    {
                        'widget': s.widget_name,
                        'event': s.event_type,
                        'handler': s.handler,
                    }
                )

    def _collect_page_elements(self, page_node):
        """Convert PageDef/HtmlElement nodes to Compose widget entries."""
        for elem in page_node.elements:
            if isinstance(elem, ast.HtmlElement):
                tag = elem.tag.lower()
                content = elem.content
                if tag in ('heading', 'h1', 'h2', 'h3'):
                    self.widget_counter += 1
                    self.widgets.append(
                        {
                            'id': f'heading_{self.widget_counter}',
                            'type': 'heading',
                            'text': content,
                            'properties': {'tag': tag},
                            'action': None,
                        }
                    )
                elif tag in ('text', 'paragraph', 'p'):
                    self.widget_counter += 1
                    self.widgets.append(
                        {
                            'id': f'text_{self.widget_counter}',
                            'type': 'label',
                            'text': content,
                            'properties': {},
                            'action': None,
                        }
                    )
                elif tag == 'button':
                    self.widget_counter += 1
                    action = elem.attributes.get('action')
                    self.widgets.append(
                        {
                            'id': f'button_{self.widget_counter}',
                            'type': 'button',
                            'text': content,
                            'properties': {},
                            'action': action,
                        }
                    )
                elif tag in ('input', 'textbox'):
                    self.widget_counter += 1
                    self.widgets.append(
                        {
                            'id': f'input_{self.widget_counter}',
                            'type': 'input',
                            'text': content,
                            'properties': elem.attributes,
                            'action': None,
                        }
                    )
                elif tag in ('link', 'a'):
                    self.widget_counter += 1
                    self.widgets.append(
                        {
                            'id': f'link_{self.widget_counter}',
                            'type': 'link',
                            'text': content,
                            'properties': elem.attributes,
                            'action': None,
                        }
                    )
                elif tag == 'image':
                    self.widget_counter += 1
                    self.widgets.append(
                        {
                            'id': f'image_{self.widget_counter}',
                            'type': 'image',
                            'text': content,
                            'properties': elem.attributes,
                            'action': None,
                        }
                    )
                else:
                    self.widget_counter += 1
                    self.widgets.append(
                        {
                            'id': f'elem_{self.widget_counter}',
                            'type': 'label',
                            'text': content,
                            'properties': {},
                            'action': None,
                        }
                    )

    def _android_widget_class(self, wtype):
        """Map EPL widget type to Android widget class."""
        mapping = {
            'button': 'Button',
            'label': 'TextView',
            'input': 'EditText',
            'textarea': 'EditText',
            'checkbox': 'CheckBox',
            'dropdown': 'Spinner',
            'slider': 'SeekBar',
            'progress': 'ProgressBar',
            'image': 'ImageView',
            'listbox': 'ListView',
            'canvas': 'View',
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
                action_name = (
                    self._expr(w['action']) if hasattr(w['action'], 'line') else str(w['action'])
                )
                self._line(f'{wid}.setOnClickListener {{ {action_name.strip(chr(34))}() }}')

            self._line(f'mainLayout.addView({wid})')
            self._line('')

    def _emit_event_bindings(self):
        """Generate event binding code."""
        for binding in self.event_bindings:
            widget = binding['widget']
            event = binding['event']
            handler_expr = (
                self._expr(binding['handler'])
                if hasattr(binding['handler'], 'line')
                else str(binding['handler'])
            )
            handler_name = handler_expr.strip('"')

            if event in ('click', 'onClick'):
                self._line(f'{widget}.setOnClickListener {{ {handler_name}() }}')
            elif event in ('change', 'onTextChanged'):
                self.imports.add('android.text.TextWatcher')
                self.imports.add('android.text.Editable')
                self._line(f'{widget}.addTextChangedListener(object : TextWatcher {{')
                self.indent += 1
                self._line(
                    'override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}'
                )
                self._line(
                    'override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {'
                )
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

    def _emit_program_logic(self, stmts):
        """Emit non-GUI top-level statements in source order.

        FunctionDefs become local functions inside onCreate (single emission —
        no duplicate class-level copies), so they close over locals such as a
        `db` handle and are in scope for event-binding lambdas emitted after.
        """
        logic = [s for s in stmts if not isinstance(s, ast.EnumDef) and not self._is_gui_node(s)]
        self._declare_hoisted(logic)
        for s in logic:
            self._emit_stmt(s)

    # ─── Helper ──────────────────────────────────────────

    def _line(self, text):
        self.output.append('    ' * self.indent + text)

    # ─── Statement Dispatch ──────────────────────────────

    def _emit_stmt(self, node):
        if node is None:
            return
        if isinstance(node, ast.VarDeclaration):
            self._emit_var_decl(node)
        elif isinstance(node, ast.VarAssignment):
            self._emit_var_assign(node)
        elif isinstance(node, ast.PrintStatement):
            self._emit_print(node)
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
        elif isinstance(node, ast.MethodCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.PropertySet):
            recv = self._infer_kotlin_type(node.obj)
            if 'Map' in recv:
                key = self._kotlin_str_literal(node.property_name)
                self._line(f'{self._expr(node.obj)}[{key}] = {self._expr(node.value)}')
            else:
                self._line(
                    f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)}'
                )
        elif isinstance(node, ast.IndexSet):
            self._line(
                f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)}'
            )
        elif isinstance(node, ast.AugmentedAssignment):
            self._line(f'{self._safe_ident(node.name)} {node.operator} {self._expr(node.value)}')
        elif isinstance(node, ast.ThrowStatement):
            # Interpreter parity: a thrown value surfaces in Catch as the string
            # "EPL Runtime Error on line N: <msg>".
            self._line(
                f'throw RuntimeException("EPL Runtime Error on line {node.line}: " '
                f'+ EPLRuntime.toText({self._expr(node.expression)}))'
            )
        elif isinstance(node, ast.ConstDeclaration):
            kt_type = self._infer_kotlin_type(node.value)
            self.symbols.define(node.name, kt_type)
            self._line(f'val {self._safe_ident(node.name)}: {kt_type} = {self._expr(node.value)}')
        elif isinstance(node, ast.EnumDef):
            self._emit_enum(node)
        elif isinstance(node, ast.InputStatement):
            self._emit_input(node)
        elif isinstance(node, ast.ExitStatement):
            self.imports.add('kotlin.system.exitProcess')
            self._line('exitProcess(0)')
        elif isinstance(node, ast.AssertStatement):
            # Not Kotlin's assert(): that's disabled on the JVM without -ea, so it
            # would silently pass. Explicit check, interpreter-formatted message.
            self._line(
                f'if (!EPLRuntime.eplTruthy({self._expr(node.expression)})) '
                f'throw RuntimeException("EPL Runtime Error on line {node.line}: '
                f'Assertion failed on line {node.line}.")'
            )
        # GUI nodes - emit as comments in non-Android context
        elif isinstance(node, ast.WindowCreate):
            self._emit_window_comment(node)
        elif isinstance(node, ast.WidgetAdd):
            pass  # handled by Android activity generator
        elif isinstance(node, ast.LayoutBlock):
            pass
        elif isinstance(node, ast.BindEvent):
            pass
        elif isinstance(node, ast.DialogShow):
            self._emit_dialog(node)
        elif isinstance(node, ast.CanvasDraw):
            pass
        elif isinstance(node, ast.AsyncFunctionDef):
            self._emit_async_function(node)
        elif isinstance(node, ast.SuperCall):
            self._emit_super_call(node)
        # v4 AST node support
        elif isinstance(node, ast.InterfaceDefNode):
            self._emit_interface(node)
        elif isinstance(node, ast.ModuleDef):
            self._emit_module(node)
        elif isinstance(node, ast.TryCatchFinally):
            self._emit_try_catch_finally(node)
        elif isinstance(node, ast.ExportStatement):
            self._emit_stmt(node.statement)
        elif isinstance(node, ast.VisibilityModifier):
            self._emit_visibility(node)
        elif isinstance(node, ast.StaticMethodDef):
            self._emit_static_method(node)
        elif isinstance(node, ast.AbstractMethodDef):
            self._emit_abstract_method(node)
        elif isinstance(node, ast.YieldStatement):
            self._emit_yield(node)
        elif isinstance(node, ast.DestructureAssignment):
            self._emit_destructure(node)
        elif isinstance(node, ast.ModuleAccess):
            self._line(f'{self._expr(node)}')
        # v6.0: Style & Layout System (Compose)
        elif isinstance(node, ast.StyleDef):
            self._emit_style_def_compose(node)
        elif isinstance(node, ast.StyledElement):
            self._emit_styled_element_compose(node)
        elif isinstance(node, ast.LayoutContainer):
            self._emit_layout_container_compose(node)
        elif isinstance(node, ast.ComponentDef):
            self._emit_component_def_compose(node)
        elif isinstance(node, ast.ComponentUse):
            self._emit_component_use_compose(node)
        elif isinstance(node, ast.AnimateDef):
            self._emit_animate_def_compose(node)
        # v6.1: 3D & Canvas
        elif isinstance(node, ast.Scene3D):
            self._emit_scene_3d_compose(node)
        elif isinstance(node, ast.DrawCommand):
            self._emit_draw_command_compose(node)
        elif isinstance(node, ast.FileWrite):
            # Content goes through toText: the interpreter writes the
            # EPL-formatted value (5.0 prints as 5), not Kotlin's toString.
            self._line(
                f'EPLRuntime.fileWrite({self._expr(node.filepath)}, '
                f'EPLRuntime.toText({self._expr(node.content)}))'
            )
        elif isinstance(node, ast.FileAppend):
            # The `Append ... to file` statement adds a trailing newline
            # (interpreter parity); the file_append builtin does not.
            self._line(
                f'EPLRuntime.fileAppend({self._expr(node.filepath)}, '
                f'EPLRuntime.toText({self._expr(node.content)}) + "\\n")'
            )
        elif isinstance(node, (ast.ResponsiveBlock, ast.TransitionDef, ast.KeyframeDef)):
            pass  # CSS-specific, no Kotlin equivalent

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
        # catch_clauses entries are (error_type, error_var, body) tuples. Typed
        # EPL error classes don't map to JVM exception types, so all clauses
        # collapse into one Exception catch; the first clause's var binds the
        # MESSAGE string (interpreter parity), matching _emit_try_catch.
        if node.catch_clauses:
            _, error_var, body = node.catch_clauses[0]
            var = self._safe_ident(error_var or 'e')
            self._line('} catch (__exc: Exception) {')
            self.indent += 1
            self._line(f'val {var}: String = __exc.message ?: __exc.toString()')
            self.symbols.define(error_var or 'e', 'String')
            for s in body:
                self._emit_stmt(s)
            self.indent -= 1
        else:
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
            indent_str = line[: len(line) - len(stripped)]
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
        if ret_type != 'Unit' and not self._always_returns(node.body):
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
        if self.in_class and node.name in self.class_properties:
            self._line(f'this.{node.name} = {self._expr(node.value)}')
            return
        if self.symbols.is_declared(node.name):
            val = self._coerce_assign(node.value, self.symbols.lookup(node.name))
            self._line(f'{self._safe_ident(node.name)} = {val}')
            return
        kt_type = self._widen_decl_type(node.value, self._infer_kotlin_type(node.value))
        self.symbols.define(node.name, kt_type)
        self.symbols.mark_declared(node.name)
        self._line(f'var {self._safe_ident(node.name)}: {kt_type} = {self._expr(node.value)}')

    def _widen_decl_type(self, value, kt_type) -> str:
        """Widen a `var` declared type so later dynamic reassignments type-check.
        A bare `Any` local in EPL is dynamic and may be reassigned to a nullable
        value (e.g. a lambda-call result), so it must be declared `Any?`. An empty
        list literal is similarly widened to hold nullable/dynamic elements."""
        if kt_type == 'Any':
            return 'Any?'
        # An empty list gets `add`ed dynamic (possibly null) values later.
        if kt_type == 'MutableList<Any>' and isinstance(value, ast.ListLiteral) and not value.elements:
            return 'MutableList<Any?>'
        return kt_type

    def _coerce_assign(self, value, decl_type) -> str:
        """Emit an assignment RHS, coercing a dynamic/Int value into a typed var.
        Kotlin won't auto-promote Int→Double, nor accept Any where Int/Double/String
        is declared (list-element / map-lookup reassignments)."""
        val = self._expr(value)
        vt = self._infer_kotlin_type(value)
        if decl_type in ('Double', 'Float'):
            if vt in ('Int', 'Long'):
                return f'({val}).toDouble()'
            if vt in ('Any', 'Any?'):
                return f'({val} as Number).toDouble()'
        elif decl_type in ('Int', 'Long') and vt in ('Any', 'Any?'):
            return f'({val} as Number).toInt()'
        elif decl_type == 'String' and vt in ('Any', 'Any?'):
            return f'({val}).toString()'
        return val

    def _emit_var_assign(self, node):
        # `Set x to ...` in EPL is create-or-update. A class property assigns
        # through `this`; an already-declared local is a bare reassignment;
        # otherwise this is the first sight of the name and must declare it,
        # else Kotlin reports an unresolved reference.
        if self.in_class and node.name in self.class_properties:
            self._line(f'this.{node.name} = {self._expr(node.value)}')
            return
        if self.symbols.is_declared(node.name):
            val = self._coerce_assign(node.value, self.symbols.lookup(node.name))
            self._line(f'{self._safe_ident(node.name)} = {val}')
            return
        kt_type = self._infer_kotlin_type(node.value)
        self.symbols.define(node.name, kt_type)
        self.symbols.mark_declared(node.name)
        self._line(f'var {self._safe_ident(node.name)}: {kt_type} = {self._expr(node.value)}')

    # Nodes that open a new variable scope — hoisting must not descend into them.
    _SCOPE_BOUNDARY = tuple(
        c
        for c in (
            getattr(ast, n, None)
            for n in (
                'FunctionDef',
                'AsyncFunctionDef',
                'ClassDef',
                'GenericClassDef',
                'LambdaExpression',
                'ComponentDef',
                'ModuleDef',
                'InterfaceDefNode',
            )
        )
        if c is not None
    )

    def _walk_scope(self, node):
        """Yield node and every descendant in the same variable scope."""
        yield node
        if isinstance(node, self._SCOPE_BOUNDARY):
            return
        for v in vars(node).values():
            if isinstance(v, ast.ASTNode):
                yield from self._walk_scope(v)
            elif isinstance(v, list):
                for it in v:
                    if isinstance(it, ast.ASTNode):
                        yield from self._walk_scope(it)

    def _hoist_locals(self, stmts, skip_names=()):
        """Names whose first assignment is nested inside a block (try/if/loop) yet
        which are used in another top-level region. EPL variables are function-
        scoped, so such a name must be declared at scope top or Kotlin's block
        scoping makes it an unresolved reference outside the block.

        `skip_names` are already-in-scope names (e.g. params) never to redeclare.
        Returns an ordered list of (name, kt_type).
        """
        first_value = {}
        first_nested = {}
        first_topidx = {}
        ref_topidx = {}
        for i, top in enumerate(stmts):
            if isinstance(top, self._SCOPE_BOUNDARY):
                continue
            for node in self._walk_scope(top):
                if isinstance(node, (ast.VarAssignment, ast.VarDeclaration)):
                    nm = node.name
                    ref_topidx.setdefault(nm, set()).add(i)
                    if nm not in first_value:
                        first_value[nm] = node.value
                        first_nested[nm] = node is not top
                        first_topidx[nm] = i
                elif isinstance(node, ast.Identifier):
                    ref_topidx.setdefault(node.name, set()).add(i)
        hoisted = []
        for nm, val in first_value.items():
            if not first_nested.get(nm):
                continue
            if not (ref_topidx.get(nm, set()) - {first_topidx[nm]}):
                continue
            if nm in skip_names:
                continue
            if self.in_class and nm in self.class_properties:
                continue
            if self.symbols.is_declared(nm):
                continue
            hoisted.append((nm, self._infer_kotlin_type(val)))
        return hoisted

    def _declare_hoisted(self, stmts, skip_names=()):
        """Emit scope-top `var` declarations for function-scoped locals first seen
        inside a nested block, so later out-of-block uses resolve."""
        for nm, kt in self._hoist_locals(stmts, skip_names):
            default = self._zero_value(kt)
            decl_type = kt if default != 'null' or kt.endswith('?') else f'{kt}?'
            self.symbols.define(nm, decl_type)
            self.symbols.mark_declared(nm)
            self._line(f'var {nm}: {decl_type} = {default}')

    def _reassigned_names(self, stmts):
        """Names that are targets of an assignment anywhere in the body.

        Kotlin function parameters are immutable `val`; an EPL body that reassigns
        a parameter (e.g. `n = n / 2`) needs a mutable local shadow, else Kotlin
        rejects it as 'val cannot be reassigned'.
        """
        names = set()
        for top in stmts:
            for node in self._walk_scope(top):
                if isinstance(node, (ast.VarAssignment, ast.VarDeclaration)):
                    names.add(node.name)
        return names

    def _shadow_reassigned_params(self, param_types, body):
        """Emit `var p = p` shadows for parameters the body reassigns.

        Returns the set of shadowed names. Each becomes a mutable local declared
        at function top, so subsequent reassignments compile and later reads see
        the updated value (EPL parameters are mutable locals, Kotlin's are not).
        """
        reassigned = self._reassigned_names(body)
        shadowed = set()
        for name, pt in param_types:
            if name in reassigned:
                self._line(f'var {self._safe_ident(name)} = {self._safe_ident(name)}')
                self.symbols.mark_declared(name)
                shadowed.add(name)
        return shadowed

    @staticmethod
    def _zero_value(kt):
        if kt in ('Int', 'Long'):
            return '0'
        if kt in ('Double', 'Float'):
            return '0.0'
        if kt == 'Boolean':
            return 'false'
        if kt == 'String':
            return '""'
        if kt.startswith('MutableList'):
            return 'mutableListOf()'
        if kt.startswith('MutableMap'):
            return 'mutableMapOf()'
        return 'null'

    def _emit_print(self, node):
        expr = self._expr(node.expression)
        # A String literal/expression prints directly; anything whose static type
        # is dynamic (Any?) hits Kotlin's println overload-resolution ambiguity and
        # also wouldn't match EPL's display formatting (nothing, whole decimals) —
        # route those through EPLRuntime.toText so output is a well-formed String.
        expr_type = self._infer_kotlin_type(node.expression)
        if expr_type == 'String':
            self._line(f'println({expr})')
        else:
            self._line(f'println(EPLRuntime.toText({expr}))')

    def _emit_input(self, node):
        if node.prompt:
            self._line(f'print({self._expr(node.prompt)})')
        if self.symbols.is_declared(node.variable_name):
            self._line(f'{node.variable_name} = readLine() ?: ""')
        else:
            self.symbols.define(node.variable_name, 'String')
            self.symbols.mark_declared(node.variable_name)
            self._line(f'var {node.variable_name} = readLine() ?: ""')

    def _cond(self, node):
        """Emit a boolean condition. A condition whose static type isn't Boolean
        (e.g. a dynamic lambda-call result typed Any?) is wrapped in EPLRuntime.truthy
        so Kotlin — which requires a Boolean here — accepts it with EPL semantics."""
        expr = self._expr(node)
        if self._infer_kotlin_type(node) == 'Boolean':
            return expr
        return f'EPLRuntime.truthy({expr})'

    def _emit_if(self, node):
        self._line(f'if ({self._cond(node.condition)}) {{')
        self.indent += 1
        for s in node.then_body:
            self._emit_stmt(s)
        self.indent -= 1
        if node.else_body:
            self._line('} else {')
            self.indent += 1
            for s in node.else_body:
                self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    def _emit_while(self, node):
        self._line(f'while ({self._cond(node.condition)}) {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_repeat(self, node):
        self._line(f'repeat({self._expr(node.count)}) {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_for_range(self, node):
        start = self._range_bound(node.start)
        end = self._range_bound(node.end)
        step = self._expr(node.step) if node.step else None
        loop_var = self._safe_ident(node.var_name)
        if step:
            try:
                step_val = int(step)
                if step_val < 0:
                    abs_step = abs(step_val)
                    if abs_step == 1:
                        self._line(f'for ({loop_var} in {start} downTo {end}) {{')
                    else:
                        self._line(
                            f'for ({loop_var} in {start} downTo {end} step {abs_step}) {{'
                        )
                elif step_val != 1:
                    self._line(f'for ({loop_var} in {start}..{end} step {step}) {{')
                else:
                    self._line(f'for ({loop_var} in {start}..{end}) {{')
            except (ValueError, TypeError):
                self._line(f'for ({loop_var} in {start}..{end} step {step}) {{')
        else:
            self._line(f'for ({loop_var} in {start}..{end}) {{')
        # Register the loop variable so a reassignment inside the body is a
        # bare assignment, not a spurious `var` re-declaration.
        self.symbols.define(node.var_name, 'Int')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _range_bound(self, node) -> str:
        """A `From a To b` range bound must be Int; coerce a dynamic value."""
        code = self._expr(node)
        if self._infer_kotlin_type(node) in ('Any', 'Any?'):
            return f'({code} as Number).toInt()'
        return code

    def _emit_for_each(self, node):
        # Element type of the iterable, falling back to Any for dynamic values.
        iter_type = self._infer_kotlin_type(node.iterable)
        iterable = self._expr(node.iterable)
        if iter_type.startswith(('MutableList<', 'List<')):
            elem_type = iter_type[iter_type.index('<') + 1 : -1]
        elif iter_type.startswith(('MutableMap<', 'Map<')):
            # EPL iterates a map over its keys, not its entries.
            iterable = f'{iterable}.keys'
            elem_type = 'String'
        elif iter_type == 'String':
            # EPL iterates a string as 1-char strings, not Kotlin Chars.
            iterable = f'{iterable}.map {{ it.toString() }}'
            elem_type = 'String'
        else:
            # Dynamic value (Any): a list iterates its items, a string its chars.
            iterable = f'EPLRuntime.iterate({iterable})'
            elem_type = 'Any'
        self._line(f'for ({self._safe_ident(node.var_name)} in {iterable}) {{')
        self.symbols.define(node.var_name, elem_type)
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    @staticmethod
    def _split_rest(params):
        """Split params into (plain tuple-params, trailing RestParameter or None).

        EPL allows one trailing `rest` parameter (varargs); it arrives as a
        RestParameter node, not a (name, type, default) tuple, so every code
        path that indexes params must go through this split.
        """
        if params and isinstance(params[-1], ast.RestParameter):
            return params[:-1], params[-1]
        return params, None

    def _emit_function(self, node):
        # Filter out 'self' param (not needed in Kotlin)
        plain, rest = self._split_rest(node.params)
        real_params = [p for p in plain if p[0] != 'self']
        param_types = self._resolve_param_types(real_params, node.body)
        # Seed the signature from non-recursive returns first so a recursive
        # self-call resolves to a concrete type, then refine with all paths.
        seed_ret = self._infer_return_type(node, param_types, skip_recursive=True)
        self.symbols.define_function(node.name, param_types, seed_ret)
        ret_type = self._infer_return_type(node, param_types)
        self.symbols.define_function(node.name, param_types, ret_type)
        params = ', '.join(
            self._format_param_typed(p, pt) for p, (_, pt) in zip(real_params, param_types)
        )
        if rest is not None:
            rest_decl = f'vararg {self._safe_ident(rest.name)}: Any?'
            params = f'{params}, {rest_decl}' if params else rest_decl
        self._line(f'fun {node.name}({params}): {ret_type} {{')
        self.indent += 1
        prev_symbols = self.symbols
        prev_ret = getattr(self, '_current_ret_type', None)
        self._current_ret_type = ret_type
        self.symbols = self.symbols.child()
        for name, pt in param_types:
            self.symbols.define(name, pt)
        if rest is not None:
            # EPL sees a rest parameter as a list; Kotlin's vararg is an Array.
            # Shadow it with a list so list methods/iteration match interpreter
            # semantics inside the body.
            self._line(f'val {self._safe_ident(rest.name)} = {self._safe_ident(rest.name)}.toMutableList()')
            self.symbols.define(rest.name, 'MutableList<Any?>')
        hoist_skip = {n for n, _ in param_types}
        if rest is not None:
            hoist_skip.add(rest.name)
        shadowed = self._shadow_reassigned_params(param_types, node.body)
        self._declare_hoisted(node.body, hoist_skip - shadowed)
        for s in node.body:
            self._emit_stmt(s)
        if ret_type != 'Unit' and not self._always_returns(node.body):
            self._line('return Unit')
        self.symbols = prev_symbols
        self._current_ret_type = prev_ret
        self.indent -= 1
        self._line('}')

    def _always_returns(self, body) -> bool:
        """True if every control-flow path through `body` ends in a return/throw.
        Recurses into if/else so a value-returning function whose returns are all
        nested in branches isn't given a spurious trailing `return Unit`."""
        if not body:
            return False
        last = body[-1]
        if isinstance(last, (ast.ReturnStatement, ast.ThrowStatement)):
            return True
        if isinstance(last, ast.IfStatement):
            return (
                bool(last.else_body)
                and self._always_returns(last.then_body)
                and self._always_returns(last.else_body)
            )
        return False

    def _emit_class_method(self, node):
        """Emit a method inside a class, with this. prefixing for properties."""
        real_params = [p for p in node.params if p[0] != 'self']
        param_types = self._resolve_param_types(real_params, node.body)
        ret_type = self._infer_return_type(node, param_types)
        modifier = 'open ' if self.in_class else ''
        params = ', '.join(
            self._format_param_typed(p, pt) for p, (_, pt) in zip(real_params, param_types)
        )
        self._line(f'{modifier}fun {node.name}({params}): {ret_type} {{')
        self.indent += 1
        prev_symbols = self.symbols
        prev_ret = getattr(self, '_current_ret_type', None)
        self._current_ret_type = ret_type
        self.symbols = self.symbols.child()
        for name, pt in param_types:
            self.symbols.define(name, pt)
        shadowed = self._shadow_reassigned_params(param_types, node.body)
        self._declare_hoisted(node.body, {n for n, _ in param_types} - shadowed)
        for s in node.body:
            self._emit_stmt(s)
        if ret_type != 'Unit' and not self._always_returns(node.body):
            self._line('return Unit')
        self.symbols = prev_symbols
        self._current_ret_type = prev_ret
        self.indent -= 1
        self._line('}')

    def _infer_kotlin_type(self, node) -> str:
        """Infer Kotlin type from an AST value node using symbol table."""
        if node is None:
            return 'Any?'
        if isinstance(node, ast.Literal):
            if isinstance(node.value, bool):
                return 'Boolean'
            if isinstance(node.value, int):
                return 'Int'
            if isinstance(node.value, float):
                return 'Double'
            if isinstance(node.value, str):
                return 'String'
            if node.value is None:
                return 'Any?'
        if isinstance(node, ast.ListLiteral):
            if node.elements:
                elem_type = self._infer_kotlin_type(node.elements[0])
                if all(self._infer_kotlin_type(e) == elem_type for e in node.elements):
                    return f'MutableList<{elem_type}>'
            return 'MutableList<Any>'
        if isinstance(node, ast.DictLiteral):
            if node.pairs:

                def _key_type(k):
                    return self._infer_kotlin_type(
                        ast.Literal(k, 0) if isinstance(k, (int, float, str, bool)) else k
                    )

                key_types = {_key_type(k) for k, _ in node.pairs}
                val_types = {self._infer_kotlin_type(v) for _, v in node.pairs}
                # A map literal compiles to a single Kotlin type — collapse to
                # Any when the keys (or values) aren't all the same, else the
                # declared type won't match the inferred element types.
                key_type = next(iter(key_types)) if len(key_types) == 1 else 'Any'
                val_type = next(iter(val_types)) if len(val_types) == 1 else 'Any'
                return f'MutableMap<{key_type}, {val_type}>'
            return 'MutableMap<String, Any>'
        if isinstance(node, ast.Identifier):
            looked = self.symbols.lookup(node.name)
            if looked:
                return looked
            if self.in_class and node.name in self.class_properties:
                return self.class_properties[node.name]
        if isinstance(node, ast.BinaryOp):
            lt = self._infer_kotlin_type(node.left)
            rt = self._infer_kotlin_type(node.right)
            if node.operator == '+':
                numeric = {'Int', 'Long', 'Double', 'Float'}
                # Mirror _expr_binary exactly: native String concat (String result)
                # happens only for a String left, or a String right with a
                # non-dynamic left. A dynamic left lowers to eplAdd, whose return is
                # Any? — inferring String there mis-declares the enclosing concat.
                if lt == 'String':
                    return 'String'
                if rt == 'String' and lt not in self._DYNAMIC:
                    return 'String'
                if lt not in numeric and rt not in numeric:
                    return 'Any?'
            if node.operator in ('==', '!=', '<', '>', '<=', '>=', 'and', 'or'):
                return 'Boolean'
            if node.operator in ('+', '-', '*', '%'):
                if lt in self._DYNAMIC or rt in self._DYNAMIC:
                    return 'Any?'
                if lt == 'Double' or rt == 'Double':
                    return 'Double'
                if lt == 'Int' and rt == 'Int':
                    return 'Int'
            if node.operator == '/':
                # eplDiv keeps an evenly-divisible int/int integral (interpreter
                # parity: 10/2 prints 5, not 5.0), so `/` can't pin to Double.
                return 'Any'
            if node.operator == '//':
                return 'Int'
            if node.operator == '**':
                # Int base with non-negative Int exponent stays integral at
                # runtime (eplPow), so the static type can't be pinned to Double.
                return 'Any'
        if isinstance(node, ast.UnaryOp):
            if node.operator == 'not':
                return 'Boolean'
            return self._infer_kotlin_type(node.operand)
        if isinstance(node, ast.FunctionCall):
            fn_info = self.symbols.lookup_function(node.name)
            if fn_info:
                return fn_info['return']
            if self.symbols.lookup(node.name) in self._DYNAMIC:
                return 'Any?'
            # db_* builtins (native SQLite bridge)
            db_ret = {
                'db_query': 'MutableList<Map<String, Any?>>',
                'db_query_params': 'MutableList<Map<String, Any?>>',
                'db_query_one': 'Map<String, Any?>?',
                'db_count': 'Long',
                'db_open': 'Any',
                'db_execute': 'Unit',
                'db_execute_params': 'Unit',
                'db_close': 'Unit',
                'db_create_table': 'Boolean',
                'db_tables': 'MutableList<String>',
                'file_exists': 'Boolean',
                'file_delete': 'Boolean',
                'file_read': 'String',
                'file_write': 'Boolean',
                'file_append': 'Boolean',
                'file_size': 'Long',
            }
            if node.name in db_ret:
                return db_ret[node.name]
            # Built-in return types
            builtin_types = {
                'length': 'Int',
                'to_integer': 'Int',
                'to_text': 'String',
                'to_decimal': 'Double',
                'uppercase': 'String',
                'lowercase': 'String',
                'sqrt': 'Double',
                'power': 'Any',
                'floor': 'Int',
                'ceil': 'Int',
                'round': 'Long',
                'absolute': 'Int',
                'abs': 'Int',
                'typeof': 'String',
                'max': 'Int',
                'min': 'Int',
                'random': 'Double',
                'log': 'Double',
                'sin': 'Double',
                'cos': 'Double',
                'type_of': 'String',
                'is_integer': 'Boolean',
                'is_decimal': 'Boolean',
                'is_text': 'Boolean',
                'is_boolean': 'Boolean',
                'is_list': 'Boolean',
                'is_map': 'Boolean',
                'is_nothing': 'Boolean',
                'is_number': 'Boolean',
                'range': 'MutableList<Int>',
                'sum': 'Any',
                'sorted': 'MutableList<Any?>',
                'reversed': 'Any?',
                'reverse': 'Any?',
                'char_code': 'Int',
                'from_char_code': 'String',
                'json_parse': 'Any?',
                'json_stringify': 'String',
                'keys': 'MutableList<String>',
                'values': 'MutableList<Any?>',
                'random_integer': 'Int',
                'format': 'String',
                'hash_sha256': 'String',
                'hash_md5': 'String',
                'base64_encode': 'String',
                'base64_decode': 'String',
                'hex_encode': 'String',
                'hex_decode': 'String',
                'url_encode': 'String',
                'url_decode': 'String',
                'uuid4': 'String',
                'uuid': 'String',
                'timestamp': 'Double',
                'today': 'String',
                'now': 'String',
                'regex_find_all': 'MutableList<String>',
                'regex_test': 'Boolean',
                'regex_replace': 'String',
                'regex_split': 'MutableList<String>',
                'pi': 'Double',
                'euler': 'Double',
                'factorial': 'Long',
                'gcd': 'Long',
                'dict_from_lists': 'MutableMap<Any?, Any?>',
            }
            return builtin_types.get(node.name, 'Any')
        if isinstance(node, ast.TernaryExpression):
            tt = self._infer_kotlin_type(node.true_expr)
            ft = self._infer_kotlin_type(node.false_expr)
            if tt == ft:
                return tt
        if isinstance(node, ast.NewInstance):
            return node.class_name
        if isinstance(node, ast.LambdaExpression):
            # EPL lambdas are dynamic: uniform (Any?...) -> Any?.
            params_part = ', '.join(['Any?'] * len(node.params)) if node.params else ''
            return f'({params_part}) -> Any?'
        if isinstance(node, ast.MethodCall):
            # A call on a known user-class instance (e.g. `calc.add(...)`) resolves
            # to that class's declared method return type — otherwise the generic
            # builtin-method map below would misread it (e.g. list `.add` ⇒ Unit).
            recv_type = self._infer_kotlin_type(node.obj)
            cls = self.symbols.lookup_class(recv_type)
            if cls and node.method_name in cls.get('methods', {}):
                return cls['methods'][node.method_name]
            if 'Map' in recv_type:
                map_ret = {
                    'has': 'Boolean',
                    'has_key': 'Boolean',
                    'keys': 'MutableList<String>',
                    'values': 'MutableList<Any?>',
                    'entries': 'MutableList<MutableList<Any?>>',
                    'merge': 'MutableMap<String, Any?>',
                    'copy': 'MutableMap<String, Any?>',
                    'get': 'Any?',
                    'set': 'Unit',
                    'clear': 'Unit',
                    'remove': 'Unit',
                }
                if node.method_name in map_ret:
                    return map_ret[node.method_name]
            if recv_type == 'String':
                str_ret = {
                    'find': 'Int',
                    'index_of': 'Int',
                    'count': 'Int',
                    'char_at': 'String',
                    'reverse': 'String',
                    'pad_left': 'String',
                    'pad_right': 'String',
                    'to_list': 'MutableList<String>',
                    'is_number': 'Boolean',
                    'is_alpha': 'Boolean',
                    'is_empty': 'Boolean',
                    'to_integer': 'Int',
                    'to_decimal': 'Double',
                    'format': 'String',
                }
                if node.method_name in str_ret:
                    return str_ret[node.method_name]
            # Methods shared by strings and lists route through EPLRuntime on a
            # dynamic receiver — mirror those helpers' return types.
            if recv_type in ('Any', 'Any?'):
                dyn_ret = {
                    'reverse': 'Any',
                    'replace': 'String',
                    'count': 'Int',
                    'length': 'Int',
                    'contains': 'Boolean',
                }
                if node.method_name in dyn_ret:
                    return dyn_ret[node.method_name]
            method_ret = {
                'length': 'Int',
                'size': 'Int',
                'contains': 'Boolean',
                'starts_with': 'Boolean',
                'ends_with': 'Boolean',
                'index_of': 'Int',
                'find': 'Any?',
                'count': 'Int',
                'upper': 'String',
                'uppercase': 'String',
                'lower': 'String',
                'lowercase': 'String',
                'trim': 'String',
                'replace': 'String',
                'substring': 'String',
                'split': 'MutableList<String>',
                'join': 'String',
                'sort': 'MutableList<Any>',
                'sorted': 'MutableList<Any>',
                'reverse': 'MutableList<Any>',
                'reversed': 'MutableList<Any>',
                'add': 'Unit',
                'push': 'Unit',
                'remove': 'Unit',
                'repeat': 'String',
                # Higher-order list methods route through EPLRuntime (see _expr_method).
                'map': 'MutableList<Any?>',
                'filter': 'MutableList<Any?>',
                'reduce': 'Any?',
                'every': 'Boolean',
                'some': 'Boolean',
            }
            return method_ret.get(node.method_name, 'Any')
        if isinstance(node, ast.SliceAccess):
            if self._infer_kotlin_type(node.obj) == 'String':
                return 'String'
            return 'Any?'
        if isinstance(node, ast.IndexAccess):
            obj_type = self._infer_kotlin_type(node.obj)
            if obj_type == 'String':
                return 'Char'
            if obj_type.startswith('MutableList<') or obj_type.startswith('List<'):
                inner = obj_type[obj_type.index('<') + 1 : -1]
                return inner
            if obj_type.startswith('MutableMap<') or obj_type.startswith('Map<'):
                parts = obj_type[obj_type.index('<') + 1 : -1].split(', ', 1)
                if len(parts) == 2:
                    return parts[1]
            if obj_type in ('Any', 'Any?'):
                # dynamic index access goes through EPLRuntime.at → nullable
                return 'Any?'
        if isinstance(node, ast.PropertyAccess):
            obj_type = self._infer_kotlin_type(node.obj)
            prop = node.property_name
            if prop == 'length':
                return 'Int'
            if obj_type == 'String' and prop in ('uppercase', 'lowercase', 'trim'):
                return 'String'
            cls_info = self.symbols.lookup_class(obj_type)
            if cls_info and prop in cls_info.get('properties', {}):
                return cls_info['properties'][prop]
            if self._is_dynamic_or_map(obj_type):
                # dynamic field access (map row / Any) goes through EPLRuntime.field
                return 'Any?'
        return 'Any'

    @staticmethod
    def _is_dynamic_or_map(t: str) -> bool:
        """A Kotlin type that EPL treats as a dynamic key/value bag (map or Any)."""
        return t in ('Any', 'Any?') or t.startswith('Map<') or t.startswith('MutableMap<')

    @staticmethod
    def _is_list_or_dynamic(t: str) -> bool:
        """A receiver the runtime list helpers accept: a List type or a dynamic value."""
        return t in ('Any', 'Any?') or 'List<' in t

    def _infer_param_type(self, param) -> str:
        """Infer Kotlin type for a function parameter."""
        if len(param) > 1 and param[1]:
            type_map = {
                'integer': 'Int',
                'int': 'Int',
                'decimal': 'Double',
                'float': 'Double',
                'text': 'String',
                'string': 'String',
                'boolean': 'Boolean',
                'bool': 'Boolean',
                'list': 'MutableList<Any>',
                'map': 'MutableMap<String, Any>',
            }
            return type_map.get(str(param[1]).lower(), 'Any')
        return 'Any'

    def _format_param(self, p) -> str:
        """Format a parameter with type and optional default value."""
        return self._format_param_typed(p, self._infer_param_type(p))

    # Kotlin hard keywords that can legally appear as EPL identifiers — must be
    # backtick-escaped wherever emitted as a name. Excludes `this`/`super`, which
    # EPL uses with the same meaning as Kotlin and must pass through unescaped.
    _KOTLIN_HARD_KEYWORDS = frozenset(
        {
            'val', 'var', 'fun', 'object', 'when', 'is', 'in', 'as',
            'class', 'interface', 'typealias', 'typeof', 'by', 'package',
        }
    )

    @classmethod
    def _safe_ident(cls, name: str) -> str:
        """Backtick-escape an identifier that collides with a Kotlin hard keyword."""
        return f'`{name}`' if name in cls._KOTLIN_HARD_KEYWORDS else name

    def _format_param_typed(self, p, kt_type) -> str:
        """Format a parameter with a pre-resolved Kotlin type + optional default."""
        name = self._safe_ident(p[0])
        if len(p) > 2 and p[2] is not None:
            return f'{name}: {kt_type} = {self._expr(p[2])}'
        return f'{name}: {kt_type}'

    def _resolve_param_types(self, params, body):
        """Resolve each param's Kotlin type: annotation wins, else infer from usage.

        Returns a list of (name, kotlin_type). An unannotated parameter is typed
        from how `body` uses it (arithmetic/comparison ⇒ numeric, string concat ⇒
        String), so untyped EPL functions still emit compilable Kotlin instead of
        `Any` receivers that no operator applies to. Body-local variable types are
        pre-scanned so a parameter compared/combined with a local (e.g. a loop
        counter) resolves even though the local isn't emitted yet.
        """
        prev = self.symbols
        self.symbols = self.symbols.child()
        for lname, lt in self._scan_local_types(body).items():
            self.symbols.define(lname, lt)
        try:
            resolved = []
            for p in params:
                if len(p) > 1 and p[1]:
                    resolved.append((p[0], self._infer_param_type(p)))
                else:
                    resolved.append((p[0], self._infer_param_from_usage(p[0], body)))
            return resolved
        finally:
            self.symbols = prev

    def _scan_local_types(self, body):
        """Best-effort map of body-local name → Kotlin type from its first simple
        assignment. Lets param/return inference resolve references to locals that
        haven't been emitted into the symbol table yet. Values that infer to Any
        (e.g. assigned from an as-yet-untyped param) are skipped."""
        types: dict = {}
        for n in self._walk_ast(body):
            if isinstance(n, (ast.VarAssignment, ast.VarDeclaration)) and n.name not in types:
                # Mirror _widen_decl_type exactly: a local first assigned an Any
                # value (or an empty list) is emitted with a widened nullable type,
                # so return-type inference must see the same widened type — else it
                # mis-declares `return <local>` and Kotlin rejects the mismatch.
                t = self._widen_decl_type(n.value, self._infer_kotlin_type(n.value))
                if t != 'Any':
                    types[n.name] = t
        return types

    # Method names that only a String receiver has (drive param inference).
    _STR_ONLY_METHODS = frozenset(
        {
            'substring', 'split', 'trim', 'uppercase', 'lowercase', 'upper', 'lower',
            'starts_with', 'ends_with', 'is_number', 'is_alpha', 'char_at',
            'pad_left', 'pad_right', 'to_list', 'is_empty',
        }
    )
    # Method names that only a list receiver has.
    _LIST_ONLY_METHODS = frozenset({'add', 'push', 'join'})

    def _infer_param_from_usage(self, name, body) -> str:
        """Infer an unannotated parameter's type from how the body uses it.

        Numeric signals: true arithmetic (`-`, `*`, `/`, `%`, `//`, `**`), ordering
        comparisons against a numeric operand, and `+` *only* when the other operand
        is itself numeric (so it's addition, not string concatenation). A bare `+`
        against a string/dynamic operand is ignored — in EPL `+` doubles as concat
        and stringifies any value. String/list signals come from receiver-specific
        method calls (`s.substring(...)` ⇒ String, `items.add(...)` ⇒ list) so
        untyped stdlib helpers emit typed receivers instead of `Any`, on which no
        member resolves. Numeric evidence wins; anything inconclusive stays `Any`.
        """
        # `/` infers like the int-preserving ops: eplDiv keeps an evenly-divisible
        # int/int integral, so pinning its operands to Double would print 5.0
        # where the interpreter prints 5. `**` is absent for the same reason.
        arith_int = {'-', '*', '%', '//', '/'}
        compare = {'<', '>', '<=', '>='}
        evidence = set()
        for n in self._walk_ast(body):
            if isinstance(n, ast.MethodCall) and self._is_identifier(n.obj, name):
                if n.method_name in self._STR_ONLY_METHODS:
                    evidence.add('String')
                elif n.method_name in self._LIST_ONLY_METHODS:
                    evidence.add('List')
                continue
            # `For i from 1 to param` ⇒ param is a numeric range bound.
            if isinstance(n, ast.ForRange) and (
                self._is_identifier(n.start, name) or self._is_identifier(n.end, name)
            ):
                evidence.add('Int')
                continue
            if not isinstance(n, ast.BinaryOp):
                continue
            left_is = self._is_identifier(n.left, name)
            right_is = self._is_identifier(n.right, name)
            if not (left_is or right_is):
                continue
            other_t = self._infer_kotlin_type(n.right if left_is else n.left)
            if n.operator in arith_int:
                evidence.add('Double' if other_t == 'Double' else 'Int')
            elif n.operator == '+' and other_t in ('Int', 'Double'):
                evidence.add(other_t)
            elif n.operator in compare and other_t in ('Int', 'Double'):
                evidence.add(other_t)
        if 'Double' in evidence:
            return 'Double'
        if 'Int' in evidence:
            return 'Int'
        if 'String' in evidence and 'List' not in evidence:
            return 'String'
        if 'List' in evidence and 'String' not in evidence:
            return 'MutableList<Any>'
        return 'Any'

    @staticmethod
    def _is_identifier(node, name) -> bool:
        return isinstance(node, ast.Identifier) and node.name == name

    def _walk_ast(self, node):
        """Yield every AST node in the subtree (lists are descended into)."""
        if isinstance(node, list):
            for item in node:
                yield from self._walk_ast(item)
            return
        if not hasattr(node, '__dict__'):
            return
        yield node
        for v in vars(node).values():
            if isinstance(v, list):
                for item in v:
                    if hasattr(item, '__dict__'):
                        yield from self._walk_ast(item)
            elif hasattr(v, '__dict__'):
                yield from self._walk_ast(v)

    def _calls_function(self, expr, name) -> bool:
        """True if `expr` contains a call to the named function (recursion check)."""
        return any(isinstance(n, ast.FunctionCall) and n.name == name for n in self._walk_ast(expr))

    def _infer_return_type(self, node, param_types=None, skip_recursive=False) -> str:
        """Infer return type from function body by scanning all return paths.

        With `param_types` (list of (name, kt_type)), the parameters are placed in
        a temporary scope so return expressions that use them resolve correctly.
        With `skip_recursive`, return expressions that call this function are
        ignored — used to seed the signature from non-recursive (base-case) paths
        before a second pass resolves the recursive ones.
        """
        # Check explicit return type annotation
        if hasattr(node, 'return_type') and node.return_type:
            type_map = {
                'integer': 'Int',
                'int': 'Int',
                'decimal': 'Double',
                'float': 'Double',
                'text': 'String',
                'string': 'String',
                'boolean': 'Boolean',
                'bool': 'Boolean',
                'list': 'MutableList<Any>',
                'nothing': 'Unit',
            }
            return type_map.get(str(node.return_type).lower(), 'Any')

        prev_symbols = self.symbols
        if param_types is not None:
            self.symbols = self.symbols.child()
            for name, pt in param_types:
                self.symbols.define(name, pt)
            # Body-local types help resolve `return <local>` expressions.
            for lname, lt in self._scan_local_types(node.body).items():
                if self.symbols.lookup(lname) is None:
                    self.symbols.define(lname, lt)
        try:
            return_types: set = set()
            skip_fn = getattr(node, 'name', None) if skip_recursive else None
            self._collect_return_types(node.body, return_types, skip_fn)
        finally:
            self.symbols = prev_symbols

        return_types.discard(None)
        if not return_types:
            return 'Unit'
        # Remove Unit from mixed returns
        non_unit = return_types - {'Unit'}
        # A `Return Nothing` path (typed Any?) means null flows out, so the
        # signature must stay nullable even when merged with concrete types.
        nullable = any(t.endswith('?') for t in non_unit)
        if len(non_unit) == 1:
            return non_unit.pop()
        if len(non_unit) == 0:
            return 'Unit'
        # Multiple return types — find common supertype
        bare = {t[:-1] if t.endswith('?') else t for t in non_unit}
        if bare <= {'Int', 'Double'}:
            return 'Double?' if nullable else 'Double'
        return 'Any?' if nullable else 'Any'

    def _collect_return_types(self, stmts, types, skip_fn=None):
        """Recursively collect return types from statement list.

        `skip_fn`: if set, return expressions containing a call to that function
        name are skipped (recursion seeding — see `_infer_return_type`).
        """
        for s in stmts:
            if isinstance(s, ast.ReturnStatement):
                if s.value:
                    if skip_fn and self._calls_function(s.value, skip_fn):
                        continue
                    types.add(self._infer_kotlin_type(s.value))
                else:
                    types.add('Unit')
            elif isinstance(s, ast.IfStatement):
                self._collect_return_types(s.then_body, types, skip_fn)
                if s.else_body:
                    self._collect_return_types(s.else_body, types, skip_fn)
            elif isinstance(s, ast.WhileLoop):
                self._collect_return_types(s.body, types, skip_fn)
            elif isinstance(s, ast.ForRange):
                self._collect_return_types(s.body, types, skip_fn)
            elif isinstance(s, ast.ForEachLoop):
                self._collect_return_types(s.body, types, skip_fn)
            elif isinstance(s, ast.TryCatch):
                self._collect_return_types(s.try_body, types, skip_fn)
                self._collect_return_types(s.catch_body, types, skip_fn)

    def _emit_return(self, node):
        if node.value:
            val = self._expr(node.value)
            # A Double-returning function with an Int-literal return path (e.g. a
            # `return 0` guard) needs the value widened — Kotlin won't auto-promote.
            rt = getattr(self, '_current_ret_type', None)
            if rt in ('Double', 'Float') and self._infer_kotlin_type(node.value) in ('Int', 'Long'):
                val = f'({val}).toDouble()'
            self._line(f'return {val}')
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
        has_companion = static_methods or (
            init_method and [p for p in init_method.params if p[0] != 'self']
        )
        if has_companion:
            self._line('')
            self._line('companion object {')
            self.indent += 1
            # Factory method
            if init_method:
                init_params = [p for p in init_method.params if p[0] != 'self']
                if init_params:
                    params_sig = ', '.join(
                        f'{p[0]}: {self._infer_param_type(p)}' for p in init_params
                    )
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
        # Interpreter parity: an EPL enum is a name → ordinal map (Color.RED == 0,
        # prints as 0, matches `When 0`). A real Kotlin `enum class` would print
        # the member name and never equal an Int, so emit Int constants instead.
        self._line(f'object {node.name} {{')
        self.indent += 1
        for i, member in enumerate(node.members):
            self._line(f'const val {member}: Int = {i}')
        self.indent -= 1
        self._line('}')

    def _emit_match(self, node):
        self._line(f'when ({self._expr(node.expression)}) {{')
        self.indent += 1
        for clause in node.when_clauses:
            vals = ', '.join(self._expr(v) for v in clause.values)
            self._line(f'{vals} -> {{')
            self.indent += 1
            for s in clause.body:
                self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        if node.default_body:
            self._line('else -> {')
            self.indent += 1
            for s in node.default_body:
                self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        self.indent -= 1
        self._line('}')

    def _emit_try_catch(self, node):
        self._line('try {')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        self.indent -= 1
        # EPL's catch variable is the error MESSAGE (a string), not the exception.
        var = self._safe_ident(node.error_var or 'e')
        self._line('} catch (__exc: Exception) {')
        self.indent += 1
        self._line(f'val {var}: String = __exc.message ?: __exc.toString()')
        self.symbols.define(node.error_var or 'e', 'String')
        for s in node.catch_body:
            self._emit_stmt(s)
        self.indent -= 1
        if hasattr(node, 'finally_body') and node.finally_body:
            self._line('} finally {')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
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
            self._line(
                f'AlertDialog.Builder(this).setTitle("Error").setMessage({msg}).setPositiveButton("OK", null).show()'
            )
        elif dtype in ('yesno', 'confirm'):
            self._line(f'AlertDialog.Builder(this).setMessage({msg})')
            self.indent += 1
            self._line('.setPositiveButton("Yes") { _, _ -> /* yes handler */ }')
            self._line('.setNegativeButton("No") { _, _ -> /* no handler */ }')
            self._line('.show()')
            self.indent -= 1
        elif dtype == 'input':
            self.imports.add('android.widget.EditText')
            self._line('val dialogInput = EditText(this)')
            self._line(f'AlertDialog.Builder(this).setTitle({msg}).setView(dialogInput)')
            self.indent += 1
            self._line(
                '.setPositiveButton("OK") { _, _ -> val text = dialogInput.text.toString() }'
            )
            self._line('.show()')
            self.indent -= 1
        else:
            self._line(f'Toast.makeText(this, {msg}, Toast.LENGTH_LONG).show()')

    def _emit_async_function(self, node):
        """Emit async function as Kotlin coroutine."""
        self.imports.add('kotlinx.coroutines.*')
        real_params = [p for p in node.params if p[0] != 'self']
        param_types = self._resolve_param_types(real_params, node.body)
        # Register in symbol table before body (supports recursion)
        seed_ret = self._infer_return_type(node, param_types, skip_recursive=True)
        self.symbols.define_function(node.name, param_types, seed_ret)
        ret_type = self._infer_return_type(node, param_types)
        self.symbols.define_function(node.name, param_types, ret_type)
        params = ', '.join(
            self._format_param_typed(p, pt) for p, (_, pt) in zip(real_params, param_types)
        )
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
        if node is None:
            return 'null'
        if isinstance(node, ast.Literal):
            return self._expr_literal(node)
        if isinstance(node, ast.Identifier):
            name = node.name
            if self.in_class and name in self.class_properties:
                return f'this.{name}'
            return self._safe_ident(name)
        if isinstance(node, ast.BinaryOp):
            return self._expr_binary(node)
        if isinstance(node, ast.UnaryOp):
            return self._expr_unary(node)
        if isinstance(node, ast.FunctionCall):
            return self._expr_call(node)
        if isinstance(node, ast.PropertyAccess):
            obj_code = self._expr(node.obj)
            obj_type = self._infer_kotlin_type(node.obj)
            prop = node.property_name
            # EPL exposes some methods as property-style accessors (no parens).
            if prop == 'length':
                if obj_type == 'String':
                    return f'{obj_code}.length'
                if self._is_dynamic_or_map(obj_type):
                    return f'EPLRuntime.lengthOf({obj_code})'
                return f'{obj_code}.size'
            if obj_type == 'String' and prop in ('uppercase', 'lowercase', 'trim'):
                return f'{obj_code}.{prop}()'
            # On a map/db-row/Any, `row.field` means key lookup, not a Kotlin member.
            if self._is_dynamic_or_map(obj_type):
                return f'EPLRuntime.field({obj_code}, "{prop}")'
            return f'{obj_code}.{prop}'
        if isinstance(node, ast.MethodCall):
            return self._expr_method(node)
        if isinstance(node, ast.IndexAccess):
            obj_code = self._expr(node.obj)
            obj_type = self._infer_kotlin_type(node.obj)
            # Indexing an Any value has no static get operator — go through the bridge.
            if obj_type in ('Any', 'Any?'):
                return f'EPLRuntime.at({obj_code}, {self._expr(node.index)})'
            return f'{obj_code}[{self._expr(node.index)}]'
        if isinstance(node, ast.SliceAccess):
            def slice_arg(x):
                if x is None or (
                    isinstance(x, ast.Literal) and getattr(x, 'value', 0) is None
                ):
                    return 'null'
                return self._expr(x)

            obj_code = self._expr(node.obj)
            start = slice_arg(node.start)
            end = slice_arg(node.end)
            step = slice_arg(node.step)
            call = f'EPLRuntime.slice({obj_code}, {start}, {end}, {step})'
            if self._infer_kotlin_type(node.obj) == 'String':
                return f'({call} as String)'
            return call
        if isinstance(node, ast.ListLiteral):
            return f'mutableListOf({", ".join(self._expr(e) for e in node.elements)})'
        if isinstance(node, ast.DictLiteral):
            return self._expr_dict(node)
        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.arguments:
                cls_info = self.symbols.lookup_class(node.class_name)
                if cls_info:
                    return f'{node.class_name}.create({args})'
                return f'{node.class_name}({args})'
            return f'{node.class_name}()'
        if isinstance(node, ast.LambdaExpression):
            # Params annotated Any? so the body's operators route through the
            # dynamic runtime helpers and the lambda fits bare `Any` targets.
            param_str = ', '.join(f'{p}: Any?' for p in node.params) if node.params else ''
            saved = self.symbols
            self.symbols = self.symbols.child()
            for p in node.params:
                self.symbols.define(p, 'Any?')
            body_str = self._expr(node.body)
            self.symbols = saved
            return f'{{ {param_str} -> {body_str} }}' if param_str else f'{{ {body_str} }}'
        if isinstance(node, ast.TernaryExpression):
            return f'if ({self._expr(node.condition)}) {self._expr(node.true_expr)} else {self._expr(node.false_expr)}'
        if isinstance(node, ast.ModuleAccess):
            return f'{node.module_name}.{node.member_name}'
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
        if isinstance(node, ast.FileRead):
            return f'EPLRuntime.fileRead({self._expr(node.filepath)})'
        if isinstance(node, str):
            return f'"{node}"'
        # Fallback with type info comment
        return f'null /* unhandled: {type(node).__name__} */'

    @staticmethod
    def _kotlin_str_literal(value: str) -> str:
        """Render a Python string as a safe Kotlin double-quoted literal.

        SECURITY: Kotlin interpolates `$name` and `${expr}` inside double-quoted
        strings, so `$` MUST be escaped — otherwise an EPL string literal like
        "${Runtime.getRuntime().exec(...)}" would become live Kotlin in the
        generated app (arbitrary code execution in the transpiled Android/desktop
        binary). Backslash is escaped first so the other escapes aren't doubled.
        """
        escaped = (
            value.replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('$', '\\$')
            .replace('\n', '\\n')
            .replace('\t', '\\t')
        )
        return f'"{escaped}"'

    def _expr_literal(self, node):
        if isinstance(node.value, bool):
            return 'true' if node.value else 'false'
        if isinstance(node.value, str):
            if '$' in node.value:
                return self._interpolated_str_literal(node.value)
            return self._kotlin_str_literal(node.value)
        if node.value is None:
            return 'null'
        if isinstance(node.value, float):
            return str(node.value)
        return str(node.value)

    _TEMPLATE_RE = re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)')

    def _interpolated_str_literal(self, value: str) -> str:
        """EPL string templates: `$var` / `${expr}` interpolate (interpreter parity).

        SECURITY: raw text is never spliced into Kotlin. `$var` resolves only for
        identifiers declared in the symbol table (name shape enforced by the
        regex); `${expr}` is parsed as EPL and routed through the code generator.
        Anything unresolved stays a `\\$`-escaped literal, exactly like the
        interpreter leaves unknown templates as-is.
        """
        out = []
        pos = 0
        for m in self._TEMPLATE_RE.finditer(value):
            expr_text, var_name = m.group(1), m.group(2)
            kt = None
            if var_name is not None:
                if self.symbols.lookup(var_name) is not None:
                    kt = f'EPLRuntime.toText({self._safe_ident(var_name)})'
            else:
                kt = self._template_expr_kotlin(expr_text)
            if kt is None:
                continue
            lit = self._kotlin_str_literal(value[pos : m.start()])[1:-1]
            out.append(lit)
            out.append(f'${{{kt}}}')
            pos = m.end()
        out.append(self._kotlin_str_literal(value[pos:])[1:-1])
        return '"' + ''.join(out) + '"'

    def _template_expr_kotlin(self, expr_text: str):
        """Parse a `${...}` template body as an EPL expression → Kotlin, or None."""
        try:
            from epl.lexer import Lexer
            from epl.parser import Parser

            tokens = Lexer(expr_text).tokenize()
            node = Parser(tokens)._parse_expression()
            return f'EPLRuntime.toText({self._expr(node)})'
        except Exception:
            return None

    _DYNAMIC = {'Any', 'Any?'}

    def _expr_binary(self, node):
        l, r = self._expr(node.left), self._expr(node.right)
        op = node.operator
        m = {'and': '&&', 'or': '||', '**': '', '//': ''}
        lt = self._infer_kotlin_type(node.left)
        rt = self._infer_kotlin_type(node.right)
        dynamic = lt in self._DYNAMIC or rt in self._DYNAMIC
        # Dynamic operands can't use Kotlin's native operators; route to EPLRuntime.
        if dynamic:
            dyn = {
                '*': 'eplMul',
                '-': 'eplSub',
                '%': 'eplMod',
                '**': 'eplPow',
                '<': 'eplLt',
                '>': 'eplGt',
                '<=': 'eplLe',
                '>=': 'eplGe',
                '==': 'eplEq',
            }
            if op in dyn:
                return f'EPLRuntime.{dyn[op]}({l}, {r})'
            if op == '!=':
                return f'(!EPLRuntime.eplEq({l}, {r}))'
            if op == '//':
                return f'kotlin.math.floor(EPLRuntime.toDecimal(EPLRuntime.eplDiv({l}, {r}, {node.line}))).toInt()'
            # `+` on a dynamic left is add-or-concat at runtime (String left concats natively).
            if op == '+' and lt != 'String':
                return f'EPLRuntime.eplAdd({l}, {r})'
        if op == '**':
            # eplPow keeps int ** non-negative int integral (interpreter parity)
            return f'EPLRuntime.eplPow({l}, {r})'
        if op == '//':
            self.imports.add('kotlin.math.floor')
            return f'floor({l}.toDouble() / {r}.toDouble()).toInt()'
        if op == '/':
            return f'EPLRuntime.eplDiv({l}, {r}, {node.line})'
        if op == '+':
            numeric = {'Int', 'Long', 'Double', 'Float'}
            # String concat: native `+` needs a String LEFT (String.plus(Any?)); a
            # non-String left with a String right is coerced. Both-numeric stays
            # native. Anything else is dynamic → eplAdd decides add-vs-concat.
            if lt == 'String':
                pass
            elif rt == 'String':
                l = f'({l}).toString()'
            elif not (lt in numeric and rt in numeric):
                return f'EPLRuntime.eplAdd({l}, {r})'
        # Kotlin won't mix Double and Int in a comparison or arithmetic op; coerce
        # the integer side so `b == 0` / `d - 1` compile when b/d are Double.
        float_types = {'Double', 'Float'}
        int_types = {'Int', 'Long'}
        if op not in ('/', '+'):
            if lt in float_types and rt in int_types:
                r = f'({r}).toDouble()'
            elif rt in float_types and lt in int_types:
                l = f'({l}).toDouble()'
        return f'({l} {m.get(op, op)} {r})'

    def _expr_unary(self, node):
        if node.operator == 'not':
            # Kotlin's `!` requires Boolean; a dynamic operand (Any?/Any, e.g. a
            # dynamic-lambda call result) must go through EPL truthiness first.
            operand_type = self._infer_kotlin_type(node.operand)
            if operand_type in ('Any', 'Any?'):
                return f'!EPLRuntime.truthy({self._expr(node.operand)})'
            return f'!{self._expr(node.operand)}'
        return f'{node.operator}{self._expr(node.operand)}'

    def _coerce_call_args(self, arguments, params):
        """Emit call args, widening an Int-typed arg to Double when the declared
        param is a floating-point type — Kotlin won't auto-promote at call sites."""
        float_types = {'Double', 'Float'}
        int_types = {'Int', 'Long'}
        out = []
        for i, a in enumerate(arguments):
            code = self._expr(a)
            if i < len(params):
                pt = params[i][1]
                at = self._infer_kotlin_type(a)
                if pt in float_types and at in int_types:
                    code = f'({code}).toDouble()'
                elif pt in int_types and at in ('Any', 'Any?'):
                    # A dynamic value (list element, map lookup) into an Int param.
                    code = f'({code} as Number).toInt()'
                elif pt in float_types and at in ('Any', 'Any?'):
                    code = f'({code} as Number).toDouble()'
                elif pt == 'String' and at in ('Any', 'Any?'):
                    # A dynamic value into a String param (Kotlin won't accept Any).
                    code = f'({code}).toString()'
                elif pt == 'Any' and at == 'Any?':
                    # A nullable dynamic value (list element, map lookup) into a
                    # non-null Any param: assert non-null so the call type-checks.
                    code = f'({code})!!'
            out.append(code)
        return ', '.join(out)

    def _str_arg(self, arg):
        """Emit an expression for a String-consuming builtin, coercing a dynamic
        value (e.g. a loop var of type Any) to String so members resolve."""
        code = self._expr(arg)
        if self._infer_kotlin_type(arg) == 'String':
            return code
        return f'({code}).toString()'

    def _expr_call(self, node):
        args = ', '.join(self._expr(a) for a in node.arguments)
        # db_* builtins → native SQLite bridge in EPLRuntime (see _epl_runtime_kt)
        db_map = {
            'db_open': 'EPLRuntime.dbOpen',
            'db_close': 'EPLRuntime.dbClose',
            'db_execute': 'EPLRuntime.dbExecute',
            'db_execute_params': 'EPLRuntime.dbExecute',
            'db_query': 'EPLRuntime.dbQuery',
            'db_query_params': 'EPLRuntime.dbQuery',
            'db_query_one': 'EPLRuntime.dbQueryOne',
            'db_count': 'EPLRuntime.dbCount',
            'db_create_table': 'EPLRuntime.dbCreateTable',
            'db_tables': 'EPLRuntime.dbTables',
        }
        if node.name in db_map:
            return f'{db_map[node.name]}({args})'
        # file_* builtins → sandboxed file bridge in EPLRuntime
        file_map = {
            'file_exists': 'EPLRuntime.fileExists',
            'file_delete': 'EPLRuntime.fileDelete',
            'file_read': 'EPLRuntime.fileRead',
            'file_write': 'EPLRuntime.fileWrite',
            'file_append': 'EPLRuntime.fileAppend',
            'file_size': 'EPLRuntime.fileSize',
        }
        if node.name in file_map:
            return f'{file_map[node.name]}({args})'
        # A user-defined function shadows a builtin of the same name (e.g. a
        # function literally called `power` or `max`), so don't rewrite its call
        # into the builtin form.
        fn = self.symbols.lookup_function(node.name)
        if fn:
            return f'{node.name}({self._coerce_call_args(node.arguments, fn["params"])})'
        # A dynamic value used as a callable (e.g. a lambda in an Any param) needs
        # a cast to a function type before Kotlin will invoke it.
        var_type = self.symbols.lookup(node.name)
        if var_type in self._DYNAMIC:
            sig = ', '.join(['Any?'] * len(node.arguments))
            return f'({node.name} as ({sig}) -> Any?)({args})'
        m = {
            'length': lambda: f'EPLRuntime.lengthOf({self._expr(node.arguments[0])})',
            'to_integer': lambda: f'{self._expr(node.arguments[0])}.toString().toInt()',
            'to_text': lambda: f'{self._expr(node.arguments[0])}.toString()',
            'to_decimal': lambda: f'{self._expr(node.arguments[0])}.toString().toDouble()',
            'uppercase': lambda: f'{self._str_arg(node.arguments[0])}.uppercase()',
            'lowercase': lambda: f'{self._str_arg(node.arguments[0])}.lowercase()',
            'sqrt': lambda: f'kotlin.math.sqrt(EPLRuntime.toDecimal({args}))',
            # eplPow keeps int ** non-negative int integral (interpreter parity)
            'power': lambda: f'EPLRuntime.eplPow({args})',
            'floor': lambda: f'kotlin.math.floor(EPLRuntime.toDecimal({args})).toInt()',
            'ceil': lambda: f'kotlin.math.ceil(EPLRuntime.toDecimal({args})).toInt()',
            'round': lambda: f'EPLRuntime.roundNum({args})',
            'absolute': lambda: f'EPLRuntime.absNum({args})',
            'abs': lambda: f'EPLRuntime.absNum({args})',
            'type_of': lambda: f'EPLRuntime.typeName({args})',
            'typeof': lambda: f'EPLRuntime.typeName({args})',
            'max': lambda: f'maxOf({args})',
            'min': lambda: f'minOf({args})',
            'random': lambda: 'kotlin.random.Random.nextDouble()',
            'log': lambda: f'kotlin.math.ln(EPLRuntime.toDecimal({args}))',
            'sin': lambda: f'kotlin.math.sin(EPLRuntime.toDecimal({args}))',
            'cos': lambda: f'kotlin.math.cos(EPLRuntime.toDecimal({args}))',
            'reversed': lambda: f'EPLRuntime.reversed({args})',
            'reverse': lambda: f'EPLRuntime.reversed({args})',
            'range': lambda: f'EPLRuntime.rangeOf({args})',
            'sum': lambda: f'EPLRuntime.sumOf({args})',
            'sorted': lambda: f'EPLRuntime.sortedOf({args})',
            'is_integer': lambda: f'EPLRuntime.isInteger({args})',
            'is_decimal': lambda: f'EPLRuntime.isDecimal({args})',
            'is_text': lambda: f'EPLRuntime.isText({args})',
            'is_boolean': lambda: f'EPLRuntime.isBoolean({args})',
            'is_list': lambda: f'EPLRuntime.isList({args})',
            'is_map': lambda: f'EPLRuntime.isMap({args})',
            'is_nothing': lambda: f'EPLRuntime.isNothing({args})',
            'is_number': lambda: f'EPLRuntime.isNumber({args})',
            'char_code': lambda: f'EPLRuntime.charCode({args})',
            'from_char_code': lambda: f'EPLRuntime.fromCharCode({args})',
            'json_parse': lambda: f'EPLRuntime.jsonParse({args})',
            'json_stringify': lambda: f'EPLRuntime.jsonStringify({args})',
            'keys': lambda: f'EPLRuntime.mapKeys({args})',
            'values': lambda: f'EPLRuntime.mapValues({args})',
            'random_integer': lambda: f'EPLRuntime.randomInt({args})',
            'format': lambda: f'EPLRuntime.strFormat({args})',
            # crypto / encoding native builtins
            'hash_sha256': lambda: f'EPLRuntime.hashSha256({self._str_arg(node.arguments[0])})',
            'hash_md5': lambda: f'EPLRuntime.hashMd5({self._str_arg(node.arguments[0])})',
            'base64_encode': lambda: f'EPLRuntime.base64Encode({self._str_arg(node.arguments[0])})',
            'base64_decode': lambda: f'EPLRuntime.base64Decode({self._str_arg(node.arguments[0])})',
            'hex_encode': lambda: f'EPLRuntime.hexEncode({self._str_arg(node.arguments[0])})',
            'hex_decode': lambda: f'EPLRuntime.hexDecode({self._str_arg(node.arguments[0])})',
            'url_encode': lambda: f'EPLRuntime.urlEncode({self._str_arg(node.arguments[0])})',
            'url_decode': lambda: f'EPLRuntime.urlDecode({self._str_arg(node.arguments[0])})',
            'uuid4': lambda: 'EPLRuntime.uuid4()',
            'uuid': lambda: 'EPLRuntime.uuid4()',
            # datetime native builtins
            'timestamp': lambda: 'EPLRuntime.timestamp()',
            'today': lambda: 'EPLRuntime.today()',
            'now': lambda: 'EPLRuntime.now()',
            # regex native builtins
            'regex_find_all': lambda: (
                f'EPLRuntime.regexFindAll({self._str_arg(node.arguments[0])}, '
                f'{self._str_arg(node.arguments[1])})'
            ),
            'regex_test': lambda: (
                f'EPLRuntime.regexTest({self._str_arg(node.arguments[0])}, '
                f'{self._str_arg(node.arguments[1])})'
            ),
            'regex_replace': lambda: (
                f'EPLRuntime.regexReplace({self._str_arg(node.arguments[0])}, '
                f'{self._str_arg(node.arguments[1])}, {self._str_arg(node.arguments[2])})'
            ),
            'regex_split': lambda: (
                f'EPLRuntime.regexSplit({self._str_arg(node.arguments[0])}, '
                f'{self._str_arg(node.arguments[1])})'
            ),
            # math constants exposed as zero-arg builtins
            'pi': lambda: 'Math.PI',
            'euler': lambda: 'Math.E',
            'factorial': lambda: f'EPLRuntime.factorial({args})',
            'gcd': lambda: f'EPLRuntime.gcd({args})',
            # collections
            'dict_from_lists': lambda: f'EPLRuntime.dictFromLists({args})',
        }
        if node.name in m:
            if node.name == 'power':
                self.imports.add('kotlin.math.pow')
            return m[node.name]()
        return f'{node.name}({args})'

    # EPL string methods → native Kotlin member (parens appended by caller).
    _STR_NATIVE = {
        'uppercase': 'uppercase',
        'upper': 'uppercase',
        'lowercase': 'lowercase',
        'lower': 'lowercase',
        'trim': 'trim',
        'contains': 'contains',
        'replace': 'replace',
        'starts_with': 'startsWith',
        'ends_with': 'endsWith',
        'substring': 'substring',
        'find': 'indexOf',
        'index_of': 'indexOf',
        'repeat': 'repeat',
        'reverse': 'reversed',
        'is_empty': 'isEmpty',
        'to_integer': 'toInt',
        'to_decimal': 'toDouble',
    }
    # EPL string methods with no clean Kotlin member → EPLRuntime helper.
    _STR_HELPERS = {
        'count': 'strCount',
        'pad_left': 'padLeft',
        'pad_right': 'padRight',
        'char_at': 'charAt',
        'to_list': 'toCharList',
        'is_number': 'isNumberStr',
        'is_alpha': 'isAlphaStr',
        'format': 'strFormat',
    }

    # String-only methods safe to dispatch on a dynamic receiver by coercing to
    # String. Excludes methods a list also has (reverse/count/replace/contains/
    # length/find/index_of/repeat) — those are resolved by runtime dispatch.
    _DYN_STR_METHODS = frozenset(
        {
            'uppercase', 'upper', 'lowercase', 'lower', 'trim', 'starts_with',
            'ends_with', 'substring', 'split', 'char_at', 'pad_left', 'pad_right',
            'to_list', 'is_number', 'is_alpha', 'is_empty', 'to_integer',
            'to_decimal', 'format',
        }
    )

    # String members whose argument must be a CharSequence (not an index/count).
    _STR_ARG_METHODS = frozenset(
        {'contains', 'replace', 'starts_with', 'ends_with', 'find', 'index_of', 'split'}
    )

    def _string_method(self, obj, m, args):
        """Emit a String-receiver method call, or None if not a known string method."""
        if m == 'split':
            return f'{obj}.split({args}).toMutableList()'
        if m in self._STR_HELPERS:
            call_args = f'{obj}, {args}' if args else obj
            return f'EPLRuntime.{self._STR_HELPERS[m]}({call_args})'
        if m in self._STR_NATIVE:
            return f'{obj}.{self._STR_NATIVE[m]}({args})'
        return None

    def _expr_method(self, node):
        obj = self._expr(node.obj)
        args = ', '.join(self._expr(a) for a in node.arguments)
        m = node.method_name
        # EPL map methods don't line up with Kotlin MutableMap's API (keys/entries
        # are properties, has/merge/copy don't exist, get takes no default), so
        # route them through EPLRuntime helpers that dispatch on the actual value.
        map_helpers = {
            'has': 'mapHas',
            'has_key': 'mapHas',
            'keys': 'mapKeys',
            'values': 'mapValues',
            'entries': 'mapEntries',
            'merge': 'mapMerge',
            'get': 'mapGet',
            'set': 'mapSet',
            'clear': 'mapClear',
            'copy': 'mapCopy',
            'remove': 'mapRemove',
        }
        map_only = {'has', 'has_key', 'keys', 'values', 'entries', 'merge', 'set'}
        recv = self._infer_kotlin_type(node.obj)
        if m in map_helpers and ('Map' in recv or (recv in ('Any', 'Any?') and m in map_only)):
            call_args = f'{obj}, {args}' if args else obj
            return f'EPLRuntime.{map_helpers[m]}({call_args})'
        # String methods diverge from list methods (find/count/reverse take a
        # predicate on Kotlin CharSequence, pad/char_at/to_list have no member),
        # so dispatch string receivers through their own map + EPLRuntime helpers.
        if recv == 'String':
            # String members taking a CharSequence arg reject a dynamic (Any)
            # value — coerce those args to String first (e.g. a loop var from
            # iterate()). Index/count args (substring/char_at/pad/repeat) stay numeric.
            if m in self._STR_ARG_METHODS:
                args = ', '.join(self._str_arg(a) for a in node.arguments)
            result = self._string_method(obj, m, args)
            if result is not None:
                return result
        # Higher-order list methods take dynamic lambdas; route to EPLRuntime.
        ho = {
            'map': 'mapList',
            'filter': 'filterList',
            'reduce': 'reduceList',
            'find': 'findList',
            'every': 'everyList',
            'some': 'someList',
        }
        if m in ho and node.arguments and self._is_list_or_dynamic(recv):
            call_args = f'{obj}, {args}' if args else obj
            return f'EPLRuntime.{ho[m]}({call_args})'
        # Methods shared by strings and lists (reverse/count/replace/contains):
        # on a dynamic receiver the static type is unknown, so dispatch at runtime.
        dyn_shared = {
            'reverse': 'reverseOf',
            'count': 'countOf',
            'replace': 'replaceOf',
            'contains': 'containsOf',
            'length': 'lengthOf',
        }
        if m in dyn_shared and recv in ('Any', 'Any?'):
            call_args = f'{obj}, {args}' if args else obj
            return f'EPLRuntime.{dyn_shared[m]}({call_args})'
        # List mutators on a dynamic receiver (Any) — Kotlin can't see the member,
        # so dispatch through EPLRuntime which casts to MutableList.
        dyn_list_mut = {'add': 'listAdd', 'push': 'listAdd', 'remove': 'listRemove', 'pop': 'listPop'}
        if m in dyn_list_mut and recv in ('Any', 'Any?'):
            call_args = f'{obj}, {args}' if args else obj
            return f'EPLRuntime.{dyn_list_mut[m]}({call_args})'
        # String-only transforms on a dynamic receiver (e.g. a loop var of type
        # Any bound from EPLRuntime.iterate): coerce to String, then dispatch.
        if recv in ('Any', 'Any?') and m in self._DYN_STR_METHODS:
            result = self._string_method(f'({obj}).toString()', m, args)
            if result is not None:
                return result
        km = {
            'add': 'add',
            'push': 'add',
            # EPL list.remove(x) removes the value (Python semantics), not the index.
            'remove': 'remove',
            'upper': 'uppercase',
            'uppercase': 'uppercase',
            'lower': 'lowercase',
            'lowercase': 'lowercase',
            'trim': 'trim',
            'contains': 'contains',
            'replace': 'replace',
            'starts_with': 'startsWith',
            'ends_with': 'endsWith',
            # sort/reverse mutate in place in EPL — Kotlin's sorted()/reversed()
            # return a new list and would silently drop the mutation.
            'reverse': 'reverse',
            'sort': 'sort',
            'substring': 'substring',
            'join': 'joinToString',
            'index_of': 'indexOf',
            'find': 'find',
            'repeat': 'repeat',
        }
        if m == 'length':
            return f'{obj}.size'
        # EPL list.pop() removes and returns the last element (Kotlin has no `pop`).
        if m == 'pop':
            return f'EPLRuntime.listPop({obj})'
        # String.split returns List; EPL lists are MutableList, so normalize.
        if m == 'split':
            return f'{obj}.split({args}).toMutableList()'
        return f'{obj}.{km.get(m, m)}({args})'

    def _expr_dict(self, node):
        def key_expr(k):
            if isinstance(k, str):
                return self._kotlin_str_literal(k)
            if hasattr(k, 'line'):  # AST node
                return self._expr(k)
            return str(k)

        pairs = ', '.join(f'{key_expr(k)} to {self._expr(v)}' for k, v in node.pairs)
        return f'mutableMapOf({pairs})'

    # ─── v6.0+v6.1: Style, Layout, 3D & Canvas (Compose) ────

    _NAMED_COLORS = {
        'red': 'ff0000',
        'green': '00ff00',
        'blue': '0000ff',
        'white': 'ffffff',
        'black': '000000',
        'yellow': 'ffff00',
        'cyan': '00ffff',
        'magenta': 'ff00ff',
        'orange': 'ff8c00',
        'purple': '800080',
        'pink': 'ffc0cb',
        'gray': '808080',
        'grey': '808080',
        'transparent': '000000',
    }

    def _css_color_to_compose(self, color_str):
        """Convert CSS color string to Compose Color()."""
        if not color_str:
            return 'Color.Unspecified'
        c = color_str.strip().lstrip('#')
        if c.lower() in self._NAMED_COLORS:
            c = self._NAMED_COLORS[c.lower()]
        if len(c) == 3 and all(ch in '0123456789abcdefABCDEF' for ch in c):
            c = ''.join(ch * 2 for ch in c)
        if len(c) == 6 and all(ch in '0123456789abcdefABCDEF' for ch in c):
            return f'Color(0xFF{c})'
        return 'Color(0xFF000000)'

    def _css_value_to_dp(self, value):
        """Extract numeric value from CSS size string (e.g., '16px' -> 16)."""
        if isinstance(value, (int, float)):
            return int(value)
        s = (
            str(value)
            .replace('px', '')
            .replace('rem', '')
            .replace('em', '')
            .replace('%', '')
            .strip()
        )
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return 0

    def _parse_duration_ms(self, duration):
        """Parse CSS duration string to milliseconds."""
        d = str(duration or '1s').strip()
        if d.endswith('ms'):
            try:
                return int(float(d[:-2]))
            except ValueError:
                return 1000
        elif d.endswith('s'):
            try:
                return int(float(d[:-1]) * 1000)
            except ValueError:
                return 1000
        try:
            return int(float(d) * 1000)
        except ValueError:
            return 1000

    def _emit_style_def_compose(self, node):
        """Emit @Composable style wrapper function with Modifier chain."""
        self.imports.add('androidx.compose.foundation.background')
        self.imports.add('androidx.compose.foundation.layout.*')
        self.imports.add('androidx.compose.foundation.shape.RoundedCornerShape')
        self.imports.add('androidx.compose.ui.draw.clip')
        self.imports.add('androidx.compose.ui.draw.shadow')
        self.imports.add('androidx.compose.ui.graphics.Color')
        self.imports.add('androidx.compose.ui.unit.dp')
        self.imports.add('androidx.compose.runtime.Composable')

        name = node.name.replace('-', '_').replace(' ', '_').title().replace('_', '')
        self._line('@Composable')
        self._line(f'fun {name}Style(content: @Composable () -> Unit) {{')
        self.indent += 1

        modifiers = []
        for prop in node.properties:
            pname = prop.property_name.lower().replace('-', '_')
            val = prop.value
            if pname == 'background':
                modifiers.append(f'.background({self._css_color_to_compose(val)})')
            elif pname in ('padding', 'padding_all'):
                modifiers.append(f'.padding({self._css_value_to_dp(val)}.dp)')
            elif pname in ('border_radius', 'borderradius'):
                modifiers.append(f'.clip(RoundedCornerShape({self._css_value_to_dp(val)}.dp))')
            elif pname in ('box_shadow', 'boxshadow'):
                modifiers.append(f'.shadow(elevation = {self._css_value_to_dp(val)}.dp)')
            elif pname == 'width':
                modifiers.append(f'.width({self._css_value_to_dp(val)}.dp)')
            elif pname == 'height':
                modifiers.append(f'.height({self._css_value_to_dp(val)}.dp)')
            elif pname == 'opacity':
                modifiers.append(f'.alpha({val}f)')

        mod_chain = 'Modifier' + ''.join(modifiers) if modifiers else 'Modifier'
        self._line(f'Box(modifier = {mod_chain}) {{')
        self.indent += 1
        self._line('content()')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')

    def _emit_styled_element_compose(self, node):
        """Emit Box/Column with Modifier chain from styles, then children."""
        self.imports.add('androidx.compose.foundation.layout.*')
        self.imports.add('androidx.compose.foundation.background')
        self.imports.add('androidx.compose.ui.graphics.Color')
        self.imports.add('androidx.compose.ui.unit.dp')
        self.imports.add('androidx.compose.runtime.Composable')

        modifiers = []
        for prop in node.inline_styles or []:
            pname = prop.property_name.lower().replace('-', '_')
            val = prop.value
            if pname == 'background':
                modifiers.append(f'.background({self._css_color_to_compose(val)})')
            elif pname in ('padding', 'padding_all'):
                modifiers.append(f'.padding({self._css_value_to_dp(val)}.dp)')
            elif pname == 'width':
                modifiers.append(f'.width({self._css_value_to_dp(val)}.dp)')
            elif pname == 'height':
                modifiers.append(f'.height({self._css_value_to_dp(val)}.dp)')

        mod_chain = 'Modifier' + ''.join(modifiers) if modifiers else 'Modifier'
        tag = node.tag
        compose_widget = 'Column' if tag in ('section', 'article', 'main', 'nav') else 'Box'

        self._line(f'{compose_widget}(modifier = {mod_chain}) {{')
        self.indent += 1
        for child in node.children or []:
            self._emit_stmt(child)
        self.indent -= 1
        self._line('}')

    def _emit_layout_container_compose(self, node):
        """Emit Row/Column/LazyVerticalGrid based on layout_type."""
        self.imports.add('androidx.compose.foundation.layout.*')
        self.imports.add('androidx.compose.ui.unit.dp')
        self.imports.add('androidx.compose.runtime.Composable')

        props = node.properties
        gap = self._css_value_to_dp(props.get('gap', '0'))

        if node.layout_type == 'grid':
            self.imports.add('androidx.compose.foundation.lazy.grid.LazyVerticalGrid')
            self.imports.add('androidx.compose.foundation.lazy.grid.GridCells')
            cols = int(props.get('columns', 2))
            self._line('LazyVerticalGrid(')
            self.indent += 1
            self._line(f'columns = GridCells.Fixed({cols}),')
            self._line(f'horizontalArrangement = Arrangement.spacedBy({gap}.dp),')
            self._line(f'verticalArrangement = Arrangement.spacedBy({gap}.dp)')
            self.indent -= 1
            self._line(') {')
            self.indent += 1
            for child in node.children or []:
                self._line('item {')
                self.indent += 1
                self._emit_stmt(child)
                self.indent -= 1
                self._line('}')
            self.indent -= 1
            self._line('}')
        else:
            direction = props.get('direction', 'column')
            container = 'Row' if direction == 'row' else 'Column'
            arrangement = 'horizontalArrangement' if direction == 'row' else 'verticalArrangement'
            self._line(f'{container}({arrangement} = Arrangement.spacedBy({gap}.dp)) {{')
            self.indent += 1
            for child in node.children or []:
                self._emit_stmt(child)
            self.indent -= 1
            self._line('}')

    def _emit_component_def_compose(self, node):
        """Emit @Composable function definition."""
        self.imports.add('androidx.compose.runtime.Composable')
        name = node.name.replace('-', '_').replace(' ', '_')
        param_strs = []
        for p in node.params or []:
            pname = p[0] if isinstance(p, tuple) else str(p)
            param_strs.append(f'{pname}: Any? = null')
        params = ', '.join(param_strs)
        self._line('@Composable')
        self._line(f'fun {name}({params}) {{')
        self.indent += 1
        for stmt in node.body or []:
            self._emit_stmt(stmt)
        self.indent -= 1
        self._line('}')

    def _emit_component_use_compose(self, node):
        """Emit component function call."""
        name = node.component_name.replace('-', '_').replace(' ', '_').title().replace('_', '')
        args = ', '.join(
            f'{k} = {self._expr(v)}' if hasattr(v, 'line') else f'{k} = "{v}"'
            for k, v in (node.arguments or {}).items()
        )
        self._line(f'{name}({args})')

    def _emit_animate_def_compose(self, node):
        """Emit Compose animation using InfiniteTransition or animateFloatAsState."""
        self.imports.add('androidx.compose.animation.core.*')
        self.imports.add('androidx.compose.runtime.*')

        name = node.name.replace('-', '_')
        duration_ms = self._parse_duration_ms(node.duration)
        easing_map = {
            'ease': 'FastOutSlowInEasing',
            'ease-in': 'FastOutLinearInEasing',
            'ease-out': 'LinearOutSlowInEasing',
            'ease-in-out': 'FastOutSlowInEasing',
            'linear': 'LinearEasing',
        }
        easing = easing_map.get(node.easing or 'ease', 'FastOutSlowInEasing')

        if (node.iteration or '1') == 'infinite':
            self._line(f'val {name}Transition = rememberInfiniteTransition()')
            self._line(f'val {name}Anim by {name}Transition.animateFloat(')
            self.indent += 1
            self._line('initialValue = 0f,')
            self._line('targetValue = 1f,')
            self._line('animationSpec = infiniteRepeatable(')
            self.indent += 1
            self._line(f'animation = tween(durationMillis = {duration_ms}, easing = {easing}),')
            self._line('repeatMode = RepeatMode.Restart')
            self.indent -= 1
            self._line(')')
            self.indent -= 1
            self._line(')')
        else:
            self._line(f'val {name}Anim = animateFloatAsState(')
            self.indent += 1
            self._line('targetValue = 1f,')
            self._line(f'animationSpec = tween(durationMillis = {duration_ms}, easing = {easing})')
            self.indent -= 1
            self._line(')')

    def _emit_scene_3d_compose(self, node):
        """Emit 3D scene using Compose Canvas with basic shapes."""
        self.imports.add('androidx.compose.foundation.Canvas')
        self.imports.add('androidx.compose.foundation.layout.size')
        self.imports.add('androidx.compose.ui.graphics.Color')
        self.imports.add('androidx.compose.ui.geometry.Offset')
        self.imports.add('androidx.compose.ui.geometry.Size')
        self.imports.add('androidx.compose.ui.unit.dp')

        w, h = node.width, node.height
        self._line(f'// 3D Scene: {node.name}')
        self._line(f'Canvas(modifier = Modifier.size({w}.dp, {h}.dp)) {{')
        self.indent += 1
        self._line('drawRect(color = Color(0xFF1a1a2e), size = size)')

        for child in node.body:
            if isinstance(child, ast.MeshAdd):
                color = self._css_color_to_compose(child.color or '#667eea')
                px, py = child.position[0], child.position[1]
                sx, sy = child.scale[0], child.scale[1]
                if child.shape == 'cube':
                    self._line(
                        f'drawRect(color = {color}, '
                        f'topLeft = Offset({px + w // 2}f, {py + h // 2}f), '
                        f'size = Size({50 * sx}f, {50 * sy}f))'
                    )
                elif child.shape == 'sphere':
                    self._line(
                        f'drawCircle(color = {color}, '
                        f'radius = {25 * sx}f, '
                        f'center = Offset({px + w // 2}f, {py + h // 2}f))'
                    )
                elif child.shape in ('plane', 'floor'):
                    self._line(
                        f'drawRect(color = {color}, '
                        f'topLeft = Offset(0f, {h - 50}f), '
                        f'size = Size({w}f, 50f))'
                    )

        self.indent -= 1
        self._line('}')

    def _emit_draw_command_compose(self, node):
        """Emit Compose Canvas { drawRect/drawCircle/drawLine/drawPath }."""
        self.imports.add('androidx.compose.foundation.Canvas')
        self.imports.add('androidx.compose.foundation.layout.size')
        self.imports.add('androidx.compose.ui.graphics.Color')
        self.imports.add('androidx.compose.ui.graphics.Path')
        self.imports.add('androidx.compose.ui.graphics.drawscope.Stroke')
        self.imports.add('androidx.compose.ui.geometry.Offset')
        self.imports.add('androidx.compose.ui.geometry.Size')
        self.imports.add('androidx.compose.ui.unit.dp')

        props = node.properties
        shape = node.shape

        self._line('Canvas(modifier = Modifier.size(800.dp, 600.dp)) {')
        self.indent += 1

        if shape == 'rect':
            x, y = props.get('x', 0), props.get('y', 0)
            w, h = props.get('width', 100), props.get('height', 50)
            fill = self._css_color_to_compose(props.get('fill', '#000'))
            self._line(
                f'drawRect(color = {fill}, topLeft = Offset({x}f, {y}f), size = Size({w}f, {h}f))'
            )
        elif shape == 'circle':
            x, y = props.get('x', 50), props.get('y', 50)
            r = props.get('radius', 25)
            fill = self._css_color_to_compose(props.get('fill', '#000'))
            self._line(f'drawCircle(color = {fill}, radius = {r}f, center = Offset({x}f, {y}f))')
        elif shape == 'line':
            x1, y1 = props.get('x1', 0), props.get('y1', 0)
            x2, y2 = props.get('x2', 100), props.get('y2', 100)
            stroke = self._css_color_to_compose(props.get('stroke', '#000'))
            lw = props.get('width', 1)
            self._line(
                f'drawLine(color = {stroke}, '
                f'start = Offset({x1}f, {y1}f), '
                f'end = Offset({x2}f, {y2}f), '
                f'strokeWidth = {lw}f)'
            )
        elif shape == 'text':
            self._line('// Text drawing requires native canvas')
            x, y = props.get('x', 10), props.get('y', 30)
            content = props.get('content', '')
            fill = self._css_color_to_compose(props.get('fill', '#000'))
            self._line(
                f'drawContext.canvas.nativeCanvas.drawText("{content}", '
                f'{x}f, {y}f, android.graphics.Paint().apply {{ color = {fill}.toArgb() }})'
            )
        elif shape == 'path':
            points = props.get('points', '')
            fill = self._css_color_to_compose(props.get('fill', '#000'))
            self._line(f'// SVG Path: {points}')
            self._line('val path = Path()')
            self._line(f'drawPath(path = path, color = {fill})')

        self.indent -= 1
        self._line('}')


class AndroidProjectGenerator:
    """Generates a complete Android project structure from EPL source."""

    GRADLE_WRAPPER_VERSION = ANDROID_GRADLE_WRAPPER_VERSION
    ANDROID_PLUGIN_VERSION = ANDROID_GRADLE_PLUGIN_VERSION
    KOTLIN_VERSION = ANDROID_KOTLIN_VERSION

    def __init__(self, app_name='EPLApp', package_name='com.epl.app'):
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
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/MainActivity.kt', activity_code
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/EPLRuntime.kt',
            self._epl_runtime_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/EPLApplication.kt',
            self._application_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/DetailActivity.kt',
            self._detail_activity_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/SettingsActivity.kt',
            self._settings_activity_kt(),
        )
        # Data layer: Room + Retrofit
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/data/Repository.kt',
            self._repository_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/data/model/EPLEntity.kt',
            self._room_entity_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/data/local/EPLDao.kt',
            self._room_dao_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/data/local/EPLDatabase.kt',
            self._room_database_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/data/remote/ApiService.kt',
            self._retrofit_api_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/data/remote/RetrofitClient.kt',
            self._retrofit_client_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/di/ServiceLocator.kt',
            self._service_locator_kt(),
        )
        # UI layer
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/ui/MainViewModel.kt',
            self._viewmodel_kt(),
        )
        self._write(
            f'{output_dir}/app/src/main/java/{self.package_path}/ui/ItemAdapter.kt',
            self._adapter_kt(),
        )
        # Resources
        self._write(f'{output_dir}/app/src/main/AndroidManifest.xml', self._manifest())
        self._write(
            f'{output_dir}/app/src/main/res/layout/activity_main.xml',
            self._layout_from_widgets(gen.widgets),
        )
        self._write(
            f'{output_dir}/app/src/main/res/layout/activity_detail.xml', self._detail_layout()
        )
        self._write(
            f'{output_dir}/app/src/main/res/layout/activity_settings.xml', self._settings_layout()
        )
        self._write(f'{output_dir}/app/src/main/res/layout/item_list.xml', self._item_layout())
        self._write(f'{output_dir}/app/src/main/res/menu/main_menu.xml', self._main_menu())
        self._write(f'{output_dir}/app/src/main/res/navigation/nav_graph.xml', self._nav_graph())
        self._write(f'{output_dir}/app/src/main/res/values/strings.xml', self._strings())
        self._write(f'{output_dir}/app/src/main/res/values/themes.xml', self._themes())
        self._write(f'{output_dir}/app/src/main/res/values/colors.xml', self._colors())
        self._write(f'{output_dir}/app/src/main/res/values/dimens.xml', self._dimens())
        self._write(f'{output_dir}/app/src/main/res/values-night/themes.xml', self._themes_night())
        self._write(
            f'{output_dir}/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml',
            self._adaptive_icon(),
        )
        self._write(
            f'{output_dir}/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml',
            self._adaptive_icon_round(),
        )
        self._write(
            f'{output_dir}/app/src/main/res/drawable/ic_launcher_foreground.xml',
            self._icon_foreground(),
        )
        self._write(
            f'{output_dir}/app/src/main/res/drawable/ic_launcher_background.xml',
            self._icon_background(),
        )
        self._write(f'{output_dir}/app/build.gradle.kts', self._app_gradle(use_compose=use_compose))
        self._write(f'{output_dir}/build.gradle.kts', self._root_gradle())
        self._write(f'{output_dir}/settings.gradle.kts', self._settings())
        self._write(f'{output_dir}/gradle.properties', self._gradle_props())
        self._copy_gradle_wrapper_assets(output_dir)
        self._write(
            f'{output_dir}/gradle/wrapper/gradle-wrapper.properties', self._gradle_wrapper_props()
        )
        self._write(f'{output_dir}/app/proguard-rules.pro', self._proguard_rules())
        self._write(f'{output_dir}/.gitignore', self._gitignore())
        self._write(f'{output_dir}/local.properties', self._local_properties())
        self._write(f'{output_dir}/README.md', self._readme())
        # Test files
        self._write(
            f'{output_dir}/app/src/test/java/{self.package_path}/EPLRuntimeTest.kt',
            self._unit_test_kt(),
        )
        self._write(
            f'{output_dir}/app/src/androidTest/java/{self.package_path}/MainActivityTest.kt',
            self._instrumented_test_kt(),
        )

        # Make gradlew executable on Unix
        try:
            os.chmod(f'{output_dir}/gradlew', 0o755)
        except Exception:
            _debug_log.suppressed('kotlin_gen:2220')

        return output_dir

    def _write(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _copy_gradle_wrapper_assets(self, output_dir):
        output_root = Path(output_dir)
        assets = (
            ('gradlew', 'gradlew'),
            ('gradlew.bat', 'gradlew.bat'),
            ('gradle/wrapper/gradle-wrapper.jar', 'gradle/wrapper/gradle-wrapper.jar'),
        )
        for source_rel, dest_rel in assets:
            source = ANDROID_TEMPLATE_ROOT / source_rel
            destination = output_root / dest_rel
            if not source.exists():
                raise FileNotFoundError(f'Missing Android wrapper asset: {source}')
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
        return f"""<?xml version="1.0" encoding="utf-8"?>
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
</ScrollView>"""

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
            extra = (
                '\n        android:scaleType="fitCenter"\n        android:adjustViewBounds="true"'
            )

        return f'''    <{xml_type}
        android:id="@+id/{wid}"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"{text_attr}{hint_attr}{extra}
        android:layout_marginBottom="8dp" />'''

    def _layout_default(self):
        return """<?xml version="1.0" encoding="utf-8"?>
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

</LinearLayout>"""

    def _strings(self):
        return f"""<resources>
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
</resources>"""

    def _themes(self):
        return """<resources>
    <style name="Theme.EPLApp" parent="Theme.MaterialComponents.DayNight.DarkActionBar">
        <item name="colorPrimary">@color/primary</item>
        <item name="colorPrimaryVariant">@color/primary_dark</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorSecondary">@color/accent</item>
        <item name="colorOnSecondary">@color/white</item>
    </style>
</resources>"""

    def _themes_night(self):
        return """<resources>
    <style name="Theme.EPLApp" parent="Theme.MaterialComponents.DayNight.DarkActionBar">
        <item name="colorPrimary">@color/primary_night</item>
        <item name="colorPrimaryVariant">@color/primary_dark_night</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorSecondary">@color/accent_night</item>
        <item name="colorOnSecondary">@color/white</item>
        <item name="android:statusBarColor">@color/primary_dark_night</item>
        <item name="android:navigationBarColor">@color/background_dark</item>
    </style>
</resources>"""

    def _colors(self):
        return """<resources>
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
</resources>"""

    def _app_gradle(self, use_compose=False):
        compose_plugin = '\n    id("org.jetbrains.kotlin.plugin.compose")' if use_compose else ''
        compose_build_features = (
            """
    buildFeatures {
        compose = true
        viewBinding = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }"""
            if use_compose
            else """
    buildFeatures {
        viewBinding = true
    }"""
        )
        compose_deps = (
            """
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
"""
            if use_compose
            else ''
        )
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
        return """android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true"""

    def _gradlew_unix(self):
        return (ANDROID_TEMPLATE_ROOT / 'gradlew').read_text(encoding='utf-8')

    def _gradlew_bat(self):
        return (ANDROID_TEMPLATE_ROOT / 'gradlew.bat').read_text(encoding='utf-8')

    def _gradle_wrapper_props(self):
        return f"""distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{self.GRADLE_WRAPPER_VERSION}-bin.zip
networkTimeout=120000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists"""

    def _readme(self):
        return f"""# {self.app_name}

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
"""

    def _proguard_rules(self):
        return (
            """# EPL Generated App ProGuard Rules
# Keep EPL runtime classes
-keep class """
            + self.package
            + """.** { *; }

# Keep Material Components
-keep class com.google.android.material.** { *; }

# General Android rules
-keepclassmembers class * implements android.os.Parcelable {
    static ** CREATOR;
}
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
}
"""
        )

    def _gitignore(self):
        return """*.iml
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
"""

    def _epl_runtime_kt(self):
        # Single source of truth for the runtime shim lives in epl.kotlin_runtime;
        # the Android assembly is byte-identical to the historically verified APK
        # runtime (locked by tests/test_kotlin_runtime_golden.py).
        from epl.kotlin_runtime import android_runtime

        return android_runtime(self.package)

    def _application_kt(self):
        return f"""package {self.package}

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
"""

    def _detail_activity_kt(self):
        return f"""package {self.package}

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
"""

    def _settings_activity_kt(self):
        return f"""package {self.package}

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
"""

    def _repository_kt(self):
        return f"""package {self.package}.data

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
"""

    def _room_entity_kt(self):
        return f"""package {self.package}.data.model

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
"""

    def _room_dao_kt(self):
        return f"""package {self.package}.data.local

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
"""

    def _room_database_kt(self):
        return f"""package {self.package}.data.local

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
"""

    def _retrofit_api_kt(self):
        return f"""package {self.package}.data.remote

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
"""

    def _retrofit_client_kt(self):
        return f"""package {self.package}.data.remote

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
"""

    def _service_locator_kt(self):
        return f"""package {self.package}.di

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
"""

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
        return f"""package {self.package}.ui

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
"""

    def _adapter_kt(self):
        return f"""package {self.package}.ui

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
"""

    def _detail_layout(self):
        return """<?xml version="1.0" encoding="utf-8"?>
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
</ScrollView>"""

    def _settings_layout(self):
        return """<?xml version="1.0" encoding="utf-8"?>
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
</LinearLayout>"""

    def _item_layout(self):
        return """<?xml version="1.0" encoding="utf-8"?>
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
</com.google.android.material.card.MaterialCardView>"""

    def _main_menu(self):
        return """<?xml version="1.0" encoding="utf-8"?>
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
</menu>"""

    def _dimens(self):
        return """<resources>
    <dimen name="screen_padding">16dp</dimen>
    <dimen name="item_margin">8dp</dimen>
    <dimen name="text_title">24sp</dimen>
    <dimen name="text_body">16sp</dimen>
    <dimen name="text_caption">12sp</dimen>
    <dimen name="corner_radius">8dp</dimen>
    <dimen name="elevation_card">2dp</dimen>
</resources>"""

    def _adaptive_icon(self):
        return """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background"/>
    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
</adaptive-icon>"""

    def _adaptive_icon_round(self):
        return """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background"/>
    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
</adaptive-icon>"""

    def _icon_foreground(self):
        return """<?xml version="1.0" encoding="utf-8"?>
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
</vector>"""

    def _icon_background(self):
        return """<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#3b82f6"
        android:pathData="M0,0h108v108h-108z"/>
</vector>"""

    def _local_properties(self):
        return """# This file should NOT be checked into version control.
# Set sdk.dir to point to your Android SDK installation.
# sdk.dir=/path/to/android/sdk
"""

    def _unit_test_kt(self):
        return f"""package {self.package}

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
"""

    def _instrumented_test_kt(self):
        return f"""package {self.package}

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
"""


def transpile_to_kotlin(program: ast.Program, package='com.epl.app', include_runtime=True) -> str:
    """Convenience: transpile EPL AST to a single self-contained Kotlin file.

    include_runtime defaults True so the emitted `.kt` compiles standalone
    (bundles the EPLRuntime shim). Callers embedding into a project that already
    ships EPLRuntime can pass False.
    """
    return KotlinGenerator(package).generate(program, include_runtime=include_runtime)


def generate_android_project(
    program: ast.Program, output_dir: str, app_name='EPLApp', package='com.epl.app'
):
    """Convenience: generate a full Android project from EPL."""
    gen = AndroidProjectGenerator(app_name, package)
    return gen.generate(program, output_dir)
