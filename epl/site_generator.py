"""
EPL Documentation Site Generator v4.2
Generates a complete static documentation website with:
  - Getting started guide
  - Language reference
  - API reference (auto-generated from source)
  - Package directory (50 official packages)
  - Tutorials
  - Search functionality
  - Responsive design with dark/light mode
  - Sidebar navigation

Usage:
    python main.py site [source_dir]     Generate docs site in docs/site/
"""

import os
import json
import time
import html as html_mod
from pathlib import Path
from typing import List, Dict, Optional


# ═══════════════════════════════════════════════════════════
#  Site Configuration
# ═══════════════════════════════════════════════════════════

SITE_TITLE = "EPL Documentation"
SITE_DESCRIPTION = "English Programming Language — Write code in plain English"

# ═══════════════════════════════════════════════════════════
#  CSS Theme
# ═══════════════════════════════════════════════════════════

SITE_CSS = '''
:root {
  --bg: #ffffff; --bg-alt: #f6f8fa; --bg-card: #ffffff;
  --text: #1f2328; --text-muted: #656d76; --text-link: #0969da;
  --border: #d0d7de; --border-light: #e8ebef;
  --accent: #0969da; --accent-hover: #0550ae;
  --code-bg: #f6f8fa; --code-border: #d0d7de;
  --sidebar-bg: #f6f8fa; --sidebar-active: #0969da;
  --badge-fn: #0550ae; --badge-class: #8250df; --badge-var: #1a7f37;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 6px;
}
@media(prefers-color-scheme:dark){
  :root {
    --bg: #0d1117; --bg-alt: #161b22; --bg-card: #161b22;
    --text: #e6edf3; --text-muted: #8b949e; --text-link: #58a6ff;
    --border: #30363d; --border-light: #21262d;
    --accent: #58a6ff; --accent-hover: #79c0ff;
    --code-bg: #161b22; --code-border: #30363d;
    --sidebar-bg: #0d1117; --sidebar-active: #58a6ff;
    --badge-fn: #58a6ff; --badge-class: #d2a8ff; --badge-var: #3fb950;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  color:var(--text);background:var(--bg);line-height:1.6;font-size:16px}
a{color:var(--text-link);text-decoration:none}
a:hover{text-decoration:underline}

/* Layout */
.site-header{background:var(--bg-alt);border-bottom:1px solid var(--border);padding:12px 24px;
  display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}
.site-header h1{font-size:20px;font-weight:600}
.site-header .version{color:var(--text-muted);font-size:14px}
.site-header nav{margin-left:auto;display:flex;gap:16px;font-size:14px}
.layout{display:flex;min-height:calc(100vh - 52px)}
.sidebar{width:260px;background:var(--sidebar-bg);border-right:1px solid var(--border);
  padding:16px 0;overflow-y:auto;position:sticky;top:52px;height:calc(100vh - 52px);flex-shrink:0}
.sidebar .section-title{font-size:11px;font-weight:600;text-transform:uppercase;
  color:var(--text-muted);padding:12px 16px 4px;letter-spacing:0.5px}
.sidebar a{display:block;padding:4px 16px;font-size:14px;color:var(--text);border-left:2px solid transparent}
.sidebar a:hover{background:var(--bg);text-decoration:none}
.sidebar a.active{border-left-color:var(--sidebar-active);color:var(--sidebar-active);font-weight:500}
.content{flex:1;max-width:900px;padding:32px 48px;margin:0 auto}

/* Typography */
h1{font-size:32px;font-weight:600;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border)}
h2{font-size:24px;font-weight:600;margin:32px 0 12px;color:var(--text)}
h3{font-size:18px;font-weight:600;margin:24px 0 8px}
p{margin:8px 0}
ul,ol{margin:8px 0 8px 24px}
li{margin:4px 0}

/* Code */
code{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;
  font-size:0.875em;background:var(--code-bg);border:1px solid var(--code-border);
  border-radius:4px;padding:2px 6px}
pre{background:var(--code-bg);border:1px solid var(--code-border);border-radius:var(--radius);
  padding:16px;overflow-x:auto;margin:12px 0;font-size:14px;line-height:1.5}
pre code{background:none;border:none;padding:0}

/* Cards */
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);
  padding:20px;margin:12px 0;box-shadow:var(--shadow)}
.card h3{margin-top:0}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin:16px 0}

/* Badges */
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;
  font-weight:600;color:#fff;vertical-align:middle}
.badge-function{background:var(--badge-fn)}
.badge-class{background:var(--badge-class)}
.badge-variable,.badge-constant{background:var(--badge-var)}
.badge-method{background:#e74c3c}
.badge-enum{background:#8250df}
.badge-package{background:var(--accent)}

/* Entry */
.entry{border:1px solid var(--border-light);border-radius:var(--radius);padding:16px;margin:12px 0}
.entry .signature{font-family:monospace;font-size:15px;font-weight:500}
.params{list-style:none;padding-left:0;margin:8px 0}
.params li{padding:4px 0;font-size:14px}
.params li code{font-size:13px}
.deprecated{background:#fff3cd;color:#856404;border-left:3px solid #ffc107;padding:8px 12px;margin:8px 0;border-radius:0 4px 4px 0}

/* Search */
.search-box{width:100%;padding:10px 14px;font-size:15px;border:1px solid var(--border);
  border-radius:var(--radius);background:var(--bg);color:var(--text);margin-bottom:20px}
.search-box:focus{border-color:var(--accent);outline:none;box-shadow:0 0 0 3px rgba(9,105,218,0.15)}

/* Package list */
.pkg-row{display:flex;align-items:center;padding:12px 0;border-bottom:1px solid var(--border-light)}
.pkg-row .pkg-name{font-weight:600;min-width:200px}
.pkg-row .pkg-version{color:var(--text-muted);font-size:13px;min-width:80px}
.pkg-row .pkg-desc{color:var(--text-muted);font-size:14px;flex:1}

/* Responsive */
@media(max-width:768px){
  .sidebar{display:none}
  .content{padding:20px}
  .card-grid{grid-template-columns:1fr}
  .site-header nav{display:none}
}

/* Table */
table{border-collapse:collapse;width:100%;margin:12px 0}
th,td{text-align:left;padding:8px 12px;border:1px solid var(--border)}
th{background:var(--bg-alt);font-weight:600;font-size:14px}
td{font-size:14px}

/* Footer */
.footer{text-align:center;padding:24px;color:var(--text-muted);font-size:13px;
  border-top:1px solid var(--border);margin-top:48px}
'''


# ═══════════════════════════════════════════════════════════
#  Site Generator
# ═══════════════════════════════════════════════════════════

class SiteGenerator:
    """Generate a complete static documentation website."""

    def __init__(self):
        self.pages = []  # list of (slug, title, section, html_content)
        self._nav_sections = {}

    def _esc(self, text: str) -> str:
        return html_mod.escape(str(text)) if text else ''

    # ── Page Shell ──

    def _page_shell(self, title: str, content: str, active_slug: str = '') -> str:
        """Wrap content in full HTML page with sidebar navigation."""
        sidebar_html = self._build_sidebar(active_slug)
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{self._esc(title)} — {SITE_TITLE}</title>
<meta name="description" content="{self._esc(SITE_DESCRIPTION)}">
<style>{SITE_CSS}</style>
</head>
<body>
<header class="site-header">
  <h1><a href="index.html" style="color:inherit;text-decoration:none">EPL</a></h1>
  <span class="version">v4.2</span>
  <nav>
    <a href="getting-started.html">Getting Started</a>
    <a href="reference.html">Reference</a>
    <a href="api.html">API</a>
    <a href="packages.html">Packages</a>
    <a href="tutorials.html">Tutorials</a>
  </nav>
</header>
<div class="layout">
<aside class="sidebar">
{sidebar_html}
</aside>
<main class="content">
{content}
</main>
</div>
<footer class="footer">EPL Documentation — Generated {time.strftime("%Y-%m-%d")}</footer>
</body>
</html>'''

    def _build_sidebar(self, active_slug: str) -> str:
        """Build sidebar navigation from registered pages."""
        html = ''
        sections = {}
        for slug, title, section, _ in self.pages:
            sections.setdefault(section, []).append((slug, title))

        for section_name, items in sections.items():
            html += f'<div class="section-title">{self._esc(section_name)}</div>\n'
            for slug, title in items:
                cls = ' class="active"' if slug == active_slug else ''
                html += f'<a href="{slug}.html"{cls}>{self._esc(title)}</a>\n'
        return html

    # ── Content Generators ──

    def _gen_index(self) -> str:
        return '''
<h1>EPL Documentation</h1>
<p>Welcome to the official documentation for <strong>EPL</strong> — the English Programming Language.
Write code using natural English syntax. No cryptic symbols, no arcane keywords.</p>

<div class="card-grid">
<div class="card">
  <h3>Getting Started</h3>
  <p>Install EPL, write your first program, and learn the basics in minutes.</p>
  <p><a href="getting-started.html">Start here &rarr;</a></p>
</div>
<div class="card">
  <h3>Language Reference</h3>
  <p>Complete reference for all EPL syntax: variables, functions, classes, loops, and more.</p>
  <p><a href="reference.html">Read reference &rarr;</a></p>
</div>
<div class="card">
  <h3>API Reference</h3>
  <p>Auto-generated documentation for all built-in functions, classes, and modules.</p>
  <p><a href="api.html">Browse API &rarr;</a></p>
</div>
<div class="card">
  <h3>50 Official Packages</h3>
  <p>Charts, auth, email, PDF, CSV, ORM, validation, and more — ready to install.</p>
  <p><a href="packages.html">Browse packages &rarr;</a></p>
</div>
<div class="card">
  <h3>Tutorials</h3>
  <p>Step-by-step guides for building real projects: web apps, CLI tools, data processing.</p>
  <p><a href="tutorials.html">View tutorials &rarr;</a></p>
</div>
<div class="card">
  <h3>Compiler &amp; VM</h3>
  <p>Compile to native executables with LLVM, or run faster with the bytecode VM.</p>
  <p><a href="compiler.html">Learn more &rarr;</a></p>
</div>
</div>

<h2>Quick Example</h2>
<pre><code>Create name equal to "World"
Print "Hello, " + name + "!"

Function Greet(person)
    Return "Welcome, " + person + "!"
End

Print Greet("EPL Developer")</code></pre>

<h2>Install</h2>
<pre><code># Requirements: Python 3.9+
pip install epl-lang

# Or clone and run directly
git clone https://github.com/epl-lang/epl.git
cd epl
python main.py examples/hello.epl</code></pre>
'''

    def _gen_getting_started(self) -> str:
        return '''
<h1>Getting Started</h1>

<h2>Installation</h2>
<p>EPL requires Python 3.9 or later. Install from PyPI or clone the repository:</p>
<pre><code># From PyPI
pip install epl-lang

# Or clone from GitHub
git clone https://github.com/epl-lang/epl.git
cd epl</code></pre>

<h2>Your First Program</h2>
<p>Create a file called <code>hello.epl</code>:</p>
<pre><code>Print "Hello, World!"
Print "Welcome to EPL!"</code></pre>
<p>Run it:</p>
<pre><code>python main.py hello.epl</code></pre>

<h2>Variables</h2>
<pre><code>Create name equal to "Alice"
Create age equal to 25
Create pi equal to 3.14159
Create active equal to true
Create items equal to List(1, 2, 3)

Set age to 26
Print name + " is " + to_text(age) + " years old"</code></pre>

<h2>Functions</h2>
<pre><code>Function Greet(name)
    Return "Hello, " + name + "!"
End

Print Greet("World")

Function Add(a, b)
    Return a + b
End

Print Add(3, 4)</code></pre>

<h2>Control Flow</h2>
<pre><code>Create score equal to 85

If score >= 90
    Print "Grade: A"
Otherwise if score >= 80
    Print "Grade: B"
Otherwise if score >= 70
    Print "Grade: C"
Else
    Print "Grade: F"
End</code></pre>

<h2>Loops</h2>
<pre><code># Repeat loop
Repeat 5 times
    Print "Hello!"
End

# While loop
Create count equal to 0
While count < 5
    Print count
    Set count to count + 1
End

# For range
For i from 1 to 10
    Print i
End

# For each
Create fruits equal to List("apple", "banana", "cherry")
For Each fruit in fruits
    Print fruit
End</code></pre>

<h2>Classes</h2>
<pre><code>Class Animal
    Function Init(name, sound)
        Set this.name to name
        Set this.sound to sound
    End

    Function Speak()
        Print this.name + " says " + this.sound
    End
End

Create dog equal to new Animal("Rex", "Woof!")
Call dog.Speak()</code></pre>

<h2>Packages</h2>
<pre><code># Initialize a project
python main.py init

# Install a package
python main.py install epl-math

# Use it in your code
Import "epl-math" as Math
Print Math::PI()</code></pre>

<h2>Next Steps</h2>
<ul>
  <li><a href="reference.html">Language Reference</a> — Complete syntax guide</li>
  <li><a href="tutorials.html">Tutorials</a> — Build real projects</li>
  <li><a href="packages.html">Packages</a> — Browse 50 official packages</li>
  <li><a href="api.html">API Reference</a> — Built-in functions and modules</li>
</ul>
'''

    def _gen_reference(self) -> str:
        return '''
<h1>Language Reference</h1>

<h2>Data Types</h2>
<table>
<tr><th>Type</th><th>Example</th><th>Description</th></tr>
<tr><td>Integer</td><td><code>42</code></td><td>Whole numbers</td></tr>
<tr><td>Decimal</td><td><code>3.14</code></td><td>Floating-point numbers</td></tr>
<tr><td>Text</td><td><code>"hello"</code></td><td>String values</td></tr>
<tr><td>Boolean</td><td><code>true</code>, <code>false</code></td><td>Logical values</td></tr>
<tr><td>Nothing</td><td><code>nothing</code></td><td>Null/none value</td></tr>
<tr><td>List</td><td><code>List(1, 2, 3)</code></td><td>Ordered collection</td></tr>
<tr><td>Map</td><td><code>Map("key", value)</code></td><td>Key-value pairs</td></tr>
</table>

<h2>Variables</h2>
<pre><code># Create (declare + assign)
Create x equal to 10
Create name equal to "EPL"

# Set (reassign)
Set x to 20

# Constants
Constant PI equal to 3.14159</code></pre>

<h2>Operators</h2>
<table>
<tr><th>Operator</th><th>Symbol</th><th>Example</th></tr>
<tr><td>Add</td><td><code>+</code></td><td><code>a + b</code></td></tr>
<tr><td>Subtract</td><td><code>-</code></td><td><code>a - b</code></td></tr>
<tr><td>Multiply</td><td><code>*</code></td><td><code>a * b</code></td></tr>
<tr><td>Divide</td><td><code>/</code></td><td><code>a / b</code></td></tr>
<tr><td>Modulo</td><td><code>%</code></td><td><code>a % b</code></td></tr>
<tr><td>Power</td><td><code>**</code></td><td><code>a ** b</code></td></tr>
<tr><td>Floor Divide</td><td><code>//</code></td><td><code>a // b</code></td></tr>
<tr><td>Equal</td><td><code>==</code> / <code>is equal to</code></td><td><code>a == b</code></td></tr>
<tr><td>Not Equal</td><td><code>!=</code> / <code>is not equal to</code></td><td><code>a != b</code></td></tr>
<tr><td>Greater</td><td><code>&gt;</code> / <code>is greater than</code></td><td><code>a &gt; b</code></td></tr>
<tr><td>Less</td><td><code>&lt;</code> / <code>is less than</code></td><td><code>a &lt; b</code></td></tr>
<tr><td>And</td><td><code>and</code></td><td><code>a and b</code></td></tr>
<tr><td>Or</td><td><code>or</code></td><td><code>a or b</code></td></tr>
<tr><td>Not</td><td><code>not</code></td><td><code>not a</code></td></tr>
</table>

<h2>Control Flow</h2>
<h3>If / Otherwise / Else</h3>
<pre><code>If condition
    Note: body
Otherwise if other_condition
    Note: body
Else
    Note: body
End</code></pre>

<h3>Match / When</h3>
<pre><code>Match value
    When 1
        Print "one"
    When 2
        Print "two"
    Default
        Print "other"
End</code></pre>

<h2>Loops</h2>
<pre><code># While loop
While condition
    Note: body
End

# Repeat N times
Repeat 10 times
    Note: body
End

# For range (inclusive)
For i from 1 to 10
    Note: body
End

# For range with step
For i from 0 to 100 step 5
    Note: body
End

# For each
For Each item in collection
    Note: body
End

# Break and Continue
While true
    If done
        Break
    End
    Continue
End</code></pre>

<h2>Functions</h2>
<pre><code># Basic function
Function Name(param1, param2)
    Return result
End

# With default parameters
Function Greet(name, greeting: "Hello")
    Return greeting + ", " + name
End

# Lambda
Create double equal to Lambda(x) => x * 2</code></pre>

<h2>Classes</h2>
<pre><code>Class ClassName
    Function Init(params)
        Set this.prop to value
    End

    Function MethodName()
        Return this.prop
    End
End

# Inheritance
Class Child extends Parent
    Function Init()
        Call Super()
    End
End

# Instantiation
Create obj equal to new ClassName(args)</code></pre>

<h2>Error Handling</h2>
<pre><code>Try
    Note: risky code
Catch error
    Print "Error: " + error
Finally
    Note: always runs
End

Throw "Custom error message"</code></pre>

<h2>Modules &amp; Imports</h2>
<pre><code># Import a file
Import "utils.epl"

# Import with alias
Import "math_lib.epl" as Math

# Use aliased module
Print Math::PI()

# Define a module
Module Utils
    Export Function Helper()
        Return "help"
    End
End

# Python bridge
Use python "json"
Create data equal to json::loads(text)</code></pre>

<h2>File I/O</h2>
<pre><code># Write
Write "content" to file "output.txt"

# Read
Read data from file "input.txt"
Print data

# Append
Append "more" to file "output.txt"</code></pre>

<h2>Async / Await</h2>
<pre><code>Async Function FetchData(url)
    Create result equal to Await http_get(url)
    Return result
End</code></pre>
'''

    def _gen_tutorials(self) -> str:
        return '''
<h1>Tutorials</h1>
<p>Learn EPL by building real projects.</p>

<div class="card-grid">
<div class="card">
<h3>Tutorial 1: Calculator</h3>
<p>Build an interactive calculator with functions and error handling.</p>
</div>
<div class="card">
<h3>Tutorial 2: To-Do List</h3>
<p>Create a task manager with lists, file persistence, and a menu system.</p>
</div>
<div class="card">
<h3>Tutorial 3: Web API</h3>
<p>Build a REST API with routes, JSON responses, and database storage.</p>
</div>
<div class="card">
<h3>Tutorial 4: Data Processing</h3>
<p>Read CSV files, transform data, and generate charts.</p>
</div>
</div>

<h2>Tutorial 1: Calculator</h2>
<pre><code>Note: Simple Calculator in EPL

Function Calculate(a, op, b)
    If op == "+"
        Return a + b
    Otherwise if op == "-"
        Return a - b
    Otherwise if op == "*"
        Return a * b
    Otherwise if op == "/"
        If b == 0
            Throw "Cannot divide by zero"
        End
        Return a / b
    Else
        Throw "Unknown operator: " + op
    End
End

Print "EPL Calculator"
Print "=============="

Try
    Print Calculate(10, "+", 5)
    Print Calculate(10, "-", 3)
    Print Calculate(10, "*", 4)
    Print Calculate(10, "/", 2)
Catch error
    Print "Error: " + error
End</code></pre>

<h2>Tutorial 2: To-Do Manager</h2>
<pre><code>Note: To-Do List Manager

Create tasks equal to List()

Function AddTask(title)
    Create task equal to Map()
    Set task["title"] to title
    Set task["done"] to false
    Call append(tasks, task)
    Print "Added: " + title
End

Function ListTasks()
    If length(tasks) == 0
        Print "No tasks yet!"
        Return
    End
    Create i equal to 1
    For Each task in tasks
        Create status equal to "[x]"
        If task["done"] == false
            Set status to "[ ]"
        End
        Print to_text(i) + ". " + status + " " + task["title"]
        Set i to i + 1
    End
End

Function CompleteTask(index)
    If index < 1 or index > length(tasks)
        Print "Invalid task number"
        Return
    End
    Set tasks[index - 1]["done"] to true
    Print "Completed: " + tasks[index - 1]["title"]
End

Call AddTask("Learn EPL basics")
Call AddTask("Build a project")
Call AddTask("Read the docs")
Call CompleteTask(1)
Call ListTasks()</code></pre>

<h2>Tutorial 3: Web API</h2>
<pre><code>Note: REST API with EPL Web Framework

Create App "TaskAPI" on port 8080

Create tasks equal to List()
Create next_id equal to 1

Route GET "/tasks"
    Send JSON tasks
End

Route POST "/tasks"
    Create task equal to Map()
    Set task["id"] to next_id
    Set task["title"] to request["body"]["title"]
    Set task["done"] to false
    Call append(tasks, task)
    Set next_id to next_id + 1
    Send JSON task
End

Start App</code></pre>

<h2>Tutorial 4: Data Processing</h2>
<pre><code>Note: Data processing with EPL

Import "epl-csv" as CSV
Import "epl-charts" as Charts

Note: Read sales data
Create data equal to CSV::ReadFile("sales.csv")

Note: Calculate totals by category
Create totals equal to Map()
For Each row in data
    Create category equal to row["category"]
    Create amount equal to to_decimal(row["amount"])
    If totals[category] == nothing
        Set totals[category] to 0
    End
    Set totals[category] to totals[category] + amount
End

Note: Generate chart
Create labels equal to keys(totals)
Create values equal to List()
For Each label in labels
    Call append(values, totals[label])
End

Create chart equal to Charts::BarChart("Sales by Category", labels, values, 800, 400)
Call Charts::SaveChart(chart, "sales_chart.svg")
Print "Chart saved to sales_chart.svg"</code></pre>
'''

    def _gen_packages(self) -> str:
        """Generate the packages directory page."""
        try:
            from epl.package_manager import BUILTIN_REGISTRY
        except ImportError:
            BUILTIN_REGISTRY = {}

        categories = {
            'Core': [], 'Data': [], 'Web': [], 'Security': [],
            'DevTools': [], 'Utility': [], 'Communication': []
        }

        cat_map = {
            'epl-math': 'Core', 'epl-string': 'Core', 'epl-collections': 'Core',
            'epl-json': 'Data', 'epl-csv': 'Data', 'epl-xml': 'Data',
            'epl-db': 'Data', 'epl-database': 'Data', 'epl-orm': 'Data',
            'epl-http': 'Web', 'epl-web': 'Web', 'epl-wsgi': 'Web',
            'epl-websocket': 'Web', 'epl-template': 'Web',
            'epl-crypto': 'Security', 'epl-auth': 'Security',
            'epl-rate-limit': 'Security', 'epl-validation': 'Security',
            'epl-testing': 'DevTools', 'epl-debug': 'DevTools',
            'epl-profiler': 'DevTools', 'epl-types': 'DevTools',
            'epl-logging': 'DevTools', 'epl-cli': 'DevTools',
            'epl-email': 'Communication', 'epl-networking': 'Communication',
            'epl-i18n': 'Communication',
        }

        for name in sorted(BUILTIN_REGISTRY.keys()):
            info = BUILTIN_REGISTRY[name]
            cat = cat_map.get(name, 'Utility')
            categories[cat].append((name, info))

        html = '<h1>Official Packages</h1>\n'
        html += f'<p>EPL ships with <strong>{len(BUILTIN_REGISTRY)}</strong> official packages. '
        html += 'Install any package with <code>python main.py install &lt;name&gt;</code>.</p>\n'
        html += '<input class="search-box" type="text" placeholder="Search packages..." '
        html += 'oninput="filterPkgs(this.value)">\n'

        for cat_name in ['Core', 'Data', 'Web', 'Security', 'Communication', 'DevTools', 'Utility']:
            pkgs = categories.get(cat_name, [])
            if not pkgs:
                continue
            html += f'<h2>{self._esc(cat_name)} ({len(pkgs)})</h2>\n'
            for name, info in pkgs:
                desc = self._esc(info.get('description', ''))
                ver = self._esc(info.get('version', '1.0.0'))
                html += f'<div class="pkg-row" data-name="{self._esc(name)}">'
                html += f'<span class="pkg-name">{self._esc(name)}</span>'
                html += f'<span class="pkg-version">v{ver}</span>'
                html += f'<span class="pkg-desc">{desc}</span>'
                html += '</div>\n'

        html += '''
<h2>Installing Packages</h2>
<pre><code># Install from built-in registry
python main.py install epl-math

# Install from GitHub
python main.py install github:user/repo

# Install from URL
python main.py install https://example.com/package.zip

# List installed packages
python main.py packages

# Search for packages
python main.py search charts</code></pre>

<h2>Publishing Packages</h2>
<pre><code># Initialize your project
python main.py init my-package

# Edit epl.json with your details
# Add your code in main.epl

# Validate your package
python main.py publish --dry-run

# Publish to registry
python main.py publish</code></pre>

<script>
function filterPkgs(q){
  q=q.toLowerCase();
  document.querySelectorAll('.pkg-row').forEach(el=>{
    const n=el.dataset.name||'';
    const d=el.querySelector('.pkg-desc');
    const text=n+(d?d.textContent:'');
    el.style.display=text.toLowerCase().includes(q)||!q?'flex':'none';
  });
}
</script>'''
        return html

    def _gen_api(self, source_dirs: List[str] = None) -> str:
        """Generate API reference from source files."""
        html = '<h1>API Reference</h1>\n'
        html += '<p>Auto-generated from EPL source files.</p>\n'
        html += '<input class="search-box" type="text" placeholder="Search functions, classes..." '
        html += 'oninput="filterEntries(this.value)">\n'

        if source_dirs:
            try:
                from epl.doc_linter import DocGenerator
                gen = DocGenerator()
                for d in source_dirs:
                    if os.path.isdir(d):
                        gen.parse_directory(d)
                    elif os.path.isfile(d):
                        gen.parse_file(d)

                for mod in gen.modules:
                    html += f'<h2 id="{self._esc(mod.name)}">{self._esc(mod.name)}</h2>\n'
                    if mod.description:
                        html += f'<p>{self._esc(mod.description)}</p>\n'
                    for entry in mod.entries:
                        html += self._entry_html(entry)
            except Exception as e:
                html += f'<p>Error generating API docs: {self._esc(str(e))}</p>\n'

        # Built-in functions reference
        html += '<h2>Built-in Functions</h2>\n'
        builtins = [
            ('length(x)', 'Returns the length of a string, list, or map'),
            ('type_of(x)', 'Returns the type name of a value as text'),
            ('to_integer(x)', 'Converts a value to an integer'),
            ('to_text(x)', 'Converts a value to a text string'),
            ('to_decimal(x)', 'Converts a value to a decimal number'),
            ('to_boolean(x)', 'Converts a value to a boolean'),
            ('absolute(x)', 'Returns the absolute value'),
            ('round(x)', 'Rounds to the nearest integer'),
            ('floor(x)', 'Rounds down to the nearest integer'),
            ('ceil(x)', 'Rounds up to the nearest integer'),
            ('sqrt(x)', 'Returns the square root'),
            ('power(base, exp)', 'Returns base raised to exp'),
            ('max(a, b)', 'Returns the larger value'),
            ('min(a, b)', 'Returns the smaller value'),
            ('random(low, high)', 'Returns a random integer in range'),
            ('uppercase(s)', 'Converts string to uppercase'),
            ('lowercase(s)', 'Converts string to lowercase'),
            ('trim(s)', 'Removes leading/trailing whitespace'),
            ('split(s, sep)', 'Splits string into a list'),
            ('join(list, sep)', 'Joins list elements into a string'),
            ('replace(s, old, new)', 'Replaces occurrences in a string'),
            ('contains(s, sub)', 'Checks if string contains substring'),
            ('starts_with(s, prefix)', 'Checks if string starts with prefix'),
            ('ends_with(s, suffix)', 'Checks if string ends with suffix'),
            ('index_of(s, sub)', 'Returns index of first occurrence, or -1'),
            ('substring(s, start, end)', 'Returns a substring'),
            ('append(list, item)', 'Adds an item to a list'),
            ('remove(list, index)', 'Removes item at index from list'),
            ('sort(list)', 'Sorts a list in place'),
            ('reverse(list)', 'Reverses a list in place'),
            ('unique(list)', 'Returns a list with duplicates removed'),
            ('keys(map)', 'Returns the keys of a map as a list'),
            ('values(map)', 'Returns the values of a map as a list'),
            ('sum(list)', 'Returns the sum of numeric list elements'),
            ('range(n)', 'Returns a list of integers from 0 to n-1'),
            ('sorted(list)', 'Returns a new sorted list'),
            ('reversed(list)', 'Returns a new reversed list'),
            ('time_now()', 'Returns current timestamp in milliseconds'),
            ('read_file(path)', 'Reads file contents as text'),
            ('write_file(path, data)', 'Writes text to a file'),
            ('file_exists(path)', 'Checks if a file exists'),
        ]
        html += '<table>\n<tr><th>Function</th><th>Description</th></tr>\n'
        for sig, desc in builtins:
            html += f'<tr><td><code>{self._esc(sig)}</code></td><td>{self._esc(desc)}</td></tr>\n'
        html += '</table>\n'

        html += '''
<script>
function filterEntries(q){
  q=q.toLowerCase();
  document.querySelectorAll('.entry').forEach(el=>{
    const n=el.dataset.name||'';
    el.style.display=n.toLowerCase().includes(q)||!q?'block':'none';
  });
}
</script>'''
        return html

    def _entry_html(self, entry) -> str:
        """Render a DocEntry as HTML."""
        badge = entry.kind
        h = f'<div class="entry" data-name="{self._esc(entry.name)}">\n'
        h += f'<span class="badge badge-{badge}">{badge}</span> '
        h += f'<span class="signature">{self._esc(entry.name)}'
        if entry.kind in ('function', 'method') and entry.params:
            params = ', '.join(p.name for p in entry.params)
            h += f'({self._esc(params)})'
        h += '</span>\n'
        if entry.deprecated:
            h += f'<div class="deprecated">Deprecated: {self._esc(entry.deprecated)}</div>\n'
        if entry.description:
            h += f'<p>{self._esc(entry.description)}</p>\n'
        if entry.params:
            h += '<ul class="params">\n'
            for p in entry.params:
                h += f'<li><code>{self._esc(p.name)}</code>'
                if p.type_hint:
                    h += f' <code>{self._esc(p.type_hint)}</code>'
                if p.description:
                    h += f' — {self._esc(p.description)}'
                h += '</li>\n'
            h += '</ul>\n'
        if entry.returns:
            h += f'<p><strong>Returns:</strong> {self._esc(entry.returns)}</p>\n'
        if entry.source:
            h += f'<details><summary>Source</summary><pre><code>{self._esc(entry.source)}</code></pre></details>\n'
        for child in entry.children:
            h += self._entry_html(child)
        h += '</div>\n'
        return h

    def _gen_compiler(self) -> str:
        return '''
<h1>Compiler &amp; VM</h1>

<h2>LLVM Compiler</h2>
<p>EPL can compile programs to native machine code using LLVM, with a mark-and-sweep garbage collector.</p>

<h3>Compile to Executable</h3>
<pre><code># Compile an EPL file to native executable
python main.py compile my_program.epl

# This generates:
#   my_program.ll   — LLVM IR (intermediate representation)
#   my_program.exe  — Native executable (via clang)</code></pre>

<h3>View LLVM IR</h3>
<pre><code># Show the generated LLVM IR without compiling
python main.py ir my_program.epl</code></pre>

<h3>Requirements</h3>
<ul>
  <li><code>pip install llvmlite</code> — LLVM Python bindings</li>
  <li>Clang/LLVM toolchain installed (<code>winget install LLVM.LLVM</code> on Windows)</li>
</ul>

<h3>Supported Features</h3>
<ul>
  <li>Integer and float arithmetic</li>
  <li>String operations (concat, length, comparison)</li>
  <li>Functions with parameters and return values</li>
  <li>If/else, while, for, repeat loops</li>
  <li>Lists, maps, and objects</li>
  <li>Classes with methods and properties</li>
  <li>Mark-and-sweep garbage collection</li>
  <li>GC-safe loops with root stack management</li>
</ul>

<h2>Bytecode VM</h2>
<p>For faster interpretation without native compilation, use the bytecode VM:</p>
<pre><code># Run with the VM (10-50x faster than tree-walking interpreter)
python main.py vm my_program.epl</code></pre>

<h2>Transpilers</h2>
<pre><code># Transpile to JavaScript
python main.py js my_program.epl

# Transpile to Python
python main.py python my_program.epl

# Transpile to Kotlin
python main.py kotlin my_program.epl

# Generate Android project
python main.py android my_program.epl</code></pre>
'''

    # ── Build Site ──

    def generate(self, source_dirs: List[str] = None, output_dir: str = None):
        """Generate the complete documentation site."""
        if output_dir is None:
            output_dir = os.path.join('docs', 'site')

        # Register all pages
        self.pages = [
            ('index', 'Home', 'Overview', self._gen_index()),
            ('getting-started', 'Getting Started', 'Guide', self._gen_getting_started()),
            ('reference', 'Language Reference', 'Guide', self._gen_reference()),
            ('api', 'API Reference', 'Reference', self._gen_api(source_dirs)),
            ('packages', 'Packages', 'Reference', self._gen_packages()),
            ('tutorials', 'Tutorials', 'Guide', self._gen_tutorials()),
            ('compiler', 'Compiler & VM', 'Reference', self._gen_compiler()),
        ]

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate each page
        for slug, title, section, content in self.pages:
            html = self._page_shell(title, content, active_slug=slug)
            filepath = os.path.join(output_dir, f'{slug}.html')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)

        return output_dir, len(self.pages)


def generate_site(source_dirs: List[str] = None, output_dir: str = None):
    """Public API to generate the documentation site."""
    gen = SiteGenerator()
    out_dir, page_count = gen.generate(source_dirs, output_dir)
    return out_dir, page_count
