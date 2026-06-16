"""
EPL HTML Generator (v0.5)
Converts PageDef and HtmlElement AST nodes into styled HTML.
"""

import re
import secrets

from epl import ast_nodes as ast

# ─── Page-level config (v9.2.0) ────────────────────────────
# Footer and font-loading were hardcoded before v9.2.0. Defaults now match
# enterprise expectations: no branding footer, no third-party CDN.
# Override via configure_page(footer=..., fonts=...) before generate_html().
_CONFIG = {
    'footer': None,  # str | None.  None = omit footer entirely.
    'fonts': 'system',  # 'system' (default) | 'cdn'  (cdn = legacy Google Fonts)
    'theme': 'auto',  # v9.3.0 Phase 4: 'light' | 'dark' | 'auto' (follows OS)
    'csp': False,  # Phase 5: opt-in strict CSP with per-response script nonce.
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


def configure_page(footer=None, fonts=None, theme=None, csp=None):
    """Configure page-level rendering options.

    Args:
        footer: Footer HTML text, or None to omit. Default None.
        fonts:  'system' uses native system font stack (no network);
                'cdn' loads Inter from Google Fonts (pre-v9.2.0 behaviour).
        theme:  'light', 'dark', or 'auto' (default — follows OS preference).
                Sets the `color-scheme` meta + the built-in CSS variable palette
                (`--bg`, `--fg`, `--muted`, `--accent`, `--surface`, `--border`,
                `--danger`).
        csp:    True enables strict Content-Security-Policy mode (Phase 5):
                every generated <script> gets a per-response nonce and the
                response-header CSP becomes `script-src 'self' 'nonce-…'`.
                Default False keeps output byte-identical.

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
    if csp is not None:
        _CONFIG['csp'] = bool(csp)


def reset_config():
    """Reset page config to defaults. Primarily used by tests."""
    _CONFIG['footer'] = None
    _CONFIG['fonts'] = 'system'
    _CONFIG['theme'] = 'auto'
    _CONFIG['csp'] = False


# ─── Phase 5: Content-Security-Policy / script nonce ─────────


def new_nonce():
    """Return a fresh per-response script nonce when CSP mode is on, else None.

    Uses a CSPRNG; the value is URL-safe base64 (A–Z a–z 0–9 _ -) so it is safe
    verbatim in both an HTML attribute and a CSP `'nonce-…'` source.
    """
    return secrets.token_urlsafe(16) if _CONFIG['csp'] else None


def build_csp_header(nonce=None):
    """Single source of truth for the Content-Security-Policy value.

    With `nonce`, `script-src` authorizes the generated inline scripts via
    `'nonce-…'`. Without it, returns the exact policy used before Phase 5 so
    behaviour is unchanged when CSP mode is off.
    """
    script_src = "'self'" if not nonce else f"'self' 'nonce-{nonce}'"
    return (
        f"default-src 'self'; script-src {script_src}; "
        "style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'"
    )


def _add_nonce_to_scripts(html, nonce):
    """Add `nonce="…"` to every generated <script> tag that lacks one.

    A nonce on a <script> tag authorizes it under CSP3 regardless of `src`, so
    this covers native-animation, event, hoisted-Script, and canvas/3D CDN
    scripts uniformly without threading the nonce into each renderer. The
    negative lookahead prevents double-adding.
    """
    return re.sub(r'<script(?![^>]*\bnonce=)', f'<script nonce="{nonce}"', html)


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
    page_def,
    data_store=None,
    form_data=None,
    styles=None,
    components=None,
    animations=None,
    stylesheets=None,
    head=None,
    nonce=None,
):
    """Convert a PageDef AST node into a full HTML page string.

    styles: list of StyleDef nodes collected from the program
    components: dict of component_name -> ComponentDef
    animations: list of AnimateDef nodes
    stylesheets: list of RawStylesheet nodes (raw CSS, server-rendered into head)
    head: list of site-wide HeadDirective nodes (SEO/meta/fonts); per-page
          overrides ride on page_def.head_directives and win over these.
    nonce: Phase 5 — when set, every generated <script> is tagged with this
           CSP nonce. Default None keeps output byte-identical.
    """
    title = page_def.title if isinstance(page_def, ast.PageDef) else 'EPL Page'
    elements = page_def.elements if isinstance(page_def, ast.PageDef) else []
    store = data_store if data_store is not None else {}
    comps = components or {}

    batched_elements = _batch_draw_commands(elements)
    # Phase 4 — assign data-evt ids and build native event JS BEFORE rendering
    # body, so the selector-hook attribute is present in the emitted markup.
    events_js = _collect_event_handlers(batched_elements)
    body_html = '\n'.join(
        _render_any_element(e, store, form_data, comps) for e in batched_elements if e
    )
    scripts = '\n'.join(_extract_scripts(e) for e in elements if e)
    # Combine native event JS + hoisted Script content into one slot so pages
    # without either add no markup (keeps output byte-stable when unused).
    scripts_html = (f'<script>{events_js}</script>' if events_js else '') + (
        f'<script>{scripts}</script>' if scripts else ''
    )

    # Page-scoped CSS (Phase 6): a Page's own Style/Stylesheet blocks render
    # only on this route, appended AFTER site-wide CSS so they win the cascade.
    page_styles = getattr(page_def, 'styles', None) if isinstance(page_def, ast.PageDef) else None
    page_sheets = (
        getattr(page_def, 'stylesheets', None) if isinstance(page_def, ast.PageDef) else None
    )
    merged_styles = (styles or []) + (page_styles or [])
    merged_sheets = (stylesheets or []) + (page_sheets or [])

    custom_css = _generate_custom_css(merged_styles)
    animation_css = _generate_animation_css(animations or [])
    raw_css = _collect_raw_stylesheets(merged_sheets)
    extra_css = ''
    if custom_css or animation_css or raw_css:
        extra_css = f'\n    <style>\n{custom_css}\n{animation_css}\n{raw_css}\n    </style>'

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

    # Phase 3 — server-rendered head/SEO directives. Site-wide `head` merges
    # with per-page overrides (page wins). A native Font directive supersedes
    # the legacy _CONFIG font link to avoid emitting two font stylesheets.
    page_head = (
        getattr(page_def, 'head_directives', None) if isinstance(page_def, ast.PageDef) else None
    )
    merged_head = _merge_head_directives(head or [], page_head or [])
    head_tags, font_present = _render_head_directives(merged_head)
    if font_present:
        font_link = ''
    head_block = f'\n    {head_tags}' if head_tags else ''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {color_scheme_meta}
    <title>{_esc(title)}</title>{head_block}
    {font_link}
    <style>{theme_css}\n{STYLES}</style>{extra_css}
</head>
<body>
    <div class="container">
        {body_html}
    </div>
    {footer_html}
    {native_animations_js}
    {scripts_html}
</body>
</html>"""
    if nonce:
        html = _add_nonce_to_scripts(html, nonce)
    return html


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


_CSS_SELECTOR_ALLOWED = set(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .#>+~*[]="\':()_-,'
)


def _esc_css_selector(selector):
    """Sanitize a descendant/combinator selector fragment.

    Allows the common selector characters but strips block/markup characters
    (`{ } < >`) so a `Select "..."` value can't break out of its rule.
    """
    if not isinstance(selector, str):
        selector = str(selector)
    return ''.join(c for c in selector if c in _CSS_SELECTOR_ALLOWED)


def _safe_href(url):
    """Sanitize href to prevent javascript: URI injection."""
    if not isinstance(url, str):
        return '#'
    url_stripped = url.strip().lower()
    if url_stripped.startswith(('javascript:', 'vbscript:', 'data:text/html')):
        return '#'
    return _esc(url)


_SAFE_ATTR_NAME_RE = _re.compile(r'^[a-zA-Z][a-zA-Z0-9-]*$')


def _is_render_safe_attr(name):
    """Render-time attribute allowlist (defense in depth; mirrors the parser).

    Blocks inline event handlers (`on*`) and any name with unexpected
    characters. `class`/`id`/`style` are emitted by dedicated code paths.
    """
    if not isinstance(name, str) or not _SAFE_ATTR_NAME_RE.match(name):
        return False
    lowered = name.lower()
    if lowered.startswith('on') or lowered in ('style', 'class'):
        return False
    return True


def _render_safe_attrs(attributes, skip=()):
    """Emit `attributes` as escaped HTML attributes, dropping unsafe names.

    `skip` lists keys handled elsewhere (e.g. 'href', 'id', 'data-animate').
    """
    if not attributes:
        return ''
    skip_set = set(skip)
    out = []
    for name, value in attributes.items():
        if name in skip_set or not _is_render_safe_attr(name):
            continue
        out.append(f' {name}="{_esc(value if isinstance(value, str) else str(value))}"')
    return ''.join(out)


def _render_element_attrs(attributes, skip=()):
    """Emit class/id/style plus generic safe attributes from a flat attrs dict.

    Used by one-line elements (link, button). `skip` lists keys rendered by
    their own code path (e.g. 'href', 'onclick').
    """
    if not attributes:
        return ''
    skip_set = set(skip)
    parts = []
    for key in ('class', 'id', 'style'):
        if key in attributes and key not in skip_set:
            parts.append(f' {key}="{_esc(str(attributes[key]))}"')
    parts.append(_render_safe_attrs(attributes, skip=skip_set | {'class', 'id', 'style'}))
    return ''.join(parts)


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
        extra = _render_element_attrs(attrs, skip={'href'})
        return f'<a href="{_safe_href(href)}"{extra}>{_esc(content)}</a>'

    if tag == 'image':
        src = attrs.get('src', '')
        return f'<img src="{_esc(src)}" alt="image">'

    if tag == 'button':
        onclick = attrs.get('onclick', '')
        # Sanitize onclick: only allow bare function calls with safe argument chars
        if onclick and not re.match(
            r'^[a-zA-Z_][a-zA-Z0-9_]*\([a-zA-Z0-9_,\s\'\"\.\-]*\)$', onclick
        ):
            onclick = ''  # Strip unsafe onclick values
        onclick_attr = f' onclick="{_esc(onclick)}"' if onclick else ''
        extra = _render_element_attrs(attrs, skip={'onclick'})
        return f'<button{onclick_attr}{extra}>{_esc(content)}</button>'

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
        has_button = any(getattr(c, 'tag', '') == 'button' for c in (elem.children or []))
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
        return (
            '<div class="noise-overlay native-noise"></div>'
            + '<svg style="display:none"><filter id="noise"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" stitchTiles="stitch"/></filter></svg>'
        )

    if tag == 'bg_noise':
        return (
            '<div class="bg-noise native-noise-bg"></div>'
            + '<svg style="display:none"><filter id="bgNoise"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch"/></filter></svg>'
        )

    if tag == 'words_pull_up':
        asterisk = attrs.get('asterisk', '').lower() == 'true'
        words = str(content).split(' ')
        spans = []
        for i, w in enumerate(words):
            if not w:
                continue
            delay = i * 0.1
            spans.append(
                f'<span class="native-pull-up" style="transition-delay: {delay}s;">{_esc(w)}</span>'
            )
        if asterisk:
            delay = len(words) * 0.1
            spans.append(
                f'<span class="native-pull-up hero-asterisk" style="transition-delay: {delay}s;">*</span>'
            )
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
                    if not w:
                        continue
                    delay = word_index * 0.1
                    spans.append(
                        f'<span class="native-pull-up {seg_style}" style="transition-delay: {delay}s;">{_esc(w)}</span>'
                    )
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
    import html as _html_mod
    import re

    def replace_count(m):
        coll = m.group(1)
        return str(len(data_store.get(coll, [])))

    def replace_items(m):
        coll = m.group(1)
        items = data_store.get(coll, [])
        # Escape HTML in each item value to prevent stored-XSS
        if isinstance(items, list):
            escaped = [_html_mod.escape(str(item)) for item in items]
            return str(escaped)
        return _html_mod.escape(str(items))

    text = re.sub(r'\$count\{(\w+)\}', replace_count, text)
    text = re.sub(r'\$items\{(\w+)\}', replace_items, text)
    return text


# ─── Phase 4: Native event handlers → CSP-safe generated JS ──────────────────


def _event_action_js(action, i):
    """Render one EventAction to a JS statement. `i` makes locals unique.

    Class/selector/fn names are parse-validated; string values are _esc_js'd
    and URLs pass through _safe_href. Output is static — no eval/Function.
    """
    kind = action.kind
    data = action.data or {}
    if kind in ('add_class', 'remove_class', 'toggle_class'):
        op = {'add_class': 'add', 'remove_class': 'remove', 'toggle_class': 'toggle'}[kind]
        cls = _esc_js(data.get('class', ''))
        sel = data.get('selector')
        if sel:
            return (
                f"var t{i}=document.querySelector('{_esc_js(sel)}')||el;"
                f"t{i}.classList.{op}('{cls}');"
            )
        return f"el.classList.{op}('{cls}');"
    if kind == 'navigate':
        return f"window.location.href='{_esc_js(_safe_href(data.get('url', '')))}';"
    if kind == 'scroll':
        return (
            f"var s{i}=document.querySelector('{_esc_js(data.get('selector', ''))}');"
            f"if(s{i})s{i}.scrollIntoView({{behavior:'smooth'}});"
        )
    if kind == 'run':
        fn = data.get('fn', '')  # validated ^[A-Za-z_$][\\w$]*$ at parse
        return f"if(typeof window.{fn}==='function')window.{fn}(el);"
    return ''


def _event_handler_js(evt_id, handler):
    """Render one EventHandler to a querySelectorAll().forEach(...) block."""
    body = ''.join(_event_action_js(a, i) for i, a in enumerate(handler.actions))
    sel = f'document.querySelectorAll(\'[data-evt="{evt_id}"]\')'
    if handler.event == 'reveal':
        # Fires once on scroll-into-view via the shared observer (__ro).
        return f'{sel}.forEach(function(el){{el.__r=function(){{{body}}};__ro.observe(el);}});'
    js_event = 'mouseenter' if handler.event == 'hover' else 'click'
    return (
        f"{sel}.forEach(function(el){{el.addEventListener('{js_event}',function(){{{body}}});}});"
    )


def _collect_event_handlers(elements):
    """Pre-pass: assign data-evt ids to elements with events and build their JS.

    Walks the element tree, mutating each event-bearing element's `attributes`
    with a unique `data-evt` selector hook (rendered via the existing safe-attr
    path), and returns the combined IIFE JS (or '' if there are no handlers).
    Must run before body rendering so the data-evt attribute is present.
    """
    state = {'next': 0, 'parts': [], 'has_reveal': False}

    def walk(el):
        events = getattr(el, 'events', None)
        if events and isinstance(getattr(el, 'attributes', None), dict):
            state['next'] += 1
            evt_id = str(state['next'])
            el.attributes['data-evt'] = evt_id
            for handler in events:
                if handler.event == 'reveal':
                    state['has_reveal'] = True
                state['parts'].append(_event_handler_js(evt_id, handler))
        for child in getattr(el, 'children', None) or []:
            if child is not None:
                walk(child)

    for el in elements:
        if el is not None:
            walk(el)

    if not state['parts']:
        return ''
    prelude = ''
    if state['has_reveal']:
        prelude = (
            'var __ro=new IntersectionObserver(function(es){es.forEach(function(en){'
            'if(en.isIntersecting){if(en.target.__r)en.target.__r();__ro.unobserve(en.target);}'
            '});},{threshold:0.12});'
        )
    return '(function(){' + prelude + ''.join(state['parts']) + '})();'


def _extract_scripts(elem):
    """Extract JavaScript from script elements, recursing into children.

    Scripts may be nested inside structural elements (Div/Section/…) or layout
    containers; their content is hoisted into the page's single <script> block.
    """
    if isinstance(elem, ast.HtmlElement):
        if elem.tag == 'script' and elem.content:
            return str(elem.content)
        parts = [_extract_scripts(c) for c in (elem.children or [])]
        return '\n'.join(p for p in parts if p)
    if isinstance(elem, (ast.StyledElement, ast.LayoutContainer)):
        parts = [_extract_scripts(c) for c in (elem.children or [])]
        return '\n'.join(p for p in parts if p)
    return ''


# ─── v6.0: Style & Layout Rendering ─────────────────────────


def _css_declarations(properties):
    """Render a list of StyleProperty nodes as indented CSS declarations."""
    decls = []
    for prop in properties:
        value = prop.value
        if isinstance(value, ast.Literal):
            value = value.value
        decls.append(f'    {_esc_css_ident(prop.property_name)}: {_esc_css_value(value)};')
    return '\n'.join(decls)


def _generate_custom_css(styles):
    """Generate CSS from StyleDef AST nodes, including nested StyleRule variants
    (pseudo-states, descendant selectors) and media-query blocks."""
    if not styles:
        return ''
    css_parts = []
    for style_def in styles:
        base = _esc_css_ident(style_def.name)
        css_parts.append(f'.{base} {{\n' + _css_declarations(style_def.properties) + '\n}')
        for rule in getattr(style_def, 'rules', None) or []:
            selector = f'.{base}{_esc_css_selector(rule.suffix)}'
            block = f'{selector} {{\n' + _css_declarations(rule.properties) + '\n}'
            if rule.media:
                # Media condition is parser-validated (named breakpoint or a
                # vetted width); wrap the rule in an @media query.
                block = f'@media {rule.media} {{\n{block}\n}}'
            css_parts.append(block)
    return '\n\n'.join(css_parts)


def _collect_raw_stylesheets(stylesheets):
    """Concatenate RawStylesheet bodies for emission into the head <style>.

    The body is a trusted, author-supplied escape hatch (like Raw HTML), but a
    breakout guard rejects content that could close the <style> element or open
    a <script>, since the text is emitted as raw stylesheet content.
    """
    if not stylesheets:
        return ''
    parts = []
    for sheet in stylesheets:
        css = sheet.css if isinstance(sheet.css, str) else str(sheet.css)
        lowered = css.lower()
        if '</style' in lowered or '<script' in lowered or '</script' in lowered:
            raise ValueError(
                'Stylesheet block may not contain "</style>" or "<script>" '
                '(would break out of the <style> element). Remove it or use a '
                'Script block for JavaScript.'
            )
        parts.append(css)
    return '\n'.join(parts)


_HEAD_LINK_ATTRS = ('rel', 'href', 'as', 'type', 'crossorigin', 'media', 'sizes', 'hreflang')
_FAVICON_TYPES = {
    'png': 'image/png',
    'svg': 'image/svg+xml',
    'ico': 'image/x-icon',
    'gif': 'image/gif',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
}


def _merge_head_directives(site, page):
    """Merge site-wide and per-page directives; page overrides win.

    Single-valued kinds (meta-by-name, canonical, favicon, opengraph, twitter)
    are de-duplicated so a page-level value replaces the site-wide one. Fonts
    and generic links accumulate (deduped by identity).
    """
    merged = []
    seen = {}

    def key_for(d):
        if d.kind == 'meta':
            return ('meta', d.data.get('name', ''))
        if d.kind in ('canonical', 'favicon', 'opengraph', 'twitter'):
            return (d.kind,)
        return None  # font / link accumulate

    for d in list(site or []) + list(page or []):
        k = key_for(d)
        if k is None:
            merged.append(d)
            continue
        if k in seen:
            merged[seen[k]] = d  # page (later) overrides
        else:
            seen[k] = len(merged)
            merged.append(d)
    return merged


def _render_head_directives(directives):
    """Render HeadDirective nodes to escaped <meta>/<link> tags for <head>.

    Returns (tags_html, font_present). All text is escaped and all URLs pass
    through _safe_href. Google-Font preconnect links are emitted at most once.
    """
    if not directives:
        return '', False
    out = []
    preconnect_done = False
    font_present = False

    for d in directives:
        data = d.data or {}
        if d.kind == 'meta':
            name = data.get('name', '')
            if name:
                out.append(f'<meta name="{_esc(name)}" content="{_esc(data.get("content", ""))}">')
        elif d.kind == 'canonical':
            out.append(f'<link rel="canonical" href="{_safe_href(data.get("href", ""))}">')
        elif d.kind == 'favicon':
            href = data.get('href', '')
            ext = href.rsplit('.', 1)[-1].lower() if '.' in href else ''
            type_attr = f' type="{_FAVICON_TYPES[ext]}"' if ext in _FAVICON_TYPES else ''
            out.append(f'<link rel="icon"{type_attr} href="{_safe_href(href)}">')
        elif d.kind == 'font':
            font_present = True
            if not preconnect_done:
                out.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
                out.append('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
                preconnect_done = True
            family = str(data.get('family', '')).strip()
            weights = str(data.get('weights', '400'))
            fam_param = _esc(family.replace(' ', '+'))
            wght = _esc(weights)
            out.append(
                f'<link rel="stylesheet" '
                f'href="https://fonts.googleapis.com/css2?family={fam_param}:wght@{wght}&display=swap">'
            )
        elif d.kind == 'link':
            attrs = []
            for k in _HEAD_LINK_ATTRS:
                if k not in data:
                    continue
                val = data[k]
                if k == 'href':
                    attrs.append(f' href="{_safe_href(val)}"')
                else:
                    attrs.append(f' {k}="{_esc(val)}"')
            if attrs:
                out.append(f'<link{"".join(attrs)}>')
        elif d.kind == 'opengraph':
            for k in ('title', 'description', 'type', 'image', 'url', 'site_name'):
                if k in data:
                    prop = 'og:site_name' if k == 'site_name' else f'og:{k}'
                    out.append(f'<meta property="{prop}" content="{_esc(data[k])}">')
        elif d.kind == 'twitter':
            for k in ('card', 'title', 'description', 'image', 'site', 'creator'):
                if k in data:
                    out.append(f'<meta name="twitter:{k}" content="{_esc(data[k])}">')

    return '\n    '.join(out), font_present


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

    # Generic safe attributes (aria-*, data-*, role, target, …). `id` and the
    # internal `data-animate` marker are handled above, so skip them here.
    extra_attr = _render_safe_attrs(elem.attributes, skip={'id', 'data-animate'})

    comps = components or {}
    children_html = '\n'.join(
        _render_any_element(c, data_store, form_data, comps) for c in elem.children if c
    )

    return f'<{tag}{class_attr}{id_attr}{style_attr}{extra_attr}>\n{children_html}\n</{tag}>'


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
