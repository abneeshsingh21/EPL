# -*- mode: python ; coding: utf-8 -*-
"""
EPL PyInstaller Spec — Build standalone `epl` executable.

Usage:
    pip install pyinstaller
    pyinstaller epl.spec

Output: dist/epl/epl.exe (Windows) or dist/epl/epl (Linux/macOS)
"""

import os
import glob

block_cipher = None

# Collect all EPL stdlib .epl files
stdlib_data = []
stdlib_dir = os.path.join('epl', 'stdlib')
if os.path.isdir(stdlib_dir):
    for epl_file in glob.glob(os.path.join(stdlib_dir, '*.epl')):
        stdlib_data.append((epl_file, 'epl/stdlib'))
    registry_file = os.path.join(stdlib_dir, 'registry.json')
    if os.path.exists(registry_file):
        stdlib_data.append((registry_file, 'epl/stdlib'))

# Collect runtime assets required by packaged installs
runtime_data = []
for source, destination in [
    (os.path.join('epl', 'registry.json'), 'epl'),
    (os.path.join('epl', 'runtime.c'), 'epl'),
    (os.path.join('epl', 'models', 'Modelfile'), os.path.join('epl', 'models')),
    (os.path.join('epl', 'templates', 'android', 'gradlew'), os.path.join('epl', 'templates', 'android')),
    (os.path.join('epl', 'templates', 'android', 'gradlew.bat'), os.path.join('epl', 'templates', 'android')),
    (
        os.path.join('epl', 'templates', 'android', 'gradle', 'wrapper', 'gradle-wrapper.jar'),
        os.path.join('epl', 'templates', 'android', 'gradle', 'wrapper'),
    ),
]:
    if os.path.exists(source):
        runtime_data.append((source, destination))

official_package_data = []
official_dir = os.path.join('epl', 'official_packages')
if os.path.isdir(official_dir):
    for root, _, files in os.walk(official_dir):
        for filename in files:
            source = os.path.join(root, filename)
            destination = root.replace('\\', '/')
            official_package_data.append((source, destination))

# Collect example files (optional, for distribution)
example_data = []
if os.path.isdir('examples'):
    for epl_file in glob.glob(os.path.join('examples', '*.epl')):
        example_data.append((epl_file, 'examples'))

# Collect docs (optional)
doc_data = []
if os.path.isdir('docs'):
    for md_file in glob.glob(os.path.join('docs', '*.md')):
        doc_data.append((md_file, 'docs'))

a = Analysis(
    ['epl/cli.py'],
    pathex=['.'],
    binaries=[],
    datas=stdlib_data + runtime_data + official_package_data + example_data + doc_data,
    hiddenimports=[
        'epl',
        'epl.lexer',
        'epl.parser',
        'epl.interpreter',
        'epl.environment',
        'epl.errors',
        'epl.ast_nodes',
        'epl.tokens',
        'epl.stdlib',
        'epl.compiler',
        'epl.html_gen',
        'epl.web',
        'main',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'cv2',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='epl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,  # Set to 'epl.ico' if icon file exists
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='epl',
)
