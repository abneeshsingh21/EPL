"""
EPL Phase 7 Tests — Full Package Ecosystem Infrastructure
Tests for: Package Index (7a), Resolver (7c), Publisher (7b),
           Scoped Names (7d), Workspace (7e), CI Generation (7f)

Run: python -m pytest tests/test_phase7.py -v
"""

import json
import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
#  7a: Package Index Tests
# ═══════════════════════════════════════════════════════════

class TestPackageMetadata(unittest.TestCase):
    """Tests for PackageMetadata data class."""

    def test_create_metadata(self):
        from epl.package_index import PackageMetadata
        m = PackageMetadata('test-pkg', description='A test', author='Alice')
        self.assertEqual(m.name, 'test-pkg')
        self.assertEqual(m.description, 'A test')
        self.assertEqual(m.author, 'Alice')
        self.assertEqual(m.license, 'MIT')

    def test_metadata_to_dict(self):
        from epl.package_index import PackageMetadata
        m = PackageMetadata('pkg', description='desc', author='Bob', license_='Apache-2.0')
        d = m.to_dict()
        self.assertEqual(d['name'], 'pkg')
        self.assertEqual(d['license'], 'Apache-2.0')
        self.assertIn('created_at', d)

    def test_metadata_from_dict(self):
        from epl.package_index import PackageMetadata
        d = {'name': 'pkg', 'description': 'hi', 'author': 'X', 'license': 'MIT'}
        m = PackageMetadata.from_dict(d)
        self.assertEqual(m.name, 'pkg')
        self.assertEqual(m.description, 'hi')

    def test_metadata_roundtrip(self):
        from epl.package_index import PackageMetadata
        m1 = PackageMetadata('pkg', 'desc', 'auth', 'ISC', 'repo/url', 'http://hp', ['web'])
        d = m1.to_dict()
        m2 = PackageMetadata.from_dict(d)
        self.assertEqual(m1.name, m2.name)
        self.assertEqual(m1.description, m2.description)
        self.assertEqual(m1.keywords, m2.keywords)

    def test_metadata_defaults(self):
        from epl.package_index import PackageMetadata
        m = PackageMetadata('x')
        self.assertEqual(m.description, '')
        self.assertEqual(m.author, '')
        self.assertEqual(m.keywords, [])
        self.assertTrue(m.created_at > 0)


class TestVersionEntry(unittest.TestCase):
    """Tests for VersionEntry data class."""

    def test_create_version(self):
        from epl.package_index import VersionEntry
        v = VersionEntry('1.0.0', checksum='abc123')
        self.assertEqual(v.version, '1.0.0')
        self.assertEqual(v.checksum, 'abc123')
        self.assertFalse(v.yanked)

    def test_version_to_dict(self):
        from epl.package_index import VersionEntry
        v = VersionEntry('2.0.0', dependencies={'epl-http': '^1.0.0'})
        d = v.to_dict()
        self.assertEqual(d['version'], '2.0.0')
        self.assertEqual(d['dependencies']['epl-http'], '^1.0.0')

    def test_version_from_dict(self):
        from epl.package_index import VersionEntry
        d = {'version': '1.5.0', 'checksum': 'sha', 'yanked': True}
        v = VersionEntry.from_dict(d)
        self.assertEqual(v.version, '1.5.0')
        self.assertTrue(v.yanked)

    def test_version_roundtrip(self):
        from epl.package_index import VersionEntry
        v1 = VersionEntry('3.0.0', 'cs', 'http://dl', dependencies={'a': '1.0.0'})
        d = v1.to_dict()
        v2 = VersionEntry.from_dict(d)
        self.assertEqual(v1.version, v2.version)
        self.assertEqual(v1.dependencies, v2.dependencies)

    def test_yanked_version(self):
        from epl.package_index import VersionEntry
        v = VersionEntry('0.1.0', yanked=True)
        self.assertTrue(v.yanked)
        d = v.to_dict()
        self.assertTrue(d['yanked'])


class TestPackageIndexEntry(unittest.TestCase):
    """Tests for PackageIndexEntry."""

    def test_create_entry(self):
        from epl.package_index import PackageMetadata, VersionEntry, PackageIndexEntry
        m = PackageMetadata('test')
        v1 = VersionEntry('1.0.0')
        v2 = VersionEntry('2.0.0')
        entry = PackageIndexEntry(m, [v1, v2])
        self.assertEqual(entry.name, 'test')
        self.assertEqual(len(entry.versions), 2)

    def test_latest_version(self):
        from epl.package_index import PackageMetadata, VersionEntry, PackageIndexEntry
        m = PackageMetadata('test')
        v1 = VersionEntry('1.0.0')
        v2 = VersionEntry('2.0.0')
        entry = PackageIndexEntry(m, [v1, v2])
        self.assertEqual(entry.latest_version.version, '2.0.0')

    def test_latest_version_skips_yanked(self):
        from epl.package_index import PackageMetadata, VersionEntry, PackageIndexEntry
        m = PackageMetadata('test')
        v1 = VersionEntry('1.0.0')
        v2 = VersionEntry('2.0.0', yanked=True)
        entry = PackageIndexEntry(m, [v1, v2])
        self.assertEqual(entry.latest_version.version, '1.0.0')

    def test_get_version(self):
        from epl.package_index import PackageMetadata, VersionEntry, PackageIndexEntry
        m = PackageMetadata('test')
        v1 = VersionEntry('1.0.0')
        v2 = VersionEntry('2.0.0')
        entry = PackageIndexEntry(m, [v1, v2])
        self.assertEqual(entry.get_version('1.0.0').version, '1.0.0')
        self.assertIsNone(entry.get_version('3.0.0'))

    def test_available_versions(self):
        from epl.package_index import PackageMetadata, VersionEntry, PackageIndexEntry
        m = PackageMetadata('test')
        versions = [VersionEntry('1.0.0'), VersionEntry('2.0.0', yanked=True), VersionEntry('3.0.0')]
        entry = PackageIndexEntry(m, versions)
        available = entry.available_versions()
        self.assertEqual(available, ['1.0.0', '3.0.0'])
        all_versions = entry.available_versions(include_yanked=True)
        self.assertEqual(len(all_versions), 3)

    def test_entry_roundtrip(self):
        from epl.package_index import PackageMetadata, VersionEntry, PackageIndexEntry
        m = PackageMetadata('pkg', 'desc')
        v = VersionEntry('1.0.0', checksum='abc')
        entry = PackageIndexEntry(m, [v])
        d = entry.to_dict()
        entry2 = PackageIndexEntry.from_dict(d)
        self.assertEqual(entry2.name, 'pkg')
        self.assertEqual(entry2.versions[0].checksum, 'abc')


class TestIndexCache(unittest.TestCase):
    """Tests for IndexCache."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache_path = os.path.join(self.tmp, 'cache.json')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_cache(self):
        from epl.package_index import IndexCache
        cache = IndexCache(self.cache_path)
        self.assertEqual(cache.package_count, 0)
        self.assertTrue(cache.is_stale())

    def test_set_and_get_package(self):
        from epl.package_index import IndexCache, PackageMetadata, VersionEntry, PackageIndexEntry
        cache = IndexCache(self.cache_path)
        m = PackageMetadata('test-pkg')
        v = VersionEntry('1.0.0')
        entry = PackageIndexEntry(m, [v])
        cache.set_package('test-pkg', entry)
        got = cache.get_package('test-pkg')
        self.assertIsNotNone(got)
        self.assertEqual(got.name, 'test-pkg')

    def test_cache_persistence(self):
        from epl.package_index import IndexCache, PackageMetadata, VersionEntry, PackageIndexEntry
        cache1 = IndexCache(self.cache_path)
        m = PackageMetadata('persisted')
        v = VersionEntry('1.0.0')
        cache1.set_package('persisted', PackageIndexEntry(m, [v]))

        cache2 = IndexCache(self.cache_path)
        got = cache2.get_package('persisted')
        self.assertIsNotNone(got)
        self.assertEqual(got.name, 'persisted')

    def test_cache_search(self):
        from epl.package_index import IndexCache, PackageMetadata, VersionEntry, PackageIndexEntry
        cache = IndexCache(self.cache_path)
        for name in ['epl-math', 'epl-http', 'epl-json']:
            m = PackageMetadata(name, description=f'{name} package')
            v = VersionEntry('1.0.0')
            cache.set_package(name, PackageIndexEntry(m, [v]))

        results = cache.search('math')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].name, 'epl-math')

    def test_cache_clear(self):
        from epl.package_index import IndexCache, PackageMetadata, VersionEntry, PackageIndexEntry
        cache = IndexCache(self.cache_path)
        m = PackageMetadata('test')
        cache.set_package('test', PackageIndexEntry(m, []))
        self.assertEqual(cache.package_count, 1)
        cache.clear()
        self.assertEqual(cache.package_count, 0)

    def test_set_all(self):
        from epl.package_index import IndexCache, PackageMetadata, VersionEntry, PackageIndexEntry
        cache = IndexCache(self.cache_path)
        entries = {
            'a': PackageIndexEntry(PackageMetadata('a'), [VersionEntry('1.0.0')]),
            'b': PackageIndexEntry(PackageMetadata('b'), [VersionEntry('2.0.0')]),
        }
        cache.set_all(entries)
        self.assertEqual(cache.package_count, 2)
        self.assertFalse(cache.is_stale())


class TestPackageIndex(unittest.TestCase):
    """Tests for PackageIndex (offline mode)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache_path = os.path.join(self.tmp, 'cache.json')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_offline_mode(self):
        from epl.package_index import PackageIndex, IndexCache
        cache = IndexCache(self.cache_path)
        idx = PackageIndex(offline=True, cache=cache)
        self.assertTrue(idx.offline)

    def test_fetch_from_cache(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        cache = IndexCache(self.cache_path)
        m = PackageMetadata('cached-pkg')
        v = VersionEntry('1.0.0')
        cache.set_package('cached-pkg', PackageIndexEntry(m, [v]))

        idx = PackageIndex(offline=True, cache=cache)
        result = idx.fetch_package('cached-pkg')
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'cached-pkg')

    def test_get_versions(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        cache = IndexCache(self.cache_path)
        m = PackageMetadata('multi-ver')
        versions = [VersionEntry('1.0.0'), VersionEntry('2.0.0'), VersionEntry('3.0.0')]
        cache.set_package('multi-ver', PackageIndexEntry(m, versions))

        idx = PackageIndex(offline=True, cache=cache)
        result = idx.get_versions('multi-ver')
        self.assertEqual(result, ['1.0.0', '2.0.0', '3.0.0'])

    def test_get_dependencies(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        cache = IndexCache(self.cache_path)
        m = PackageMetadata('dep-pkg')
        v = VersionEntry('1.0.0', dependencies={'epl-math': '^1.0.0'})
        cache.set_package('dep-pkg', PackageIndexEntry(m, [v]))

        idx = PackageIndex(offline=True, cache=cache)
        deps = idx.get_dependencies('dep-pkg', '1.0.0')
        self.assertEqual(deps, {'epl-math': '^1.0.0'})

    def test_get_checksum(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        cache = IndexCache(self.cache_path)
        m = PackageMetadata('check-pkg')
        v = VersionEntry('1.0.0', checksum='abc123def456')
        cache.set_package('check-pkg', PackageIndexEntry(m, [v]))

        idx = PackageIndex(offline=True, cache=cache)
        cs = idx.get_checksum('check-pkg', '1.0.0')
        self.assertEqual(cs, 'abc123def456')

    def test_search(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        cache = IndexCache(self.cache_path)
        for name in ['epl-math', 'epl-http', 'epl-json', 'epl-csv']:
            m = PackageMetadata(name, description=f'{name} module')
            cache.set_package(name, PackageIndexEntry(m, [VersionEntry('1.0.0')]))

        idx = PackageIndex(offline=True, cache=cache)
        results = idx.search('http')
        names = [r.name for r in results]
        self.assertIn('epl-http', names)

    def test_create_index_entry(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry)
        cache = IndexCache(self.cache_path)
        idx = PackageIndex(offline=True, cache=cache)
        m = PackageMetadata('new-pkg', description='New')
        v = VersionEntry('1.0.0')
        entry = idx.create_index_entry('new-pkg', m, v)
        self.assertEqual(entry.name, 'new-pkg')
        self.assertEqual(len(entry.versions), 1)

    def test_generate_pr_content(self):
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry)
        cache = IndexCache(self.cache_path)
        idx = PackageIndex(offline=True, cache=cache)
        m = PackageMetadata('pr-pkg', description='PR test', author='Dev')
        v = VersionEntry('1.0.0', checksum='sha256hash')
        entry = idx.create_index_entry('pr-pkg', m, v)
        pr_files = idx.generate_index_pr_content(entry)
        self.assertIn('packages/pr-pkg/metadata.json', pr_files)
        self.assertIn('packages/pr-pkg/versions.json', pr_files)
        meta = json.loads(pr_files['packages/pr-pkg/metadata.json'])
        self.assertEqual(meta['name'], 'pr-pkg')


class TestScopedName(unittest.TestCase):
    """Tests for ScopedName (7d)."""

    def test_plain_name(self):
        from epl.package_index import ScopedName
        s = ScopedName('epl-math')
        self.assertFalse(s.is_scoped)
        self.assertIsNone(s.scope)
        self.assertEqual(s.name, 'epl-math')
        self.assertEqual(s.full, 'epl-math')

    def test_scoped_name(self):
        from epl.package_index import ScopedName
        s = ScopedName('@myorg/utils')
        self.assertTrue(s.is_scoped)
        self.assertEqual(s.scope, 'myorg')
        self.assertEqual(s.name, 'utils')
        self.assertEqual(s.full, '@myorg/utils')

    def test_safe_dir_name(self):
        from epl.package_index import ScopedName
        self.assertEqual(ScopedName('plain').safe_dir_name, 'plain')
        self.assertEqual(ScopedName('@org/pkg').safe_dir_name, '@org__pkg')

    def test_validate(self):
        from epl.package_index import ScopedName
        self.assertTrue(ScopedName.validate('epl-math'))
        self.assertTrue(ScopedName.validate('@org/pkg'))
        self.assertFalse(ScopedName.validate(''))
        self.assertFalse(ScopedName.validate('123invalid'))
        self.assertFalse(ScopedName.validate('@/bad'))

    def test_equality(self):
        from epl.package_index import ScopedName
        self.assertEqual(ScopedName('a'), ScopedName('a'))
        self.assertEqual(ScopedName('@o/p'), ScopedName('@o/p'))
        self.assertNotEqual(ScopedName('a'), ScopedName('b'))

    def test_hash(self):
        from epl.package_index import ScopedName
        s = {ScopedName('a'), ScopedName('a'), ScopedName('b')}
        self.assertEqual(len(s), 2)

    def test_str(self):
        from epl.package_index import ScopedName
        self.assertEqual(str(ScopedName('@org/pkg')), '@org/pkg')
        self.assertEqual(str(ScopedName('simple')), 'simple')


class TestParsePackageSpec(unittest.TestCase):
    """Tests for parse_package_spec function."""

    def test_simple_name(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('epl-math')
        self.assertEqual(name, 'epl-math')
        self.assertIsNone(ver)
        self.assertIsNone(reg)

    def test_name_with_version(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('epl-math@1.0.0')
        self.assertEqual(name, 'epl-math')
        self.assertEqual(ver, '1.0.0')

    def test_name_with_caret_version(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('epl-math@^2.0.0')
        self.assertEqual(name, 'epl-math')
        self.assertEqual(ver, '^2.0.0')

    def test_scoped_name(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('@org/pkg')
        self.assertEqual(name, '@org/pkg')
        self.assertIsNone(ver)

    def test_scoped_name_with_version(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('@org/pkg@1.0.0')
        self.assertEqual(name, '@org/pkg')
        self.assertEqual(ver, '1.0.0')

    def test_registry_prefix(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('company:utils')
        self.assertEqual(name, 'utils')
        self.assertEqual(reg, 'company')

    def test_http_url_not_registry(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('http://example.com/pkg')
        self.assertIsNone(reg)

    def test_github_prefix_not_registry(self):
        from epl.package_index import parse_package_spec
        name, ver, reg = parse_package_spec('github:user/repo')
        self.assertIsNone(reg)


class TestMultiRegistry(unittest.TestCase):
    """Tests for MultiRegistry."""

    def test_default_registry(self):
        from epl.package_index import MultiRegistry
        mr = MultiRegistry()
        self.assertIn('default', mr.registry_names())

    def test_add_registry(self):
        from epl.package_index import MultiRegistry, RegistryConfig
        mr = MultiRegistry()
        mr.add_registry(RegistryConfig('company', 'https://git.company.com/index.git'))
        self.assertIn('company', mr.registry_names())

    def test_load_from_manifest(self):
        from epl.package_index import MultiRegistry
        mr = MultiRegistry()
        manifest = {
            'registries': {
                'private': {'url': 'https://private.com/index.git', 'priority': 10},
            }
        }
        mr.load_from_manifest(manifest)
        self.assertIn('private', mr.registry_names())


class TestRegistryConfig(unittest.TestCase):
    """Tests for RegistryConfig."""

    def test_create(self):
        from epl.package_index import RegistryConfig
        rc = RegistryConfig('test', 'https://github.com/test/index.git')
        self.assertEqual(rc.name, 'test')
        self.assertEqual(rc.url, 'https://github.com/test/index.git')

    def test_from_dict_string(self):
        from epl.package_index import RegistryConfig
        rc = RegistryConfig.from_dict('simple', 'https://example.com/idx.git')
        self.assertEqual(rc.name, 'simple')
        self.assertEqual(rc.url, 'https://example.com/idx.git')

    def test_from_dict_map(self):
        from epl.package_index import RegistryConfig
        rc = RegistryConfig.from_dict('corp', {
            'url': 'https://corp.com/idx.git',
            'token_env': 'CORP_TOKEN',
            'priority': 5,
        })
        self.assertEqual(rc.token_env, 'CORP_TOKEN')
        self.assertEqual(rc.priority, 5)

    def test_to_dict(self):
        from epl.package_index import RegistryConfig
        rc = RegistryConfig('x', 'url', token_env='TOK', priority=3)
        d = rc.to_dict()
        self.assertEqual(d['url'], 'url')
        self.assertEqual(d['token_env'], 'TOK')
        self.assertEqual(d['priority'], 3)


class TestBuildIndexFromBuiltin(unittest.TestCase):
    """Tests for build_index_from_builtin_registry."""

    def test_builds_entries(self):
        from epl.package_index import build_index_from_builtin_registry
        entries = build_index_from_builtin_registry()
        self.assertTrue(len(entries) > 0)
        self.assertIn('epl-math', entries)
        entry = entries['epl-math']
        self.assertEqual(entry.name, 'epl-math')
        self.assertTrue(len(entry.versions) > 0)

    def test_all_builtin_covered(self):
        from epl.package_index import build_index_from_builtin_registry
        from epl.package_manager import BUILTIN_REGISTRY
        entries = build_index_from_builtin_registry()
        for name in BUILTIN_REGISTRY:
            self.assertIn(name, entries, f"Missing builtin: {name}")


# ═══════════════════════════════════════════════════════════
#  7c: Resolver Tests
# ═══════════════════════════════════════════════════════════

class TestVersionConstraint(unittest.TestCase):
    """Tests for VersionConstraint."""

    def test_wildcard(self):
        from epl.resolver import VersionConstraint
        from epl.package_manager import SemVer
        vc = VersionConstraint('*')
        self.assertTrue(vc.matches(SemVer(1, 0, 0)))
        self.assertTrue(vc.matches(SemVer(99, 0, 0)))

    def test_exact(self):
        from epl.resolver import VersionConstraint
        from epl.package_manager import SemVer
        vc = VersionConstraint('1.0.0')
        self.assertTrue(vc.matches(SemVer(1, 0, 0)))
        self.assertFalse(vc.matches(SemVer(2, 0, 0)))

    def test_caret(self):
        from epl.resolver import VersionConstraint
        from epl.package_manager import SemVer
        vc = VersionConstraint('^1.0.0')
        self.assertTrue(vc.matches(SemVer(1, 0, 0)))
        self.assertTrue(vc.matches(SemVer(1, 5, 0)))
        self.assertFalse(vc.matches(SemVer(2, 0, 0)))

    def test_tilde(self):
        from epl.resolver import VersionConstraint
        from epl.package_manager import SemVer
        vc = VersionConstraint('~1.2.0')
        self.assertTrue(vc.matches(SemVer(1, 2, 0)))
        self.assertTrue(vc.matches(SemVer(1, 2, 5)))
        self.assertFalse(vc.matches(SemVer(1, 3, 0)))

    def test_equality(self):
        from epl.resolver import VersionConstraint
        self.assertEqual(VersionConstraint('^1.0.0'), VersionConstraint('^1.0.0'))
        self.assertNotEqual(VersionConstraint('^1.0.0'), VersionConstraint('^2.0.0'))

    def test_hash(self):
        from epl.resolver import VersionConstraint
        s = {VersionConstraint('^1.0.0'), VersionConstraint('^1.0.0')}
        self.assertEqual(len(s), 1)


class TestConstraintSet(unittest.TestCase):
    """Tests for ConstraintSet."""

    def test_single_constraint(self):
        from epl.resolver import ConstraintSet, VersionConstraint
        from epl.package_manager import SemVer
        cs = ConstraintSet('pkg')
        cs.add(VersionConstraint('^1.0.0', source='root'))
        self.assertTrue(cs.matches(SemVer(1, 5, 0)))
        self.assertFalse(cs.matches(SemVer(2, 0, 0)))

    def test_multiple_constraints(self):
        from epl.resolver import ConstraintSet, VersionConstraint
        from epl.package_manager import SemVer
        cs = ConstraintSet('pkg')
        cs.add(VersionConstraint('>=1.0.0', source='A'))
        cs.add(VersionConstraint('<2.0.0', source='B'))
        self.assertTrue(cs.matches(SemVer(1, 5, 0)))
        self.assertFalse(cs.matches(SemVer(2, 0, 0)))
        self.assertFalse(cs.matches(SemVer(0, 5, 0)))

    def test_filter_versions(self):
        from epl.resolver import ConstraintSet, VersionConstraint
        from epl.package_manager import SemVer
        cs = ConstraintSet('pkg')
        cs.add(VersionConstraint('^1.0.0'))
        versions = [SemVer(0, 9, 0), SemVer(1, 0, 0), SemVer(1, 5, 0), SemVer(2, 0, 0)]
        filtered = cs.filter_versions(versions)
        self.assertEqual(len(filtered), 2)

    def test_explain_conflict(self):
        from epl.resolver import ConstraintSet, VersionConstraint
        from epl.package_manager import SemVer
        cs = ConstraintSet('pkg')
        cs.add(VersionConstraint('^1.0.0', source='A'))
        cs.add(VersionConstraint('^2.0.0', source='B'))
        explanations = cs.explain_conflict(SemVer(1, 5, 0))
        self.assertTrue(len(explanations) > 0)


class TestResolvedPackage(unittest.TestCase):
    """Tests for ResolvedPackage."""

    def test_create(self):
        from epl.resolver import ResolvedPackage
        rp = ResolvedPackage('pkg', None, '1.0.0', {'a': '1.0.0'}, ['root'])
        self.assertEqual(rp.name, 'pkg')
        self.assertEqual(rp.version_str, '1.0.0')
        self.assertEqual(rp.dependencies, {'a': '1.0.0'})

    def test_to_dict(self):
        from epl.resolver import ResolvedPackage
        rp = ResolvedPackage('pkg', None, '1.0.0')
        d = rp.to_dict()
        self.assertEqual(d['name'], 'pkg')
        self.assertEqual(d['version'], '1.0.0')


class TestResolutionResult(unittest.TestCase):
    """Tests for ResolutionResult."""

    def test_empty_is_success(self):
        from epl.resolver import ResolutionResult
        r = ResolutionResult()
        self.assertTrue(r.success)
        self.assertEqual(r.package_count, 0)

    def test_add_error(self):
        from epl.resolver import ResolutionResult
        r = ResolutionResult()
        r.errors.append("bad")
        self.assertFalse(r.success)

    def test_install_order(self):
        from epl.resolver import ResolutionResult, ResolvedPackage
        r = ResolutionResult()
        r.add_package(ResolvedPackage('b', None, '1.0.0', {'a': '1.0.0'}))
        r.add_package(ResolvedPackage('a', None, '1.0.0'))
        order = r.get_install_order()
        names = [p.name for p in order]
        self.assertEqual(names.index('a'), 0)
        self.assertEqual(names.index('b'), 1)

    def test_to_dict(self):
        from epl.resolver import ResolutionResult, ResolvedPackage
        r = ResolutionResult()
        r.add_package(ResolvedPackage('pkg', None, '1.0.0'))
        d = r.to_dict()
        self.assertIn('pkg', d['packages'])


class TestBuiltinVersionProvider(unittest.TestCase):
    """Tests for BuiltinVersionProvider."""

    def test_get_versions(self):
        from epl.resolver import BuiltinVersionProvider
        p = BuiltinVersionProvider()
        versions = p.get_versions('epl-math')
        self.assertTrue(len(versions) > 0)

    def test_unknown_package(self):
        from epl.resolver import BuiltinVersionProvider
        p = BuiltinVersionProvider()
        versions = p.get_versions('nonexistent-pkg-xyz')
        self.assertEqual(versions, [])

    def test_get_dependencies(self):
        from epl.resolver import BuiltinVersionProvider
        p = BuiltinVersionProvider()
        deps = p.get_dependencies('epl-math', '1.0.0')
        self.assertIsInstance(deps, dict)


class TestCompositeVersionProvider(unittest.TestCase):
    """Tests for CompositeVersionProvider."""

    def test_combines_providers(self):
        from epl.resolver import CompositeVersionProvider, BuiltinVersionProvider
        cp = CompositeVersionProvider()
        cp.add_provider(BuiltinVersionProvider())
        versions = cp.get_versions('epl-math')
        self.assertTrue(len(versions) > 0)

    def test_empty_provider(self):
        from epl.resolver import CompositeVersionProvider
        cp = CompositeVersionProvider()
        versions = cp.get_versions('anything')
        self.assertEqual(versions, [])


class TestDependencyResolver(unittest.TestCase):
    """Tests for the backtracking DependencyResolver."""

    def test_empty_deps(self):
        from epl.resolver import DependencyResolver, BuiltinVersionProvider
        r = DependencyResolver(BuiltinVersionProvider())
        result = r.resolve({})
        self.assertTrue(result.success)
        self.assertEqual(result.package_count, 0)

    def test_single_dep(self):
        from epl.resolver import DependencyResolver, BuiltinVersionProvider
        r = DependencyResolver(BuiltinVersionProvider())
        result = r.resolve({'epl-math': '*'})
        self.assertTrue(result.success)
        self.assertIn('epl-math', result.packages)

    def test_multiple_deps(self):
        from epl.resolver import DependencyResolver, BuiltinVersionProvider
        r = DependencyResolver(BuiltinVersionProvider())
        result = r.resolve({'epl-math': '*', 'epl-http': '*', 'epl-json': '*'})
        self.assertTrue(result.success)
        self.assertEqual(result.package_count, 3)

    def test_caret_constraint(self):
        from epl.resolver import DependencyResolver, BuiltinVersionProvider
        r = DependencyResolver(BuiltinVersionProvider())
        result = r.resolve({'epl-math': '^1.0.0'})
        self.assertTrue(result.success)

    def test_unknown_package_fails(self):
        from epl.resolver import DependencyResolver, BuiltinVersionProvider
        r = DependencyResolver(BuiltinVersionProvider())
        result = r.resolve({'nonexistent-xyz': '*'})
        self.assertFalse(result.success)
        self.assertTrue(len(result.errors) > 0)

    def test_max_iterations_guard(self):
        from epl.resolver import DependencyResolver, VersionProvider
        class InfiniteProvider(VersionProvider):
            def get_versions(self, name):
                from epl.package_manager import SemVer
                return [SemVer(1, 0, 0)]
            def get_dependencies(self, name, version):
                return {'loop-' + name: '*'}

        r = DependencyResolver(InfiniteProvider(), max_iterations=50)
        result = r.resolve({'start': '*'})
        self.assertFalse(result.success)

    def test_backtracking_with_conflict(self):
        """Test backtracking when initial choice leads to conflict."""
        from epl.resolver import DependencyResolver, VersionProvider
        from epl.package_manager import SemVer

        class ConflictProvider(VersionProvider):
            """
            root needs A=* and B=*
            A has 2.0.0 and 1.0.0
            B has 1.0.0
            A@2.0.0 needs C@^2.0.0
            A@1.0.0 needs C@^1.0.0
            B@1.0.0 needs C@^1.0.0
            C has 2.0.0 and 1.0.0
            => A@2.0.0 + B@1.0.0 conflicts on C (^2 vs ^1)
            => backtrack to A@1.0.0 + B@1.0.0 + C@1.0.0
            """
            _versions = {
                'A': [SemVer(1, 0, 0), SemVer(2, 0, 0)],
                'B': [SemVer(1, 0, 0)],
                'C': [SemVer(1, 0, 0), SemVer(2, 0, 0)],
            }
            _deps = {
                ('A', '2.0.0'): {'C': '^2.0.0'},
                ('A', '1.0.0'): {'C': '^1.0.0'},
                ('B', '1.0.0'): {'C': '^1.0.0'},
                ('C', '2.0.0'): {},
                ('C', '1.0.0'): {},
            }

            def get_versions(self, name):
                return list(self._versions.get(name, []))

            def get_dependencies(self, name, version):
                return dict(self._deps.get((name, str(version)), {}))

        r = DependencyResolver(ConflictProvider())
        result = r.resolve({'A': '*', 'B': '*'})
        self.assertTrue(result.success, f"Resolution failed: {result.errors}")
        self.assertIn('A', result.packages)
        self.assertIn('B', result.packages)
        self.assertIn('C', result.packages)
        # A should be 1.0.0 (backtracked from 2.0.0)
        self.assertEqual(result.packages['A'].version_str, '1.0.0')
        self.assertEqual(result.packages['C'].version_str, '1.0.0')

    def test_resolve_install_order(self):
        from epl.resolver import DependencyResolver, VersionProvider
        from epl.package_manager import SemVer

        class OrderProvider(VersionProvider):
            def get_versions(self, name):
                return [SemVer(1, 0, 0)]
            def get_dependencies(self, name, version):
                if name == 'app':
                    return {'lib': '^1.0.0'}
                return {}

        r = DependencyResolver(OrderProvider())
        result = r.resolve({'app': '*'})
        self.assertTrue(result.success)
        order = result.get_install_order()
        names = [p.name for p in order]
        self.assertTrue(names.index('lib') < names.index('app'))


class TestResolveDeps(unittest.TestCase):
    """Tests for resolve_deps convenience function."""

    def test_resolve_builtin(self):
        from epl.resolver import resolve_deps
        result = resolve_deps({'epl-math': '*'})
        self.assertTrue(result.success)

    def test_resolve_empty(self):
        from epl.resolver import resolve_deps
        result = resolve_deps({})
        self.assertTrue(result.success)
        self.assertEqual(result.package_count, 0)


# ═══════════════════════════════════════════════════════════
#  7b: Publisher Tests
# ═══════════════════════════════════════════════════════════

class TestPublishChecks(unittest.TestCase):
    """Tests for pre-publish validation checks."""

    def test_valid_manifest(self):
        from epl.publisher import run_publish_checks
        manifest = {
            'name': 'my-pkg',
            'version': '1.0.0',
            'description': 'A great package',
            'license': 'MIT',
            'repository': 'user/repo',
        }
        with tempfile.TemporaryDirectory() as tmp:
            # Create entry point
            with open(os.path.join(tmp, 'main.epl'), 'w') as f:
                f.write('Display "hello"')
            checks = run_publish_checks(manifest, tmp)
            error_checks = [c for c in checks if not c.passed and c.severity == 'error']
            self.assertEqual(len(error_checks), 0)

    def test_missing_name(self):
        from epl.publisher import run_publish_checks
        manifest = {'version': '1.0.0'}
        checks = run_publish_checks(manifest)
        name_check = [c for c in checks if c.name == 'name']
        self.assertTrue(len(name_check) > 0)
        self.assertFalse(name_check[0].passed)

    def test_invalid_name(self):
        from epl.publisher import run_publish_checks
        manifest = {'name': '123invalid', 'version': '1.0.0'}
        checks = run_publish_checks(manifest)
        name_check = [c for c in checks if c.name == 'name']
        self.assertFalse(name_check[0].passed)

    def test_reserved_name(self):
        from epl.publisher import run_publish_checks
        manifest = {'name': 'epl', 'version': '1.0.0'}
        checks = run_publish_checks(manifest)
        name_check = [c for c in checks if c.name == 'name']
        self.assertFalse(name_check[0].passed)

    def test_missing_version(self):
        from epl.publisher import run_publish_checks
        manifest = {'name': 'valid-pkg'}
        checks = run_publish_checks(manifest)
        ver_check = [c for c in checks if c.name == 'version']
        self.assertFalse(ver_check[0].passed)

    def test_invalid_version(self):
        from epl.publisher import run_publish_checks
        manifest = {'name': 'pkg', 'version': 'not-semver'}
        checks = run_publish_checks(manifest)
        ver_check = [c for c in checks if c.name == 'version']
        self.assertFalse(ver_check[0].passed)

    def test_sensitive_files_detected(self):
        from epl.publisher import run_publish_checks
        manifest = {'name': 'pkg', 'version': '1.0.0'}
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, '.env'), 'w') as f:
                f.write('SECRET=abc')
            checks = run_publish_checks(manifest, tmp)
            sens_check = [c for c in checks if c.name == 'sensitive_files']
            self.assertFalse(sens_check[0].passed)

    def test_scoped_name_valid(self):
        from epl.publisher import run_publish_checks
        manifest = {'name': '@myorg/utils', 'version': '1.0.0'}
        checks = run_publish_checks(manifest)
        name_check = [c for c in checks if c.name == 'name']
        self.assertTrue(name_check[0].passed)


class TestPackForPublish(unittest.TestCase):
    """Tests for pack_for_publish."""

    def test_pack_basic(self):
        from epl.publisher import pack_for_publish
        with tempfile.TemporaryDirectory() as tmp:
            # Create a minimal epl.toml
            toml_path = os.path.join(tmp, 'epl.toml')
            with open(toml_path, 'w') as f:
                f.write('[project]\nname = "test-pkg"\nversion = "1.0.0"\n')
            # Create a source file
            with open(os.path.join(tmp, 'main.epl'), 'w') as f:
                f.write('Display "hello"\n')

            out_dir = os.path.join(tmp, 'dist')
            result = pack_for_publish(tmp, out_dir)
            self.assertIsNotNone(result)
            archive_path, size, checksum = result
            self.assertTrue(os.path.isfile(archive_path))
            self.assertTrue(size > 0)
            self.assertTrue(len(checksum) == 64)

    def test_pack_ignores_git(self):
        from epl.publisher import pack_for_publish
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, 'epl.toml')
            with open(toml_path, 'w') as f:
                f.write('[project]\nname = "pkg"\nversion = "1.0.0"\n')
            with open(os.path.join(tmp, 'main.epl'), 'w') as f:
                f.write('Display "hi"\n')
            # Create a .git dir
            os.makedirs(os.path.join(tmp, '.git'))
            with open(os.path.join(tmp, '.git', 'HEAD'), 'w') as f:
                f.write('ref: refs/heads/main\n')

            out_dir = os.path.join(tmp, 'dist')
            result = pack_for_publish(tmp, out_dir)
            self.assertIsNotNone(result)
            archive_path = result[0]
            with zipfile.ZipFile(archive_path, 'r') as z:
                names = z.namelist()
                # .git should not be included
                git_files = [n for n in names if n.startswith('.git')]
                self.assertEqual(len(git_files), 0)


class TestPublishResult(unittest.TestCase):
    """Tests for PublishResult."""

    def test_empty_result(self):
        from epl.publisher import PublishResult
        r = PublishResult()
        self.assertTrue(r.checks_passed)
        self.assertFalse(r.published)

    def test_checks_passed_with_warnings(self):
        from epl.publisher import PublishResult
        r = PublishResult()
        r.add_check('name', True, 'OK')
        r.add_check('desc', False, 'Missing', severity='warning')
        self.assertTrue(r.checks_passed)

    def test_checks_failed_with_errors(self):
        from epl.publisher import PublishResult
        r = PublishResult()
        r.add_check('name', False, 'Bad name', severity='error')
        self.assertFalse(r.checks_passed)


class TestEnhancedPublish(unittest.TestCase):
    """Tests for enhanced_publish."""

    def test_dry_run(self):
        from epl.publisher import enhanced_publish
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, 'epl.toml')
            with open(toml_path, 'w') as f:
                f.write('[project]\nname = "dry-pkg"\nversion = "1.0.0"\n'
                        'description = "Test"\nlicense = "MIT"\n'
                        'repository = "user/repo"\n')
            with open(os.path.join(tmp, 'main.epl'), 'w') as f:
                f.write('Display "hello"\n')

            result = enhanced_publish(tmp, dry_run=True)
            self.assertIsNotNone(result)
            self.assertFalse(result.published)
            self.assertTrue(len(result.index_pr_content) > 0)

    def test_no_manifest_fails(self):
        from epl.publisher import enhanced_publish
        with tempfile.TemporaryDirectory() as tmp:
            result = enhanced_publish(tmp)
            self.assertEqual(result.error, "No manifest found")


class TestGeneratePublishPrMarkdown(unittest.TestCase):
    """Tests for generate_publish_pr_markdown."""

    def test_generates_markdown(self):
        from epl.publisher import PublishResult, generate_publish_pr_markdown
        r = PublishResult()
        r.add_check('name', True, 'OK')
        r.archive_size = 10240
        r.archive_checksum = 'abc123def456'
        r.index_pr_content = {'packages/pkg/metadata.json': '{}'}
        md = generate_publish_pr_markdown(r, 'pkg', '1.0.0')
        self.assertIn('# Publish pkg@1.0.0', md)
        self.assertIn(':white_check_mark:', md)
        self.assertIn('abc123def456', md)


# ═══════════════════════════════════════════════════════════
#  7e: Workspace Tests
# ═══════════════════════════════════════════════════════════

class TestWorkspaceMember(unittest.TestCase):
    """Tests for WorkspaceMember."""

    def test_create(self):
        from epl.workspace import WorkspaceMember
        m = WorkspaceMember('lib-a', 'packages/lib-a', '1.0.0', {'epl-math': '^1.0.0'})
        self.assertEqual(m.name, 'lib-a')
        self.assertEqual(m.path, 'packages/lib-a')
        self.assertEqual(m.version, '1.0.0')

    def test_to_dict(self):
        from epl.workspace import WorkspaceMember
        m = WorkspaceMember('x', 'p/x', '2.0.0')
        d = m.to_dict()
        self.assertEqual(d['name'], 'x')
        self.assertEqual(d['version'], '2.0.0')


class TestWorkspace(unittest.TestCase):
    """Tests for Workspace."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_workspace(self, members=None):
        """Helper to create a workspace with member packages."""
        members = members or {'lib-a': {}, 'lib-b': {'lib-a': '^1.0.0'}}
        toml = (
            '[project]\n'
            'name = "my-ws"\n'
            'version = "1.0.0"\n'
            '\n'
            '[workspace]\n'
            'members = ["packages/*"]\n'
        )
        with open(os.path.join(self.tmp, 'epl.toml'), 'w') as f:
            f.write(toml)

        for name, deps in members.items():
            pkg_dir = os.path.join(self.tmp, 'packages', name)
            os.makedirs(pkg_dir, exist_ok=True)
            manifest = {'name': name, 'version': '1.0.0', 'dependencies': deps}
            with open(os.path.join(pkg_dir, 'epl.json'), 'w') as f:
                json.dump(manifest, f)
            with open(os.path.join(pkg_dir, 'main.epl'), 'w') as f:
                f.write(f'Display "{name}"\n')

    def test_load_workspace(self):
        self._create_workspace()
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        self.assertTrue(ws.load())
        self.assertTrue(ws.is_workspace)
        self.assertEqual(ws.member_count, 2)

    def test_member_discovery(self):
        self._create_workspace()
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        self.assertIn('lib-a', ws.members)
        self.assertIn('lib-b', ws.members)

    def test_internal_deps(self):
        self._create_workspace()
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        internal = ws.get_internal_deps()
        self.assertIn('lib-b', internal)
        self.assertIn('lib-a', internal['lib-b'])

    def test_build_order(self):
        self._create_workspace()
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        order = ws.get_build_order()
        names = [m.name for m in order]
        self.assertTrue(names.index('lib-a') < names.index('lib-b'))

    def test_get_all_deps(self):
        self._create_workspace({
            'a': {'epl-math': '^1.0.0'},
            'b': {'epl-http': '^1.0.0'},
        })
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        all_deps = ws.get_all_dependencies()
        self.assertIn('epl-math', all_deps)
        self.assertIn('epl-http', all_deps)

    def test_validate_valid_workspace(self):
        self._create_workspace()
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        errors = ws.validate()
        self.assertEqual(len(errors), 0)

    def test_validate_no_members_pattern(self):
        with open(os.path.join(self.tmp, 'epl.toml'), 'w') as f:
            f.write('[project]\nname = "ws"\n[workspace]\nmembers = []\n')
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        errors = ws.validate()
        self.assertTrue(len(errors) > 0)

    def test_no_workspace_config(self):
        with open(os.path.join(self.tmp, 'epl.toml'), 'w') as f:
            f.write('[project]\nname = "not-ws"\nversion = "1.0.0"\n')
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        result = ws.load()
        self.assertFalse(result)
        self.assertFalse(ws.is_workspace)

    def test_cycle_detection(self):
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        # Direct cycle test through the method
        graph = {'a': ['b'], 'b': ['a']}
        self.assertTrue(ws._has_cycle(graph))

    def test_no_cycle(self):
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        graph = {'a': ['b'], 'b': ['c'], 'c': []}
        self.assertFalse(ws._has_cycle(graph))

    def test_to_dict(self):
        self._create_workspace({'pkg': {}})
        from epl.workspace import Workspace
        ws = Workspace(self.tmp)
        ws.load()
        d = ws.to_dict()
        self.assertIn('root', d)
        self.assertIn('members', d)
        self.assertIn('pkg', d['members'])


class TestLoadWorkspace(unittest.TestCase):
    """Tests for load_workspace convenience function."""

    def test_load_nonexistent(self):
        from epl.workspace import load_workspace
        with tempfile.TemporaryDirectory() as tmp:
            result = load_workspace(tmp)
            self.assertIsNone(result)

    def test_load_valid(self):
        from epl.workspace import load_workspace
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "ws"\n[workspace]\nmembers = ["p/*"]\n')
            result = load_workspace(tmp)
            self.assertIsNotNone(result)


class TestInitWorkspace(unittest.TestCase):
    """Tests for init_workspace."""

    def test_init_creates_toml(self):
        from epl.workspace import init_workspace
        with tempfile.TemporaryDirectory() as tmp:
            path = init_workspace(tmp)
            self.assertTrue(os.path.isfile(path))
            with open(path) as f:
                content = f.read()
            self.assertIn('[workspace]', content)

    def test_init_creates_dirs(self):
        from epl.workspace import init_workspace
        with tempfile.TemporaryDirectory() as tmp:
            init_workspace(tmp, ['packages/*', 'apps/*'])
            self.assertTrue(os.path.isdir(os.path.join(tmp, 'packages')))
            self.assertTrue(os.path.isdir(os.path.join(tmp, 'apps')))

    def test_init_adds_to_existing_toml(self):
        from epl.workspace import init_workspace
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "existing"\nversion = "1.0.0"\n')
            init_workspace(tmp)
            with open(os.path.join(tmp, 'epl.toml')) as f:
                content = f.read()
            self.assertIn('[workspace]', content)


# ═══════════════════════════════════════════════════════════
#  7f: CI Generation Tests
# ═══════════════════════════════════════════════════════════

class TestCIWorkflowGeneration(unittest.TestCase):
    """Tests for CI workflow template generation."""

    def test_index_validation_workflow(self):
        from epl.ci_gen import generate_index_validation_workflow
        wf = generate_index_validation_workflow()
        self.assertIn('name:', wf)
        self.assertIn('validate', wf.lower())
        self.assertIn('actions/checkout', wf)
        self.assertIn('python', wf.lower())

    def test_auto_merge_workflow(self):
        from epl.ci_gen import generate_auto_merge_workflow
        wf = generate_auto_merge_workflow()
        self.assertIn('auto-merge', wf.lower())
        self.assertIn('epl-publish-bot', wf)

    def test_package_ci_workflow(self):
        from epl.ci_gen import generate_package_ci_workflow
        wf = generate_package_ci_workflow('my-pkg', '7.0.0')
        self.assertIn('my-pkg', wf)
        self.assertIn('epl install', wf)
        self.assertIn('epl test', wf)
        self.assertIn('epl publish', wf)

    def test_workspace_ci_workflow(self):
        from epl.ci_gen import generate_workspace_ci_workflow
        wf = generate_workspace_ci_workflow('my-ws', ['core', 'utils'])
        self.assertIn('my-ws', wf)
        self.assertIn('core', wf)
        self.assertIn('utils', wf)
        self.assertIn('workspace validate', wf)
        self.assertIn('workspace install', wf)

    def test_validation_script(self):
        from epl.ci_gen import generate_validation_script
        script = generate_validation_script()
        self.assertIn('validate_package_dir', script)
        self.assertIn('metadata.json', script)
        self.assertIn('versions.json', script)
        self.assertIn('SEMVER_RE', script)


class TestCIForProject(unittest.TestCase):
    """Tests for generate_ci_for_project."""

    def test_generate_for_package(self):
        from epl.ci_gen import generate_ci_for_project
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "test-pkg"\nversion = "1.0.0"\n')
            files = generate_ci_for_project(tmp)
            self.assertIn('ci.yml', files)
            self.assertIn('test-pkg', files['ci.yml'])

    def test_generate_for_workspace(self):
        from epl.ci_gen import generate_ci_for_project
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "ws"\n[workspace]\nmembers = ["p/*"]\n')
            pkg_dir = os.path.join(tmp, 'p', 'core')
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, 'epl.json'), 'w') as f:
                json.dump({'name': 'core', 'version': '1.0.0'}, f)
            files = generate_ci_for_project(tmp)
            self.assertIn('ci.yml', files)
            self.assertIn('workspace', files['ci.yml'].lower())


class TestWriteCIFiles(unittest.TestCase):
    """Tests for write_ci_files."""

    def test_write_files(self):
        from epl.ci_gen import write_ci_files
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "ci-test"\nversion = "1.0.0"\n')
            count = write_ci_files(tmp)
            self.assertTrue(count > 0)
            wf_dir = os.path.join(tmp, '.github', 'workflows')
            self.assertTrue(os.path.isdir(wf_dir))

    def test_no_manifest(self):
        from epl.ci_gen import write_ci_files
        with tempfile.TemporaryDirectory() as tmp:
            count = write_ci_files(tmp)
            self.assertEqual(count, 0)


class TestCIForIndex(unittest.TestCase):
    """Tests for generate_ci_for_index."""

    def test_generates_files(self):
        from epl.ci_gen import generate_ci_for_index
        files = generate_ci_for_index()
        self.assertIn('.github/workflows/validate-pr.yml', files)
        self.assertIn('.github/workflows/auto-merge.yml', files)
        self.assertIn('scripts/validate_index.py', files)


# ═══════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════

class TestResolverWithIndex(unittest.TestCase):
    """Integration: resolver + package index."""

    def test_index_provider(self):
        from epl.resolver import IndexVersionProvider
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = os.path.join(tmp, 'cache.json')
            cache = IndexCache(cache_path)
            m = PackageMetadata('test-dep')
            v1 = VersionEntry('1.0.0', dependencies={})
            v2 = VersionEntry('2.0.0', dependencies={})
            cache.set_package('test-dep', PackageIndexEntry(m, [v1, v2]))

            idx = PackageIndex(offline=True, cache=cache)
            provider = IndexVersionProvider(idx)
            versions = provider.get_versions('test-dep')
            self.assertTrue(len(versions) >= 2)

    def test_composite_resolver(self):
        from epl.resolver import (DependencyResolver, CompositeVersionProvider,
                                   BuiltinVersionProvider, IndexVersionProvider)
        from epl.package_index import (PackageIndex, IndexCache, PackageMetadata,
                                        VersionEntry, PackageIndexEntry)
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = os.path.join(tmp, 'cache.json')
            cache = IndexCache(cache_path)
            m = PackageMetadata('custom-lib')
            v = VersionEntry('1.0.0', dependencies={'epl-math': '*'})
            cache.set_package('custom-lib', PackageIndexEntry(m, [v]))

            idx = PackageIndex(offline=True, cache=cache)
            provider = CompositeVersionProvider()
            provider.add_provider(BuiltinVersionProvider())
            provider.add_provider(IndexVersionProvider(idx))

            resolver = DependencyResolver(provider)
            result = resolver.resolve({'custom-lib': '*'})
            self.assertTrue(result.success)
            self.assertIn('custom-lib', result.packages)
            # epl-math should also be resolved (transitive dep)
            self.assertIn('epl-math', result.packages)


class TestPublisherWithIndex(unittest.TestCase):
    """Integration: publisher + package index."""

    def test_dry_run_generates_index_content(self):
        from epl.publisher import enhanced_publish
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "integ-pkg"\nversion = "1.0.0"\n'
                        'description = "Test"\nlicense = "MIT"\n'
                        'repository = "user/repo"\n')
            with open(os.path.join(tmp, 'main.epl'), 'w') as f:
                f.write('Display "hello"\n')

            result = enhanced_publish(tmp, dry_run=True)
            self.assertTrue(len(result.index_pr_content) > 0)
            # Verify metadata.json content
            meta_key = 'packages/integ-pkg/metadata.json'
            self.assertIn(meta_key, result.index_pr_content)
            meta = json.loads(result.index_pr_content[meta_key])
            self.assertEqual(meta['name'], 'integ-pkg')


class TestWorkspaceResolve(unittest.TestCase):
    """Integration: workspace + resolver."""

    def test_workspace_deps_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write('[project]\nname = "ws"\n[workspace]\nmembers = ["p/*"]\n')
            for pkg_name, deps in [('core', {'epl-math': '*'}), ('web', {'epl-http': '*'})]:
                pkg_dir = os.path.join(tmp, 'p', pkg_name)
                os.makedirs(pkg_dir)
                with open(os.path.join(pkg_dir, 'epl.json'), 'w') as f:
                    json.dump({'name': pkg_name, 'version': '1.0.0', 'dependencies': deps}, f)

            from epl.workspace import Workspace
            ws = Workspace(tmp)
            ws.load()
            all_deps = ws.get_all_dependencies()
            self.assertIn('epl-math', all_deps)
            self.assertIn('epl-http', all_deps)


class TestEndToEnd(unittest.TestCase):
    """End-to-end: create project -> resolve -> publish (dry) -> CI."""

    def test_full_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Create manifest
            with open(os.path.join(tmp, 'epl.toml'), 'w') as f:
                f.write(
                    '[project]\n'
                    'name = "e2e-pkg"\n'
                    'version = "1.0.0"\n'
                    'description = "E2E test"\n'
                    'license = "MIT"\n'
                    'repository = "user/e2e"\n'
                    '\n'
                    '[dependencies]\n'
                    'epl-math = "*"\n'
                )
            with open(os.path.join(tmp, 'main.epl'), 'w') as f:
                f.write('Display "e2e"\n')

            # 2. Resolve
            from epl.resolver import resolve_deps, BuiltinVersionProvider
            result = resolve_deps({'epl-math': '*'}, BuiltinVersionProvider())
            self.assertTrue(result.success)

            # 3. Publish (dry run)
            from epl.publisher import enhanced_publish
            pub_result = enhanced_publish(tmp, dry_run=True)
            self.assertTrue(len(pub_result.index_pr_content) > 0)

            # 4. Generate CI
            from epl.ci_gen import generate_ci_for_project
            ci_files = generate_ci_for_project(tmp)
            self.assertIn('ci.yml', ci_files)


# ═══════════════════════════════════════════════════════════
#  CLI Tests
# ═══════════════════════════════════════════════════════════

class TestResolveCommand(unittest.TestCase):
    """Tests for the resolve CLI command."""

    def test_main_py_delegates_to_cli(self):
        """Verify the source entry point delegates to the authoritative CLI."""
        import main as main_module
        import inspect
        source = inspect.getsource(main_module.main)
        self.assertIn("cli_main", source)

    def test_resolve_legacy_dispatcher(self):
        """Verify the resolve command remains available in the legacy dispatcher."""
        import main as main_module
        import inspect
        source = inspect.getsource(main_module.legacy_main)
        self.assertIn("'resolve'", source)

    def test_workspace_legacy_dispatcher(self):
        """Verify the workspace command remains available in the legacy dispatcher."""
        import main as main_module
        import inspect
        source = inspect.getsource(main_module.legacy_main)
        self.assertIn("'workspace'", source)

    def test_ci_legacy_dispatcher(self):
        """Verify the ci command remains available in the legacy dispatcher."""
        import main as main_module
        import inspect
        source = inspect.getsource(main_module.legacy_main)
        self.assertIn("'ci'", source)

    def test_sync_index_legacy_dispatcher(self):
        """Verify the sync-index command remains available in the legacy dispatcher."""
        import main as main_module
        import inspect
        source = inspect.getsource(main_module.legacy_main)
        self.assertIn("'sync-index'", source)


class TestCLICommands(unittest.TestCase):
    """Tests for CLI dispatch table."""

    def test_cli_has_resolve(self):
        from epl.cli import cli_main
        import inspect
        source = inspect.getsource(cli_main)
        self.assertIn("'resolve'", source)

    def test_cli_has_workspace(self):
        from epl.cli import cli_main
        import inspect
        source = inspect.getsource(cli_main)
        self.assertIn("'workspace'", source)

    def test_cli_has_ci(self):
        from epl.cli import cli_main
        import inspect
        source = inspect.getsource(cli_main)
        self.assertIn("'ci'", source)

    def test_cli_has_sync_index(self):
        from epl.cli import cli_main
        import inspect
        source = inspect.getsource(cli_main)
        self.assertIn("'sync-index'", source)


# ═══════════════════════════════════════════════════════════
#  Module Import Tests
# ═══════════════════════════════════════════════════════════

class TestModuleImports(unittest.TestCase):
    """Verify all Phase 7 modules import cleanly."""

    def test_import_package_index(self):
        import epl.package_index
        self.assertTrue(hasattr(epl.package_index, 'PackageIndex'))
        self.assertTrue(hasattr(epl.package_index, 'PackageMetadata'))
        self.assertTrue(hasattr(epl.package_index, 'VersionEntry'))
        self.assertTrue(hasattr(epl.package_index, 'ScopedName'))
        self.assertTrue(hasattr(epl.package_index, 'MultiRegistry'))
        self.assertTrue(hasattr(epl.package_index, 'parse_package_spec'))

    def test_import_resolver(self):
        import epl.resolver
        self.assertTrue(hasattr(epl.resolver, 'DependencyResolver'))
        self.assertTrue(hasattr(epl.resolver, 'VersionConstraint'))
        self.assertTrue(hasattr(epl.resolver, 'ConstraintSet'))
        self.assertTrue(hasattr(epl.resolver, 'ResolutionResult'))
        self.assertTrue(hasattr(epl.resolver, 'BuiltinVersionProvider'))
        self.assertTrue(hasattr(epl.resolver, 'resolve_deps'))

    def test_import_publisher(self):
        import epl.publisher
        self.assertTrue(hasattr(epl.publisher, 'enhanced_publish'))
        self.assertTrue(hasattr(epl.publisher, 'run_publish_checks'))
        self.assertTrue(hasattr(epl.publisher, 'pack_for_publish'))
        self.assertTrue(hasattr(epl.publisher, 'PublishResult'))

    def test_import_workspace(self):
        import epl.workspace
        self.assertTrue(hasattr(epl.workspace, 'Workspace'))
        self.assertTrue(hasattr(epl.workspace, 'WorkspaceMember'))
        self.assertTrue(hasattr(epl.workspace, 'load_workspace'))
        self.assertTrue(hasattr(epl.workspace, 'init_workspace'))

    def test_import_ci_gen(self):
        import epl.ci_gen
        self.assertTrue(hasattr(epl.ci_gen, 'generate_package_ci_workflow'))
        self.assertTrue(hasattr(epl.ci_gen, 'generate_workspace_ci_workflow'))
        self.assertTrue(hasattr(epl.ci_gen, 'generate_ci_for_project'))
        self.assertTrue(hasattr(epl.ci_gen, 'write_ci_files'))


# ═══════════════════════════════════════════════════════════
#  Run all
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    unittest.main(verbosity=2)
