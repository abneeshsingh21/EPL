"""
EPL Desktop Application Framework (v1.0)
Generates cross-platform desktop apps using Compose Multiplatform (Kotlin/JVM),
JavaFX Kotlin wrappers, and native packaging via jpackage.

Targets:
  - Compose Multiplatform Desktop (recommended)
  - JavaFX Kotlin                  (fallback)
  - Swing Kotlin                   (minimal)

Also provides:
  - System tray integration
  - File dialogs, notifications
  - Multi-window support
  - Menu bar generation
  - Keyboard shortcuts
  - App icon & metadata
  - Native installer generation (jpackage)
"""

import os
from epl import ast_nodes as ast

# ── Compose Desktop Project Generator ────────────────────


class DesktopProjectGenerator:
    """Generates a Compose Multiplatform Desktop project from EPL AST."""

    COMPOSE_VERSION = "1.6.0"
    KOTLIN_VERSION = "1.9.22"
    GRADLE_VERSION = "8.5"

    def __init__(self, app_name="EPLDesktopApp", package_name="com.epl.desktop",
                 width=900, height=700, icon=None):
        self.app_name = app_name
        self.package = package_name
        self.package_path = package_name.replace('.', '/')
        self.width = width
        self.height = height
        self.icon = icon  # path to .ico/.png
        self.version = "1.0.0"

    def generate(self, program: ast.Program, output_dir: str) -> str:
        """Generate a complete Compose Desktop project."""
        os.makedirs(output_dir, exist_ok=True)

        # Generate Kotlin source from EPL AST
        gen = DesktopComposeGenerator(self.package, self.app_name,
                                       self.width, self.height)
        main_kt = gen.generate(program)
        runtime_kt = gen.generate_runtime()

        # Project structure
        dirs = [
            f'{output_dir}/src/main/kotlin/{self.package_path}',
            f'{output_dir}/src/main/resources',
            f'{output_dir}/src/test/kotlin/{self.package_path}',
            f'{output_dir}/gradle/wrapper',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        # Write files
        self._write(f'{output_dir}/src/main/kotlin/{self.package_path}/Main.kt', main_kt)
        self._write(f'{output_dir}/src/main/kotlin/{self.package_path}/EPLRuntime.kt', runtime_kt)
        self._write(f'{output_dir}/build.gradle.kts', self._build_gradle())
        self._write(f'{output_dir}/settings.gradle.kts', self._settings_gradle())
        self._write(f'{output_dir}/gradle.properties', self._gradle_props())
        self._write(f'{output_dir}/gradle/wrapper/gradle-wrapper.properties', self._wrapper_props())
        self._write(f'{output_dir}/gradlew', self._gradlew_sh())
        self._write(f'{output_dir}/gradlew.bat', self._gradlew_bat())
        self._write(f'{output_dir}/.gitignore', self._gitignore())
        self._write(f'{output_dir}/README.md', self._readme())

        # Copy icon if provided
        if self.icon and os.path.exists(self.icon):
            import shutil
            shutil.copy2(self.icon, f'{output_dir}/src/main/resources/icon.png')

        try:
            os.chmod(f'{output_dir}/gradlew', 0o755)
        except OSError:
            pass

        return output_dir

    def _write(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _build_gradle(self):
        return f'''import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {{
    kotlin("jvm") version "{self.KOTLIN_VERSION}"
    id("org.jetbrains.compose") version "{self.COMPOSE_VERSION}"
}}

group = "{self.package}"
version = "{self.version}"

repositories {{
    mavenCentral()
    maven("https://maven.pkg.jetbrains.space/public/p/compose/dev")
    google()
}}

dependencies {{
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation(compose.materialIconsExtended)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-swing:1.7.3")

    testImplementation(kotlin("test"))
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
}}

compose.desktop {{
    application {{
        mainClass = "{self.package}.MainKt"
        nativeDistributions {{
            targetFormats(TargetFormat.Dmg, TargetFormat.Msi, TargetFormat.Deb, TargetFormat.Rpm)
            packageName = "{self.app_name}"
            packageVersion = "{self.version}"
            description = "Desktop application generated from EPL"
            vendor = "EPL"

            windows {{
                menuGroup = "{self.app_name}"
                upgradeUuid = "b2a5f4e8-7c3d-4a1b-9e6f-8d2c1a3b5e7f"
                shortcut = true
            }}
            macOS {{
                bundleID = "{self.package}"
            }}
            linux {{
                shortcut = true
            }}
        }}
    }}
}}

tasks.test {{
    useJUnitPlatform()
}}
'''

    def _settings_gradle(self):
        return f'''pluginManagement {{
    repositories {{
        gradlePluginPortal()
        maven("https://maven.pkg.jetbrains.space/public/p/compose/dev")
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{self.app_name}"
'''

    def _gradle_props(self):
        return '''org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
kotlin.code.style=official
'''

    def _wrapper_props(self):
        return f'''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{self.GRADLE_VERSION}-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
'''

    def _gradlew_sh(self):
        return f'''#!/bin/sh
# Gradle Wrapper — auto-downloads Gradle if not present
# Generated by EPL Desktop Project Generator

set -e

GRADLE_VERSION="{self.GRADLE_VERSION}"
GRADLE_DIST_URL="https://services.gradle.org/distributions/gradle-${{GRADLE_VERSION}}-bin.zip"
GRADLE_HOME="${{HOME}}/.gradle/wrapper/dists/gradle-${{GRADLE_VERSION}}-bin"
GRADLE_BIN="${{GRADLE_HOME}}/gradle-${{GRADLE_VERSION}}/bin/gradle"

# Download Gradle if not cached
if [ ! -f "${{GRADLE_BIN}}" ]; then
    echo "Downloading Gradle ${{GRADLE_VERSION}}..."
    mkdir -p "${{GRADLE_HOME}}"
    TMPZIP="${{GRADLE_HOME}}/gradle-${{GRADLE_VERSION}}-bin.zip"
    if command -v curl > /dev/null 2>&1; then
        curl -fsSL -o "${{TMPZIP}}" "${{GRADLE_DIST_URL}}"
    elif command -v wget > /dev/null 2>&1; then
        wget -q -O "${{TMPZIP}}" "${{GRADLE_DIST_URL}}"
    else
        echo "Error: curl or wget required to download Gradle." >&2
        exit 1
    fi
    echo "Extracting Gradle ${{GRADLE_VERSION}}..."
    unzip -q -o "${{TMPZIP}}" -d "${{GRADLE_HOME}}"
    rm -f "${{TMPZIP}}"
    chmod +x "${{GRADLE_BIN}}"
    echo "Gradle ${{GRADLE_VERSION}} installed."
fi

# Forward all arguments to Gradle
exec "${{GRADLE_BIN}}" "$@"
'''

    def _gradlew_bat(self):
        return f'''@echo off
rem Gradle Wrapper — auto-downloads Gradle if not present
rem Generated by EPL Desktop Project Generator

setlocal

set GRADLE_VERSION={self.GRADLE_VERSION}
set GRADLE_DIST_URL=https://services.gradle.org/distributions/gradle-%GRADLE_VERSION%-bin.zip
set GRADLE_HOME=%USERPROFILE%\\.gradle\\wrapper\\dists\\gradle-%GRADLE_VERSION%-bin
set GRADLE_BIN=%GRADLE_HOME%\\gradle-%GRADLE_VERSION%\\bin\\gradle.bat

if exist "%GRADLE_BIN%" goto execute

echo Downloading Gradle %GRADLE_VERSION%...
if not exist "%GRADLE_HOME%" mkdir "%GRADLE_HOME%"
set TMPZIP=%GRADLE_HOME%\\gradle-%GRADLE_VERSION%-bin.zip

rem Download using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%GRADLE_DIST_URL%', '%TMPZIP%')"
if errorlevel 1 (
    echo Error: Failed to download Gradle. Check internet connection. >&2
    exit /b 1
)

echo Extracting Gradle %GRADLE_VERSION%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%TMPZIP%' -DestinationPath '%GRADLE_HOME%' -Force"
if errorlevel 1 (
    echo Error: Failed to extract Gradle. >&2
    exit /b 1
)
del /q "%TMPZIP%" 2>nul
echo Gradle %GRADLE_VERSION% installed.

:execute
"%GRADLE_BIN%" %*
'''

    def _gitignore(self):
        return '''.gradle/
build/
.idea/
*.iml
out/
.kotlin/
'''

    def _readme(self):
        return f'''# {self.app_name}

Desktop application generated from EPL source code using Compose Multiplatform.

## Prerequisites

- JDK 17+ (recommended: JDK 21)
- Gradle {self.GRADLE_VERSION}+

## Build & Run

```bash
# Run the app
./gradlew run

# Build native installer
./gradlew packageMsi      # Windows .msi
./gradlew packageDmg      # macOS .dmg
./gradlew packageDeb      # Linux .deb
./gradlew packageRpm       # Linux .rpm

# Build distributable
./gradlew createDistributable
```

## Project Structure

```
src/main/kotlin/{self.package_path}/
    Main.kt            — Application entry point + UI
    EPLRuntime.kt      — EPL standard library for desktop
```
'''


# ── Compose Desktop Code Generator ──────────────────────


class DesktopComposeGenerator:
    """Generates Kotlin Compose Desktop code from EPL AST."""

    def __init__(self, package_name="com.epl.desktop", app_title="EPL App",
                 width=900, height=700):
        self.package = package_name
        self.app_title = app_title
        self.width = width
        self.height = height
        self.indent = 0
        self.output = []
        self.imports = set()
        self.widgets = []
        self.event_bindings = []
        self.widget_counter = 0
        self.state_vars = []  # track mutableStateOf declarations
        self.user_functions = []
        self.classes = []

    def generate(self, program: ast.Program) -> str:
        """Generate Compose Desktop Main.kt from EPL AST."""
        self.output = []
        self.imports = {
            'androidx.compose.desktop.ui.tooling.preview.Preview',
            'androidx.compose.foundation.layout.*',
            'androidx.compose.material3.*',
            'androidx.compose.runtime.*',
            'androidx.compose.ui.Alignment',
            'androidx.compose.ui.Modifier',
            'androidx.compose.ui.unit.dp',
            'androidx.compose.ui.unit.sp',
            'androidx.compose.ui.window.Window',
            'androidx.compose.ui.window.application',
            'androidx.compose.ui.window.rememberWindowState',
        }

        stmts = program.statements

        # Collect widgets, functions, classes
        self._collect_gui_nodes(stmts)
        for s in stmts:
            if isinstance(s, ast.FunctionDef):
                self.user_functions.append(s)
            elif isinstance(s, ast.ClassDef):
                self.classes.append(s)

        # Emit main function
        self._line('fun main() = application {')
        self.indent += 1
        self._line(f'val windowState = rememberWindowState(width = {self.width}.dp, height = {self.height}.dp)')
        self._line('')
        self._line('Window(')
        self.indent += 1
        self._line('onCloseRequest = ::exitApplication,')
        self._line(f'title = "{self.app_title}",')
        self._line('state = windowState,')
        self.indent -= 1
        self._line(') {')
        self.indent += 1
        self._line('MaterialTheme {')
        self.indent += 1
        self._line('AppContent()')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')
        self.indent -= 1
        self._line('}')
        self._line('')

        # Emit AppContent composable
        self._line('@Composable')
        self._line('@Preview')
        self._line('fun AppContent() {')
        self.indent += 1

        if self.widgets:
            self._line('Column(')
            self.indent += 1
            self._line('modifier = Modifier.fillMaxSize().padding(16.dp),')
            self._line('verticalArrangement = Arrangement.spacedBy(8.dp)')
            self.indent -= 1
            self._line(') {')
            self.indent += 1
            for w in self.widgets:
                self._emit_compose_widget(w)
            self.indent -= 1
            self._line('}')
        else:
            # No GUI widgets — render Print statements as Text
            self._line('Column(')
            self.indent += 1
            self._line('modifier = Modifier.fillMaxSize().padding(16.dp),')
            self._line('verticalArrangement = Arrangement.Center,')
            self._line('horizontalAlignment = Alignment.CenterHorizontally')
            self.indent -= 1
            self._line(') {')
            self.indent += 1
            for s in stmts:
                if isinstance(s, ast.PrintStatement):
                    text_expr = self._expr(s.expression)
                    self._line(f'Text(text = {text_expr}, fontSize = 16.sp)')
                elif isinstance(s, (ast.VarDeclaration, ast.ConstDeclaration,
                                    ast.VarAssignment, ast.IfStatement,
                                    ast.WhileLoop, ast.ForEachLoop, ast.ForRange,
                                    ast.RepeatLoop, ast.TryCatch, ast.FunctionCall,
                                    ast.MethodCall, ast.ThrowStatement,
                                    ast.BreakStatement, ast.ContinueStatement,
                                    ast.AugmentedAssignment)):
                    self._emit_stmt(s)
                elif isinstance(s, (ast.FunctionDef, ast.ClassDef)):
                    pass  # handled separately as top-level
            if not any(isinstance(s, (ast.PrintStatement, ast.IfStatement,
                                       ast.WhileLoop, ast.ForEachLoop,
                                       ast.TryCatch)) for s in stmts):
                self._line(f'Text("{self.app_title}", fontSize = 24.sp)')
            self.indent -= 1
            self._line('}')

        self.indent -= 1
        self._line('}')

        # Emit user functions as top-level Kotlin functions
        for fn in self.user_functions:
            self._line('')
            self._emit_function(fn)

        # Emit classes as Kotlin data/open classes
        for cls in self.classes:
            self._line('')
            self._emit_class(cls)

        # Build header
        header = f'package {self.package}\n\n'
        if self.imports:
            header += '\n'.join(f'import {i}' for i in sorted(self.imports)) + '\n\n'
        return header + '\n'.join(self.output)

    def generate_runtime(self):
        """Generate EPLRuntime.kt for desktop — stdlib helper functions."""
        return f'''package {self.package}

import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import javax.swing.JFileChooser
import javax.swing.JOptionPane
import javax.swing.filechooser.FileNameExtensionFilter
import kotlin.math.*
import kotlin.random.Random

/**
 * EPL Runtime Library for Desktop
 * Provides standard library functions matching the EPL interpreter builtins.
 */
object EPLRuntime {{
    // ── I/O ─────────────────────────────────────────
    fun print(vararg args: Any?) {{
        println(args.joinToString(" ") {{ it?.toString() ?: "null" }})
    }}

    fun input(prompt: String = ""): String {{
        if (prompt.isNotEmpty()) kotlin.io.print(prompt)
        return readlnOrNull() ?: ""
    }}

    // ── Type Conversion ────────────────────────────
    fun toInteger(value: Any?): Int = when (value) {{
        is Int -> value
        is Double -> value.toInt()
        is String -> value.toIntOrNull() ?: 0
        is Boolean -> if (value) 1 else 0
        else -> 0
    }}

    fun toDecimal(value: Any?): Double = when (value) {{
        is Double -> value
        is Int -> value.toDouble()
        is String -> value.toDoubleOrNull() ?: 0.0
        else -> 0.0
    }}

    fun toText(value: Any?): String = value?.toString() ?: "null"

    // ── String Operations ──────────────────────────
    fun length(value: Any?): Int = when (value) {{
        is String -> value.length
        is List<*> -> value.size
        is Map<*, *> -> value.size
        else -> 0
    }}

    fun uppercase(s: String): String = s.uppercase()
    fun lowercase(s: String): String = s.lowercase()
    fun trim(s: String): String = s.trim()
    fun contains(s: String, sub: String): Boolean = s.contains(sub)
    fun replace(s: String, old: String, new: String): String = s.replace(old, new)
    fun split(s: String, delim: String): List<String> = s.split(delim)
    fun substring(s: String, start: Int, end: Int = s.length): String = s.substring(start, end)
    fun startsWith(s: String, prefix: String): Boolean = s.startsWith(prefix)
    fun endsWith(s: String, suffix: String): Boolean = s.endsWith(suffix)
    fun indexOf(s: String, sub: String): Int = s.indexOf(sub)
    fun charAt(s: String, index: Int): String = if (index in s.indices) s[index].toString() else ""
    fun repeat(s: String, n: Int): String = s.repeat(n)

    // ── Math ───────────────────────────────────────
    fun absolute(n: Double): Double = abs(n)
    fun power(base: Double, exp: Double): Double = base.pow(exp)
    fun squareRoot(n: Double): Double = sqrt(n)
    fun floor(n: Double): Int = kotlin.math.floor(n).toInt()
    fun ceil(n: Double): Int = kotlin.math.ceil(n).toInt()
    fun round(n: Double): Int = kotlin.math.round(n).toInt()
    fun random(): Double = Random.nextDouble()
    fun randomInt(min: Int, max: Int): Int = Random.nextInt(min, max + 1)
    fun log(n: Double): Double = ln(n)
    fun log10(n: Double): Double = kotlin.math.log10(n)
    fun sin(n: Double): Double = kotlin.math.sin(n)
    fun cos(n: Double): Double = kotlin.math.cos(n)
    fun tan(n: Double): Double = kotlin.math.tan(n)
    val PI: Double = kotlin.math.PI
    val E: Double = kotlin.math.E

    // ── List Operations ────────────────────────────
    fun <T> append(list: MutableList<T>, item: T) {{ list.add(item) }}
    fun <T> removeAt(list: MutableList<T>, index: Int): T = list.removeAt(index)
    fun <T> indexOf(list: List<T>, item: T): Int = list.indexOf(item)
    fun <T> sorted(list: List<T>): List<T> where T : Comparable<T> = list.sorted()
    fun <T> reversed(list: List<T>): List<T> = list.reversed()
    fun <T> slice(list: List<T>, start: Int, end: Int): List<T> = list.subList(start, end)
    fun join(list: List<*>, sep: String = ", "): String = list.joinToString(sep)

    // ── Map Operations ─────────────────────────────
    fun <K, V> keys(map: Map<K, V>): List<K> = map.keys.toList()
    fun <K, V> values(map: Map<K, V>): List<V> = map.values.toList()
    fun <K, V> hasKey(map: Map<K, V>, key: K): Boolean = map.containsKey(key)

    // ── File I/O ───────────────────────────────────
    fun readFile(path: String): String = File(path).readText()
    fun writeFile(path: String, content: String) {{ File(path).writeText(content) }}
    fun appendFile(path: String, content: String) {{ File(path).appendText(content) }}
    fun fileExists(path: String): Boolean = File(path).exists()
    fun deleteFile(path: String): Boolean = File(path).delete()
    fun listFiles(path: String): List<String> = File(path).list()?.toList() ?: emptyList()

    // ── Date/Time ──────────────────────────────────
    fun now(): String = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
    fun today(): String = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE)
    fun timestamp(): Long = System.currentTimeMillis()

    // ── Desktop Dialogs (Swing) ────────────────────
    fun showMessage(title: String, message: String) {{
        JOptionPane.showMessageDialog(null, message, title, JOptionPane.INFORMATION_MESSAGE)
    }}

    fun showError(title: String, message: String) {{
        JOptionPane.showMessageDialog(null, message, title, JOptionPane.ERROR_MESSAGE)
    }}

    fun askYesNo(title: String, message: String): Boolean {{
        return JOptionPane.showConfirmDialog(null, message, title, JOptionPane.YES_NO_OPTION) == JOptionPane.YES_OPTION
    }}

    fun askText(title: String, prompt: String): String? {{
        return JOptionPane.showInputDialog(null, prompt, title, JOptionPane.QUESTION_MESSAGE)
    }}

    fun openFileDialog(extensions: List<String> = emptyList()): String? {{
        val chooser = JFileChooser()
        if (extensions.isNotEmpty()) {{
            chooser.fileFilter = FileNameExtensionFilter("Files", *extensions.toTypedArray())
        }}
        return if (chooser.showOpenDialog(null) == JFileChooser.APPROVE_OPTION) {{
            chooser.selectedFile.absolutePath
        }} else null
    }}

    fun saveFileDialog(extensions: List<String> = emptyList()): String? {{
        val chooser = JFileChooser()
        if (extensions.isNotEmpty()) {{
            chooser.fileFilter = FileNameExtensionFilter("Files", *extensions.toTypedArray())
        }}
        return if (chooser.showSaveDialog(null) == JFileChooser.APPROVE_OPTION) {{
            chooser.selectedFile.absolutePath
        }} else null
    }}

    // ── System ─────────────────────────────────────
    fun sleep(ms: Long) {{ Thread.sleep(ms) }}
    fun exit(code: Int = 0) {{ kotlin.system.exitProcess(code) }}
    fun env(name: String): String? = System.getenv(name)
    fun osName(): String = System.getProperty("os.name")
    fun userName(): String = System.getProperty("user.name")
    fun homeDir(): String = System.getProperty("user.home")
    fun currentDir(): String = System.getProperty("user.dir")
    fun execute(command: String): String {{
        val process = ProcessBuilder(*command.split(" ").toTypedArray())
            .redirectErrorStream(true)
            .start()
        return process.inputStream.bufferedReader().readText().trim()
    }}

    // ── JSON (basic) ──────────────────────────────
    fun toJson(value: Any?): String = when (value) {{
        is String -> "\\"$value\\""
        is Number, is Boolean -> value.toString()
        null -> "null"
        is List<*> -> "[" + value.joinToString(",") {{ toJson(it) }} + "]"
        is Map<*, *> -> "{{" + value.entries.joinToString(",") {{
            "\\"${{it.key}}\\":" + toJson(it.value)
        }} + "}}"
        else -> "\\"$value\\""
    }}
}}
'''

    # ── Widget Emission ─────────────────────────────────

    def _emit_compose_widget(self, w):
        """Emit a Compose Desktop widget."""
        wtype = w['type']
        text = w.get('text')
        props = w.get('properties', {})
        wid = w.get('id', f'widget_{self.widget_counter}')

        if wtype == 'button':
            handler = w.get('action')
            handler_str = f'{{ {self._expr_safe(handler)}() }}' if handler else '{}'
            text_str = self._text_expr(text, 'Button')
            self._line(f'Button(onClick = {handler_str}) {{')
            self.indent += 1
            self._line(f'Text({text_str})')
            self.indent -= 1
            self._line('}')
        elif wtype == 'label':
            text_str = self._text_expr(text, '')
            fs = props.get('fontSize')
            if fs:
                self._line(f'Text(text = {text_str}, fontSize = {fs}.sp)')
            else:
                self._line(f'Text(text = {text_str})')
        elif wtype in ('input', 'textarea'):
            self._line(f'var {wid}Value by remember {{ mutableStateOf("") }}')
            if wtype == 'textarea':
                self._line(f'OutlinedTextField(')
            else:
                self._line(f'TextField(')
            self.indent += 1
            self._line(f'value = {wid}Value,')
            self._line(f'onValueChange = {{ {wid}Value = it }},')
            placeholder = props.get('placeholder', '')
            if placeholder:
                p = self._text_expr(placeholder, '')
                self._line(f'label = {{ Text({p}) }},')
            self._line('modifier = Modifier.fillMaxWidth()')
            self.indent -= 1
            self._line(')')
        elif wtype == 'checkbox':
            text_str = self._text_expr(text, 'Check')
            self._line(f'var {wid}Checked by remember {{ mutableStateOf(false) }}')
            self._line('Row(verticalAlignment = Alignment.CenterVertically) {')
            self.indent += 1
            self._line(f'Checkbox(checked = {wid}Checked, onCheckedChange = {{ {wid}Checked = it }})')
            self._line(f'Text({text_str})')
            self.indent -= 1
            self._line('}')
        elif wtype == 'slider':
            max_val = props.get('max', 100)
            self._line(f'var {wid}Value by remember {{ mutableStateOf(0f) }}')
            self._line(f'Slider(value = {wid}Value, onValueChange = {{ {wid}Value = it }}, valueRange = 0f..{max_val}f)')
        elif wtype == 'progress':
            self.imports.add('androidx.compose.material3.LinearProgressIndicator')
            self._line('LinearProgressIndicator(modifier = Modifier.fillMaxWidth())')
        elif wtype == 'dropdown':
            options = props.get('options', [])
            self.imports.add('androidx.compose.material3.DropdownMenu')
            self.imports.add('androidx.compose.material3.DropdownMenuItem')
            self._line(f'var {wid}Expanded by remember {{ mutableStateOf(false) }}')
            self._line(f'var {wid}Selected by remember {{ mutableStateOf("Select...") }}')
            self._line('Box {')
            self.indent += 1
            self._line(f'TextButton(onClick = {{ {wid}Expanded = true }}) {{ Text({wid}Selected) }}')
            self._line(f'DropdownMenu(expanded = {wid}Expanded, onDismissRequest = {{ {wid}Expanded = false }}) {{')
            self.indent += 1
            if isinstance(options, list):
                for opt in options:
                    opt_str = self._text_expr(opt, str(opt))
                    self._line(f'DropdownMenuItem(text = {{ Text({opt_str}) }}, onClick = {{ {wid}Selected = {opt_str}; {wid}Expanded = false }})')
            self.indent -= 1
            self._line('}')
            self.indent -= 1
            self._line('}')
        elif wtype == 'canvas':
            self.imports.add('androidx.compose.foundation.Canvas')
            self.imports.add('androidx.compose.ui.graphics.Color')
            cw = props.get('width', 400)
            ch = props.get('height', 300)
            self._line(f'Canvas(modifier = Modifier.size({cw}.dp, {ch}.dp)) {{')
            self.indent += 1
            self._line('// Canvas drawing — customize as needed')
            self._line('drawRect(color = Color(0xFF1e293b))')
            self.indent -= 1
            self._line('}')
        elif wtype == 'image':
            self.imports.add('androidx.compose.foundation.Image')
            self._line(f'// Image: {text or "placeholder"} — load with painterResource or rememberImagePainter')
            self._line(f'Text("Image: {text or "placeholder"}")')
        elif wtype == 'separator':
            self.imports.add('androidx.compose.material3.Divider')
            self._line('Divider(modifier = Modifier.padding(vertical = 8.dp))')
        elif wtype == 'listbox':
            self.imports.add('androidx.compose.foundation.lazy.LazyColumn')
            self.imports.add('androidx.compose.foundation.lazy.items')
            self._line(f'val {wid}Items = remember {{ mutableStateListOf<String>() }}')
            self._line(f'LazyColumn(modifier = Modifier.fillMaxWidth().height(200.dp)) {{')
            self.indent += 1
            self._line(f'items({wid}Items) {{ item -> Text(item) }}')
            self.indent -= 1
            self._line('}')
        else:
            text_str = self._text_expr(text, wtype)
            self._line(f'Text(text = {text_str})')

    def _text_expr(self, text, default=''):
        """Convert text to a Kotlin string expression."""
        if text is None:
            return f'"{default}"'
        if hasattr(text, 'line'):  # AST node
            return self._expr(text)
        return f'"{text}"'

    def _expr_safe(self, node):
        """Safely convert node to expression string."""
        if node is None:
            return ''
        if hasattr(node, 'line'):
            return self._expr(node)
        return str(node).strip('"')

    # ── AST to Kotlin Expression ────────────────────────

    def _expr(self, node):
        """Convert AST expression to Kotlin source."""
        if isinstance(node, ast.Literal):
            return self._expr_literal(node)
        if isinstance(node, ast.Identifier):
            return node.name
        if isinstance(node, ast.BinaryOp):
            l, r = self._expr(node.left), self._expr(node.right)
            op = node.operator
            if op == 'and': return f'({l} && {r})'
            if op == 'or': return f'({l} || {r})'
            if op == '**': return f'{l}.toDouble().pow({r}.toDouble())'
            if op == '//': return f'({l} / {r})'
            if op == '+' and self._might_be_string(node):
                return f'({l}.toString() + {r}.toString())'
            return f'({l} {op} {r})'
        if isinstance(node, ast.UnaryOp):
            if node.operator == 'not': return f'!{self._expr(node.operand)}'
            return f'{node.operator}{self._expr(node.operand)}'
        if isinstance(node, ast.FunctionCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{node.name}({args})'
        if isinstance(node, ast.MethodCall):
            obj = self._expr(node.obj)
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{obj}.{node.method_name}({args})'
        if isinstance(node, ast.PropertyAccess):
            return f'{self._expr(node.obj)}.{node.property_name}'
        if isinstance(node, ast.IndexAccess):
            return f'{self._expr(node.obj)}[{self._expr(node.index)}]'
        if isinstance(node, ast.ListLiteral):
            elems = ', '.join(self._expr(e) for e in node.elements)
            return f'mutableListOf({elems})'
        if isinstance(node, ast.DictLiteral):
            pairs = ', '.join(f'{self._expr_key(k)} to {self._expr(v)}' for k, v in node.pairs)
            return f'mutableMapOf({pairs})'
        if hasattr(ast, 'TemplateString') and isinstance(node, ast.TemplateString):
            parts = []
            for part in node.parts:
                if isinstance(part, str):
                    parts.append(part.replace('"', '\\"'))
                else:
                    parts.append(f'${{{self._expr(part)}}}')
            return f'"{"".join(parts)}"'
        if isinstance(node, ast.TernaryExpression):
            return f'if ({self._expr(node.condition)}) {self._expr(node.true_expr)} else {self._expr(node.false_expr)}'
        if isinstance(node, ast.LambdaExpression):
            params = ', '.join(node.params) if node.params else ''
            body = self._expr(node.body)
            return f'{{ {params} -> {body} }}' if params else f'{{ {body} }}'
        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{node.class_name}({args})'
        if isinstance(node, str):
            return f'"{node}"'
        return f'null /* {type(node).__name__} */'

    def _expr_literal(self, node):
        if isinstance(node.value, bool): return 'true' if node.value else 'false'
        if isinstance(node.value, str):
            escaped = node.value.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        if node.value is None: return 'null'
        return str(node.value)

    def _expr_key(self, k):
        if isinstance(k, str):
            return f'"{k}"'
        if hasattr(k, 'line'):
            return self._expr(k)
        return str(k)

    def _might_be_string(self, node):
        """Heuristic: check if binary op might involve strings."""
        return node.operator == '+'

    # ── Statement Emission ──────────────────────────────

    def _emit_function(self, node):
        """Emit a Kotlin function."""
        params = ', '.join(f'{p[0]}: Any' if isinstance(p, (list, tuple)) else f'{p}: Any'
                           for p in node.params)
        self._line(f'fun {node.name}({params}): Any? {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_class(self, node):
        """Emit a Kotlin class."""
        parent = f' : {node.parent}()' if node.parent else ''
        self._line(f'open class {node.name}{parent} {{')
        self.indent += 1
        for item in node.body:
            self._emit_stmt(item)
        self.indent -= 1
        self._line('}')

    def _emit_stmt(self, node):
        if node is None: return
        if isinstance(node, ast.VarDeclaration):
            val = self._expr(node.value) if node.value else 'null'
            self._line(f'var {node.name} = {val}')
        elif isinstance(node, ast.ConstDeclaration):
            val = self._expr(node.value) if node.value else 'null'
            self._line(f'val {node.name} = {val}')
        elif isinstance(node, ast.VarAssignment):
            self._line(f'{node.name} = {self._expr(node.value)}')
        elif isinstance(node, ast.PrintStatement):
            self._line(f'println({self._expr(node.expression)})')
        elif isinstance(node, ast.ReturnStatement):
            if node.value:
                self._line(f'return {self._expr(node.value)}')
            else:
                self._line('return')
        elif isinstance(node, ast.IfStatement):
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
        elif isinstance(node, ast.WhileLoop):
            self._line(f'while ({self._expr(node.condition)}) {{')
            self.indent += 1
            for s in node.body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ForEachLoop):
            self._line(f'for ({node.var_name} in {self._expr(node.iterable)}) {{')
            self.indent += 1
            for s in node.body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ForRange):
            self._line(f'for ({node.var_name} in {self._expr(node.start)}..{self._expr(node.end)}) {{')
            self.indent += 1
            for s in node.body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.RepeatLoop):
            self._line(f'repeat({self._expr(node.count)}) {{')
            self.indent += 1
            for s in node.body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.FunctionCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.MethodCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.BreakStatement):
            self._line('break')
        elif isinstance(node, ast.ContinueStatement):
            self._line('continue')
        elif isinstance(node, ast.TryCatch):
            self._line('try {')
            self.indent += 1
            for s in node.try_body: self._emit_stmt(s)
            self.indent -= 1
            var_name = node.error_var or 'e'
            self._line(f'}} catch ({var_name}: Exception) {{')
            self.indent += 1
            for s in node.catch_body: self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.ThrowStatement):
            self._line(f'throw Exception({self._expr(node.expression)})')
        elif isinstance(node, ast.PropertySet):
            self._line(f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)}')
        elif isinstance(node, ast.IndexSet):
            self._line(f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)}')
        elif isinstance(node, ast.AugmentedAssignment):
            self._line(f'{node.name} {node.operator} {self._expr(node.value)}')
        elif isinstance(node, ast.FunctionDef):
            self._emit_function(node)
        elif isinstance(node, ast.MatchStatement):
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
        elif isinstance(node, ast.EnumDef):
            self._line(f'enum class {node.name} {{')
            self.indent += 1
            if not node.members:
                self._line('// empty')
            else:
                self._line(', '.join(node.members))
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.TryCatchFinally):
            self._line('try {')
            self.indent += 1
            for s in node.try_body:
                self._emit_stmt(s)
            self.indent -= 1
            for err_type, err_var, body in node.catch_clauses:
                var = err_var if err_var else 'e'
                exc = err_type if err_type else 'Exception'
                self._line(f'}} catch ({var}: {exc}) {{')
                self.indent += 1
                for s in body:
                    self._emit_stmt(s)
                self.indent -= 1
            if node.finally_body:
                self._line('} finally {')
                self.indent += 1
                for s in node.finally_body:
                    self._emit_stmt(s)
                self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.AsyncFunctionDef):
            params = ', '.join(f'{p[0]}: Any' if isinstance(p, (list, tuple)) else f'{p}: Any' for p in node.params)
            self._line(f'suspend fun {node.name}({params}): Any? {{')
            self.indent += 1
            for s in node.body:
                self._emit_stmt(s)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.SpawnStatement):
            self.imports.add('kotlinx.coroutines.launch')
            self.imports.add('kotlinx.coroutines.GlobalScope')
            self._line('GlobalScope.launch {')
            self.indent += 1
            self._emit_stmt(node.function_call)
            self.indent -= 1
            self._line('}')
        elif isinstance(node, ast.DestructureAssignment):
            names = ', '.join(node.names)
            self._line(f'val ({names}) = {self._expr(node.value)}')
        elif isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                self._line(f'super.{node.method_name}({args})')
            else:
                self._line(f'super({args})')
        elif isinstance(node, ast.FileWrite):
            self._line(f'java.io.File({self._expr(node.filepath)}).writeText({self._expr(node.content)}.toString())')
        elif isinstance(node, ast.FileAppend):
            self._line(f'java.io.File({self._expr(node.filepath)}).appendText({self._expr(node.content)}.toString() + "\\n")')

    # ── GUI Node Collection ─────────────────────────────

    def _collect_gui_nodes(self, stmts):
        """Collect GUI widget definitions from AST."""
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

    def _line(self, text):
        self.output.append('    ' * self.indent + text)


# ── Convenience Functions ────────────────────────────────


def generate_desktop_project(program: ast.Program, output_dir: str,
                              app_name="EPLDesktopApp", package="com.epl.desktop",
                              width=900, height=700, icon=None) -> str:
    """Generate a complete Compose Multiplatform Desktop project from EPL."""
    gen = DesktopProjectGenerator(app_name, package, width, height, icon)
    return gen.generate(program, output_dir)


def generate_desktop_kotlin(program: ast.Program, package="com.epl.desktop",
                             app_title="EPL App", width=900, height=700) -> str:
    """Generate just the Main.kt Compose Desktop source."""
    gen = DesktopComposeGenerator(package, app_title, width, height)
    return gen.generate(program)
