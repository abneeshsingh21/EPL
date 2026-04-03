"""
EPL Debugger v1.0
Interactive step-through debugger for EPL programs.

Features:
- Breakpoints (by line number or function name)
- Step Into, Step Over, Step Out
- Variable inspection (locals, globals)
- Call stack display
- Watch expressions
- Conditional breakpoints
- REPL at breakpoint (evaluate expressions in context)

Usage:
    from epl.debugger import EPLDebugger
    debugger = EPLDebugger()
    debugger.run("path/to/program.epl")

CLI:
    python -m epl.debugger program.epl
"""

import sys
import os
import readline  # for input history on Linux/Mac; silently ignored on Windows
import traceback
from typing import Dict, List, Optional, Set, Tuple, Callable, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl import ast_nodes as ast
from epl.environment import Environment


# ═══════════════════════════════════════════════════════════
# Breakpoint Management
# ═══════════════════════════════════════════════════════════

class Breakpoint:
    """Represents a debugger breakpoint."""
    _id_counter = 0

    def __init__(self, line: int = None, function_name: str = None,
                 condition: str = None, hit_count: int = 0):
        Breakpoint._id_counter += 1
        self.id = Breakpoint._id_counter
        self.line = line
        self.function_name = function_name
        self.condition = condition  # EPL expression string
        self.hit_count = hit_count  # Number of times to skip
        self.hits = 0
        self.enabled = True

    def should_break(self, current_line: int, current_func: str, env: dict) -> bool:
        """Check if this breakpoint should trigger."""
        if not self.enabled:
            return False
        # Match by line or function
        matched = False
        if self.line is not None and self.line == current_line:
            matched = True
        if self.function_name and self.function_name == current_func:
            matched = True
        if not matched:
            return False
        # Check hit count
        self.hits += 1
        if self.hit_count > 0 and self.hits <= self.hit_count:
            return False
        # Check condition
        if self.condition:
            try:
                # Evaluate condition using EPL parser, not Python eval
                from epl.lexer import Lexer
                from epl.parser import Parser
                lexer = Lexer(self.condition)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                expr_node = parser._parse_expression()
                # Build a minimal Environment from the env dict
                from epl.environment import Environment
                temp_env = Environment(name='breakpoint')
                for k, v in env.items():
                    temp_env.define_variable(k, v)
                from epl.interpreter import Interpreter
                interp = Interpreter()
                result = interp._eval(expr_node, temp_env)
                return bool(result)
            except Exception:
                return True  # Break if condition errors
        return True

    def __repr__(self):
        parts = [f'#{self.id}']
        if self.line is not None:
            parts.append(f'line {self.line}')
        if self.function_name:
            parts.append(f'func {self.function_name}')
        if self.condition:
            parts.append(f'if {self.condition}')
        if self.hit_count:
            parts.append(f'after {self.hit_count} hits')
        if not self.enabled:
            parts.append('(disabled)')
        return ' '.join(parts)


# ═══════════════════════════════════════════════════════════
# Debug State
# ═══════════════════════════════════════════════════════════

class DebugState:
    """Tracks debugger execution state."""

    # Stop modes
    CONTINUE = 'continue'
    STEP_INTO = 'step_into'
    STEP_OVER = 'step_over'
    STEP_OUT = 'step_out'

    def __init__(self):
        self.mode = self.CONTINUE
        self.breakpoints: List[Breakpoint] = []
        self.call_stack: List[dict] = []  # [{name, line, env}]
        self.watch_expressions: List[str] = []
        self.step_depth = 0  # For step over/out
        self.current_line = 0
        self.current_function = '<main>'
        self.paused = False
        self.source_lines: List[str] = []
        self.source_file = ''
        self.history: List[str] = []  # Command history

    @property
    def depth(self):
        return len(self.call_stack)

    def push_frame(self, name: str, line: int, env: dict):
        self.call_stack.append({
            'name': name,
            'line': line,
            'env': env
        })

    def pop_frame(self):
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def add_breakpoint(self, **kwargs) -> Breakpoint:
        bp = Breakpoint(**kwargs)
        self.breakpoints.append(bp)
        return bp

    def remove_breakpoint(self, bp_id: int) -> bool:
        for i, bp in enumerate(self.breakpoints):
            if bp.id == bp_id:
                self.breakpoints.pop(i)
                return True
        return False

    def should_stop(self, line: int, func_name: str, env: dict) -> bool:
        """Determine if execution should pause at this point."""
        self.current_line = line
        self.current_function = func_name

        # Check mode
        if self.mode == self.STEP_INTO:
            return True
        if self.mode == self.STEP_OVER:
            return self.depth <= self.step_depth
        if self.mode == self.STEP_OUT:
            return self.depth < self.step_depth

        # Check breakpoints
        for bp in self.breakpoints:
            if bp.should_break(line, func_name, env):
                return True

        return False


# ═══════════════════════════════════════════════════════════
# Debugger Engine
# ═══════════════════════════════════════════════════════════

class EPLDebugger:
    """Interactive step-through debugger for EPL programs."""

    HELP_TEXT = """
EPL Debugger Commands:
  b <line>          Set breakpoint at line number
  b <func>          Set breakpoint at function entry
  b <line> if <cond> Set conditional breakpoint
  delete <id>       Remove breakpoint by ID
  enable <id>       Enable breakpoint
  disable <id>      Disable breakpoint
  bl                List all breakpoints

  s / step          Step into (execute one statement, enter functions)
  n / next          Step over (execute one statement, skip functions)
  o / out           Step out (run until current function returns)
  c / continue      Continue until next breakpoint
  r / run           Restart program

  p <expr>          Print/evaluate expression in current scope
  pp <var>          Pretty-print variable
  locals            Show local variables
  globals           Show global variables
  stack             Show call stack
  where             Show current position in source

  w <expr>          Add watch expression
  unwatch <expr>    Remove watch expression
  watches           Show all watch values

  l [n]             List source around current line (or line n)
  source            Show entire source

  h / help          Show this help
  q / quit          Exit debugger
"""

    def __init__(self, silent=False):
        self.state = DebugState()
        self.interpreter = None
        self.program = None
        self.silent = silent

    def run(self, source_or_path: str):
        """Run a program under the debugger."""
        # Load source
        if os.path.isfile(source_or_path):
            self.state.source_file = source_or_path
            with open(source_or_path, 'r', encoding='utf-8') as f:
                source = f.read()
        else:
            self.state.source_file = '<stdin>'
            source = source_or_path

        self.state.source_lines = source.split('\n')

        # Parse
        try:
            tokens = Lexer(source).tokenize()
            self.program = Parser(tokens).parse()
        except Exception as e:
            print(f"Parse error: {e}")
            return

        if not self.silent:
            print(f"EPL Debugger v1.0 — {self.state.source_file}")
            print(f"  {len(self.state.source_lines)} lines loaded")
            print('  Type "help" for commands, "c" to run, "s" to step')
            print()

        # Initial pause
        self.state.mode = DebugState.STEP_INTO
        self._debug_loop()

    def _debug_loop(self):
        """Main debug execution loop."""
        self.interpreter = DebugInterpreter(self)
        try:
            self.interpreter.execute(self.program)
            if not self.silent:
                print("\n--- Program finished ---")
        except DebugQuit:
            if not self.silent:
                print("\n--- Debugger quit ---")
        except Exception as e:
            print(f"\n--- Runtime error: {e} ---")
            self._show_position()
            self._interact()

    def on_statement(self, node, env_dict: dict):
        """Called by DebugInterpreter before each statement."""
        line = getattr(node, 'line', 0)
        func = self.state.current_function

        if self.state.should_stop(line, func, env_dict):
            self.state.paused = True
            self._show_watches(env_dict)
            self._show_position()
            self._interact()

    def _show_position(self):
        """Show current source line with context."""
        line = self.state.current_line
        if line <= 0 or line > len(self.state.source_lines):
            return
        print(f"\n  {self.state.current_function}() at line {line}:")
        self._list_source(line, context=2)

    def _list_source(self, center: int, context: int = 5):
        """Display source lines around center."""
        start = max(1, center - context)
        end = min(len(self.state.source_lines), center + context)
        for i in range(start, end + 1):
            marker = '-->' if i == self.state.current_line else '   '
            bp_marker = '●' if any(bp.line == i and bp.enabled for bp in self.state.breakpoints) else ' '
            line_text = self.state.source_lines[i - 1] if i <= len(self.state.source_lines) else ''
            print(f"  {bp_marker}{marker} {i:4d} | {line_text}")

    def _show_watches(self, env_dict: dict):
        """Display watch expression values."""
        if not self.state.watch_expressions:
            return
        print("  Watches:")
        for expr in self.state.watch_expressions:
            try:
                value = self._eval_epl_expr(expr, env_dict)
                print(f"    {expr} = {repr(value)}")
            except Exception as e:
                print(f"    {expr} = <error: {e}>")

    def _eval_epl_expr(self, expr_text: str, env_dict: dict):
        """Evaluate an EPL expression string in the given environment."""
        from epl.lexer import Lexer
        from epl.parser import Parser
        from epl.environment import Environment
        from epl.interpreter import Interpreter
        lexer = Lexer(expr_text)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        expr_node = parser._parse_expression()
        temp_env = Environment(name='debug_eval')
        for k, v in env_dict.items():
            temp_env.define_variable(k, v)
        interp = Interpreter()
        return interp._eval(expr_node, temp_env)

    def _interact(self):
        """Interactive command loop at breakpoint."""
        while True:
            try:
                cmd = input("(epl-dbg) ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                raise DebugQuit()

            if not cmd:
                continue

            self.state.history.append(cmd)
            parts = cmd.split(None, 1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ''

            try:
                if command in ('h', 'help'):
                    print(self.HELP_TEXT)
                elif command in ('q', 'quit', 'exit'):
                    raise DebugQuit()
                elif command in ('c', 'continue'):
                    self.state.mode = DebugState.CONTINUE
                    return
                elif command in ('s', 'step'):
                    self.state.mode = DebugState.STEP_INTO
                    return
                elif command in ('n', 'next'):
                    self.state.mode = DebugState.STEP_OVER
                    self.state.step_depth = self.state.depth
                    return
                elif command in ('o', 'out'):
                    self.state.mode = DebugState.STEP_OUT
                    self.state.step_depth = self.state.depth
                    return
                elif command == 'b':
                    self._cmd_breakpoint(arg)
                elif command == 'delete':
                    self._cmd_delete_breakpoint(arg)
                elif command == 'enable':
                    self._cmd_toggle_breakpoint(arg, True)
                elif command == 'disable':
                    self._cmd_toggle_breakpoint(arg, False)
                elif command == 'bl':
                    self._cmd_list_breakpoints()
                elif command == 'p':
                    self._cmd_print(arg)
                elif command == 'pp':
                    self._cmd_pretty_print(arg)
                elif command == 'locals':
                    self._cmd_locals()
                elif command == 'globals':
                    self._cmd_globals()
                elif command == 'stack':
                    self._cmd_stack()
                elif command == 'where':
                    self._show_position()
                elif command == 'l':
                    self._cmd_list(arg)
                elif command == 'source':
                    self._cmd_source()
                elif command == 'w':
                    self._cmd_watch(arg)
                elif command == 'unwatch':
                    self._cmd_unwatch(arg)
                elif command == 'watches':
                    env = self._get_current_env()
                    self._show_watches(env)
                elif command in ('r', 'run'):
                    self.state.mode = DebugState.STEP_INTO
                    self.state.call_stack = []
                    raise DebugRestart()
                else:
                    # Try evaluating as expression
                    self._cmd_print(cmd)
            except (DebugQuit, DebugRestart):
                raise
            except Exception as e:
                print(f"  Error: {e}")

    # ─── Breakpoint Commands ────────────────────────

    def _cmd_breakpoint(self, arg: str):
        if not arg:
            print("  Usage: b <line> or b <func> [if <condition>]")
            return
        condition = None
        if ' if ' in arg:
            arg, condition = arg.split(' if ', 1)
            arg = arg.strip()
            condition = condition.strip()
        try:
            line = int(arg)
            bp = self.state.add_breakpoint(line=line, condition=condition)
            print(f"  Breakpoint {bp}")
        except ValueError:
            bp = self.state.add_breakpoint(function_name=arg, condition=condition)
            print(f"  Breakpoint {bp}")

    def _cmd_delete_breakpoint(self, arg: str):
        try:
            bp_id = int(arg)
            if self.state.remove_breakpoint(bp_id):
                print(f"  Removed breakpoint #{bp_id}")
            else:
                print(f"  No breakpoint #{bp_id}")
        except ValueError:
            print("  Usage: delete <id>")

    def _cmd_toggle_breakpoint(self, arg: str, enabled: bool):
        try:
            bp_id = int(arg)
            for bp in self.state.breakpoints:
                if bp.id == bp_id:
                    bp.enabled = enabled
                    status = 'enabled' if enabled else 'disabled'
                    print(f"  Breakpoint #{bp_id} {status}")
                    return
            print(f"  No breakpoint #{bp_id}")
        except ValueError:
            print(f"  Usage: {'enable' if enabled else 'disable'} <id>")

    def _cmd_list_breakpoints(self):
        if not self.state.breakpoints:
            print("  No breakpoints set")
            return
        for bp in self.state.breakpoints:
            print(f"  {bp}")

    # ─── Inspection Commands ────────────────────────

    def _cmd_print(self, expr: str):
        if not expr:
            print("  Usage: p <expression>")
            return
        env = self._get_current_env()
        try:
            result = self._eval_epl_expr(expr, env)
            print(f"  {repr(result)}")
        except Exception as e:
            # Fallback: try simple variable lookup
            if expr in env:
                print(f"  {repr(env[expr])}")
            else:
                print(f"  Error evaluating '{expr}': {e}")

    def _cmd_pretty_print(self, var_name: str):
        if not var_name:
            print("  Usage: pp <variable>")
            return
        env = self._get_current_env()
        val = env.get(var_name)
        if val is None:
            print(f"  '{var_name}' not found")
            return
        import pprint
        pprint.pprint(val, indent=2)

    def _cmd_locals(self):
        env = self._get_current_env()
        if not env:
            print("  No local variables")
            return
        print("  Local variables:")
        for k, v in sorted(env.items()):
            if not k.startswith('_'):
                val_str = repr(v)
                if len(val_str) > 80:
                    val_str = val_str[:77] + '...'
                print(f"    {k} = {val_str}")

    def _cmd_globals(self):
        if self.interpreter and hasattr(self.interpreter, 'global_env'):
            env = self.interpreter.global_env
            if hasattr(env, 'variables'):
                print("  Global variables:")
                for k, v in sorted(env.variables.items()):
                    if not k.startswith('_'):
                        val_str = repr(v)
                        if len(val_str) > 80:
                            val_str = val_str[:77] + '...'
                        print(f"    {k} = {val_str}")
            else:
                print("  (no global scope available)")
        else:
            print("  (no interpreter context)")

    def _cmd_stack(self):
        if not self.state.call_stack:
            print(f"  #0  <main> at line {self.state.current_line}")
            return
        print("  Call stack:")
        for i, frame in enumerate(reversed(self.state.call_stack)):
            marker = '-->' if i == 0 else '   '
            print(f"  {marker} #{i}  {frame['name']}() at line {frame['line']}")
        print(f"      #{len(self.state.call_stack)}  <main>")

    # ─── Source Commands ────────────────────────────

    def _cmd_list(self, arg: str):
        if arg:
            try:
                center = int(arg)
            except ValueError:
                center = self.state.current_line
        else:
            center = self.state.current_line
        self._list_source(center, context=10)

    def _cmd_source(self):
        for i, line in enumerate(self.state.source_lines, 1):
            marker = '-->' if i == self.state.current_line else '   '
            bp_marker = '●' if any(bp.line == i and bp.enabled for bp in self.state.breakpoints) else ' '
            print(f"  {bp_marker}{marker} {i:4d} | {line}")

    # ─── Watch Commands ─────────────────────────────

    def _cmd_watch(self, expr: str):
        if not expr:
            print("  Usage: w <expression>")
            return
        self.state.watch_expressions.append(expr)
        print(f"  Watching: {expr}")

    def _cmd_unwatch(self, expr: str):
        if expr in self.state.watch_expressions:
            self.state.watch_expressions.remove(expr)
            print(f"  Unwatched: {expr}")
        else:
            print(f"  '{expr}' not in watch list")

    # ─── Helpers ────────────────────────────────────

    def _get_current_env(self) -> dict:
        """Get current scope as a flat dict for eval."""
        if self.interpreter and hasattr(self.interpreter, 'global_env'):
            env = self.interpreter.global_env
            result = {}
            if hasattr(env, 'variables'):
                result.update(env.variables)
            return result
        return {}


# ═══════════════════════════════════════════════════════════
# Debug-Instrumented Interpreter
# ═══════════════════════════════════════════════════════════

class DebugInterpreter(Interpreter):
    """Interpreter subclass that calls debugger hooks before each statement."""

    def __init__(self, debugger: EPLDebugger):
        super().__init__()
        self.debugger = debugger

    def _exec_statement(self, node, env):
        """Override to add debug hook before each statement."""
        if node is not None:
            env_dict = {}
            if hasattr(env, 'variables'):
                env_dict = dict(env.variables)
            self.debugger.on_statement(node, env_dict)
        return super()._exec_statement(node, env)


# ═══════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════

class DebugQuit(Exception):
    """Raised to quit the debugger."""
    pass

class DebugRestart(Exception):
    """Raised to restart program execution."""
    pass


# ═══════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='EPL Debugger')
    parser.add_argument('file', nargs='?', help='EPL source file to debug')
    parser.add_argument('-b', '--break', dest='breakpoints', action='append',
                       default=[], help='Set breakpoint (line number or function name)')
    args = parser.parse_args()

    if not args.file:
        print("Usage: python -m epl.debugger <file.epl>")
        print("       python -m epl.debugger <file.epl> -b 5 -b main")
        sys.exit(1)

    debugger = EPLDebugger()

    # Set initial breakpoints
    for bp_spec in args.breakpoints:
        try:
            line = int(bp_spec)
            debugger.state.add_breakpoint(line=line)
        except ValueError:
            debugger.state.add_breakpoint(function_name=bp_spec)

    debugger.run(args.file)


if __name__ == '__main__':
    main()
