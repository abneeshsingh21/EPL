"""
EPL Package Index v1.0 — Phase 7a: Git-Native Package Index

A decentralized, git-native package index that stores package metadata
in a Git repository (epl-lang/packages-index) and fetches packages
from their source (GitHub releases, tarballs).

Architecture:
  packages-index repo:
    packages/{name}/metadata.toml   — name, author, repo URL, license
    packages/{name}/versions.toml   — all published versions + checksums

The index is cloned/fetched locally to ~/.epl/index/ and cached.
Packages themselves are hosted by their authors (GitHub releases).
"""

import json
import os
import re
import time
import hashlib
import shutil
import tempfile
import urllib.request
import urllib.error
import zipfile
from typing import Dict, List, Optional, Tuple, Any


# ═══════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════

EPL_HOME = os.path.expanduser('~/.epl')
INDEX_DIR = os.path.join(EPL_HOME, 'index')
INDEX_CACHE_FILE = os.path.join(EPL_HOME, 'index_cache.json')
DEFAULT_INDEX_URL = 'https://github.com/epl-lang/packages-index.git'
DEFAULT_INDEX_RAW = 'https://raw.githubusercontent.com/epl-lang/packages-index/main'
INDEX_CACHE_TTL = 1800  # 30 minutes


def _ensure_dirs():
    os.makedirs(EPL_HOME, exist_ok=True)
    os.makedirs(INDEX_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
#  Index Entry — Per-Package Metadata
# ═══════════════════════════════════════════════════════════

class PackageMetadata:
    """Metadata for a package in the index."""

    __slots__ = ('name', 'description', 'author', 'license', 'repository',
                 'homepage', 'keywords', 'created_at', 'updated_at')

    def __init__(self, name: str, description: str = '', author: str = '',
                 license_: str = 'MIT', repository: str = '',
                 homepage: str = '', keywords: Optional[List[str]] = None,
                 created_at: float = 0, updated_at: float = 0):
        self.name = name
        self.description = description
        self.author = author
        self.license = license_
        self.repository = repository
        self.homepage = homepage
        self.keywords = keywords or []
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'license': self.license,
            'repository': self.repository,
            'homepage': self.homepage,
            'keywords': self.keywords,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PackageMetadata':
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            author=data.get('author', ''),
            license_=data.get('license', 'MIT'),
            repository=data.get('repository', ''),
            homepage=data.get('homepage', ''),
            keywords=data.get('keywords', []),
            created_at=data.get('created_at', 0),
            updated_at=data.get('updated_at', 0),
        )

    def __repr__(self):
        return f"PackageMetadata({self.name!r}, {self.description!r})"


class VersionEntry:
    """A single published version of a package."""

    __slots__ = ('version', 'checksum', 'download_url', 'published_at',
                 'yanked', 'dependencies', 'epl_version', 'size')

    def __init__(self, version: str, checksum: str = '', download_url: str = '',
                 published_at: float = 0, yanked: bool = False,
                 dependencies: Optional[Dict[str, str]] = None,
                 epl_version: str = '*', size: int = 0):
        self.version = version
        self.checksum = checksum
        self.download_url = download_url
        self.published_at = published_at or time.time()
        self.yanked = yanked
        self.dependencies = dependencies or {}
        self.epl_version = epl_version
        self.size = size

    def to_dict(self) -> dict:
        d = {
            'version': self.version,
            'checksum': self.checksum,
            'download_url': self.download_url,
            'published_at': self.published_at,
            'epl_version': self.epl_version,
            'size': self.size,
        }
        if self.yanked:
            d['yanked'] = True
        if self.dependencies:
            d['dependencies'] = dict(self.dependencies)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'VersionEntry':
        return cls(
            version=data.get('version', '0.0.0'),
            checksum=data.get('checksum', ''),
            download_url=data.get('download_url', ''),
            published_at=data.get('published_at', 0),
            yanked=data.get('yanked', False),
            dependencies=data.get('dependencies', {}),
            epl_version=data.get('epl_version', '*'),
            size=data.get('size', 0),
        )

    def __repr__(self):
        return f"VersionEntry({self.version!r})"


class PackageIndexEntry:
    """Full index entry: metadata + all versions."""

    def __init__(self, metadata: PackageMetadata, versions: Optional[List[VersionEntry]] = None):
        self.metadata = metadata
        self.versions = versions or []

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def latest_version(self) -> Optional[VersionEntry]:
        non_yanked = [v for v in self.versions if not v.yanked]
        if not non_yanked:
            return self.versions[-1] if self.versions else None
        return non_yanked[-1]

    def get_version(self, ver_str: str) -> Optional[VersionEntry]:
        for v in self.versions:
            if v.version == ver_str:
                return v
        return None

    def available_versions(self, include_yanked=False) -> List[str]:
        if include_yanked:
            return [v.version for v in self.versions]
        return [v.version for v in self.versions if not v.yanked]

    def to_dict(self) -> dict:
        return {
            'metadata': self.metadata.to_dict(),
            'versions': [v.to_dict() for v in self.versions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PackageIndexEntry':
        metadata = PackageMetadata.from_dict(data.get('metadata', data))
        versions = [VersionEntry.from_dict(v) for v in data.get('versions', [])]
        return cls(metadata, versions)


# ═══════════════════════════════════════════════════════════
#  Index Cache — Local JSON Cache of Remote Index
# ═══════════════════════════════════════════════════════════

class IndexCache:
    """In-memory + disk cache for the package index."""

    def __init__(self, path: str = INDEX_CACHE_FILE, ttl: int = INDEX_CACHE_TTL):
        self._path = path
        self._ttl = ttl
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {'packages': {}, 'updated_at': 0, 'index_url': ''}

    def _save(self):
        _ensure_dirs()
        tmp = self._path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self._path)

    def is_stale(self) -> bool:
        return time.time() - self._data.get('updated_at', 0) > self._ttl

    def get_package(self, name: str) -> Optional[PackageIndexEntry]:
        pkg_data = self._data.get('packages', {}).get(name)
        if pkg_data:
            return PackageIndexEntry.from_dict(pkg_data)
        return None

    def set_package(self, name: str, entry: PackageIndexEntry):
        self._data.setdefault('packages', {})[name] = entry.to_dict()
        self._data['updated_at'] = time.time()
        self._save()

    def set_all(self, packages: Dict[str, PackageIndexEntry]):
        self._data['packages'] = {n: e.to_dict() for n, e in packages.items()}
        self._data['updated_at'] = time.time()
        self._save()

    def all_packages(self) -> Dict[str, PackageIndexEntry]:
        result = {}
        for name, data in self._data.get('packages', {}).items():
            result[name] = PackageIndexEntry.from_dict(data)
        return result

    def search(self, query: str, limit: int = 30) -> List[PackageIndexEntry]:
        """Search packages by name, description, or keywords."""
        query_lower = query.lower()
        scored = []
        for name, data in self._data.get('packages', {}).items():
            entry = PackageIndexEntry.from_dict(data)
            score = 0
            if query_lower == name:
                score += 100
            elif query_lower in name:
                score += 50
            if query_lower in (entry.metadata.description or '').lower():
                score += 20
            for kw in entry.metadata.keywords:
                if query_lower in kw.lower():
                    score += 30
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def clear(self):
        self._data = {'packages': {}, 'updated_at': 0, 'index_url': ''}
        if os.path.exists(self._path):
            os.unlink(self._path)

    @property
    def package_count(self) -> int:
        return len(self._data.get('packages', {}))

    @property
    def last_updated(self) -> float:
        return self._data.get('updated_at', 0)


# ═══════════════════════════════════════════════════════════
#  Package Index — Git-Native Fetcher
# ═══════════════════════════════════════════════════════════

class PackageIndex:
    """Git-native package index fetcher.

    Fetches package metadata from a git-based index repository.
    Supports:
      - Full index sync (clone/pull)
      - Sparse fetch (individual package metadata)
      - Offline mode (local cache only)
      - Multiple index sources (registries)
    """

    def __init__(self, index_url: str = DEFAULT_INDEX_URL,
                 raw_url: str = DEFAULT_INDEX_RAW,
                 cache: Optional[IndexCache] = None,
                 offline: bool = False):
        self._index_url = index_url
        self._raw_url = raw_url
        self._cache = cache or IndexCache()
        self._offline = offline
        _ensure_dirs()

    @property
    def cache(self) -> IndexCache:
        return self._cache

    @property
    def offline(self) -> bool:
        return self._offline

    # ── Fetch Operations ──

    def fetch_package(self, name: str, force: bool = False) -> Optional[PackageIndexEntry]:
        """Fetch metadata for a single package.

        Checks cache first (unless force=True), then fetches from remote.
        """
        if not force:
            cached = self._cache.get_package(name)
            if cached and not self._cache.is_stale():
                return cached

        if self._offline:
            return self._cache.get_package(name)

        entry = self._fetch_remote_package(name)
        if entry:
            self._cache.set_package(name, entry)
        return entry or self._cache.get_package(name)

    def fetch_all(self, force: bool = False) -> Dict[str, PackageIndexEntry]:
        """Fetch the full index.

        Uses cache if fresh, otherwise fetches from remote.
        """
        if not force and not self._cache.is_stale():
            cached = self._cache.all_packages()
            if cached:
                return cached

        if self._offline:
            return self._cache.all_packages()

        all_pkgs = self._fetch_remote_index()
        if all_pkgs:
            self._cache.set_all(all_pkgs)
            return all_pkgs
        return self._cache.all_packages()

    def search(self, query: str, limit: int = 30) -> List[PackageIndexEntry]:
        """Search the index for packages matching query."""
        # Ensure index is loaded
        if self._cache.package_count == 0:
            self.fetch_all()
        return self._cache.search(query, limit)

    def get_versions(self, name: str) -> List[str]:
        """Get available versions for a package."""
        entry = self.fetch_package(name)
        if entry:
            return entry.available_versions()
        return []

    def get_download_url(self, name: str, version: str) -> Optional[str]:
        """Get the download URL for a specific package version."""
        entry = self.fetch_package(name)
        if entry:
            ver = entry.get_version(version)
            if ver:
                return ver.download_url
        return None

    def get_checksum(self, name: str, version: str) -> Optional[str]:
        """Get the SHA-256 checksum for a specific package version."""
        entry = self.fetch_package(name)
        if entry:
            ver = entry.get_version(version)
            if ver:
                return ver.checksum
        return None

    def get_dependencies(self, name: str, version: str) -> Dict[str, str]:
        """Get the dependency map for a specific package version."""
        entry = self.fetch_package(name)
        if entry:
            ver = entry.get_version(version)
            if ver:
                return dict(ver.dependencies)
        return {}

    # ── Remote Fetch Implementation ──

    def _fetch_remote_package(self, name: str) -> Optional[PackageIndexEntry]:
        """Fetch a single package's metadata from the remote index."""
        try:
            # Fetch metadata.toml
            meta_url = f"{self._raw_url}/packages/{name}/metadata.json"
            meta_data = self._http_get_json(meta_url)
            if not meta_data:
                return None

            # Fetch versions.json
            ver_url = f"{self._raw_url}/packages/{name}/versions.json"
            ver_data = self._http_get_json(ver_url)

            metadata = PackageMetadata.from_dict(meta_data)
            versions = []
            if ver_data and 'versions' in ver_data:
                for v in ver_data['versions']:
                    versions.append(VersionEntry.from_dict(v))

            return PackageIndexEntry(metadata, versions)
        except Exception:
            return None

    def _fetch_remote_index(self) -> Optional[Dict[str, PackageIndexEntry]]:
        """Fetch the full index from remote."""
        try:
            index_url = f"{self._raw_url}/index.json"
            data = self._http_get_json(index_url)
            if not data or 'packages' not in data:
                return None

            result = {}
            for name, pkg_data in data['packages'].items():
                result[name] = PackageIndexEntry.from_dict(pkg_data)
            return result
        except Exception:
            return None

    def _http_get_json(self, url: str, timeout: int = 10) -> Optional[dict]:
        """Fetch JSON from a URL."""
        headers = {'User-Agent': 'EPL-PackageIndex/1.0'}
        token = os.environ.get('EPL_GITHUB_TOKEN', '')
        if token:
            headers['Authorization'] = f'token {token}'
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                json.JSONDecodeError):
            return None

    # ── Index Sync (Git-based) ──

    def sync_index(self, force: bool = False) -> bool:
        """Sync the local index directory with the remote git repo.

        Uses git clone/pull if git is available, otherwise falls back
        to HTTP download of the index.json.
        """
        if not force and not self._cache.is_stale():
            return True

        if self._offline:
            return False

        # Try git-based sync
        if self._git_available():
            return self._git_sync()

        # Fall back to HTTP-based full index fetch
        all_pkgs = self._fetch_remote_index()
        if all_pkgs:
            self._cache.set_all(all_pkgs)
            return True
        return False

    def _git_available(self) -> bool:
        """Check if git is available on the system."""
        try:
            import subprocess
            result = subprocess.run(['git', '--version'],
                                    capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def _git_sync(self) -> bool:
        """Sync using git clone/pull."""
        try:
            import subprocess
            git_dir = os.path.join(INDEX_DIR, 'repo')

            if os.path.isdir(os.path.join(git_dir, '.git')):
                # Pull latest
                result = subprocess.run(
                    ['git', '-C', git_dir, 'pull', '--ff-only'],
                    capture_output=True, timeout=30
                )
                return result.returncode == 0
            else:
                # Clone with depth 1 for speed
                os.makedirs(git_dir, exist_ok=True)
                result = subprocess.run(
                    ['git', 'clone', '--depth', '1', self._index_url, git_dir],
                    capture_output=True, timeout=60
                )
                return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    # ── Package Download (from source) ──

    def download_package(self, name: str, version: str,
                         dest_dir: str) -> Optional[str]:
        """Download a specific package version to dest_dir.

        Returns the path to the extracted package, or None on failure.
        Verifies SHA-256 checksum if available.
        """
        entry = self.fetch_package(name)
        if not entry:
            return None

        ver_entry = entry.get_version(version)
        if not ver_entry:
            return None

        if ver_entry.yanked:
            print(f"  Warning: {name}@{version} is yanked.")

        url = ver_entry.download_url
        if not url:
            # Generate URL from repository
            repo = entry.metadata.repository
            if repo:
                url = f"https://github.com/{repo}/archive/refs/tags/v{version}.zip"
            else:
                return None

        # Validate URL scheme
        if not url.startswith('https://'):
            return None

        try:
            # Download to temp file
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = os.path.join(tmp, 'package.zip')
                headers = {'User-Agent': 'EPL-PackageIndex/1.0'}
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    with open(zip_path, 'wb') as f:
                        f.write(resp.read())

                # Verify checksum
                if ver_entry.checksum:
                    actual = _sha256_file(zip_path)
                    if actual != ver_entry.checksum:
                        print(f"  Checksum mismatch for {name}@{version}!")
                        print(f"  Expected: {ver_entry.checksum}")
                        print(f"  Got:      {actual}")
                        return None

                # Extract with zip-slip protection
                pkg_dest = os.path.join(dest_dir, name)
                os.makedirs(pkg_dest, exist_ok=True)
                _safe_extract_zip(zip_path, pkg_dest)
                return pkg_dest

        except (urllib.error.URLError, OSError, zipfile.BadZipFile) as e:
            print(f"  Download failed for {name}@{version}: {e}")
            return None

    # ── Publishing Support ──

    def create_index_entry(self, name: str, metadata: PackageMetadata,
                           version_entry: VersionEntry) -> PackageIndexEntry:
        """Create or update an index entry for publishing."""
        existing = self._cache.get_package(name)
        if existing:
            existing.metadata = metadata
            existing.versions.append(version_entry)
            existing.metadata.updated_at = time.time()
            self._cache.set_package(name, existing)
            return existing
        else:
            entry = PackageIndexEntry(metadata, [version_entry])
            self._cache.set_package(name, entry)
            return entry

    def generate_index_pr_content(self, entry: PackageIndexEntry) -> Dict[str, str]:
        """Generate the file contents for a PR to the packages-index repo.

        Returns dict of {filepath: content} for the PR.
        """
        name = entry.name
        metadata = {
            'name': entry.metadata.name,
            'description': entry.metadata.description,
            'author': entry.metadata.author,
            'license': entry.metadata.license,
            'repository': entry.metadata.repository,
            'homepage': entry.metadata.homepage,
            'keywords': entry.metadata.keywords,
        }
        versions_data = {
            'versions': [v.to_dict() for v in entry.versions],
        }
        return {
            f'packages/{name}/metadata.json': json.dumps(metadata, indent=2),
            f'packages/{name}/versions.json': json.dumps(versions_data, indent=2),
        }


# ═══════════════════════════════════════════════════════════
#  Multi-Registry Support
# ═══════════════════════════════════════════════════════════

class RegistryConfig:
    """Configuration for a named package registry."""

    def __init__(self, name: str, url: str, raw_url: str = '',
                 token_env: str = '', priority: int = 0):
        self.name = name
        self.url = url
        self.raw_url = raw_url or url.replace('.git', '').replace(
            'github.com', 'raw.githubusercontent.com') + '/main'
        self.token_env = token_env
        self.priority = priority

    def to_dict(self) -> dict:
        d = {'url': self.url}
        if self.token_env:
            d['token_env'] = self.token_env
        if self.priority:
            d['priority'] = self.priority
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict) -> 'RegistryConfig':
        if isinstance(data, str):
            return cls(name=name, url=data)
        return cls(
            name=name,
            url=data.get('url', ''),
            raw_url=data.get('raw_url', ''),
            token_env=data.get('token_env', ''),
            priority=data.get('priority', 0),
        )


class MultiRegistry:
    """Manages multiple package registries for dependency resolution.

    Searches registries in priority order and merges results.
    Supports the [registries] table in epl.toml.
    """

    def __init__(self):
        self._registries: Dict[str, RegistryConfig] = {}
        self._indexes: Dict[str, PackageIndex] = {}
        # Add default registry
        self.add_registry(RegistryConfig(
            name='default',
            url=DEFAULT_INDEX_URL,
            raw_url=DEFAULT_INDEX_RAW,
            priority=0,
        ))

    def add_registry(self, config: RegistryConfig):
        self._registries[config.name] = config
        cache_file = os.path.join(EPL_HOME, f'index_cache_{config.name}.json')
        self._indexes[config.name] = PackageIndex(
            index_url=config.url,
            raw_url=config.raw_url,
            cache=IndexCache(path=cache_file),
        )

    def load_from_manifest(self, manifest: dict):
        """Load registry configs from a manifest's [registries] section."""
        registries = manifest.get('registries', {})
        for name, data in registries.items():
            config = RegistryConfig.from_dict(name, data)
            self.add_registry(config)

    def fetch_package(self, name: str, registry: str = None) -> Optional[PackageIndexEntry]:
        """Fetch a package from the specified registry, or search all."""
        if registry and registry in self._indexes:
            return self._indexes[registry].fetch_package(name)

        # Search all registries in priority order
        for reg_name in self._sorted_registry_names():
            result = self._indexes[reg_name].fetch_package(name)
            if result:
                return result
        return None

    def search(self, query: str, limit: int = 30) -> List[PackageIndexEntry]:
        """Search across all registries."""
        seen = set()
        results = []
        for reg_name in self._sorted_registry_names():
            for entry in self._indexes[reg_name].search(query, limit):
                if entry.name not in seen:
                    seen.add(entry.name)
                    results.append(entry)
        return results[:limit]

    def get_index(self, registry: str = 'default') -> Optional[PackageIndex]:
        return self._indexes.get(registry)

    def registry_names(self) -> List[str]:
        return list(self._registries.keys())

    def _sorted_registry_names(self) -> List[str]:
        items = sorted(self._registries.items(),
                       key=lambda x: x[1].priority, reverse=True)
        return [name for name, _ in items]


# ═══════════════════════════════════════════════════════════
#  Scoped Package Name Support (@scope/name)
# ═══════════════════════════════════════════════════════════

_SCOPE_RE = re.compile(r'^@([a-zA-Z][a-zA-Z0-9_-]*)/([a-zA-Z][a-zA-Z0-9_-]*)$')
_PLAIN_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')


class ScopedName:
    """Represents a potentially scoped package name like @org/pkg or just pkg."""

    __slots__ = ('scope', 'name', 'full')

    def __init__(self, full_name: str):
        m = _SCOPE_RE.match(full_name)
        if m:
            self.scope = m.group(1)
            self.name = m.group(2)
            self.full = full_name
        else:
            self.scope = None
            self.name = full_name
            self.full = full_name

    @property
    def is_scoped(self) -> bool:
        return self.scope is not None

    @property
    def safe_dir_name(self) -> str:
        """File-safe directory name: @org/pkg -> @org__pkg"""
        if self.scope:
            return f"@{self.scope}__{self.name}"
        return self.name

    @staticmethod
    def validate(name: str) -> bool:
        """Check if a name is a valid package name (scoped or plain)."""
        return bool(_SCOPE_RE.match(name) or _PLAIN_RE.match(name))

    def __str__(self):
        return self.full

    def __repr__(self):
        return f"ScopedName({self.full!r})"

    def __eq__(self, other):
        if isinstance(other, ScopedName):
            return self.full == other.full
        if isinstance(other, str):
            return self.full == other
        return NotImplemented

    def __hash__(self):
        return hash(self.full)


# ═══════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════

def _sha256_file(path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _safe_extract_zip(zip_path: str, dest: str):
    """Extract a zip file with zip-slip protection."""
    real_dest = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path, 'r') as z:
        for member in z.namelist():
            member_path = os.path.normpath(member)
            if os.path.isabs(member_path) or member_path.startswith('..'):
                continue
            full_path = os.path.realpath(os.path.join(dest, member_path))
            if not full_path.startswith(real_dest):
                continue
            z.extract(member, dest)


def parse_package_spec(spec: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse a package specification string.

    Formats:
      'epl-math'           -> ('epl-math', None, None)
      'epl-math@1.0.0'     -> ('epl-math', '1.0.0', None)
      'epl-math@^2.0.0'    -> ('epl-math', '^2.0.0', None)
      '@org/pkg'            -> ('@org/pkg', None, None)
      '@org/pkg@1.0.0'      -> ('@org/pkg', '1.0.0', None)
      'company:utils'       -> ('utils', None, 'company')

    Returns (name, version_spec, registry_name).
    """
    registry = None
    version = None

    # Check for registry: prefix (not http: or github:)
    if ':' in spec and not spec.startswith('http') and not spec.startswith('github:'):
        colon_idx = spec.index(':')
        potential_reg = spec[:colon_idx]
        if _PLAIN_RE.match(potential_reg) and not spec[colon_idx + 1:].startswith('//'):
            registry = potential_reg
            spec = spec[colon_idx + 1:]

    # Check for @version
    if '@' in spec:
        # Handle scoped names: @scope/pkg@version
        if spec.startswith('@'):
            slash_idx = spec.find('/')
            if slash_idx > 0:
                rest = spec[slash_idx + 1:]
                if '@' in rest:
                    at_idx = rest.index('@')
                    name = spec[:slash_idx + 1 + at_idx]
                    version = rest[at_idx + 1:]
                else:
                    name = spec
            else:
                name = spec
        else:
            at_idx = spec.index('@')
            name = spec[:at_idx]
            version = spec[at_idx + 1:]
    else:
        name = spec

    return name, version or None, registry


def build_index_from_builtin_registry() -> Dict[str, PackageIndexEntry]:
    """Build PackageIndexEntry objects from the BUILTIN_REGISTRY.

    Bridges the existing builtin packages to the new index system.
    """
    from epl.package_manager import BUILTIN_REGISTRY

    entries = {}
    for name, info in BUILTIN_REGISTRY.items():
        metadata = PackageMetadata(
            name=name,
            description=info.get('description', ''),
            author='EPL Team',
            license_='MIT',
            repository='epl-lang/epl',
            keywords=info.get('keywords', []),
        )
        version = VersionEntry(
            version=info.get('version', '1.0.0'),
            checksum='',
            download_url='',
            dependencies={},
            epl_version='>=7.0.0',
        )
        entries[name] = PackageIndexEntry(metadata, [version])
    return entries
