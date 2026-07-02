"""WebView native shells (v10.0.0).

The transliterating native targets (`epl android|ios|desktop`) can only carry
pure EPL *logic* across to Kotlin/Swift — they cannot reproduce an EPL **web
app**, whose UI is built from `Page`/`Raw HTML`/`Script`/`Stylesheet` and whose
data lives behind an HTTP + SQLite backend. That is why a real app's UI vanished
in the omniapp stress test (finding H2).

The WebView target ships the **real** web app instead of transliterating it:

  * **android** / **ios** — a thin native shell (Android `WebView` /
    iOS `WKWebView`) that loads the running EPL web server. Point it at a
    deployed URL with ``--url``; the default targets the local dev server so you
    can ``epl run app.epl`` on your machine and see the actual app on a device
    or emulator.
  * **desktop** — a Python launcher that starts the EPL web app and opens it in
    a native `pywebview` window. Because EPL itself is Python, this runs the
    **entire** app — UI *and* backend — with zero transliteration.

No EPL construct is dropped here: the UI, routes, `Raw HTML`, `Script`,
`Stylesheet`, and the `db_*` backend are exactly what you built for the web.
"""

from __future__ import annotations

import os
import re
import shutil

from epl import ast_nodes as ast
from epl.kotlin_gen import ANDROID_TEMPLATE_ROOT

# Loopback address the Android emulator uses to reach the host machine's
# localhost (a real "127.0.0.1" inside the emulator is the emulator itself).
ANDROID_EMULATOR_HOST = '10.0.2.2'
DEFAULT_PORT = 5000


def detect_port(program, default: int = DEFAULT_PORT) -> int:
    """Return the port the program's `Start ... on port N` declares, else default."""
    found = []

    def visit(node):
        if isinstance(node, ast.StartServer):
            port = getattr(node, 'port', None)
            value = getattr(port, 'value', port)
            if isinstance(value, bool):
                return
            if isinstance(value, int):
                found.append(value)
            elif isinstance(value, str) and value.isdigit():
                found.append(int(value))

    _walk(program, visit)
    return found[0] if found else default


def _walk(node, visit):
    if isinstance(node, ast.ASTNode):
        visit(node)
        for value in vars(node).values():
            _walk(value, visit)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _walk(item, visit)
    elif isinstance(node, dict):
        for item in node.values():
            _walk(item, visit)


def _slug(name: str) -> str:
    """A lowercase identifier safe for a Java/Kotlin package segment."""
    s = re.sub(r'[^a-z0-9]+', '', (name or 'app').lower())
    return s or 'app'


def _swift_name(name: str) -> str:
    """A PascalCase identifier safe as a Swift type prefix."""
    parts = re.split(r'[^A-Za-z0-9]+', name or 'App')
    s = ''.join(p[:1].upper() + p[1:] for p in parts if p)
    if not s or not s[0].isalpha():
        s = 'App' + s
    return s


def _fill(template: str, mapping: dict) -> str:
    """Replace __TOKEN__ sentinels. Sentinels (not str.format) are used so the
    Kotlin/Swift/Gradle `$` and `{}` in templates need no escaping."""
    out = template
    for key, val in mapping.items():
        out = out.replace(key, str(val))
    return out


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


# --------------------------------------------------------------------------- #
# Android WebView shell
# --------------------------------------------------------------------------- #

_ANDROID_MANIFEST = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.Material.Light.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

_ANDROID_ACTIVITY = """\
package __PKG__

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback

/**
 * WebView shell for __APPNAME__.
 *
 * Loads the EPL web app running at __URL__. Run the backend with
 * `epl run app.epl` on the host machine; the emulator reaches it via 10.0.2.2.
 */
class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
        }
        webView.webViewClient = WebViewClient()
        setContentView(webView)
        webView.loadUrl("__URL__")

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }
}
"""

_ANDROID_APP_GRADLE = """\
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "__PKG__"
    compileSdk = 34

    defaultConfig {
        applicationId = "__PKG__"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.0")
}
"""

_ANDROID_ROOT_GRADLE = """\
plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}
"""

_ANDROID_SETTINGS_GRADLE = """\
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "__APPNAME__"
include(":app")
"""

_ANDROID_GRADLE_PROPS = """\
org.gradle.jvmargs=-Xmx2048m
android.useAndroidX=true
kotlin.code.style=official
"""

_GRADLE_WRAPPER_PROPS = """\
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""


def generate_android_webview(program, output_dir, app_name, url=None, package_name=None):
    """Generate an Android WebView shell project that loads the EPL web app."""
    pkg = package_name or f'com.epl.{_slug(app_name)}'
    target_url = url or f'http://{ANDROID_EMULATOR_HOST}:{detect_port(program)}'
    mapping = {
        '__PKG__': pkg,
        '__APPNAME__': app_name,
        '__URL__': target_url,
    }
    pkg_path = pkg.replace('.', '/')

    _write(
        os.path.join(output_dir, 'settings.gradle.kts'), _fill(_ANDROID_SETTINGS_GRADLE, mapping)
    )
    _write(os.path.join(output_dir, 'build.gradle.kts'), _ANDROID_ROOT_GRADLE)
    _write(os.path.join(output_dir, 'gradle.properties'), _ANDROID_GRADLE_PROPS)
    _write(os.path.join(output_dir, 'app', 'build.gradle.kts'), _fill(_ANDROID_APP_GRADLE, mapping))
    _write(
        os.path.join(output_dir, 'app', 'src', 'main', 'AndroidManifest.xml'),
        _ANDROID_MANIFEST,
    )
    _write(
        os.path.join(output_dir, 'app', 'src', 'main', 'java', pkg_path, 'MainActivity.kt'),
        _fill(_ANDROID_ACTIVITY, mapping),
    )
    _write(
        os.path.join(output_dir, 'app', 'src', 'main', 'res', 'values', 'strings.xml'),
        f'<resources>\n    <string name="app_name">{app_name}</string>\n</resources>\n',
    )

    # Gradle wrapper — reuse the shipped assets so `./gradlew` works out of the box.
    _write(
        os.path.join(output_dir, 'gradle', 'wrapper', 'gradle-wrapper.properties'),
        _GRADLE_WRAPPER_PROPS,
    )
    _copy_android_wrapper(output_dir)

    _write(
        os.path.join(output_dir, 'README.md'),
        _android_readme(app_name, target_url, url is not None),
    )
    return target_url


def _copy_android_wrapper(output_dir):
    """Copy gradlew / gradlew.bat / gradle-wrapper.jar from the shipped template."""
    assets = [
        ('gradlew', 'gradlew'),
        ('gradlew.bat', 'gradlew.bat'),
        (
            'gradle/wrapper/gradle-wrapper.jar',
            os.path.join('gradle', 'wrapper', 'gradle-wrapper.jar'),
        ),
    ]
    for source_rel, dest_rel in assets:
        source = ANDROID_TEMPLATE_ROOT / source_rel
        if not source.exists():
            continue
        dest = os.path.join(output_dir, dest_rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(source, dest)
    gradlew = os.path.join(output_dir, 'gradlew')
    if os.path.isfile(gradlew) and os.name != 'nt':
        os.chmod(gradlew, 0o755)


def _android_readme(app_name, url, custom_url):
    backend = (
        'This shell loads your deployed app at the URL above.'
        if custom_url
        else (
            'This shell loads your **local** EPL web server. The emulator reaches '
            'your host machine at `10.0.2.2`, so:\n\n'
            '1. Start the backend on your machine: `epl run app.epl`\n'
            '2. Run this shell on an **emulator** (a physical device cannot see '
            '`10.0.2.2` — rebuild with `--url http://<your-ip>:PORT` for that).'
        )
    )
    return (
        f'# {app_name} — Android WebView shell\n\n'
        f'Loads the real EPL web app (UI + backend, nothing dropped) in a native '
        f'`WebView` pointed at:\n\n    {url}\n\n'
        f'{backend}\n\n'
        '## Build\n\n'
        '```bash\n'
        './gradlew assembleDebug      # APK at app/build/outputs/apk/debug/\n'
        '```\n\n'
        'Or open this folder in Android Studio.\n'
    )


# --------------------------------------------------------------------------- #
# iOS WebView shell
# --------------------------------------------------------------------------- #

_IOS_APP = """\
import SwiftUI

@main
struct __NAME__App: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
"""

_IOS_CONTENT = """\
import SwiftUI
import WebKit

/// A SwiftUI wrapper around WKWebView that loads the EPL web app.
struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

struct ContentView: View {
    // The running EPL web server. Use a LAN IP or deployed host for a device.
    private let appURL = URL(string: "__URL__")!

    var body: some View {
        WebView(url: appURL)
            .ignoresSafeArea()
    }
}
"""

_IOS_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>__APPNAME__</string>
    <key>CFBundleIdentifier</key>
    <string>__BUNDLE__</string>
    <key>CFBundleName</key>
    <string>__NAME__</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
    <key>UILaunchScreen</key>
    <dict/>
</dict>
</plist>
"""


def generate_ios_webview(program, output_dir, app_name, url=None, bundle_id='com.epl.app'):
    """Generate iOS WKWebView SwiftUI sources that load the EPL web app."""
    name = _swift_name(app_name)
    target_url = url or f'http://localhost:{detect_port(program)}'
    mapping = {
        '__NAME__': name,
        '__APPNAME__': app_name,
        '__BUNDLE__': bundle_id,
        '__URL__': target_url,
    }
    src = os.path.join(output_dir, name)
    _write(os.path.join(src, f'{name}App.swift'), _fill(_IOS_APP, mapping))
    _write(os.path.join(src, 'ContentView.swift'), _fill(_IOS_CONTENT, mapping))
    _write(os.path.join(src, 'Info.plist'), _fill(_IOS_PLIST, mapping))
    _write(
        os.path.join(output_dir, 'README.md'),
        f'# {app_name} — iOS WebView shell\n\n'
        f'A SwiftUI app whose single screen is a `WKWebView` loading the real EPL '
        f'web app at:\n\n    {target_url}\n\n'
        '## Run\n\n'
        '1. In Xcode, create a new **iOS App** (SwiftUI lifecycle) named '
        f'`{name}`.\n'
        f'2. Replace the generated files with `{name}/{name}App.swift`, '
        f'`{name}/ContentView.swift`, and `{name}/Info.plist` from this folder.\n'
        '3. Start the backend (`epl run app.epl`) and run on the Simulator. For a '
        'physical device, rebuild with `--url http://<your-ip>:PORT`.\n',
    )
    return target_url


# --------------------------------------------------------------------------- #
# Desktop WebView shell (runs the REAL app — Python launcher + pywebview)
# --------------------------------------------------------------------------- #

_DESKTOP_LAUNCHER = '''\
"""Desktop shell for __APPNAME__ — runs the real EPL web app in a native window.

Because EPL is Python, this launches the actual web server (UI + backend, nothing
transliterated) and shows it in a `pywebview` window — no browser, no port to
remember.
"""
import os
import subprocess
import sys
import time
import urllib.request

import webview

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app.epl")
URL = "http://127.0.0.1:__PORT__"


def _serve():
    """Start the EPL web app as a child process."""
    return subprocess.Popen([sys.executable, "-m", "epl", "run", APP], cwd=HERE)


def _wait_for_server(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    server = _serve()
    try:
        if not _wait_for_server(URL):
            print("EPL web server did not start within 30s.", file=sys.stderr)
            return 1
        webview.create_window("__APPNAME__", URL, width=__WIDTH__, height=__HEIGHT__)
        webview.start()
        return 0
    finally:
        server.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _bundle_local_imports(source_path, output_dir):
    """Copy `source_path`'s transitive local `.epl` imports into `output_dir`.

    Files are placed at their path relative to the entry file's directory, which
    is where the launcher runs `app.epl` from — so an `Import "utils/api"` in the
    entry resolves to `<output>/utils/api.epl`, exactly as it did in the source
    tree. Imports that live outside the entry's directory are flattened to their
    basename to avoid escaping the output project. Uses the shared
    DependencyScanner (which now resolves imports source-file-relative).
    """
    try:
        from epl.packager import DependencyScanner
    except Exception:
        return []

    src_abs = os.path.abspath(source_path)
    src_dir = os.path.dirname(src_abs)
    copied = []
    for dep in DependencyScanner(source_path).scan():
        dep_abs = os.path.abspath(dep)
        if dep_abs == src_abs:
            continue  # the entry file is already copied as app.epl
        rel = os.path.relpath(dep_abs, src_dir)
        if rel.startswith('..'):
            rel = os.path.basename(dep_abs)
        dest = os.path.join(output_dir, rel)
        dest_dir = os.path.dirname(dest)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        shutil.copyfile(dep_abs, dest)
        copied.append(rel)
    return copied


def generate_desktop_webview(
    program, output_dir, app_name, source_path=None, url=None, width=1100, height=800
):
    """Generate a Python/pywebview desktop launcher that runs the real EPL app."""
    port = detect_port(program)
    mapping = {
        '__APPNAME__': app_name,
        '__PORT__': port,
        '__WIDTH__': width,
        '__HEIGHT__': height,
    }
    os.makedirs(output_dir, exist_ok=True)
    _write(os.path.join(output_dir, 'main.py'), _fill(_DESKTOP_LAUNCHER, mapping))

    # Bundle the EPL source so the launcher is self-contained. The entry file
    # becomes app.epl; its transitive local Imports are copied alongside it,
    # preserving their paths relative to the entry so source-file-relative
    # `Import` statements still resolve when the launcher runs `epl run app.epl`.
    # Without this, the subprocess dies on its first local import and the shell
    # only reports a generic "server did not start" timeout.
    if source_path and os.path.isfile(source_path):
        shutil.copyfile(source_path, os.path.join(output_dir, 'app.epl'))
        _bundle_local_imports(source_path, output_dir)

    _write(
        os.path.join(output_dir, 'requirements.txt'),
        'pywebview>=4.0\neplang>=10.0.0\n',
    )
    _write(
        os.path.join(output_dir, 'README.md'),
        f'# {app_name} — desktop app\n\n'
        'Runs the **complete** EPL web app (UI *and* backend) in a native window '
        'via `pywebview`. Nothing is transliterated or dropped.\n\n'
        '## Run\n\n'
        '```bash\n'
        'pip install -r requirements.txt\n'
        'python main.py\n'
        '```\n\n'
        f'The launcher starts `epl run app.epl` (serving on port {port}) and opens '
        'it in a desktop window.\n',
    )
    return f'http://127.0.0.1:{port}'
