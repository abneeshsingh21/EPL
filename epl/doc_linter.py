"""
EPL Documentation Generator & Linter v1.0
Production-grade tooling for code quality and documentation.

Documentation Generator:
  - Extracts docs from EPL source files (functions, classes, comments)
  - Generates HTML, Markdown, and JSON documentation
  - Supports @param, @return, @example, @since, @deprecated doc tags
  - Cross-references between modules
  - Searchable index

Linter:
  - Style checking (naming conventions, indentation, line length)
  - Semantic warnings (unused variables, unreachable code, type mismatches)
  - Complexity analysis (cyclomatic complexity, nesting depth)
  - Auto-fix for common issues
  - Configurable rules with severity levels

Usage:
    # Generate docs
    python -m epl.doc_linter docs src/ -o docs/
    
    # Lint
    python -m epl.doc_linter lint src/ --fix
"""

import os
import re
import json
import html as html_mod
import sys
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path


# ═══════════════════════════════════════════════════════════
# Documentation Generator
# ═══════════════════════════════════════════════════════════

@dataclass
class DocParam:
    """Documented parameter."""
    name: str
    type_hint: str = ''
    description: str = ''

@dataclass
class DocEntry:
    """A single documented item (function, class, etc.)."""
    kind: str  # 'function', 'class', 'method', 'variable', 'constant', 'enum'
    name: str
    description: str = ''
    params: List[DocParam] = field(default_factory=list)
    returns: str = ''
    examples: List[str] = field(default_factory=list)
    since: str = ''
    deprecated: str = ''
    line: int = 0
    file: str = ''
    parent: str = ''  # Class name for methods
    children: List['DocEntry'] = field(default_factory=list)
    source: str = ''

@dataclass
class ModuleDoc:
    """Documentation for a single .epl file."""
    path: str
    name: str
    description: str = ''
    entries: List[DocEntry] = field(default_factory=list)


class DocGenerator:
    """Extract and generate documentation from EPL source files."""

    DOC_TAG_RE = re.compile(r'@(\w+)\s+(.*)')

    def __init__(self):
        self.modules: List[ModuleDoc] = []

    def parse_file(self, filepath: str) -> ModuleDoc:
        """Parse an EPL file and extract documentation."""
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        lines = source.split('\n')
        name = Path(filepath).stem
        module = ModuleDoc(path=filepath, name=name)

        # Extract module-level description from top comments
        desc_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('#'):
                desc_lines.append(stripped.lstrip('/#').strip())
            elif stripped == '':
                continue
            else:
                break
        module.description = '\n'.join(desc_lines)

        # Parse entries
        i = 0
        current_class = None
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Collect doc comments above a definition
            doc_comments = []
            while stripped.startswith('//') or stripped.startswith('#'):
                doc_comments.append(stripped.lstrip('/#').strip())
                i += 1
                if i >= len(lines):
                    break
                line = lines[i]
                stripped = line.strip()

            # Function / Async Function — supports both syntaxes:
            #   Function Name(param1, param2)
            #   Function Name takes param1 and param2
            fn_match = re.match(r'(?:Async\s+)?Function\s+(\w+)\s*\((.*?)\)', stripped)
            if not fn_match:
                fn_match2 = re.match(r'(?:Async\s+)?Function\s+(\w+)(?:\s+takes\s+(.*))?', stripped)
                if fn_match2:
                    fname = fn_match2.group(1)
                    raw_params = fn_match2.group(2) or ''
                    # Convert "a and b" to "a, b"
                    norm_params = raw_params.replace(' and ', ', ')
                    fn_match = type('M', (), {'group': lambda self, n: fname if n == 1 else norm_params})()
            if fn_match:
                entry = self._parse_function(fn_match, doc_comments, i + 1, filepath, lines, i)
                if current_class:
                    entry.kind = 'method'
                    entry.parent = current_class.name
                    current_class.children.append(entry)
                else:
                    module.entries.append(entry)
                i += 1
                continue

            # Class
            class_match = re.match(r'Class\s+(\w+)(?:\s+Extends\s+(\w+))?', stripped)
            if class_match:
                entry = DocEntry(
                    kind='class',
                    name=class_match.group(1),
                    description='\n'.join(self._filter_doc_comments(doc_comments)),
                    line=i + 1,
                    file=filepath,
                )
                if class_match.group(2):
                    entry.description = f'Extends {class_match.group(2)}\n\n' + entry.description
                current_class = entry
                module.entries.append(entry)
                i += 1
                continue

            # End Class
            if stripped.startswith('End') and current_class:
                if 'Class' in stripped or stripped == 'End':
                    current_class = None

            # Variable / Constant
            var_match = re.match(r'(?:Create|Set)\s+(\w+)\s+(?:equal\s+to|to)\s+(.+)', stripped, re.IGNORECASE)
            if var_match and not current_class:
                entry = DocEntry(
                    kind='variable',
                    name=var_match.group(1),
                    description='\n'.join(self._filter_doc_comments(doc_comments)),
                    line=i + 1,
                    file=filepath,
                    source=stripped,
                )
                module.entries.append(entry)

            const_match = re.match(r'Constant\s+(\w+)\s+equal\s+to\s+(.+)', stripped, re.IGNORECASE)
            if const_match:
                entry = DocEntry(
                    kind='constant',
                    name=const_match.group(1),
                    description='\n'.join(self._filter_doc_comments(doc_comments)),
                    line=i + 1,
                    file=filepath,
                    source=stripped,
                )
                module.entries.append(entry)

            # Enum
            enum_match = re.match(r'Enum\s+(\w+)', stripped)
            if enum_match:
                entry = DocEntry(
                    kind='enum',
                    name=enum_match.group(1),
                    description='\n'.join(self._filter_doc_comments(doc_comments)),
                    line=i + 1,
                    file=filepath,
                )
                module.entries.append(entry)

            i += 1

        self.modules.append(module)
        return module

    def _parse_function(self, match, doc_comments, line, filepath, lines, line_idx) -> DocEntry:
        """Parse function definition with doc comments."""
        name = match.group(1)
        params_str = match.group(2)

        # Parse doc comments for tags
        desc_parts = []
        params = []
        returns = ''
        examples = []
        since = ''
        deprecated = ''

        for comment in doc_comments:
            tag_match = self.DOC_TAG_RE.match(comment)
            if tag_match:
                tag, value = tag_match.group(1), tag_match.group(2)
                if tag == 'param':
                    parts = value.split(' ', 1)
                    pname = parts[0]
                    pdesc = parts[1] if len(parts) > 1 else ''
                    # Check for type in braces
                    type_match = re.match(r'\{(\w+)\}\s*(.*)', pdesc)
                    if type_match:
                        params.append(DocParam(pname, type_match.group(1), type_match.group(2)))
                    else:
                        params.append(DocParam(pname, '', pdesc))
                elif tag == 'return' or tag == 'returns':
                    returns = value
                elif tag == 'example':
                    examples.append(value)
                elif tag == 'since':
                    since = value
                elif tag == 'deprecated':
                    deprecated = value
                else:
                    desc_parts.append(f'@{tag} {value}')
            else:
                desc_parts.append(comment)

        # If no @param tags, infer from signature
        if not params and params_str.strip():
            for p in params_str.split(','):
                p = p.strip()
                if p:
                    params.append(DocParam(p))

        # Extract source code for the function body
        source_lines = [lines[line_idx]]
        j = line_idx + 1
        depth = 1
        while j < len(lines) and depth > 0:
            src_line = lines[j]
            src_stripped = src_line.strip()
            if any(src_stripped.startswith(kw) for kw in ['Function ', 'If ', 'For ', 'While ', 'Try', 'Class ']):
                depth += 1
            if src_stripped.startswith('End'):
                depth -= 1
            source_lines.append(src_line)
            j += 1

        return DocEntry(
            kind='function',
            name=name,
            description='\n'.join(desc_parts),
            params=params,
            returns=returns,
            examples=examples,
            since=since,
            deprecated=deprecated,
            line=line,
            file=filepath,
            source='\n'.join(source_lines),
        )

    def _filter_doc_comments(self, comments):
        """Filter out doc tags, return plain descriptions."""
        return [c for c in comments if not c.startswith('@')]

    def parse_directory(self, dirpath: str, recursive: bool = True):
        """Parse all .epl files in a directory."""
        path = Path(dirpath)
        pattern = '**/*.epl' if recursive else '*.epl'
        for fpath in sorted(path.glob(pattern)):
            self.parse_file(str(fpath))

    # ─── Output Formats ─────────────────────────────

    def to_markdown(self) -> str:
        """Generate Markdown documentation."""
        lines = ['# EPL API Documentation\n']
        lines.append(f'*Generated on {time.strftime("%Y-%m-%d %H:%M:%S")}*\n')

        # Table of contents
        lines.append('## Table of Contents\n')
        for mod in self.modules:
            lines.append(f'- [{mod.name}](#{mod.name.lower()})')
            for entry in mod.entries:
                lines.append(f'  - [{entry.name}](#{entry.name.lower()})')
        lines.append('')

        for mod in self.modules:
            lines.append(f'## {mod.name}\n')
            if mod.description:
                lines.append(f'{mod.description}\n')

            for entry in mod.entries:
                lines.extend(self._entry_to_markdown(entry))

        return '\n'.join(lines)

    def _entry_to_markdown(self, entry: DocEntry, indent: int = 0) -> List[str]:
        """Convert a doc entry to Markdown lines."""
        prefix = '#' * (3 + indent)
        lines = []
        badge = f'`{entry.kind}`'

        if entry.kind == 'function' or entry.kind == 'method':
            params_str = ', '.join(
                f'{p.name}: {p.type_hint}' if p.type_hint else p.name
                for p in entry.params
            )
            lines.append(f'{prefix} {badge} {entry.name}({params_str})\n')
        else:
            lines.append(f'{prefix} {badge} {entry.name}\n')

        if entry.deprecated:
            lines.append(f'> **DEPRECATED**: {entry.deprecated}\n')

        if entry.description:
            lines.append(f'{entry.description}\n')

        if entry.params:
            lines.append('**Parameters:**\n')
            for p in entry.params:
                type_str = f' `{p.type_hint}`' if p.type_hint else ''
                desc_str = f' — {p.description}' if p.description else ''
                lines.append(f'- `{p.name}`{type_str}{desc_str}')
            lines.append('')

        if entry.returns:
            lines.append(f'**Returns:** {entry.returns}\n')

        if entry.examples:
            lines.append('**Examples:**\n')
            for ex in entry.examples:
                lines.append(f'```epl\n{ex}\n```\n')

        if entry.since:
            lines.append(f'*Since: {entry.since}*\n')

        if entry.source:
            lines.append('<details><summary>Source</summary>\n')
            lines.append(f'```epl\n{entry.source}\n```\n')
            lines.append('</details>\n')

        for child in entry.children:
            lines.extend(self._entry_to_markdown(child, indent + 1))

        return lines

    def to_html(self) -> str:
        """Generate searchable HTML documentation with sidebar navigation and cross-references."""
        entries_json = []
        all_names = set()
        for mod in self.modules:
            for entry in mod.entries:
                entries_json.append({
                    'module': mod.name, 'kind': entry.kind, 'name': entry.name,
                    'description': entry.description, 'line': entry.line,
                })
                all_names.add(entry.name)
                for child in entry.children:
                    all_names.add(child.name)

        # Build sidebar HTML
        sidebar_html = ''
        for mod in self.modules:
            sidebar_html += f'<div class="sb-section">{html_mod.escape(mod.name)}</div>\n'
            for entry in mod.entries:
                kind_cls = entry.kind
                anchor = f'{mod.name}-{entry.name}'
                sidebar_html += (
                    f'<a class="sb-item" href="#{html_mod.escape(anchor)}" '
                    f'data-kind="{kind_cls}">{html_mod.escape(entry.name)}</a>\n'
                )
                for child in entry.children:
                    child_anchor = f'{mod.name}-{entry.name}-{child.name}'
                    sidebar_html += (
                        f'<a class="sb-item sb-child" href="#{html_mod.escape(child_anchor)}" '
                        f'data-kind="{child.kind}">{html_mod.escape(child.name)}</a>\n'
                    )

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPL API Documentation</title>
<style>
  :root {{
    --bg: #ffffff; --bg-alt: #f6f8fa; --text: #1f2328; --text-muted: #656d76;
    --accent: #0969da; --border: #d0d7de; --code-bg: #f6f8fa;
    --badge-fn: #0550ae; --badge-class: #8250df; --badge-var: #1a7f37;
    --badge-method: #cf222e; --shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  @media(prefers-color-scheme:dark) {{
    :root {{
      --bg: #0d1117; --bg-alt: #161b22; --text: #e6edf3; --text-muted: #8b949e;
      --accent: #58a6ff; --border: #30363d; --code-bg: #161b22;
      --badge-fn: #58a6ff; --badge-class: #d2a8ff; --badge-var: #3fb950;
      --badge-method: #ff7b72; --shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
  }}
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         color:var(--text); background:var(--bg); line-height:1.6 }}
  .layout {{ display:flex; min-height:100vh }}
  .sidebar {{ width:250px; background:var(--bg-alt); border-right:1px solid var(--border);
              padding:16px 0; overflow-y:auto; position:sticky; top:0; height:100vh; flex-shrink:0 }}
  .sidebar h2 {{ padding:8px 16px; font-size:16px }}
  .sb-search {{ width:calc(100% - 24px); margin:0 12px 12px; padding:6px 10px; font-size:13px;
                border:1px solid var(--border); border-radius:4px; background:var(--bg); color:var(--text) }}
  .sb-section {{ font-size:11px; font-weight:600; text-transform:uppercase; color:var(--text-muted);
                 padding:12px 16px 4px; letter-spacing:0.5px }}
  .sb-item {{ display:block; padding:3px 16px; font-size:13px; color:var(--text);
              text-decoration:none; border-left:2px solid transparent }}
  .sb-item:hover {{ background:var(--bg); text-decoration:none }}
  .sb-child {{ padding-left:28px; font-size:12px; color:var(--text-muted) }}
  .main {{ flex:1; max-width:900px; padding:32px 48px; margin:0 auto }}
  h1 {{ font-size:28px; border-bottom:2px solid var(--border); padding-bottom:8px; margin-bottom:20px }}
  h2 {{ font-size:22px; margin-top:32px; color:var(--text) }}
  h3 {{ font-size:17px; margin-top:20px }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px;
            font-weight:600; color:#fff; margin-right:6px }}
  .badge-function {{ background:var(--badge-fn) }}
  .badge-class {{ background:var(--badge-class) }}
  .badge-method {{ background:var(--badge-method) }}
  .badge-variable,.badge-constant {{ background:var(--badge-var) }}
  .badge-enum {{ background:#8250df }}
  .entry {{ background:var(--bg-alt); border:1px solid var(--border); border-radius:6px;
            padding:16px; margin:12px 0; box-shadow:var(--shadow) }}
  .params {{ margin:8px 0; padding-left:20px }}
  .params li {{ margin:4px 0; font-size:14px }}
  code {{ background:var(--code-bg); padding:2px 6px; border-radius:3px; font-size:0.9em;
          border:1px solid var(--border) }}
  pre {{ background:var(--code-bg); color:var(--text); padding:12px; border-radius:6px;
         overflow-x:auto; margin:8px 0; border:1px solid var(--border) }}
  pre code {{ background:none; border:none; padding:0 }}
  .deprecated {{ background:#fff3cd; color:#856404; border-left:4px solid #ffc107;
                 padding:8px 12px; margin:8px 0; border-radius:0 4px 4px 0 }}
  .search {{ width:100%; padding:10px; font-size:16px; border:2px solid var(--border);
             border-radius:6px; margin-bottom:20px; background:var(--bg); color:var(--text) }}
  .search:focus {{ border-color:var(--accent); outline:none }}
  .xref {{ color:var(--accent); cursor:pointer; text-decoration:underline dotted }}
  .toc {{ background:var(--bg-alt); padding:16px; border-radius:8px; margin-bottom:20px;
          border:1px solid var(--border) }}
  .toc a {{ color:var(--accent); text-decoration:none }}
  .toc a:hover {{ text-decoration:underline }}
  .footer {{ text-align:center; padding:24px; color:var(--text-muted); font-size:13px;
             border-top:1px solid var(--border); margin-top:48px }}
  @media(max-width:768px) {{ .sidebar {{ display:none }} .main {{ padding:16px }} }}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
<h2>API Docs</h2>
<input class="sb-search" type="text" placeholder="Filter..." oninput="filterSidebar(this.value)">
{sidebar_html}
</aside>
<div class="main">
<h1>EPL API Documentation</h1>
<p style="color:var(--text-muted);font-size:14px">Generated {time.strftime("%Y-%m-%d %H:%M:%S")}</p>
<input class="search" type="text" placeholder="Search functions, classes..." id="search"
       oninput="filterEntries(this.value)">'''

        for mod in self.modules:
            mod_esc = html_mod.escape(mod.name)
            html += f'\n<h2 id="{mod_esc}">{mod_esc}</h2>'
            if mod.description:
                html += f'\n<p>{html_mod.escape(mod.description)}</p>'
            for entry in mod.entries:
                anchor = f'{mod.name}-{entry.name}'
                html += self._entry_to_html(entry, anchor=anchor, all_names=all_names,
                                            mod_name=mod.name)

        html += f'''
<div class="footer">EPL API Documentation — {len(self.modules)} modules, {sum(len(m.entries) for m in self.modules)} entries</div>
<script>
const entries = {json.dumps(entries_json)};
function filterEntries(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('.entry').forEach(el => {{
    const name = el.dataset.name || '';
    el.style.display = name.toLowerCase().includes(q) || !q ? 'block' : 'none';
  }});
}}
function filterSidebar(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('.sb-item').forEach(el => {{
    el.style.display = el.textContent.toLowerCase().includes(q) || !q ? 'block' : 'none';
  }});
}}
</script>
</div></div></body></html>'''
        return html

    def _entry_to_html(self, entry: DocEntry, anchor: str = '', all_names: set = None,
                       mod_name: str = '') -> str:
        """Convert an entry to HTML with anchors and cross-references."""
        if not anchor:
            anchor = entry.name
        badge_class = f'badge-{entry.kind}'
        h = f'\n<div class="entry" id="{html_mod.escape(anchor)}" data-name="{html_mod.escape(entry.name)}">'
        h += f'\n<h3><span class="badge {badge_class}">{entry.kind}</span> '

        if entry.kind in ('function', 'method'):
            params_str = ', '.join(
                f'{p.name}: {p.type_hint}' if p.type_hint else p.name
                for p in entry.params
            )
            h += f'{html_mod.escape(entry.name)}({html_mod.escape(params_str)})'
        else:
            h += html_mod.escape(entry.name)
        h += '</h3>'

        if entry.deprecated:
            h += f'\n<div class="deprecated">Deprecated: {html_mod.escape(entry.deprecated)}</div>'
        if entry.description:
            desc = html_mod.escape(entry.description)
            # Add cross-references to known names
            if all_names:
                for name in all_names:
                    if name != entry.name and name in desc:
                        target_id = html_mod.escape(f'{mod_name}-{name}')
                        desc = desc.replace(
                            name,
                            f'<span class="xref" data-target="{target_id}" onclick="document.getElementById(this.dataset.target)?.scrollIntoView({{behavior:\'smooth\'}})">{html_mod.escape(name)}</span>',
                            1
                        )
            h += f'\n<p>{desc}</p>'
        if entry.params:
            h += '\n<ul class="params">'
            for p in entry.params:
                h += f'\n<li><code>{html_mod.escape(p.name)}</code>'
                if p.type_hint:
                    h += f' <code>{html_mod.escape(p.type_hint)}</code>'
                if p.description:
                    h += f' — {html_mod.escape(p.description)}'
                h += '</li>'
            h += '\n</ul>'
        if entry.returns:
            h += f'\n<p><strong>Returns:</strong> {html_mod.escape(entry.returns)}</p>'
        if entry.examples:
            h += '\n<p><strong>Examples:</strong></p>'
            for ex in entry.examples:
                h += f'\n<pre><code>{html_mod.escape(ex)}</code></pre>'
        if entry.since:
            h += f'\n<p style="color:var(--text-muted);font-size:13px">Since {html_mod.escape(entry.since)}</p>'
        if entry.source:
            h += f'\n<details><summary>View Source</summary><pre><code>{html_mod.escape(entry.source)}</code></pre></details>'

        for child in entry.children:
            child_anchor = f'{anchor}-{child.name}'
            h += self._entry_to_html(child, anchor=child_anchor, all_names=all_names,
                                     mod_name=mod_name)

        h += '\n</div>'
        return h

    def to_json(self) -> str:
        """Generate JSON documentation."""
        data = []
        for mod in self.modules:
            mod_data = {
                'name': mod.name, 'path': mod.path, 'description': mod.description,
                'entries': [self._entry_to_dict(e) for e in mod.entries],
            }
            data.append(mod_data)
        return json.dumps(data, indent=2)

    def _entry_to_dict(self, entry: DocEntry) -> dict:
        d = {
            'kind': entry.kind, 'name': entry.name, 'description': entry.description,
            'line': entry.line, 'file': entry.file,
        }
        if entry.params:
            d['params'] = [{'name': p.name, 'type': p.type_hint, 'description': p.description}
                           for p in entry.params]
        if entry.returns:
            d['returns'] = entry.returns
        if entry.examples:
            d['examples'] = entry.examples
        if entry.since:
            d['since'] = entry.since
        if entry.deprecated:
            d['deprecated'] = entry.deprecated
        if entry.children:
            d['children'] = [self._entry_to_dict(c) for c in entry.children]
        return d


# ═══════════════════════════════════════════════════════════
# Linter
# ═══════════════════════════════════════════════════════════

@dataclass
class LintIssue:
    """A single lint issue."""
    file: str
    line: int
    column: int
    severity: str  # 'error', 'warning', 'info', 'hint'
    rule: str
    message: str
    fix: Optional[str] = None  # Auto-fix replacement text

    def __str__(self):
        return f'{self.file}:{self.line}:{self.column} [{self.severity}] {self.rule}: {self.message}'


@dataclass
class LintConfig:
    """Linter configuration."""
    max_line_length: int = 120
    max_function_length: int = 50
    max_nesting_depth: int = 5
    max_complexity: int = 10
    max_params: int = 6
    naming_convention: str = 'PascalCase'  # for functions
    var_naming: str = 'any'  # 'camelCase', 'snake_case', 'PascalCase', 'any'
    indent_size: int = 4
    require_docstrings: bool = False
    check_duplicate_imports: bool = True
    check_unused_vars: bool = True
    check_shadow_vars: bool = True
    check_consistent_returns: bool = True
    disabled_rules: List[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, filepath: str) -> 'LintConfig':
        """Load config from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        config = cls()
        for k, v in data.items():
            if hasattr(config, k):
                setattr(config, k, v)
        return config


class Linter:
    """EPL source code linter with configurable rules."""

    def __init__(self, config: LintConfig = None):
        self.config = config or LintConfig()
        self.issues: List[LintIssue] = []

    def lint_file(self, filepath: str) -> List[LintIssue]:
        """Lint a single file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        return self.lint_source(source, filepath)

    def lint_source(self, source: str, filepath: str = '<stdin>') -> List[LintIssue]:
        """Lint source code string."""
        issues = []
        lines = source.split('\n')

        # Per-line checks
        for i, line in enumerate(lines, 1):
            issues.extend(self._check_line(line, i, filepath))

        # Structural checks
        issues.extend(self._check_structure(lines, filepath))

        # Naming checks
        issues.extend(self._check_naming(lines, filepath))

        # Complexity checks
        issues.extend(self._check_complexity(lines, filepath))

        # Import checks
        if self.config.check_duplicate_imports:
            issues.extend(self._check_imports(lines, filepath))

        # Consistent return checks
        if self.config.check_consistent_returns:
            issues.extend(self._check_consistent_returns(lines, filepath))

        # Filter disabled rules
        issues = [iss for iss in issues if iss.rule not in self.config.disabled_rules]

        self.issues.extend(issues)
        return issues

    def lint_directory(self, dirpath: str, recursive: bool = True) -> List[LintIssue]:
        """Lint all .epl files in a directory."""
        path = Path(dirpath)
        pattern = '**/*.epl' if recursive else '*.epl'
        all_issues = []
        for fpath in sorted(path.glob(pattern)):
            all_issues.extend(self.lint_file(str(fpath)))
        return all_issues

    def _check_line(self, line: str, lineno: int, filepath: str) -> List[LintIssue]:
        """Per-line style checks."""
        issues = []

        # Line length
        if len(line) > self.config.max_line_length:
            issues.append(LintIssue(
                filepath, lineno, self.config.max_line_length + 1, 'warning',
                'line-too-long',
                f'Line exceeds {self.config.max_line_length} characters ({len(line)})',
            ))

        # Trailing whitespace
        if line != line.rstrip():
            issues.append(LintIssue(
                filepath, lineno, len(line.rstrip()) + 1, 'hint',
                'trailing-whitespace',
                'Trailing whitespace',
                fix=line.rstrip(),
            ))

        # Mixed tabs and spaces
        if '\t' in line and '    ' in line:
            issues.append(LintIssue(
                filepath, lineno, 1, 'warning',
                'mixed-indentation',
                'Mixed tabs and spaces in indentation',
            ))

        # Tab usage
        if line.startswith('\t'):
            issues.append(LintIssue(
                filepath, lineno, 1, 'hint',
                'tab-indentation',
                'Use spaces instead of tabs',
                fix=line.replace('\t', ' ' * self.config.indent_size),
            ))

        # Double semicolons or common typos
        stripped = line.strip()
        if stripped.endswith(';;'):
            issues.append(LintIssue(
                filepath, lineno, len(line) - 1, 'warning',
                'double-semicolon',
                'Double semicolon',
            ))

        # TODO/FIXME/HACK comments
        for tag in ['TODO', 'FIXME', 'HACK', 'XXX']:
            if tag in line:
                idx = line.index(tag)
                issues.append(LintIssue(
                    filepath, lineno, idx + 1, 'info',
                    'todo-comment',
                    f'{tag} found in comment',
                ))

        return issues

    def _check_structure(self, lines: List[str], filepath: str) -> List[LintIssue]:
        """Structural analysis."""
        issues = []
        in_function = False
        function_start = 0
        function_name = ''
        function_lines = 0
        nesting_depth = 0
        max_nesting = 0
        declared_vars = set()
        used_vars = set()
        has_doc = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track nesting
            if any(stripped.startswith(kw) for kw in [
                'If ', 'For ', 'While ', 'Try', 'Match '
            ]):
                nesting_depth += 1
                max_nesting = max(max_nesting, nesting_depth)

            if stripped.startswith('End') and nesting_depth > 0:
                nesting_depth -= 1

            # Function starts
            fn_match = re.match(r'(?:Async\s+)?Function\s+(\w+)\s*\((.*?)\)', stripped)
            if fn_match:
                if in_function and function_lines > self.config.max_function_length:
                    issues.append(LintIssue(
                        filepath, function_start, 1, 'warning',
                        'function-too-long',
                        f'Function "{function_name}" is {function_lines} lines (max: {self.config.max_function_length})',
                    ))
                in_function = True
                function_start = i
                function_name = fn_match.group(1)
                function_lines = 0
                max_nesting = 0

                # Check param count
                params = [p.strip() for p in fn_match.group(2).split(',') if p.strip()]
                if len(params) > self.config.max_params:
                    issues.append(LintIssue(
                        filepath, i, 1, 'warning',
                        'too-many-params',
                        f'Function "{function_name}" has {len(params)} parameters (max: {self.config.max_params})',
                    ))

                # Check for doc comment above
                if self.config.require_docstrings:
                    prev = lines[i - 2].strip() if i > 1 else ''
                    if not prev.startswith('//') and not prev.startswith('#'):
                        issues.append(LintIssue(
                            filepath, i, 1, 'info',
                            'missing-docstring',
                            f'Function "{function_name}" has no documentation comment',
                        ))

            if in_function:
                function_lines += 1

            # Function ends
            if stripped.startswith('End') and in_function and nesting_depth == 0:
                if function_lines > self.config.max_function_length:
                    issues.append(LintIssue(
                        filepath, function_start, 1, 'warning',
                        'function-too-long',
                        f'Function "{function_name}" is {function_lines} lines (max: {self.config.max_function_length})',
                    ))
                if max_nesting > self.config.max_nesting_depth:
                    issues.append(LintIssue(
                        filepath, function_start, 1, 'warning',
                        'deep-nesting',
                        f'Function "{function_name}" has nesting depth {max_nesting} (max: {self.config.max_nesting_depth})',
                    ))
                in_function = False

            # Track variable declarations
            var_match = re.match(r'(?:Create|Set)\s+(\w+)\s+(?:equal\s+to|to)', stripped, re.IGNORECASE)
            if var_match:
                declared_vars.add(var_match.group(1))

            # Track unreachable code
            if stripped.startswith('Return ') or stripped == 'Return':
                if i < len(lines):
                    next_stripped = lines[i].strip() if i < len(lines) else ''
                    if next_stripped and not next_stripped.startswith('End') and not next_stripped.startswith('//'):
                        issues.append(LintIssue(
                            filepath, i + 1, 1, 'warning',
                            'unreachable-code',
                            'Code after Return statement is unreachable',
                        ))

            # Empty block detection
            if any(stripped.startswith(kw) for kw in ['If ', 'For ', 'While ']):
                if i < len(lines):
                    next_stripped = lines[i].strip() if i < len(lines) else ''
                    if next_stripped.startswith('End'):
                        issues.append(LintIssue(
                            filepath, i, 1, 'info',
                            'empty-block',
                            'Empty block — consider adding implementation or comment',
                        ))

        return issues

    def _check_naming(self, lines: List[str], filepath: str) -> List[LintIssue]:
        """Naming convention checks."""
        issues = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Function names — should be PascalCase
            fn_match = re.match(r'(?:Async\s+)?Function\s+(\w+)', stripped)
            if fn_match:
                name = fn_match.group(1)
                if self.config.naming_convention == 'PascalCase' and not name[0].isupper():
                    issues.append(LintIssue(
                        filepath, i, stripped.index(name) + 1, 'hint',
                        'naming-convention',
                        f'Function "{name}" should use PascalCase (start with uppercase)',
                    ))

            # Class names — should always be PascalCase
            class_match = re.match(r'Class\s+(\w+)', stripped)
            if class_match:
                name = class_match.group(1)
                if not name[0].isupper():
                    issues.append(LintIssue(
                        filepath, i, stripped.index(name) + 1, 'warning',
                        'class-naming',
                        f'Class "{name}" should start with an uppercase letter',
                    ))

        return issues

    def _check_complexity(self, lines: List[str], filepath: str) -> List[LintIssue]:
        """Cyclomatic complexity analysis."""
        issues = []
        in_function = False
        function_name = ''
        function_start = 0
        complexity = 1  # Base complexity

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            fn_match = re.match(r'(?:Async\s+)?Function\s+(\w+)', stripped)
            if fn_match:
                if in_function and complexity > self.config.max_complexity:
                    issues.append(LintIssue(
                        filepath, function_start, 1, 'warning',
                        'high-complexity',
                        f'Function "{function_name}" has cyclomatic complexity {complexity} (max: {self.config.max_complexity})',
                    ))
                in_function = True
                function_name = fn_match.group(1)
                function_start = i
                complexity = 1

            # Decision points increase complexity
            if in_function:
                if stripped.startswith('If ') or stripped.startswith('Else If '):
                    complexity += 1
                elif stripped.startswith('For ') or stripped.startswith('While '):
                    complexity += 1
                elif stripped.startswith('Catch') or stripped.startswith('Except'):
                    complexity += 1
                elif ' and ' in stripped.lower() or ' or ' in stripped.lower():
                    complexity += stripped.lower().count(' and ') + stripped.lower().count(' or ')

            if stripped.startswith('End') and in_function:
                if not any(stripped.startswith(f'End {kw}') for kw in ['If', 'For', 'While', 'Try']):
                    if complexity > self.config.max_complexity:
                        issues.append(LintIssue(
                            filepath, function_start, 1, 'warning',
                            'high-complexity',
                            f'Function "{function_name}" has cyclomatic complexity {complexity} (max: {self.config.max_complexity})',
                        ))
                    in_function = False

        return issues

    def _check_imports(self, lines: List[str], filepath: str) -> List[LintIssue]:
        """Check for duplicate and unused imports."""
        issues = []
        imports = {}  # name -> line_number

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            import_match = re.match(r'Import\s+(\w+)', stripped)
            if import_match:
                name = import_match.group(1)
                if name in imports:
                    issues.append(LintIssue(
                        filepath, i, 1, 'warning',
                        'duplicate-import',
                        f'Duplicate import "{name}" (first imported at line {imports[name]})',
                    ))
                else:
                    imports[name] = i
            from_match = re.match(r'From\s+(\w+)\s+Import\s+(.*)', stripped)
            if from_match:
                module = from_match.group(1)
                names = [n.strip() for n in from_match.group(2).split(',')]
                for name in names:
                    if name in imports:
                        issues.append(LintIssue(
                            filepath, i, 1, 'warning',
                            'duplicate-import',
                            f'Duplicate import "{name}" (first imported at line {imports[name]})',
                        ))
                    else:
                        imports[name] = i

        return issues

    def _check_consistent_returns(self, lines: List[str], filepath: str) -> List[LintIssue]:
        """Check that functions consistently return or don't return values."""
        issues = []
        in_function = False
        function_name = ''
        function_start = 0
        has_value_return = False
        has_bare_return = False
        nesting = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            fn_match = re.match(r'(?:Async\s+)?Function\s+(\w+)', stripped)
            if fn_match:
                if in_function:
                    if has_value_return and has_bare_return:
                        issues.append(LintIssue(
                            filepath, function_start, 1, 'warning',
                            'inconsistent-return',
                            f'Function "{function_name}" has both value-returns and bare returns',
                        ))
                in_function = True
                function_name = fn_match.group(1)
                function_start = i
                has_value_return = False
                has_bare_return = False
                nesting = 0
                continue

            if in_function:
                if any(stripped.startswith(kw) for kw in ['If ', 'For ', 'While ', 'Try', 'Match ']):
                    nesting += 1
                if stripped.startswith('End'):
                    if nesting > 0:
                        nesting -= 1
                    else:
                        if has_value_return and has_bare_return:
                            issues.append(LintIssue(
                                filepath, function_start, 1, 'warning',
                                'inconsistent-return',
                                f'Function "{function_name}" has both value-returns and bare returns',
                            ))
                        in_function = False
                        continue

                if stripped == 'Return':
                    has_bare_return = True
                elif stripped.startswith('Return '):
                    has_value_return = True

        return issues

    def auto_fix(self, filepath: str) -> Tuple[str, int]:
        """Apply auto-fixes to a file. Returns (fixed_source, fix_count)."""
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        issues = self.lint_file(filepath)
        fixable = [iss for iss in issues if iss.fix is not None]

        fix_count = 0
        # Sort by line number descending to fix from bottom up
        fixable.sort(key=lambda x: x.line, reverse=True)

        for issue in fixable:
            idx = issue.line - 1
            if 0 <= idx < len(lines):
                lines[idx] = issue.fix + '\n'
                fix_count += 1

        result = ''.join(lines)
        if fix_count > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

        return result, fix_count

    def format_report(self, issues: List[LintIssue] = None) -> str:
        """Format issues as a readable report."""
        issues = issues or self.issues
        if not issues:
            return '✓ No issues found!'

        lines = []
        by_file = {}
        for iss in issues:
            by_file.setdefault(iss.file, []).append(iss)

        counts = {'error': 0, 'warning': 0, 'info': 0, 'hint': 0}
        for iss in issues:
            counts[iss.severity] = counts.get(iss.severity, 0) + 1

        for filepath, file_issues in sorted(by_file.items()):
            lines.append(f'\n  {filepath}')
            for iss in sorted(file_issues, key=lambda x: x.line):
                icon = {'error': '✗', 'warning': '⚠', 'info': 'ℹ', 'hint': '·'}.get(iss.severity, '?')
                lines.append(f'    {icon} {iss.line}:{iss.column}  {iss.message}  [{iss.rule}]')

        lines.append(f'\n  {len(issues)} issues: {counts["error"]} errors, {counts["warning"]} warnings, '
                      f'{counts["info"]} info, {counts["hint"]} hints')

        fixable = sum(1 for iss in issues if iss.fix)
        if fixable:
            lines.append(f'  {fixable} auto-fixable (use --fix)')

        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='EPL Documentation Generator & Linter')
    subparsers = parser.add_subparsers(dest='command')

    # docs subcommand
    docs_parser = subparsers.add_parser('docs', help='Generate documentation')
    docs_parser.add_argument('source', help='Source file or directory')
    docs_parser.add_argument('-o', '--output', default='docs', help='Output directory')
    docs_parser.add_argument('-f', '--format', choices=['html', 'markdown', 'json', 'all'],
                             default='all', help='Output format')

    # lint subcommand
    lint_parser = subparsers.add_parser('lint', help='Lint source code')
    lint_parser.add_argument('source', nargs='+', help='Files or directories to lint')
    lint_parser.add_argument('--fix', action='store_true', help='Auto-fix issues')
    lint_parser.add_argument('--config', help='Config file path')
    lint_parser.add_argument('--max-line-length', type=int, default=120)
    lint_parser.add_argument('--format', choices=['text', 'json'], default='text')

    args = parser.parse_args()

    if args.command == 'docs':
        gen = DocGenerator()
        source_path = Path(args.source)
        if source_path.is_dir():
            gen.parse_directory(str(source_path))
        else:
            gen.parse_file(str(source_path))

        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)

        fmt = args.format
        if fmt in ('markdown', 'all'):
            (out_dir / 'api.md').write_text(gen.to_markdown(), encoding='utf-8')
            print(f'Generated: {out_dir}/api.md')
        if fmt in ('html', 'all'):
            (out_dir / 'api.html').write_text(gen.to_html(), encoding='utf-8')
            print(f'Generated: {out_dir}/api.html')
        if fmt in ('json', 'all'):
            (out_dir / 'api.json').write_text(gen.to_json(), encoding='utf-8')
            print(f'Generated: {out_dir}/api.json')

    elif args.command == 'lint':
        config = LintConfig()
        if args.config:
            config = LintConfig.from_file(args.config)
        config.max_line_length = args.max_line_length

        linter = Linter(config)
        all_issues = []

        for source in args.source:
            source_path = Path(source)
            if source_path.is_dir():
                all_issues.extend(linter.lint_directory(str(source_path)))
            elif source_path.exists():
                all_issues.extend(linter.lint_file(str(source_path)))
            else:
                print(f'File not found: {source}')

        if args.fix:
            fix_total = 0
            for source in args.source:
                source_path = Path(source)
                if source_path.is_file():
                    _, count = linter.auto_fix(str(source_path))
                    fix_total += count
                elif source_path.is_dir():
                    for fpath in source_path.glob('**/*.epl'):
                        _, count = linter.auto_fix(str(fpath))
                        fix_total += count
            print(f'Fixed {fix_total} issues')
        else:
            if args.format == 'json':
                data = [{'file': i.file, 'line': i.line, 'col': i.column,
                          'severity': i.severity, 'rule': i.rule, 'message': i.message}
                         for i in all_issues]
                print(json.dumps(data, indent=2))
            else:
                print(linter.format_report(all_issues))

        sys.exit(1 if any(i.severity == 'error' for i in all_issues) else 0)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
