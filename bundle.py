"""
EPL Bundle Script — package the EPL CLI itself as a standalone executable.

Usage:
    python bundle.py                Build dist/epl/epl.exe
    python bundle.py --onefile      Build single-file dist/epl.exe
    python bundle.py --install      Build and add to PATH
    python bundle.py --clean        Remove build artifacts
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


_HIDDEN_IMPORTS = [
    "epl",
    "epl.lexer",
    "epl.parser",
    "epl.interpreter",
    "epl.environment",
    "epl.errors",
    "epl.ast_nodes",
    "epl.tokens",
    "epl.stdlib",
    "main",
]

_DATA_SPECS = [
    (os.path.join("epl", "stdlib"), os.path.join("epl", "stdlib")),
    (os.path.join("epl", "registry.json"), "epl"),
    (os.path.join("epl", "runtime.c"), "epl"),
    (os.path.join("epl", "models", "Modelfile"), os.path.join("epl", "models")),
]


def check_pyinstaller():
    try:
        import PyInstaller  # type: ignore[reportMissingModuleSource]
        return True
    except ImportError:
        return False


def install_pyinstaller():
    print("[EPL Bundle] Installing PyInstaller...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("[EPL Bundle] PyInstaller installed.")


def clean():
    for directory in ("build", "dist", "__pycache__"):
        if os.path.isdir(directory):
            shutil.rmtree(directory)
            print(f"[EPL Bundle] Removed {directory}/")
    print("[EPL Bundle] Clean complete.")


def _iter_data_specs():
    for source, destination in _DATA_SPECS:
        if os.path.exists(source):
            yield source, destination


def build(onefile=False):
    if not check_pyinstaller():
        install_pyinstaller()

    print("[EPL Bundle] Building EPL executable...")

    if onefile:
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--name",
            "epl",
            "--console",
        ]
        for source, destination in _iter_data_specs():
            cmd.extend(["--add-data", f"{source}{os.pathsep}{destination}"])
        for module in _HIDDEN_IMPORTS:
            cmd.extend(["--hidden-import", module])
        cmd.append("epl/cli.py")
    else:
        cmd = [sys.executable, "-m", "PyInstaller", "epl.spec"]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("[EPL Bundle] Build FAILED.")
        return False

    if onefile:
        exe_path = os.path.join("dist", "epl.exe" if sys.platform == "win32" else "epl")
    else:
        exe_path = os.path.join("dist", "epl", "epl.exe" if sys.platform == "win32" else "epl")

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n[EPL Bundle] SUCCESS: {exe_path} ({size_mb:.1f} MB)")
        print(f"[EPL Bundle] Run with: {exe_path} --version")
        return True

    print("[EPL Bundle] Build completed but executable not found.")
    return False


def add_to_path():
    """Add the bundled EPL CLI to the current user's PATH on Windows."""
    if sys.platform != "win32":
        print("[EPL Bundle] PATH installation is Windows-only. Copy to /usr/local/bin on Unix.")
        return

    dist_dir = os.path.abspath(os.path.join("dist", "epl"))
    if not os.path.isdir(dist_dir):
        print("[EPL Bundle] Build first: python bundle.py")
        return

    import ctypes
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""

        if dist_dir in current_path:
            print(f"[EPL Bundle] Already in PATH: {dist_dir}")
            return

        new_path = current_path + ";" + dist_dir if current_path else dist_dir
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        print(f"[EPL Bundle] Added to PATH: {dist_dir}")
        print("[EPL Bundle] Restart your terminal for changes to take effect.")
    finally:
        winreg.CloseKey(key)

    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    ctypes.windll.user32.SendMessageW(hwnd_broadcast, wm_settingchange, 0, "Environment")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if "--clean" in sys.argv:
        clean()
    elif "--install" in sys.argv:
        if build(onefile="--onefile" in sys.argv):
            add_to_path()
    else:
        build(onefile="--onefile" in sys.argv)
