"""
EPL Cross-Platform Packager (v1.0)
Bundles EPL programs into standalone distributable executables.

Supports:
  - PyInstaller-based packaging (EPL interpreter + source bundled)
  - LLVM native compilation (for supported programs)
  - Single-file and directory bundles
  - Windows (.exe), Linux (ELF), macOS (Mach-O)
  - Icon, metadata, and version info embedding
  - Dependency auto-detection and bundling
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
import platform
import struct
import zipfile
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any


# ═══════════════════════════════════════════════════════════
#  Build Configuration
# ═══════════════════════════════════════════════════════════

class BuildConfig:
    """Configuration for building a distributable package."""

    def __init__(self, source_file: str, **kwargs):
        self.source_file = os.path.abspath(source_file)
        self.output_name = kwargs.get('name', Path(source_file).stem)
        self.output_dir = kwargs.get('output_dir', os.path.join(os.getcwd(), 'dist'))
        self.icon = kwargs.get('icon', None)
        self.version = kwargs.get('version', '1.0.0')
        self.author = kwargs.get('author', '')
        self.description = kwargs.get('description', '')
        self.one_file = kwargs.get('one_file', True)
        self.console = kwargs.get('console', True)
        self.hidden_imports = kwargs.get('hidden_imports', [])
        self.extra_data = kwargs.get('extra_data', [])
        self.extra_files = kwargs.get('extra_files', [])
        self.target_platform = kwargs.get('target', platform.system().lower())
        self.optimize = kwargs.get('optimize', True)
        self.strip = kwargs.get('strip', True)
        self.upx = kwargs.get('upx', False)
        self.clean = kwargs.get('clean', True)
        self.debug = kwargs.get('debug', False)
        self.mode = kwargs.get('mode', 'interpreter')  # 'interpreter' or 'native'

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    @classmethod
    def from_dict(cls, d: dict) -> 'BuildConfig':
        src = d.pop('source_file', '')
        return cls(src, **d)

    @classmethod
    def from_epl_project(cls, project_dir: str = '.') -> 'BuildConfig':
        """Load config from an EPL project manifest (epl.toml preferred, epl.json legacy)."""
        from epl.package_manager import (
            load_manifest,
            get_manifest_format,
            TOML_MANIFEST_NAME,
            MANIFEST_NAME,
            _parse_toml,
        )

        manifest = load_manifest(project_dir)
        if not manifest:
            raise FileNotFoundError(f"No epl.toml or epl.json found in {project_dir}")

        build_cfg = {}
        manifest_format = get_manifest_format(project_dir)
        if manifest_format == 'toml':
            proj_file = os.path.join(project_dir, TOML_MANIFEST_NAME)
            with open(proj_file, 'r', encoding='utf-8') as f:
                raw_manifest = _parse_toml(f.read())
            build_cfg = raw_manifest.get('build', {})
        elif manifest_format == 'json':
            proj_file = os.path.join(project_dir, MANIFEST_NAME)
            with open(proj_file, 'r', encoding='utf-8') as f:
                raw_manifest = json.load(f)
            build_cfg = raw_manifest.get('build', {})

        main_file = manifest.get('entry') or manifest.get('main') or 'main.epl'
        src = os.path.join(project_dir, main_file)
        return cls(src,
                   name=manifest.get('name', Path(src).stem),
                   version=manifest.get('version', '1.0.0'),
                   author=manifest.get('author', ''),
                   description=manifest.get('description', ''),
                   **build_cfg)


# ═══════════════════════════════════════════════════════════
#  Dependency Scanner
# ═══════════════════════════════════════════════════════════

class DependencyScanner:
    """Scans EPL source for import/use dependencies."""

    def __init__(self, source_file: str):
        self.source_file = os.path.abspath(source_file)
        self.base_dir = os.path.dirname(self.source_file)
        self.scanned = set()
        self.dependencies = []
        self.epl_packages = []

    def scan(self) -> List[str]:
        """Scan the source and all imported files recursively."""
        self._scan_file(self.source_file)
        return self.dependencies

    def _scan_file(self, filepath: str):
        filepath = os.path.abspath(filepath)
        if filepath in self.scanned:
            return
        self.scanned.add(filepath)

        if not os.path.exists(filepath):
            return

        self.dependencies.append(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        import re
        # Match: import "file.epl"
        for m in re.finditer(r'import\s+"([^"]+)"', source):
            dep_path = os.path.join(self.base_dir, m.group(1))
            if not dep_path.endswith('.epl'):
                dep_path += '.epl'
            self._scan_file(dep_path)

        # Match: use package_name
        for m in re.finditer(r'use\s+(\w+)', source):
            pkg = m.group(1)
            if pkg not in self.epl_packages:
                self.epl_packages.append(pkg)
                # Look for package in epl_packages/
                pkg_dir = os.path.join(self.base_dir, 'epl_packages', pkg)
                if os.path.isdir(pkg_dir):
                    for f in os.listdir(pkg_dir):
                        if f.endswith('.epl'):
                            self._scan_file(os.path.join(pkg_dir, f))


# ═══════════════════════════════════════════════════════════
#  Launcher Script Generator
# ═══════════════════════════════════════════════════════════

def _generate_launcher_script(config: BuildConfig, epl_files: List[str]) -> str:
    """Generate a Python launcher that embeds the EPL interpreter and runs the program."""
    # Read all EPL source files
    sources = {}
    for f in epl_files:
        rel = os.path.relpath(f, os.path.dirname(config.source_file))
        with open(f, 'r', encoding='utf-8') as fh:
            sources[rel] = fh.read()

    main_rel = os.path.basename(config.source_file)

    launcher = f'''#!/usr/bin/env python3
"""EPL Packaged Application: {config.output_name} v{config.version}"""
import sys
import os

# Add the bundled EPL runtime to path
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    _base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
else:
    _base = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, 'epl_runtime'))

# Embedded EPL source
_EPL_SOURCES = {json.dumps(sources, indent=2)}

_MAIN_FILE = {json.dumps(main_rel)}

def main():
    try:
        from epl.lexer import Lexer
        from epl.parser import Parser
        from epl.interpreter import Interpreter
    except ImportError:
        print("Error: EPL runtime not found. Package may be corrupted.", file=sys.stderr)
        sys.exit(1)

    source = _EPL_SOURCES.get(_MAIN_FILE)
    if source is None:
        print(f"Error: Main file {{_MAIN_FILE}} not found in package.", file=sys.stderr)
        sys.exit(1)

    interpreter = Interpreter()
    try:
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        interpreter.execute(program)
    except Exception as e:
        print(f"Error: {{e}}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
'''
    return launcher


# ═══════════════════════════════════════════════════════════
#  PyInstaller Packager
# ═══════════════════════════════════════════════════════════

class PyInstallerPackager:
    """Package EPL programs using PyInstaller."""

    def __init__(self, config: BuildConfig):
        self.config = config
        self.temp_dir = None

    def _check_pyinstaller(self) -> bool:
        """Check if PyInstaller is installed."""
        try:
            import PyInstaller  # type: ignore[reportMissingModuleSource]
            return True
        except ImportError:
            return False

    def _install_pyinstaller(self) -> bool:
        """Attempt to install PyInstaller."""
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'pyinstaller'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def build(self) -> Optional[str]:
        """Build the distributable package. Returns path to output."""
        if not os.path.exists(self.config.source_file):
            print(f"Error: Source file not found: {self.config.source_file}")
            return None

        # Check/install PyInstaller
        if not self._check_pyinstaller():
            print("PyInstaller not found. Installing...")
            if not self._install_pyinstaller():
                print("Error: Failed to install PyInstaller. Install manually: pip install pyinstaller")
                return None

        # Scan dependencies
        scanner = DependencyScanner(self.config.source_file)
        epl_files = scanner.scan()
        print(f"  Found {len(epl_files)} EPL file(s)")
        if scanner.epl_packages:
            print(f"  Packages: {', '.join(scanner.epl_packages)}")

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix='epl_build_')

        try:
            # Generate launcher
            launcher_code = _generate_launcher_script(self.config, epl_files)
            launcher_path = os.path.join(self.temp_dir, f'{self.config.output_name}_launcher.py')
            with open(launcher_path, 'w', encoding='utf-8') as f:
                f.write(launcher_code)

            # Copy EPL runtime
            epl_runtime_dir = os.path.join(self.temp_dir, 'epl_runtime', 'epl')
            os.makedirs(epl_runtime_dir, exist_ok=True)

            epl_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
            for py_file in os.listdir(epl_src_dir):
                if py_file.endswith('.py'):
                    shutil.copy2(
                        os.path.join(epl_src_dir, py_file),
                        os.path.join(epl_runtime_dir, py_file)
                    )

            # Build PyInstaller command
            cmd = [
                sys.executable, '-m', 'PyInstaller',
                '--noconfirm',
                '--name', self.config.output_name,
                '--distpath', self.config.output_dir,
                '--workpath', os.path.join(self.temp_dir, 'build'),
                '--specpath', self.temp_dir,
                '--add-data', f'{os.path.join(self.temp_dir, "epl_runtime")}{os.pathsep}epl_runtime',
            ]

            if self.config.one_file:
                cmd.append('--onefile')
            else:
                cmd.append('--onedir')

            if not self.config.console:
                cmd.append('--windowed')

            if self.config.icon and os.path.exists(self.config.icon):
                cmd.extend(['--icon', self.config.icon])

            if self.config.strip:
                cmd.append('--strip')

            if self.config.upx:
                cmd.append('--upx-dir=upx')

            for hi in self.config.hidden_imports:
                cmd.extend(['--hidden-import', hi])

            for df in self.config.extra_data:
                cmd.extend(['--add-data', df])

            for ef in self.config.extra_files:
                cmd.extend(['--add-binary', ef])

            # Add version info on Windows
            if platform.system() == 'Windows' and self.config.version:
                vi_path = self._create_version_info()
                if vi_path:
                    cmd.extend(['--version-file', vi_path])

            cmd.append(launcher_path)

            # Run PyInstaller
            print(f"  Building {self.config.output_name}...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.temp_dir
            )

            if result.returncode != 0:
                print(f"Build failed:\n{result.stderr}")
                if self.config.debug:
                    print(f"STDOUT:\n{result.stdout}")
                return None

            # Determine output path
            if self.config.one_file:
                ext = '.exe' if platform.system() == 'Windows' else ''
                output = os.path.join(self.config.output_dir, f'{self.config.output_name}{ext}')
            else:
                output = os.path.join(self.config.output_dir, self.config.output_name)

            if os.path.exists(output):
                size = os.path.getsize(output) if os.path.isfile(output) else _dir_size(output)
                print(f"  Built: {output} ({_human_size(size)})")
                return output
            else:
                print("Build completed but output not found.")
                return None

        finally:
            if self.config.clean and self.temp_dir:
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_version_info(self) -> Optional[str]:
        """Create Windows version info file."""
        parts = self.config.version.split('.')
        while len(parts) < 4:
            parts.append('0')

        vi_content = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({','.join(parts[:4])}),
    prodvers=({','.join(parts[:4])}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(u'040904B0', [
        StringStruct(u'CompanyName', u'{self.config.author}'),
        StringStruct(u'FileDescription', u'{self.config.description or self.config.output_name}'),
        StringStruct(u'FileVersion', u'{self.config.version}'),
        StringStruct(u'InternalName', u'{self.config.output_name}'),
        StringStruct(u'OriginalFilename', u'{self.config.output_name}.exe'),
        StringStruct(u'ProductName', u'{self.config.output_name}'),
        StringStruct(u'ProductVersion', u'{self.config.version}'),
      ])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
        vi_path = os.path.join(self.temp_dir, 'version_info.txt')
        with open(vi_path, 'w', encoding='utf-8') as f:
            f.write(vi_content)
        return vi_path


# ═══════════════════════════════════════════════════════════
#  Standalone Zip Packager (no external deps)
# ═══════════════════════════════════════════════════════════

class ZipPackager:
    """Create a portable zip bundle with Python launcher."""

    def __init__(self, config: BuildConfig):
        self.config = config

    def build(self) -> Optional[str]:
        """Build a zip package with embedded EPL source and runtime."""
        if not os.path.exists(self.config.source_file):
            print(f"Error: Source file not found: {self.config.source_file}")
            return None

        os.makedirs(self.config.output_dir, exist_ok=True)

        scanner = DependencyScanner(self.config.source_file)
        epl_files = scanner.scan()

        zip_path = os.path.join(self.config.output_dir, f'{self.config.output_name}.zip')

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add launcher
            launcher = _generate_launcher_script(self.config, epl_files)
            zf.writestr(f'{self.config.output_name}/run.py', launcher)

            # Add EPL runtime
            epl_src_dir = os.path.dirname(os.path.abspath(__file__))
            for py_file in os.listdir(epl_src_dir):
                if py_file.endswith('.py'):
                    src_path = os.path.join(epl_src_dir, py_file)
                    zf.write(src_path, f'{self.config.output_name}/epl_runtime/epl/{py_file}')

            # Add batch/shell scripts
            if platform.system() == 'Windows':
                bat = f'@echo off\npython "%~dp0run.py" %*\n'
                zf.writestr(f'{self.config.output_name}/run.bat', bat)
            else:
                sh = f'#!/bin/sh\npython3 "$(dirname "$0")/run.py" "$@"\n'
                zf.writestr(f'{self.config.output_name}/run.sh', sh)

            # Add README
            readme = f"""# {self.config.output_name} v{self.config.version}

{self.config.description}

## Running

Requires Python 3.8+.

### Windows
    run.bat

### Linux/macOS
    chmod +x run.sh
    ./run.sh

Or directly:
    python run.py
"""
            zf.writestr(f'{self.config.output_name}/README.md', readme)

            # Add extra files
            for ef in self.config.extra_files:
                if os.path.exists(ef):
                    zf.write(ef, f'{self.config.output_name}/{os.path.basename(ef)}')

        size = os.path.getsize(zip_path)
        print(f"  Built: {zip_path} ({_human_size(size)})")
        return zip_path


# ═══════════════════════════════════════════════════════════
#  Native LLVM Packager
# ═══════════════════════════════════════════════════════════

class NativePackager:
    """Compile EPL to native executable via LLVM."""

    def __init__(self, config: BuildConfig):
        self.config = config

    def build(self) -> Optional[str]:
        """Compile EPL source to native binary."""
        if not os.path.exists(self.config.source_file):
            print(f"Error: Source file not found: {self.config.source_file}")
            return None

        try:
            from epl.compiler import Compiler, HAS_LLVM
            if not HAS_LLVM:
                print("Error: llvmlite required for native compilation.")
                print("  Install: pip install llvmlite")
                return None
        except ImportError:
            print("Error: LLVM compiler not available.")
            return None

        with open(self.config.source_file, 'r', encoding='utf-8') as f:
            source = f.read()

        from epl.lexer import Lexer
        from epl.parser import Parser

        try:
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()
        except Exception as e:
            print(f"Parse error: {e}")
            return None

        compiler = Compiler()
        try:
            compiler.compile(program)
        except Exception as e:
            print(f"Compilation error: {e}")
            print("  Note: Not all EPL features are supported in native compilation.")
            print("  Use interpreter mode (--mode interpreter) for full feature support.")
            return None

        os.makedirs(self.config.output_dir, exist_ok=True)

        ext = '.exe' if platform.system() == 'Windows' else ''
        output = os.path.join(self.config.output_dir, f'{self.config.output_name}{ext}')

        try:
            obj_path = compiler.emit_object(output.replace(ext, '.o'))
            if not obj_path or not os.path.exists(obj_path):
                print("Error: Failed to emit object file.")
                return None

            # Link with system linker
            runtime_c = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runtime.c')
            runtime_o = os.path.join(self.config.output_dir, 'runtime.o')

            # Compile runtime.c
            cc = _find_c_compiler()
            if not cc:
                print("Error: No C compiler found. Install gcc, clang, or MSVC.")
                return None

            # Compile runtime.c to runtime.o
            cc_cmd = [cc, '-c', '-O2', runtime_c, '-o', runtime_o]
            result = subprocess.run(cc_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error compiling runtime.c: {result.stderr}")
                return None

            # Link everything
            link_cmd = [cc, obj_path, runtime_o, '-o', output, '-lm']
            if self.config.strip and platform.system() != 'Windows':
                link_cmd.append('-s')
            if self.config.optimize:
                link_cmd.append('-O2')

            result = subprocess.run(link_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Link error: {result.stderr}")
                return None

            # Cleanup object files
            if self.config.clean:
                for f in [obj_path, runtime_o]:
                    if os.path.exists(f):
                        os.remove(f)

            if os.path.exists(output):
                size = os.path.getsize(output)
                print(f"  Built native: {output} ({_human_size(size)})")
                return output

        except Exception as e:
            print(f"Native build failed: {e}")
            print("  Falling back to interpreter mode.")
            return None

        return None


# ═══════════════════════════════════════════════════════════
#  Installer Generator
# ═══════════════════════════════════════════════════════════

class InstallerGenerator:
    """Generate platform-specific installers."""

    def __init__(self, config: BuildConfig):
        self.config = config

    def generate_nsis(self, exe_path: str) -> Optional[str]:
        """Generate NSIS installer script for Windows."""
        nsis_script = f'''
!define APPNAME "{self.config.output_name}"
!define VERSION "{self.config.version}"
!define DESCRIPTION "{self.config.description}"

Name "${{APPNAME}} ${{VERSION}}"
OutFile "{self.config.output_name}_setup.exe"
InstallDir "$PROGRAMFILES\\${{APPNAME}}"

Section "Install"
    SetOutPath $INSTDIR
    File "{exe_path}"
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    
    ; Start menu
    CreateDirectory "$SMPROGRAMS\\${{APPNAME}}"
    CreateShortCut "$SMPROGRAMS\\${{APPNAME}}\\${{APPNAME}}.lnk" "$INSTDIR\\{os.path.basename(exe_path)}"
    CreateShortCut "$SMPROGRAMS\\${{APPNAME}}\\Uninstall.lnk" "$INSTDIR\\uninstall.exe"
    
    ; Registry
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "DisplayName" "${{APPNAME}}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "UninstallString" "$INSTDIR\\uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "DisplayVersion" "${{VERSION}}"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\{os.path.basename(exe_path)}"
    Delete "$INSTDIR\\uninstall.exe"
    RMDir "$INSTDIR"
    Delete "$SMPROGRAMS\\${{APPNAME}}\\*.*"
    RMDir "$SMPROGRAMS\\${{APPNAME}}"
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}"
SectionEnd
'''
        script_path = os.path.join(self.config.output_dir, f'{self.config.output_name}.nsi')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(nsis_script)
        print(f"  NSIS script: {script_path}")
        return script_path

    def generate_desktop_entry(self, exe_path: str) -> Optional[str]:
        """Generate a .desktop file for Linux."""
        desktop = f"""[Desktop Entry]
Type=Application
Name={self.config.output_name}
Comment={self.config.description}
Exec={exe_path}
Terminal={'true' if self.config.console else 'false'}
Categories=Application;
Version={self.config.version}
"""
        desktop_path = os.path.join(self.config.output_dir, f'{self.config.output_name}.desktop')
        with open(desktop_path, 'w', encoding='utf-8') as f:
            f.write(desktop)
        print(f"  Desktop entry: {desktop_path}")
        return desktop_path


# ═══════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════

def _find_c_compiler() -> Optional[str]:
    """Find an available C compiler."""
    candidates = ['gcc', 'clang', 'cc']
    if platform.system() == 'Windows':
        candidates = ['gcc', 'clang', 'cl']

    for cc in candidates:
        if shutil.which(cc):
            return cc
    return None


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _dir_size(path: str) -> int:
    """Get total size of directory."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


# ═══════════════════════════════════════════════════════════
#  High-Level API
# ═══════════════════════════════════════════════════════════

def package(source_file: str, **kwargs) -> Optional[str]:
    """
    Package an EPL program into a distributable format.

    Args:
        source_file: Path to the main .epl file
        mode: 'exe' (PyInstaller), 'zip' (portable), 'native' (LLVM)
        name: Output name (default: source filename)
        output_dir: Output directory (default: ./dist)
        one_file: Single executable (default: True)
        console: Console app (default: True)
        icon: Path to icon file
        version: Version string
        author: Author name
        description: App description

    Returns:
        Path to built package, or None on failure
    """
    mode = kwargs.pop('mode', 'exe')
    config = BuildConfig(source_file, **kwargs)

    print(f"\n  EPL Packager v1.0")
    print(f"  ─────────────────────────────────────────")
    print(f"  Source:   {config.source_file}")
    print(f"  Name:     {config.output_name}")
    print(f"  Version:  {config.version}")
    print(f"  Mode:     {mode}")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print()

    if mode == 'exe':
        packager = PyInstallerPackager(config)
        result = packager.build()
    elif mode == 'zip':
        packager = ZipPackager(config)
        result = packager.build()
    elif mode == 'native':
        packager = NativePackager(config)
        result = packager.build()
    else:
        print(f"  Unknown mode: {mode}. Use 'exe', 'zip', or 'native'.")
        return None

    if result:
        print(f"\n  ✓ Package built successfully!")
        print(f"  Output: {result}")

        # Generate installer scripts on request
        if kwargs.get('installer', False):
            ig = InstallerGenerator(config)
            if platform.system() == 'Windows':
                ig.generate_nsis(result)
            else:
                ig.generate_desktop_entry(result)

    return result


def package_project(project_dir: str = '.', mode: str = 'exe') -> Optional[str]:
    """Package an EPL project from its manifest config."""
    try:
        config = BuildConfig.from_epl_project(project_dir)
    except FileNotFoundError:
        print("Error: No epl.toml or epl.json found. Run 'epl init' first or specify a source file.")
        return None
    config.mode = mode
    return package(config.source_file, mode=mode, **{
        k: v for k, v in config.to_dict().items()
        if k not in ('source_file', 'mode', 'target_platform')
    })
