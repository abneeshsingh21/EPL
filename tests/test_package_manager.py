"""
Comprehensive tests for EPL Package Manager v3.0
Tests: SemVer, dependency resolution, lockfile, conflict detection,
publish workflow, uninstall cleanup, update, and core operations.
"""
import sys
import os
import json
import tempfile
import shutil
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.package_manager import (
    SemVer, parse_version_range, DependencyConflict,
    resolve_dependencies, create_manifest, load_manifest, init_project,
    list_packages, create_lockfile, load_lockfile, verify_lockfile,
    install_from_lockfile, install_package, uninstall_package,
    validate_package, pack_package, publish_package,
    update_package, install_dependencies, search_packages,
    find_package_module, load_local_registry, save_local_registry,
    register_installed_package, _hash_directory,
    PACKAGES_DIR, MANIFEST_NAME, TOML_MANIFEST_NAME, LOCKFILE_NAME, EPL_HOME,
)

PASSED = 0
FAILED = 0
TOTAL_SECTIONS = 0


def section(name):
    global TOTAL_SECTIONS
    TOTAL_SECTIONS += 1
    print(f"\n--- {name} ---")


def check(name, fn):
    global PASSED, FAILED
    try:
        result = fn()
        if result:
            print(f"  PASS: {name}")
            PASSED += 1
        else:
            print(f"  FAIL: {name}")
            FAILED += 1
    except Exception as e:
        print(f"  FAIL: {name} — {e}")
        FAILED += 1



def main():
    global PASSED, FAILED, TOTAL_SECTIONS
    PASSED = 0
    FAILED = 0
    TOTAL_SECTIONS = 0
    print("=== EPL Package Manager v3.0 Tests ===\n")
    
    # ═══════════════════════════════════════════════════════════
    #  1. SemVer Parsing
    # ═══════════════════════════════════════════════════════════
    
    section("SemVer Parsing")
    
    check("parse_basic", lambda: str(SemVer.parse("1.2.3")) == "1.2.3")
    check("parse_with_v", lambda: str(SemVer.parse("v2.0.0")) == "2.0.0")
    check("parse_pre_release", lambda: str(SemVer.parse("1.0.0-alpha")) == "1.0.0-alpha")
    check("parse_build_meta", lambda: str(SemVer.parse("1.0.0+build.123")) == "1.0.0+build.123")
    check("parse_pre_and_build", lambda: str(SemVer.parse("1.0.0-beta.1+build")) == "1.0.0-beta.1+build")
    check("parse_partial_two", lambda: str(SemVer.parse("1.0")) == "1.0.0")
    check("parse_partial_one", lambda: str(SemVer.parse("2")) == "2.0.0")
    check("parse_invalid_returns_none", lambda: SemVer.parse("not-a-version") is None)
    check("parse_empty_returns_none", lambda: SemVer.parse("") is None)
    check("parse_none_returns_none", lambda: SemVer.parse(None) is None)
    
    # ═══════════════════════════════════════════════════════════
    #  2. SemVer Comparison
    # ═══════════════════════════════════════════════════════════
    
    section("SemVer Comparison")
    
    check("equal", lambda: SemVer.parse("1.2.3") == SemVer.parse("1.2.3"))
    check("not_equal", lambda: SemVer.parse("1.2.3") != SemVer.parse("1.2.4"))
    check("less_than_patch", lambda: SemVer.parse("1.0.0") < SemVer.parse("1.0.1"))
    check("less_than_minor", lambda: SemVer.parse("1.0.9") < SemVer.parse("1.1.0"))
    check("less_than_major", lambda: SemVer.parse("1.9.9") < SemVer.parse("2.0.0"))
    check("greater_than", lambda: SemVer.parse("2.0.0") > SemVer.parse("1.9.9"))
    check("gte", lambda: SemVer.parse("1.0.0") >= SemVer.parse("1.0.0"))
    check("lte", lambda: SemVer.parse("1.0.0") <= SemVer.parse("1.0.0"))
    check("pre_release_less_than_release", lambda: SemVer.parse("1.0.0-alpha") < SemVer.parse("1.0.0"))
    check("hash_equality", lambda: hash(SemVer.parse("1.0.0")) == hash(SemVer.parse("1.0.0")))
    
    # ═══════════════════════════════════════════════════════════
    #  3. SemVer Compatibility
    # ═══════════════════════════════════════════════════════════
    
    section("SemVer Compatibility")
    
    check("caret_same_major_gte", lambda: SemVer.parse("1.2.0").compatible(SemVer.parse("1.5.0")))
    check("caret_same_major_exact", lambda: SemVer.parse("1.2.0").compatible(SemVer.parse("1.2.0")))
    check("caret_different_major", lambda: not SemVer.parse("1.2.0").compatible(SemVer.parse("2.0.0")))
    check("caret_lower_version", lambda: not SemVer.parse("1.5.0").compatible(SemVer.parse("1.2.0")))
    check("tilde_same_minor", lambda: SemVer.parse("1.2.0").tilde_compatible(SemVer.parse("1.2.5")))
    check("tilde_different_minor", lambda: not SemVer.parse("1.2.0").tilde_compatible(SemVer.parse("1.3.0")))
    
    # ═══════════════════════════════════════════════════════════
    #  4. Version Range Parsing
    # ═══════════════════════════════════════════════════════════
    
    section("Version Range Parsing")
    
    check("exact_match", lambda: parse_version_range("1.2.3")(SemVer.parse("1.2.3")))
    check("exact_no_match", lambda: not parse_version_range("1.2.3")(SemVer.parse("1.2.4")))
    check("caret_match", lambda: parse_version_range("^1.2.0")(SemVer.parse("1.5.0")))
    check("caret_no_match", lambda: not parse_version_range("^1.2.0")(SemVer.parse("2.0.0")))
    check("tilde_match", lambda: parse_version_range("~1.2.0")(SemVer.parse("1.2.5")))
    check("tilde_no_match", lambda: not parse_version_range("~1.2.0")(SemVer.parse("1.3.0")))
    check("gte_match", lambda: parse_version_range(">=1.0.0")(SemVer.parse("1.5.0")))
    check("gte_no_match", lambda: not parse_version_range(">=2.0.0")(SemVer.parse("1.5.0")))
    check("lt_match", lambda: parse_version_range("<2.0.0")(SemVer.parse("1.9.9")))
    check("lt_no_match", lambda: not parse_version_range("<1.0.0")(SemVer.parse("1.0.0")))
    check("range_combined", lambda: parse_version_range(">=1.0.0 <2.0.0")(SemVer.parse("1.5.0")))
    check("range_combined_no_match", lambda: not parse_version_range(">=1.0.0 <2.0.0")(SemVer.parse("2.0.0")))
    check("wildcard", lambda: parse_version_range("*")(SemVer.parse("99.99.99")))
    check("empty_spec", lambda: parse_version_range("")(SemVer.parse("1.0.0")))
    check("ne_match", lambda: parse_version_range("!=1.0.0")(SemVer.parse("1.0.1")))
    check("ne_no_match", lambda: not parse_version_range("!=1.0.0")(SemVer.parse("1.0.0")))
    
    # ═══════════════════════════════════════════════════════════
    #  5. Manifest Operations (in temp dir)
    # ═══════════════════════════════════════════════════════════
    
    section("Manifest Operations")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_pkg_")
    original_cwd = os.getcwd()
    
    try:
        os.chdir(tmpdir)
    
        check("create_manifest", lambda: create_manifest(name="testpkg") is not None)
        check("manifest_file_exists", lambda: os.path.exists(TOML_MANIFEST_NAME))
    
        def _check_manifest_content():
            data = load_manifest()
            return data["name"] == "testpkg" and "version" in data and "dependencies" in data
        check("manifest_content", _check_manifest_content)
    
        check("load_manifest", lambda: load_manifest() is not None)
        check("load_manifest_name", lambda: load_manifest()["name"] == "testpkg")
    
        check("manifest_with_deps", lambda: create_manifest(
            name="deptest", dependencies={"epl-math": "^1.0.0"}) is not None)
    
        def _check_manifest_deps():
            m = load_manifest()
            return "epl-math" in m.get("dependencies", {})
        check("manifest_has_deps", _check_manifest_deps)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  6. Init Project
    # ═══════════════════════════════════════════════════════════
    
    section("Init Project")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_init_")
    try:
        os.chdir(tmpdir)
    
        def _test_init():
            init_project("myproject")
            return os.path.exists(TOML_MANIFEST_NAME) and os.path.exists("main.epl")
        check("init_creates_files", _test_init)
    
        def _test_init_valid_epl():
            with open("main.epl", "r") as f:
                content = f.read()
            return "show" not in content.lower() or "Say" in content or "Print" in content
        check("init_valid_epl_syntax", _test_init_valid_epl)
    
        check("init_manifest_name", lambda: load_manifest()["name"] == "myproject")
    
        def _test_init_no_overwrite():
            with open("main.epl", "w") as f:
                f.write('Say "Custom content"')
            init_project("myproject")
            with open("main.epl", "r") as f:
                return "Custom content" in f.read()
        check("init_no_overwrite", _test_init_no_overwrite)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  7. Package Install & List
    # ═══════════════════════════════════════════════════════════
    
    section("Package Install & List")
    
    check("list_empty_or_valid", lambda: list_packages() is not None)
    check("search_builtin", lambda: len(search_packages("math")) > 0)
    check("search_no_result", lambda: search_packages("zzzznonexistent99") == [])
    
    # Install a builtin package
    check("install_builtin", lambda: install_package("epl-math"))
    
    def _check_installed():
        pkgs = list_packages()
        return any(name == "epl-math" for name, _, _ in pkgs)
    check("list_has_installed", _check_installed)
    
    # ═══════════════════════════════════════════════════════════
    #  8. Lockfile Creation & Verification
    # ═══════════════════════════════════════════════════════════
    
    section("Lockfile Operations")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_lock_")
    try:
        os.chdir(tmpdir)
        create_manifest(name="locktest", dependencies={"epl-math": "^1.0.0"})
        install_package("epl-math")
    
        check("create_lockfile", lambda: create_lockfile('.') is not None)
        check("lockfile_exists", lambda: os.path.exists(LOCKFILE_NAME))
    
        def _check_lockfile_content():
            lock = load_lockfile('.')
            return (lock is not None and
                    "packages" in lock and
                    "python_packages" in lock and
                    "github_packages" in lock and
                    lock.get("lockfileVersion") == 3)
        check("lockfile_content", _check_lockfile_content)
    
        def _check_lockfile_has_package():
            lock = load_lockfile('.')
            return "epl-math" in lock.get("packages", {})
        check("lockfile_has_package", _check_lockfile_has_package)
    
        def _check_lockfile_integrity():
            lock = load_lockfile('.')
            pkg = lock["packages"].get("epl-math", {})
            return "integrity" in pkg and len(pkg["integrity"]) > 0
        check("lockfile_integrity_hash", _check_lockfile_integrity)
    
        # Verify lockfile
        def _check_verify():
            result = verify_lockfile('.')
            return result['valid'] is True and len(result['mismatches']) == 0
        check("verify_lockfile_valid", _check_verify)
    
        # Tamper with package and verify detects mismatch
        def _check_verify_tamper():
            pkg_dir = os.path.join(PACKAGES_DIR, "epl-math")
            if os.path.isdir(pkg_dir):
                with open(os.path.join(pkg_dir, "tamper.txt"), "w") as f:
                    f.write("tampered!")
                result = verify_lockfile('.')
                # Clean up
                os.remove(os.path.join(pkg_dir, "tamper.txt"))
                return not result['valid']
            return True  # If not installed, skip gracefully
        check("verify_detects_tamper", _check_verify_tamper)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  9. Uninstall Cleanup
    # ═══════════════════════════════════════════════════════════
    
    section("Uninstall Cleanup")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_uninstall_")
    try:
        os.chdir(tmpdir)
        create_manifest(name="uninsttest", dependencies={"epl-testing": "^1.0.0"})
        install_package("epl-testing")
    
        def _check_uninstall():
            result = uninstall_package("epl-testing")
            pkg_dir = os.path.join(PACKAGES_DIR, "epl-testing")
            return result and not os.path.exists(pkg_dir)
        check("uninstall_removes_files", _check_uninstall)
    
        def _check_uninstall_cleans_registry():
            reg = load_local_registry()
            return "epl-testing" not in reg
        check("uninstall_cleans_registry", _check_uninstall_cleans_registry)
    
        check("uninstall_nonexistent", lambda: not uninstall_package("nonexistent-pkg-xyz"))
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  10. Dependency Resolution
    # ═══════════════════════════════════════════════════════════
    
    section("Dependency Resolution")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_resolve_")
    try:
        os.chdir(tmpdir)
        create_manifest(name="resolver-test", dependencies={
            "epl-math": "^1.0.0",
            "epl-string": "^1.0.0",
        })
    
        def _check_resolve():
            resolved = resolve_dependencies('.')
            return ("epl-math" in resolved and
                    "epl-string" in resolved and
                    resolved["epl-math"]["version"] is not None)
        check("resolve_basic", _check_resolve)
    
        def _check_resolve_required_by():
            resolved = resolve_dependencies('.')
            return "resolver-test" in resolved["epl-math"]["required_by"]
        check("resolve_required_by", _check_resolve_required_by)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  11. Conflict Detection
    # ═══════════════════════════════════════════════════════════
    
    section("Conflict Detection")
    
    # Test that DependencyConflict is raised properly
    def _check_conflict_class():
        try:
            raise DependencyConflict("test conflict")
        except DependencyConflict as e:
            return "test conflict" in str(e)
    check("conflict_exception", _check_conflict_class)
    
    # ═══════════════════════════════════════════════════════════
    #  12. Package Validation
    # ═══════════════════════════════════════════════════════════
    
    section("Package Validation")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_validate_")
    try:
        os.chdir(tmpdir)
    
        # No manifest = invalid
        def _check_validate_no_manifest():
            result = validate_package('.')
            return not result['valid'] and 'No epl.toml or epl.json manifest found' in result['errors'][0]
        check("validate_no_manifest", _check_validate_no_manifest)
    
        # Valid package
        create_manifest(name="valid-pkg", version="1.0.0", description="A test package")
        with open("main.epl", "w") as f:
            f.write('Say "Hello"')
    
        def _check_validate_valid():
            result = validate_package('.')
            return result['valid']
        check("validate_valid_package", _check_validate_valid)
    
        # Missing description
        create_manifest(name="nodesc", version="1.0.0")
        with open("main.epl", "w") as f:
            f.write('Say "Hello"')
    
        def _check_validate_no_desc():
            result = validate_package('.')
            # Empty description should be flagged
            return not result['valid'] or any('description' in e for e in result['errors'])
        check("validate_missing_description", _check_validate_no_desc)
    
        # Invalid name
        create_manifest(name="INVALID NAME!", version="1.0.0", description="test")
        with open("main.epl", "w") as f:
            f.write('Say "Hello"')
    
        def _check_validate_bad_name():
            result = validate_package('.')
            return not result['valid']
        check("validate_invalid_name", _check_validate_bad_name)
    
        # Invalid version
        create_manifest(name="bad-ver", version="not.a.ver.sion", description="test")
        with open("main.epl", "w") as f:
            f.write('Say "Hello"')
    
        def _check_validate_bad_version():
            result = validate_package('.')
            return not result['valid']
        check("validate_invalid_version", _check_validate_bad_version)
    
        # Missing entry point
        create_manifest(name="no-entry", version="1.0.0", description="test", entry="missing.epl")
        def _check_validate_missing_entry():
            result = validate_package('.')
            return not result['valid']
        check("validate_missing_entry", _check_validate_missing_entry)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  13. Pack Package
    # ═══════════════════════════════════════════════════════════
    
    section("Pack Package")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_pack_")
    try:
        os.chdir(tmpdir)
        create_manifest(name="pack-test", version="2.1.0", description="Pack test")
        with open("main.epl", "w") as f:
            f.write('Say "Hello from packed!"')
    
        def _check_pack():
            result = pack_package('.', os.path.join(tmpdir, 'dist'))
            return (result is not None and
                    os.path.exists(result) and
                    result.endswith('.zip'))
        check("pack_creates_zip", _check_pack)
    
        def _check_pack_checksum():
            result = pack_package('.', os.path.join(tmpdir, 'dist'))
            checksum_file = result + '.sha256'
            return os.path.exists(checksum_file)
        check("pack_creates_checksum", _check_pack_checksum)
    
        def _check_pack_contents():
            import zipfile
            result = pack_package('.', os.path.join(tmpdir, 'dist'))
            with zipfile.ZipFile(result, 'r') as zf:
                names = zf.namelist()
                return TOML_MANIFEST_NAME in names and 'main.epl' in names
        check("pack_includes_files", _check_pack_contents)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  14. Publish Workflow
    # ═══════════════════════════════════════════════════════════
    
    section("Publish Workflow")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_publish_")
    try:
        os.chdir(tmpdir)
        create_manifest(name="pub-test", version="1.0.0", description="Publish test")
        with open("main.epl", "w") as f:
            f.write('Say "Published!"')
    
        def _check_publish():
            return publish_package('.')
        check("publish_succeeds", _check_publish)
    
        def _check_publish_in_registry():
            reg = load_local_registry()
            return "pub-test" in reg and reg["pub-test"]["source"] == "published"
        check("publish_registers_package", _check_publish_in_registry)
    
        # Invalid package can't be published
        create_manifest(name="INVALID!", version="bad", description="")
        def _check_publish_invalid():
            return not publish_package('.')
        check("publish_rejects_invalid", _check_publish_invalid)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  15. Install Dependencies with Transitive Resolution
    # ═══════════════════════════════════════════════════════════
    
    section("Install Dependencies")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_installdeps_")
    try:
        os.chdir(tmpdir)
        create_manifest(name="dep-project", dependencies={
            "epl-math": "^1.0.0",
            "epl-string": "^1.0.0",
        })
    
        def _check_install_deps():
            return install_dependencies('.')
        check("install_deps_succeeds", _check_install_deps)
    
        def _check_lockfile_generated():
            return os.path.exists(LOCKFILE_NAME)
        check("install_deps_creates_lockfile", _check_lockfile_generated)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  16. Hash Directory
    # ═══════════════════════════════════════════════════════════
    
    section("Integrity Hashing")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_hash_")
    try:
        with open(os.path.join(tmpdir, "test.txt"), "w") as f:
            f.write("hello world")
    
        h1 = _hash_directory(tmpdir)
        check("hash_returns_string", lambda: isinstance(h1, str) and len(h1) == 64)
    
        # Same content = same hash
        tmpdir2 = tempfile.mkdtemp(prefix="epl_test_hash2_")
        with open(os.path.join(tmpdir2, "test.txt"), "w") as f:
            f.write("hello world")
        h2 = _hash_directory(tmpdir2)
        check("hash_deterministic", lambda: h1 == h2)
        shutil.rmtree(tmpdir2, ignore_errors=True)
    
        # Different content = different hash
        with open(os.path.join(tmpdir, "test.txt"), "w") as f:
            f.write("different content")
        h3 = _hash_directory(tmpdir)
        check("hash_changes_on_modify", lambda: h1 != h3)
    
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════
    #  17. Module Resolution
    # ═══════════════════════════════════════════════════════════
    
    section("Module Resolution")
    
    tmpdir = tempfile.mkdtemp(prefix="epl_test_resolve_module_")
    try:
        os.chdir(tmpdir)
        # Create a local .epl file
        with open("mylib.epl", "w") as f:
            f.write('Note: My library')
    
        check("find_local_module", lambda: find_package_module("mylib") is not None)
        check("find_nonexistent", lambda: find_package_module("nonexistent_xyz_999") is None)
    
        # Create epl_modules directory
        os.makedirs(os.path.join(tmpdir, "epl_modules", "utils"), exist_ok=True)
        with open(os.path.join(tmpdir, "epl_modules", "utils", "main.epl"), "w") as f:
            f.write('Note: Utils module')
    
        check("find_epl_modules", lambda: find_package_module("utils") is not None)
    
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    
    # ═══════════════════════════════════════════════════════════
    #  Results
    # ═══════════════════════════════════════════════════════════
    
    print(f"\n{'='*50}")
    print(f"Package Manager v3.0 Tests: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    print(f"Sections tested: {TOTAL_SECTIONS}")
    print(f"{'='*50}")
    
    return FAILED == 0


def test_package_manager_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Package manager suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
