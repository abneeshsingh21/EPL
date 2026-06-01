"""
EPL HTML Generator (v0.5)
Converts PageDef and HtmlElement AST nodes into styled HTML.
"""

import re

from epl import ast_nodes as ast

# ─── Page-level config (v9.2.0) ────────────────────────────
# Footer and font-loading were hardcoded before v9.2.0. Defaults now match
# enterprise expectations: no branding footer, no third-party CDN.
# Override via configure_page(footer=..., fonts=...) before generate_html().
_CONFIG = {
    'footer': None,        # str | None.  None = omit footer entirely.
    'fonts': 'system',     # 'system' (default) | 'cdn'  (cdn = legacy Google Fonts)
    'theme': 'auto',       # v9.3.0 Phase 4: 'light' | 'dark' | 'auto' (follows OS)
}

# v9.3.0 Phase 4 — palette tokens shipped as CSS variables. Apps reference
# `var(--bg)`, `var(--fg)`, `var(--accent)` etc. and get the right value for
# whichever theme is active. The "auto" theme emits both palettes wrapped in
# `@media (prefers-color-scheme: ...)` so the browser picks.
_THEME_PALETTES = {
    'dark': {
        '--bg': '#0f172a',
        '--fg': '#f8fafc',
        '--muted': '#94a3b8',
        '--accent': '#38bdf8',
        '--surface': '#1e293b',
        '--border': 'rgba(255,255,255,0.08)',
        '--danger': '#ef4444',
    },
    'light': {
        '--bg': '#ffffff',
        '--fg': '#0f172a',
        '--muted': '#64748b',
        '--accent': '#0284c7',
        '--surface': '#f1f5f9',
        '--border': 'rgba(0,0,0,0.08)',
        '--danger': '#dc2626',
    },
}


def _emit_palette(name):
    """Render a palette dict as a CSS variable block (no selector wrapper)."""
    return '\n'.join(f'    {k}: {v};' for k, v in _THEME_PALETTES[name].items())


def _theme_css(theme):
    """Return the <style>-ready CSS for the requested theme.

    - 'dark' / 'light' emit a single :root palette plus a `body` colour pair.
    - 'auto' emits a default (light) palette and a `prefers-color-scheme: dark`
      override, letting the OS pick.
    """
    if theme == 'dark':
        body = f':root {{\n{_emit_palette("dark")}\n}}\nbody {{ background: var(--bg); color: var(--fg); }}'
        return body
    if theme == 'light':
        body = f':root {{\n{_emit_palette("light")}\n}}\nbody {{ background: var(--bg); color: var(--fg); }}'
        return body
    # auto
    return (
        f':root {{\n{_emit_palette("light")}\n}}\n'
        f'@media (prefers-color-scheme: dark) {{\n'
        f'  :root {{\n{_emit_palette("dark")}\n  }}\n'
        f'}}\n'
        f'body {{ background: var(--bg); color: var(--fg); }}'
    )


def configure_page(footer=None, fonts=None, theme=None):
    """Configure page-level rendering options.

    Args:
        footer: Footer HTML text, or None to omit. Default None.
        fonts:  'system' uses native system font stack (no network);
                'cdn' loads Inter from Google Fonts (pre-v9.2.0 behaviour).
        theme:  'light', 'dark', or 'auto' (default — follows OS preference).
                Sets the `color-scheme` meta + the built-in CSS variable palette
                (`--bg`, `--fg`, `--muted`, `--accent`, `--surface`, `--border`,
                `--danger`).

    Setting `footer` to the empty string also omits the footer.
    """
    if footer is not None:
        _CONFIG['footer'] = footer or None
    if fonts is not None:
        if fonts not in ('system', 'cdn'):
            raise ValueError(f"fonts must be 'system' or 'cdn', got {fonts!r}")
        _CONFIG['fonts'] = fonts
    if theme is not None:
        if theme not in ('light', 'dark', 'auto'):
            raise ValueError(f"theme must be 'light', 'dark', or 'auto', got {theme!r}")
        _CONFIG['theme'] = theme


def reset_config():
    """Reset page config to defaults. Primarily used by tests."""
    _CONFIG['footer'] = None
    _CONFIG['fonts'] = 'system'
    _CONFIG['theme'] = 'auto'


# Modern Premium CSS - Professional Component Design
STYLES = """
/* Minimal Reset for EPL Web */
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; padding: 0; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }


/* Native Component Styles */
.native-pull-up {
    display: inline-block;
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.8s cubic-bezier(0.16,1,0.3,1), transform 0.8s cubic-bezier(0.16,1,0.3,1);
}
.native-pull-up.visible {
    opacity: 1;
    transform: translateY(0);
}
.native-words-wrapper {
    display: inline-block;
}
.noise-overlay.native-noise {
    position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0.7; mix-blend-mode: overlay; pointer-events: none; background-color: transparent; filter: url('#noise'); z-index: 1;
}
.bg-noise.native-noise-bg {
    position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0.4; pointer-events: none; background-color: transparent; filter: url('#bgNoise'); z-index: 0;
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

    native_animations_js = """
    <script>
    document.addEventListener('DOMContentLoaded', () => {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if(entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1 });
        document.querySelectorAll('.native-pull-up').forEach(el => observer.observe(el));
    });
    </script>
    """

    # Font loading — system stack (default, no network) or Google Fonts CDN.
    if _CONFIG['fonts'] == 'cdn':
        font_link = (
            '<link href="https://fonts.googleapis.com/css2?'
            'family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        )
    else:
        font_link = ''

    # Footer — None/empty = omit. User-provided text is HTML-escaped.
    footer_html = f'<footer>{_esc(_CONFIG["footer"])}</footer>' if _CONFIG['footer'] else ''

    # Theme (v9.3.0 Phase 4) — color-scheme meta drives native form controls
    # and scrollbars; the palette CSS injects the CSS-variable colour tokens.
    theme = _CONFIG['theme']
    color_scheme_meta = {
        'dark': '<meta name="color-scheme" content="dark">\n    <meta name="darkreader-lock">',
        'light': '<meta name="color-scheme" content="light">',
        'auto': '<meta name="color-scheme" content="light dark">',
    }[theme]
    theme_css = _theme_css(theme)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {color_scheme_meta}
    <title>{_esc(title)}</title>
    {font_link}
    <style>{theme_css}\n{STYLES}</style>{extra_css}
</head>
<body>
    <div class="container">
        {body_html}
    </div>
    {footer_html}
    {native_animations_js}
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
        # Auto-detect input type from name attribute
        input_type = attrs.get('type', 'text')
        if input_type == 'text' and 'password' in name.lower():
            input_type = 'password'
        elif input_type == 'text' and 'email' in name.lower():
            input_type = 'email'
        return f'<input type="{_esc(input_type)}" name="{_esc(name)}" id="{_esc(name)}" placeholder="{_esc(ph)}">'

    if tag == 'form':
        action = attrs.get('action', '')
        children_html = '\n'.join(
            _render_element(c, store, form_data) for c in (elem.children or [])
        )
        # Only add a default Submit button if the form doesn't already have one
        has_button = any(
            getattr(c, 'tag', '') == 'button' for c in (elem.children or [])
        )
        submit_btn = '' if has_button else '\n<button type="submit" class="btn">Submit</button>'
        return f'<form action="{_esc(action)}" method="POST">\n{children_html}{submit_btn}\n</form>'

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

    if tag == 'noise_overlay':
        return '<div class="noise-overlay native-noise"></div>' + \
               '<svg style="display:none"><filter id="noise"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" stitchTiles="stitch"/></filter></svg>'

    if tag == 'bg_noise':
        return '<div class="bg-noise native-noise-bg"></div>' + \
               '<svg style="display:none"><filter id="bgNoise"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch"/></filter></svg>'

    if tag == 'words_pull_up':
        asterisk = attrs.get('asterisk', '').lower() == 'true'
        words = str(content).split(' ')
        spans = []
        for i, w in enumerate(words):
            if not w: continue
            delay = i * 0.1
            spans.append(f'<span class="native-pull-up" style="transition-delay: {delay}s;">{_esc(w)}</span>')
        if asterisk:
            delay = len(words) * 0.1
            spans.append(f'<span class="native-pull-up hero-asterisk" style="transition-delay: {delay}s;">*</span>')
        return f'<div class="native-words-wrapper">{"&nbsp;".join(spans)}</div>'

    if tag == 'words_pull_up_multi_style':
        children = elem.children or []
        spans = []
        word_index = 0
        for child in children:
            if getattr(child, 'tag', '') == 'segment':
                seg_content = str(getattr(child, 'content', ''))
                seg_style = getattr(child, 'attributes', {}).get('style', '')
                words = seg_content.split(' ')
                for w in words:
                    if not w: continue
                    delay = word_index * 0.1
                    spans.append(f'<span class="native-pull-up {seg_style}" style="transition-delay: {delay}s;">{_esc(w)}</span>')
                    word_index += 1
        return f'<div class="native-words-wrapper">{"&nbsp;".join(spans)}</div>'

    if tag == 'script':
        return ''  # scripts go in the <script> section

    if tag == 'raw_html':
        # Escape hatch (v9.3.0). Emits the source string verbatim — no escaping.
        # The author is responsible for ensuring `content` is safe. Never pass
        # user input here without first sanitising it (e.g. via bleach).
        return content if isinstance(content, str) else str(content)

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
