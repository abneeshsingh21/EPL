"""Smoke tests for maintained reference apps and package workflows."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import json
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.desktop import generate_desktop_project
from epl.deploy import deploy_generate
from epl.interpreter import Interpreter
from epl.kotlin_gen import AndroidProjectGenerator, generate_android_project
from epl.lexer import Lexer
from epl.package_manager import install_package, load_manifest, pack_package, validate_package
from epl.parser import Parser
from epl.web import start_server


ROOT = Path(__file__).resolve().parents[1]
APPS_DIR = ROOT / "apps"
PACKAGES_DIR = ROOT / "packages"


def _parse_program(path: Path):
    source = path.read_text(encoding="utf-8")
    return Parser(Lexer(source).tokenize()).parse()


def _execute_program(path: Path) -> Interpreter:
    program = _parse_program(path)
    interpreter = Interpreter()
    interpreter.execute(program)
    return interpreter


def _pick_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_server(base_url: str, health_path: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}{health_path}", timeout=0.5):
                return
        except Exception:
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for server at {base_url}{health_path}")


def _start_web_app(interpreter: Interpreter):
    import epl.web as web_module

    port = _pick_free_port()
    app = getattr(interpreter, "_web_app", None)
    if app is None:
        raise AssertionError("Reference app did not create an EPL WebApp.")

    thread = threading.Thread(
        target=start_server,
        args=(app, port, interpreter),
        kwargs={"threaded": True, "workers": 4},
        daemon=True,
    )
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, getattr(app, "_health_path", "/_health"))
        return base_url, thread, web_module
    except Exception:
        if web_module._active_server is not None:
            web_module._active_server.shutdown()
            web_module._active_server.server_close()
            web_module._active_server = None
        thread.join(timeout=2)
        raise


def _http_get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def _http_get_json(url: str):
    return json.loads(_http_get_text(url))


def _run_command(cmd, cwd: Path, *, env=None, timeout: float = 300.0):
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = (
        str(ROOT)
        if not merged_env.get("PYTHONPATH")
        else os.pathsep.join([str(ROOT), merged_env["PYTHONPATH"]])
    )
    if env:
        merged_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"Command timed out: {' '.join(map(str, cmd))}\n"
            f"cwd: {cwd}\n"
            f"timeout: {timeout}\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}"
        ) from exc
    if result.returncode != 0:
        raise AssertionError(
            f"Command failed: {' '.join(map(str, cmd))}\n"
            f"cwd: {cwd}\n"
            f"exit: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _stop_process(proc: subprocess.Popen) -> str:
    if proc.poll() is None:
        proc.terminate()
        try:
            stdout, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, _ = proc.communicate(timeout=5)
        return stdout or ""
    stdout, _ = proc.communicate(timeout=5)
    return stdout or ""


def _start_cli_server(project_dir: Path):
    port = _pick_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(ROOT)
        if not env.get("PYTHONPATH")
        else os.pathsep.join([str(ROOT), env["PYTHONPATH"]])
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "epl", "serve", "--port", str(port)],
        cwd=str(project_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, "/_health", timeout=15.0)
    except Exception as exc:
        output = _stop_process(proc)
        raise AssertionError(
            f"Timed out waiting for CLI server for {project_dir}.\nProcess output:\n{output}"
        ) from exc
    return base_url, proc


def _load_module_from_path(module_path: Path):
    module_name = f"epl_dynamic_{module_path.stem}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to import module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _start_wsgi_server(application):
    from wsgiref.simple_server import make_server

    port = _pick_free_port()
    server = make_server("127.0.0.1", port, application)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, "/_health", timeout=10.0)
    except Exception:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        raise
    return base_url, server, thread


def _asgi_request(application, path: str, method: str = "GET"):
    messages = []
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1")],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 8000),
    }

    asyncio.run(application(scope, receive, send))

    start = next(msg for msg in messages if msg["type"] == "http.response.start")
    body = b"".join(msg.get("body", b"") for msg in messages if msg["type"] == "http.response.body")
    headers = {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in start.get("headers", [])
    }
    return start["status"], headers, body


def _android_sdk_path():
    return os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")


def _write_android_local_properties(project_dir: Path, sdk_path: str) -> None:
    escaped = sdk_path.replace("\\", "\\\\")
    (project_dir / "local.properties").write_text(f"sdk.dir={escaped}\n", encoding="utf-8")


def _gradle_command(project_dir: Path):
    return (
        ["cmd", "/c", str(project_dir / "gradlew.bat")]
        if os.name == "nt"
        else [str(project_dir / "gradlew")]
    )


def _gradle_tempdir(prefix: str):
    kwargs = {"prefix": prefix}
    if os.name == "nt":
        kwargs["ignore_cleanup_errors"] = True
    return tempfile.TemporaryDirectory(**kwargs)


def _shared_gradle_user_home(name: str) -> Path:
    home = Path(tempfile.gettempdir()) / "epl_gradle_home" / name
    home.mkdir(parents=True, exist_ok=True)
    return home


class TestReferenceApps(unittest.TestCase):
    def test_reference_backend_api_routes(self):
        source = APPS_DIR / "reference-backend-api" / "src" / "main.epl"
        interpreter = _execute_program(source)
        base_url, thread, web_module = _start_web_app(interpreter)
        try:
            health = _http_get_json(f"{base_url}/api/health")
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["service"], "reference-backend-api")

            todos = _http_get_json(f"{base_url}/api/todos")
            self.assertEqual(len(todos), 2)
            self.assertEqual(todos[0]["title"], "Ship EPL")
        finally:
            if web_module._active_server is not None:
                web_module._active_server.shutdown()
                web_module._active_server.server_close()
                web_module._active_server = None
            thread.join(timeout=2)

    def test_reference_fullstack_flow(self):
        source = APPS_DIR / "reference-fullstack-web" / "src" / "main.epl"
        interpreter = _execute_program(source)
        base_url, thread, web_module = _start_web_app(interpreter)
        try:
            home = _http_get_text(f"{base_url}/")
            self.assertIn("EPL Reference Fullstack", home)
            self.assertIn("Notes API", home)

            login = _http_get_json(f"{base_url}/api/login")
            self.assertEqual(login["user"], "alice")
            self.assertEqual(login["token"], "reference-session")

            notes = _http_get_json(f"{base_url}/api/notes")
            self.assertEqual(notes["user"], "alice")
            self.assertEqual(len(notes["notes"]), 2)
        finally:
            if web_module._active_server is not None:
                web_module._active_server.shutdown()
                web_module._active_server.server_close()
                web_module._active_server = None
            thread.join(timeout=2)

    def test_reference_fullstack_cli_serve_flow(self):
        project_dir = APPS_DIR / "reference-fullstack-web"
        base_url, proc = _start_cli_server(project_dir)
        try:
            home = _http_get_text(f"{base_url}/")
            self.assertIn("EPL Reference Fullstack", home)
            self.assertIn("Login API", home)

            login = _http_get_json(f"{base_url}/api/login")
            self.assertEqual(login["user"], "alice")

            notes = _http_get_json(f"{base_url}/api/notes")
            self.assertEqual(notes["user"], "alice")
            self.assertEqual(len(notes["notes"]), 2)
        finally:
            _stop_process(proc)

    def test_reference_fullstack_deploy_generation(self):
        source_project = APPS_DIR / "reference-fullstack-web"
        with tempfile.TemporaryDirectory(prefix="epl_ref_deploy_") as tmpdir:
            project_dir = Path(tmpdir) / "reference-fullstack-web"
            shutil.copytree(source_project, project_dir)
            out_dir = project_dir / "deploy"
            _run_command(
                [
                    sys.executable,
                    "-m",
                    "epl",
                    "deploy",
                    "all",
                    "--name",
                    "reference-fullstack-web",
                    "--output",
                    "deploy",
                ],
                cwd=project_dir,
                timeout=120.0,
            )

            expected = [
                out_dir / "wsgi.py",
                out_dir / "gunicorn_conf.py",
                out_dir / "asgi.py",
                out_dir / "Dockerfile",
                out_dir / "docker-compose.yml",
                out_dir / "nginx" / "epl_nginx.conf",
                out_dir / "reference-fullstack-web.service",
            ]
            for path in expected:
                self.assertTrue(path.exists(), path)

            wsgi_text = (out_dir / "wsgi.py").read_text(encoding="utf-8")
            asgi_text = (out_dir / "asgi.py").read_text(encoding="utf-8")
            compose_text = (out_dir / "docker-compose.yml").read_text(encoding="utf-8")
            self.assertIn("src/main.epl", wsgi_text)
            self.assertIn("src/main.epl", asgi_text)
            self.assertIn('context: ".."', compose_text)
            self.assertIn('dockerfile: "deploy/Dockerfile"', compose_text)

    def test_reference_fullstack_generated_wsgi_deploy_adapter(self):
        source_project = APPS_DIR / "reference-fullstack-web"
        with tempfile.TemporaryDirectory(prefix="epl_ref_wsgi_") as tmpdir:
            project_dir = Path(tmpdir) / "reference-fullstack-web"
            shutil.copytree(source_project, project_dir)
            _run_command(
                [
                    sys.executable,
                    "-m",
                    "epl",
                    "deploy",
                    "all",
                    "--name",
                    "reference-fullstack-web",
                    "--output",
                    "deploy",
                ],
                cwd=project_dir,
                timeout=120.0,
            )

            module = _load_module_from_path(project_dir / "deploy" / "wsgi.py")
            base_url, server, thread = _start_wsgi_server(module.application)
            try:
                home = _http_get_text(f"{base_url}/")
                self.assertIn("EPL Reference Fullstack", home)

                login = _http_get_json(f"{base_url}/api/login")
                self.assertEqual(login["user"], "alice")

                notes = _http_get_json(f"{base_url}/api/notes")
                self.assertEqual(notes["user"], "alice")
                self.assertEqual(len(notes["notes"]), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_reference_fullstack_generated_asgi_deploy_adapter(self):
        source_project = APPS_DIR / "reference-fullstack-web"
        with tempfile.TemporaryDirectory(prefix="epl_ref_asgi_") as tmpdir:
            project_dir = Path(tmpdir) / "reference-fullstack-web"
            shutil.copytree(source_project, project_dir)
            _run_command(
                [
                    sys.executable,
                    "-m",
                    "epl",
                    "deploy",
                    "all",
                    "--name",
                    "reference-fullstack-web",
                    "--output",
                    "deploy",
                ],
                cwd=project_dir,
                timeout=120.0,
            )

            module = _load_module_from_path(project_dir / "deploy" / "asgi.py")

            status, headers, body = _asgi_request(module.application, "/")
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("content-type"), "text/html; charset=utf-8")
            self.assertIn("EPL Reference Fullstack", body.decode("utf-8"))

            status, headers, body = _asgi_request(module.application, "/api/login")
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("content-type"), "application/json; charset=utf-8")
            login = json.loads(body.decode("utf-8"))
            self.assertEqual(login["user"], "alice")

            status, headers, body = _asgi_request(module.application, "/api/notes")
            self.assertEqual(status, 200)
            notes = json.loads(body.decode("utf-8"))
            self.assertEqual(notes["user"], "alice")
            self.assertEqual(len(notes["notes"]), 2)

    @unittest.skipUnless(
        os.environ.get("EPL_RUN_DOCKER_DEPLOY_TESTS") == "1",
        "Set EPL_RUN_DOCKER_DEPLOY_TESTS=1 to run Docker deploy validation.",
    )
    def test_reference_fullstack_docker_deploy_smoke(self):
        if shutil.which("docker") is None:
            self.skipTest("Docker is required for container deploy validation.")
        docker_info = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )
        if docker_info.returncode != 0:
            self.skipTest("Docker daemon is not available for container deploy validation.")

        source_project = APPS_DIR / "reference-fullstack-web"
        with tempfile.TemporaryDirectory(prefix="epl_ref_docker_") as tmpdir:
            project_dir = Path(tmpdir) / "reference-fullstack-web"
            shutil.copytree(source_project, project_dir)
            out_dir = project_dir / "deploy"
            dist_dir = out_dir / "dist"
            dist_dir.mkdir(parents=True, exist_ok=True)
            suffix = str(time.time_ns())
            host_port = _pick_free_port()
            app_name = f"reference-fullstack-web-{suffix}"
            compose_project = f"eplref{suffix}"

            _run_command(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--outdir",
                    str(dist_dir),
                ],
                cwd=ROOT,
                timeout=1200.0,
            )
            wheel_path = next(dist_dir.glob("*.whl"))

            deploy_generate(
                "all",
                output_dir=str(out_dir),
                app_name=app_name,
                project_root=str(project_dir),
                port=host_port,
                nginx=False,
                epl_requirement=f"./dist/{wheel_path.name}",
            )

            compose_file = out_dir / "docker-compose.yml"
            compose_cmd = [
                "docker",
                "compose",
                "-p",
                compose_project,
                "-f",
                str(compose_file),
            ]

            _run_command(compose_cmd + ["config"], cwd=project_dir, timeout=120.0)

            try:
                _run_command(compose_cmd + ["up", "-d", "--build"], cwd=project_dir, timeout=2400.0)

                base_url = f"http://127.0.0.1:{host_port}"
                _wait_for_server(base_url, "/_health", timeout=60.0)

                login = _http_get_json(f"{base_url}/api/login")
                self.assertEqual(login["user"], "alice")

                notes = _http_get_json(f"{base_url}/api/notes")
                self.assertEqual(notes["user"], "alice")
                self.assertEqual(len(notes["notes"]), 2)
            finally:
                subprocess.run(
                    compose_cmd + ["down", "--volumes", "--remove-orphans", "--rmi", "local"],
                    cwd=str(project_dir),
                    capture_output=True,
                    text=True,
                )

    def test_reference_android_project_generation(self):
        source = APPS_DIR / "reference-android" / "src" / "main.epl"
        program = _parse_program(source)

        with tempfile.TemporaryDirectory(prefix="epl_ref_android_") as tmpdir:
            out_dir = Path(tmpdir) / "android_app"
            generate_android_project(
                program,
                str(out_dir),
                app_name="ReferenceAndroid",
                package="com.epl.reference.android",
            )

            self.assertTrue((out_dir / "settings.gradle.kts").exists())
            self.assertTrue((out_dir / "app" / "build.gradle.kts").exists())
            self.assertTrue((out_dir / "gradlew").exists())
            self.assertTrue((out_dir / "gradlew.bat").exists())
            self.assertTrue((out_dir / "gradle" / "wrapper" / "gradle-wrapper.jar").exists())
            self.assertTrue((out_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").exists())
            self.assertTrue(
                (out_dir / "app" / "src" / "main" / "java" / "com" / "epl" / "reference" / "android" / "MainActivity.kt").exists()
            )
            self.assertTrue((out_dir / "app" / "src" / "main" / "AndroidManifest.xml").exists())

            gradlew_text = (out_dir / "gradlew").read_text(encoding="utf-8")
            gradlew_bat_text = (out_dir / "gradlew.bat").read_text(encoding="utf-8")
            wrapper_props = (out_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(encoding="utf-8")
            manifest_text = (out_dir / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

            self.assertIn("Gradle start up script for POSIX generated by Gradle", gradlew_text)
            self.assertIn("org.gradle.wrapper.GradleWrapperMain", gradlew_text)
            self.assertNotIn("Downloading Gradle", gradlew_text)
            self.assertNotIn("curl -fsSL", gradlew_text)

            self.assertIn("Gradle startup script for Windows", gradlew_bat_text)
            self.assertIn("org.gradle.wrapper.GradleWrapperMain", gradlew_bat_text)
            self.assertNotIn("DownloadFile", gradlew_bat_text)
            self.assertNotIn("Downloading Gradle", gradlew_bat_text)
            self.assertNotIn('package="com.epl.reference.android"', manifest_text)
            self.assertIn('android:name="com.epl.reference.android.MainActivity"', manifest_text)
            self.assertIn('android:name="com.epl.reference.android.EPLApplication"', manifest_text)

            self.assertIn(
                f"gradle-{AndroidProjectGenerator.GRADLE_WRAPPER_VERSION}-bin.zip",
                wrapper_props,
            )

    @unittest.skipUnless(
        os.environ.get("EPL_RUN_ANDROID_BUILD_TESTS") == "1",
        "Set EPL_RUN_ANDROID_BUILD_TESTS=1 to run Android Gradle validation.",
    )
    def test_reference_android_gradle_build(self):
        sdk_path = _android_sdk_path()
        if not sdk_path:
            self.skipTest("ANDROID_SDK_ROOT or ANDROID_HOME is required for Android build validation.")

        source = APPS_DIR / "reference-android" / "src" / "main.epl"
        program = _parse_program(source)

        with _gradle_tempdir("epl_ref_android_build_") as tmpdir:
            tmp_path = Path(tmpdir)
            out_dir = tmp_path / "android_app"
            generate_android_project(
                program,
                str(out_dir),
                app_name="ReferenceAndroid",
                package="com.epl.reference.android",
            )
            _write_android_local_properties(out_dir, sdk_path)

            env = os.environ.copy()
            env.setdefault("ANDROID_SDK_ROOT", sdk_path)
            env.setdefault("ANDROID_HOME", sdk_path)
            env["GRADLE_USER_HOME"] = str(_shared_gradle_user_home("android"))
            if os.name == "nt":
                java_tool_options = env.get("JAVA_TOOL_OPTIONS", "").strip()
                windows_root = "-Djavax.net.ssl.trustStoreType=WINDOWS-ROOT"
                if windows_root not in java_tool_options.split():
                    env["JAVA_TOOL_OPTIONS"] = (
                        f"{java_tool_options} {windows_root}".strip()
                    )

            try:
                _run_command(
                    _gradle_command(out_dir)
                    + [
                        "lintDebug",
                        "testDebugUnitTest",
                        "assembleDebug",
                        "assembleRelease",
                        "--stacktrace",
                        "--no-daemon",
                    ],
                    cwd=out_dir,
                    env=env,
                    timeout=2400.0,
                )
            except AssertionError as exc:
                message = str(exc)
                if (
                    "dl.google.com" in message
                    and (
                        "Remote host terminated the handshake" in message
                        or "TLS protocol versions" in message
                    )
                ):
                    self.skipTest(
                        "Local JDK/network could not reach Google Maven over TLS for Android dependency resolution."
                    )
                raise

            debug_apk_dir = out_dir / "app" / "build" / "outputs" / "apk" / "debug"
            release_apk_dir = out_dir / "app" / "build" / "outputs" / "apk" / "release"
            lint_reports_dir = out_dir / "app" / "build" / "reports"

            self.assertTrue(debug_apk_dir.exists())
            self.assertTrue(any(debug_apk_dir.glob("*.apk")))
            self.assertTrue(release_apk_dir.exists())
            self.assertTrue(any(release_apk_dir.glob("*.apk")))
            self.assertTrue(any(lint_reports_dir.rglob("lint-results-debug.*")))

    def test_reference_desktop_project_generation(self):
        source = APPS_DIR / "reference-desktop" / "src" / "main.epl"
        program = _parse_program(source)

        with tempfile.TemporaryDirectory(prefix="epl_ref_desktop_") as tmpdir:
            out_dir = Path(tmpdir) / "desktop_app"
            generate_desktop_project(
                program,
                str(out_dir),
                app_name="ReferenceDesktop",
                package="com.epl.reference.desktop",
                width=1024,
                height=768,
            )

            self.assertTrue((out_dir / "build.gradle.kts").exists())
            self.assertTrue((out_dir / "settings.gradle.kts").exists())
            self.assertTrue(
                (out_dir / "src" / "main" / "kotlin" / "com" / "epl" / "reference" / "desktop" / "Main.kt").exists()
            )
            self.assertTrue((out_dir / "README.md").exists())

    @unittest.skipUnless(
        os.environ.get("EPL_RUN_DESKTOP_BUILD_TESTS") == "1",
        "Set EPL_RUN_DESKTOP_BUILD_TESTS=1 to run desktop Gradle validation.",
    )
    def test_reference_desktop_gradle_build(self):
        if shutil.which("java") is None:
            self.skipTest("A JDK is required for desktop build validation.")

        source = APPS_DIR / "reference-desktop" / "src" / "main.epl"
        program = _parse_program(source)

        with _gradle_tempdir("epl_ref_desktop_build_") as tmpdir:
            tmp_path = Path(tmpdir)
            out_dir = tmp_path / "desktop_app"
            generate_desktop_project(
                program,
                str(out_dir),
                app_name="ReferenceDesktop",
                package="com.epl.reference.desktop",
                width=1024,
                height=768,
            )

            env = os.environ.copy()
            env["GRADLE_USER_HOME"] = str(_shared_gradle_user_home("desktop"))

            _run_command(
                _gradle_command(out_dir) + ["compileKotlin", "test", "--stacktrace", "--no-daemon"],
                cwd=out_dir,
                env=env,
                timeout=1800.0,
            )

            self.assertTrue((out_dir / "build" / "classes" / "kotlin" / "main").exists())

    def test_reference_package_validate_pack_and_install(self):
        package_dir = PACKAGES_DIR / "reference-hello-lib"
        validation = validate_package(str(package_dir))
        self.assertTrue(validation["valid"], validation)

        with tempfile.TemporaryDirectory(prefix="epl_ref_pkg_") as tmpdir:
            archive = pack_package(str(package_dir), output_dir=tmpdir)
            self.assertIsNotNone(archive)
            self.assertTrue(Path(archive).exists())
            self.assertTrue(Path(archive + ".sha256").exists())

        install_ok = install_package(str(package_dir), save=False)
        self.assertTrue(install_ok)

        installed_manifest = load_manifest(Path.home() / ".epl" / "packages" / "reference-hello-lib")
        self.assertEqual(installed_manifest["name"], "reference-hello-lib")
