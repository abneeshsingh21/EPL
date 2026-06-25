# Android Development with EPL

EPL can generate full Android Studio projects from your EPL code via Kotlin transpilation.

## Quick Start

```bash
# Generate Android project
epl android myapp.epl

# Generate and build APK
epl android myapp.epl --build

# Custom app name
epl android myapp.epl --name "My App" --build
```

## How It Works

1. EPL parses your `.epl` file
2. Transpiles to Kotlin using `kotlin_gen.py`
3. Generates a full Gradle project with:
   - `build.gradle.kts` (app + project level)
   - `AndroidManifest.xml`
   - `MainActivity.kt`
   - Jetpack Compose UI code
   - Gradle wrapper

## Example: Simple Android App

```epl
Note: A simple counter app
count = 0

Function increment
    count = count + 1
    Say "Count: " + to_string(count)
End

Function decrement
    count = count - 1
    Say "Count: " + to_string(count)
End
```

```bash
epl android counter.epl --name "Counter App" --build
```

## Build Requirements

To build APKs from the CLI, you need:

- **Android SDK** — Install via [Android Studio](https://developer.android.com/studio)
- **Java JDK 17+** — Install via `winget install Microsoft.OpenJDK.17`
- **Set ANDROID_HOME** — EPL auto-detects common paths:
  - Windows: `%LOCALAPPDATA%\Android\Sdk`
  - macOS: `~/Library/Android/sdk`
  - Linux: `~/Android/Sdk`

## CLI Options

| Flag | Description |
| ---- | ----------- |
| `--build` | Build APK after generating project |
| `--name NAME` | Set the app display name |
| `--compose` | Use Jetpack Compose UI (default) |
| `--strict` | Fail the build (exit code `2`) if any construct could not be ported |
| `--webview` | Ship the **real** web app in a native WebView shell (nothing dropped) |
| `--url URL` | With `--webview`, the URL the shell loads (default: local dev server) |

## What gets ported (and what doesn't)

The native targets (`android`, `ios`, `desktop`) **transliterate EPL logic** to
Kotlin/Swift. EPL web apps, however, rely on things that have no native-widget
equivalent: HTTP routing (`Route`, `WebApp`, `Start ... on port`), a server-side
backend, and the web escape hatches `Raw HTML` / `Script` / `Stylesheet`. Those
cannot be turned into native widgets.

Rather than drop them silently, every native build now:

- prints a summary of unportable constructs, and
- writes a **`PORTING_REPORT.md`** into the output directory listing each one
  (with its line number and why it was dropped) plus what *did* port.

Use `--strict` in CI to turn any unportable construct into a build failure:

```bash
epl android myapp.epl --strict   # exit 2 if anything couldn't be ported
```

Pure-logic EPL (functions, math, data) ports cleanly with an empty report.

## Shipping a real web app: `--webview`

For an app whose UI is a web UI (Page DSL, `Raw HTML`, `Script`, `Stylesheet`)
backed by routes and a database, transliteration is the wrong tool — use the
**WebView target**, which ships the real app with nothing dropped:

```bash
# Native shell that loads your running EPL web server (emulator → host):
epl android myapp.epl --webview

# Point it at a deployed backend instead:
epl android myapp.epl --webview --url https://myapp.example.com
```

The Android shell is a `WebView`; the iOS shell (`epl ios … --webview`) is a
`WKWebView`; and the desktop shell (`epl desktop … --webview`) is a Python
`pywebview` launcher that runs the **whole** app — UI *and* backend — in a native
window with zero transliteration. For the local default, run the backend with
`epl run myapp.epl`; the emulator reaches your machine at `10.0.2.2`.

## Project Structure

```text
myapp_android/
├── app/
│   ├── src/main/
│   │   ├── java/com/epl/myapp/
│   │   │   └── MainActivity.kt
│   │   ├── res/
│   │   │   ├── values/
│   │   │   └── layout/
│   │   └── AndroidManifest.xml
│   └── build.gradle.kts
├── build.gradle.kts
├── settings.gradle.kts
├── gradle/wrapper/
├── gradlew
└── gradlew.bat
```

## Kotlin Transpilation

You can also just transpile to Kotlin without generating a full project:

```bash
epl kotlin myapp.epl    # Generates myapp.kt
```
