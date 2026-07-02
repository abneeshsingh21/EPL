"""Tests for the WebView native-shell generators (v10.0.0).

The WebView target ships the *real* EPL web app — Android `WebView` / iOS
`WKWebView` shells that load the running web server, and a desktop pywebview
launcher that runs the whole app (UI + backend) with zero transliteration. Tests
assert the generated project files carry the right wiring; native compilation is
out of scope here (same as the other codegen suites).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.webview_gen import (
    ANDROID_EMULATOR_HOST,
    detect_port,
    generate_android_webview,
    generate_desktop_webview,
    generate_ios_webview,
)


def parse(source):
    return Parser(Lexer(source).tokenize()).parse()


WEB_APP = """\
Create WebApp called app

Route "/" shows
    Page "Home"
        Heading "Hello"
    End
End

Start app on port 4321
"""

NO_PORT_APP = 'Display "hi"\n'


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# Port detection
# --------------------------------------------------------------------------- #


def test_detect_port_reads_start_server():
    assert detect_port(parse(WEB_APP)) == 4321


def test_detect_port_defaults_when_absent():
    assert detect_port(parse(NO_PORT_APP), default=5000) == 5000


# --------------------------------------------------------------------------- #
# Android
# --------------------------------------------------------------------------- #


def test_android_webview_project_files(tmp_path):
    out = str(tmp_path / 'app_android')
    url = generate_android_webview(parse(WEB_APP), out, 'My App')

    # Default URL targets the emulator-to-host loopback on the detected port.
    assert url == f'http://{ANDROID_EMULATOR_HOST}:4321'

    manifest = _read(os.path.join(out, 'app', 'src', 'main', 'AndroidManifest.xml'))
    assert 'android.permission.INTERNET' in manifest
    assert 'usesCleartextTraffic="true"' in manifest

    activity = _read(
        os.path.join(out, 'app', 'src', 'main', 'java', 'com', 'epl', 'myapp', 'MainActivity.kt')
    )
    assert 'WebView' in activity
    assert 'javaScriptEnabled = true' in activity
    assert f'loadUrl("{url}")' in activity

    # The gradle wrapper jar must be present so ./gradlew works out of the box.
    assert os.path.isfile(os.path.join(out, 'gradle', 'wrapper', 'gradle-wrapper.jar'))
    assert os.path.isfile(os.path.join(out, 'gradlew'))


def test_android_webview_custom_url_and_package(tmp_path):
    out = str(tmp_path / 'a')
    url = generate_android_webview(
        parse(WEB_APP), out, 'My App', url='https://prod.example.com', package_name='com.acme.x'
    )
    assert url == 'https://prod.example.com'
    activity = _read(
        os.path.join(out, 'app', 'src', 'main', 'java', 'com', 'acme', 'x', 'MainActivity.kt')
    )
    assert 'package com.acme.x' in activity
    assert 'loadUrl("https://prod.example.com")' in activity


# --------------------------------------------------------------------------- #
# iOS
# --------------------------------------------------------------------------- #


def test_ios_webview_sources(tmp_path):
    out = str(tmp_path / 'app_ios')
    url = generate_ios_webview(parse(WEB_APP), out, 'My App', bundle_id='com.acme.app')
    assert url == 'http://localhost:4321'

    content = _read(os.path.join(out, 'MyApp', 'ContentView.swift'))
    assert 'WKWebView' in content
    assert url in content

    app = _read(os.path.join(out, 'MyApp', 'MyAppApp.swift'))
    assert '@main' in app
    assert 'struct MyAppApp: App' in app

    plist = _read(os.path.join(out, 'MyApp', 'Info.plist'))
    assert 'com.acme.app' in plist
    assert 'NSAllowsLocalNetworking' in plist


# --------------------------------------------------------------------------- #
# Desktop
# --------------------------------------------------------------------------- #


def test_desktop_webview_launcher(tmp_path):
    src = tmp_path / 'app.epl'
    src.write_text(WEB_APP, encoding='utf-8')
    out = str(tmp_path / 'app_desktop')
    url = generate_desktop_webview(
        parse(WEB_APP), out, 'My App', source_path=str(src), width=1000, height=720
    )
    assert url == 'http://127.0.0.1:4321'

    launcher = _read(os.path.join(out, 'main.py'))
    assert 'import webview' in launcher
    assert 'http://127.0.0.1:4321' in launcher
    assert '"-m", "epl", "run"' in launcher
    assert 'width=1000' in launcher and 'height=720' in launcher

    # The launcher must be valid Python.
    compile(launcher, 'main.py', 'exec')

    # The EPL source is bundled so the launcher is self-contained.
    assert os.path.isfile(os.path.join(out, 'app.epl'))

    reqs = _read(os.path.join(out, 'requirements.txt'))
    assert 'pywebview' in reqs
    assert 'eplang' in reqs


# --------------------------------------------------------------------------- #
# Desktop — bundling the entry file's local imports (the "nothing dropped" path)
# --------------------------------------------------------------------------- #


def test_desktop_webview_bundles_local_imports(tmp_path):
    """The whole value of --webview is running the *real, complete* app. If the
    entry file imports other project files, they must be copied too — else the
    subprocess dies on its first `Import` before the port ever binds."""
    (tmp_path / 'utils').mkdir()
    (tmp_path / 'utils' / 'api.epl').write_text(
        'Function ping\n    Return "pong"\nEnd\n', encoding='utf-8'
    )
    entry_src = 'Import "utils/api"\n' + WEB_APP
    src = tmp_path / 'main.epl'
    src.write_text(entry_src, encoding='utf-8')

    out = str(tmp_path / 'app_desktop')
    generate_desktop_webview(parse(entry_src), out, 'My App', source_path=str(src))

    assert os.path.isfile(os.path.join(out, 'app.epl'))
    # The imported file is copied at the same relative path the entry references.
    assert os.path.isfile(os.path.join(out, 'utils', 'api.epl'))


def test_desktop_webview_bundles_nested_imports(tmp_path):
    """Imports are source-file-relative, so an imported module that imports a
    sibling must also be bundled (this is what the old copy-only-entry missed)."""
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    (pkg / 'helpers.epl').write_text('Function h\n    Return 1\nEnd\n', encoding='utf-8')
    (pkg / 'api.epl').write_text(
        'Import "helpers"\nFunction a\n    Return h()\nEnd\n', encoding='utf-8'
    )
    entry_src = 'Import "pkg/api"\n' + WEB_APP
    src = tmp_path / 'main.epl'
    src.write_text(entry_src, encoding='utf-8')

    out = str(tmp_path / 'd')
    generate_desktop_webview(parse(entry_src), out, 'My App', source_path=str(src))

    assert os.path.isfile(os.path.join(out, 'pkg', 'api.epl'))
    assert os.path.isfile(os.path.join(out, 'pkg', 'helpers.epl'))  # sibling, two deep
