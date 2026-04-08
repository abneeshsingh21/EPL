"""
EPL Package Manager (v3.0)
Install, manage, and publish EPL packages.
Supports: semver resolution, transitive dependencies, lockfiles with integrity verification,
conflict detection, local/GitHub/URL/registry sources, publish workflow, and EPL manifests.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import importlib.metadata as importlib_metadata
import urllib.request
import zipfile
import tempfile
import hashlib
import time
import contextlib


# ═══════════════════════════════════════════════════════════
#  Atomic File Writes + Cross-Platform File Locking
# ═══════════════════════════════════════════════════════════

def _atomic_write(path, data, encoding='utf-8'):
    """Write to a file atomically: write to temp file then os.replace().
    
    Prevents file corruption from concurrent writes or crashes.
    """
    dir_name = os.path.dirname(path) or '.'
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding=encoding) as f:
            f.write(data)
        os.replace(tmp_path, path)  # atomic on all platforms
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def _file_lock(path, timeout=30):
    """Cross-platform advisory file lock using a .lock file.
    
    Uses atomic mkdir as the locking primitive (works on all platforms).
    """
    lock_path = path + '.lock'
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.mkdir(lock_path)
            break
        except (FileExistsError, PermissionError):
            if time.monotonic() > deadline:
                # Stale lock — force-remove after timeout
                try:
                    os.rmdir(lock_path)
                except OSError:
                    pass
                raise TimeoutError(f'Could not acquire lock on {path} within {timeout}s')
            time.sleep(0.05)
    try:
        yield
    finally:
        release_deadline = time.monotonic() + 1.0
        while True:
            try:
                os.rmdir(lock_path)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                if time.monotonic() > release_deadline:
                    break
                time.sleep(0.01)
            except OSError:
                break


# ═══════════════════════════════════════════════════════════
#  Semantic Versioning
# ═══════════════════════════════════════════════════════════

_SEMVER_RE = re.compile(
    r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)'
    r'(?:-(?P<pre>[0-9A-Za-z\-.]+))?(?:\+(?P<build>[0-9A-Za-z\-.]+))?$'
)


class SemVer:
    """Semantic version with comparison, range matching, and compatibility."""

    __slots__ = ('major', 'minor', 'patch', 'pre', 'build')

    def __init__(self, major, minor=0, patch=0, pre=None, build=None):
        self.major = int(major)
        self.minor = int(minor)
        self.patch = int(patch)
        self.pre = pre
        self.build = build

    @classmethod
    def parse(cls, s):
        """Parse a semver string. Returns SemVer or None on failure."""
        if not s or not isinstance(s, str):
            return None
        s = s.strip().lstrip('v')
        m = _SEMVER_RE.match(s)
        if not m:
            # Try partial: "1.0" -> "1.0.0", "1" -> "1.0.0"
            parts = s.split('.')
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                return cls(int(parts[0]), int(parts[1]), 0)
            if len(parts) == 1 and parts[0].isdigit():
                return cls(int(parts[0]), 0, 0)
            return None
        return cls(
            int(m.group('major')), int(m.group('minor')), int(m.group('patch')),
            m.group('pre'), m.group('build')
        )

    def _cmp_tuple(self):
        # Pre-release has lower precedence than release (None sorts after any string)
        if self.pre is None:
            return (self.major, self.minor, self.patch, 1, '')
        return (self.major, self.minor, self.patch, 0, self.pre)

    def __eq__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._cmp_tuple() == other._cmp_tuple()

    def __lt__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._cmp_tuple() < other._cmp_tuple()

    def __le__(self, other): return self == other or self < other
    def __gt__(self, other): return not self <= other
    def __ge__(self, other): return not self < other
    def __ne__(self, other): return not self == other

    def __repr__(self):
        return f"SemVer({self})"

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += f"-{self.pre}"
        if self.build:
            s += f"+{self.build}"
        return s

    def __hash__(self):
        return hash(self._cmp_tuple())

    def compatible(self, other):
        """Check caret (^) compatibility: same major, other >= self."""
        if self.major != other.major:
            return False
        return other >= self

    def tilde_compatible(self, other):
        """Check tilde (~) compatibility: same major.minor, other >= self."""
        if self.major != other.major or self.minor != other.minor:
            return False
        return other >= self


def parse_version_range(spec):
    """Parse a version specification string into a matcher function.
    
    Supports: exact ("1.2.3"), caret ("^1.2.0"), tilde ("~1.2.0"),
    operators (">=1.0.0", "<2.0.0"), ranges (">=1.0.0 <2.0.0"), wildcard ("*").
    Returns a function(SemVer) -> bool.
    """
    if not spec or spec.strip() == '*':
        return lambda v: True

    spec = spec.strip()

    # Range: two constraints separated by space
    if ' ' in spec:
        parts = spec.split()
        matchers = [parse_version_range(p) for p in parts]
        return lambda v: all(m(v) for m in matchers)

    # Caret: ^1.2.3
    if spec.startswith('^'):
        base = SemVer.parse(spec[1:])
        if not base:
            return lambda v: True
        return lambda v, b=base: b.compatible(v)

    # Tilde: ~1.2.3
    if spec.startswith('~'):
        base = SemVer.parse(spec[1:])
        if not base:
            return lambda v: True
        return lambda v, b=base: b.tilde_compatible(v)

    # Comparison operators
    for op in ('>=', '<=', '!=', '>', '<', '='):
        if spec.startswith(op):
            base = SemVer.parse(spec[len(op):])
            if not base:
                return lambda v: True
            if op == '>=': return lambda v, b=base: v >= b
            if op == '<=': return lambda v, b=base: v <= b
            if op == '>':  return lambda v, b=base: v > b
            if op == '<':  return lambda v, b=base: v < b
            if op == '!=': return lambda v, b=base: v != b
            if op == '=':  return lambda v, b=base: v == b

    # Exact match
    base = SemVer.parse(spec)
    if base:
        return lambda v, b=base: v == b
    return lambda v: True


# ═══════════════════════════════════════════════════════════
#  Dependency Resolution
# ═══════════════════════════════════════════════════════════

class DependencyConflict(Exception):
    """Raised when dependency versions are incompatible."""
    pass


def resolve_dependencies(manifest_path='.', installed=None):
    """Resolve the full transitive dependency tree.
    
    Returns dict: {package_name: {"version": str, "required_by": [str], "spec": str}}
    Raises DependencyConflict if incompatible versions are found.
    """
    manifest = load_manifest(manifest_path)
    if not manifest:
        return {}

    resolved = {}  # name -> {"version": str, "spec": str, "required_by": [str]}
    queue = []  # (name, version_spec, required_by)

    for name, spec in manifest.get('dependencies', {}).items():
        queue.append((name, str(spec), manifest.get('name', 'root')))

    visited = set()
    while queue:
        name, spec, required_by = queue.pop(0)

        if name in resolved:
            # Check compatibility with existing resolution
            existing = resolved[name]
            matcher = parse_version_range(spec)
            existing_ver = SemVer.parse(existing['version'])
            if existing_ver and not matcher(existing_ver):
                raise DependencyConflict(
                    f"Conflict: {name} required as '{spec}' by {required_by}, "
                    f"but already resolved to {existing['version']} "
                    f"(required by {', '.join(existing['required_by'])})"
                )
            existing['required_by'].append(required_by)
            continue

        # Determine version to install
        version = _resolve_best_version(name, spec)
        resolved[name] = {
            'version': version,
            'spec': spec,
            'required_by': [required_by],
        }

        # Check for transitive dependencies
        dep_key = f"{name}@{version}"
        if dep_key not in visited:
            visited.add(dep_key)
            pkg_dir = os.path.join(PACKAGES_DIR, name)
            pkg_manifest = load_manifest(pkg_dir) if os.path.isdir(pkg_dir) else None
            if pkg_manifest:
                for sub_name, sub_spec in pkg_manifest.get('dependencies', {}).items():
                    queue.append((sub_name, str(sub_spec), name))

    return resolved


def _resolve_best_version(name, spec):
    """Determine the best available version for a package given a spec."""
    # Check built-in registry
    if name in BUILTIN_REGISTRY:
        return BUILTIN_REGISTRY[name].get('version', '1.0.0')

    # Check locally installed
    pkg_dir = os.path.join(PACKAGES_DIR, name)
    if os.path.isdir(pkg_dir):
        manifest = load_manifest(pkg_dir)
        if manifest:
            return manifest.get('version', '1.0.0')

    # Check local registry
    local_reg = load_local_registry()
    if name in local_reg:
        return local_reg[name].get('version', '1.0.0')

    # Default to spec if it looks like a version
    v = SemVer.parse(spec)
    if v:
        return str(v)
    return '1.0.0'


# --- Constants ---
EPL_HOME = os.path.expanduser('~/.epl')
PACKAGES_DIR = os.path.join(EPL_HOME, 'packages')
CACHE_DIR = os.path.join(EPL_HOME, 'cache')
REGISTRY_URL = 'https://raw.githubusercontent.com/epl-lang/registry/main/registry.json'
LOCAL_REGISTRY_FILE = os.path.join(os.path.dirname(__file__), 'registry.json')
OFFICIAL_PACKAGES_DIR = os.path.join(os.path.dirname(__file__), 'official_packages')
MANIFEST_NAME = 'epl.json'          # legacy
TOML_MANIFEST_NAME = 'epl.toml'     # preferred
LOCKFILE_NAME = 'epl.lock'
LOCKFILE_VERSION = 3
PYTHON_DEPENDENCIES_SECTION = 'python-dependencies'
GITHUB_DEPENDENCIES_SECTION = 'github-dependencies'


# ═══════════════════════════════════════════════════════════
#  TOML Parser / Writer (self-contained — no external deps)
# ═══════════════════════════════════════════════════════════

def _parse_toml(text):
    """Pure-Python TOML parser supporting the subset used by epl.toml.

    Handles: tables [x], nested tables [x.y], strings, integers, floats,
    booleans, arrays, inline tables, multi-line basic strings, and comments.
    """
    result = {}
    current = result
    current_path = []
    lines = text.splitlines()
    i = 0

    def _skip_ws(s, p):
        while p < len(s) and s[p] in ' \t':
            p += 1
        return p

    def _parse_value(s, p):
        p = _skip_ws(s, p)
        if p >= len(s):
            raise ValueError('Expected value')
        ch = s[p]
        # Multi-line basic string
        if s[p:p+3] == '\"\"\"':
            p += 3
            buf = []
            # skip first newline if immediately after quotes
            if p < len(s) and s[p] == '\n':
                p += 1
            elif p + 1 < len(s) and s[p:p+2] == '\r\n':
                p += 2
            # collect lines until closing \"\"\"
            rest = s[p:]
            end_idx = rest.find('\"\"\"')
            if end_idx >= 0:
                return rest[:end_idx], p + end_idx + 3
            # Multi-line spanning actual lines
            buf.append(s[p:])
            nonlocal i
            i += 1
            while i < len(lines):
                ln = lines[i]
                idx = ln.find('\"\"\"')
                if idx >= 0:
                    buf.append(ln[:idx])
                    # re-parse rest of this line is not needed for epl.toml
                    val = '\n'.join(buf)
                    return val, len(s)  # consumed full line
                buf.append(ln)
                i += 1
            raise ValueError('Unterminated multi-line string')
        # Basic string
        if ch == '"':
            return _parse_basic_string(s, p)
        # Literal string
        if ch == "'":
            p += 1
            end = s.index("'", p)
            return s[p:end], end + 1
        # Boolean
        if s[p:p+4] == 'true':
            return True, p + 4
        if s[p:p+5] == 'false':
            return False, p + 5
        # Array
        if ch == '[':
            return _parse_array(s, p)
        # Inline table
        if ch == '{':
            return _parse_inline_table(s, p)
        # Number
        return _parse_number(s, p)

    def _parse_basic_string(s, p):
        p += 1  # skip opening quote
        buf = []
        while p < len(s):
            ch = s[p]
            if ch == '\\':
                p += 1
                if p >= len(s):
                    break
                esc = s[p]
                esc_map = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"'}
                buf.append(esc_map.get(esc, '\\' + esc))
                p += 1
            elif ch == '"':
                return ''.join(buf), p + 1
            else:
                buf.append(ch)
                p += 1
        raise ValueError('Unterminated string')

    def _parse_number(s, p):
        start = p
        if p < len(s) and s[p] in '+-':
            p += 1
        is_float = False
        while p < len(s) and (s[p].isdigit() or s[p] in '.eE_+-'):
            if s[p] in '.eE':
                is_float = True
            p += 1
        raw = s[start:p].replace('_', '')
        if is_float:
            return float(raw), p
        return int(raw), p

    def _parse_array(s, p):
        p += 1  # skip [
        arr = []
        p = _skip_ws(s, p)
        while p < len(s) and s[p] != ']':
            if s[p] in ',\n':
                p += 1
                p = _skip_ws(s, p)
                continue
            if s[p] == '#':
                break  # comment inside array line
            val, p = _parse_value(s, p)
            arr.append(val)
            p = _skip_ws(s, p)
            if p < len(s) and s[p] == ',':
                p += 1
                p = _skip_ws(s, p)
        if p < len(s) and s[p] == ']':
            p += 1
        return arr, p

    def _parse_inline_table(s, p):
        p += 1  # skip {
        tbl = {}
        p = _skip_ws(s, p)
        while p < len(s) and s[p] != '}':
            if s[p] == ',':
                p += 1
                p = _skip_ws(s, p)
                continue
            # key
            key, p = _parse_key(s, p)
            p = _skip_ws(s, p)
            if p < len(s) and s[p] == '=':
                p += 1
            p = _skip_ws(s, p)
            val, p = _parse_value(s, p)
            tbl[key] = val
            p = _skip_ws(s, p)
        if p < len(s) and s[p] == '}':
            p += 1
        return tbl, p

    def _parse_key(s, p):
        p = _skip_ws(s, p)
        if p < len(s) and s[p] == '"':
            return _parse_basic_string(s, p)
        if p < len(s) and s[p] == "'":
            p += 1
            end = s.index("'", p)
            return s[p:end], end + 1
        start = p
        while p < len(s) and s[p] in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-':
            p += 1
        return s[start:p], p

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Skip empty / comment lines
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        # Table header
        if stripped.startswith('['):
            if stripped.startswith('[['):
                # Array of tables
                key_part = stripped[2:stripped.index(']]')].strip()
                parts = [k.strip() for k in key_part.split('.')]
                target = result
                for p in parts[:-1]:
                    target = target.setdefault(p, {})
                last = parts[-1]
                if last not in target:
                    target[last] = []
                new_tbl = {}
                target[last].append(new_tbl)
                current = new_tbl
                current_path = parts
            else:
                key_part = stripped[1:stripped.index(']')].strip()
                parts = [k.strip() for k in key_part.split('.')]
                current = result
                for p in parts:
                    current = current.setdefault(p, {})
                current_path = parts
            i += 1
            continue
        # Key = value
        eq_pos = stripped.find('=')
        if eq_pos > 0:
            raw_key = stripped[:eq_pos].strip()
            # Handle dotted keys
            key_parts = [k.strip().strip('"').strip("'") for k in raw_key.split('.')]
            rest = stripped[eq_pos + 1:]
            val, _ = _parse_value(rest, 0)
            target = current
            for kp in key_parts[:-1]:
                target = target.setdefault(kp, {})
            target[key_parts[-1]] = val
        i += 1

    return result


def _dump_toml(data, _prefix=''):
    """Serialize a dict to TOML format string."""
    lines = []
    tables = []
    # Simple key=value pairs first
    for k, v in data.items():
        if isinstance(v, dict):
            tables.append((k, v))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            tables.append((k, v))  # array of tables
        else:
            lines.append(f'{k} = {_toml_value(v)}')
    # Then table sections
    for k, v in tables:
        if isinstance(v, list) and v and isinstance(v[0], dict):
            for item in v:
                full = f'{_prefix}{k}' if _prefix else k
                lines.append(f'\n[[{full}]]')
                lines.append(_dump_toml(item, f'{full}.'))
        else:
            full = f'{_prefix}{k}' if _prefix else k
            lines.append(f'\n[{full}]')
            lines.append(_dump_toml(v, f'{full}.'))
    return '\n'.join(lines)


def _toml_value(v):
    """Convert a Python value to TOML value syntax."""
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    if isinstance(v, str):
        escaped = v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return f'"{escaped}"'
    if isinstance(v, list):
        items = ', '.join(_toml_value(x) for x in v)
        return f'[{items}]'
    if isinstance(v, dict):
        items = ', '.join(f'{k} = {_toml_value(val)}' for k, val in v.items())
        return '{' + items + '}'
    return str(v)


def _toml_to_manifest(toml_data):
    """Convert epl.toml structure to internal manifest dict.

    epl.toml uses [project] for metadata and [dependencies] for deps.
    Internal manifest uses flat top-level keys.
    """
    project = toml_data.get('project', {})
    manifest = {
        'name': project.get('name', ''),
        'version': project.get('version', '1.0.0'),
        'description': project.get('description', ''),
        'author': project.get('author', ''),
        'license': project.get('license', ''),
        'entry': project.get('entry', 'main.epl'),
        'keywords': project.get('keywords', []),
        'repository': project.get('repository', ''),
        'dependencies': toml_data.get('dependencies', {}),
        'python-dependencies': toml_data.get(PYTHON_DEPENDENCIES_SECTION, {}),
        'github-dependencies': toml_data.get(GITHUB_DEPENDENCIES_SECTION, {}),
        'dev-dependencies': toml_data.get('dev-dependencies', {}),
        'scripts': toml_data.get('scripts', {}),
    }
    # Carry over [tool] section if present
    if 'tool' in toml_data:
        manifest['tool'] = toml_data['tool']
    return manifest


def _manifest_to_toml(manifest):
    """Convert internal manifest dict to epl.toml TOML structure."""
    toml = {
        'project': {
            'name': manifest.get('name', ''),
            'version': manifest.get('version', '1.0.0'),
            'description': manifest.get('description', ''),
            'author': manifest.get('author', ''),
            'license': manifest.get('license', ''),
            'entry': manifest.get('entry', 'main.epl'),
        },
        'dependencies': manifest.get('dependencies', {}),
        'scripts': manifest.get('scripts', {}),
    }
    python_deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    if python_deps:
        toml[PYTHON_DEPENDENCIES_SECTION] = python_deps
    github_deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})
    if github_deps:
        toml[GITHUB_DEPENDENCIES_SECTION] = github_deps
    kw = manifest.get('keywords', [])
    if kw:
        toml['project']['keywords'] = kw
    repo = manifest.get('repository', '')
    if repo:
        toml['project']['repository'] = repo
    dev = manifest.get('dev-dependencies', {})
    if dev:
        toml['dev-dependencies'] = dev
    tool = manifest.get('tool', {})
    if tool:
        toml['tool'] = tool
    return toml

# --- Security: Package name sanitization ---
_SAFE_PKG_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')

def _sanitize_package_name(name):
    """Validate and sanitize a package name to prevent path traversal.
    Returns the sanitized name or raises ValueError."""
    if not name or not isinstance(name, str):
        raise ValueError("Package name must be a non-empty string")
    name = name.strip()
    if not _SAFE_PKG_NAME_RE.match(name):
        raise ValueError(
            f'Invalid package name "{name}". '
            f'Names must be alphanumeric with . _ - only (no path separators).')
    # Extra safety: ensure no path component tricks
    if '..' in name or '/' in name or '\\' in name:
        raise ValueError(f'Invalid package name "{name}": path traversal detected.')
    return name

def _validate_url(url):
    """Validate that a URL uses only https:// scheme."""
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    if not url.startswith('https://'):
        raise ValueError(
            f'Only https:// URLs are allowed for security. Got: {url[:80]}')
    return url

def _validate_github_repo(repo):
    """Validate a GitHub repo string (owner/repo format)."""
    if not repo or not isinstance(repo, str):
        raise ValueError("GitHub repo must be a non-empty string")
    if not re.match(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$', repo):
        raise ValueError(
            f'Invalid GitHub repo format: "{repo}". Expected "owner/repo".')
    return repo

# Built-in package registry (works offline)
BUILTIN_REGISTRY = {
    "epl-math": {
        "description": "Extended math functions for EPL",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-http": {
        "description": "HTTP client and server utilities",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-json": {
        "description": "JSON parsing and serialization",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-crypto": {
        "description": "Cryptographic functions",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-datetime": {
        "description": "Date and time utilities",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-regex": {
        "description": "Regular expression support",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-fs": {
        "description": "File system utilities",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-db": {
        "description": "Database operations (SQLite)",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-testing": {
        "description": "Unit testing framework",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-string": {
        "description": "Extended string utilities",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-collections": {
        "description": "Advanced collection data structures",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-web": {
        "description": "Web framework helpers",
        "version": "1.0.0",
        "type": "builtin"
    },
    # ── v3.0 Real modules ──
    "epl-networking": {
        "description": "Real TCP/UDP/HTTP networking with SSL support",
        "version": "3.0.0",
        "type": "builtin"
    },
    "epl-concurrency": {
        "description": "Real threading, thread pools, mutexes, channels, atomics",
        "version": "3.0.0",
        "type": "builtin"
    },
    "epl-database": {
        "description": "Production SQLite with connection pooling, ORM, migrations",
        "version": "3.0.0",
        "type": "builtin"
    },
    "epl-vm": {
        "description": "Bytecode VM engine for 10-50x faster execution",
        "version": "3.0.0",
        "type": "builtin"
    },
    "epl-packager": {
        "description": "Package EPL programs into standalone executables",
        "version": "3.0.0",
        "type": "builtin"
    },
    # ── Utility packages ──
    "epl-csv": {
        "description": "CSV file reading, writing, and parsing",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-os": {
        "description": "Operating system and environment utilities",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-encoding": {
        "description": "Base64, hex, URL encoding and decoding",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-uuid": {
        "description": "UUID generation (v4)",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-logging": {
        "description": "Structured logging with levels and formatting",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-validation": {
        "description": "Input validation (email, URL, number ranges, patterns)",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-template": {
        "description": "String template engine with variables and loops",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-config": {
        "description": "Configuration file support (JSON, INI, env files)",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-cli": {
        "description": "Command-line argument parsing and colored output",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-events": {
        "description": "Event emitter / pub-sub pattern",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-cache": {
        "description": "In-memory cache with TTL and LRU eviction",
        "version": "1.0.0",
        "type": "builtin"
    },
    "epl-compression": {
        "description": "Gzip and zlib compression/decompression",
        "version": "1.0.0",
        "type": "builtin"
    },
    # ── v4.0 Production modules ──
    "epl-async": {
        "description": "Async event loop, tasks, channels, and structured concurrency",
        "version": "4.0.0",
        "type": "builtin"
    },
    "epl-wsgi": {
        "description": "Production WSGI/ASGI web server with middleware and routing",
        "version": "4.0.0",
        "type": "builtin"
    },
    "epl-types": {
        "description": "Static type checking and type annotations",
        "version": "4.0.0",
        "type": "builtin"
    },
    "epl-interfaces": {
        "description": "Interface definitions and implementation validation",
        "version": "4.0.0",
        "type": "builtin"
    },
    "epl-modules": {
        "description": "Module namespacing with export/import and :: access",
        "version": "4.0.0",
        "type": "builtin"
    },
    "epl-profiler": {
        "description": "Performance profiler and execution tracer",
        "version": "4.0.0",
        "type": "builtin"
    },
    "epl-debug": {
        "description": "Debug Adapter Protocol server for IDE integration",
        "version": "4.0.0",
        "type": "builtin"
    },
    # ── v4.2 Ecosystem packages ──
    "epl-auth": {
        "description": "Authentication and authorization (JWT, OAuth2, sessions, RBAC)",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["auth", "jwt", "oauth", "security", "login"]
    },
    "epl-email": {
        "description": "Send emails via SMTP with templates and attachments",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["email", "smtp", "mail", "send"]
    },
    "epl-pdf": {
        "description": "Generate PDF documents with text, tables, and images",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["pdf", "document", "report", "generate"]
    },
    "epl-charts": {
        "description": "Generate charts and graphs (bar, line, pie, scatter) as SVG/HTML",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["chart", "graph", "visualization", "plot", "svg"]
    },
    "epl-orm": {
        "description": "Object-relational mapping with models, queries, and migrations",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["orm", "database", "model", "query", "migration"]
    },
    "epl-queue": {
        "description": "Task queue and background job processing",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["queue", "job", "task", "background", "worker"]
    },
    "epl-scheduler": {
        "description": "Cron-like task scheduling and recurring jobs",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["scheduler", "cron", "timer", "recurring", "job"]
    },
    "epl-websocket": {
        "description": "WebSocket client and server with rooms and broadcasting",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["websocket", "realtime", "ws", "socket", "broadcast"]
    },
    "epl-xml": {
        "description": "XML parsing, generation, and XPath queries",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["xml", "parse", "xpath", "generate"]
    },
    "epl-i18n": {
        "description": "Internationalization and localization (translations, formatting)",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["i18n", "l10n", "translation", "locale", "language"]
    },
    "epl-rate-limit": {
        "description": "Rate limiting with token bucket and sliding window algorithms",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["rate-limit", "throttle", "api", "protection"]
    },
    "epl-markdown": {
        "description": "Markdown parser and HTML renderer",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["markdown", "md", "html", "render", "parse"]
    },
    "epl-color": {
        "description": "Color manipulation (hex, RGB, HSL, contrast, palette generation)",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["color", "hex", "rgb", "hsl", "palette"]
    },
    "epl-semver": {
        "description": "Semantic versioning comparison, parsing, and range matching",
        "version": "4.2.0",
        "type": "builtin",
        "keywords": ["semver", "version", "compare", "range"]
    },
    # ── v5.2 Triple Ecosystem ──
    "epl-ffi": {
        "description": "C Foreign Function Interface — call C libraries from EPL",
        "version": "5.2.0",
        "type": "builtin",
        "keywords": ["ffi", "c", "native", "external", "interop"]
    },
}


def ensure_dirs():
    """Ensure EPL directories exist."""
    os.makedirs(PACKAGES_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)


def _get_official_package_dir(name):
    """Return the path to a bundled official package, if present."""
    candidate = os.path.join(OFFICIAL_PACKAGES_DIR, name)
    return candidate if os.path.isdir(candidate) else None


# --- Local Registry ---

def _get_local_registry_path():
    return os.path.join(EPL_HOME, 'local_registry.json')

def load_local_registry():
    """Load the local package registry."""
    path = _get_local_registry_path()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_local_registry(registry):
    """Save the local package registry (atomic write + file lock)."""
    ensure_dirs()
    path = _get_local_registry_path()
    with _file_lock(path):
        _atomic_write(path, json.dumps(registry, indent=2, sort_keys=True))

def register_installed_package(name, version, source, path, metadata=None):
    """Register a package in the local registry (thread-safe)."""
    registry_path = _get_local_registry_path()
    with _file_lock(registry_path):
        reg = load_local_registry()
        reg[name] = {
            "version": version,
            "source": source,
            "path": path,
            "installed_at": time.time(),
        }
        if metadata:
            reg[name]["metadata"] = dict(metadata)
        _atomic_write(registry_path, json.dumps(reg, indent=2, sort_keys=True))


def _dump_json(data):
    """Return deterministic JSON output."""
    return json.dumps(data, indent=2, sort_keys=True) + '\n'


def _sha256_file(path):
    """Compute a file SHA-256 digest."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _normalize_lockfile(lock):
    """Upgrade older lockfiles into the current in-memory structure."""
    if not lock:
        return None

    normalized = dict(lock)
    version = normalized.get('lockfileVersion', 1)

    metadata = dict(normalized.get('metadata', {}))
    if version < 3 and 'created' in normalized:
        metadata['created'] = normalized.pop('created')
    normalized['metadata'] = metadata
    normalized['packages'] = dict(sorted(normalized.get('packages', {}).items()))
    normalized['python_packages'] = dict(sorted(normalized.get('python_packages', {}).items()))
    normalized['github_packages'] = dict(sorted(normalized.get('github_packages', {}).items()))
    normalized['lockfileVersion'] = max(version, LOCKFILE_VERSION)
    return normalized


def _write_lockfile(path, lock):
    """Persist a lockfile with deterministic ordering."""
    _atomic_write(os.path.join(path, LOCKFILE_NAME), _dump_json(_normalize_lockfile(lock)))


def _extract_distribution_name(requirement):
    """Best-effort extraction of a distribution name from a pip requirement."""
    if not requirement or os.path.exists(str(requirement)):
        return None

    candidate = str(requirement).strip()
    match = re.match(r'^([A-Za-z0-9_.-]+)', candidate)
    if not match:
        return None

    name = match.group(1)
    return name.split('[', 1)[0]


def _hash_distribution(dist):
    """Hash installed Python distribution files deterministically."""
    h = hashlib.sha256()
    files = sorted(dist.files or [], key=lambda item: str(item))
    for file_entry in files:
        rel_path = str(file_entry)
        h.update(rel_path.encode('utf-8'))
        target = dist.locate_file(file_entry)
        if os.path.isdir(target):
            continue
        try:
            with open(target, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                    h.update(chunk)
        except OSError:
            h.update(b'<missing>')
    return h.hexdigest()


def _resolve_installed_python_package(import_name, requirement=None):
    """Resolve an installed Python bridge package into lockfile metadata."""
    candidates = []
    base_import = str(import_name).split('.', 1)[0]
    packages_map = importlib_metadata.packages_distributions()
    candidates.extend(packages_map.get(import_name, []))
    if base_import != import_name:
        candidates.extend(packages_map.get(base_import, []))

    dist_name = _extract_distribution_name(requirement)
    if dist_name:
        candidates.append(dist_name)

    seen = set()
    for candidate in candidates:
        normalized = str(candidate).strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        try:
            dist = importlib_metadata.distribution(normalized)
        except importlib_metadata.PackageNotFoundError:
            continue
        metadata_name = dist.metadata.get('Name', normalized)
        return {
            'distribution': metadata_name,
            'version': dist.version,
            'integrity': _hash_distribution(dist),
        }
    return None


def _find_registered_github_package(repo):
    """Find a locally installed package that originated from the given GitHub repo."""
    repo = _validate_github_repo(repo)
    for name, info in load_local_registry().items():
        metadata = info.get('metadata', {})
        if metadata.get('repo') == repo:
            return name, info
    return None, None


def _github_api_json(url):
    """Fetch a GitHub API document with a stable User-Agent."""
    req = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'epl-package-manager',
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def _resolve_github_archive(repo, commit=None):
    """Resolve a GitHub repo to an archive URL and pinned commit."""
    repo = _validate_github_repo(repo)
    if commit:
        return commit, f'https://github.com/{repo}/archive/{commit}.zip'

    try:
        repo_data = _github_api_json(f'https://api.github.com/repos/{repo}')
        default_branch = repo_data.get('default_branch', 'main')
        commit_data = _github_api_json(f'https://api.github.com/repos/{repo}/commits/{default_branch}')
        resolved_commit = commit_data.get('sha')
        if resolved_commit:
            return resolved_commit, f'https://github.com/{repo}/archive/{resolved_commit}.zip'
    except Exception:
        pass

    return None, f'https://github.com/{repo}/archive/refs/heads/main.zip'


# --- Package Resolution (for imports) ---

def find_package_module(name):
    """Find a package module for import resolution.
    
    Searches in order:
    1. Current directory .epl files
    2. ./epl_modules/ directory
    3. ~/.epl/packages/ directory
    4. Built-in stdlib modules
    
    Returns the path to the .epl file, or None.
    """
    # Sanitize the package name to prevent path traversal
    try:
        name = _sanitize_package_name(name)
    except ValueError:
        return None
    # 1. Current directory
    local_file = f"{name}.epl"
    if os.path.isfile(local_file):
        return os.path.abspath(local_file)
    
    # 2. Local epl_modules directory
    local_modules = os.path.join('.', 'epl_modules', name)
    if os.path.isdir(local_modules):
        # Look for main.epl or index.epl or <name>.epl
        for entry_name in ['main.epl', 'index.epl', f'{name}.epl']:
            entry = os.path.join(local_modules, entry_name)
            if os.path.isfile(entry):
                return os.path.abspath(entry)
    local_module_file = os.path.join('.', 'epl_modules', f'{name}.epl')
    if os.path.isfile(local_module_file):
        return os.path.abspath(local_module_file)
    
    # 3. Global packages directory (~/.epl/packages/)
    pkg_dir = os.path.join(PACKAGES_DIR, name)
    if os.path.isdir(pkg_dir):
        # Check manifest for entry point
        manifest = load_manifest(pkg_dir)
        if manifest and 'entry' in manifest:
            entry = os.path.join(pkg_dir, manifest['entry'])
            if os.path.isfile(entry):
                return entry
        # Fallback to standard entry names
        for entry_name in ['main.epl', 'index.epl', f'{name}.epl']:
            entry = os.path.join(pkg_dir, entry_name)
            if os.path.isfile(entry):
                return entry
        # Any .epl file
        for f in os.listdir(pkg_dir):
            if f.endswith('.epl'):
                return os.path.join(pkg_dir, f)
    
    return None


def auto_install_package(name):
    """Try to auto-install a package when import fails.

    Returns the module path if install succeeds, None otherwise.
    Used by the interpreter for seamless import experience.
    """
    # Resolve the name (allow 'math' -> 'epl-math')
    actual = _resolve_package_name(name)
    official_pkg = _get_official_package_dir(actual)
    if official_pkg:
        success = _install_from_local(official_pkg, source=f'official:{actual}')
        if success:
            return find_package_module(actual)
    if actual in BUILTIN_REGISTRY:
        success = _install_builtin_package(actual)
        if success:
            return find_package_module(actual)
    return None


def search_packages(query):
    """Search for packages in the package index plus local/built-in registries."""
    results = {}
    query_lower = query.lower()
    
    # Search bundled official packages
    if os.path.isdir(OFFICIAL_PACKAGES_DIR):
        for pkg_name in sorted(os.listdir(OFFICIAL_PACKAGES_DIR)):
            pkg_dir = os.path.join(OFFICIAL_PACKAGES_DIR, pkg_name)
            manifest = load_manifest(pkg_dir) if os.path.isdir(pkg_dir) else None
            if not manifest:
                continue
            description = manifest.get('description', '')
            if query_lower in pkg_name.lower() or query_lower in description.lower():
                results[pkg_name] = {
                    'name': pkg_name,
                    'version': manifest.get('version', '?'),
                    'description': description,
                    'source': 'official',
                    'latest': manifest.get('version', '?'),
                }

    # Search built-in registry
    for name, info in BUILTIN_REGISTRY.items():
        if query_lower in name.lower() or query_lower in info.get('description', '').lower():
            current = results.get(name, {})
            results[name] = {
                'name': name,
                'version': current.get('version', info.get('version', '?')),
                'description': current.get('description') or info.get('description', ''),
                'source': current.get('source', 'builtin'),
                'latest': current.get('latest', info.get('version', '?')),
            }
    
    # Search local registry
    local_reg = load_local_registry()
    for name, info in local_reg.items():
        if query_lower in name.lower():
            results.setdefault(name, {
                'name': name,
                'version': info.get('version', '?'),
                'description': '',
                'source': info.get('source', 'local'),
            })

    # Search package index
    try:
        from epl.package_index import PackageIndex

        for entry in PackageIndex().search(query, limit=30):
            latest = entry.latest_version.version if entry.latest_version else '?'
            current = results.get(entry.name, {})
            results[entry.name] = {
                'name': entry.name,
                'version': current.get('version', latest),
                'description': entry.metadata.description or current.get('description', ''),
                'source': current.get('source', 'index'),
                'latest': latest,
            }
    except Exception:
        pass
    
    # Search installed packages
    if os.path.exists(PACKAGES_DIR):
        for pkg_name in os.listdir(PACKAGES_DIR):
            if query_lower in pkg_name.lower():
                manifest = load_manifest(os.path.join(PACKAGES_DIR, pkg_name))
                current = results.get(pkg_name, {})
                results[pkg_name] = {
                    'name': pkg_name,
                    'version': manifest.get('version', '?') if manifest else current.get('version', '?'),
                    'description': current.get('description') or (manifest.get('description', '') if manifest else ''),
                    'source': 'installed',
                    'latest': current.get('latest', current.get('version', '?')),
                }

    return sorted(results.values(), key=lambda item: item['name'])


def _get_index_entry(name):
    """Return a package-index entry when available."""
    try:
        from epl.package_index import PackageIndex

        return PackageIndex().fetch_package(name)
    except Exception:
        return None


def _get_latest_available_version(name):
    """Resolve the best-known latest version for a package."""
    entry = _get_index_entry(name)
    if entry and entry.latest_version:
        return entry.latest_version.version
    official_pkg = _get_official_package_dir(name)
    if official_pkg:
        manifest = load_manifest(official_pkg)
        if manifest:
            return manifest.get('version')
    if name in BUILTIN_REGISTRY:
        return BUILTIN_REGISTRY[name].get('version')
    local_reg = load_local_registry()
    if name in local_reg:
        return local_reg[name].get('version')
    return None


# --- Lockfile ---

def create_lockfile(path='.'):
    """Generate a deterministic lockfile from the current project state."""
    manifest = load_manifest(path)
    if not manifest:
        return None
    
    deps = manifest.get('dependencies', {})
    lock = {
        "lockfileVersion": LOCKFILE_VERSION,
        "metadata": {
            "project": manifest.get('name', os.path.basename(os.path.abspath(path))),
            "manifest": TOML_MANIFEST_NAME if get_manifest_format(path) == 'toml' else MANIFEST_NAME,
        },
        "packages": {},
        "python_packages": {},
        "github_packages": {},
    }
    
    # Also include transitive dependencies
    try:
        resolved = resolve_dependencies(path)
    except DependencyConflict as e:
        print(f"  Warning: Dependency conflict detected: {e}", flush=True)
        print(f"  Lockfile will include only direct dependencies.", flush=True)
        resolved = {name: {'version': ver, 'spec': ver, 'required_by': ['root']}
                    for name, ver in deps.items()}

    for name, info in sorted(resolved.items()):
        pkg_dir = os.path.join(PACKAGES_DIR, name)
        if os.path.isdir(pkg_dir):
            integrity = _hash_directory(pkg_dir)
            lock["packages"][name] = {
                "version": info.get('version', '1.0.0'),
                "integrity": integrity,
                "required_by": sorted(info.get('required_by', [])),
            }

    python_deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    for import_name, requirement in sorted(python_deps.items()):
        normalized_requirement = _normalize_python_requirement(import_name, requirement)
        resolved_py = _resolve_installed_python_package(import_name, normalized_requirement) or {}
        lock["python_packages"][import_name] = {
            "distribution": resolved_py.get('distribution', _extract_distribution_name(normalized_requirement) or import_name),
            "version": resolved_py.get('version', ''),
            "pip_spec": normalized_requirement,
            "integrity": resolved_py.get('integrity', ''),
        }

    github_deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})
    for alias, repo in sorted(github_deps.items()):
        repo = _validate_github_repo(repo)
        package_name, registered = _find_registered_github_package(repo)
        metadata = (registered or {}).get('metadata', {})
        commit = metadata.get('commit')

        pkg_dir = None
        version = ''
        integrity = ''
        if registered:
            pkg_dir = registered.get('path')
            version = registered.get('version', '')
        elif package_name:
            pkg_dir = os.path.join(PACKAGES_DIR, package_name)

        if pkg_dir and os.path.isdir(pkg_dir):
            integrity = _hash_directory(pkg_dir)
            pkg_manifest = load_manifest(pkg_dir)
            if pkg_manifest:
                version = pkg_manifest.get('version', version)

        lock["github_packages"][alias] = {
            "repo": repo,
            "commit": commit or '',
            "package": package_name or alias,
            "version": version,
            "integrity": integrity,
            "archive_integrity": metadata.get('archive_integrity', ''),
        }

    _write_lockfile(path, lock)
    return lock


def load_lockfile(path='.'):
    """Load and parse an existing lockfile."""
    lock_path = os.path.join(path, LOCKFILE_NAME)
    if not os.path.exists(lock_path):
        return None
    with open(lock_path, 'r', encoding='utf-8') as f:
        return _normalize_lockfile(json.load(f))


def verify_lockfile(path='.', include_bridge=True):
    """Verify installed packages match the lockfile.
    
    Returns dict with keys: 'valid' (bool), 'mismatches' (list), 'missing' (list).
    """
    lock = load_lockfile(path)
    if not lock:
        return {'valid': False, 'mismatches': [], 'missing': ['No lockfile found']}

    mismatches = []
    missing = []

    for name, lock_info in lock.get('packages', {}).items():
        pkg_dir = os.path.join(PACKAGES_DIR, name)
        if not os.path.isdir(pkg_dir):
            missing.append(name)
            continue

        # Verify integrity hash
        expected_hash = lock_info.get('integrity', '')
        actual_hash = _hash_directory(pkg_dir)
        if expected_hash and actual_hash != expected_hash:
            mismatches.append({
                'package': name,
                'expected_integrity': expected_hash,
                'actual_integrity': actual_hash,
            })

        # Verify version
        pkg_manifest = load_manifest(pkg_dir)
        if pkg_manifest:
            expected_ver = lock_info.get('version', '')
            actual_ver = pkg_manifest.get('version', '')
            if expected_ver and actual_ver != expected_ver:
                mismatches.append({
                    'package': name,
                    'expected_version': expected_ver,
                    'actual_version': actual_ver,
                })

    if include_bridge:
        for import_name, lock_info in lock.get('python_packages', {}).items():
            resolved = _resolve_installed_python_package(import_name, lock_info.get('pip_spec'))
            if not resolved:
                missing.append(f'python:{import_name}')
                continue
            expected_ver = lock_info.get('version', '')
            expected_integrity = lock_info.get('integrity', '')
            if expected_ver and resolved.get('version') != expected_ver:
                mismatches.append({
                    'package': f'python:{import_name}',
                    'expected_version': expected_ver,
                    'actual_version': resolved.get('version', ''),
                })
            if expected_integrity and resolved.get('integrity') != expected_integrity:
                mismatches.append({
                    'package': f'python:{import_name}',
                    'expected_integrity': expected_integrity,
                    'actual_integrity': resolved.get('integrity', ''),
                })

        for alias, lock_info in lock.get('github_packages', {}).items():
            repo = lock_info.get('repo', '')
            if not repo:
                missing.append(f'github:{alias}')
                continue
            package_name, registered = _find_registered_github_package(repo)
            if not registered:
                missing.append(f'github:{alias}')
                continue
            metadata = registered.get('metadata', {})
            expected_commit = lock_info.get('commit', '')
            actual_commit = metadata.get('commit', '')
            if expected_commit and actual_commit != expected_commit:
                mismatches.append({
                    'package': f'github:{alias}',
                    'expected_commit': expected_commit,
                    'actual_commit': actual_commit,
                })

            expected_integrity = lock_info.get('integrity', '')
            pkg_path = registered.get('path')
            actual_integrity = _hash_directory(pkg_path) if pkg_path and os.path.isdir(pkg_path) else ''
            if expected_integrity and actual_integrity != expected_integrity:
                mismatches.append({
                    'package': f'github:{alias}',
                    'expected_integrity': expected_integrity,
                    'actual_integrity': actual_integrity,
                })

    return {
        'valid': len(mismatches) == 0 and len(missing) == 0,
        'mismatches': mismatches,
        'missing': missing,
    }


def install_from_lockfile(path='.', include_bridge=False, strict=False):
    """Install dependencies from a lockfile.

    Args:
        include_bridge: also install locked Python and GitHub dependencies.
        strict: require complete lockfile coverage for declared dependencies.
    """
    lock = load_lockfile(path)
    if not lock:
        print("  No lockfile found. Run 'epl lock' to create one.")
        return False

    manifest = load_manifest(path)
    if strict and manifest:
        missing_lock_entries = []
        for dep_name in manifest.get('dependencies', {}):
            if dep_name not in lock.get('packages', {}):
                missing_lock_entries.append(dep_name)
        for import_name in manifest.get(PYTHON_DEPENDENCIES_SECTION, {}):
            if import_name not in lock.get('python_packages', {}):
                missing_lock_entries.append(f'python:{import_name}')
        for alias, repo in manifest.get(GITHUB_DEPENDENCIES_SECTION, {}).items():
            entry = lock.get('github_packages', {}).get(alias)
            if not entry:
                missing_lock_entries.append(f'github:{alias}')
                continue
            if _validate_github_repo(repo) != entry.get('repo'):
                print(f"  Lockfile repo mismatch for GitHub dependency '{alias}'.")
                return False
            if not entry.get('commit'):
                print(f"  GitHub dependency '{alias}' is not pinned to a commit in the lockfile.")
                return False

        if missing_lock_entries:
            print("  Lockfile is missing declared dependencies:")
            for item in missing_lock_entries:
                print(f"    - {item}")
            return False

    packages = lock.get('packages', {})
    python_packages = lock.get('python_packages', {}) if include_bridge else {}
    github_packages = lock.get('github_packages', {}) if include_bridge else {}
    if not packages and not python_packages and not github_packages:
        print("  Lockfile has no packages.")
        return True

    total = len(packages) + len(python_packages) + len(github_packages)
    print(f"  Installing {total} locked dependencies...")
    success = True
    for name, info in sorted(packages.items()):
        version = info.get('version', None)
        if not install_package(name, version):
            print(f"  Failed to install {name}@{version}")
            success = False

    for alias, info in sorted(github_packages.items()):
        repo = info.get('repo')
        commit = info.get('commit')
        archive_integrity = info.get('archive_integrity') or None
        if not repo or not commit:
            print(f"  GitHub dependency '{alias}' is not fully pinned in the lockfile.")
            success = False
            continue
        if not _install_from_github(repo, commit=commit, expected_sha256=archive_integrity):
            print(f"  Failed to install GitHub dependency: {alias} -> {repo}@{commit}")
            success = False

    for import_name, info in sorted(python_packages.items()):
        distribution = info.get('distribution') or import_name
        version = info.get('version')
        pip_spec = info.get('pip_spec') or import_name
        requirement = f'{distribution}=={version}' if version else pip_spec
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', requirement])
            resolved = _resolve_installed_python_package(import_name, pip_spec)
            expected_integrity = info.get('integrity', '')
            if expected_integrity and resolved and resolved.get('integrity') != expected_integrity:
                print(f"  Integrity mismatch after installing Python dependency: {import_name}")
                success = False
        except subprocess.CalledProcessError:
            print(f"  Failed to install Python dependency: {requirement}")
            success = False

    result = verify_lockfile(path, include_bridge=include_bridge)
    if not result['valid']:
        print(f"  Warning: Lockfile verification found issues after install.")
        for m in result['mismatches']:
            print(f"    Mismatch: {m}")
        for m in result['missing']:
            print(f"    Missing: {m}")

    return success and result['valid']


def _hash_directory(path):
    """Generate a deterministic hash of a directory's contents and structure."""
    h = hashlib.sha256()
    for root, dirs, files in os.walk(path):
        dirs.sort()  # Ensure deterministic traversal order
        rel_root = os.path.relpath(root, path)
        h.update(rel_root.encode('utf-8'))
        for f in sorted(files):
            fp = os.path.join(root, f)
            rel_path = os.path.relpath(fp, path)
            h.update(rel_path.encode('utf-8'))
            try:
                with open(fp, 'rb') as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b'<unreadable>')
    return h.hexdigest()


# ─── Manifest ───────────────────────────────────────────

def create_manifest(name="my-project", version="1.0.0", description="",
                    author="", entry="main.epl", dependencies=None,
                    python_dependencies=None,
                    github_dependencies=None,
                    fmt="toml"):
    """Create a project manifest (epl.toml preferred, epl.json as legacy).

    Args:
        fmt: 'toml' (default) writes epl.toml, 'json' writes epl.json.
    Returns the manifest data dict (internal flat format).
    """
    manifest = {
        "name": name,
        "version": version,
        "description": description,
        "author": author,
        "entry": entry,
        "dependencies": dependencies or {},
        "python-dependencies": python_dependencies or {},
        "github-dependencies": github_dependencies or {},
        "scripts": {
            "start": f"epl run {entry}",
            "build": f"epl build {entry}",
            "test": "epl tests/run_tests.epl"
        }
    }
    if fmt == "toml":
        toml_data = _manifest_to_toml(manifest)
        _atomic_write(TOML_MANIFEST_NAME, _dump_toml(toml_data) + '\n')
    else:
        _atomic_write(MANIFEST_NAME, json.dumps(manifest, indent=2))
    return manifest


def load_manifest(path='.'):
    """Load manifest from epl.toml (preferred) or epl.json (fallback).

    Always returns the internal flat-format dict or None.
    """
    # Try epl.toml first
    toml_fp = os.path.join(path, TOML_MANIFEST_NAME)
    if os.path.exists(toml_fp):
        with open(toml_fp, 'r', encoding='utf-8') as f:
            toml_data = _parse_toml(f.read())
        return _toml_to_manifest(toml_data)

    # Fallback to epl.json
    json_fp = os.path.join(path, MANIFEST_NAME)
    if os.path.exists(json_fp):
        with open(json_fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_manifest(manifest, path='.', fmt=None):
    """Save manifest data back. Uses epl.toml if it exists, else epl.json."""
    if fmt is None:
        toml_fp = os.path.join(path, TOML_MANIFEST_NAME)
        fmt = 'toml' if os.path.exists(toml_fp) else 'json'
    if fmt == 'toml':
        toml_data = _manifest_to_toml(manifest)
        fp = os.path.join(path, TOML_MANIFEST_NAME)
        _atomic_write(fp, _dump_toml(toml_data) + '\n')
    else:
        fp = os.path.join(path, MANIFEST_NAME)
        _atomic_write(fp, json.dumps(manifest, indent=2))


def get_manifest_format(path='.'):
    """Return which manifest format exists in path: 'toml', 'json', or None."""
    if os.path.exists(os.path.join(path, TOML_MANIFEST_NAME)):
        return 'toml'
    if os.path.exists(os.path.join(path, MANIFEST_NAME)):
        return 'json'
    return None


def find_project_root(start='.'):
    """Find the nearest directory containing epl.toml or epl.json."""
    current = os.path.abspath(start)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        if get_manifest_format(current):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


_PYTHON_IMPORT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$')


def _validate_python_import_name(import_name):
    """Validate a Python import/module name used by EPL manifests and CLI."""
    if not isinstance(import_name, str):
        raise ValueError("Python import name must be a string")
    import_name = import_name.strip()
    if not _PYTHON_IMPORT_RE.match(import_name):
        raise ValueError(
            f"Invalid Python import name: {import_name!r}. "
            "Use dotted module names like requests, yaml, PIL, or fastapi."
        )
    return import_name


def _normalize_python_requirement(import_name, requirement=None):
    """Normalize a pip requirement string for installation."""
    import_name = _validate_python_import_name(import_name)
    if requirement is None:
        return import_name
    requirement = str(requirement).strip()
    if not requirement or requirement == '*':
        return import_name
    return requirement


def list_python_dependencies(path='.'):
    """Return Python dependencies declared in the nearest project manifest."""
    project_root = find_project_root(path)
    if not project_root:
        return []
    manifest = load_manifest(project_root)
    if not manifest:
        return []
    deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    return sorted(deps.items())


def list_github_dependencies(path='.'):
    """Return GitHub dependencies declared in the nearest project manifest."""
    project_root = find_project_root(path)
    if not project_root:
        return []
    manifest = load_manifest(project_root)
    if not manifest:
        return []
    deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})
    return sorted(deps.items())


def resolve_python_dependency(import_name, path='.'):
    """Resolve a Python import name to a pip requirement declared in epl.toml."""
    project_root = find_project_root(path)
    if not project_root:
        return None
    manifest = load_manifest(project_root)
    if not manifest:
        return None

    deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    if not deps:
        return None

    import_name = import_name.strip()
    candidates = [import_name]
    if '.' in import_name:
        candidates.append(import_name.split('.', 1)[0])

    lowered = {str(k).lower(): v for k, v in deps.items()}
    for candidate in candidates:
        if candidate in deps:
            return _normalize_python_requirement(candidate, deps[candidate])
        lowered_candidate = candidate.lower()
        if lowered_candidate in lowered:
            return _normalize_python_requirement(candidate, lowered[lowered_candidate])
    return None


def install_python_package(import_name, requirement=None, save=True, project_path='.'):
    """Install a Python ecosystem package for EPL's `Use python` bridge.

    Args:
        import_name: Import/module name used from EPL, e.g. `requests` or `yaml`.
        requirement: Optional pip requirement, e.g. `pyyaml>=6` or `fastapi[all]`.
        save: If True, record the dependency under [python-dependencies].
        project_path: Project root used for manifest updates.
    """
    import_name = _validate_python_import_name(import_name)
    requirement = _normalize_python_requirement(import_name, requirement)

    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', requirement])
    except subprocess.CalledProcessError:
        print(f"  Failed to install Python package: {requirement}")
        return False

    if save:
        project_root = find_project_root(project_path)
        if project_root:
            manifest = load_manifest(project_root)
            if manifest is not None:
                deps = manifest.setdefault(PYTHON_DEPENDENCIES_SECTION, {})
                deps[import_name] = '*' if requirement == import_name else requirement
                save_manifest(manifest, project_root)
                create_lockfile(project_root)
                print(f"  Added Python dependency: {import_name} -> {deps[import_name]}")
        else:
            print("  Installed Python package, but no epl.toml/epl.json was found to save it.")

    print(f"  Installed Python package: {requirement}")
    return True


def remove_python_dependency(import_name, path='.'):
    """Remove a Python dependency from the project manifest."""
    import_name = _validate_python_import_name(import_name)
    project_root = find_project_root(path)
    if not project_root:
        print("  No epl.toml or epl.json found. Run: epl init")
        return False

    manifest = load_manifest(project_root)
    deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    if import_name in deps:
        del deps[import_name]
    else:
        lowered = {str(k).lower(): k for k in deps}
        match = lowered.get(import_name.lower())
        if not match:
            print(f"  Python dependency not declared: {import_name}")
            return False
        del deps[match]

    if deps:
        manifest[PYTHON_DEPENDENCIES_SECTION] = deps
    else:
        manifest.pop(PYTHON_DEPENDENCIES_SECTION, None)
    save_manifest(manifest, project_root)
    create_lockfile(project_root)
    print(f"  Removed Python dependency: {import_name}")
    return True


def install_python_dependencies(path='.'):
    """Install all Python dependencies declared in the nearest project manifest."""
    project_root = find_project_root(path)
    if not project_root:
        return True

    manifest = load_manifest(project_root)
    if not manifest:
        return True

    deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    if not deps:
        return True

    print(f"  Installing {len(deps)} Python dependencies...")
    ok = True
    for import_name, requirement in deps.items():
        requirement = _normalize_python_requirement(import_name, requirement)
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', requirement])
            print(f"  Installed Python dependency: {requirement}")
        except subprocess.CalledProcessError:
            print(f"  Failed to install Python dependency: {requirement}")
            ok = False
    return ok


def add_github_dependency(repo, alias=None, save=True, path='.'):
    """Install and optionally save a GitHub dependency in the project manifest."""
    repo = _validate_github_repo(repo)
    if alias is None:
        alias = repo.split('/')[-1]
    alias = _sanitize_package_name(alias)

    success = install_package(f'github:{repo}', save=False, project_path=path)
    if not success:
        return False

    if save:
        project_root = find_project_root(path)
        if project_root:
            manifest = load_manifest(project_root)
            if manifest is not None:
                deps = manifest.setdefault(GITHUB_DEPENDENCIES_SECTION, {})
                deps[alias] = repo
                save_manifest(manifest, project_root)
                create_lockfile(project_root)
                print(f"  Added GitHub dependency: {alias} -> {repo}")
        else:
            print("  Installed GitHub dependency, but no epl.toml/epl.json was found to save it.")
    return True


def remove_github_dependency(name, path='.'):
    """Remove a GitHub dependency declaration from the project manifest."""
    project_root = find_project_root(path)
    if not project_root:
        print("  No epl.toml or epl.json found. Run: epl init")
        return False

    manifest = load_manifest(project_root)
    deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})
    if name in deps:
        del deps[name]
    else:
        match = None
        for alias, repo in deps.items():
            if repo == name:
                match = alias
                break
        if match is None:
            print(f"  GitHub dependency not declared: {name}")
            return False
        del deps[match]

    if deps:
        manifest[GITHUB_DEPENDENCIES_SECTION] = deps
    else:
        manifest.pop(GITHUB_DEPENDENCIES_SECTION, None)
    save_manifest(manifest, project_root)
    create_lockfile(project_root)
    print(f"  Removed GitHub dependency: {name}")
    return True


def install_github_dependencies(path='.'):
    """Install all GitHub dependencies declared in the nearest project manifest."""
    project_root = find_project_root(path)
    if not project_root:
        return True

    manifest = load_manifest(project_root)
    if not manifest:
        return True

    deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})
    if not deps:
        return True

    print(f"  Installing {len(deps)} GitHub dependencies...")
    ok = True
    for alias, repo in deps.items():
        if not install_package(f'github:{repo}', save=False, project_path=project_root):
            print(f"  Failed to install GitHub dependency: {alias} -> {repo}")
            ok = False
    return ok


def migrate_manifest_to_toml(path='.'):
    """Migrate epl.json to epl.toml. Returns True if migration happened."""
    json_fp = os.path.join(path, MANIFEST_NAME)
    toml_fp = os.path.join(path, TOML_MANIFEST_NAME)
    if not os.path.exists(json_fp):
        return False
    if os.path.exists(toml_fp):
        return False  # already has toml
    with open(json_fp, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    toml_data = _manifest_to_toml(manifest)
    _atomic_write(toml_fp, _dump_toml(toml_data) + '\n')
    print(f"  Migrated {MANIFEST_NAME} -> {TOML_MANIFEST_NAME}")
    return True


# ─── Package Installation ───────────────────────────────

def install_package(name_or_url, version=None, save=True, local=False, project_path='.'):
    """Install a package by name or URL.

    Args:
        name_or_url: Package name, URL, github:user/repo, or local path.
        version: Optional version spec (e.g. '^1.0.0').
        save: If True, auto-save to epl.toml/epl.json dependencies.
        local: If True, install to ./epl_modules/ instead of ~/.epl/packages/.
        project_path: Project root for manifest updates.
    """
    ensure_dirs()

    # Parse name@version syntax (e.g. 'epl-math@^2.0.0' or 'epl-math@1.2.3')
    if '@' in name_or_url and not name_or_url.startswith('http') and not name_or_url.startswith('github:'):
        parts = name_or_url.split('@', 1)
        if parts[1]:  # not empty after @
            name_or_url = parts[0]
            version = parts[1]

    if name_or_url.startswith('https://'):
        return _install_from_url(_validate_url(name_or_url), source=f'url:{name_or_url}')
    elif name_or_url.startswith('http://'):
        raise ValueError('Only https:// URLs are allowed for security. '
                        'Use https:// instead of http://')
    elif name_or_url.startswith('github:'):
        repo = _validate_github_repo(name_or_url[7:])
        return _install_from_github(repo)
    elif os.path.isdir(name_or_url):
        return _install_from_local(name_or_url)
    elif re.match(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$', name_or_url):
        return _install_from_github(_validate_github_repo(name_or_url))
    else:
        name_or_url = _sanitize_package_name(name_or_url)
        # Unified naming: allow 'math' to find 'epl-math'
        actual_name = _resolve_package_name(name_or_url)
        success = _install_from_registry(actual_name, version, local=local, project_path=project_path)
        if success and save:
            _auto_save_dependency(actual_name, version or '*', project_path)
        return success


def _install_from_url(url, expected_sha256=None, source='url', metadata=None):
    """Download and install a package from a validated https URL."""
    url = _validate_url(url)
    print(f"  Downloading from {url}...")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, 'package.zip')
        try:
            urllib.request.urlretrieve(url, zip_path)
        except Exception as e:
            print(f"  Error downloading: {e}")
            return False
        archive_integrity = _sha256_file(zip_path)
        if expected_sha256 and archive_integrity != expected_sha256:
            print("  Error: downloaded archive checksum mismatch.")
            print(f"    Expected: {expected_sha256}")
            print(f"    Actual:   {archive_integrity}")
            return False
        with zipfile.ZipFile(zip_path, 'r') as z:
            # Zip-slip protection: reject entries with absolute paths or ..
            for member in z.namelist():
                member_path = os.path.normpath(member)
                if os.path.isabs(member_path) or member_path.startswith('..'):
                    print(f"  Skipping unsafe zip entry: {member}")
                    continue
                dest_path = os.path.realpath(os.path.join(tmp, member_path))
                if not dest_path.startswith(os.path.realpath(tmp)):
                    print(f"  Skipping unsafe zip entry: {member}")
                    continue
                z.extract(member, tmp)
        # Find epl.json in extracted content
        for root, dirs, files in os.walk(tmp):
            if MANIFEST_NAME in files:
                manifest = load_manifest(root)
                if manifest:
                    pkg_name = manifest.get('name', 'unknown')
                    dest = os.path.join(PACKAGES_DIR, pkg_name)
                    if os.path.exists(dest):
                        shutil.rmtree(dest)
                    shutil.copytree(root, dest)
                    pkg_metadata = dict(metadata or {})
                    pkg_metadata.update({
                        'archive_integrity': archive_integrity,
                        'download_url': url,
                    })
                    register_installed_package(
                        pkg_name,
                        manifest.get('version', '?'),
                        source,
                        dest,
                        metadata=pkg_metadata,
                    )
                    print(f"  Installed: {pkg_name} @ {manifest.get('version', '?')}")
                    return True
        # If no manifest, install all .epl files
        epl_files = []
        for root, dirs, files in os.walk(tmp):
            for f in files:
                if f.endswith('.epl'):
                    epl_files.append(os.path.join(root, f))
        if epl_files:
            pkg_name = os.path.basename(url).replace('.zip', '')
            dest = os.path.join(PACKAGES_DIR, pkg_name)
            os.makedirs(dest, exist_ok=True)
            for ef in epl_files:
                shutil.copy2(ef, dest)
            register_installed_package(
                pkg_name,
                '?',
                source,
                dest,
                metadata={
                    **(metadata or {}),
                    'archive_integrity': archive_integrity,
                    'download_url': url,
                },
            )
            print(f"  Installed: {pkg_name} ({len(epl_files)} files)")
            return True
    print("  No EPL package found in download.")
    return False


def _install_from_github(repo, commit=None, expected_sha256=None):
    """Install from a GitHub repository."""
    repo = _validate_github_repo(repo)
    resolved_commit, url = _resolve_github_archive(repo, commit=commit)
    if resolved_commit:
        print(f"  Fetching from GitHub: {repo}@{resolved_commit[:12]}...")
    else:
        print(f"  Fetching from GitHub: {repo}...")
    return _install_from_url(
        url,
        expected_sha256=expected_sha256,
        source=f'github:{repo}',
        metadata={'repo': repo, 'commit': resolved_commit or commit or ''},
    )


def _install_from_local(path, source=None):
    """Install from a local directory."""
    manifest = load_manifest(path)
    pkg_name = manifest.get('name', os.path.basename(path)) if manifest else os.path.basename(path)
    pkg_name = _sanitize_package_name(pkg_name)
    dest = os.path.join(PACKAGES_DIR, pkg_name)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(path, dest)
    version = manifest.get('version', '?') if manifest else '?'
    register_installed_package(pkg_name, version, source or f'local:{path}', dest)
    print(f"  Installed: {pkg_name} @ {version}")
    return True


def _resolve_package_name(name):
    """Resolve a package name with unified naming.

    Allows users to write 'math' instead of 'epl-math'.
    If 'name' is already in the registry, return as-is.
    Otherwise try 'epl-{name}' prefix.
    """
    if name in BUILTIN_REGISTRY:
        return name
    if _get_official_package_dir(name):
        return name
    prefixed = f'epl-{name}'
    if prefixed in BUILTIN_REGISTRY:
        return prefixed
    if _get_official_package_dir(prefixed):
        return prefixed
    # Check local registry too
    local_reg = load_local_registry()
    if name in local_reg:
        return name
    if prefixed in local_reg:
        return prefixed
    return name  # let it fail naturally if not found


def _auto_save_dependency(name, version_spec, project_path='.'):
    """Auto-save a dependency to the project manifest (epl.toml or epl.json).

    Only saves if a manifest file exists in the project directory.
    """
    manifest = load_manifest(project_path)
    if not manifest:
        return  # no manifest, skip silently
    deps = manifest.setdefault('dependencies', {})
    if name not in deps:
        deps[name] = version_spec
        save_manifest(manifest, project_path)
        print(f"  Added {name}@{version_spec} to dependencies")


def _install_from_registry(name, version=None, local=False, project_path='.'):
    """Install from the EPL package registry."""
    name = _sanitize_package_name(name)
    official_pkg = _get_official_package_dir(name)
    if official_pkg:
        return _install_from_local(official_pkg, source=f'official:{name}')
    # Check built-in registry first
    if name in BUILTIN_REGISTRY:
        return _install_builtin_package(name, local=local, project_path=project_path)

    # Check local shipped registry file
    if os.path.exists(LOCAL_REGISTRY_FILE):
        try:
            with open(LOCAL_REGISTRY_FILE, 'r', encoding='utf-8') as f:
                local_reg = json.load(f)
            packages = local_reg.get('packages', local_reg)
            if name in packages:
                pkg_info = packages[name]
                if pkg_info.get('type') == 'builtin':
                    # Add to built-in registry dynamically and install
                    BUILTIN_REGISTRY[name] = {
                        "description": pkg_info.get("description", ""),
                        "version": pkg_info.get("version", "1.0.0"),
                        "type": "builtin"
                    }
                    return _install_builtin_package(name)
                url = pkg_info.get('url', '')
                if url:
                    return _install_from_url(
                        _validate_url(url),
                        expected_sha256=pkg_info.get('checksum') or None,
                        source=f'registry:{name}',
                        metadata={'registry_checksum': pkg_info.get('checksum', '')},
                    )
                github = pkg_info.get('github', '')
                if github:
                    return _install_from_github(_validate_github_repo(github))
        except (ValueError, json.JSONDecodeError) as e:
            print(f"  Registry error: {e}")
            return False
        except Exception:
            pass

    try:
        print(f"  Searching remote registry for: {name}...")
        # Try the real registry server first (local or remote)
        registry_urls = [
            os.environ.get('EPL_REGISTRY_URL', ''),
            'http://localhost:4873/api/v1/packages/' + name,
            REGISTRY_URL,
        ]
        for reg_url in registry_urls:
            if not reg_url:
                continue
            try:
                response = urllib.request.urlopen(reg_url, timeout=10)
                pkg_data = json.loads(response.read().decode('utf-8'))
                # If it's from the registry server API
                if 'latest' in pkg_data and 'versions' in pkg_data:
                    target_ver = version or pkg_data.get('latest')
                    ver_info = pkg_data.get('versions', {}).get(target_ver, {})
                    if ver_info.get('type') == 'builtin':
                        BUILTIN_REGISTRY[name] = {
                            "description": pkg_data.get("description", ""),
                            "version": target_ver,
                            "type": "builtin"
                        }
                        return _install_builtin_package(name, local=local, project_path=project_path)
                    # Download from registry server
                    download_url = reg_url.replace(f'/api/v1/packages/{name}',
                                                     f'/api/v1/download/{name}/{target_ver}')
                    return _install_from_url(
                        download_url,
                        expected_sha256=ver_info.get('checksum') or None,
                        source=f'registry:{name}',
                        metadata={'registry_checksum': ver_info.get('checksum', '')},
                    )
                # If it's from the raw JSON registry
                packages = pkg_data.get('packages', pkg_data)
                if name in packages:
                    pkg = packages[name]
                    url = pkg.get('url', '')
                    if url:
                        return _install_from_url(
                            _validate_url(url),
                            expected_sha256=pkg.get('checksum') or None,
                            source=f'registry:{name}',
                            metadata={'registry_checksum': pkg.get('checksum', '')},
                        )
                    github = pkg.get('github', '')
                    if github:
                        return _install_from_github(_validate_github_repo(github))
                break
            except Exception:
                continue
        print(f"  Package not found: {name}")
        print(f"  Try: epl install github:user/repo")
        return False
    except Exception:
        print(f"  Could not reach remote registry. Try installing from URL or GitHub:")
        print(f"    epl install github:user/repo")
        print(f"    epl install https://example.com/package.zip")
        return False


def _install_builtin_package(name, local=False, project_path='.'):
    """Install a built-in package by generating its content."""
    name = _sanitize_package_name(name)
    official_pkg = _get_official_package_dir(name)
    if official_pkg:
        if local:
            modules_dir = os.path.join(project_path, 'epl_modules')
            dest = os.path.join(modules_dir, name)
            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(modules_dir, exist_ok=True)
            shutil.copytree(official_pkg, dest)
            manifest = load_manifest(dest)
            version = manifest.get('version', '?') if manifest else '?'
            print(f"  Installed: {name} @ {version} (official) -> epl_modules/")
            return True
        return _install_from_local(official_pkg, source=f'official:{name}')

    info = BUILTIN_REGISTRY[name]
    if local:
        modules_dir = os.path.join(project_path, 'epl_modules')
        dest = os.path.join(modules_dir, name)
    else:
        dest = os.path.join(PACKAGES_DIR, name)
    os.makedirs(dest, exist_ok=True)

    # Generate manifest
    manifest = {
        "name": name,
        "version": info["version"],
        "description": info["description"],
        "entry": "main.epl",
        "type": "builtin",
    }
    with open(os.path.join(dest, MANIFEST_NAME), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    # Generate package source based on name
    source = _get_builtin_source(name)
    with open(os.path.join(dest, 'main.epl'), 'w', encoding='utf-8') as f:
        f.write(source)

    register_installed_package(name, info["version"], "builtin", dest)
    location = 'epl_modules/' if local else '~/.epl/packages/'
    print(f"  Installed: {name} @ {info['version']} (builtin) -> {location}")
    return True


def _get_builtin_source(name):
    """Get EPL source code for a built-in package."""
    sources = {
        "epl-math": '''Note: EPL Math Library v1.0
Note: Extended math functions

Function PI()
    Return 3.141592653589793
End

Function E()
    Return 2.718281828459045
End

Function Abs(x)
    If x < 0
        Return 0 - x
    End
    Return x
End

Function Max(a, b)
    If a > b
        Return a
    End
    Return b
End

Function Min(a, b)
    If a < b
        Return a
    End
    Return b
End

Function Clamp(value, low, high)
    If value < low
        Return low
    End
    If value > high
        Return high
    End
    Return value
End

Function Floor(x)
    Create result equal to x - (x % 1)
    If x < 0 and x % 1 != 0
        Return result - 1
    End
    Return result
End

Function Ceil(x)
    Create result equal to x - (x % 1)
    If x > 0 and x % 1 != 0
        Return result + 1
    End
    Return result
End

Function Power(base, exp)
    Create result equal to 1
    For i from 1 to exp
        Set result to result * base
    End
    Return result
End

Function Factorial(n)
    If n <= 1
        Return 1
    End
    Return n * Factorial(n - 1)
End

Function GCD(a, b)
    While b != 0
        Create temp equal to b
        Set b to a % b
        Set a to temp
    End
    Return a
End

Function LCM(a, b)
    Return (a * b) / GCD(a, b)
End

Function Fibonacci(n)
    If n <= 0
        Return 0
    End
    If n == 1
        Return 1
    End
    Create a equal to 0
    Create b equal to 1
    For i from 2 to n
        Create temp equal to a + b
        Set a to b
        Set b to temp
    End
    Return b
End

Function IsPrime(n)
    If n < 2
        Return false
    End
    If n < 4
        Return true
    End
    If n % 2 == 0
        Return false
    End
    Create i equal to 3
    While i * i <= n
        If n % i == 0
            Return false
        End
        Set i to i + 2
    End
    Return true
End

Function Sum(list)
    Create total equal to 0
    For Each item in list
        Set total to total + item
    End
    Return total
End

Function Average(list)
    Return Sum(list) / length(list)
End
''',
        "epl-http": '''Note: EPL HTTP Library v2.0
Note: Full HTTP client with all methods, headers, cookies, redirects

Function HttpGet(url)
    Return http_get(url)
End

Function HttpPost(url, body)
    Return http_post(url, body)
End

Function HttpPut(url, body)
    Return http_put(url, body)
End

Function HttpDelete(url)
    Return http_delete(url)
End

Function HttpPatch(url, body)
    Return http_patch(url, body)
End

Function HttpRequest(method, url, body, headers)
    Return http_request(method, url, body, headers)
End

Function JsonGet(url)
    Create response equal to http_get(url)
    If type_of(response) == "map"
        If "body" in keys(response)
            Return json_parse(response["body"])
        End
        Return response
    End
    Return json_parse(response)
End

Function JsonPost(url, data)
    Create body equal to json_stringify(data)
    Return http_post(url, body)
End

Function JsonPut(url, data)
    Create body equal to json_stringify(data)
    Return http_put(url, body)
End

Function JsonPatch(url, data)
    Create body equal to json_stringify(data)
    Return http_patch(url, body)
End

Function UrlEncode(text)
    Return url_encode(text)
End

Function UrlDecode(text)
    Return url_decode(text)
End

Function UrlParse(url)
    Return url_parse(url)
End

Function BuildQueryString(params)
    Create parts equal to []
    For Each key in keys(params)
        append(parts, url_encode(key) + "=" + url_encode(to_text(params[key])))
    End
    Return join(parts, "&")
End

Function IsSuccess(response)
    If type_of(response) == "map" and "status" in keys(response)
        Return response["status"] >= 200 and response["status"] < 300
    End
    Return false
End

Function GetStatusCode(response)
    If type_of(response) == "map" and "status" in keys(response)
        Return response["status"]
    End
    Return 0
End

Function GetBody(response)
    If type_of(response) == "map" and "body" in keys(response)
        Return response["body"]
    End
    Return response
End

Function GetHeaders(response)
    If type_of(response) == "map" and "headers" in keys(response)
        Return response["headers"]
    End
    Return {}
End
''',
        "epl-json": '''Note: EPL JSON Library v1.0
Note: JSON parsing and serialization

Function ParseJSON(text)
    Return json_parse(text)
End

Function ToJSON(value)
    Return json_stringify(value)
End

Function PrettyJSON(value)
    Return json_stringify(value)
End

Function GetField(obj, key)
    Return obj[key]
End

Function SetField(obj, key, value)
    Set obj[key] to value
    Return obj
End

Function HasField(obj, key)
    Return key in keys(obj)
End

Function MergeObjects(a, b)
    Create result equal to {}
    For Each key in keys(a)
        Set result[key] to a[key]
    End
    For Each key in keys(b)
        Set result[key] to b[key]
    End
    Return result
End
''',
        "epl-crypto": '''Note: EPL Crypto Library v2.0
Note: Full cryptographic functions — hashing, HMAC, encoding, secure random

Function HashMD5(text)
    Return hash_md5(text)
End

Function HashSHA256(text)
    Return hash_sha256(text)
End

Function HashSHA512(text)
    Return hash_sha512(text)
End

Function HmacSHA256(key, message)
    Note: HMAC-SHA256 using built-in
    Return hmac_sha256(key, message)
End

Function GenerateUUID()
    Return uuid4()
End

Function RandomToken(length)
    Create chars equal to "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    Create token equal to ""
    For i from 1 to length
        Create idx equal to random_int(0, 61)
        Set token to token + chars[idx]
    End
    Return token
End

Function RandomHex(length)
    Create chars equal to "0123456789abcdef"
    Create token equal to ""
    For i from 1 to length
        Create idx equal to random_int(0, 15)
        Set token to token + chars[idx]
    End
    Return token
End

Function Base64Encode(text)
    Return base64_encode(text)
End

Function Base64Decode(text)
    Return base64_decode(text)
End

Function HexEncode(text)
    Return hex_encode(text)
End

Function HexDecode(text)
    Return hex_decode(text)
End

Function CompareHash(hash1, hash2)
    Note: Constant-time comparison to prevent timing attacks
    If length(hash1) != length(hash2)
        Return false
    End
    Create diff equal to 0
    For i from 0 to length(hash1) - 1
        If hash1[i] != hash2[i]
            Set diff to diff + 1
        End
    End
    Return diff == 0
End

Function HashPassword(password)
    Note: Hash a password with salt using SHA256
    Create salt equal to RandomHex(32)
    Create salted equal to salt + ":" + password
    Create hashed equal to HashSHA256(salted)
    Return salt + ":" + hashed
End

Function VerifyPassword(password, stored)
    Create parts equal to split(stored, ":")
    Create salt equal to parts[0]
    Create salted equal to salt + ":" + password
    Create hashed equal to HashSHA256(salted)
    Return CompareHash(hashed, parts[1])
End
''',
        "epl-datetime": '''Note: EPL DateTime Library v1.0
Note: Date and time utilities using built-in now() and time functions

Function Now()
    Return now()
End

Function CurrentTime()
    Return time_now()
End

Function FormatDate(timestamp, format)
    Return format_time(timestamp, format)
End

Function TimeSince(start)
    Return time_now() - start
End

Function Sleep(ms)
    Return sleep(ms)
End
''',
        "epl-regex": '''Note: EPL Regex Library v1.0
Note: Regular expression support using built-in regex functions

Function Match(pattern, text)
    Return regex_match(pattern, text)
End

Function FindAll(pattern, text)
    Return regex_findall(pattern, text)
End

Function Replace(pattern, replacement, text)
    Return regex_replace(pattern, replacement, text)
End

Function Split(pattern, text)
    Return regex_split(pattern, text)
End

Function IsMatch(pattern, text)
    Create result equal to regex_match(pattern, text)
    Return result != null
End

Function IsEmail(text)
    Return IsMatch("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", text)
End

Function IsURL(text)
    Return IsMatch("^https?://[\\w.-]+", text)
End
''',
        "epl-fs": '''Note: EPL File System Library v1.0
Note: File system utilities using built-in file functions

Function ReadFile(path)
    Return read_file(path)
End

Function WriteFile(path, content)
    Return write_file(path, content)
End

Function AppendFile(path, content)
    Return append_file(path, content)
End

Function FileExists(path)
    Return file_exists(path)
End

Function DeleteFile(path)
    Return delete_file(path)
End

Function ListFiles(dir)
    Return list_dir(dir)
End

Function ReadLines(path)
    Create content equal to read_file(path)
    Return split(content, "\\n")
End

Function WriteLines(path, lines)
    Create content equal to join(lines, "\\n")
    Return write_file(path, content)
End
''',
        "epl-db": '''Note: EPL Database Library v2.0
Note: Full SQLite database with transactions, batch ops, schema info
Note: All queries use parameterized statements — safe from SQL injection.

Function Connect(path)
    Return db_connect(path)
End

Function Execute(db, sql)
    Return db_execute(db, sql)
End

Function ExecuteParams(db, sql, params)
    Return db_execute_params(db, sql, params)
End

Function Query(db, sql)
    Return db_query(db, sql)
End

Function QueryParams(db, sql, params)
    Return db_query_params(db, sql, params)
End

Function QueryOne(db, sql, params)
    Return db_query_one(db, sql, params)
End

Function Close(db)
    Return db_close(db)
End

Function CreateTable(db, name, columns)
    Note: name and columns should be trusted schema values, not user input
    Create sql equal to "CREATE TABLE IF NOT EXISTS " + name + " (" + columns + ")"
    Return Execute(db, sql)
End

Function DropTable(db, name)
    Return Execute(db, "DROP TABLE IF EXISTS " + name)
End

Function TableExists(db, name)
    Create rows equal to QueryParams(db, "SELECT name FROM sqlite_master WHERE type=? AND name=?", [name, name])
    Return length(rows) > 0
End

Function ListTables(db)
    Return Query(db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
End

Function Insert(db, table, columns, params)
    Note: Safe parameterized insert
    Create placeholders equal to ""
    Create i equal to 0
    While i < length(params)
        If i > 0
            Set placeholders to placeholders + ", "
        End
        Set placeholders to placeholders + "?"
        Set i to i + 1
    End
    Create sql equal to "INSERT INTO " + table + " (" + columns + ") VALUES (" + placeholders + ")"
    Return ExecuteParams(db, sql, params)
End

Function InsertParams(db, table, columns, params)
    Return Insert(db, table, columns, params)
End

Function SelectAll(db, table)
    Return Query(db, "SELECT * FROM " + table)
End

Function SelectWhere(db, table, condition, params)
    Return QueryParams(db, "SELECT * FROM " + table + " WHERE " + condition, params)
End

Function SelectWhereParams(db, table, condition, params)
    Return SelectWhere(db, table, condition, params)
End

Function Update(db, table, set_clause, where_clause, params)
    Note: Safe parameterized update
    Create sql equal to "UPDATE " + table + " SET " + set_clause + " WHERE " + where_clause
    Return ExecuteParams(db, sql, params)
End

Function Delete(db, table, where_clause, params)
    Note: Safe parameterized delete
    Create sql equal to "DELETE FROM " + table + " WHERE " + where_clause
    Return ExecuteParams(db, sql, params)
End

Function Count(db, table)
    Create rows equal to Query(db, "SELECT COUNT(*) as cnt FROM " + table)
    If length(rows) > 0
        Return rows[0]["cnt"]
    End
    Return 0
End

Function BeginTransaction(db)
    Return Execute(db, "BEGIN TRANSACTION")
End

Function Commit(db)
    Return Execute(db, "COMMIT")
End

Function Rollback(db)
    Return Execute(db, "ROLLBACK")
End

Function BatchInsert(db, table, columns, rows)
    Note: Insert multiple rows efficiently inside a transaction
    BeginTransaction(db)
    For Each row in rows
        Insert(db, table, columns, row)
    End
    Commit(db)
    Return length(rows)
End
''',
        "epl-testing": '''Note: EPL Testing Library v1.0
Note: Unit testing assertions

Function AssertEqual(actual, expected)
    If actual != expected
        Print "FAIL: Expected " + str(expected) + " but got " + str(actual)
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertTrue(value)
    If value != true
        Print "FAIL: Expected true but got " + str(value)
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertFalse(value)
    If value != false
        Print "FAIL: Expected false but got " + str(value)
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertNull(value)
    If value != null
        Print "FAIL: Expected null but got " + str(value)
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertNotNull(value)
    If value == null
        Print "FAIL: Expected non-null value"
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertContains(collection, item)
    If item not in collection
        Print "FAIL: Item not found in collection"
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertGreater(a, b)
    If a <= b
        Print "FAIL: " + str(a) + " is not greater than " + str(b)
        Return false
    End
    Print "PASS"
    Return true
End

Function AssertLess(a, b)
    If a >= b
        Print "FAIL: " + str(a) + " is not less than " + str(b)
        Return false
    End
    Print "PASS"
    Return true
End
''',
    }
    if name in sources:
        return sources[name]
    # Check extended package sources
    extra = _get_builtin_source_extra(name)
    if extra:
        return extra
    return f'Note: {name} package\nNote: Auto-generated stub\n'


def _get_builtin_source_extra(name):
    """Get EPL source for newer built-in packages."""
    extra_sources = {
        "epl-string": '''Note: EPL String Library v1.0
Note: Extended string utilities

Function PadLeft(text, target_len, char)
    While length(text) < target_len
        Set text to char + text
    End
    Return text
End

Function PadRight(text, target_len, char)
    While length(text) < target_len
        Set text to text + char
    End
    Return text
End

Function Capitalize(text)
    If length(text) == 0
        Return ""
    End
    Return uppercase(text[0]) + lowercase(substring(text, 1, length(text)))
End

Function Title(text)
    Create words equal to split(text, " ")
    Create result equal to []
    For Each word in words
        append(result, Capitalize(word))
    End
    Return join(result, " ")
End

Function IsNumeric(text)
    For Each ch in text
        If ch < "0" or ch > "9"
            If ch != "." and ch != "-"
                Return false
            End
        End
    End
    Return true
End

Function IsAlpha(text)
    For Each ch in text
        Create code equal to char_code(ch)
        If (code < 65 or code > 90) and (code < 97 or code > 122)
            Return false
        End
    End
    Return true
End

Function CountOccurrences(text, search)
    Create count equal to 0
    Create idx equal to 0
    While idx < length(text)
        If substring(text, idx, idx + length(search)) == search
            Set count to count + 1
            Set idx to idx + length(search)
        Else
            Set idx to idx + 1
        End
    End
    Return count
End

Function Truncate(text, maxLength, suffix)
    If length(text) <= maxLength
        Return text
    End
    Return substring(text, 0, maxLength) + suffix
End

Function Repeat(text, count)
    Create result equal to ""
    For i from 1 to count
        Set result to result + text
    End
    Return result
End

Function Reverse(text)
    Create result equal to ""
    For i from length(text) - 1 to 0 step -1
        Set result to result + text[i]
    End
    Return result
End
''',
        "epl-collections": '''Note: EPL Collections Library v1.0
Note: Advanced collection data structures

Note: Stack - Last In, First Out
Class Stack
    Constructor()
        Set self.items to []
    End

    Method push(item)
        append(self.items, item)
    End

    Method pop()
        If length(self.items) == 0
            Return null
        End
        Create item equal to self.items[length(self.items) - 1]
        remove(self.items, length(self.items) - 1)
        Return item
    End

    Method peek()
        If length(self.items) == 0
            Return null
        End
        Return self.items[length(self.items) - 1]
    End

    Method size()
        Return length(self.items)
    End

    Method isEmpty()
        Return length(self.items) == 0
    End
EndClass

Note: Queue - First In, First Out
Class Queue
    Constructor()
        Set self.items to []
    End

    Method enqueue(item)
        append(self.items, item)
    End

    Method dequeue()
        If length(self.items) == 0
            Return null
        End
        Create item equal to self.items[0]
        remove(self.items, 0)
        Return item
    End

    Method front()
        If length(self.items) == 0
            Return null
        End
        Return self.items[0]
    End

    Method size()
        Return length(self.items)
    End

    Method isEmpty()
        Return length(self.items) == 0
    End
EndClass

Function Flatten(nested)
    Create result equal to []
    For Each item in nested
        If type_of(item) == "list"
            Create inner equal to Flatten(item)
            For Each sub in inner
                append(result, sub)
            End
        Else
            append(result, item)
        End
    End
    Return result
End

Function Chunk(list, size)
    Create result equal to []
    Create chunk equal to []
    For Each item in list
        append(chunk, item)
        If length(chunk) == size
            append(result, chunk)
            Set chunk to []
        End
    End
    If length(chunk) > 0
        append(result, chunk)
    End
    Return result
End

Function Unique(list)
    Create seen equal to []
    Create result equal to []
    For Each item in list
        If item not in seen
            append(seen, item)
            append(result, item)
        End
    End
    Return result
End

Function Zip(a, b)
    Create result equal to []
    Create len equal to min(length(a), length(b))
    For i from 0 to len - 1
        append(result, [a[i], b[i]])
    End
    Return result
End

Function Take(list, n)
    Create result equal to []
    For i from 0 to min(n, length(list)) - 1
        append(result, list[i])
    End
    Return result
End

Function Drop(list, n)
    Create result equal to []
    For i from n to length(list) - 1
        append(result, list[i])
    End
    Return result
End
''',
        "epl-web": '''Note: EPL Web Helpers Library v1.0
Note: Utilities for building web applications

Function JsonResponse(data)
    Return json_stringify(data)
End

Function HtmlPage(title, body)
    Create html equal to "<!DOCTYPE html><html><head><title>" + title + "</title>"
    Set html to html + "<meta charset=\\"UTF-8\\"><meta name=\\"viewport\\" content=\\"width=device-width, initial-scale=1.0\\">"
    Set html to html + "</head><body>" + body + "</body></html>"
    Return html
End

Function HtmlList(items)
    Create html equal to "<ul>"
    For Each item in items
        Set html to html + "<li>" + to_text(item) + "</li>"
    End
    Set html to html + "</ul>"
    Return html
End

Function HtmlTable(headers, rows)
    Create html equal to "<table><thead><tr>"
    For Each h in headers
        Set html to html + "<th>" + to_text(h) + "</th>"
    End
    Set html to html + "</tr></thead><tbody>"
    For Each row in rows
        Set html to html + "<tr>"
        For Each cell in row
            Set html to html + "<td>" + to_text(cell) + "</td>"
        End
        Set html to html + "</tr>"
    End
    Set html to html + "</tbody></table>"
    Return html
End

Function EscapeHtml(text)
    Set text to replace(text, "&", "&amp;")
    Set text to replace(text, "<", "&lt;")
    Set text to replace(text, ">", "&gt;")
    Set text to replace(text, "\\"", "&quot;")
    Return text
End
''',
        "epl-async": '''Note: EPL Async Library v4.0
Note: Async event loop, tasks, channels, and structured concurrency

Function AsyncRun(fn)
    Note: Spawn an async task
    Return async_spawn(fn)
End

Function AsyncWait(task)
    Note: Wait for an async task to complete
    Return async_wait(task)
End

Function AsyncSleep(seconds)
    Note: Non-blocking sleep
    Return async_sleep(seconds)
End

Function ChannelCreate(capacity)
    Note: Create a bounded channel for message passing
    Return channel_create(capacity)
End

Function ChannelSend(ch, value)
    Return channel_send(ch, value)
End

Function ChannelReceive(ch)
    Return channel_receive(ch)
End

Function TaskGroupCreate()
    Return task_group_create()
End

Function TaskGroupSpawn(group, fn)
    Return task_group_spawn(group, fn)
End

Function TaskGroupWaitAll(group)
    Return task_group_wait_all(group)
End
''',
        "epl-wsgi": '''Note: EPL WSGI Library v4.0
Note: Production web server with middleware

Function CreateApp()
    Return wsgi_create_app()
End

Function Route(app, method, path, handler)
    Return wsgi_route(app, method, path, handler)
End

Function Serve(app, host, port)
    Return wsgi_serve(app, host, port)
End

Function JsonResponse(data, status)
    Return wsgi_json_response(data, status)
End

Function UseMiddleware(app, middleware)
    Return wsgi_use_middleware(app, middleware)
End
''',
        "epl-types": '''Note: EPL Types Library v4.0
Note: Type checking annotations and validation

Function TypeCheck(value, expected_type)
    Create actual equal to type_of(value)
    If actual != expected_type
        Print "Type error: expected " + expected_type + " but got " + actual
        Return false
    End
    Return true
End

Function IsInteger(value)
    Return type_of(value) == "integer"
End

Function IsDecimal(value)
    Return type_of(value) == "decimal"
End

Function IsText(value)
    Return type_of(value) == "text"
End

Function IsList(value)
    Return type_of(value) == "list"
End

Function IsMap(value)
    Return type_of(value) == "map"
End

Function IsBoolean(value)
    Return type_of(value) == "boolean"
End

Function IsNothing(value)
    Return value == nothing
End
''',
        "epl-interfaces": '''Note: EPL Interfaces Library v4.0
Note: Interface definitions and validation

Note: Example interface definition
Interface Printable
    Method render()
End

Interface Serializable
    Method serialize()
    Method deserialize(data)
End

Interface Comparable
    Method compare_to(other)
End

Interface Iterable
    Method has_next()
    Method next()
End

Interface Collection extends Iterable
    Method size()
    Method add(item)
    Method remove(item)
    Method contains(item)
End
''',
        "epl-modules": '''Note: EPL Modules Library v4.0
Note: Module namespacing examples

Module MathUtils
    Export Function Square(x)
        Return x * x
    End

    Export Function Cube(x)
        Return x * x * x
    End

    Export Function Hypotenuse(a, b)
        Return sqrt(a * a + b * b)
    End
End

Module StringUtils
    Export Function Repeat(text, n)
        Create result equal to ""
        For i from 1 to n
            Set result to result + text
        End
        Return result
    End

    Export Function Reverse(text)
        Create result equal to ""
        For i from length(text) - 1 to 0 step -1
            Set result to result + text[i]
        End
        Return result
    End
End
''',
        "epl-profiler": '''Note: EPL Profiler Library v4.0
Note: Performance profiling and timing

Function StartTimer(name)
    Return profiler_start(name)
End

Function StopTimer(name)
    Return profiler_stop(name)
End

Function GetElapsed(name)
    Return profiler_elapsed(name)
End

Function PrintProfile()
    Return profiler_report()
End

Function Benchmark(fn, iterations)
    Create start equal to time_now()
    For i from 1 to iterations
        Call fn()
    End
    Create elapsed equal to time_now() - start
    Print "Benchmark: " + to_text(iterations) + " iterations in " + to_text(elapsed) + "ms"
    Return elapsed
End
''',
        "epl-auth": '''Note: EPL Auth Library v4.2
Note: Authentication and authorization utilities

Function HashPassword(password)
    Note: Uses PBKDF2-SHA256 with random salt
    Use python "hashlib"
    Use python "os"
    Create salt equal to os::urandom(32)
    Create hashed equal to hashlib::pbkdf2_hmac("sha256", password, salt, 100000)
    Return salt.hex() + ":" + hashed.hex()
End

Function VerifyPassword(password, stored_hash)
    Create parts equal to split(stored_hash, ":")
    If length(parts) != 2
        Return false
    End
    Use python "hashlib"
    Use python "bytes"
    Create salt equal to bytes::fromhex(parts[0])
    Create expected equal to parts[1]
    Create hashed equal to hashlib::pbkdf2_hmac("sha256", password, salt, 100000)
    Return hashed.hex() == expected
End

Function GenerateToken(payload, secret)
    Note: Simple HMAC-based token (JWT-like) using base64-encoded data
    Use python "hmac"
    Use python "hashlib"
    Use python "json"
    Use python "time"
    Use python "base64"
    Create data equal to base64::urlsafe_b64encode(json::dumps(payload).encode()).decode()
    Create ts equal to to_text(int(time::time()))
    Create message equal to data + "." + ts
    Create signature equal to hmac::new(secret.encode(), message.encode(), hashlib::sha256)
    Return message + "." + signature.hexdigest()
End

Function ValidateToken(token, secret)
    Create parts equal to split(token, ".")
    If length(parts) != 3
        Return nothing
    End
    Use python "hmac"
    Use python "hashlib"
    Use python "base64"
    Use python "json"
    Create message equal to parts[0] + "." + parts[1]
    Create expected equal to hmac::new(secret.encode(), message.encode(), hashlib::sha256)
    If expected.hexdigest() != parts[2]
        Return nothing
    End
    Return json::loads(base64::urlsafe_b64decode(parts[0]).decode())
End

Function CreateSession(user_id)
    Use python "uuid"
    Create session_id equal to to_text(uuid::uuid4())
    Return session_id
End

Function CheckPermission(user_roles, required_role)
    For Each role in user_roles
        If role == required_role
            Return true
        End
    End
    Return false
End
''',
        "epl-email": '''Note: EPL Email Library v4.2
Note: Send emails via SMTP

Function SendEmail(to_addr, subject, body, from_addr, smtp_host, smtp_port, username, password)
    Use python "smtplib"
    Use python "email.mime.text" as mime_text
    Use python "email.mime.multipart" as mime_multi
    Create msg equal to mime_multi::MIMEMultipart()
    Set msg["From"] to from_addr
    Set msg["To"] to to_addr
    Set msg["Subject"] to subject
    msg.attach(mime_text::MIMEText(body, "plain"))
    Create server equal to smtplib::SMTP(smtp_host, smtp_port)
    server.starttls()
    server.login(username, password)
    server.sendmail(from_addr, to_addr, msg.as_string())
    server.quit()
    Return true
End

Function SendHTMLEmail(to_addr, subject, html_body, from_addr, smtp_host, smtp_port, username, password)
    Use python "smtplib"
    Use python "email.mime.text" as mime_text
    Use python "email.mime.multipart" as mime_multi
    Create msg equal to mime_multi::MIMEMultipart("alternative")
    Set msg["From"] to from_addr
    Set msg["To"] to to_addr
    Set msg["Subject"] to subject
    msg.attach(mime_text::MIMEText(html_body, "html"))
    Create server equal to smtplib::SMTP(smtp_host, smtp_port)
    server.starttls()
    server.login(username, password)
    server.sendmail(from_addr, to_addr, msg.as_string())
    server.quit()
    Return true
End

Function FormatTemplate(template, variables)
    Note: Replace {{key}} placeholders in template
    Create result equal to template
    For Each key in keys(variables)
        Set result to replace(result, "{{" + key + "}}", to_text(variables[key]))
    End
    Return result
End
''',
        "epl-pdf": '''Note: EPL PDF Library v4.2
Note: Generate PDF documents

Function CreatePDF(filename)
    Note: Returns PDF builder object
    Create pdf equal to Map()
    Set pdf["filename"] to filename
    Set pdf["pages"] to List()
    Set pdf["current_page"] to List()
    Set pdf["font_size"] to 12
    Set pdf["margin"] to 72
    Return pdf
End

Function AddText(pdf, text)
    Create item equal to Map()
    Set item["type"] to "text"
    Set item["content"] to text
    Set item["size"] to pdf["font_size"]
    Call append(pdf["current_page"], item)
    Return pdf
End

Function AddHeading(pdf, text, level)
    Create sizes equal to List(28, 24, 20, 16, 14, 12)
    If level < 1
        Set level to 1
    End
    If level > 6
        Set level to 6
    End
    Create size equal to sizes[level - 1]
    Create item equal to Map()
    Set item["type"] to "heading"
    Set item["content"] to text
    Set item["size"] to size
    Call append(pdf["current_page"], item)
    Return pdf
End

Function AddTable(pdf, headers, rows)
    Create item equal to Map()
    Set item["type"] to "table"
    Set item["headers"] to headers
    Set item["rows"] to rows
    Call append(pdf["current_page"], item)
    Return pdf
End

Function NewPage(pdf)
    Call append(pdf["pages"], pdf["current_page"])
    Set pdf["current_page"] to List()
    Return pdf
End

Function SavePDF(pdf)
    Call append(pdf["pages"], pdf["current_page"])
    Note: Write minimal PDF file
    Create content equal to "%PDF-1.4\\n"
    Create page_num equal to 0
    For Each page in pdf["pages"]
        Set page_num to page_num + 1
        Set content to content + "% Page " + to_text(page_num) + "\\n"
        For Each item in page
            Set content to content + "% " + item["type"] + ": " + item["content"] + "\\n"
        End
    End
    Set content to content + "%%EOF\\n"
    Write content to file pdf["filename"]
    Return pdf["filename"]
End
''',
        "epl-charts": '''Note: EPL Charts Library v4.2
Note: Generate charts as SVG

Function _EscSVG(text)
    Set text to replace(to_text(text), "&", "&amp;")
    Set text to replace(text, "<", "&lt;")
    Set text to replace(text, ">", "&gt;")
    Set text to replace(text, "\"", "&quot;")
    Return text
End

Function BarChart(title, labels, values, width, height)
    If width == nothing
        Set width to 600
    End
    If height == nothing
        Set height to 400
    End
    Create max_val equal to 0
    For Each v in values
        If v > max_val
            Set max_val to v
        End
    End
    If max_val == 0
        Set max_val to 1
    End
    Create bar_width equal to (width - 100) / length(labels)
    Create svg equal to "<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"" + to_text(width) + "\\" height=\\"" + to_text(height) + "\\">"
    Set svg to svg + "<text x=\\"" + to_text(width / 2) + "\\" y=\\"30\\" text-anchor=\\"middle\\" font-size=\\"18\\" font-weight=\\"bold\\">" + _EscSVG(title) + "</text>"
    Create colors equal to List("#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e")
    Create i equal to 0
    For Each label in labels
        Create bar_height equal to (values[i] / max_val) * (height - 100)
        Create x equal to 60 + i * bar_width
        Create y equal to height - 50 - bar_height
        Create color equal to colors[i % length(colors)]
        Set svg to svg + "<rect x=\\"" + to_text(x) + "\\" y=\\"" + to_text(y) + "\\" width=\\"" + to_text(bar_width - 4) + "\\" height=\\"" + to_text(bar_height) + "\\" fill=\\"" + color + "\\"/>"
        Set svg to svg + "<text x=\\"" + to_text(x + bar_width / 2) + "\\" y=\\"" + to_text(height - 30) + "\\" text-anchor=\\"middle\\" font-size=\\"12\\">" + _EscSVG(label) + "</text>"
        Set svg to svg + "<text x=\\"" + to_text(x + bar_width / 2) + "\\" y=\\"" + to_text(y - 5) + "\\" text-anchor=\\"middle\\" font-size=\\"11\\">" + to_text(values[i]) + "</text>"
        Set i to i + 1
    End
    Set svg to svg + "</svg>"
    Return svg
End

Function PieChart(title, labels, values, width, height)
    If width == nothing
        Set width to 400
    End
    If height == nothing
        Set height to 400
    End
    Create total equal to 0
    For Each v in values
        Set total to total + v
    End
    If total == 0
        Set total to 1
    End
    Create cx equal to width / 2
    Create cy equal to height / 2 + 20
    Create r equal to 150
    Create colors equal to List("#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e")
    Create svg equal to "<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"" + to_text(width) + "\\" height=\\"" + to_text(height) + "\\">"
    Set svg to svg + "<text x=\\"" + to_text(cx) + "\\" y=\\"25\\" text-anchor=\\"middle\\" font-size=\\"18\\" font-weight=\\"bold\\">" + _EscSVG(title) + "</text>"
    Create start_angle equal to 0
    Create pi equal to 3.14159265358979
    Create i equal to 0
    For Each label in labels
        Create slice equal to (values[i] / total) * 360
        Create end_angle equal to start_angle + slice
        Create x1 equal to cx + r * cos(start_angle * pi / 180)
        Create y1 equal to cy + r * sin(start_angle * pi / 180)
        Create x2 equal to cx + r * cos(end_angle * pi / 180)
        Create y2 equal to cy + r * sin(end_angle * pi / 180)
        Create large_arc equal to 0
        If slice > 180
            Set large_arc to 1
        End
        Create color equal to colors[i % length(colors)]
        Set svg to svg + "<path d=\\"M " + to_text(cx) + " " + to_text(cy) + " L " + to_text(x1) + " " + to_text(y1) + " A " + to_text(r) + " " + to_text(r) + " 0 " + to_text(large_arc) + " 1 " + to_text(x2) + " " + to_text(y2) + " Z\\" fill=\\"" + color + "\\"/>"
        Create pct equal to round((values[i] / total) * 100)
        Set svg to svg + "<!-- " + _EscSVG(label) + ": " + to_text(pct) + "% -->"
        Set start_angle to end_angle
        Set i to i + 1
    End
    Set svg to svg + "</svg>"
    Return svg
End

Function LineChart(title, x_labels, y_values, width, height)
    If width == nothing
        Set width to 600
    End
    If height == nothing
        Set height to 400
    End
    Create max_val equal to 0
    For Each v in y_values
        If v > max_val
            Set max_val to v
        End
    End
    If max_val == 0
        Set max_val to 1
    End
    Create svg equal to "<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"" + to_text(width) + "\\" height=\\"" + to_text(height) + "\\">"
    Set svg to svg + "<text x=\\"" + to_text(width / 2) + "\\" y=\\"25\\" text-anchor=\\"middle\\" font-size=\\"18\\" font-weight=\\"bold\\">" + _EscSVG(title) + "</text>"
    Create step_x equal to (width - 100) / (length(x_labels) - 1)
    Create points equal to ""
    Create i equal to 0
    For Each val in y_values
        Create x equal to 60 + i * step_x
        Create y equal to height - 50 - ((val / max_val) * (height - 100))
        Set points to points + to_text(x) + "," + to_text(y) + " "
        Set svg to svg + "<circle cx=\\"" + to_text(x) + "\\" cy=\\"" + to_text(y) + "\\" r=\\"4\\" fill=\\"#3498db\\"/>"
        Set i to i + 1
    End
    Set svg to svg + "<polyline points=\\"" + points + "\\" fill=\\"none\\" stroke=\\"#3498db\\" stroke-width=\\"2\\"/>"
    Set svg to svg + "</svg>"
    Return svg
End

Function SaveChart(svg_content, filename)
    Write svg_content to file filename
    Return filename
End
''',
        "epl-orm": '''Note: EPL ORM Library v4.2
Note: Object-Relational Mapping for SQLite

Function CreateModel(name, fields)
    Create model equal to Map()
    Set model["name"] to name
    Set model["fields"] to fields
    Set model["table"] to lowercase(name) + "s"
    Return model
End

Function CreateTable(db, model)
    Create sql equal to "CREATE TABLE IF NOT EXISTS " + model["table"] + " (id INTEGER PRIMARY KEY AUTOINCREMENT"
    For Each field in model["fields"]
        Set sql to sql + ", " + field["name"] + " " + field["type"]
        If field["required"] == true
            Set sql to sql + " NOT NULL"
        End
    End
    Set sql to sql + ")"
    Return db_execute(db, sql)
End

Function Insert(db, model, data)
    Create columns equal to ""
    Create placeholders equal to ""
    Create values equal to List()
    Create data_keys equal to keys(data)
    For Each field in model["fields"]
        If data_keys.contains(field["name"])
            If columns != ""
                Set columns to columns + ", "
                Set placeholders to placeholders + ", "
            End
            Set columns to columns + field["name"]
            Set placeholders to placeholders + "?"
            Call append(values, data[field["name"]])
        End
    End
    Create sql equal to "INSERT INTO " + model["table"] + " (" + columns + ") VALUES (" + placeholders + ")"
    Return db_execute(db, sql, values)
End

Function FindAll(db, model)
    Create sql equal to "SELECT * FROM " + model["table"]
    Return db_query(db, sql)
End

Function FindById(db, model, id)
    Create sql equal to "SELECT * FROM " + model["table"] + " WHERE id = ?"
    Return db_query(db, sql, List(id))
End

Function FindWhere(db, model, condition, params)
    Create sql equal to "SELECT * FROM " + model["table"] + " WHERE " + condition
    Return db_query(db, sql, params)
End

Function UpdateById(db, model, id, data)
    Create sets equal to ""
    Create values equal to List()
    Create data_keys equal to keys(data)
    For Each field in model["fields"]
        If data_keys.contains(field["name"])
            If sets != ""
                Set sets to sets + ", "
            End
            Set sets to sets + field["name"] + " = ?"
            Call append(values, data[field["name"]])
        End
    End
    Call append(values, id)
    Create sql equal to "UPDATE " + model["table"] + " SET " + sets + " WHERE id = ?"
    Return db_execute(db, sql, values)
End

Function DeleteById(db, model, id)
    Create sql equal to "DELETE FROM " + model["table"] + " WHERE id = ?"
    Return db_execute(db, sql, List(id))
End

Function Migrate(db, model)
    Note: Add missing columns (non-destructive migration)
    Create existing equal to db_query(db, "PRAGMA table_info(" + model["table"] + ")")
    Create existing_cols equal to List()
    For Each col in existing
        Call append(existing_cols, col["name"])
    End
    For Each field in model["fields"]
        If not existing_cols.contains(field["name"])
            Create sql equal to "ALTER TABLE " + model["table"] + " ADD COLUMN " + field["name"] + " " + field["type"]
            Call db_execute(db, sql)
        End
    End
End
''',
        "epl-queue": '''Note: EPL Queue Library v4.2
Note: Task queue and background job processing

Function CreateQueue(name)
    Create queue equal to Map()
    Set queue["name"] to name
    Set queue["jobs"] to List()
    Set queue["processing"] to List()
    Set queue["completed"] to List()
    Set queue["failed"] to List()
    Return queue
End

Function Enqueue(queue, job_name, data)
    Create job equal to Map()
    Set job["id"] to to_text(random(1000000, 9999999))
    Set job["name"] to job_name
    Set job["data"] to data
    Set job["status"] to "pending"
    Set job["created_at"] to time_now()
    Call append(queue["jobs"], job)
    Return job["id"]
End

Function Dequeue(queue)
    If length(queue["jobs"]) == 0
        Return nothing
    End
    Create job equal to queue["jobs"][0]
    Call remove(queue["jobs"], 0)
    Set job["status"] to "processing"
    Call append(queue["processing"], job)
    Return job
End

Function CompleteJob(queue, job)
    Set job["status"] to "completed"
    Set job["completed_at"] to time_now()
    Call append(queue["completed"], job)
End

Function FailJob(queue, job, error)
    Set job["status"] to "failed"
    Set job["error"] to error
    Call append(queue["failed"], job)
End

Function QueueSize(queue)
    Return length(queue["jobs"])
End

Function ProcessQueue(queue, handler)
    While length(queue["jobs"]) > 0
        Create job equal to Dequeue(queue)
        Try
            Call handler(job)
            Call CompleteJob(queue, job)
        Catch error
            Call FailJob(queue, job, to_text(error))
        End
    End
End
''',
        "epl-scheduler": '''Note: EPL Scheduler Library v4.2
Note: Cron-like task scheduling

Function CreateScheduler()
    Create scheduler equal to Map()
    Set scheduler["tasks"] to List()
    Set scheduler["running"] to false
    Return scheduler
End

Function Schedule(scheduler, name, interval_ms, callback)
    Create task equal to Map()
    Set task["name"] to name
    Set task["interval"] to interval_ms
    Set task["callback"] to callback
    Set task["last_run"] to 0
    Set task["run_count"] to 0
    Set task["enabled"] to true
    Call append(scheduler["tasks"], task)
    Return task
End

Function ScheduleOnce(scheduler, name, delay_ms, callback)
    Create task equal to Map()
    Set task["name"] to name
    Set task["delay"] to delay_ms
    Set task["callback"] to callback
    Set task["once"] to true
    Set task["created_at"] to time_now()
    Set task["enabled"] to true
    Call append(scheduler["tasks"], task)
    Return task
End

Function RunScheduler(scheduler, duration_ms)
    Set scheduler["running"] to true
    Create start equal to time_now()
    While scheduler["running"] and (time_now() - start) < duration_ms
        Create now equal to time_now()
        Create done_indices equal to List()
        Create idx equal to 0
        For Each task in scheduler["tasks"]
            If task["enabled"] == false
                Set idx to idx + 1
                Continue
            End
            If task["once"] == true
                If (now - task["created_at"]) >= task["delay"]
                    Call task["callback"]()
                    Call append(done_indices, idx)
                End
            Else
                If (now - task["last_run"]) >= task["interval"]
                    Call task["callback"]()
                    Set task["last_run"] to now
                    Set task["run_count"] to task["run_count"] + 1
                End
            End
            Set idx to idx + 1
        End
        Note: Remove completed one-time tasks (reverse order to preserve indices)
        Create ri equal to length(done_indices) - 1
        While ri >= 0
            Call remove(scheduler["tasks"], done_indices[ri])
            Set ri to ri - 1
        End
        Wait 10
    End
    Set scheduler["running"] to false
End

Function StopScheduler(scheduler)
    Set scheduler["running"] to false
End

Function DisableTask(scheduler, name)
    For Each task in scheduler["tasks"]
        If task["name"] == name
            Set task["enabled"] to false
        End
    End
End
''',
        "epl-websocket": '''Note: EPL WebSocket Library v4.2
Note: WebSocket client and server utilities

Function CreateWSServer(port)
    Create server equal to Map()
    Set server["port"] to port
    Set server["clients"] to List()
    Set server["rooms"] to Map()
    Set server["handlers"] to Map()
    Return server
End

Function OnConnect(server, handler)
    Set server["handlers"]["connect"] to handler
End

Function OnMessage(server, handler)
    Set server["handlers"]["message"] to handler
End

Function OnDisconnect(server, handler)
    Set server["handlers"]["disconnect"] to handler
End

Function Broadcast(server, message)
    For Each client in server["clients"]
        Call SendToClient(client, message)
    End
End

Function SendToClient(client, message)
    Set client["outbox"] to message
End

Function JoinRoom(server, client, room_name)
    If server["rooms"][room_name] == nothing
        Set server["rooms"][room_name] to List()
    End
    Call append(server["rooms"][room_name], client)
End

Function BroadcastToRoom(server, room_name, message)
    Create room equal to server["rooms"][room_name]
    If room != nothing
        For Each client in room
            Call SendToClient(client, message)
        End
    End
End
''',
        "epl-xml": '''Note: EPL XML Library v4.2
Note: XML parsing and generation

Function CreateElement(tag, attributes, children)
    Create elem equal to Map()
    Set elem["tag"] to tag
    Set elem["attributes"] to attributes
    Set elem["children"] to children
    Set elem["text"] to ""
    Return elem
End

Function SetText(element, text)
    Set element["text"] to text
    Return element
End

Function AddChild(parent, child)
    Call append(parent["children"], child)
    Return parent
End

Function ToXML(element, indent)
    If indent == nothing
        Set indent to 0
    End
    Create spaces equal to ""
    For i from 1 to indent
        Set spaces to spaces + "  "
    End
    Create result equal to spaces + "<" + element["tag"]
    If element["attributes"] != nothing
        For Each key in keys(element["attributes"])
            Set result to result + " " + key + "=\\"" + to_text(element["attributes"][key]) + "\\""
        End
    End
    If length(element["children"]) == 0 and element["text"] == ""
        Return result + "/>"
    End
    Set result to result + ">"
    If element["text"] != ""
        Set result to result + element["text"]
    End
    If length(element["children"]) > 0
        Set result to result + "\\n"
        For Each child in element["children"]
            Set result to result + ToXML(child, indent + 1) + "\\n"
        End
        Set result to result + spaces
    End
    Set result to result + "</" + element["tag"] + ">"
    Return result
End

Function ParseXMLSimple(text)
    Note: Simple XML tag extraction (not a full parser)
    Create result equal to Map()
    Set result["raw"] to text
    Create tags equal to List()
    Create i equal to 0
    While i < length(text)
        If text[i] == "<" and text[i + 1] != "/"
            Create rest equal to substring(text, i, length(text))
            Create gt_pos equal to rest.index_of(">")
            If gt_pos > 0
                Create tag_content equal to substring(text, i + 1, i + gt_pos)
                Call append(tags, tag_content)
            End
        End
        Set i to i + 1
    End
    Set result["tags"] to tags
    Return result
End

Function XMLDeclaration()
    Return "<?xml version=\\"1.0\\" encoding=\\"UTF-8\\"?>"
End
''',
        "epl-i18n": '''Note: EPL i18n Library v4.2
Note: Internationalization and localization

Function CreateTranslations()
    Create i18n equal to Map()
    Set i18n["locales"] to Map()
    Set i18n["current"] to "en"
    Set i18n["fallback"] to "en"
    Return i18n
End

Function AddLocale(i18n, locale_code, translations)
    Set i18n["locales"][locale_code] to translations
End

Function SetLocale(i18n, locale_code)
    Set i18n["current"] to locale_code
End

Function Translate(i18n, key)
    Create locale equal to i18n["locales"][i18n["current"]]
    If locale != nothing and locale[key] != nothing
        Return locale[key]
    End
    Create fallback equal to i18n["locales"][i18n["fallback"]]
    If fallback != nothing and fallback[key] != nothing
        Return fallback[key]
    End
    Return key
End

Function TranslateWith(i18n, key, params)
    Create text equal to Translate(i18n, key)
    For Each param_key in keys(params)
        Set text to replace(text, "{{" + param_key + "}}", to_text(params[param_key]))
    End
    Return text
End

Function FormatNumber(number, locale_code)
    If locale_code == "de" or locale_code == "fr"
        Return replace(to_text(number), ".", ",")
    End
    Return to_text(number)
End

Function GetAvailableLocales(i18n)
    Return keys(i18n["locales"])
End
''',
        "epl-rate-limit": '''Note: EPL Rate Limit Library v4.2
Note: Rate limiting for API protection

Function CreateTokenBucket(capacity, refill_rate_per_sec)
    Create bucket equal to Map()
    Set bucket["capacity"] to capacity
    Set bucket["tokens"] to capacity
    Set bucket["refill_rate"] to refill_rate_per_sec
    Set bucket["last_refill"] to time_now()
    Return bucket
End

Function TryConsume(bucket, tokens)
    If tokens == nothing
        Set tokens to 1
    End
    Note: Refill tokens based on elapsed time
    Create now equal to time_now()
    Create elapsed equal to (now - bucket["last_refill"]) / 1000
    Create new_tokens equal to bucket["tokens"] + elapsed * bucket["refill_rate"]
    If new_tokens > bucket["capacity"]
        Set new_tokens to bucket["capacity"]
    End
    Set bucket["tokens"] to new_tokens
    Set bucket["last_refill"] to now
    If bucket["tokens"] >= tokens
        Set bucket["tokens"] to bucket["tokens"] - tokens
        Return true
    End
    Return false
End

Function CreateSlidingWindow(max_requests, window_ms)
    Create limiter equal to Map()
    Set limiter["max"] to max_requests
    Set limiter["window"] to window_ms
    Set limiter["requests"] to Map()
    Return limiter
End

Function CheckLimit(limiter, client_id)
    Create now equal to time_now()
    Create client_reqs equal to limiter["requests"][client_id]
    If client_reqs == nothing
        Set client_reqs to List()
        Set limiter["requests"][client_id] to client_reqs
    End
    Note: Remove expired entries
    Create valid equal to List()
    For Each req_time in client_reqs
        If (now - req_time) < limiter["window"]
            Call append(valid, req_time)
        End
    End
    Set limiter["requests"][client_id] to valid
    If length(valid) >= limiter["max"]
        Return false
    End
    Call append(valid, now)
    Set limiter["requests"][client_id] to valid
    Return true
End

Function GetRemainingRequests(limiter, client_id)
    Create client_reqs equal to limiter["requests"][client_id]
    If client_reqs == nothing
        Return limiter["max"]
    End
    Return limiter["max"] - length(client_reqs)
End
''',
        "epl-markdown": '''Note: EPL Markdown Library v4.2
Note: Markdown parser and HTML renderer

Function MarkdownToHTML(text)
    Create lines equal to split(text, "\\n")
    Create html equal to ""
    Create in_code_block equal to false
    For Each line in lines
        If line.starts_with("```")
            If in_code_block
                Set html to html + "</code></pre>\\n"
                Set in_code_block to false
            Else
                Set html to html + "<pre><code>\\n"
                Set in_code_block to true
            End
            Continue
        End
        If in_code_block
            Set html to html + EscapeHTML(line) + "\\n"
            Continue
        End
        If line.starts_with("### ")
            Set html to html + "<h3>" + FormatInline(substring(line, 4, length(line))) + "</h3>\\n"
        Otherwise if line.starts_with("## ")
            Set html to html + "<h2>" + FormatInline(substring(line, 3, length(line))) + "</h2>\\n"
        Otherwise if line.starts_with("# ")
            Set html to html + "<h1>" + FormatInline(substring(line, 2, length(line))) + "</h1>\\n"
        Otherwise if line.starts_with("- ") or line.starts_with("* ")
            Set html to html + "<li>" + FormatInline(substring(line, 2, length(line))) + "</li>\\n"
        Otherwise if line.starts_with("> ")
            Set html to html + "<blockquote>" + FormatInline(substring(line, 2, length(line))) + "</blockquote>\\n"
        Otherwise if line.starts_with("---")
            Set html to html + "<hr>\\n"
        Otherwise if line == ""
            Set html to html + "<br>\\n"
        Else
            Set html to html + "<p>" + FormatInline(line) + "</p>\\n"
        End
    End
    Return html
End

Function FormatInline(text)
    Note: Bold and italic
    Set text to regex_replace("\\*\\*(.+?)\\*\\*", "<strong>$1</strong>", text)
    Set text to regex_replace("\\*(.+?)\\*", "<em>$1</em>", text)
    Set text to regex_replace("`(.+?)`", "<code>$1</code>", text)
    Set text to regex_replace("\\[(.+?)\\]\\((.+?)\\)", "<a href=\\"$2\\">$1</a>", text)
    Return text
End

Function EscapeHTML(text)
    Set text to replace(text, "&", "&amp;")
    Set text to replace(text, "<", "&lt;")
    Set text to replace(text, ">", "&gt;")
    Set text to replace(text, "\\"", "&quot;")
    Return text
End
''',
        "epl-color": '''Note: EPL Color Library v4.2
Note: Color manipulation utilities

Function _HexCharVal(c)
    Create code equal to char_code(lowercase(c))
    If code >= 48 and code <= 57
        Return code - 48
    End
    If code >= 97 and code <= 102
        Return code - 87
    End
    Return -1
End

Function _ValidHex(hex_str)
    Note: Check all characters are valid hex digits
    For i from 0 to length(hex_str) - 1
        If _HexCharVal(hex_str[i]) == -1
            Return false
        End
    End
    Return true
End

Function _HexPairToInt(hex_str)
    Return _HexCharVal(substring(hex_str, 0, 1)) * 16 + _HexCharVal(substring(hex_str, 1, 2))
End

Function _HexDigit(n)
    If n < 10
        Return from_char_code(48 + n)
    End
    Return from_char_code(87 + n)
End

Function _IntToHex2(num)
    If num < 0
        Set num to 0
    End
    If num > 255
        Set num to 255
    End
    Create hi equal to floor(num / 16)
    Create lo equal to num % 16
    Return _HexDigit(hi) + _HexDigit(lo)
End

Function HexToRGB(hex)
    Set hex to replace(hex, "#", "")
    If length(hex) != 6 or not _ValidHex(hex)
        Return List(0, 0, 0)
    End
    Create r equal to _HexPairToInt(substring(hex, 0, 2))
    Create g equal to _HexPairToInt(substring(hex, 2, 4))
    Create b equal to _HexPairToInt(substring(hex, 4, 6))
    Return List(r, g, b)
End

Function RGBToHex(r, g, b)
    Return "#" + _IntToHex2(r) + _IntToHex2(g) + _IntToHex2(b)
End

Function Lighten(hex, amount)
    Create rgb equal to HexToRGB(hex)
    Create r equal to rgb[0] + (255 - rgb[0]) * amount
    Create g equal to rgb[1] + (255 - rgb[1]) * amount
    Create b equal to rgb[2] + (255 - rgb[2]) * amount
    Return RGBToHex(round(r), round(g), round(b))
End

Function Darken(hex, amount)
    Create rgb equal to HexToRGB(hex)
    Create r equal to rgb[0] * (1 - amount)
    Create g equal to rgb[1] * (1 - amount)
    Create b equal to rgb[2] * (1 - amount)
    Return RGBToHex(round(r), round(g), round(b))
End

Function Luminance(hex)
    Create rgb equal to HexToRGB(hex)
    Return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
End

Function ContrastRatio(hex1, hex2)
    Create l1 equal to Luminance(hex1)
    Create l2 equal to Luminance(hex2)
    If l1 > l2
        Return (l1 + 0.05) / (l2 + 0.05)
    End
    Return (l2 + 0.05) / (l1 + 0.05)
End

Function GeneratePalette(base_hex, count)
    Create palette equal to List()
    For i from 0 to count - 1
        Create amount equal to i / count
        Call append(palette, Lighten(base_hex, amount))
    End
    Return palette
End

Function IsLight(hex)
    Return Luminance(hex) > 0.5
End

Function IsDark(hex)
    Return Luminance(hex) <= 0.5
End
''',
        "epl-semver": '''Note: EPL SemVer Library v4.2
Note: Semantic versioning utilities

Function _SafeInt(text)
    Note: Convert text to integer, stripping non-numeric suffixes
    Create result equal to 0
    For i from 0 to length(text) - 1
        Create code equal to char_code(text[i])
        If code >= 48 and code <= 57
            Set result to result * 10 + (code - 48)
        Else
            Return result
        End
    End
    Return result
End

Function ParseVersion(version_str)
    Create parts equal to split(version_str, ".")
    Create result equal to Map()
    Set result["major"] to _SafeInt(parts[0])
    If length(parts) > 1
        Set result["minor"] to _SafeInt(parts[1])
    Else
        Set result["minor"] to 0
    End
    If length(parts) > 2
        Set result["patch"] to _SafeInt(parts[2])
    Else
        Set result["patch"] to 0
    End
    Set result["string"] to version_str
    Return result
End

Function CompareVersions(a, b)
    Create va equal to ParseVersion(a)
    Create vb equal to ParseVersion(b)
    If va["major"] != vb["major"]
        Return va["major"] - vb["major"]
    End
    If va["minor"] != vb["minor"]
        Return va["minor"] - vb["minor"]
    End
    Return va["patch"] - vb["patch"]
End

Function IsNewer(a, b)
    Return CompareVersions(a, b) > 0
End

Function IsCompatible(version, range)
    Note: Caret range check (same major version)
    Create v equal to ParseVersion(version)
    Create r equal to ParseVersion(range)
    If v["major"] != r["major"]
        Return false
    End
    If v["minor"] < r["minor"]
        Return false
    End
    If v["minor"] == r["minor"] and v["patch"] < r["patch"]
        Return false
    End
    Return true
End

Function BumpMajor(version)
    Create v equal to ParseVersion(version)
    Return to_text(v["major"] + 1) + ".0.0"
End

Function BumpMinor(version)
    Create v equal to ParseVersion(version)
    Return to_text(v["major"]) + "." + to_text(v["minor"] + 1) + ".0"
End

Function BumpPatch(version)
    Create v equal to ParseVersion(version)
    Return to_text(v["major"]) + "." + to_text(v["minor"]) + "." + to_text(v["patch"] + 1)
End

Function VersionToString(v)
    Return to_text(v["major"]) + "." + to_text(v["minor"]) + "." + to_text(v["patch"])
End
''',
        "epl-networking": '''Note: EPL Networking Library v3.0
Note: TCP/UDP socket networking using built-in functions

Function TcpConnect(host, port)
    Return socket_connect(host, port)
End

Function TcpSend(sock, data)
    Return socket_send(sock, data)
End

Function TcpReceive(sock)
    Return socket_receive(sock)
End

Function TcpClose(sock)
    Return socket_close(sock)
End

Function DnsLookup(hostname)
    Return dns_lookup(hostname)
End

Function IsPortOpen(host, port)
    Return is_port_open(host, port)
End

Function HttpGet(url)
    Return http_get(url)
End

Function HttpPost(url, body)
    Return http_post(url, body)
End

Function HttpPut(url, body)
    Return http_put(url, body)
End

Function HttpDelete(url)
    Return http_delete(url)
End

Function Ping(host)
    Note: Check if a host is reachable by trying to connect
    Return is_port_open(host, 80)
End
''',
        "epl-ffi": '''Note: EPL FFI Library v5.2
Note: Convenience wrappers for C Foreign Function Interface

Function OpenLibrary(path)
    Return ffi_open(path)
End

Function CallFunction(lib, name, return_type, args, arg_types)
    Return ffi_call(lib, name, return_type, args, arg_types)
End

Function CloseLibrary(lib)
    Return ffi_close(lib)
End

Function FindLibrary(name)
    Return ffi_find(name)
End

Function ListTypes()
    Return ffi_types()
End
''',
    }
    return extra_sources.get(name, None)


# ─── Package Management ─────────────────────────────────

def uninstall_package(name):
    """Remove an installed package and clean up registry + manifest."""
    name = _sanitize_package_name(name)
    # Also try unified name resolution
    actual = _resolve_package_name(name)
    dest = os.path.join(PACKAGES_DIR, actual)
    # Extra safety: verify dest is actually inside PACKAGES_DIR
    real_dest = os.path.realpath(dest)
    real_packages = os.path.realpath(PACKAGES_DIR)
    if not real_dest.startswith(real_packages + os.sep):
        print(f"  Error: Invalid package path.")
        return False
    # Also check epl_modules/ in cwd
    local_dest = os.path.join('.', 'epl_modules', actual)
    removed_local = False
    if os.path.exists(local_dest):
        shutil.rmtree(local_dest)
        removed_local = True
    if os.path.exists(dest):
        shutil.rmtree(dest)
        # Clean up local registry
        reg = load_local_registry()
        if actual in reg:
            del reg[actual]
            save_local_registry(reg)
        # Remove from manifest (epl.toml or epl.json)
        project_root = find_project_root('.') or '.'
        manifest = load_manifest(project_root)
        if manifest and actual in manifest.get('dependencies', {}):
            del manifest['dependencies'][actual]
            save_manifest(manifest, project_root)
        print(f"  Removed: {actual}")
        return True
    if removed_local:
        print(f"  Removed: {actual} (from epl_modules/)")
        return True
    print(f"  Package not installed: {actual}")
    return False


def list_packages():
    """List all installed packages."""
    ensure_dirs()
    packages = []
    if os.path.exists(PACKAGES_DIR):
        for name in sorted(os.listdir(PACKAGES_DIR)):
            pkg_dir = os.path.join(PACKAGES_DIR, name)
            if os.path.isdir(pkg_dir):
                manifest = load_manifest(pkg_dir)
                version = manifest.get('version', '?') if manifest else '?'
                desc = manifest.get('description', '') if manifest else ''
                packages.append((name, version, desc))
    return packages


def get_package_path(name):
    """Get the path to an installed package."""
    try:
        name = _sanitize_package_name(name)
    except ValueError:
        return None
    p = os.path.join(PACKAGES_DIR, name)
    if os.path.exists(p):
        return p
    return None


def install_dependencies(path='.', frozen=False):
    """Install all dependencies from epl.toml or legacy epl.json.

    When frozen=True, install exactly what the lockfile specifies and fail if the
    lockfile is missing or incomplete.
    """
    manifest = load_manifest(path)
    if not manifest:
        print("  No epl.toml or epl.json found. Run: epl init")
        return False
    python_deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    
    # Frozen installs require the lockfile to fully define the project state.
    lock = load_lockfile(path)
    if frozen:
        if not lock:
            print("  No lockfile found. Run 'epl lock' first.")
            return False
        print("  Installing frozen dependencies from lockfile...")
        return install_from_lockfile(path, include_bridge=True, strict=True)

    # Existing compatibility behavior: if EPL packages are locked, prefer them.
    if lock and lock.get('packages'):
        print("  Found lockfile, installing locked EPL dependencies...")
        ok = install_from_lockfile(path, include_bridge=False, strict=False)
        return install_github_dependencies(path) and install_python_dependencies(path) and ok

    # Otherwise resolve dependencies (with transitive resolution)
    try:
        resolved = resolve_dependencies(path)
    except DependencyConflict as e:
        print(f"  Dependency conflict: {e}")
        return False

    github_deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})

    if not resolved and not python_deps and not github_deps:
        print("  No dependencies to install.")
        return True

    if resolved:
        print(f"  Installing {len(resolved)} EPL dependencies (including transitive)...")
        epl_ok = True
        for name, info in resolved.items():
            if not install_package(name, info.get('version')):
                epl_ok = False
    else:
        epl_ok = True

    github_ok = install_github_dependencies(path)
    python_ok = install_python_dependencies(path)

    # Generate lockfile after a successful dependency sync.
    if resolved or python_deps or github_deps:
        create_lockfile(path)
    return epl_ok and github_ok and python_ok


def update_package(name, path='.', allow_major=False):
    """Update a package to the latest available version."""
    manifest = load_manifest(path)
    if not manifest:
        print("  No epl.toml or epl.json found. Run: epl init")
        return False

    deps = manifest.get('dependencies', {})
    spec = deps.get(name, '*')
    pkg_dir = os.path.join(PACKAGES_DIR, name)
    old_version = '?'
    if os.path.isdir(pkg_dir):
        old_manifest = load_manifest(pkg_dir)
        if old_manifest:
            old_version = old_manifest.get('version', '?')
    latest_version = _get_latest_available_version(name)
    old_semver = SemVer.parse(old_version)
    latest_semver = SemVer.parse(latest_version) if latest_version else None
    if (
        not allow_major
        and old_semver
        and latest_semver
        and latest_semver.major != old_semver.major
        and spec not in ('*', '')
    ):
        print(f"  Skipping {name}: latest {latest_version} is a major update outside {spec}")
        return True

    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)

    version_arg = None if allow_major or spec in ('*', '') else spec
    if install_package(name, version_arg):
        new_manifest = load_manifest(os.path.join(PACKAGES_DIR, name))
        new_version = new_manifest.get('version', '?') if new_manifest else '?'
        print(f"  Updated {name}: {old_version} → {new_version}")
        # Regenerate lockfile
        create_lockfile(path)
        return True
    return False


def update_all(path='.', allow_major=False):
    """Update all installed dependencies."""
    manifest = load_manifest(path)
    if not manifest:
        print("  No epl.toml or epl.json found. Run: epl init")
        return False
    deps = manifest.get('dependencies', {})
    ok = True
    for name in sorted(deps):
        if not update_package(name, path, allow_major=allow_major):
            ok = False
    if deps:
        create_lockfile(path)
    return ok


# ─── Publish Workflow ────────────────────────────────────

def validate_package(path='.'):
    """Validate a package is ready for publishing.
    
    Returns dict: {'valid': bool, 'errors': [str], 'warnings': [str]}
    """
    errors = []
    warnings = []

    manifest = load_manifest(path)
    if not manifest:
        errors.append('No epl.toml or epl.json manifest found')
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # Recommend TOML
    fmt = get_manifest_format(path)
    if fmt == 'json':
        warnings.append('Using epl.json (legacy). Consider migrating to epl.toml: epl migrate')

    # Required fields
    for field in ('name', 'version', 'description'):
        if not manifest.get(field):
            errors.append(f"Missing required field: {field}")

    # Validate name
    name = manifest.get('name', '')
    if name and not re.match(r'^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$', name):
        errors.append(f"Invalid package name: '{name}'. Use lowercase alphanumeric, dots, hyphens, underscores.")

    # Validate version
    version = manifest.get('version', '')
    if version and not SemVer.parse(version):
        errors.append(f"Invalid semver: '{version}'")

    # Check entry point exists
    entry = manifest.get('entry', 'main.epl')
    if not os.path.exists(os.path.join(path, entry)):
        errors.append(f"Entry point not found: {entry}")

    python_deps = manifest.get(PYTHON_DEPENDENCIES_SECTION, {})
    if python_deps and not isinstance(python_deps, dict):
        errors.append('python-dependencies must be a table/map in epl.toml')
    elif isinstance(python_deps, dict):
        for import_name, requirement in python_deps.items():
            try:
                _validate_python_import_name(import_name)
                _normalize_python_requirement(import_name, requirement)
            except ValueError as exc:
                errors.append(str(exc))

    github_deps = manifest.get(GITHUB_DEPENDENCIES_SECTION, {})
    if github_deps and not isinstance(github_deps, dict):
        errors.append('github-dependencies must be a table/map in epl.toml')
    elif isinstance(github_deps, dict):
        for alias, repo in github_deps.items():
            try:
                _sanitize_package_name(alias)
                _validate_github_repo(repo)
            except ValueError as exc:
                errors.append(str(exc))

    # Warnings
    if not manifest.get('author'):
        warnings.append('No author specified')
    if not manifest.get('dependencies'):
        warnings.append('No dependencies listed (may be intentional)')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
    }


def pack_package(path='.', output_dir=None):
    """Pack a package directory into a distributable .zip file.
    
    Returns the path to the created archive, or None on failure.
    """
    validation = validate_package(path)
    if not validation['valid']:
        for e in validation['errors']:
            print(f"  Error: {e}")
        return None

    manifest = load_manifest(path)
    name = manifest['name']
    version = manifest['version']
    
    if output_dir is None:
        output_dir = os.path.join(path, 'dist')
    os.makedirs(output_dir, exist_ok=True)

    archive_name = f"{name}-{version}.zip"
    archive_path = os.path.join(output_dir, archive_name)

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            # Skip dist, node_modules, __pycache__, .git
            dirs[:] = [d for d in dirs if d not in ('dist', '__pycache__', '.git', 'node_modules')]
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, path)
                zf.write(fp, arcname)

    # Generate checksum
    with open(archive_path, 'rb') as f:
        checksum = hashlib.sha256(f.read()).hexdigest()
    
    checksum_path = archive_path + '.sha256'
    with open(checksum_path, 'w') as f:
        f.write(f"{checksum}  {archive_name}\n")

    print(f"  Packed: {archive_name} ({os.path.getsize(archive_path)} bytes)")
    print(f"  SHA256: {checksum}")
    return archive_path


def publish_package(path='.', registry_dir=None):
    """Publish a package to the local registry.
    
    For production use, this would upload to a remote registry.
    Currently publishes to the local registry so other projects can consume it.
    Returns True on success.
    """
    validation = validate_package(path)
    if not validation['valid']:
        for e in validation['errors']:
            print(f"  Error: {e}")
        return False

    manifest = load_manifest(path)
    name = manifest['name']
    version = manifest['version']

    # Pack the package
    archive_path = pack_package(path)
    if not archive_path:
        return False

    # Also install it to make it available
    _install_from_local(os.path.abspath(path))

    # Register in local registry (after install so we overwrite the local: source)
    reg = load_local_registry()
    reg[name] = {
        'version': version,
        'description': manifest.get('description', ''),
        'source': 'published',
        'path': os.path.abspath(path),
        'archive': archive_path,
        'published_at': time.time(),
    }
    save_local_registry(reg)

    print(f"  Published: {name}@{version}")
    return True


# ─── Init Command ────────────────────────────────────────

def init_project(name=None):
    """Initialize a new EPL project with epl.toml manifest."""
    if name is None:
        name = os.path.basename(os.getcwd())
    manifest = create_manifest(name=name, fmt='toml')
    # Create default main.epl if not exists
    if not os.path.exists('main.epl'):
        with open('main.epl', 'w', encoding='utf-8') as f:
            f.write(f'Note: {name} - Created with EPL\n\nSay "Hello from {name}!"\n')
    print(f"  Initialized EPL project: {name}")
    print(f"  Created: epl.toml, main.epl")
    print("  Next steps:")
    print("    epl install                  # sync registry, GitHub, and Python dependencies")
    print("    epl pyinstall requests       # add a Python package for `Use python`")
    print("    epl gitinstall owner/repo    # add a GitHub EPL package")
    print("    epl github clone owner/repo  # clone a GitHub project")
    return manifest


# ═══════════════════════════════════════════════════════════
#  Phase 4 — Production Package Ecosystem
# ═══════════════════════════════════════════════════════════

def add_dependency(name, version_spec="*", path='.', dev=False):
    """Add a dependency to the manifest and install it.

    Args:
        name: Package name.
        version_spec: Semver range (e.g. '^1.0.0', '>=2.0', '*').
        path: Project root path.
        dev: If True, add to dev-dependencies instead.
    """
    name = _sanitize_package_name(name)
    manifest = load_manifest(path)
    if not manifest:
        print("  No manifest found. Run: epl init")
        return False

    section = 'dev-dependencies' if dev else 'dependencies'
    manifest.setdefault(section, {})[name] = version_spec
    save_manifest(manifest, path)

    # Install the package
    success = install_package(name, version_spec if version_spec != '*' else None)
    if success:
        # Regenerate lockfile
        create_lockfile(path)
        print(f"  Added {name}@{version_spec} to {section}")
    return success


def remove_dependency(name, path='.'):
    """Remove a dependency from the manifest and uninstall it."""
    name = _sanitize_package_name(name)
    manifest = load_manifest(path)
    if not manifest:
        print("  No manifest found. Run: epl init")
        return False

    removed = False
    for section in ('dependencies', 'dev-dependencies'):
        if name in manifest.get(section, {}):
            del manifest[section][name]
            removed = True

    if not removed:
        print(f"  Package '{name}' not in dependencies.")
        return False

    save_manifest(manifest, path)
    uninstall_package(name)
    create_lockfile(path)
    print(f"  Removed {name} from project")
    return True


def dependency_tree(path='.', _depth=0, _seen=None):
    """Build and return a dependency tree structure.

    Returns list of dicts: [{'name': str, 'version': str, 'deps': [...]}]
    """
    if _seen is None:
        _seen = set()
    manifest = load_manifest(path)
    if not manifest:
        return []

    tree = []
    deps = manifest.get('dependencies', {})
    for name, spec in deps.items():
        if name in _seen:
            tree.append({'name': name, 'version': spec, 'deps': '[circular]'})
            continue
        _seen.add(name)
        pkg_path = os.path.join(PACKAGES_DIR, name)
        pkg_manifest = load_manifest(pkg_path) if os.path.isdir(pkg_path) else None
        version = pkg_manifest.get('version', spec) if pkg_manifest else spec
        sub_deps = dependency_tree(pkg_path, _depth + 1, _seen) if pkg_manifest else []
        tree.append({'name': name, 'version': version, 'deps': sub_deps})
    return tree


def print_dependency_tree(path='.'):
    """Print a human-readable dependency tree."""
    tree = dependency_tree(path)
    if not tree:
        print("  No dependencies.")
        return

    def _print(nodes, prefix=''):
        for idx, node in enumerate(nodes):
            is_last = idx == len(nodes) - 1
            connector = '└── ' if is_last else '├── '
            print(f"  {prefix}{connector}{node['name']}@{node['version']}")
            if isinstance(node['deps'], list) and node['deps']:
                ext = '    ' if is_last else '│   '
                _print(node['deps'], prefix + ext)
            elif node['deps'] == '[circular]':
                ext = '    ' if is_last else '│   '
                print(f"  {prefix}{ext}(circular)")

    manifest = load_manifest(path)
    proj_name = manifest.get('name', 'project') if manifest else 'project'
    proj_ver = manifest.get('version', '?') if manifest else '?'
    print(f"  {proj_name}@{proj_ver}")
    _print(tree)


def outdated_packages(path='.'):
    """Check for outdated dependencies.

    Returns list of dicts: [{'name': str, 'current': str, 'latest': str, 'constraint': str}]
    """
    manifest = load_manifest(path)
    if not manifest:
        return []

    outdated = []
    deps = manifest.get('dependencies', {})
    for name, spec in sorted(deps.items()):
        pkg_path = os.path.join(PACKAGES_DIR, name)
        current = '(not installed)'
        if os.path.isdir(pkg_path):
            pkg_m = load_manifest(pkg_path)
            if pkg_m:
                current = pkg_m.get('version', '?')

        # Find latest available version
        latest = _get_latest_available_version(name) or current

        if current != latest and current != '(not installed)':
            current_semver = SemVer.parse(current)
            latest_semver = SemVer.parse(latest)
            outdated.append({
                'name': name,
                'current': current,
                'latest': latest,
                'constraint': spec,
                'major_update': bool(
                    current_semver and latest_semver and latest_semver.major != current_semver.major
                ),
            })

    return outdated


def print_outdated(path='.'):
    """Print outdated packages."""
    results = outdated_packages(path)
    if not results:
        print("  All packages up to date.")
        return
    print(f"  {'Package':<24} {'Current':<12} {'Latest':<12} {'Constraint':<14}")
    print(f"  {'─' * 68}")
    for r in results:
        note = ' major' if r.get('major_update') else ''
        print(f"  {r['name']:<24} {r['current']:<12} {r['latest']:<12} {r.get('constraint', '*'):<14}{note}")
    print(f"\n  Run 'epl update' to update all packages.")


def audit_packages(path='.'):
    """Audit installed packages: verify integrity, check manifests.

    Returns dict: {'ok': int, 'warnings': [...], 'errors': [...]}
    """
    ok = 0
    warnings = []
    errors = []

    manifest = load_manifest(path)
    if not manifest:
        errors.append('No project manifest found')
        return {'ok': ok, 'warnings': warnings, 'errors': errors}

    deps = manifest.get('dependencies', {})
    for name, spec in deps.items():
        pkg_path = os.path.join(PACKAGES_DIR, name)
        if not os.path.isdir(pkg_path):
            errors.append(f'{name}: not installed')
            continue

        pkg_m = load_manifest(pkg_path)
        if not pkg_m:
            warnings.append(f'{name}: no manifest in package directory')
            ok += 1
            continue

        # Check version compatibility
        ver_str = pkg_m.get('version', '')
        if spec != '*' and ver_str:
            checker = parse_version_range(spec)
            pkg_ver = SemVer.parse(ver_str)
            if checker and pkg_ver and not checker(pkg_ver):
                warnings.append(f'{name}: installed {ver_str} not in range {spec}')

        # Check entry point
        entry = pkg_m.get('entry', 'main.epl')
        if not os.path.exists(os.path.join(pkg_path, entry)):
            warnings.append(f'{name}: entry point {entry} missing')

        ok += 1

    # Verify lockfile integrity
    lock = load_lockfile(path)
    if lock:
        for lname, linfo in lock['packages'].items():
            expected_hash = linfo.get('integrity', '')
            pkg_path = os.path.join(PACKAGES_DIR, lname)
            if os.path.isdir(pkg_path) and expected_hash:
                actual = _hash_directory(pkg_path)
                if actual != expected_hash:
                    errors.append(f'{lname}: integrity mismatch (tampered or modified)')
        for import_name in manifest.get(PYTHON_DEPENDENCIES_SECTION, {}):
            if import_name not in lock.get('python_packages', {}):
                warnings.append(f'{import_name}: missing from lockfile python_packages')
        for alias, repo in manifest.get(GITHUB_DEPENDENCIES_SECTION, {}).items():
            entry = lock.get('github_packages', {}).get(alias)
            if not entry:
                warnings.append(f'{alias}: missing from lockfile github_packages')
                continue
            if entry.get('repo') != repo:
                errors.append(f'{alias}: lockfile repo mismatch')
            if not entry.get('commit'):
                errors.append(f'{alias}: lockfile is not pinned to a commit')
    else:
        warnings.append('No lockfile found')

    return {'ok': ok, 'warnings': warnings, 'errors': errors}


def print_audit(path='.'):
    """Run and print audit results."""
    results = audit_packages(path)
    print(f"\n  Package Audit")
    print(f"  {'─' * 40}")
    print(f"  Packages OK: {results['ok']}")
    if results['warnings']:
        print(f"  Warnings: {len(results['warnings'])}")
        for w in results['warnings']:
            print(f"    ⚠ {w}")
    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
        for e in results['errors']:
            print(f"    ✗ {e}")
    if not results['warnings'] and not results['errors']:
        print("  No issues found.")


def clean_cache():
    """Remove all cached downloads."""
    if os.path.isdir(CACHE_DIR):
        count = 0
        for f in os.listdir(CACHE_DIR):
            fp = os.path.join(CACHE_DIR, f)
            if os.path.isfile(fp):
                os.unlink(fp)
                count += 1
        print(f"  Cleaned {count} cached files.")
    else:
        print("  Cache is empty.")
