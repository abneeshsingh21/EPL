# Publishing EPL Packages

This guide explains how to create, publish, and distribute EPL packages.

## Quick Start

```bash
# 1. Create your package
mkdir my-package && cd my-package

# 2. Initialize with a manifest
cat > epl.toml << 'EOF'
[project]
name = "my-package"
version = "1.0.0"
description = "A useful utility library for EPL"
author = "Your Name"
license = "MIT"
entry = "src/main.epl"
keywords = ["utils", "helpers"]

[dependencies]
EOF

# 3. Write your code
mkdir src
echo 'Function hello takes name
    Return "Hello, " + name + "!"
End' > src/main.epl

# 4. Login (one time)
epl login

# 5. Publish
epl publish --repo yourname/my-package
```

That's it. Your package is automatically registered in the EPL package index.

---

## Detailed Guide

### Step 1: Create Package Structure

```
my-package/
├── epl.toml          # Package manifest (required)
├── README.md         # Package documentation (recommended)
├── LICENSE           # License file (recommended)
├── src/
│   └── main.epl     # Entry point (must match epl.toml entry field)
├── examples/
│   └── basic.epl    # Usage examples (optional)
└── tests/
    └── test.epl     # Tests (optional)
```

### Step 2: Write the Manifest (`epl.toml`)

```toml
[project]
name = "my-package"           # Package name (letters, digits, hyphens, underscores)
version = "1.0.0"             # Semantic version (MAJOR.MINOR.PATCH)
description = "What it does"  # At least 10 characters
author = "Your Name"          # Your name or org
license = "MIT"               # SPDX license identifier
entry = "src/main.epl"       # Main entry point file
keywords = ["tag1", "tag2"]   # For search/discovery

[dependencies]
# Other EPL packages your package depends on
# epl-array = "^1.0.0"

[python]
# Python packages needed (if using Python bridge)
# requires = ["numpy>=1.20.0"]
```

### Step 3: Login

```bash
epl login
```

This saves your GitHub personal access token locally. You need a token with `public_repo` scope.

Create one at: https://github.com/settings/tokens

You only need to do this once.

### Step 4: Create a GitHub Repository

Push your package to a public GitHub repository:

```bash
git init
git add .
git commit -m "Initial release"
gh repo create yourname/my-package --public --push
```

### Step 5: Publish

```bash
epl publish --repo yourname/my-package
```

This will:
1. Validate your manifest (name, version, description, license, entry point)
2. Create a ZIP archive of your package
3. Create a GitHub Release on your repo with the archive attached
4. **Automatically register** your package in the EPL central index

### Step 6: Verify

```bash
epl search my-package
```

Your package should appear in search results within a minute.

---

## How Others Install Your Package

```bash
epl install my-package
```

Or directly from GitHub:

```bash
epl install github:yourname/my-package
```

---

## Updating Your Package

1. Bump the version in `epl.toml`
2. Commit and push
3. Run `epl publish --repo yourname/my-package` again

The index automatically updates with the new version.

---

## Quality Gates

When you publish, the following checks must pass:

| Check | Requirement |
|-------|-------------|
| Name | Valid characters, not reserved, not already taken by another author |
| Version | Valid semantic version (e.g., 1.0.0, 2.1.3-beta) |
| Description | At least 10 characters |
| Author | Must be specified |
| License | Must be specified |
| Entry point | File must exist in your package |
| Download URL | Must be HTTPS |

If any check fails, your package is rejected with a clear error message.

---

## Reserved Package Names

The following names cannot be used:
`epl`, `epl-core`, `epl-std`, `epl-lang`, `epl-cli`, `test`, `tests`, `node`, `python`, `java`, `rust`

---

## Checking Login Status

```bash
epl login --status    # Check if logged in
epl login --logout    # Remove saved credentials
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub token (alternative to `epl login`) |
| `EPL_GITHUB_TOKEN` | Same as above (fallback) |

---

## Troubleshooting

**"Auto-registration failed"**
- Ensure your token has `public_repo` scope
- Check your internet connection
- Try `epl login` again with a fresh token

**"Pre-publish checks failed"**
- Run `epl publish --repo yourname/repo` and fix the reported errors
- Use `--skip-checks` to bypass (not recommended)

**"Package name already registered by another author"**
- Choose a different name — package names are first-come, first-served
- Use a scoped name: `yourname-packagename`
