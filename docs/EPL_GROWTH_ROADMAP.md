# EPL Growth Roadmap — From Project to Production Language

> **Goal**: Transform EPL from a personal project into a production-grade programming language
> with real users, community, and ecosystem.
>
> **Created**: March 26, 2026
> **Status**: Active Planning

---

## Table of Contents

1. [Current State Assessment](#current-state-assessment)
2. [Phase 1: Make EPL Discoverable](#phase-1-make-epl-discoverable-week-1-2)
3. [Phase 2: Get First 100 Users](#phase-2-get-first-100-users-month-1-2)
4. [Phase 3: Build Real-World Proof](#phase-3-build-real-world-proof-month-2-4)
5. [Phase 4: Build Community](#phase-4-build-community-month-3-6)
6. [Phase 5: Education Market](#phase-5-education-market-month-6-12)
7. [Phase 6: Enterprise Readiness](#phase-6-enterprise-readiness-year-1-2)
8. [Critical Security Fixes](#critical-security-fixes-before-any-public-release)
9. [Technical Debt Tracker](#technical-debt-tracker)
10. [Marketing Assets Checklist](#marketing-assets-checklist)
11. [Success Metrics](#success-metrics)
12. [Reference: How Other Languages Grew](#reference-how-other-languages-grew)

---

## Current State Assessment

### ✅ What EPL Has (Strengths)

| Component | Status | Notes |
|-----------|--------|-------|
| Lexer / Parser | ✅ Complete | Multi-word English keywords, error recovery |
| Tree-walking Interpreter | ✅ Complete | Async/await, generators, OOP, dispatch tables |
| LLVM Compiler Backend | 🟡 Partial | Works for core features, many nodes fall back to interpreter |
| VM Bytecode Engine | 🟡 Partial | Fast for simple programs, missing feature parity |
| Type Checker v2.0 | ✅ Complete | Unused var detection, fuzzy suggestions, LSP output |
| Type System | ✅ Complete | Generics, union types, interface conformance |
| LSP Server | ✅ Complete | JSON-RPC, completions, hover, diagnostics, type checking |
| Package Manager | ✅ Complete | Semver, TOML manifests, lockfiles, dependency resolution |
| Standard Library | ✅ Complete | 300+ builtins covering HTTP, DB, ML, GUI, crypto |
| Web Server (WSGI/ASGI) | ✅ Complete | Production-grade with middleware, sessions, static files |
| CLI | ✅ Complete | 50+ commands (run, build, test, serve, check, etc.) |
| Transpilers | 🟡 Partial | JS, Kotlin, Python, MicroPython (basic scaffolding) |
| Test Framework | ✅ Complete | Assert-based with coverage tracking |

### ❌ What EPL Lacks (Gaps)

| Gap | Impact | Priority |
|-----|--------|----------|
| 0 community users | No feedback, no battle-testing | 🔴 Critical |
| 0 community packages | No ecosystem | 🔴 Critical |
| No PyPI package | Can't install with `pip` | 🔴 Critical |
| No website/playground | Not discoverable | 🔴 Critical |
| Security vulnerabilities | Can't trust in production | 🔴 Critical |
| No documentation site | Can't learn the language | 🟠 High |
| No real Android/iOS apps | "Build anything" claim is unproven | 🟡 Medium |
| No IDE extension published | IDE support exists but not packaged | 🟡 Medium |

---

## Phase 1: Make EPL Discoverable (Week 1-2)

### 1.1 GitHub Repository Polish

**Goal**: A stranger lands on your repo and understands EPL in 10 seconds.

```
EPL/
├── README.md              → The hook (see template below)
├── CONTRIBUTING.md        → How to contribute
├── CODE_OF_CONDUCT.md     → Community standards
├── LICENSE                → MIT License (maximizes adoption)
├── CHANGELOG.md           → Version history
├── setup.py / pyproject.toml → PyPI packaging
├── docs/
│   ├── getting-started.md → 5-minute tutorial
│   ├── language-guide.md  → Full syntax reference
│   ├── stdlib-reference.md → All builtins documented
│   └── examples/          → Categorized examples
├── examples/              → Ready-to-run demos
├── tests/                 → Comprehensive test suite
└── .github/
    ├── workflows/ci.yml   → CI that proves tests pass
    └── ISSUE_TEMPLATE/    → Bug report + feature request templates
```

### 1.2 README Template (The Most Important File)

```markdown
# EPL — English Programming Language

**Write code in plain English. No syntax to memorize. Build anything.**

## Why EPL?

| Python | JavaScript | EPL |
|--------|------------|-----|
| `x = 10` | `let x = 10;` | `Set x To 10` |
| `print("Hello")` | `console.log("Hello")` | `Say "Hello"` |
| `if x > 5:` | `if (x > 5) {` | `If x is greater than 5 Then` |
| `for i in range(10):` | `for(let i=0;i<10;i++){` | `Repeat 10 times` |

## Install in 10 Seconds

    pip install epl-lang

## Hello World

    Say "Hello, World!"
    Set name To "EPL"
    Say "Welcome to " + name + "!"

## Run It

    epl hello.epl

## What Can EPL Build?

- ✅ Web servers     → `epl serve app.epl`
- ✅ CLI tools       → `epl run tool.epl`
- ✅ Desktop apps    → `epl gui app.epl`
- ✅ REST APIs       → Built-in web framework
- ✅ Native binaries → `epl build app.epl` (LLVM)
```

### 1.3 Publish to PyPI

**This is the single most important distribution step.**

Create `pyproject.toml`:
```toml
[project]
name = "epl-lang"
version = "7.0.0"
description = "English Programming Language — Write code in plain English"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
keywords = ["programming-language", "english", "beginner-friendly", "compiler"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Programming Language :: Python :: 3",
    "Topic :: Software Development :: Compilers",
    "Topic :: Software Development :: Interpreters",
]

[project.scripts]
epl = "epl.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

Publish commands:
```bash
pip install build twine
python -m build
twine upload dist/*
```

**Result**: Anyone in the world can now run `pip install epl-lang`.

### 1.4 Landing Page (GitHub Pages)

Create a simple site at `epl-lang.github.io` or `epl-lang.org`:

| Page | Content |
|------|---------|
| **Home** | One-liner + install command + live playground embed |
| **Docs** | Getting started, language guide, stdlib reference |
| **Examples** | Interactive code samples |
| **Community** | Discord link, GitHub link, contributing guide |

**Tool**: Use GitHub Pages + a static site generator (Hugo/Docusaurus).
Or build the site using EPL's own web server (dog-fooding!).

---

## Phase 2: Get First 100 Users (Month 1-2)

### 2.1 Target Audience

EPL's unique value is **English syntax**. Target people who are:
- Beginners scared of code syntax
- Non-programmers (marketers, designers, students)
- Educators teaching CS101
- Kids learning to code (ages 10-16)

### 2.2 Launch Channels

| Channel | Post Title | Expected Impact |
|---------|------------|-----------------|
| **Hacker News** | "Show HN: EPL — A programming language where code reads like English" | 50-200 stars |
| **Reddit r/ProgrammingLanguages** | "I built a language where 'Say Hello' prints Hello. Here's how." | 20-50 stars |
| **Reddit r/learnprogramming** | "I made a language for people who find Python too cryptic" | 30-100 stars |
| **Reddit r/Python** | "I built an English-syntax language that compiles to Python & LLVM" | 20-50 stars |
| **Twitter/X** | 30-sec video: "Hello World in 10 languages vs EPL" | Viral potential |
| **YouTube** | "Build a web server in plain English (5 min tutorial)" | Long-tail views |
| **Dev.to** | "Why I Built a Programming Language That Reads Like English" | 10-30 follows |
| **Product Hunt** | Launch with playground | 50-100 upvotes |
| **Indie Hackers** | "Building a programming language as a solo developer" | Community interest |

### 2.3 Content Calendar

| Week | Content | Channel |
|------|---------|---------|
| Week 1 | "Show HN" post with playground link | Hacker News |
| Week 2 | "EPL vs Python for beginners" comparison video | YouTube + Twitter |
| Week 3 | "Build a REST API in plain English" tutorial | Dev.to + Reddit |
| Week 4 | "Teaching my non-programmer friend to code in 10 minutes" | Twitter thread |
| Week 5 | "EPL's type system: How we catch bugs in English code" | r/ProgrammingLanguages |
| Week 6 | "1 month, 100 stars: Lessons from building a language" | Indie Hackers |

### 2.4 The Viral Hook

The comparison that gets clicks every time:

```
C++:          std::cout << "Hello, World!" << std::endl;
Java:         System.out.println("Hello, World!");
JavaScript:   console.log("Hello, World!");
Python:       print("Hello, World!")
EPL:          Say "Hello, World!"
```

**Use this in every post, video, and tweet.** It's immediately compelling.

---

## Phase 3: Build Real-World Proof (Month 2-4)

### 3.1 Build 5 Showcase Apps IN EPL

| # | App | Why It Proves EPL Works | Complexity |
|---|-----|------------------------|------------|
| 1 | **EPL website** (epl-lang.org) | "We use our own language" (dog-fooding) | Medium |
| 2 | **TODO app with SQLite** | Proves CRUD, database, persistence | Easy |
| 3 | **REST API** (user auth + JWT) | Proves backend/security capability | Medium |
| 4 | **Discord bot** | Fun, viral, easy for beginners to extend | Easy |
| 5 | **Markdown blog engine** | File I/O, templates, web serving | Medium |

Each app should have:
- Full source code in `examples/apps/`
- Step-by-step tutorial in `docs/tutorials/`
- Live demo link (deploy on Render/Railway/Vercel)

### 3.2 Benchmarks

Create an honest benchmarks page comparing EPL to Python:

```
Benchmark: Fibonacci(35)
  Python (CPython):  2.8 seconds
  EPL (Interpreter): 3.2 seconds
  EPL (VM):          1.1 seconds
  EPL (LLVM):        0.05 seconds

Benchmark: HTTP req/sec (simple JSON API)
  Flask (Python):    1,200 req/s
  EPL (serve):       1,100 req/s
  Express (Node):    8,500 req/s
```

**Honesty builds trust.** Don't hide weaknesses — explain the roadmap to fix them.

---

## Phase 4: Build Community (Month 3-6)

### 4.1 Discord Server Structure

```
EPL Discord
├── #announcements     → Version releases, milestones
├── #general           → Chat about EPL
├── #help              → Q&A for users
├── #showcase          → Projects built with EPL
├── #contribute        → For contributors
├── #ideas             → Feature requests and discussions
├── #beginners         → Safe space for new programmers
└── #off-topic         → Fun stuff
```

### 4.2 GitHub Issue Labels

Create these labels to attract contributors:

| Label | Description | Count Needed |
|-------|-------------|-------------|
| `good first issue` | Easy tasks for new contributors | 20+ always open |
| `help wanted` | Medium tasks needing help | 10+ |
| `documentation` | Docs improvements | 10+ |
| `enhancement` | Feature requests | Unlimited |
| `bug` | Confirmed bugs | As needed |
| `performance` | Speed improvements | 5+ |

### 4.3 Good First Issues (Ready to Create)

1. "Add `abs()` builtin function"
2. "Improve error message when forgetting `End` keyword"
3. "Add example: Temperature converter"
4. "Add example: Simple calculator"
5. "Document all string methods in stdlib-reference.md"
6. "Add `--version` flag to `epl lsp`"
7. "Create syntax highlighting for Sublime Text"
8. "Add EPL logo to README"
9. "Write unit test for `Repeat N times` loop"
10. "Add `shuffle()` function to list builtins"
11. "Create `.editorconfig` file"
12. "Add badge for CI status to README"
13. "Translate getting-started guide to Hindi"
14. "Add example: Fizzbuzz in EPL"
15. "Improve REPL welcome message"
16. "Add `--output` flag to `epl build`"
17. "Create EPL syntax highlighting for VS Code"
18. "Add `title_case()` string method"
19. "Write tutorial: Variables and Types"
20. "Add `is_even()` and `is_odd()` builtins"

### 4.4 Contributor Recognition

- `CONTRIBUTORS.md` — List all contributors
- GitHub releases thank new contributors by name
- Discord role: "EPL Contributor" for anyone who merges a PR

---

## Phase 5: Education Market (Month 6-12)

### 5.1 Why Education Is EPL's Killer Market

| Problem | EPL's Solution |
|---------|----------------|
| Kids struggle with Python's `:`, `()`, indentation | EPL uses English words |
| CS101 students drop out due to syntax frustration | EPL removes that barrier |
| Non-tech professionals want to learn coding basics | EPL is the easiest onramp |
| Coding bootcamps need simpler first languages | EPL is literally English |

### 5.2 Free Curriculum: "Learn Programming with EPL"

| Lesson | Topic | EPL Concept |
|--------|-------|-------------|
| 1 | Your First Program | `Say "Hello!"` |
| 2 | Variables | `Set name To "EPL"` |
| 3 | Math | `Set result To 5 + 3` |
| 4 | User Input | `Ask "What is your name?" and store in name` |
| 5 | Conditions | `If score > 90 Then Say "A grade!"` |
| 6 | Loops | `Repeat 10 times` / `For Each item In list` |
| 7 | Lists | `Set fruits To ["apple", "banana"]` |
| 8 | Functions | `Define function greet takes name` |
| 9 | Files | `Read file "data.txt" into content` |
| 10 | Web Server | `epl serve myapp.epl` |

### 5.3 Outreach Strategy

1. Email 50 CS professors with the curriculum PDF
2. Post on r/CSEducation and r/teachingprogramming
3. Submit to Code.org as a supported language
4. Partner with 1-2 coding bootcamps for a pilot program
5. Create a "EPL for Kids" visual block editor (you already have `epl blocks`!)

### 5.4 School Toolkit

Provide a complete package for educators:
- Lesson plans (10 lessons)
- Student worksheets
- Teacher's guide
- Assessment rubrics
- Pre-configured classroom server (so students just open a browser)

---

## Phase 6: Enterprise Readiness (Year 1-2)

### 6.1 Technical Requirements

| Requirement | Current State | Needed |
|-------------|---------------|--------|
| Security audit | 3 critical gaps | All fixed + external audit |
| Performance | Python-speed interpreter | JIT or mature LLVM backend |
| Debugging | Basic breakpoints | Step-through debugger |
| Profiling | Basic timing | Flame graphs, memory profiling |
| Package registry | GitHub-based | Hosted registry (npmjs-style) |
| Documentation | README | Full docs site with search |
| VS Code extension | LSP exists | Published extension on marketplace |
| CI/CD integration | Basic | GitHub Actions, Docker images |

### 6.2 VS Code Extension (High Impact)

Publish `epl-vscode` extension with:
- Syntax highlighting
- Error diagnostics (via LSP)
- Code completion
- Hover documentation
- Go-to-definition
- Format on save
- Run/debug from editor

**Impact**: Most developers discover languages through IDE extensions.

### 6.3 Docker Image

```dockerfile
FROM python:3.12-slim
RUN pip install epl-lang
ENTRYPOINT ["epl"]
```

**Usage**: `docker run epl-lang run myapp.epl`

---

## Critical Security Fixes (BEFORE Any Public Release)

> ⚠️ **DO NOT publish EPL publicly until these are fixed.**

| # | Vulnerability | File | Fix |
|---|--------------|------|-----|
| 1 | **Pickle RCE** — `.eplc` files can execute arbitrary code | `bytecode_cache.py:74` | Replace `pickle.loads()` with `json` or `marshal` |
| 2 | **No recursion limit** — infinite recursion crashes process | `interpreter.py` | Add `sys.setrecursionlimit()` + EPL-level stack depth check |
| 3 | **FFI has no sandbox** — can load ANY shared library | `ffi.py` | Add allowlist + `safe_mode` gating |

### Fix Priority Order
1. Fix Pickle RCE (30 minutes)
2. Fix recursion limit (15 minutes)
3. Fix FFI sandbox (1 hour)
4. Run security test suite
5. THEN publish

---

## Technical Debt Tracker

| # | Issue | File | Priority | Status |
|---|-------|------|----------|--------|
| 1 | VM silently falls back to interpreter | `main.py` | High | ⬜ Open |
| 2 | `_source_lines` is global mutable state | `errors.py` | High | ⬜ Open |
| 3 | Environment scope chain has no depth limit | `environment.py` | Medium | ⬜ Open |
| 4 | Duplicate `EPLChannel`/`EPLTimer` classes | `async_io.py` vs `concurrency.py` | Medium | ⬜ Open |
| 5 | No graceful shutdown for event loop | `async_io.py` | Medium | ⬜ Open |
| 6 | `RWLock` has writer starvation | `concurrency.py` | Low | ⬜ Open |
| 7 | REPL duplicate history setup | `main.py` | Low | ⬜ Open |
| 8 | `AssertionError` typo | `errors.py`, `test_framework.py` | Low | ⬜ Open |

---

## Marketing Assets Checklist

- [ ] EPL logo (simple, memorable, professional)
- [ ] Color palette & brand guide
- [ ] Social media banner images
- [ ] 30-second demo video (comparison with other languages)
- [ ] 5-minute tutorial video
- [ ] Presentation slides (for conferences/meetups)
- [ ] One-page PDF "What is EPL?" handout
- [ ] Sticker/swag designs (for conferences)
- [ ] Screenshots of IDE with EPL syntax highlighting

---

## Success Metrics

### Month 1
- [ ] Published on PyPI
- [ ] 50+ GitHub stars
- [ ] 10+ Discord members
- [ ] 1 HN post

### Month 3
- [ ] 200+ GitHub stars
- [ ] 50+ Discord members
- [ ] 5 showcase apps
- [ ] 3 community contributions (PRs merged)
- [ ] VS Code extension published

### Month 6
- [ ] 500+ GitHub stars
- [ ] 100+ Discord members
- [ ] 10+ community packages
- [ ] 1 school/bootcamp pilot
- [ ] 5+ blog posts / tutorials by community

### Year 1
- [ ] 1,000+ GitHub stars
- [ ] 500+ Discord members
- [ ] 50+ community packages
- [ ] Production deployment by at least 1 external user
- [ ] Featured in a programming language survey

### Year 2
- [ ] 5,000+ GitHub stars
- [ ] 2,000+ Discord members
- [ ] Package registry with 100+ packages
- [ ] Education adoption in 5+ schools
- [ ] Conference talk / presentation

---

## Reference: How Other Languages Grew

### Rust (2010 → Production 2015)
- **Year 1-3**: Mozilla internal use, small community
- **Year 3-5**: "Memory safety without GC" message clicked with systems programmers
- **Year 5+**: Community-driven growth, adoption at Dropbox, Discord, Cloudflare
- **Key**: Clear value proposition + excellent documentation + welcoming community

### Go (2009 → Production 2012)
- **Year 1-2**: Google backing gave instant credibility
- **Year 2-3**: "Simple concurrency" attracted web developers
- **Year 3+**: Docker, Kubernetes written in Go → massive ecosystem growth
- **Key**: Corporate backing + killer use case (cloud infrastructure)

### Zig (2015 → Growing 2020+)
- **Year 1-4**: Solo developer (Andrew Kelley), slow organic growth
- **Year 4+**: HN posts, conference talks, Zig Software Foundation
- **Key**: One passionate developer + consistent content + HN/Reddit presence

### Nim (2008 → Growing 2015+)
- **Year 1-7**: Very slow growth, small community
- **Year 7+**: Reddit presence, package manager, good documentation
- **Key**: Patience + packaging + documentation

### EPL's Advantage Over All of These
**None of these languages had the "code in English" hook.**

EPL's value proposition is understandable by a 10-year-old:
> "In EPL, you write `Say Hello` instead of `print("Hello")`"

This makes EPL's potential viral coefficient much higher than languages
that require technical understanding to appreciate (like Rust's borrow checker).

---

## Quick Reference: Key Commands

```bash
# Development
epl run app.epl              # Run a program
epl check app.epl            # Type check
epl check app.epl --strict   # Strict type check
epl lint app.epl             # Lint code
epl fmt app.epl              # Format code
epl test tests/              # Run tests
epl build app.epl            # Compile to native
epl lsp                      # Start language server

# Package Management
epl install <package>        # Install package
epl publish                  # Publish to registry
epl search <query>           # Search packages

# Deployment
epl serve app.epl            # Production web server
epl deploy <target>          # Generate deploy configs
```

---

> **Remember**: Every production language started exactly where EPL is now.
> The foundations are strong. What's needed is **time, users, and real-world usage.**
> This roadmap gives you the plan. Execute it one phase at a time.
