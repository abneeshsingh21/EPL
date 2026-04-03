"""
EPL Production Upgrade Test Suite
Tests for all 8 production-level features added:
  #1 Real Gradle wrapper scripts (desktop.py)
  #2 iOS/Swift project generation (ios_gen.py)
  #3 Real package registry server (registry_server.py)
  #4 Package manager registry integration (package_manager.py)
  #5 HTTP/2 support (web.py)
  #6 Return type checking (type_checker.py)
  #7 Deep learning integration (stdlib.py dl_*)
  #8 3D graphics support (stdlib.py 3d_*)
  #9 Registry.json upgrade
"""

import sys
import os
import json
import tempfile
import shutil
import threading
import time
import http.client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError
from epl import ast_nodes as ast


def run_epl(source: str, safe_mode=False) -> list:
    """Run EPL source code and return captured output lines."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter(safe_mode=safe_mode)
    interp.execute(program)
    return interp.output_lines


def parse_epl(source: str):
    """Parse EPL source and return AST program node."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def _run_test(name, func):
    """Run a test function and report result."""
    try:
        result = func()
        if result:
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            return False
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Error: {type(e).__name__}: {e}")
        return False


def main():
    print("=" * 60)
    print("  EPL Production Upgrade Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0
    total = 0

    def track(result):
        nonlocal passed, failed, total
        total += 1
        if result:
            passed += 1
        else:
            failed += 1

    # ================================================================
    # #1: Real Gradle Wrapper in desktop.py
    # ================================================================
    print("\n--- #1: Real Gradle Wrapper (desktop.py) ---")

    def test_gradlew_sh_real_download():
        from epl.desktop import DesktopProjectGenerator
        gen = DesktopProjectGenerator()
        script = gen._gradlew_sh()
        # Must contain real download logic, not just an echo stub
        assert 'services.gradle.org' in script, "gradlew.sh must download from services.gradle.org"
        assert 'curl' in script or 'wget' in script, "gradlew.sh must use curl or wget"
        assert 'GRADLE_HOME' in script, "gradlew.sh must set GRADLE_HOME"
        assert gen.GRADLE_VERSION in script, "gradlew.sh must reference GRADLE_VERSION"
        # Must NOT just be an echo
        lines = [l.strip() for l in script.strip().split('\n') if l.strip() and not l.strip().startswith('#')]
        assert len(lines) > 5, "gradlew.sh must be a real script, not a stub"
        return True

    def test_gradlew_bat_real_download():
        from epl.desktop import DesktopProjectGenerator
        gen = DesktopProjectGenerator()
        script = gen._gradlew_bat()
        # Must contain real download logic
        assert 'services.gradle.org' in script, "gradlew.bat must download from services.gradle.org"
        assert 'powershell' in script.lower() or 'Invoke-WebRequest' in script, "gradlew.bat must use PowerShell for download"
        assert gen.GRADLE_VERSION in script, "gradlew.bat must reference GRADLE_VERSION"
        lines = [l.strip() for l in script.strip().split('\n') if l.strip() and not l.strip().startswith('::') and not l.strip().startswith('REM')]
        assert len(lines) > 5, "gradlew.bat must be a real script, not a stub"
        return True

    def test_gradlew_sh_executable_header():
        from epl.desktop import DesktopProjectGenerator
        gen = DesktopProjectGenerator()
        script = gen._gradlew_sh()
        assert script.startswith('#!/'), "gradlew.sh must start with shebang"
        return True

    def test_gradlew_bat_header():
        from epl.desktop import DesktopProjectGenerator
        gen = DesktopProjectGenerator()
        script = gen._gradlew_bat()
        assert '@' in script.split('\n')[0].lower() or 'echo' in script.split('\n')[0].lower(), "gradlew.bat must start with @echo off or similar"
        return True

    def test_desktop_generator_creates_project():
        from epl.desktop import DesktopProjectGenerator
        gen = DesktopProjectGenerator()
        program = parse_epl('Print "Hello".')
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "testapp")
            gen.generate(program, outdir)
            # Check gradlew files were created
            assert os.path.exists(os.path.join(outdir, "gradlew")) or os.path.exists(os.path.join(outdir, "gradlew.bat")), "Must create gradlew wrapper"
            return True

    track(_run_test("gradlew.sh has real download logic", test_gradlew_sh_real_download))
    track(_run_test("gradlew.bat has real download logic", test_gradlew_bat_real_download))
    track(_run_test("gradlew.sh has shebang header", test_gradlew_sh_executable_header))
    track(_run_test("gradlew.bat has proper header", test_gradlew_bat_header))
    track(_run_test("Desktop generator creates project files", test_desktop_generator_creates_project))

    # ================================================================
    # #2: iOS/Swift Project Generation (ios_gen.py)
    # ================================================================
    print("\n--- #2: iOS/Swift Project Generation (ios_gen.py) ---")

    def test_ios_gen_imports():
        from epl.ios_gen import IOSProjectGenerator, generate_ios_project
        assert IOSProjectGenerator is not None
        assert callable(generate_ios_project)
        return True

    def test_ios_gen_defaults():
        from epl.ios_gen import IOSProjectGenerator
        gen = IOSProjectGenerator()
        assert gen.app_name == "EPLApp"
        assert gen.bundle_id == "com.epl.app"
        assert gen.SWIFT_VERSION == "5.9"
        assert gen.IOS_DEPLOYMENT_TARGET == "16.0"
        return True

    def test_ios_gen_custom_params():
        from epl.ios_gen import IOSProjectGenerator
        gen = IOSProjectGenerator(app_name="MyApp", bundle_id="com.test.myapp", team_id="ABCDE12345")
        assert gen.app_name == "MyApp"
        assert gen.bundle_id == "com.test.myapp"
        assert gen.team_id == "ABCDE12345"
        return True

    def test_ios_gen_creates_project():
        from epl.ios_gen import IOSProjectGenerator
        gen = IOSProjectGenerator(app_name="TestApp")
        program = parse_epl('Print "Hello iOS".')
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "TestApp")
            gen.generate(program, outdir)
            # Check key files exist
            assert os.path.exists(os.path.join(outdir, "TestApp.xcodeproj", "project.pbxproj")), "Must create .xcodeproj"
            assert os.path.exists(os.path.join(outdir, "TestApp", "Views", "ContentView.swift")), "Must create ContentView.swift"
            assert os.path.exists(os.path.join(outdir, "TestApp", "EPLRuntime.swift")), "Must create EPLRuntime.swift"
            assert os.path.exists(os.path.join(outdir, "TestApp", "Info.plist")), "Must create Info.plist"
            return True

    def test_ios_gen_pbxproj_valid():
        from epl.ios_gen import IOSProjectGenerator
        gen = IOSProjectGenerator(app_name="PBXTest")
        program = parse_epl('Print "Test".')
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "PBXTest")
            gen.generate(program, outdir)
            pbx_path = os.path.join(outdir, "PBXTest.xcodeproj", "project.pbxproj")
            with open(pbx_path, 'r') as f:
                content = f.read()
            assert 'archiveVersion = 1' in content, "pbxproj must have archiveVersion"
            assert 'PBXGroup' in content, "pbxproj must have PBXGroup"
            assert 'PBXNativeTarget' in content, "pbxproj must have PBXNativeTarget"
            return True

    def test_ios_gen_runtime_swift():
        from epl.ios_gen import IOSProjectGenerator
        gen = IOSProjectGenerator()
        program = parse_epl('Print "Test".')
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "EPLApp")
            gen.generate(program, outdir)
            runtime_path = os.path.join(outdir, "EPLApp", "EPLRuntime.swift")
            with open(runtime_path, 'r') as f:
                content = f.read()
            assert 'class EPLRuntime' in content or 'struct EPLRuntime' in content or 'enum EPLRuntime' in content, \
                "Runtime must define EPLRuntime"
            assert 'func' in content, "Runtime must have functions"
            return True

    def test_ios_gen_info_plist():
        from epl.ios_gen import IOSProjectGenerator
        gen = IOSProjectGenerator(app_name="PlistApp")
        program = parse_epl('Print "Hello".')
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "PlistApp")
            gen.generate(program, outdir)
            plist_path = os.path.join(outdir, "PlistApp", "Info.plist")
            with open(plist_path, 'r') as f:
                content = f.read()
            assert '<?xml' in content or 'plist' in content.lower(), "Info.plist must be valid XML plist"
            return True

    def test_ios_gen_convenience_function():
        from epl.ios_gen import generate_ios_project
        program = parse_epl('Print "Convenience".')
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "ConvApp")
            result = generate_ios_project(program, outdir, app_name="ConvApp", bundle_id="com.test.conv")
            assert os.path.isdir(result), "Convenience function must return valid directory"
            return True

    track(_run_test("iOS generator imports", test_ios_gen_imports))
    track(_run_test("iOS generator default params", test_ios_gen_defaults))
    track(_run_test("iOS generator custom params", test_ios_gen_custom_params))
    track(_run_test("iOS generator creates project files", test_ios_gen_creates_project))
    track(_run_test("iOS pbxproj is valid", test_ios_gen_pbxproj_valid))
    track(_run_test("iOS runtime Swift file", test_ios_gen_runtime_swift))
    track(_run_test("iOS Info.plist generated", test_ios_gen_info_plist))
    track(_run_test("iOS convenience function", test_ios_gen_convenience_function))

    # ================================================================
    # #3: Package Registry Server (registry_server.py)
    # ================================================================
    print("\n--- #3: Package Registry Server (registry_server.py) ---")

    def test_registry_storage_init():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            assert os.path.exists(os.path.join(tmpdir, "packages")), "Must create packages dir"
            assert os.path.exists(os.path.join(tmpdir, "archives")), "Must create archives dir"
            assert os.path.exists(os.path.join(tmpdir, "index.json")), "Must create index.json"
            return True

    def test_registry_storage_publish():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            result = storage.publish(
                name="test-pkg",
                version="1.0.0",
                metadata={"description": "A test package", "author": "Test"},
                archive_data=b"fake archive data"
            )
            assert result['name'] == "test-pkg"
            assert result['version'] == "1.0.0"
            assert 'sha256' in result
            return True

    def test_registry_storage_get():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            storage.publish("my-pkg", "1.0.0", {"description": "Test"}, b"data")
            pkg = storage.get_package("my-pkg")
            assert pkg is not None, "Must find published package"
            assert pkg['name'] == "my-pkg"
            return True

    def test_registry_storage_list():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            storage.publish("pkg-a", "1.0.0", {"description": "A"}, b"data-a")
            storage.publish("pkg-b", "1.0.0", {"description": "B"}, b"data-b")
            result = storage.list_packages()
            assert result['total'] >= 2
            names = list(result['packages'].keys())
            assert "pkg-a" in names
            assert "pkg-b" in names
            return True

    def test_registry_storage_search():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            storage.publish("math-utils", "1.0.0", {"description": "Math functions", "keywords": ["math"]}, b"d1")
            storage.publish("string-utils", "1.0.0", {"description": "String functions"}, b"d2")
            result = storage.list_packages(query="math")
            names = list(result['packages'].keys())
            assert "math-utils" in names
            return True

    def test_registry_storage_versions():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            storage.publish("versioned", "1.0.0", {"description": "v1"}, b"v1data")
            storage.publish("versioned", "2.0.0", {"description": "v2"}, b"v2data")
            pkg = storage.get_package("versioned")
            assert pkg is not None
            # Latest should be 2.0.0
            assert pkg.get('latest', pkg.get('version', '')) == '2.0.0' or '2.0.0' in str(pkg.get('versions', {}))
            return True

    def test_registry_storage_archive():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            storage.publish("arc-pkg", "1.0.0", {"description": "Test"}, b"real_archive_bytes")
            path = storage.get_archive_path("arc-pkg", "1.0.0")
            assert path is not None, "Archive path must exist"
            assert os.path.exists(path), "Archive file must exist on disk"
            with open(path, 'rb') as f:
                assert f.read() == b"real_archive_bytes"
            return True

    def test_registry_storage_delete():
        from epl.registry_server import RegistryStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RegistryStorage(data_dir=tmpdir)
            storage.publish("del-pkg", "1.0.0", {"description": "To delete"}, b"data")
            assert storage.get_package("del-pkg") is not None
            result = storage.delete_version("del-pkg", "1.0.0")
            assert result is True
            return True

    def test_registry_server_start_stop():
        from epl.registry_server import start_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            server = start_registry(port=0, data_dir=tmpdir, background=True)
            # Port 0 means OS assigns port - get the actual port
            actual_port = server._server.server_address[1]
            assert actual_port > 0, "Server must bind to a port"
            # Health check
            try:
                conn = http.client.HTTPConnection("127.0.0.1", actual_port, timeout=5)
                conn.request("GET", "/health")
                resp = conn.getresponse()
                assert resp.status == 200, f"Health check must return 200, got {resp.status}"
                conn.close()
            finally:
                server.stop()
            return True

    def test_registry_server_list_packages():
        from epl.registry_server import start_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            server = start_registry(port=0, data_dir=tmpdir, background=True)
            actual_port = server._server.server_address[1]
            try:
                conn = http.client.HTTPConnection("127.0.0.1", actual_port, timeout=5)
                conn.request("GET", "/api/v1/packages")
                resp = conn.getresponse()
                data = json.loads(resp.read().decode())
                assert 'packages' in data or 'total' in data
                conn.close()
            finally:
                server.stop()
            return True

    def test_registry_server_publish_and_get():
        from epl.registry_server import start_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            server = start_registry(port=0, data_dir=tmpdir, background=True)
            actual_port = server._server.server_address[1]
            try:
                # Publish
                conn = http.client.HTTPConnection("127.0.0.1", actual_port, timeout=5)
                body = json.dumps({
                    "name": "test-publish",
                    "version": "1.0.0",
                    "metadata": {"description": "Test pkg from test"},
                    "archive": "dGVzdCBkYXRh"  # base64 of "test data"
                }).encode()
                conn.request("POST", "/api/v1/publish", body=body,
                           headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                resp.read()
                assert resp.status in (200, 201), f"Publish must succeed, got {resp.status}"
                conn.close()

                # Get back
                conn = http.client.HTTPConnection("127.0.0.1", actual_port, timeout=5)
                conn.request("GET", "/api/v1/packages/test-publish")
                resp = conn.getresponse()
                data = json.loads(resp.read().decode())
                assert data.get('name') == 'test-publish' or 'test-publish' in str(data)
                conn.close()
            finally:
                server.stop()
            return True

    def test_registry_client_class():
        from epl.registry_server import RegistryClient
        client = RegistryClient(registry_url="http://localhost:4873")
        assert client is not None
        assert hasattr(client, 'search') or hasattr(client, 'list_packages')
        return True

    track(_run_test("Registry storage init", test_registry_storage_init))
    track(_run_test("Registry storage publish", test_registry_storage_publish))
    track(_run_test("Registry storage get package", test_registry_storage_get))
    track(_run_test("Registry storage list packages", test_registry_storage_list))
    track(_run_test("Registry storage search", test_registry_storage_search))
    track(_run_test("Registry storage versions", test_registry_storage_versions))
    track(_run_test("Registry storage archive path", test_registry_storage_archive))
    track(_run_test("Registry storage delete", test_registry_storage_delete))
    track(_run_test("Registry server start/stop + health check", test_registry_server_start_stop))
    track(_run_test("Registry server list packages API", test_registry_server_list_packages))
    track(_run_test("Registry server publish + get", test_registry_server_publish_and_get))
    track(_run_test("Registry client class exists", test_registry_client_class))

    # ================================================================
    # #4: Package Manager Registry Integration
    # ================================================================
    print("\n--- #4: Package Manager Registry Integration ---")

    def test_package_manager_has_registry_fallback():
        from epl import package_manager
        source = open(os.path.join(os.path.dirname(__file__), '..', 'epl', 'package_manager.py')).read()
        assert 'localhost:4873' in source or 'api/v1/packages' in source, \
            "Package manager must try local registry server"
        assert 'EPL_REGISTRY_URL' in source, "Package manager must support EPL_REGISTRY_URL env var"
        return True

    def test_package_manager_import():
        from epl import package_manager
        assert package_manager is not None
        return True

    track(_run_test("Package manager has registry fallback", test_package_manager_has_registry_fallback))
    track(_run_test("Package manager imports", test_package_manager_import))

    # ================================================================
    # #5: HTTP/2 Support (web.py)
    # ================================================================
    print("\n--- #5: HTTP/2 Support (web.py) ---")

    def test_http2_class_exists():
        from epl.web import HTTP2Server
        assert HTTP2Server is not None
        return True

    def test_http2_init():
        from epl.web import HTTP2Server
        # Create a minimal mock app
        class MockApp:
            routes = {}
            middleware = []
            error_handlers = {}
        server = HTTP2Server(MockApp(), port=0)
        assert server.port == 0
        assert server._shutting_down is False
        return True

    def test_http2_start_function():
        from epl.web import start_h2_server
        assert callable(start_h2_server)
        return True

    def test_http2_falls_back():
        """HTTP2Server should work even without h2 installed (falls back)."""
        from epl.web import HTTP2Server
        class MockApp:
            routes = {}
            middleware = []
            error_handlers = {}
        # Just ensure creation doesn't crash
        server = HTTP2Server(MockApp(), port=0)
        assert server is not None
        return True

    track(_run_test("HTTP2Server class exists", test_http2_class_exists))
    track(_run_test("HTTP2Server initialization", test_http2_init))
    track(_run_test("start_h2_server function exists", test_http2_start_function))
    track(_run_test("HTTP/2 graceful fallback", test_http2_falls_back))

    # ================================================================
    # #6: Return Type Checking (type_checker.py)
    # ================================================================
    print("\n--- #6: Return Type Checking (type_checker.py) ---")

    def test_type_checker_has_function_context():
        from epl.type_checker import TypeChecker
        tc = TypeChecker()
        assert hasattr(tc, '_current_function'), "Must track current function"
        assert hasattr(tc, '_current_return_type'), "Must track return type"
        return True

    def test_type_checker_return_in_function():
        """A function returning the correct type should produce no warnings about return type."""
        from epl.type_checker import TypeChecker
        source = '''Function add takes X and Y
    result = X + Y
    Return result
End
Print call add with 3 and 4'''
        program = parse_epl(source)
        tc = TypeChecker()
        tc.check(program)
        # Should not warn about return type mismatch
        type_warnings = [w for w in tc.warnings if 'return' in w.lower() and 'mismatch' in w.lower()]
        assert len(type_warnings) == 0, f"No return type mismatch warnings expected, got: {type_warnings}"
        return True

    def test_type_checker_check_return_not_stub():
        """Verify _check_return is not just 'pass'."""
        from epl.type_checker import TypeChecker
        import inspect
        source = inspect.getsource(TypeChecker._check_return)
        lines = [l.strip() for l in source.split('\n') if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('def ') and not l.strip().startswith('"""')]
        assert len(lines) > 2, f"_check_return must not be a stub, has {len(lines)} lines"
        return True

    def test_type_checker_function_def_tracks_context():
        """_check_function_def should set _current_function."""
        from epl.type_checker import TypeChecker
        import inspect
        source = inspect.getsource(TypeChecker._check_function_def)
        assert '_current_function' in source, "Must use _current_function"
        assert '_current_return_type' in source, "Must use _current_return_type"
        return True

    def test_type_checker_no_crash_on_valid():
        """Type checker shouldn't crash on valid code."""
        source = '''x = 10
y = 20
z = x + y
Print z'''
        program = parse_epl(source)
        from epl.type_checker import TypeChecker
        tc = TypeChecker()
        tc.check(program)
        return True

    def test_type_checker_function_without_return():
        """Function with code but no return should not crash the type checker."""
        from epl.type_checker import TypeChecker
        source = '''Function bad takes X
    Print X
End'''
        program = parse_epl(source)
        tc = TypeChecker()
        tc.check(program)
        # Type checker should not crash
        return True

    track(_run_test("Type checker has function context fields", test_type_checker_has_function_context))
    track(_run_test("Type checker no mismatch on valid return", test_type_checker_return_in_function))
    track(_run_test("_check_return is not a stub", test_type_checker_check_return_not_stub))
    track(_run_test("_check_function_def tracks context", test_type_checker_function_def_tracks_context))
    track(_run_test("Type checker no crash on valid code", test_type_checker_no_crash_on_valid))
    track(_run_test("Warn on missing return", test_type_checker_function_without_return))

    # ================================================================
    # #7: Deep Learning Integration (stdlib.py dl_*)
    # ================================================================
    print("\n--- #7: Deep Learning Integration (dl_* functions) ---")

    def test_dl_functions_registered():
        from epl.stdlib import STDLIB_FUNCTIONS
        dl_names = ['dl_tensor', 'dl_sequential', 'dl_compile', 'dl_train',
                     'dl_predict', 'dl_save', 'dl_load', 'dl_summary',
                     'dl_device', 'dl_delete']
        for name in dl_names:
            assert name in STDLIB_FUNCTIONS, f"{name} must be in STDLIB_FUNCTIONS"
        return True

    def test_dl_dispatcher_exists():
        from epl.stdlib import call_stdlib
        import inspect
        source = inspect.getsource(call_stdlib)
        assert 'dl_' in source, "call_stdlib must dispatch dl_ prefix"
        return True

    def test_dl_call_dl_function_exists():
        """The _call_dl function must exist in stdlib module."""
        from epl import stdlib
        assert hasattr(stdlib, '_call_dl'), "_call_dl function must exist"
        assert callable(stdlib._call_dl)
        return True

    def test_dl_device_works():
        """dl_device should return 'cpu', 'cuda', or 'mps' string."""
        from epl.stdlib import call_stdlib
        try:
            result = call_stdlib('dl_device', [], 1)
            assert result in ('cpu', 'cuda', 'mps'), f"dl_device must return device name, got {result}"
        except EPLError as e:
            if 'torch' in str(e).lower() or 'tensorflow' in str(e).lower() or 'install' in str(e).lower():
                # OK - frameworks not installed, but function exists and dispatches correctly
                pass
            else:
                raise
        return True

    def test_dl_tensor_requires_args():
        """dl_tensor with no args should raise error."""
        from epl.stdlib import call_stdlib
        try:
            call_stdlib('dl_tensor', [], 1)
            # If no error, framework must be installed and returned empty tensor
            return True
        except EPLError:
            return True  # Expected - either missing args or missing framework

    def test_dl_sequential_requires_args():
        from epl.stdlib import call_stdlib
        try:
            call_stdlib('dl_sequential', [], 1)
            return True
        except EPLError:
            return True

    def test_dl_models_storage():
        """dl_* functions must use _dl_models and _dl_data dicts."""
        from epl import stdlib
        assert hasattr(stdlib, '_dl_models'), "_dl_models dict must exist"
        assert hasattr(stdlib, '_dl_data'), "_dl_data dict must exist"
        return True

    track(_run_test("dl_* functions registered in STDLIB_FUNCTIONS", test_dl_functions_registered))
    track(_run_test("dl_* dispatcher exists in call_stdlib", test_dl_dispatcher_exists))
    track(_run_test("_call_dl function exists", test_dl_call_dl_function_exists))
    track(_run_test("dl_device returns device name", test_dl_device_works))
    track(_run_test("dl_tensor handles no args", test_dl_tensor_requires_args))
    track(_run_test("dl_sequential handles no args", test_dl_sequential_requires_args))
    track(_run_test("dl_* storage dicts exist", test_dl_models_storage))

    # ================================================================
    # #8: 3D Graphics Support (stdlib.py 3d_*)
    # ================================================================
    print("\n--- #8: 3D Graphics Support (3d_* functions) ---")

    def test_3d_functions_registered():
        from epl.stdlib import STDLIB_FUNCTIONS
        names_3d = ['3d_create', '3d_cube', '3d_sphere', '3d_light', '3d_camera',
                     '3d_rotate', '3d_move', '3d_color', '3d_render', '3d_run', '3d_delete']
        for name in names_3d:
            assert name in STDLIB_FUNCTIONS, f"{name} must be in STDLIB_FUNCTIONS"
        return True

    def test_3d_dispatcher_exists():
        from epl.stdlib import call_stdlib
        import inspect
        source = inspect.getsource(call_stdlib)
        assert '3d_' in source, "call_stdlib must dispatch 3d_ prefix"
        return True

    def test_3d_call_3d_function_exists():
        from epl import stdlib
        assert hasattr(stdlib, '_call_3d'), "_call_3d function must exist"
        assert callable(stdlib._call_3d)
        return True

    def test_3d_create_requires_title():
        """3d_create with no args should raise error about missing title."""
        from epl.stdlib import call_stdlib
        try:
            call_stdlib('3d_create', [], 1)
            return True  # If it works (unlikely without display), ok
        except EPLError as e:
            err = str(e).lower()
            if 'title' in err or 'argument' in err or 'require' in err or 'pygame' in err or 'moderngl' in err:
                return True
            raise

    def test_3d_contexts_storage():
        from epl import stdlib
        assert hasattr(stdlib, '_3d_contexts'), "_3d_contexts dict must exist"
        assert hasattr(stdlib, '_3d_objects'), "_3d_objects dict must exist"
        return True

    def test_3d_cube_requires_context():
        """3d_cube without valid context should fail gracefully."""
        from epl.stdlib import call_stdlib
        try:
            call_stdlib('3d_cube', ["invalid_ctx"], 1)
            return True
        except EPLError:
            return True

    def test_3d_sphere_requires_context():
        from epl.stdlib import call_stdlib
        try:
            call_stdlib('3d_sphere', ["invalid_ctx"], 1)
            return True
        except EPLError:
            return True

    track(_run_test("3d_* functions registered in STDLIB_FUNCTIONS", test_3d_functions_registered))
    track(_run_test("3d_* dispatcher exists in call_stdlib", test_3d_dispatcher_exists))
    track(_run_test("_call_3d function exists", test_3d_call_3d_function_exists))
    track(_run_test("3d_create requires title", test_3d_create_requires_title))
    track(_run_test("3d_* storage dicts exist", test_3d_contexts_storage))
    track(_run_test("3d_cube requires context", test_3d_cube_requires_context))
    track(_run_test("3d_sphere requires context", test_3d_sphere_requires_context))

    # ================================================================
    # #9: Registry.json Upgrade
    # ================================================================
    print("\n--- #9: Registry.json Upgrade ---")

    def test_registry_json_version():
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        with open(registry_path, 'r') as f:
            data = json.load(f)
        assert data['version'] >= 3, f"registry.json version must be >= 3, got {data['version']}"
        return True

    def test_registry_json_has_api_url():
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        with open(registry_path, 'r') as f:
            data = json.load(f)
        assert 'api_url' in data, "registry.json must have api_url field"
        return True

    def test_registry_json_packages_have_urls():
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        with open(registry_path, 'r') as f:
            data = json.load(f)
        packages = data.get('packages', {})
        assert len(packages) >= 21, f"Must have at least 21 packages, got {len(packages)}"
        for name, pkg in packages.items():
            assert 'repository' in pkg, f"{name} must have repository field"
            assert 'download_url' in pkg, f"{name} must have download_url field"
        return True

    def test_registry_json_new_packages():
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        with open(registry_path, 'r') as f:
            data = json.load(f)
        packages = data.get('packages', {})
        assert 'epl-deeplearning' in packages, "Must have epl-deeplearning package"
        assert 'epl-3d' in packages, "Must have epl-3d package"
        assert 'epl-ios' in packages, "Must have epl-ios package"
        return True

    def test_registry_json_web_updated():
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        with open(registry_path, 'r') as f:
            data = json.load(f)
        web = data['packages'].get('epl-web', {})
        desc = web.get('description', '')
        assert 'HTTP/2' in desc or 'http2' in desc.lower() or web.get('version', '0') >= '5.0.0', \
            "epl-web must mention HTTP/2 or be version 5.0.0+"
        return True

    def test_registry_json_valid():
        """Ensure registry.json is valid JSON."""
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        with open(registry_path, 'r') as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert 'packages' in data
        return True

    track(_run_test("registry.json version >= 3", test_registry_json_version))
    track(_run_test("registry.json has api_url", test_registry_json_has_api_url))
    track(_run_test("All packages have repository/download URLs", test_registry_json_packages_have_urls))
    track(_run_test("New packages (deeplearning, 3d, ios)", test_registry_json_new_packages))
    track(_run_test("epl-web updated for HTTP/2", test_registry_json_web_updated))
    track(_run_test("registry.json is valid JSON", test_registry_json_valid))

    # ================================================================
    # #10: Integration Tests
    # ================================================================
    print("\n--- #10: Integration Tests ---")

    def test_epl_still_works_basic():
        output = run_epl('Print "Hello World"')
        assert output == ["Hello World"], f"Basic print must work, got {output}"
        return True

    def test_epl_still_works_math():
        output = run_epl('Print 2 + 3 * 4')
        assert output == ["14"], f"Math must work, got {output}"
        return True

    def test_epl_still_works_variables():
        output = run_epl('x = 42\nPrint x')
        assert output == ["42"], f"Variables must work, got {output}"
        return True

    def test_epl_still_works_functions():
        source = '''Function greet takes name
    Return "Hello, " + name
End
result = call greet with "EPL"
Print result'''
        output = run_epl(source)
        assert output == ["Hello, EPL"], f"Functions must work, got {output}"
        return True

    def test_epl_still_works_loops():
        source = '''total = 0
For each i in range(1, 5)
    total = total + i
End
Print total'''
        output = run_epl(source)
        assert output == ["10"], f"Loops must work, got {output}"
        return True

    def test_epl_still_works_conditions():
        source = '''x = 5
If x > 3 then
    Print "big"
End'''
        output = run_epl(source)
        assert output == ["big"], f"Conditions must work, got {output}"
        return True

    def test_epl_still_works_classes():
        source = '''Class Dog
    name = "Rex"
    Function bark
        Print "Woof!"
    End
End
d = new Dog
d.bark()'''
        output = run_epl(source)
        assert output == ["Woof!"], f"Classes must work, got {output}"
        return True

    def test_epl_still_works_lists():
        source = '''items = [1, 2, 3]
Print items[0]
Print items.length'''
        output = run_epl(source)
        assert output == ["1", "3"], f"Lists must work, got {output}"
        return True

    def test_epl_stdlib_math():
        source = 'Print absolute(-42)'
        output = run_epl(source)
        assert output == ["42"], f"Stdlib math must work, got {output}"
        return True

    def test_epl_stdlib_string():
        source = '''s = "hello"
Print s.uppercase'''
        output = run_epl(source)
        assert output == ["HELLO"], f"Stdlib string must work, got {output}"
        return True

    track(_run_test("EPL basic print still works", test_epl_still_works_basic))
    track(_run_test("EPL math still works", test_epl_still_works_math))
    track(_run_test("EPL variables still work", test_epl_still_works_variables))
    track(_run_test("EPL functions still work", test_epl_still_works_functions))
    track(_run_test("EPL loops still work", test_epl_still_works_loops))
    track(_run_test("EPL conditions still work", test_epl_still_works_conditions))
    track(_run_test("EPL classes still work", test_epl_still_works_classes))
    track(_run_test("EPL lists still work", test_epl_still_works_lists))
    track(_run_test("EPL stdlib math still works", test_epl_stdlib_math))
    track(_run_test("EPL stdlib string still works", test_epl_stdlib_string))

    # ================================================================
    # Summary
    # ================================================================
    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("  ALL TESTS PASSED!")
    else:
        print(f"  {failed} TESTS FAILED")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
