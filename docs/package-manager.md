# EPL Package Manager Guide

Complete guide to managing EPL projects and packages.

## Quick Start

```bash
# Initialize a new project
epl init my-project
epl new my-project --template web
cd my-project

# Install a package
epl install epl-math
epl install epl-web
epl install owner/repo

# List installed packages
epl packages

# Run your project
epl run
epl serve        # for web/api/frontend/auth/chatbot/fullstack starters
```

## Project Initialization

```bash
epl init [project-name]
```

Creates a project directory (or initializes in the current directory) with:

- **`epl.toml`** — Project manifest (`epl.json` is still supported as a legacy format)
- **`main.epl`** — Entry point

### Manifest Format (`epl.toml`)

```toml
[project]
name = "my-project"
version = "1.0.0"
description = "My EPL project"
entry = "main.epl"

[dependencies]
epl-math = "^1.0.0"
epl-utils = "~2.1.0"
```

## Semantic Versioning

EPL uses [SemVer](https://semver.org/) for all package versions.

### Version Format

```
MAJOR.MINOR.PATCH[-prerelease][+build]
```

Examples: `1.0.0`, `2.3.1`, `1.0.0-alpha.1`, `1.2.3+build.456`

### Version Ranges

| Specifier | Meaning | Example |
|-----------|---------|---------|
| `1.2.3` | Exact version | Only `1.2.3` |
| `^1.2.3` | Compatible (caret) | `>=1.2.3` and `<2.0.0` |
| `~1.2.3` | Tilde (patch-level) | `>=1.2.3` and `<1.3.0` |
| `>=1.0.0` | Greater or equal | `1.0.0` and above |
| `<2.0.0` | Less than | Below `2.0.0` |
| `!=1.5.0` | Not equal | Any version except `1.5.0` |
| `*` | Wildcard | Any version |
| `>=1.0.0 <2.0.0` | Compound | Multiple constraints (space-separated) |

### Caret (`^`) vs Tilde (`~`)

- **Caret `^1.2.3`** — Allows changes that don't modify the left-most non-zero digit. `^1.2.3` matches `1.x.x` where `x >= 2.3`.
- **Tilde `~1.2.3`** — Allows patch-level changes. `~1.2.3` matches `1.2.x` where `x >= 3`.

## Installing Packages

### Install a single package

```bash
epl install epl-math
```

This:
1. Resolves the best available version
2. Downloads/installs the package to `~/.epl/packages/`
3. Adds the dependency to `epl.toml`
4. Generates/updates `epl.lock`

### Install all dependencies

```bash
epl install
epl install --frozen
```

Without a package name, installs all dependencies from `epl.toml` (or legacy `epl.json`).

Use `epl install --frozen` to enforce a lockfile-only install with exact resolved versions.

This also installs any declared GitHub dependencies from `[github-dependencies]` and Python ecosystem dependencies from `[python-dependencies]`.

### Install with version constraint

In `epl.toml`, specify version ranges:

```toml
[dependencies]
epl-math = "^1.0.0"
epl-http = ">=2.0.0 <3.0.0"
```

## Python Ecosystem Dependencies

EPL can bridge directly to Python libraries via `Use python "module"`. For project-managed third-party packages, declare them in `epl.toml`:

```toml
[python-dependencies]
requests = "*"
yaml = "pyyaml>=6"
PIL = "pillow>=10"
fastapi = "fastapi[all]>=0.115"
```

Rules:
- The key is the import name used from EPL.
- The value is the pip requirement to install.
- Use `"*"` when the pip package name matches the import name.

CLI:

```bash
epl pyinstall requests
epl pyinstall yaml pyyaml>=6
epl pydeps
epl pyremove yaml
epl install   # installs EPL + Python dependencies from the manifest
```

## GitHub Dependencies and Project Workflows

EPL projects can depend on EPL packages hosted directly on GitHub. Declare them in `epl.toml`:

```toml
[github-dependencies]
web-kit = "epl-lang/web-kit"
starter = "someone/starter"
```

Rules:
- The key is the local dependency name you want in the manifest.
- The value is the GitHub repository in `owner/repo` format.
- `epl install` installs these dependencies automatically.

CLI:

```bash
epl install owner/repo              # quick GitHub install shorthand
epl gitinstall epl-lang/web-kit     # install + save to [github-dependencies]
epl gitinstall epl-lang/web-kit ui  # save with an alias
epl gitdeps
epl gitremove web-kit
epl install                         # installs registry + GitHub + Python deps
```

EPL also exposes GitHub project workflows for real users:

```bash
epl github clone epl-lang/epl
epl github pull
epl github push . -m "Update project"
```

## Supported Official Packages

EPL currently ships supported facade packages that reuse the existing runtime:

| Package | Purpose |
|---------|---------|
| `epl-web` | Supported web helper facade for request/response/session helpers |
| `epl-db` | Supported database facade |
| `epl-test` | Supported testing facade |

`epl new --template web|api|frontend|auth|chatbot|fullstack` now generates the native `Create WebApp` DSL because that is the authoritative served web runtime. Use `epl-web` when you want explicit helper wrappers on top of the lower-level web helper builtins.

These install like normal packages:

```bash
epl install epl-web
epl install epl-db
epl install epl-test
```

## Lockfiles (`epl.lock`)

The lockfile pins exact resolved versions for reproducible builds.

### Format

```json
{
  "lockfileVersion": 3,
  "metadata": {
    "project": "my-project",
    "manifest": "epl.toml"
  },
  "packages": {
    "epl-math": {
      "version": "1.2.0",
      "integrity": "abc123...",
      "required_by": ["my-project"]
    }
  },
  "python_packages": {
    "yaml": {
      "distribution": "PyYAML",
      "version": "6.0.1",
      "pip_spec": "pyyaml>=6",
      "integrity": "def456..."
    }
  },
  "github_packages": {
    "web-kit": {
      "repo": "epl-lang/web-kit",
      "commit": "abc123def456",
      "package": "web-kit-pkg",
      "version": "1.2.0",
      "integrity": "ghi789..."
    }
  }
}
```

### Lockfile Commands

| Action | How |
|--------|-----|
| Generate lockfile | Automatic after `install` |
| Verify integrity | `verify_lockfile()` API — checks SHA256 hashes and version compatibility |
| Frozen install | `epl install --frozen` |

### Integrity Verification

Each locked package includes a SHA256 hash. On install, the lockfile verifier:
1. Checks that each locked package is still installed
2. Verifies the integrity hash matches the installed package
3. Confirms the locked version satisfies the declared version range

## Dependency Resolution

EPL resolves transitive dependencies using breadth-first search:

```
my-project
├── epl-math ^1.0.0
│   └── epl-utils ^1.0.0    ← transitive dependency
└── epl-http ^2.0.0
```

### Resolution Algorithm

1. Read direct dependencies from `epl.toml` (or legacy `epl.json`)
2. For each dependency, find the best matching version
3. Check for conflicts with already-resolved packages
4. If compatible, skip. If incompatible, raise `DependencyConflict`
5. Queue any sub-dependencies for resolution
6. Repeat until all transitive dependencies are resolved

### Conflict Detection

If two packages require incompatible versions of the same dependency:

```
epl-math requires epl-utils ^1.0.0
epl-http requires epl-utils ^3.0.0   ← CONFLICT
```

EPL raises a `DependencyConflict` error with details about which packages conflict.

## Updating Packages

```bash
# Update a specific package
epl update epl-math

# Update all packages
epl update

# Allow major-version updates
epl update --major
```

Updates remove the existing version, reinstall the latest compatible version, and regenerate the lockfile.

## Uninstalling Packages

```bash
epl uninstall epl-math
```

This:
1. Removes the package from `~/.epl/packages/`
2. Removes the package from the local registry
3. Removes the dependency from `epl.toml`

## Creating Packages

### 1. Set up the manifest

```toml
[project]
name = "my-lib"
version = "1.0.0"
description = "A useful EPL library"
entry = "main.epl"

[dependencies]
```

**Naming rules:**
- Lowercase letters, numbers, dots, hyphens, underscores
- Pattern: `^[a-z][a-z0-9._-]*$`

### 2. Write your library code

```epl
Note: main.epl - Entry point for my-lib

Function helper takes x
    Return x * 2
End
```

### 3. Validate

```bash
python main.py validate .
```

Checks:
- Name format matches the regex pattern
- Version is valid SemVer
- Description is present
- Entry point file exists

### 4. Pack

```bash
python main.py pack .
```

Creates:
- `dist/my-lib-1.0.0.zip` — Package archive
- `dist/my-lib-1.0.0.zip.sha256` — Checksum file

The packer excludes `dist/`, `__pycache__/`, and `.git/` directories.

### 5. Publish

```bash
python main.py publish .
```

Publish validates the package, creates the archive, installs it locally, and registers it in the local package registry (`~/.epl/registry.json`).

## Built-in Packages

EPL ships with several built-in packages:

| Package | Description |
|---------|-------------|
| `epl-math` | Mathematical functions and constants |
| `epl-strings` | String manipulation utilities |
| `epl-collections` | Advanced data structures |
| `epl-testing` | Test assertions and runners |
| `epl-http` | HTTP client functionality |
| `epl-json` | JSON parsing and generation |
| `epl-datetime` | Date and time operations |
| `epl-crypto` | Cryptographic functions |
| `epl-regex` | Regular expressions |

## Module Resolution

When you `Import "package-name"`, EPL searches in order:

1. **Relative path** — Check if it's a local `.epl` file
2. **Installed packages** — Look in `~/.epl/packages/<name>/`
3. **Built-in packages** — Check the built-in registry

## API Reference

For programmatic use in Python:

```python
from epl.package_manager import (
    init_project,
    install_package,
    uninstall_package,
    list_packages,
    install_dependencies,
    create_lockfile,
    verify_lockfile,
    validate_package,
    pack_package,
    publish_package,
    update_package,
    update_all,
    resolve_dependencies,
    SemVer,
    parse_version_range,
)
```
