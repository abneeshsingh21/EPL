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


def generate_html(
    page_def, data_store=None, form_data=None, styles=None, components=None, animations=None
):
    """Convert a PageDef AST node into a full HTML page string.

    styles: list of StyleDef nodes collected from the program
    components: dict of component_name -> ComponentDef
    animations: list of AnimateDef nodes
    """
    title = page_def.title if isinstance(page_def, ast.PageDef) else 'EPL Page'
    elements = page_def.elements if isinstance(page_def, ast.PageDef) else []
    store = data_store if data_store is not None else {}
    comps = components or {}

    batched_elements = _batch_draw_commands(elements)
    body_html = '\n'.join(
        _render_any_element(e, store, form_data, comps) for e in batched_elements if e
    )
    scripts = '\n'.join(_extract_scripts(e) for e in elements if e)

    custom_css = _generate_custom_css(styles or [])
    animation_css = _generate_animation_css(animations or [])
    extra_css = ''
    if custom_css or animation_css:
        extra_css = f'\n    <style>\n{custom_css}\n{animation_css}\n    </style>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>{STYLES}</style>{extra_css}
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


def _esc_js(text):
    """Escape a string for safe use inside JavaScript string literals."""
    if not isinstance(text, str):
        return str(text)
    return (
        text.replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('</', '<\\/')
    )


import re as _re

_CSS_SAFE_IDENT_RE = _re.compile(r'^[a-zA-Z_-][a-zA-Z0-9_-]*$')
_CSS_SAFE_VALUE_RE = _re.compile(r'^[a-zA-Z0-9_.#%,() /:;-]+$')


def _esc_css_ident(name):
    """Sanitize a CSS class/identifier name — strip unsafe characters."""
    if not isinstance(name, str):
        name = str(name)
    return _re.sub(r'[^a-zA-Z0-9_-]', '', name)


def _esc_css_value(value):
    """Sanitize a CSS property value — remove dangerous characters."""
    if not isinstance(value, str):
        value = str(value)
    return (
        value.replace('{', '').replace('}', '').replace(';', '').replace('<', '').replace('>', '')
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


# ─── v6.0: Style & Layout Rendering ─────────────────────────


def _generate_custom_css(styles):
    """Generate CSS from StyleDef AST nodes."""
    if not styles:
        return ''
    css_parts = []
    for style_def in styles:
        props = []
        for prop in style_def.properties:
            value = prop.value
            if isinstance(value, ast.Literal):
                value = value.value
            props.append(f'    {_esc_css_ident(prop.property_name)}: {_esc_css_value(value)};')
        css_parts.append(f'.{_esc_css_ident(style_def.name)} {{\n' + '\n'.join(props) + '\n}')
    return '\n\n'.join(css_parts)


def _generate_animation_css(animations):
    """Generate @keyframes CSS from AnimateDef AST nodes."""
    if not animations:
        return ''
    css_parts = []
    for anim in animations:
        safe_name = _esc_css_ident(anim.name)
        keyframe_css = []
        for kf in anim.keyframes:
            props = []
            for prop in kf.properties:
                value = prop.value
                if isinstance(value, ast.Literal):
                    value = value.value
                props.append(
                    f'        {_esc_css_ident(prop.property_name)}: {_esc_css_value(value)};'
                )
            keyframe_css.append(f'    {kf.percentage}% {{\n' + '\n'.join(props) + '\n    }')
        css_parts.append(f'@keyframes {safe_name} {{\n' + '\n'.join(keyframe_css) + '\n}')

        duration = _esc_css_value(anim.duration or '1s')
        easing = _esc_css_value(anim.easing or 'ease')
        iteration = _esc_css_value(anim.iteration or '1')
        css_parts.append(
            f'.animate-{safe_name} {{\n'
            f'    animation: {safe_name} {duration} {easing} {iteration};\n'
            f'}}'
        )
    return '\n\n'.join(css_parts)


def _batch_draw_commands(elements):
    """Group consecutive DrawCommand elements into batched lists for single-canvas rendering."""
    result = []
    draw_batch = []
    for elem in elements:
        if isinstance(elem, ast.DrawCommand):
            draw_batch.append(elem)
        else:
            if draw_batch:
                result.append(draw_batch)
                draw_batch = []
            result.append(elem)
    if draw_batch:
        result.append(draw_batch)
    return result


def _render_any_element(elem, data_store=None, form_data=None, components=None):
    """Render any element type including v6.0 styled elements."""
    comps = components or {}

    if isinstance(elem, ast.HtmlElement):
        return _render_element(elem, data_store, form_data)

    if isinstance(elem, ast.StyledElement):
        return _render_styled_element(elem, data_store, form_data, comps)

    if isinstance(elem, ast.LayoutContainer):
        return _render_layout_container(elem, data_store, form_data, comps)

    if isinstance(elem, ast.ComponentUse):
        return _render_component_use(elem, data_store, form_data, comps)

    if isinstance(elem, ast.ResponsiveBlock):
        return '\n'.join(
            _render_any_element(c, data_store, form_data, comps) for c in elem.body if c
        )

    if isinstance(elem, ast.Scene3D):
        return _render_scene_3d(elem)

    if isinstance(elem, ast.DrawCommand):
        return _render_draw_command(elem)

    if isinstance(elem, list) and elem and all(isinstance(e, ast.DrawCommand) for e in elem):
        return _render_draw_commands_batched(elem)

    return ''


def _render_styled_element(elem, data_store=None, form_data=None, components=None):
    """Render a StyledElement (div, section, nav, etc.) to HTML."""
    tag = elem.tag
    if tag == 'container':
        tag = 'div'

    classes = list(elem.styles) + list(elem.class_names)
    if elem.attributes.get('data-animate'):
        classes.append(f'animate-{elem.attributes["data-animate"]}')

    class_attr = f' class="{_esc(" ".join(classes))}"' if classes else ''
    id_attr = f' id="{_esc(elem.attributes["id"])}"' if 'id' in elem.attributes else ''

    style_attr = ''
    if elem.inline_styles:
        style_parts = [
            f'{_esc(p.property_name)}: {_esc(p.value if isinstance(p.value, str) else str(p.value))}'
            for p in elem.inline_styles
        ]
        style_attr = f' style="{"; ".join(style_parts)}"'

    comps = components or {}
    children_html = '\n'.join(
        _render_any_element(c, data_store, form_data, comps) for c in elem.children if c
    )

    return f'<{tag}{class_attr}{id_attr}{style_attr}>\n{children_html}\n</{tag}>'


def _render_layout_container(elem, data_store=None, form_data=None, components=None):
    """Render a Flex/Grid layout container."""
    style_parts = []

    if elem.layout_type == 'flex':
        style_parts.append('display: flex')
        props = elem.properties
        if 'direction' in props:
            style_parts.append(f'flex-direction: {props["direction"]}')
        if 'gap' in props:
            style_parts.append(f'gap: {props["gap"]}')
        if 'align' in props:
            style_parts.append(f'align-items: {props["align"]}')
        if 'justify' in props:
            style_parts.append(f'justify-content: {props["justify"]}')
        if 'wrap' in props:
            style_parts.append('flex-wrap: wrap')

    elif elem.layout_type == 'grid':
        style_parts.append('display: grid')
        props = elem.properties
        if 'columns' in props:
            val = props['columns']
            if isinstance(val, (int, float)):
                style_parts.append(f'grid-template-columns: repeat({int(val)}, 1fr)')
            else:
                try:
                    style_parts.append(f'grid-template-columns: repeat({int(val)}, 1fr)')
                except (ValueError, TypeError):
                    style_parts.append(f'grid-template-columns: {val}')
        if 'rows' in props:
            style_parts.append(f'grid-template-rows: {props["rows"]}')
        if 'gap' in props:
            style_parts.append(f'gap: {props["gap"]}')

    style_attr = f' style="{"; ".join(style_parts)}"' if style_parts else ''

    comps = components or {}
    children_html = '\n'.join(
        _render_any_element(c, data_store, form_data, comps) for c in elem.children if c
    )

    return f'<div{style_attr}>\n{children_html}\n</div>'


def _render_component_use(elem, data_store=None, form_data=None, components=None):
    """Render a component instantiation by expanding its template."""
    comps = components or {}
    comp_def = comps.get(elem.component_name)
    if not comp_def:
        return f'<!-- Unknown component: {_esc(elem.component_name)} -->'

    parts = []
    for child in comp_def.body:
        parts.append(_render_any_element(child, data_store, form_data, comps))
    return '\n'.join(parts)


def _render_scene_3d(scene):
    """Render a Scene3D node to HTML with Three.js initialization script."""
    name_js = _esc_js(scene.name)
    name_html = _esc(scene.name)
    w = scene.width
    h = scene.height

    meshes_js = []
    camera_js = 'camera.position.set(0, 5, 10);\ncamera.lookAt(0, 0, 0);'
    lights_js = []

    for node in scene.body:
        if isinstance(node, ast.CameraSetup):
            px, py, pz = node.position
            lx, ly, lz = node.look_at
            camera_js = (
                f'camera = new THREE.PerspectiveCamera({node.fov}, {w}/{h}, 0.1, 1000);\n'
                f'camera.position.set({px}, {py}, {pz});\n'
                f'camera.lookAt({lx}, {ly}, {lz});'
            )
        elif isinstance(node, ast.LightSetup):
            lt = node.light_type
            color = _esc_js(node.color)
            intensity = node.intensity
            if lt == 'ambient':
                lights_js.append(f'scene.add(new THREE.AmbientLight("{color}", {intensity}));')
            elif lt == 'directional':
                pos = node.position or [5, 10, 5]
                lights_js.append(
                    f'{{ const l = new THREE.DirectionalLight("{color}", {intensity});\n'
                    f'  l.position.set({pos[0]}, {pos[1]}, {pos[2]}); scene.add(l); }}'
                )
            elif lt == 'point':
                pos = node.position or [0, 5, 0]
                lights_js.append(
                    f'{{ const l = new THREE.PointLight("{color}", {intensity});\n'
                    f'  l.position.set({pos[0]}, {pos[1]}, {pos[2]}); scene.add(l); }}'
                )
        elif isinstance(node, ast.MeshAdd):
            shape = node.shape
            geo_map = {
                'cube': 'BoxGeometry(1,1,1)',
                'sphere': 'SphereGeometry(1,32,32)',
                'plane': 'PlaneGeometry(1,1)',
                'cylinder': 'CylinderGeometry(0.5,0.5,1,32)',
                'cone': 'ConeGeometry(0.5,1,32)',
                'torus': 'TorusGeometry(1,0.4,16,100)',
            }
            geo = geo_map.get(shape, 'BoxGeometry(1,1,1)')
            color = _esc_js(node.color or '#667eea')
            px, py, pz = node.position
            sx, sy, sz = node.scale
            rx, ry, rz = node.rotation
            meshes_js.append(
                f'{{ const g = new THREE.{geo};\n'
                f'  const m = new THREE.MeshStandardMaterial({{color: "{color}"}});\n'
                f'  const mesh = new THREE.Mesh(g, m);\n'
                f'  mesh.position.set({px}, {py}, {pz});\n'
                f'  mesh.scale.set({sx}, {sy}, {sz});\n'
                f'  mesh.rotation.set({rx}*Math.PI/180, {ry}*Math.PI/180, {rz}*Math.PI/180);\n'
                f'  scene.add(mesh); }}'
            )

    lights_code = (
        '\n'.join(lights_js) if lights_js else 'scene.add(new THREE.AmbientLight("#fff", 0.5));'
    )
    meshes_code = '\n'.join(meshes_js)

    return (
        f'<div id="scene-{name_html}" style="width:{w}px;height:{h}px;"></div>\n'
        f'<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n'
        f'<script>\n'
        f'(function() {{\n'
        f'  const container = document.getElementById("scene-{name_js}");\n'
        f'  const scene = new THREE.Scene();\n'
        f'  let camera;\n'
        f'  {camera_js}\n'
        f'  const renderer = new THREE.WebGLRenderer({{antialias: true}});\n'
        f'  renderer.setSize({w}, {h});\n'
        f'  container.appendChild(renderer.domElement);\n'
        f'  {lights_code}\n'
        f'  {meshes_code}\n'
        f'  function animate() {{ requestAnimationFrame(animate); renderer.render(scene, camera); }}\n'
        f'  animate();\n'
        f'}})();\n'
        f'</script>'
    )


def _render_draw_command(cmd):
    """Render a DrawCommand to HTML Canvas drawing code."""
    shape = cmd.shape
    props = cmd.properties

    canvas_id = f'canvas-{id(cmd)}'
    w = int(props.get('canvas_width', 800))
    h = int(props.get('canvas_height', 600))

    draw_code = ''
    if shape == 'rect':
        x = props.get('x', 0)
        y = props.get('y', 0)
        rw = props.get('width', 100)
        rh = props.get('height', 50)
        fill = _esc_js(props.get('fill', '#000'))
        draw_code = f'ctx.fillStyle = "{fill}";\nctx.fillRect({x}, {y}, {rw}, {rh});'
        if 'stroke' in props:
            draw_code += f'\nctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.strokeRect({x}, {y}, {rw}, {rh});'

    elif shape == 'circle':
        x = props.get('x', 50)
        y = props.get('y', 50)
        r = props.get('radius', 25)
        fill = _esc_js(props.get('fill', '#000'))
        draw_code = (
            f'ctx.beginPath();\n'
            f'ctx.arc({x}, {y}, {r}, 0, Math.PI * 2);\n'
            f'ctx.fillStyle = "{fill}"; ctx.fill();'
        )
        if 'stroke' in props:
            draw_code += f'\nctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.stroke();'

    elif shape == 'line':
        x1 = props.get('x1', 0)
        y1 = props.get('y1', 0)
        x2 = props.get('x2', 100)
        y2 = props.get('y2', 100)
        stroke = _esc_js(props.get('stroke', '#000'))
        lw = props.get('width', 1)
        draw_code = (
            f'ctx.beginPath();\n'
            f'ctx.moveTo({x1}, {y1}); ctx.lineTo({x2}, {y2});\n'
            f'ctx.strokeStyle = "{stroke}"; ctx.lineWidth = {lw}; ctx.stroke();'
        )

    elif shape == 'text':
        x = props.get('x', 10)
        y = props.get('y', 30)
        content = _esc_js(props.get('content', ''))
        font = _esc_js(props.get('font', '16px Arial'))
        fill = _esc_js(props.get('fill', '#000'))
        draw_code = (
            f'ctx.font = "{font}";\nctx.fillStyle = "{fill}";\nctx.fillText("{content}", {x}, {y});'
        )

    elif shape == 'path':
        points = _esc_js(props.get('points', ''))
        fill = _esc_js(props.get('fill', 'transparent'))
        draw_code = f'const p = new Path2D("{points}");\nctx.fillStyle = "{fill}"; ctx.fill(p);'
        if 'stroke' in props:
            draw_code += f'\nctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.stroke(p);'

    return (
        f'<canvas id="{canvas_id}" width="{w}" height="{h}"></canvas>\n'
        f'<script>\n'
        f'(function() {{\n'
        f'  const c = document.getElementById("{canvas_id}");\n'
        f'  const ctx = c.getContext("2d");\n'
        f'  {draw_code}\n'
        f'}})();\n'
        f'</script>'
    )


def _render_draw_commands_batched(commands):
    """Render multiple DrawCommand nodes onto a single shared canvas."""
    if not commands:
        return ''
    canvas_id = f'canvas-batch-{id(commands[0])}'
    w = max(int(cmd.properties.get('canvas_width', 800)) for cmd in commands)
    h = max(int(cmd.properties.get('canvas_height', 600)) for cmd in commands)

    all_draw_code = []
    for cmd in commands:
        draw_code = _get_draw_code(cmd)
        if draw_code:
            all_draw_code.append(draw_code)

    combined = '\n  '.join(all_draw_code)
    return (
        f'<canvas id="{canvas_id}" width="{w}" height="{h}"></canvas>\n'
        f'<script>\n'
        f'(function() {{\n'
        f'  const c = document.getElementById("{canvas_id}");\n'
        f'  const ctx = c.getContext("2d");\n'
        f'  {combined}\n'
        f'}})();\n'
        f'</script>'
    )


def _get_draw_code(cmd):
    """Extract just the canvas drawing code for a DrawCommand (no canvas creation)."""
    shape = cmd.shape
    props = cmd.properties

    if shape == 'rect':
        x, y = props.get('x', 0), props.get('y', 0)
        rw, rh = props.get('width', 100), props.get('height', 50)
        fill = _esc_js(props.get('fill', '#000'))
        code = f'ctx.fillStyle = "{fill}"; ctx.fillRect({x}, {y}, {rw}, {rh});'
        if 'stroke' in props:
            code += f' ctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.strokeRect({x}, {y}, {rw}, {rh});'
        return code

    elif shape == 'circle':
        x, y = props.get('x', 50), props.get('y', 50)
        r = props.get('radius', 25)
        fill = _esc_js(props.get('fill', '#000'))
        code = f'ctx.beginPath(); ctx.arc({x}, {y}, {r}, 0, Math.PI*2); ctx.fillStyle = "{fill}"; ctx.fill();'
        if 'stroke' in props:
            code += f' ctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.stroke();'
        return code

    elif shape == 'line':
        x1, y1 = props.get('x1', 0), props.get('y1', 0)
        x2, y2 = props.get('x2', 100), props.get('y2', 100)
        stroke = _esc_js(props.get('stroke', '#000'))
        lw = props.get('width', 1)
        return f'ctx.beginPath(); ctx.moveTo({x1},{y1}); ctx.lineTo({x2},{y2}); ctx.strokeStyle="{stroke}"; ctx.lineWidth={lw}; ctx.stroke();'

    elif shape == 'text':
        x, y = props.get('x', 10), props.get('y', 30)
        content = _esc_js(props.get('content', ''))
        font = _esc_js(props.get('font', '16px Arial'))
        fill = _esc_js(props.get('fill', '#000'))
        return f'ctx.font="{font}"; ctx.fillStyle="{fill}"; ctx.fillText("{content}",{x},{y});'

    elif shape == 'path':
        points = _esc_js(props.get('points', ''))
        fill = _esc_js(props.get('fill', 'transparent'))
        code = f'const p=new Path2D("{points}"); ctx.fillStyle="{fill}"; ctx.fill(p);'
        if 'stroke' in props:
            code += f' ctx.strokeStyle="{_esc_js(props["stroke"])}"; ctx.stroke(p);'
        return code

    return ''
