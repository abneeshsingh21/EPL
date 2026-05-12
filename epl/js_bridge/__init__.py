"""
EPL JavaScript/TypeScript Bridge — Python-side Manager

Manages a persistent Node.js subprocess for executing JavaScript code from EPL.
Uses a JSON-RPC protocol over stdin/stdout for IPC.

Architecture:
    EPL Interpreter  <->  NodeBridge (Python)  <->  node_worker.js (Node.js)
                          via JSON-RPC over stdin/stdout
"""

import json
import os
import shutil
import subprocess
import sys
import threading

__all__ = ['NodeBridge', 'NodeBridgeError', 'JSModuleHandle']


class NodeBridgeError(Exception):
    """Raised when the Node.js bridge encounters an error."""
    pass


class JSModuleHandle:
    """Opaque reference to a JavaScript object living in the Node.js process."""

    __slots__ = ('handle', 'type_name')

    def __init__(self, handle: str, type_name: str = 'Object'):
        self.handle = handle
        self.type_name = type_name

    def __repr__(self):
        return f'<JSHandle {self.handle} ({self.type_name})>'


class NodeBridge:
    """Singleton manager for the persistent Node.js subprocess.

    Usage:
        bridge = NodeBridge.get_instance()
        handle = bridge.require("path")
        result = bridge.call(handle, "join", ["/home", "user"])
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._process = None
        self._next_id = 1
        self._io_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        """Get or create the singleton NodeBridge instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._ensure_running()
        elif cls._instance._process is None or cls._instance._process.poll() is not None:
            cls._instance._ensure_running()
        return cls._instance

    @classmethod
    def reset(cls):
        """Shutdown the Node.js process and clear the singleton."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._shutdown()
                cls._instance = None

    # ─── Process Lifecycle ────────────────────────────────

    def _ensure_running(self):
        """Start the Node.js subprocess if not already running."""
        if self._process is not None and self._process.poll() is None:
            return

        node_bin = shutil.which('node')
        if not node_bin:
            raise NodeBridgeError(
                'Node.js is not installed or not found in PATH. '
                'Install it from https://nodejs.org/'
            )

        worker_path = os.path.join(os.path.dirname(__file__), 'node_worker.js')
        if not os.path.exists(worker_path):
            raise NodeBridgeError(
                f'Node.js worker script not found at: {worker_path}'
            )

        try:
            kwargs = {
                'stdin': subprocess.PIPE,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'bufsize': 0,
            }
            # Prevent console window on Windows
            if sys.platform == 'win32':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            self._process = subprocess.Popen([node_bin, worker_path], **kwargs)
        except OSError as e:
            raise NodeBridgeError(f'Failed to start Node.js: {e}')

        # Wait for the "Worker ready" signal on stderr (with timeout)
        import time
        ready = threading.Event()
        stderr_output = []

        def _read_stderr():
            try:
                line = self._process.stderr.readline()
                if line:
                    stderr_output.append(line)
                    ready.set()
            except Exception:
                pass

        reader = threading.Thread(target=_read_stderr, daemon=True)
        reader.start()

        # Wait up to 5 seconds for the worker to be ready
        if not ready.wait(timeout=5.0):
            # Check if the process died
            returncode = self._process.poll()
            if returncode is not None:
                raise NodeBridgeError(
                    f'Node.js worker exited immediately (code {returncode}).'
                )
            # Process is alive but didn't send ready signal — proceed anyway


    def _shutdown(self):
        """Terminate the Node.js subprocess."""
        if self._process is not None:
            try:
                self._process.stdin.close()
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    # ─── JSON-RPC Communication ───────────────────────────

    def _send(self, request: dict) -> dict:
        """Send a JSON-RPC request and return the response."""
        self._ensure_running()

        request['id'] = self._next_id
        self._next_id += 1

        payload = json.dumps(request) + '\n'

        with self._io_lock:
            try:
                self._process.stdin.write(payload.encode('utf-8'))
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise NodeBridgeError(f'JS bridge pipe broken: {e}')

            try:
                response_line = self._process.stdout.readline()
            except (BrokenPipeError, OSError) as e:
                raise NodeBridgeError(f'JS bridge pipe broken: {e}')

        if not response_line:
            returncode = self._process.poll()
            if returncode is not None:
                raise NodeBridgeError(
                    f'JS bridge process terminated unexpectedly (exit code {returncode}).'
                )
            raise NodeBridgeError('JS bridge returned empty response.')

        try:
            response = json.loads(response_line.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise NodeBridgeError(f'Invalid JSON from JS bridge: {e}')

        if not response.get('ok', False):
            raise NodeBridgeError(response.get('error', 'Unknown JS bridge error'))

        return response

    # ─── Public API ───────────────────────────────────────

    def require(self, module_name: str) -> str:
        """Load a Node.js module and return its handle ID."""
        resp = self._send({'action': 'require', 'module': module_name})
        result = resp.get('result', {})
        if result.get('type') == 'handle':
            return result['handle']
        raise NodeBridgeError(f'Unexpected result from require("{module_name}"): {result}')

    def call(self, handle: str, method: str, args: list = None):
        """Call a method on a JS object by handle."""
        serialized_args = [self._serialize_arg(a) for a in (args or [])]
        resp = self._send({
            'action': 'call',
            'handle': handle,
            'method': method,
            'args': serialized_args,
        })
        return self._deserialize_result(resp.get('result'))

    def call_direct(self, handle: str, args: list = None):
        """Call a JS function handle directly (not as a method)."""
        serialized_args = [self._serialize_arg(a) for a in (args or [])]
        resp = self._send({
            'action': 'callDirect',
            'handle': handle,
            'args': serialized_args,
        })
        return self._deserialize_result(resp.get('result'))

    def get_prop(self, handle: str, prop_name: str):
        """Get a property from a JS object by handle."""
        resp = self._send({
            'action': 'get',
            'handle': handle,
            'prop': prop_name,
        })
        return self._deserialize_result(resp.get('result'))

    def set_prop(self, handle: str, prop_name: str, value):
        """Set a property on a JS object by handle."""
        self._send({
            'action': 'set',
            'handle': handle,
            'prop': prop_name,
            'value': self._serialize_arg(value),
        })

    # ─── Serialization ────────────────────────────────────

    def _serialize_arg(self, value) -> dict:
        """Convert a Python/EPL value to the JSON wire format."""
        if value is None:
            return {'type': 'null', 'value': None}
        if isinstance(value, bool):
            return {'type': 'boolean', 'value': value}
        if isinstance(value, int):
            return {'type': 'number', 'value': value}
        if isinstance(value, float):
            return {'type': 'number', 'value': value}
        if isinstance(value, str):
            return {'type': 'string', 'value': value}
        if isinstance(value, list):
            return {'type': 'array', 'value': [self._serialize_arg(v) for v in value]}
        if isinstance(value, dict):
            return {
                'type': 'object',
                'value': {k: self._serialize_arg(v) for k, v in value.items()},
            }
        if isinstance(value, JSModuleHandle):
            return {'type': 'handle', 'handle': value.handle}
        # Fallback: convert to string
        return {'type': 'string', 'value': str(value)}

    def _deserialize_result(self, data) -> object:
        """Convert a JSON wire format response back to a Python value."""
        if data is None:
            return None
        result_type = data.get('type')
        if result_type == 'null':
            return None
        if result_type == 'boolean':
            return data['value']
        if result_type == 'number':
            return data['value']
        if result_type == 'string':
            return data['value']
        if result_type == 'handle':
            return JSModuleHandle(data['handle'], data.get('typeName', 'Object'))
        if result_type == 'array':
            return [self._deserialize_result(item) for item in data.get('value', [])]
        if result_type == 'object':
            return {
                k: self._deserialize_result(v)
                for k, v in data.get('value', {}).items()
            }
        return data.get('value')
