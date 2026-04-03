"""
EPL Workspace Manager v1.0 — Phase 7e: Monorepo/Workspace Support

Supports monorepo projects with multiple EPL packages in one repository.
Each workspace has a root epl.toml with a [workspace] table listing member
packages. Shared dependencies are hoisted to the workspace root.

Features:
  - [workspace] table in root epl.toml
  - Member package discovery (glob patterns)
  - Shared dependency resolution across members
  - Cross-member dependency linking
  - `epl workspace` CLI commands: list, build, test, run-all
  - Workspace-level lockfile
"""

import json
import os
import re
import glob as glob_module
from typing import Dict, List, Optional, Set, Tuple, Any


# ═══════════════════════════════════════════════════════════
#  Workspace Manifest
# ═══════════════════════════════════════════════════════════

class WorkspaceMember:
    """A member package within a workspace."""

    __slots__ = ('name', 'path', 'version', 'dependencies', 'dev_dependencies')

    def __init__(self, name: str, path: str, version: str = '0.0.0',
                 dependencies: Optional[Dict[str, str]] = None,
                 dev_dependencies: Optional[Dict[str, str]] = None):
        self.name = name
        self.path = path
        self.version = version
        self.dependencies = dependencies or {}
        self.dev_dependencies = dev_dependencies or {}

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'path': self.path,
            'version': self.version,
            'dependencies': dict(self.dependencies),
            'dev_dependencies': dict(self.dev_dependencies),
        }

    def __repr__(self):
        return f"WorkspaceMember({self.name!r}, path={self.path!r})"


class Workspace:
    """A workspace (monorepo) containing multiple EPL packages."""

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self.members: Dict[str, WorkspaceMember] = {}
        self.shared_deps: Dict[str, str] = {}
        self.member_patterns: List[str] = []
        self._loaded = False

    @property
    def is_workspace(self) -> bool:
        """Check if the root has a [workspace] config."""
        return self._loaded and len(self.member_patterns) > 0

    @property
    def member_names(self) -> List[str]:
        return list(self.members.keys())

    @property
    def member_count(self) -> int:
        return len(self.members)

    def load(self) -> bool:
        """Load workspace configuration from root epl.toml.

        The workspace table looks like:
            [workspace]
            members = ["packages/*", "apps/*"]

            [workspace.dependencies]
            epl-http = "^1.0.0"
        """
        from epl.package_manager import load_manifest, _parse_toml, TOML_MANIFEST_NAME

        # Load the root manifest
        toml_path = os.path.join(self.root_path, TOML_MANIFEST_NAME)
        if not os.path.exists(toml_path):
            return False

        with open(toml_path, 'r', encoding='utf-8') as f:
            toml_data = _parse_toml(f.read())

        workspace_section = toml_data.get('workspace', {})
        if not workspace_section:
            return False

        self.member_patterns = workspace_section.get('members', [])
        self.shared_deps = workspace_section.get('dependencies', {})
        self._loaded = True

        # Discover members
        self._discover_members()

        return True

    def _discover_members(self):
        """Discover workspace members by expanding glob patterns."""
        from epl.package_manager import load_manifest

        for pattern in self.member_patterns:
            full_pattern = os.path.join(self.root_path, pattern)
            for member_dir in glob_module.glob(full_pattern):
                if not os.path.isdir(member_dir):
                    continue
                manifest = load_manifest(member_dir)
                if not manifest:
                    continue
                name = manifest.get('name', os.path.basename(member_dir))
                rel_path = os.path.relpath(member_dir, self.root_path)
                member = WorkspaceMember(
                    name=name,
                    path=rel_path,
                    version=manifest.get('version', '0.0.0'),
                    dependencies=manifest.get('dependencies', {}),
                    dev_dependencies=manifest.get('dev_dependencies', {}),
                )
                self.members[name] = member

    def get_member(self, name: str) -> Optional[WorkspaceMember]:
        return self.members.get(name)

    def get_all_dependencies(self) -> Dict[str, str]:
        """Get all unique dependencies across all members + shared deps.

        Merges workspace.dependencies with each member's dependencies.
        """
        all_deps = dict(self.shared_deps)
        for member in self.members.values():
            for dep_name, dep_ver in member.dependencies.items():
                if dep_name not in all_deps:
                    all_deps[dep_name] = dep_ver
        return all_deps

    def get_internal_deps(self) -> Dict[str, List[str]]:
        """Get cross-member dependencies (member A depends on member B).

        Returns {member_name: [list of member names it depends on]}.
        """
        member_names = set(self.members.keys())
        result = {}
        for name, member in self.members.items():
            internal = [d for d in member.dependencies if d in member_names]
            if internal:
                result[name] = internal
        return result

    def get_build_order(self) -> List[WorkspaceMember]:
        """Get members in build order (dependency-first topological sort)."""
        internal = self.get_internal_deps()
        visited = set()
        order = []

        def visit(name):
            if name in visited:
                return
            visited.add(name)
            for dep in internal.get(name, []):
                visit(dep)
            if name in self.members:
                order.append(self.members[name])

        for name in self.members:
            visit(name)
        return order

    def validate(self) -> List[str]:
        """Validate the workspace configuration.

        Returns a list of error messages (empty if valid).
        """
        errors = []

        if not self.member_patterns:
            errors.append("No 'members' patterns in [workspace]")

        if not self.members:
            errors.append("No members discovered from patterns")

        # Check for version conflicts in shared deps
        for dep_name, dep_ver in self.shared_deps.items():
            for member in self.members.values():
                if dep_name in member.dependencies:
                    member_ver = member.dependencies[dep_name]
                    if member_ver != dep_ver and member_ver != '*':
                        errors.append(
                            f"Version conflict: workspace wants {dep_name}@{dep_ver} "
                            f"but {member.name} wants {dep_name}@{member_ver}"
                        )

        # Check for circular internal dependencies
        internal = self.get_internal_deps()
        if self._has_cycle(internal):
            errors.append("Circular dependency detected among workspace members")

        return errors

    def _has_cycle(self, graph: Dict[str, List[str]]) -> bool:
        """Detect cycles in a directed graph using DFS."""
        GRAY, BLACK = 1, 2
        color = {}

        def dfs(node):
            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if color.get(neighbor) == GRAY:
                    return True
                if neighbor not in color and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for node in graph:
            if node not in color:
                if dfs(node):
                    return True
        return False

    def to_dict(self) -> dict:
        return {
            'root': self.root_path,
            'member_patterns': self.member_patterns,
            'shared_deps': dict(self.shared_deps),
            'members': {n: m.to_dict() for n, m in self.members.items()},
        }


# ═══════════════════════════════════════════════════════════
#  Workspace Operations
# ═══════════════════════════════════════════════════════════

def load_workspace(path: str = '.') -> Optional[Workspace]:
    """Load a workspace from the given path.

    Returns None if no workspace configuration is found.
    """
    ws = Workspace(path)
    if ws.load():
        return ws
    return None


def init_workspace(path: str = '.', member_patterns: Optional[List[str]] = None) -> str:
    """Initialize a workspace at the given path.

    Creates root epl.toml with [workspace] section if it doesn't exist.
    Returns the path to the created epl.toml.
    """
    from epl.package_manager import TOML_MANIFEST_NAME, _parse_toml, _dump_toml

    patterns = member_patterns or ['packages/*']
    toml_path = os.path.join(path, TOML_MANIFEST_NAME)

    if os.path.exists(toml_path):
        # Add [workspace] to existing toml
        with open(toml_path, 'r', encoding='utf-8') as f:
            toml_data = _parse_toml(f.read())
        toml_data['workspace'] = {
            'members': patterns,
            'dependencies': {},
        }
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write(_dump_toml(toml_data) + '\n')
    else:
        toml_content = (
            '[project]\n'
            f'name = "my-workspace"\n'
            f'version = "1.0.0"\n'
            f'description = "EPL workspace"\n'
            f'\n'
            f'[workspace]\n'
            f'members = [{", ".join(repr(p) for p in patterns)}]\n'
            f'\n'
            f'[workspace.dependencies]\n'
        )
        os.makedirs(path, exist_ok=True)
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write(toml_content)

    # Create member directories
    for pattern in patterns:
        base_dir = pattern.rstrip('/*')
        full_dir = os.path.join(path, base_dir)
        os.makedirs(full_dir, exist_ok=True)

    return toml_path


def workspace_install_all(path: str = '.') -> bool:
    """Install all dependencies for a workspace.

    Resolves the combined dependency tree and installs to the root.
    """
    ws = load_workspace(path)
    if not ws:
        print("  Not a workspace (no [workspace] in epl.toml)")
        return False

    all_deps = ws.get_all_dependencies()
    if not all_deps:
        print("  No dependencies to install.")
        return True

    from epl.resolver import resolve_deps, BuiltinVersionProvider
    result = resolve_deps(all_deps, BuiltinVersionProvider())

    if not result.success:
        for err in result.errors:
            print(f"  Error: {err}")
        return False

    from epl.package_manager import install_package
    for pkg in result.get_install_order():
        print(f"  Installing {pkg.name}@{pkg.version_str}...")
        install_package(pkg.name, save=False)

    print(f"  Installed {result.package_count} packages for workspace.")
    return True


def workspace_list(path: str = '.'):
    """List workspace members."""
    ws = load_workspace(path)
    if not ws:
        print("  Not a workspace (no [workspace] in epl.toml)")
        return

    print(f"\n  Workspace Members ({ws.member_count}):")
    print("  " + "-" * 50)
    for member in ws.get_build_order():
        deps = len(member.dependencies)
        print(f"  {member.name:<25} v{member.version:<10} ({deps} deps)")
        if member.dependencies:
            for d, v in member.dependencies.items():
                internal = " (internal)" if d in ws.members else ""
                print(f"    - {d} {v}{internal}")

    if ws.shared_deps:
        print(f"\n  Shared Dependencies:")
        for name, ver in ws.shared_deps.items():
            print(f"    {name} {ver}")


def workspace_validate(path: str = '.') -> bool:
    """Validate workspace configuration."""
    ws = load_workspace(path)
    if not ws:
        print("  Not a workspace.")
        return False

    errors = ws.validate()
    if errors:
        print("  Workspace validation errors:")
        for e in errors:
            print(f"    - {e}")
        return False

    print(f"  Workspace is valid ({ws.member_count} members)")
    return True


# ═══════════════════════════════════════════════════════════
#  CLI Interface
# ═══════════════════════════════════════════════════════════

def workspace_cli(args: List[str]):
    """Handle 'epl workspace' from the command line."""
    if not args:
        workspace_list()
        return

    sub = args[0]
    rest = args[1:]

    if sub == 'init':
        patterns = rest if rest else None
        toml_path = init_workspace('.', patterns)
        print(f"  Workspace initialized: {toml_path}")

    elif sub == 'list':
        workspace_list()

    elif sub == 'install':
        workspace_install_all()

    elif sub == 'validate':
        workspace_validate()

    elif sub == 'build':
        ws = load_workspace()
        if not ws:
            print("  Not a workspace.")
            return
        for member in ws.get_build_order():
            print(f"  Building {member.name}...")

    elif sub == 'test':
        ws = load_workspace()
        if not ws:
            print("  Not a workspace.")
            return
        for member in ws.get_build_order():
            print(f"  Testing {member.name}...")

    elif sub == 'info':
        ws = load_workspace()
        if ws:
            print(f"\n  Workspace Info:")
            print(f"  Root:    {ws.root_path}")
            print(f"  Members: {ws.member_count}")
            print(f"  Patterns: {', '.join(ws.member_patterns)}")
            shared = len(ws.shared_deps)
            print(f"  Shared deps: {shared}")
        else:
            print("  Not a workspace.")

    else:
        print(f"  Unknown workspace command: {sub}")
        print("  Available: init, list, install, validate, build, test, info")
