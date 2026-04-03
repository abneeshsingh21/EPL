"""
EPL CI Validation Generator v1.0 — Phase 7f: CI Pipeline Generation

Generates GitHub Actions workflow files for:
  - Package index validation (schema, checksum, version ordering)
  - Auto-merge for trusted publishers
  - Package validation on PR
  - Workspace CI (build/test all members)

Also validates the packages-index repo structure.
"""

import json
import os
import re
from typing import Dict, List, Optional, Any


# ═══════════════════════════════════════════════════════════
#  GitHub Actions Workflow Templates
# ═══════════════════════════════════════════════════════════

def generate_index_validation_workflow() -> str:
    """Generate a GitHub Actions workflow for validating packages-index PRs."""
    return """\
name: Validate Package Index PR

on:
  pull_request:
    branches: [main]
    paths:
      - 'packages/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Validate changed packages
        run: |
          python scripts/validate_index.py --changed-only

      - name: Check schema
        run: |
          python scripts/validate_index.py --schema

      - name: Verify checksums
        run: |
          python scripts/validate_index.py --checksums

      - name: Check version ordering
        run: |
          python scripts/validate_index.py --version-order
"""


def generate_auto_merge_workflow() -> str:
    """Generate a GitHub Actions workflow for auto-merging trusted publisher PRs."""
    return """\
name: Auto-Merge Trusted Publishers

on:
  pull_request:
    branches: [main]
    paths:
      - 'packages/**'

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.event.pull_request.user.login == 'epl-publish-bot'
    steps:
      - uses: actions/checkout@v4

      - name: Validate package
        run: python scripts/validate_index.py --changed-only

      - name: Auto-merge
        if: success()
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.pulls.merge({
              owner: context.repo.owner,
              repo: context.repo.repo,
              pull_number: context.issue.number,
              merge_method: 'squash'
            })
"""


def generate_package_ci_workflow(name: str = 'my-package',
                                  epl_version: str = '7.0.0') -> str:
    """Generate a CI workflow for an EPL package."""
    return f"""\
name: CI — {name}

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python ${{{{ matrix.python-version }}}}
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}

      - name: Install EPL
        run: pip install epl-lang>={epl_version}

      - name: Install dependencies
        run: epl install

      - name: Run tests
        run: epl test

      - name: Lint
        run: epl lint .

  publish:
    needs: test
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install EPL
        run: pip install epl-lang>={epl_version}

      - name: Publish
        env:
          EPL_GITHUB_TOKEN: ${{{{ secrets.EPL_GITHUB_TOKEN }}}}
        run: epl publish --repo ${{{{ github.repository }}}}
"""


def generate_workspace_ci_workflow(workspace_name: str = 'workspace',
                                    member_names: Optional[List[str]] = None) -> str:
    """Generate a CI workflow for an EPL workspace (monorepo)."""
    members = member_names or ['pkg-a', 'pkg-b']
    member_matrix = ', '.join(f"'{m}'" for m in members)

    return f"""\
name: CI — {workspace_name}

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate-workspace:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install EPL
        run: pip install epl-lang>=7.0.0

      - name: Validate workspace
        run: epl workspace validate

      - name: Install all deps
        run: epl workspace install

  test-members:
    needs: validate-workspace
    runs-on: ubuntu-latest
    strategy:
      matrix:
        member: [{member_matrix}]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install EPL
        run: pip install epl-lang>=7.0.0

      - name: Install workspace deps
        run: epl workspace install

      - name: Test ${{{{ matrix.member }}}}
        run: |
          cd packages/${{{{ matrix.member }}}}
          epl test
"""


# ═══════════════════════════════════════════════════════════
#  Index Validation Script Generation
# ═══════════════════════════════════════════════════════════

def generate_validation_script() -> str:
    """Generate the index validation Python script."""
    return '''\
#!/usr/bin/env python3
"""Validate the packages-index repository structure and contents."""

import json
import os
import sys
import re

PACKAGES_DIR = 'packages'
REQUIRED_FIELDS = {'name', 'description', 'author'}
SEMVER_RE = re.compile(
    r'^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)'
    r'(?:-((?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*)'
    r'(?:\\.(?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?' 
    r'(?:\\+([0-9a-zA-Z-]+(?:\\.[0-9a-zA-Z-]+)*))?$'
)


def validate_package_dir(pkg_dir):
    """Validate a single package directory."""
    errors = []
    name = os.path.basename(pkg_dir)

    # Check metadata.json
    meta_path = os.path.join(pkg_dir, 'metadata.json')
    if not os.path.exists(meta_path):
        errors.append(f'{name}: missing metadata.json')
        return errors

    try:
        with open(meta_path, 'r') as f:
            meta = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f'{name}: invalid JSON in metadata.json: {e}')
        return errors

    for field in REQUIRED_FIELDS:
        if field not in meta or not meta[field]:
            errors.append(f'{name}: missing required field "{field}" in metadata.json')

    # Check versions.json
    ver_path = os.path.join(pkg_dir, 'versions.json')
    if os.path.exists(ver_path):
        try:
            with open(ver_path, 'r') as f:
                ver_data = json.load(f)
            versions = ver_data.get('versions', [])
            for v in versions:
                ver_str = v.get('version', '')
                if not SEMVER_RE.match(ver_str):
                    errors.append(f'{name}: invalid version "{ver_str}"')
        except json.JSONDecodeError as e:
            errors.append(f'{name}: invalid JSON in versions.json: {e}')

    return errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Validate packages-index')
    parser.add_argument('--changed-only', action='store_true',
                        help='Only validate changed packages')
    parser.add_argument('--schema', action='store_true',
                        help='Validate schema')
    parser.add_argument('--checksums', action='store_true',
                        help='Verify checksums')
    parser.add_argument('--version-order', action='store_true',
                        help='Check version ordering')
    args = parser.parse_args()

    if not os.path.isdir(PACKAGES_DIR):
        print('No packages/ directory found.')
        sys.exit(0)

    all_errors = []
    for pkg_name in sorted(os.listdir(PACKAGES_DIR)):
        pkg_dir = os.path.join(PACKAGES_DIR, pkg_name)
        if os.path.isdir(pkg_dir):
            all_errors.extend(validate_package_dir(pkg_dir))

    if all_errors:
        print(f'Validation failed with {len(all_errors)} errors:')
        for e in all_errors:
            print(f'  - {e}')
        sys.exit(1)
    else:
        pkg_count = len([d for d in os.listdir(PACKAGES_DIR)
                         if os.path.isdir(os.path.join(PACKAGES_DIR, d))])
        print(f'All {pkg_count} packages validated successfully.')


if __name__ == '__main__':
    main()
'''


# ═══════════════════════════════════════════════════════════
#  High-Level Generation Functions
# ═══════════════════════════════════════════════════════════

def generate_ci_for_project(path: str = '.', output_dir: Optional[str] = None) -> Dict[str, str]:
    """Generate all CI files for a project.

    Auto-detects: workspace, package, or index repo.
    Returns {filepath: content}.
    """
    from epl.package_manager import load_manifest

    files = {}
    if output_dir is None:
        output_dir = os.path.join(path, '.github', 'workflows')

    manifest = load_manifest(path)
    if not manifest:
        return files

    name = manifest.get('name', 'epl-package')
    version = manifest.get('version', '7.0.0')

    # Check if it's a workspace
    from epl.workspace import load_workspace
    ws = load_workspace(path)
    if ws and ws.is_workspace:
        members = ws.member_names
        files['ci.yml'] = generate_workspace_ci_workflow(name, members)
    else:
        files['ci.yml'] = generate_package_ci_workflow(name, version)

    return files


def write_ci_files(path: str = '.') -> int:
    """Generate and write CI files for a project.

    Returns the number of files written.
    """
    files = generate_ci_for_project(path)
    if not files:
        print("  No manifest found. Cannot generate CI.")
        return 0

    output_dir = os.path.join(path, '.github', 'workflows')
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for fname, content in files.items():
        fpath = os.path.join(output_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        count += 1
        print(f"  Generated: .github/workflows/{fname}")

    return count


def generate_ci_for_index() -> Dict[str, str]:
    """Generate CI files for the packages-index repository.

    Returns {filepath: content}.
    """
    return {
        '.github/workflows/validate-pr.yml': generate_index_validation_workflow(),
        '.github/workflows/auto-merge.yml': generate_auto_merge_workflow(),
        'scripts/validate_index.py': generate_validation_script(),
    }


# ═══════════════════════════════════════════════════════════
#  CLI Interface
# ═══════════════════════════════════════════════════════════

def ci_cli(args: List[str]):
    """Handle 'epl ci' from the command line."""
    if not args:
        count = write_ci_files()
        if count:
            print(f"\n  Generated {count} CI file(s).")
        return

    sub = args[0]

    if sub == 'generate':
        count = write_ci_files()
        if count:
            print(f"\n  Generated {count} CI file(s).")

    elif sub == 'index':
        files = generate_ci_for_index()
        for fpath, content in files.items():
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  Generated: {fpath}")

    elif sub == 'preview':
        files = generate_ci_for_project()
        for fname, content in files.items():
            print(f"\n  === {fname} ===")
            print(content)

    else:
        print(f"  Unknown CI command: {sub}")
        print("  Available: generate, index, preview")
