"""
EPL Profiler & Debug Adapter Protocol (DAP) Server (v6.0)
Production-ready performance profiling, memory tracking, tracing, and IDE debug integration.
"""

import time
import json
import threading
import sys
import os
import socket


# ═══════════════════════════════════════════════════════════
#  Performance Profiler
# ═══════════════════════════════════════════════════════════

class EPLProfiler:
    """Execution profiler for EPL programs."""

    def __init__(self):
        self._timers = {}       # name → start_time
        self._results = {}      # name → [elapsed_ms, ...]
        self._call_counts = {}  # name → count
        self._call_stack = []   # stack of (name, start_time)
        self._enabled = False
        self._trace_log = []    # [(timestamp, event, name, duration)]
        self._memory_snapshots = []  # [(timestamp, bytes)]

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @property
    def is_enabled(self):
        return self._enabled

    def start(self, name):
        """Start a named timer."""
        self._timers[name] = time.perf_counter()
        self._call_stack.append((name, self._timers[name]))

    def stop(self, name):
        """Stop a named timer and record elapsed time."""
        if name not in self._timers:
            return 0.0
        elapsed = (time.perf_counter() - self._timers[name]) * 1000  # ms
        self._results.setdefault(name, []).append(elapsed)
        self._call_counts[name] = self._call_counts.get(name, 0) + 1
        if self._call_stack and self._call_stack[-1][0] == name:
            self._call_stack.pop()
        self._trace_log.append((time.time(), 'call', name, elapsed))
        del self._timers[name]
        return elapsed

    def elapsed(self, name):
        """Get total elapsed time for a named timer."""
        if name in self._results:
            return sum(self._results[name])
        if name in self._timers:
            return (time.perf_counter() - self._timers[name]) * 1000
        return 0.0

    def call_enter(self, func_name):
        """Automatically called when a function is entered (if profiling)."""
        if not self._enabled:
            return
        self.start(func_name)

    def call_exit(self, func_name):
        """Automatically called when a function exits (if profiling)."""
        if not self._enabled:
            return
        self.stop(func_name)

    def report(self):
        """Generate a profiling report."""
        lines = []
        lines.append("═" * 60)
        lines.append("  EPL Profiler Report")
        lines.append("═" * 60)
        lines.append(f"  {'Function':<30} {'Calls':>6} {'Total ms':>10} {'Avg ms':>10}")
        lines.append("  " + "─" * 56)

        # Sort by total time descending
        sorted_funcs = sorted(
            self._results.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )
        total_time = sum(sum(v) for v in self._results.values())

        for name, times in sorted_funcs:
            total = sum(times)
            count = len(times)
            avg = total / count if count > 0 else 0
            pct = (total / total_time * 100) if total_time > 0 else 0
            lines.append(f"  {name:<30} {count:>6} {total:>9.2f} {avg:>9.2f}  ({pct:.1f}%)")

        lines.append("  " + "─" * 56)
        lines.append(f"  {'TOTAL':<30} {'':>6} {total_time:>9.2f}")
        lines.append("═" * 60)
        return "\n".join(lines)

    def get_stats(self):
        """Get profiling stats as a dict."""
        stats = {}
        for name, times in self._results.items():
            stats[name] = {
                'calls': len(times),
                'total_ms': sum(times),
                'avg_ms': sum(times) / len(times) if times else 0,
                'min_ms': min(times) if times else 0,
                'max_ms': max(times) if times else 0,
            }
        return stats

    def reset(self):
        """Reset all profiling data."""
        self._timers.clear()
        self._results.clear()
        self._call_counts.clear()
        self._call_stack.clear()
        self._trace_log.clear()
        self._memory_snapshots.clear()

    def memory_snapshot(self):
        """Take a memory usage snapshot."""
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            self._memory_snapshots.append((time.time(), current, peak))
            return current
        except Exception:
            return 0

    def get_memory_stats(self):
        """Get memory usage statistics."""
        if not self._memory_snapshots:
            return {'current': 0, 'peak': 0, 'snapshots': 0}
        last = self._memory_snapshots[-1]
        return {
            'current': last[1],
            'peak': max(s[2] for s in self._memory_snapshots),
            'snapshots': len(self._memory_snapshots),
        }

    def summary(self):
        """Get a concise profiling summary dict."""
        stats = self.get_stats()
        total_calls = sum(s['calls'] for s in stats.values())
        total_time = sum(s['total_ms'] for s in stats.values())
        hotspot = max(stats.items(), key=lambda x: x[1]['total_ms'])[0] if stats else None
        return {
            'functions_profiled': len(stats),
            'total_calls': total_calls,
            'total_time_ms': total_time,
            'hotspot': hotspot,
            'memory': self.get_memory_stats(),
        }

    def export_trace(self, filepath):
        """Export trace in Chrome Tracing format for chrome://tracing."""
        events = []
        for ts, event, name, duration in self._trace_log:
            events.append({
                "name": name,
                "cat": "function",
                "ph": "X",  # Complete event
                "ts": int((ts * 1e6)),  # microseconds
                "dur": int(duration * 1000),  # microseconds
                "pid": 1,
                "tid": 1,
            })
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({"traceEvents": events}, f)
        return filepath


# Singleton profiler instance
_profiler = EPLProfiler()


def get_profiler():
    return _profiler


# ═══════════════════════════════════════════════════════════
#  DAP (Debug Adapter Protocol) Server
# ═══════════════════════════════════════════════════════════

class DAPServer:
    """Debug Adapter Protocol server for EPL.

    Implements the DAP protocol for IDE integration (VS Code, etc.).
    Supports: breakpoints, step, continue, variables, stack frames.
    """

    def __init__(self, interpreter=None):
        self.interpreter = interpreter
        self.breakpoints = {}   # file → set of line numbers
        self.paused = False
        self.current_line = 0
        self.current_file = ""
        self.step_mode = None   # None, 'next', 'stepIn', 'stepOut'
        self.step_depth = 0
        self._seq = 0
        self._conn = None
        self._running = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused
        self._variables = {}
        self._stack_frames = []

    def start(self, host='127.0.0.1', port=4711):
        """Start the DAP server."""
        self._running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        server.settimeout(1.0)
        print(f"  EPL Debug Adapter listening on {host}:{port}")
        print(f"  Connect your IDE debugger to this address.")

        try:
            while self._running:
                try:
                    conn, addr = server.accept()
                    self._conn = conn
                    self._handle_client(conn)
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            server.close()

    def stop(self):
        self._running = False

    def _handle_client(self, conn):
        """Handle DAP client messages."""
        buf = b""
        while self._running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data
                while b'\r\n\r\n' in buf:
                    header_end = buf.index(b'\r\n\r\n')
                    header = buf[:header_end].decode('utf-8')
                    content_length = 0
                    for line in header.split('\r\n'):
                        if line.startswith('Content-Length:'):
                            content_length = int(line.split(':')[1].strip())
                    body_start = header_end + 4
                    if len(buf) < body_start + content_length:
                        break  # Wait for more data
                    body = buf[body_start:body_start + content_length]
                    buf = buf[body_start + content_length:]
                    msg = json.loads(body.decode('utf-8'))
                    self._dispatch(msg, conn)
            except (ConnectionError, json.JSONDecodeError):
                break
        conn.close()
        self._conn = None

    def _dispatch(self, msg, conn):
        """Dispatch a DAP message."""
        cmd = msg.get('command', '')
        seq = msg.get('seq', 0)

        if cmd == 'initialize':
            self._send_response(conn, seq, cmd, body={
                'supportsConfigurationDoneRequest': True,
                'supportsFunctionBreakpoints': True,
                'supportsConditionalBreakpoints': False,
                'supportsEvaluateForHovers': True,
                'supportsStepBack': False,
                'supportsSetVariable': True,
            })
            self._send_event(conn, 'initialized')

        elif cmd == 'setBreakpoints':
            args = msg.get('arguments', {})
            source = args.get('source', {}).get('path', '')
            bps = args.get('breakpoints', [])
            line_set = set()
            result_bps = []
            for bp in bps:
                line = bp.get('line', 0)
                line_set.add(line)
                result_bps.append({
                    'id': len(result_bps) + 1,
                    'verified': True,
                    'line': line,
                })
            self.breakpoints[source] = line_set
            self._send_response(conn, seq, cmd, body={
                'breakpoints': result_bps
            })

        elif cmd == 'configurationDone':
            self._send_response(conn, seq, cmd)

        elif cmd == 'launch':
            self._send_response(conn, seq, cmd)

        elif cmd == 'threads':
            self._send_response(conn, seq, cmd, body={
                'threads': [{'id': 1, 'name': 'EPL Main Thread'}]
            })

        elif cmd == 'stackTrace':
            frames = []
            for i, frame in enumerate(self._stack_frames):
                frames.append({
                    'id': i,
                    'name': frame.get('name', '<unknown>'),
                    'source': {'path': frame.get('file', '')},
                    'line': frame.get('line', 0),
                    'column': 1,
                })
            self._send_response(conn, seq, cmd, body={
                'stackFrames': frames,
                'totalFrames': len(frames),
            })

        elif cmd == 'scopes':
            frame_id = msg.get('arguments', {}).get('frameId', 0)
            self._send_response(conn, seq, cmd, body={
                'scopes': [{
                    'name': 'Locals',
                    'variablesReference': frame_id + 1,
                    'expensive': False,
                }]
            })

        elif cmd == 'variables':
            ref = msg.get('arguments', {}).get('variablesReference', 1)
            variables = []
            for name, value in self._variables.items():
                variables.append({
                    'name': name,
                    'value': str(value),
                    'type': type(value).__name__,
                    'variablesReference': 0,
                })
            self._send_response(conn, seq, cmd, body={
                'variables': variables,
            })

        elif cmd == 'continue':
            self.step_mode = None
            self.paused = False
            self._pause_event.set()
            self._send_response(conn, seq, cmd, body={
                'allThreadsContinued': True,
            })

        elif cmd == 'next':
            self.step_mode = 'next'
            self.step_depth = len(self._stack_frames)
            self.paused = False
            self._pause_event.set()
            self._send_response(conn, seq, cmd)

        elif cmd == 'stepIn':
            self.step_mode = 'stepIn'
            self.paused = False
            self._pause_event.set()
            self._send_response(conn, seq, cmd)

        elif cmd == 'stepOut':
            self.step_mode = 'stepOut'
            self.step_depth = len(self._stack_frames)
            self.paused = False
            self._pause_event.set()
            self._send_response(conn, seq, cmd)

        elif cmd == 'evaluate':
            expr = msg.get('arguments', {}).get('expression', '')
            val = self._variables.get(expr, 'undefined')
            self._send_response(conn, seq, cmd, body={
                'result': str(val),
                'variablesReference': 0,
            })

        elif cmd == 'disconnect':
            self._send_response(conn, seq, cmd)
            self.stop()

        else:
            self._send_response(conn, seq, cmd)

    def _send_response(self, conn, req_seq, command, body=None, success=True):
        """Send a DAP response."""
        self._seq += 1
        msg = {
            'seq': self._seq,
            'type': 'response',
            'request_seq': req_seq,
            'command': command,
            'success': success,
            'body': body or {},
        }
        self._send_message(conn, msg)

    def _send_event(self, conn, event, body=None):
        """Send a DAP event."""
        self._seq += 1
        msg = {
            'seq': self._seq,
            'type': 'event',
            'event': event,
            'body': body or {},
        }
        self._send_message(conn, msg)

    def _send_message(self, conn, msg):
        """Send a DAP message over the connection."""
        content = json.dumps(msg)
        header = f'Content-Length: {len(content)}\r\n\r\n'
        try:
            conn.sendall(header.encode('utf-8') + content.encode('utf-8'))
        except (ConnectionError, BrokenPipeError):
            pass

    # ─── Interpreter Hooks ───────────────────────────────

    def on_line(self, filename, line, variables=None):
        """Called by interpreter before executing each line."""
        self.current_file = filename
        self.current_line = line
        if variables:
            self._variables = dict(variables)

        should_pause = False

        # Check breakpoints
        if filename in self.breakpoints and line in self.breakpoints[filename]:
            should_pause = True

        # Check step mode
        if self.step_mode == 'next' and len(self._stack_frames) <= self.step_depth:
            should_pause = True
        elif self.step_mode == 'stepIn':
            should_pause = True
        elif self.step_mode == 'stepOut' and len(self._stack_frames) < self.step_depth:
            should_pause = True

        if should_pause and self._conn:
            self.paused = True
            reason = 'breakpoint' if not self.step_mode else 'step'
            self._send_event(self._conn, 'stopped', {
                'reason': reason,
                'threadId': 1,
                'allThreadsStopped': True,
            })
            self._pause_event.clear()
            self._pause_event.wait()  # Block until continue/step

    def on_function_enter(self, name, filename, line):
        """Called when entering a function."""
        self._stack_frames.append({
            'name': name,
            'file': filename,
            'line': line,
        })

    def on_function_exit(self):
        """Called when exiting a function."""
        if self._stack_frames:
            self._stack_frames.pop()


def register_profiler_builtins(env):
    """Register profiler built-in functions into an EPL environment."""
    prof = get_profiler()

    env.set('profiler_start', lambda name: prof.start(name))
    env.set('profiler_stop', lambda name: prof.stop(name))
    env.set('profiler_elapsed', lambda name: prof.elapsed(name))
    env.set('profiler_report', lambda: print(prof.report()))
    env.set('profiler_enable', lambda: prof.enable())
    env.set('profiler_disable', lambda: prof.disable())
    env.set('profiler_reset', lambda: prof.reset())
    env.set('profiler_export', lambda path: prof.export_trace(path))
    env.set('profiler_stats', lambda: prof.get_stats())
