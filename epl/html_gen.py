"""
EPL HTML Generator (v0.5)
Converts PageDef and HtmlElement AST nodes into styled HTML.
"""
import re
from epl import ast_nodes as ast


# Modern CSS theme — dark, sleek, responsive
STYLES = """
:root {
    --bg: #0f172a; --surface: #1e293b; --card: #334155;
    --text: #f1f5f9; --muted: #94a3b8; --accent: #3b82f6;
    --accent2: #8b5cf6; --success: #22c55e; --danger: #ef4444;
    --radius: 12px; --shadow: 0 4px 24px rgba(0,0,0,0.3);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    line-height: 1.7; min-height: 100vh;
}
.container {
    max-width: 900px; margin: 0 auto; padding: 40px 24px;
}
h1 {
    font-size: 2.5rem; font-weight: 800;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 16px;
}
h2 {
    font-size: 1.5rem; font-weight: 600; color: var(--muted);
    margin-bottom: 12px;
}
p {
    font-size: 1.1rem; color: var(--muted); margin-bottom: 16px;
    line-height: 1.8;
}
a {
    color: var(--accent); text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.2s;
}
a:hover { border-bottom-color: var(--accent); }
img {
    max-width: 100%; border-radius: var(--radius);
    box-shadow: var(--shadow); margin: 16px 0;
}
button, .btn {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white; border: none; padding: 12px 28px;
    border-radius: var(--radius); font-size: 1rem; font-weight: 600;
    cursor: pointer; transition: transform 0.15s, box-shadow 0.15s;
    box-shadow: 0 4px 12px rgba(59,130,246,0.3);
    margin: 8px 4px;
}
button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(59,130,246,0.4); }
button:active { transform: translateY(0); }
input, textarea {
    background: var(--surface); border: 1px solid var(--card);
    color: var(--text); padding: 12px 16px; border-radius: var(--radius);
    font-size: 1rem; width: 100%; margin: 8px 0;
    transition: border-color 0.2s;
}
input:focus, textarea:focus {
    outline: none; border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}
form {
    background: var(--surface); padding: 24px;
    border-radius: var(--radius); margin: 16px 0;
    box-shadow: var(--shadow);
}
ul, ol {
    padding-left: 24px; margin: 12px 0; color: var(--muted);
}
li { margin: 6px 0; }
.card {
    background: var(--surface); padding: 24px;
    border-radius: var(--radius); margin: 16px 0;
    box-shadow: var(--shadow);
    border: 1px solid var(--card);
}
.nav {
    background: var(--surface); padding: 16px 24px;
    border-bottom: 1px solid var(--card);
    display: flex; align-items: center; gap: 24px;
}
.nav a { color: var(--text); font-weight: 500; }
.badge {
    background: var(--accent); color: white;
    padding: 4px 12px; border-radius: 20px;
    font-size: 0.8rem; font-weight: 600;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.container > * { animation: fadeIn 0.4s ease-out both; }
.container > *:nth-child(1) { animation-delay: 0.05s; }
.container > *:nth-child(2) { animation-delay: 0.1s; }
.container > *:nth-child(3) { animation-delay: 0.15s; }
.container > *:nth-child(4) { animation-delay: 0.2s; }
.container > *:nth-child(5) { animation-delay: 0.25s; }
footer {
    text-align: center; padding: 24px; color: var(--muted);
    font-size: 0.85rem; margin-top: 40px;
    border-top: 1px solid var(--card);
}
"""


def generate_html(page_def, data_store=None, form_data=None):
    """Convert a PageDef AST node into a full HTML page string."""
    title = page_def.title if isinstance(page_def, ast.PageDef) else "EPL Page"
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
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')


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
        children_html = '\n'.join(_render_element(c, store, form_data) for c in (elem.children or []))
        return f'<form action="{_esc(action)}" method="POST">\n{children_html}\n<button type="submit" class="btn">Submit</button>\n</form>'

    if tag == 'list':
        # content is a ListLiteral or evaluated list
        if isinstance(content, ast.ListLiteral):
            items = [f'<li>{_esc(e.value if hasattr(e, "value") else str(e))}</li>' for e in content.elements]
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
