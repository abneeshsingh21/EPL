"""
EPL HTML Generator (v0.5)
Converts PageDef and HtmlElement AST nodes into styled HTML.
"""

import re

from epl import ast_nodes as ast

# Modern Premium CSS - Professional Component Design
STYLES = """
/* Bright Documentation Theme - Inspired by Modern Documentation Sites */
:root {
    /* Bright Color System */
    --bg-primary: #ffffff;
    --bg-secondary: #fafbfc;
    --bg-tertiary: #f6f8fa;
    --surface: #ffffff;
    --surface-elevated: #ffffff;
    --surface-glass: rgba(255, 255, 255, 0.9);
    
    /* Border System */
    --border-primary: #e1e8ed;
    --border-secondary: #d1dce5;
    --border-accent: #bfc8d1;
    
    /* Text Hierarchy */
    --text-primary: #1a202c;
    --text-secondary: #2d3748;
    --text-muted: #4a5568;
    --text-disabled: #a0aec0;
    
    /* Vibrant Accent System */
    --accent-primary: #e91e63;
    --accent-secondary: #f06292;
    --accent-tertiary: #f48fb1;
    --accent-glow: rgba(233, 30, 99, 0.2);
    
    /* Status Colors */
    --success: #4caf50;
    --warning: #ff9800;
    --error: #f44336;
    --info: #2196f3;
    
    /* Spacing System */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    --space-2xl: 48px;
    --space-3xl: 64px;
    --space-4xl: 96px;
    
    /* Radius System */
    --radius-xs: 4px;
    --radius-sm: 6px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;
    --radius-2xl: 24px;
    
    /* Shadow System */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
    --shadow-xl: 0 16px 48px rgba(0, 0, 0, 0.6);
    --shadow-glow: 0 0 32px var(--accent-glow);
    
    /* Animation System */
    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-slow: 350ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-bounce: 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

/* Bright Geometric Background with Colorful Accents */
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
    font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    overflow-x: hidden;
    position: relative;
}

/* Geometric Side Decorations */
body::before {
    content: '';
    position: fixed;
    top: 0;
    left: -200px;
    width: 400px;
    height: 100vh;
    background: linear-gradient(135deg, #e91e63 0%, #f06292 50%, #2196f3 100%);
    transform: skewX(-15deg);
    z-index: -2;
}

body::after {
    content: '';
    position: fixed;
    top: 0;
    right: -200px;
    width: 400px;
    height: 100vh;
    background: linear-gradient(135deg, #2196f3 0%, #64b5f6 50%, #e91e63 100%);
    transform: skewX(15deg);
    z-index: -2;
}

/* Modern Container System */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-2xl) var(--space-lg);
    position: relative;
    z-index: 1;
}

/* Hero Section Styling */
h1 {
    font-size: clamp(2.5rem, 8vw, 4rem);
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: -0.02em;
    color: var(--text-primary);
    margin-bottom: var(--space-lg);
    text-align: center;
    position: relative;
}

/* Search Section Styling */
.search-section {
    background: white;
    border-radius: 16px;
    padding: var(--space-2xl);
    box-shadow: 
        0 4px 32px rgba(233, 30, 99, 0.08),
        0 2px 16px rgba(0, 0, 0, 0.04);
    margin: var(--space-2xl) 0;
    border: 1px solid var(--border-primary);
}

.search-container {
    display: flex;
    gap: var(--space-md);
    align-items: center;
    margin: var(--space-lg) 0;
}

.search-input {
    flex: 1;
    padding: var(--space-md) var(--space-lg);
    border: 2px solid var(--border-primary);
    border-radius: 12px;
    font-size: var(--text-base);
    background: var(--bg-secondary);
    color: var(--text-primary);
    transition: all var(--transition-normal);
}

.search-input:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 4px rgba(233, 30, 99, 0.1);
}

.search-button {
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    color: white;
    border: none;
    padding: var(--space-md) var(--space-xl);
    border-radius: 12px;
    font-weight: 600;
    font-size: var(--text-base);
    cursor: pointer;
    transition: all var(--transition-normal);
    box-shadow: 0 4px 16px rgba(233, 30, 99, 0.3);
}

.search-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(233, 30, 99, 0.4);
}
/* Topic Cards Grid */
.topics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--space-xl);
    margin: var(--space-2xl) 0;
}

.topic-card {
    background: white;
    border-radius: 20px;
    padding: var(--space-xl);
    box-shadow: 
        0 8px 32px rgba(233, 30, 99, 0.08),
        0 4px 16px rgba(0, 0, 0, 0.04);
    border: 1px solid var(--border-primary);
    transition: all var(--transition-normal);
    cursor: pointer;
    position: relative;
    overflow: hidden;
}

.topic-card:hover {
    transform: translateY(-8px);
    box-shadow: 
        0 16px 48px rgba(233, 30, 99, 0.12),
        0 8px 32px rgba(0, 0, 0, 0.08);
    border-color: var(--accent-primary);
}

.topic-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: var(--space-lg);
    box-shadow: 0 8px 24px rgba(233, 30, 99, 0.3);
}

.topic-title {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: var(--space-sm);
}

.topic-description {
    color: var(--text-muted);
    line-height: 1.6;
    font-size: var(--text-sm);
}

/* Section Headers */
h2 {
    font-size: clamp(1.75rem, 4vw, 2.5rem);
    font-weight: 700;
    color: var(--text-primary);
    margin: var(--space-3xl) 0 var(--space-xl);
    text-align: center;
    position: relative;
}

h2::after {
    content: '';
    position: absolute;
    bottom: -8px;
    left: 50%;
    transform: translateX(-50%);
    width: 80px;
    height: 3px;
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    border-radius: 2px;
}

/* Clean Paragraph Styling */
p {
    font-size: var(--text-base);
    color: var(--text-secondary);
    line-height: 1.7;
    margin-bottom: var(--space-lg);
    max-width: 65ch;
}

/* Modern Button System */
a, button, .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    padding: var(--space-md) var(--space-xl);
    font-size: var(--text-sm);
    font-weight: 600;
    text-decoration: none;
    border-radius: 12px;
    border: 2px solid var(--accent-primary);
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    color: white;
    cursor: pointer;
    transition: all var(--transition-normal);
    position: relative;
    overflow: hidden;
    margin: var(--space-xs) var(--space-md) var(--space-xs) 0;
    box-shadow: 0 4px 16px rgba(233, 30, 99, 0.3);
}

/* Primary Button Variant */
.btn-primary, button {
    background: linear-gradient(135deg, 
        var(--accent-primary) 0%, 
        var(--accent-secondary) 100%
    );
    border: 1px solid var(--accent-primary);
    color: white;
    box-shadow: var(--shadow-glow);
}

/* Button Hover Effects */
a:hover, button:hover, .btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(233, 30, 99, 0.4);
    filter: brightness(1.1);
}

/* Navigation Styling */
nav {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border-primary);
    padding: var(--space-lg) 0;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.04);
}

.nav-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 var(--space-lg);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.nav-links {
    display: flex;
    gap: var(--space-lg);
    align-items: center;
}

.nav-links a {
    color: var(--text-primary);
    text-decoration: none;
    font-weight: 500;
    padding: var(--space-sm) var(--space-md);
    border-radius: 8px;
    transition: all var(--transition-normal);
    background: transparent;
    border: none;
    box-shadow: none;
    margin: 0;
}

.nav-links a:hover {
    background: var(--bg-secondary);
    color: var(--accent-primary);
    transform: none;
    box-shadow: none;
}

/* Form Elements */
input, textarea {
    width: 100%;
    padding: var(--space-md) var(--space-lg);
    font-size: 1rem;
    background: white;
    border: 2px solid var(--border-primary);
    border-radius: 12px;
    color: var(--text-primary);
    transition: all var(--transition-normal);
    margin: var(--space-sm) 0;
}

input:focus, textarea:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 4px rgba(233, 30, 99, 0.1);
}

input::placeholder, textarea::placeholder {
    color: var(--text-muted);
}

form {
    background: white;
    border: 2px solid var(--border-primary);
    border-radius: 20px;
    padding: var(--space-2xl);
    margin: var(--space-xl) 0;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
/* Clean List Styling */
ul, ol {
    margin: var(--space-lg) 0;
    padding-left: 0;
    list-style: none;
}

li {
    margin: var(--space-md) 0;
    padding: var(--space-md) var(--space-lg);
    background: white;
    border: 1px solid var(--border-primary);
    border-left: 4px solid var(--accent-primary);
    border-radius: 12px;
    color: var(--text-secondary);
    transition: all var(--transition-normal);
    position: relative;
}

li:hover {
    background: var(--bg-secondary);
    border-left-color: var(--accent-secondary);
    transform: translateX(4px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

/* Modern Card System */
.card {
    background: white;
    border: 2px solid var(--border-primary);
    border-radius: 20px;
    padding: var(--space-2xl);
    margin: var(--space-xl) 0;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
    transition: all var(--transition-slow);
    position: relative;
}

.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 48px rgba(233, 30, 99, 0.08);
    border-color: var(--accent-primary);
}

/* Footer */
footer {
    margin-top: var(--space-3xl);
    padding: var(--space-2xl);
    text-align: center;
    color: var(--text-muted);
    border-top: 2px solid var(--border-primary);
    background: var(--bg-secondary);
    font-size: var(--text-sm);
}

/* Responsive Design */
@media (max-width: 768px) {
    .container { 
        padding: var(--space-xl) var(--space-md); 
    }
    
    h1 { 
        font-size: clamp(2rem, 6vw, 3rem);
        margin-bottom: var(--space-lg);
    }
    
    h2 { 
        font-size: clamp(1.5rem, 5vw, 2rem);
        margin: var(--space-2xl) 0 var(--space-lg);
    }
    
    .topics-grid {
        grid-template-columns: 1fr;
        gap: var(--space-lg);
    }
    
    .search-container {
        flex-direction: column;
        align-items: stretch;
    }
    
    .nav-links {
        flex-direction: column;
        gap: var(--space-md);
    }
    
    body::before, body::after {
        width: 200px;
    }
}

/* Smooth Scrolling */
html {
    scroll-behavior: smooth;
    scroll-padding-top: 80px;
}

/* Selection Styling */
::selection {
    background: rgba(233, 30, 99, 0.2);
    color: var(--text-primary);
}

/* Custom Scrollbar */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-secondary);
}

::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, var(--accent-primary), var(--accent-secondary));
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, var(--accent-secondary), var(--accent-primary));
}

/* Focus Visible */
*:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}
"""


def generate_html(page_def, data_store=None, form_data=None):
    """Convert a PageDef AST node into a full HTML page string."""
    title = page_def.title if isinstance(page_def, ast.PageDef) else 'EPL Page'
    elements = page_def.elements if isinstance(page_def, ast.PageDef) else []
    store = data_store if data_store is not None else {}

    body_html = '\n'.join(_render_element(e, store, form_data) for e in elements if e)
    scripts = '\n'.join(_extract_scripts(e) for e in elements if e)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>{STYLES}</style>
</head>
<body>
    <div class="container">
        {body_html}
    </div>
    <footer>Powered by EPL v1.0</footer>
    {f'<script>{scripts}</script>' if scripts else ''}
</body>
</html>"""


def _esc(text):
    """HTML-escape text."""
    if not isinstance(text, str):
        return str(text)
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;')
    )


def _safe_href(url):
    """Sanitize href to prevent javascript: URI injection."""
    if not isinstance(url, str):
        return '#'
    url_stripped = url.strip().lower()
    if url_stripped.startswith(('javascript:', 'vbscript:', 'data:text/html')):
        return '#'
    return _esc(url)


def _render_element(elem, data_store=None, form_data=None):
    """Render a single HtmlElement to HTML."""
    if not isinstance(elem, ast.HtmlElement):
        return ''

    store = data_store if data_store is not None else {}
    tag = elem.tag
    content = elem.content or ''
    attrs = elem.attributes or {}

    # Unwrap AST Literal nodes to their value
    if isinstance(content, ast.Literal):
        content = content.value if content.value is not None else ''

    # Resolve $count{collection} and $items{collection} templates in text content
    if isinstance(content, str):
        content = _resolve_store_templates(content, store)

    if tag == 'heading':
        return f'<h1>{_esc(content)}</h1>'

    if tag == 'subheading':
        return f'<h2>{_esc(content)}</h2>'

    if tag == 'text':
        return f'<p>{_esc(content)}</p>'

    if tag == 'link':
        href = attrs.get('href', '#')
        return f'<a href="{_safe_href(href)}">{_esc(content)}</a>'

    if tag == 'image':
        src = attrs.get('src', '')
        return f'<img src="{_esc(src)}" alt="image">'

    if tag == 'button':
        onclick = attrs.get('onclick', '')
        # Sanitize onclick: only allow simple function calls (alphanumeric + parentheses)
        if onclick and not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)$', onclick):
            onclick = ''  # Strip unsafe onclick values
        onclick_attr = f' onclick="{_esc(onclick)}"' if onclick else ''
        return f'<button{onclick_attr}>{_esc(content)}</button>'

    if tag == 'input':
        name = attrs.get('name', '')
        ph = attrs.get('placeholder', '')
        return f'<input type="text" name="{_esc(name)}" id="{_esc(name)}" placeholder="{_esc(ph)}">'

    if tag == 'form':
        action = attrs.get('action', '')
        children_html = '\n'.join(
            _render_element(c, store, form_data) for c in (elem.children or [])
        )
        return f'<form action="{_esc(action)}" method="POST">\n{children_html}\n<button type="submit" class="btn">Submit</button>\n</form>'

    if tag == 'list':
        # content is a ListLiteral or evaluated list
        if isinstance(content, ast.ListLiteral):
            items = [
                f'<li>{_esc(e.value if hasattr(e, "value") else str(e))}</li>'
                for e in content.elements
            ]
        elif isinstance(content, list):
            items = [f'<li>{_esc(str(item))}</li>' for item in content]
        else:
            items = [f'<li>{_esc(str(content))}</li>']
        return f'<ul>\n{"  ".join(items)}\n</ul>'

    if tag == 'store_list':
        # Render items from the data store collection
        collection = attrs.get('collection', '')
        items = store.get(collection, [])
        if not items:
            return '<p style="color: var(--muted); font-style: italic;">No items yet.</p>'
        html_parts = []
        for i, item in enumerate(items):
            delete_action = attrs.get('delete_action', '')
            html_parts.append(
                f'<div class="card" style="display:flex; justify-content:space-between; align-items:center; padding:12px 20px;">'
                f'<span>{_esc(str(item))}</span>'
                f'<form action="{_esc(delete_action)}" method="POST" style="margin:0;padding:0;background:none;box-shadow:none;">'
                f'<input type="hidden" name="index" value="{i}">'
                f'<button type="submit" style="background:var(--danger);padding:6px 14px;font-size:0.85rem;">Delete</button>'
                f'</form></div>'
            )
        return '\n'.join(html_parts)

    if tag == 'script':
        return ''  # scripts go in the <script> section

    return f'<div>{_esc(str(content))}</div>'


def _resolve_store_templates(text, data_store):
    """Replace $count{collection} and $items{collection} in text."""
    import re

    def replace_count(m):
        coll = m.group(1)
        return str(len(data_store.get(coll, [])))

    def replace_items(m):
        coll = m.group(1)
        return str(data_store.get(coll, []))

    text = re.sub(r'\$count\{(\w+)\}', replace_count, text)
    text = re.sub(r'\$items\{(\w+)\}', replace_items, text)
    return text


def _extract_scripts(elem):
    """Extract JavaScript from script elements."""
    if not isinstance(elem, ast.HtmlElement):
        return ''
    if elem.tag == 'script' and elem.content:
        return str(elem.content)
    return ''
