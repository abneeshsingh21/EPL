"""
EPL Dependency Resolver v1.0 — Phase 7c: Backtracking Resolver

A production-grade dependency resolver using backtracking search with
constraint propagation. Replaces the naive _resolve_best_version approach.

Algorithm: PubGrub-inspired (same approach as Dart/Pub, Cargo, Poetry)
  1. Take the root package's dependencies as initial constraints
  2. For each unresolved dependency, select the best candidate version
  3. Add the candidate's own dependencies as new constraints
  4. If a conflict is detected, backtrack and try the next candidate
  5. Repeat until all dependencies are resolved or all options exhausted

Features:
  - Version constraint intersection and conflict detection
  - Backtracking with intelligent choice ordering
  - Cycle detection
  - Detailed error messages with conflict explanation
  - Support for pre-release versions
  - Integration with PackageIndex for version listing
"""

import re
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


# ═══════════════════════════════════════════════════════════
#  Version Constraint System
# ═══════════════════════════════════════════════════════════

class VersionConstraint:
    """A version constraint (requirement) from one package on another.

    Examples: '^1.0.0', '>=2.0.0 <3.0.0', '~1.5.0', '*', '1.2.3'
    """

    def __init__(self, spec: str, source: str = 'root'):
        self.spec = spec.strip() if spec else '*'
        self.source = source
        self._matcher = None

    @property
    def matcher(self):
        if self._matcher is None:
            from epl.package_manager import parse_version_range
            self._matcher = parse_version_range(self.spec)
        return self._matcher

    def matches(self, version) -> bool:
        """Check if a SemVer version satisfies this constraint."""
        return self.matcher(version)

    def __repr__(self):
        return f"VersionConstraint({self.spec!r}, source={self.source!r})"

    def __str__(self):
        return self.spec

    def __eq__(self, other):
        if isinstance(other, VersionConstraint):
            return self.spec == other.spec
        return NotImplemented

    def __hash__(self):
        return hash(self.spec)


class ConstraintSet:
    """A set of constraints on a single package from multiple sources."""

    def __init__(self, package_name: str):
        self.package_name = package_name
        self.constraints: List[VersionConstraint] = []

    def add(self, constraint: VersionConstraint):
        self.constraints.append(constraint)

    def matches(self, version) -> bool:
        """Check if a version satisfies ALL constraints."""
        return all(c.matches(version) for c in self.constraints)

    def filter_versions(self, versions: list) -> list:
        """Filter a list of SemVer objects to only those matching all constraints."""
        return [v for v in versions if self.matches(v)]

    def is_empty(self) -> bool:
        return len(self.constraints) == 0

    def explain_conflict(self, version) -> List[str]:
        """Return list of constraints that reject a version."""
        return [
            f"  {c.source} requires {self.package_name} {c.spec}"
            for c in self.constraints if not c.matches(version)
        ]

    def __repr__(self):
        specs = ', '.join(str(c) for c in self.constraints)
        return f"ConstraintSet({self.package_name}: {specs})"


# ═══════════════════════════════════════════════════════════
#  Resolution Result
# ═══════════════════════════════════════════════════════════

class ResolvedPackage:
    """A successfully resolved package with its version."""

    __slots__ = ('name', 'version', 'version_str', 'dependencies',
                 'required_by', 'source')

    def __init__(self, name: str, version, version_str: str = '',
                 dependencies: Optional[Dict[str, str]] = None,
                 required_by: Optional[List[str]] = None,
                 source: str = ''):
        self.name = name
        self.version = version
        self.version_str = version_str or str(version)
        self.dependencies = dependencies or {}
        self.required_by = required_by or []
        self.source = source

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'version': self.version_str,
            'dependencies': dict(self.dependencies),
            'required_by': list(self.required_by),
            'source': self.source,
        }

    def __repr__(self):
        return f"ResolvedPackage({self.name}@{self.version_str})"


class ResolutionResult:
    """The complete result of dependency resolution."""

    def __init__(self):
        self.packages: Dict[str, ResolvedPackage] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def package_count(self) -> int:
        return len(self.packages)

    def add_package(self, pkg: ResolvedPackage):
        self.packages[pkg.name] = pkg

    def get_install_order(self) -> List[ResolvedPackage]:
        """Return packages in dependency-first order (topological sort)."""
        visited = set()
        order = []

        def visit(name):
            if name in visited:
                return
            visited.add(name)
            pkg = self.packages.get(name)
            if pkg:
                for dep_name in pkg.dependencies:
                    if dep_name in self.packages:
                        visit(dep_name)
                order.append(pkg)

        for name in self.packages:
            visit(name)
        return order

    def to_dict(self) -> dict:
        return {
            'packages': {n: p.to_dict() for n, p in self.packages.items()},
            'errors': self.errors,
            'warnings': self.warnings,
        }


# ═══════════════════════════════════════════════════════════
#  Version Provider — Abstract interface
# ═══════════════════════════════════════════════════════════

class VersionProvider:
    """Provides available versions and dependency info for packages.

    Can be backed by the PackageIndex, BUILTIN_REGISTRY, or local installs.
    """

    def get_versions(self, name: str) -> list:
        """Return a list of SemVer objects for all available versions.

        Ordered from oldest to newest.
        """
        raise NotImplementedError

    def get_dependencies(self, name: str, version) -> Dict[str, str]:
        """Return the dependency map for a specific version.

        Returns {dep_name: version_spec}
        """
        raise NotImplementedError


class BuiltinVersionProvider(VersionProvider):
    """Provides versions from the BUILTIN_REGISTRY."""

    def __init__(self):
        from epl.package_manager import BUILTIN_REGISTRY, SemVer
        self._registry = BUILTIN_REGISTRY
        self._SemVer = SemVer

    def get_versions(self, name: str) -> list:
        if name in self._registry:
            ver_str = self._registry[name].get('version', '1.0.0')
            v = self._SemVer.parse(ver_str)
            return [v] if v else []
        return []

    def get_dependencies(self, name: str, version) -> Dict[str, str]:
        # Built-in packages have no dependencies
        return {}


class IndexVersionProvider(VersionProvider):
    """Provides versions from a PackageIndex."""

    def __init__(self, index=None):
        from epl.package_manager import SemVer
        self._SemVer = SemVer
        if index is None:
            from epl.package_index import PackageIndex
            self._index = PackageIndex(offline=True)
        else:
            self._index = index

    def get_versions(self, name: str) -> list:
        entry = self._index.fetch_package(name)
        if not entry:
            return []
        versions = []
        for v_str in entry.available_versions():
            v = self._SemVer.parse(v_str)
            if v:
                versions.append(v)
        versions.sort()
        return versions

    def get_dependencies(self, name: str, version) -> Dict[str, str]:
        return self._index.get_dependencies(name, str(version))


class CompositeVersionProvider(VersionProvider):
    """Combines multiple version providers, querying in order."""

    def __init__(self, providers: Optional[List[VersionProvider]] = None):
        self._providers = providers or []

    def add_provider(self, provider: VersionProvider):
        self._providers.append(provider)

    def get_versions(self, name: str) -> list:
        all_versions = []
        seen = set()
        for provider in self._providers:
            for v in provider.get_versions(name):
                key = str(v)
                if key not in seen:
                    seen.add(key)
                    all_versions.append(v)
        all_versions.sort()
        return all_versions

    def get_dependencies(self, name: str, version) -> Dict[str, str]:
        for provider in self._providers:
            versions = provider.get_versions(name)
            if any(str(v) == str(version) for v in versions):
                return provider.get_dependencies(name, version)
        return {}


# ═══════════════════════════════════════════════════════════
#  Backtracking Resolver
# ═══════════════════════════════════════════════════════════

class ResolutionError(Exception):
    """Raised when resolution fails and cannot be recovered."""
    pass


class DependencyResolver:
    """Backtracking dependency resolver.

    Uses a depth-first search with constraint propagation:
    1. Pick an unresolved package
    2. Try versions from newest to oldest
    3. For each candidate, check if constraints are satisfiable
    4. If yes, add the candidate's deps and recurse
    5. If no, backtrack and try the next version
    """

    def __init__(self, provider: Optional[VersionProvider] = None,
                 max_iterations: int = 10000):
        if provider is None:
            self._provider = BuiltinVersionProvider()
        else:
            self._provider = provider
        self._max_iterations = max_iterations

    def resolve(self, root_deps: Dict[str, str],
                root_name: str = 'root') -> ResolutionResult:
        """Resolve dependencies starting from root_deps.

        Args:
            root_deps: {package_name: version_spec} from the project manifest.
            root_name: Name of the root project (for error messages).

        Returns ResolutionResult with all resolved packages.
        """
        result = ResolutionResult()

        if not root_deps:
            return result

        # Build initial constraints
        constraints: Dict[str, ConstraintSet] = {}
        for name, spec in root_deps.items():
            cs = ConstraintSet(name)
            cs.add(VersionConstraint(spec, source=root_name))
            constraints[name] = cs

        # State for backtracking
        resolved: Dict[str, Any] = {}  # name -> SemVer
        resolved_deps: Dict[str, Dict[str, str]] = {}  # name -> its deps
        unresolved = list(root_deps.keys())
        iterations = 0

        # Stack for backtracking: (pkg_name, tried_versions, snapshot)
        backtrack_stack: List[Tuple[str, Set[str], dict, dict, Dict[str, ConstraintSet], list]] = []

        while unresolved:
            iterations += 1
            if iterations > self._max_iterations:
                result.errors.append(
                    f"Resolution exceeded {self._max_iterations} iterations. "
                    "This may indicate circular or overly complex dependencies."
                )
                return result

            pkg_name = unresolved[0]

            # Get available versions
            all_versions = self._provider.get_versions(pkg_name)
            if not all_versions:
                # Check if it's a builtin that we've already handled
                if pkg_name not in resolved:
                    # Try backtracking
                    if self._backtrack(backtrack_stack, resolved, resolved_deps,
                                       constraints, unresolved):
                        continue
                    result.errors.append(
                        f"Package '{pkg_name}' not found in any registry."
                    )
                    return result
                else:
                    unresolved.pop(0)
                    continue

            # Get constraint set for this package
            cs = constraints.get(pkg_name, ConstraintSet(pkg_name))

            # Filter to matching versions, newest first
            candidates = cs.filter_versions(all_versions)
            candidates.sort(reverse=True)

            if not candidates:
                # No version satisfies all constraints
                if self._backtrack(backtrack_stack, resolved, resolved_deps,
                                   constraints, unresolved):
                    continue
                # Build error message
                conflict_lines = []
                for c in cs.constraints:
                    conflict_lines.append(f"  {c.source} requires {pkg_name} {c.spec}")
                available = ', '.join(str(v) for v in all_versions[-5:])
                result.errors.append(
                    f"No version of '{pkg_name}' satisfies all constraints:\n"
                    + '\n'.join(conflict_lines) +
                    f"\nAvailable versions: {available}"
                )
                return result

            # Save state for backtracking
            snapshot_resolved = dict(resolved)
            snapshot_deps = {k: dict(v) for k, v in resolved_deps.items()}
            snapshot_constraints = {
                k: self._copy_constraint_set(v)
                for k, v in constraints.items()
            }
            snapshot_unresolved = list(unresolved)

            # Try the best candidate
            chosen = candidates[0]
            tried = {str(chosen)}

            backtrack_stack.append((
                pkg_name,
                tried,
                snapshot_resolved,
                snapshot_deps,
                snapshot_constraints,
                snapshot_unresolved,
            ))

            # Resolve this package
            resolved[pkg_name] = chosen
            unresolved.pop(0)

            # Get this version's dependencies
            pkg_deps = self._provider.get_dependencies(pkg_name, chosen)
            resolved_deps[pkg_name] = pkg_deps

            # Add transitive dependencies
            for dep_name, dep_spec in pkg_deps.items():
                if dep_name not in constraints:
                    constraints[dep_name] = ConstraintSet(dep_name)
                constraints[dep_name].add(
                    VersionConstraint(dep_spec, source=f"{pkg_name}@{chosen}")
                )
                if dep_name not in resolved and dep_name not in unresolved:
                    unresolved.append(dep_name)

        # Build result
        for name, version in resolved.items():
            deps = resolved_deps.get(name, {})
            required_by = []
            for cs in constraints.get(name, ConstraintSet(name)).constraints:
                required_by.append(cs.source)
            result.add_package(ResolvedPackage(
                name=name,
                version=version,
                version_str=str(version),
                dependencies=deps,
                required_by=required_by,
            ))

        return result

    def _backtrack(self, stack, resolved, resolved_deps,
                   constraints, unresolved) -> bool:
        """Attempt to backtrack to a previous decision point.

        Returns True if backtracking was successful, False if no more options.
        """
        while stack:
            (pkg_name, tried, snap_resolved, snap_deps,
             snap_constraints, snap_unresolved) = stack[-1]

            # Restore state
            resolved.clear()
            resolved.update(snap_resolved)
            resolved_deps.clear()
            resolved_deps.update(snap_deps)
            constraints.clear()
            constraints.update(snap_constraints)
            unresolved.clear()
            unresolved.extend(snap_unresolved)

            # Get candidates again
            all_versions = self._provider.get_versions(pkg_name)
            cs = constraints.get(pkg_name, ConstraintSet(pkg_name))
            candidates = cs.filter_versions(all_versions)
            candidates.sort(reverse=True)

            # Find next untried candidate
            next_candidate = None
            for c in candidates:
                if str(c) not in tried:
                    next_candidate = c
                    break

            if next_candidate is None:
                # Exhausted all candidates at this level, pop and try upper level
                stack.pop()
                continue

            # Try this candidate
            tried.add(str(next_candidate))
            resolved[pkg_name] = next_candidate
            unresolved.remove(pkg_name) if pkg_name in unresolved else None

            # Get its deps
            pkg_deps = self._provider.get_dependencies(pkg_name, next_candidate)
            resolved_deps[pkg_name] = pkg_deps

            for dep_name, dep_spec in pkg_deps.items():
                if dep_name not in constraints:
                    constraints[dep_name] = ConstraintSet(dep_name)
                constraints[dep_name].add(
                    VersionConstraint(dep_spec, source=f"{pkg_name}@{next_candidate}")
                )
                if dep_name not in resolved and dep_name not in unresolved:
                    unresolved.append(dep_name)

            return True

        return False

    def _copy_constraint_set(self, cs: ConstraintSet) -> ConstraintSet:
        """Deep copy a ConstraintSet."""
        new_cs = ConstraintSet(cs.package_name)
        for c in cs.constraints:
            new_cs.add(VersionConstraint(c.spec, c.source))
        return new_cs


# ═══════════════════════════════════════════════════════════
#  Convenience Functions
# ═══════════════════════════════════════════════════════════

def resolve_from_manifest(manifest_path: str = '.') -> ResolutionResult:
    """Resolve all dependencies from a project manifest.

    Uses the builtin registry + any configured indexes.
    """
    from epl.package_manager import load_manifest
    manifest = load_manifest(manifest_path)
    if not manifest:
        result = ResolutionResult()
        result.errors.append("No epl.toml or epl.json found.")
        return result

    deps = manifest.get('dependencies', {})
    if not deps:
        return ResolutionResult()

    # Build composite provider
    provider = CompositeVersionProvider()
    provider.add_provider(BuiltinVersionProvider())

    # Try to add index provider
    try:
        from epl.package_index import PackageIndex
        idx = PackageIndex(offline=True)
        provider.add_provider(IndexVersionProvider(idx))
    except ImportError:
        pass

    resolver = DependencyResolver(provider)
    return resolver.resolve(deps, manifest.get('name', 'root'))


def resolve_deps(dependencies: Dict[str, str],
                 provider: Optional[VersionProvider] = None) -> ResolutionResult:
    """Resolve a dependency map directly."""
    if provider is None:
        provider = BuiltinVersionProvider()
    resolver = DependencyResolver(provider)
    return resolver.resolve(dependencies)


def print_resolution(result: ResolutionResult):
    """Print the resolution result in a human-readable format."""
    if not result.success:
        print("  Resolution failed:")
        for err in result.errors:
            print(f"    {err}")
        return

    if result.warnings:
        for w in result.warnings:
            print(f"  Warning: {w}")

    order = result.get_install_order()
    if not order:
        print("  No dependencies to install.")
        return

    print(f"  Resolved {len(order)} packages:")
    for pkg in order:
        deps_str = ''
        if pkg.dependencies:
            dep_list = ', '.join(f"{n}@{v}" for n, v in pkg.dependencies.items())
            deps_str = f" (deps: {dep_list})"
        print(f"    {pkg.name}@{pkg.version_str}{deps_str}")
