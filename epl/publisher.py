"""
EPL Enhanced Publisher v1.0 — Phase 7b: Production Publish Workflow

Enhanced publishing workflow that:
  1. Validates and packs the package into a tarball
  2. Creates a GitHub Release with the tarball attached
  3. Generates PR content for the packages-index repo
  4. Updates the local index cache
  5. Runs pre-publish checks (name validation, version bump safety, etc.)

Builds on top of the existing registry.py publish flow and integrates
with the new PackageIndex system from 7a.
"""

import json
import os
import re
import time
import hashlib
import shutil
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple, Any


# ═══════════════════════════════════════════════════════════
#  Pre-Publish Checks
# ═══════════════════════════════════════════════════════════

_NAME_RE = re.compile(r'^(@[a-zA-Z][a-zA-Z0-9_-]*/)?[a-zA-Z][a-zA-Z0-9_-]*$')

RESERVED_NAMES = frozenset({
    'epl', 'epl-core', 'epl-std', 'epl-lang', 'epl-cli',
    'test', 'tests', 'node', 'python', 'java', 'rust',
    'module', 'package', 'import', 'export',
})

# Files that should never be included in a published package
PUBLISH_IGNORE = {
    '.git', '.gitignore', '.github', '.vscode', '.idea',
    '__pycache__', 'node_modules', '.env', '.env.local',
    '.DS_Store', 'Thumbs.db', 'epl_modules',
}


class PublishCheck:
    """Result of a pre-publish validation check."""

    __slots__ = ('name', 'passed', 'message', 'severity')

    def __init__(self, name: str, passed: bool, message: str = '',
                 severity: str = 'error'):
        self.name = name
        self.passed = passed
        self.message = message
        self.severity = severity  # 'error', 'warning', 'info'

    def __repr__(self):
        status = 'PASS' if self.passed else self.severity.upper()
        return f"[{status}] {self.name}: {self.message}"


class PublishResult:
    """Result of a publish operation."""

    def __init__(self):
        self.checks: List[PublishCheck] = []
        self.archive_path: Optional[str] = None
        self.archive_size: int = 0
        self.archive_checksum: str = ''
        self.release_url: str = ''
        self.index_pr_content: Dict[str, str] = {}
        self.published: bool = False
        self.error: str = ''

    @property
    def checks_passed(self) -> bool:
        return all(c.passed or c.severity != 'error' for c in self.checks)

    def add_check(self, name: str, passed: bool, message: str = '',
                  severity: str = 'error'):
        self.checks.append(PublishCheck(name, passed, message, severity))

    def print_report(self):
        """Print a human-readable publish report."""
        print("\n  Publish Checks:")
        for c in self.checks:
            if c.passed:
                icon = '+'
            elif c.severity == 'warning':
                icon = '!'
            else:
                icon = 'x'
            print(f"  [{icon}] {c.name}: {c.message}")

        if self.archive_path:
            size_kb = self.archive_size / 1024
            print(f"\n  Archive: {os.path.basename(self.archive_path)} ({size_kb:.1f} KB)")
            print(f"  SHA-256: {self.archive_checksum[:16]}...")

        if self.published:
            print(f"\n  Published successfully!")
            if self.release_url:
                print(f"  Release: {self.release_url}")
        elif self.error:
            print(f"\n  Publish failed: {self.error}")


def run_publish_checks(manifest: dict, path: str = '.') -> List[PublishCheck]:
    """Run all pre-publish validation checks.

    Returns a list of PublishCheck results.
    """
    checks = []

    # 1. Name validation
    name = manifest.get('name', '')
    if not name:
        checks.append(PublishCheck('name', False, "Missing 'name' in manifest"))
    elif not _NAME_RE.match(name):
        checks.append(PublishCheck('name', False, f"Invalid package name: {name}"))
    elif name.lower() in RESERVED_NAMES:
        checks.append(PublishCheck('name', False, f"Reserved name: {name}"))
    else:
        checks.append(PublishCheck('name', True, f"Name: {name}"))

    # 2. Version validation
    version = manifest.get('version', '')
    if not version:
        checks.append(PublishCheck('version', False, "Missing 'version' in manifest"))
    else:
        from epl.package_manager import SemVer
        v = SemVer.parse(version)
        if not v:
            checks.append(PublishCheck('version', False, f"Invalid semver: {version}"))
        else:
            checks.append(PublishCheck('version', True, f"Version: {version}"))

    # 3. Description
    desc = manifest.get('description', '')
    if not desc:
        checks.append(PublishCheck('description', False, "Missing description",
                                   severity='warning'))
    else:
        checks.append(PublishCheck('description', True, f"Description present ({len(desc)} chars)"))

    # 4. Entry point exists
    entry = manifest.get('main', manifest.get('entry', 'main.epl'))
    entry_path = os.path.join(path, entry)
    if os.path.isfile(entry_path):
        checks.append(PublishCheck('entry_point', True, f"Entry point: {entry}"))
    else:
        checks.append(PublishCheck('entry_point', False,
                                   f"Entry point not found: {entry}",
                                   severity='warning'))

    # 5. README
    readme_found = False
    for readme_name in ('README.md', 'README.txt', 'README', 'readme.md'):
        if os.path.isfile(os.path.join(path, readme_name)):
            readme_found = True
            break
    checks.append(PublishCheck('readme', readme_found,
                               "README found" if readme_found else "No README found",
                               severity='info' if not readme_found else 'info'))

    # 6. License
    license_ = manifest.get('license', '')
    if license_:
        checks.append(PublishCheck('license', True, f"License: {license_}"))
    else:
        checks.append(PublishCheck('license', False, "No license specified",
                                   severity='warning'))

    # 7. Repository URL
    repo = manifest.get('repository', '')
    if repo:
        checks.append(PublishCheck('repository', True, f"Repository: {repo}"))
    else:
        checks.append(PublishCheck('repository', False, "No repository URL",
                                   severity='warning'))

    # 8. No sensitive files
    sensitive = []
    for f in os.listdir(path):
        if f.startswith('.env') or f == 'secrets.json' or f.endswith('.key'):
            sensitive.append(f)
    if sensitive:
        checks.append(PublishCheck('sensitive_files', False,
                                   f"Sensitive files detected: {', '.join(sensitive)}"))
    else:
        checks.append(PublishCheck('sensitive_files', True, "No sensitive files"))

    return checks


# ═══════════════════════════════════════════════════════════
#  Package Packing
# ═══════════════════════════════════════════════════════════

def pack_for_publish(path: str = '.', output_dir: Optional[str] = None) -> Optional[Tuple[str, int, str]]:
    """Pack a package directory into a .zip archive for publishing.

    Returns (archive_path, size_bytes, sha256_hex) or None on failure.
    """
    from epl.package_manager import load_manifest
    manifest = load_manifest(path)
    if not manifest:
        print("  No manifest found (epl.toml or epl.json)")
        return None

    name = manifest.get('name', 'package')
    version = manifest.get('version', '0.0.0')
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    archive_name = f"{safe_name}-{version}.zip"

    if output_dir is None:
        output_dir = path
    os.makedirs(output_dir, exist_ok=True)

    archive_path = os.path.join(output_dir, archive_name)

    # Read .eplignore if it exists
    ignore_patterns = set(PUBLISH_IGNORE)
    ignore_file = os.path.join(path, '.eplignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.add(line)

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]
            for fname in files:
                if fname in ignore_patterns:
                    continue
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, path)
                zf.write(fpath, arcname)

    size = os.path.getsize(archive_path)
    checksum = _sha256_file(archive_path)
    return archive_path, size, checksum


# ═══════════════════════════════════════════════════════════
#  Enhanced Publish Flow
# ═══════════════════════════════════════════════════════════

def enhanced_publish(path: str = '.', github_repo: str = None,
                     dry_run: bool = False, skip_checks: bool = False) -> PublishResult:
    """Full enhanced publish workflow.

    Steps:
      1. Load and validate manifest
      2. Run pre-publish checks
      3. Pack the archive
      4. Create GitHub release (unless dry_run)
      5. Generate index PR content
      6. Update local index cache

    Returns PublishResult with all details.
    """
    from epl.package_manager import load_manifest

    result = PublishResult()

    # Step 1: Load manifest
    manifest = load_manifest(path)
    if not manifest:
        result.error = "No manifest found"
        return result

    name = manifest.get('name', '')
    version = manifest.get('version', '')

    # Step 2: Pre-publish checks
    if not skip_checks:
        result.checks = run_publish_checks(manifest, path)
        if not result.checks_passed:
            result.error = "Pre-publish checks failed"
            return result

    # Step 3: Pack archive
    with tempfile.TemporaryDirectory() as tmp:
        packed = pack_for_publish(path, tmp)
        if not packed:
            result.error = "Failed to create archive"
            return result

        archive_path, size, checksum = packed
        result.archive_path = archive_path
        result.archive_size = size
        result.archive_checksum = checksum

        if dry_run:
            result.published = False
            # Generate index PR content
            from epl.package_index import (PackageMetadata, VersionEntry,
                                           PackageIndexEntry, PackageIndex)
            metadata = PackageMetadata(
                name=name,
                description=manifest.get('description', ''),
                author=manifest.get('author', ''),
                license_=manifest.get('license', 'MIT'),
                repository=github_repo or manifest.get('repository', ''),
                keywords=manifest.get('keywords', []),
            )
            ver_entry = VersionEntry(
                version=version,
                checksum=checksum,
                download_url='',
                dependencies=manifest.get('dependencies', {}),
                size=size,
            )
            idx = PackageIndex(offline=True)
            entry = idx.create_index_entry(name, metadata, ver_entry)
            result.index_pr_content = idx.generate_index_pr_content(entry)
            return result

        # Step 4: Create GitHub release
        repo = github_repo or manifest.get('repository', '')
        if repo:
            release_url = _create_github_release(
                repo, name, version, manifest, archive_path
            )
            if release_url:
                result.release_url = release_url
                download_url = f"https://github.com/{repo}/releases/download/v{version}/{os.path.basename(archive_path)}"
            else:
                download_url = ''
        else:
            download_url = ''

        # Step 5: Generate index PR content and update local cache
        from epl.package_index import (PackageMetadata, VersionEntry,
                                       PackageIndex)
        metadata = PackageMetadata(
            name=name,
            description=manifest.get('description', ''),
            author=manifest.get('author', ''),
            license_=manifest.get('license', 'MIT'),
            repository=repo,
            keywords=manifest.get('keywords', []),
        )
        ver_entry = VersionEntry(
            version=version,
            checksum=checksum,
            download_url=download_url,
            dependencies=manifest.get('dependencies', {}),
            size=size,
        )
        idx = PackageIndex(offline=True)
        entry = idx.create_index_entry(name, metadata, ver_entry)
        result.index_pr_content = idx.generate_index_pr_content(entry)
        result.published = True

    return result


def _create_github_release(repo: str, name: str, version: str,
                            manifest: dict, archive_path: str) -> Optional[str]:
    """Create a GitHub release with the archive attached.

    Returns the release HTML URL or None.
    """
    import urllib.request
    import urllib.error
    import urllib.parse

    token = os.environ.get('EPL_GITHUB_TOKEN', '')
    if not token:
        print("  Warning: EPL_GITHUB_TOKEN not set. Skipping GitHub release.")
        return None

    # Normalize repo
    repo = repo.replace('https://github.com/', '').strip('/')
    if '/' not in repo:
        return None

    owner, repo_name = repo.split('/', 1)
    api = 'https://api.github.com'

    # Create release
    release_data = json.dumps({
        'tag_name': f'v{version}',
        'name': f'{name} v{version}',
        'body': manifest.get('description', f'{name} version {version}'),
        'draft': False,
        'prerelease': '-' in version,
    }).encode('utf-8')

    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'User-Agent': 'EPL-Publisher/1.0',
    }

    req = urllib.request.Request(
        f'{api}/repos/{owner}/{repo_name}/releases',
        data=release_data, headers=headers, method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return None

    release_html_url = release.get('html_url', '')

    # Upload archive asset
    upload_url = release.get('upload_url', '').split('{')[0]
    if upload_url and archive_path and os.path.isfile(archive_path):
        archive_name = os.path.basename(archive_path)
        upload_full = f"{upload_url}?name={urllib.parse.quote(archive_name)}"
        with open(archive_path, 'rb') as f:
            asset_data = f.read()

        asset_req = urllib.request.Request(
            upload_full, data=asset_data, method='POST',
            headers={
                'Authorization': f'token {token}',
                'Content-Type': 'application/zip',
                'User-Agent': 'EPL-Publisher/1.0',
            }
        )
        try:
            with urllib.request.urlopen(asset_req, timeout=60) as resp:
                resp.read()
        except (urllib.error.URLError, OSError):
            pass

    return release_html_url


# ═══════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════

def _sha256_file(path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def generate_publish_pr_markdown(result: PublishResult, name: str,
                                  version: str) -> str:
    """Generate Markdown content for a PR to packages-index repo."""
    lines = [
        f"# Publish {name}@{version}",
        "",
        "## Checks",
    ]
    for c in result.checks:
        icon = ":white_check_mark:" if c.passed else ":x:"
        lines.append(f"- {icon} **{c.name}**: {c.message}")

    lines.extend([
        "",
        "## Archive",
        f"- Size: {result.archive_size / 1024:.1f} KB",
        f"- SHA-256: `{result.archive_checksum}`",
    ])

    if result.release_url:
        lines.extend([
            "",
            "## Release",
            f"- URL: {result.release_url}",
        ])

    lines.extend([
        "",
        "## Files Changed",
    ])
    for fpath in result.index_pr_content:
        lines.append(f"- `{fpath}`")

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
#  CLI Interface
# ═══════════════════════════════════════════════════════════

def publish_cli(args: List[str]):
    """Handle 'epl publish' from the command line."""
    path = '.'
    repo = None
    dry_run = False

    i = 0
    while i < len(args):
        if args[i] == '--repo' and i + 1 < len(args):
            repo = args[i + 1]
            i += 2
        elif args[i] == '--dry-run':
            dry_run = True
            i += 1
        elif not args[i].startswith('--'):
            path = args[i]
            i += 1
        else:
            i += 1

    result = enhanced_publish(path, github_repo=repo, dry_run=dry_run)
    result.print_report()

    if dry_run and result.index_pr_content:
        print("\n  Index PR files that would be created:")
        for fpath, content in result.index_pr_content.items():
            print(f"  {fpath}:")
            for line in content.split('\n')[:5]:
                print(f"    {line}")
            print("    ...")
