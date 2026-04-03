"""
EPL Phase 3 Test Suite — Web & Networking
Tests: HTTP framework, WebSocket, ORM extensions, template engine, HTML builder,
       REST API helpers, Auth/JWT — 111 functions across 7 modules.
"""
import sys, os, json, tempfile, time, shutil, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.interpreter import EPLDict
from epl.stdlib import call_stdlib
from epl.errors import EPLError

PASSED = 0
FAILED = 0

def run_case(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
        print(f"  PASS: {name}")
    except Exception as e:
        FAILED += 1
        print(f"  FAIL: {name} -> {e}")

def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"

def assert_true(v, msg=""):
    assert v, msg or f"Expected truthy, got {v!r}"

def assert_in(item, collection, msg=""):
    assert item in collection, msg or f"{item!r} not in {collection!r}"

def assert_isinstance(obj, cls, msg=""):
    assert isinstance(obj, cls), msg or f"Expected {cls}, got {type(obj)}"

def _data(resp_data, key=None):
    """Unwrap EPLDict/dict data. If key given, access that sub-key."""
    d = resp_data
    if isinstance(d, EPLDict):
        d = d.data
    if key is not None:
        val = d[key]
        if isinstance(val, EPLDict):
            return val.data
        return val
    return d

def d(dct):
    """Create EPLDict from plain dict."""
    return EPLDict(dct)

# ═══════════════════════════════════════════════════════════
#  1. TEMPLATE ENGINE (6 functions + rendering features)
# ═══════════════════════════════════════════════════════════

def main():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("\n=== 1. Template Engine ===")
    
    def t_template_create():
        r = call_stdlib('template_create', ['greeting', 'Hello {{ name }}!'], 0)
        assert_eq(r, 'greeting')
    run_case("template_create", t_template_create)
    
    def t_template_exists_true():
        call_stdlib('template_create', ['exists_test', 'content'], 0)
        assert_true(call_stdlib('template_exists', ['exists_test'], 0))
    run_case("template_exists true", t_template_exists_true)
    
    def t_template_exists_false():
        assert_eq(call_stdlib('template_exists', ['no_such_template'], 0), False)
    run_case("template_exists false", t_template_exists_false)
    
    def t_template_render_variable():
        call_stdlib('template_create', ['greet', 'Hello {{ name }}!'], 0)
        r = call_stdlib('template_render', ['greet', {'name': 'World'}], 0)
        assert_eq(r, 'Hello World!')
    run_case("template_render variable", t_template_render_variable)
    
    def t_template_render_string():
        r = call_stdlib('template_render_string', ['{{ x }} + {{ y }} = {{ z }}', {'x': '2', 'y': '3', 'z': '5'}], 0)
        assert_eq(r, '2 + 3 = 5')
    run_case("template_render_string", t_template_render_string)
    
    def t_template_render_escaping():
        r = call_stdlib('template_render_string', ['{{ val }}', {'val': '<script>alert(1)</script>'}], 0)
        assert_in('&lt;', r)
        assert_true('<script>' not in r)
    run_case("template auto-escaping", t_template_render_escaping)
    
    def t_template_filter_upper():
        r = call_stdlib('template_render_string', ['{{ name|upper }}', {'name': 'hello'}], 0)
        assert_eq(r, 'HELLO')
    run_case("template filter upper", t_template_filter_upper)
    
    def t_template_filter_lower():
        r = call_stdlib('template_render_string', ['{{ name|lower }}', {'name': 'HELLO'}], 0)
        assert_eq(r, 'hello')
    run_case("template filter lower", t_template_filter_lower)
    
    def t_template_filter_title():
        r = call_stdlib('template_render_string', ['{{ name|title }}', {'name': 'hello world'}], 0)
        assert_eq(r, 'Hello World')
    run_case("template filter title", t_template_filter_title)
    
    def t_template_filter_length():
        r = call_stdlib('template_render_string', ['{{ items|length }}', {'items': [1, 2, 3]}], 0)
        assert_eq(r, '3')
    run_case("template filter length", t_template_filter_length)
    
    def t_template_filter_default():
        r = call_stdlib('template_render_string', ['{{ missing|default:"N/A" }}', {}], 0)
        assert_eq(r, 'N/A')
    run_case("template filter default", t_template_filter_default)
    
    def t_template_filter_join():
        r = call_stdlib('template_render_string', ['{{ items|join:", " }}', {'items': ['a', 'b', 'c']}], 0)
        assert_eq(r, 'a, b, c')
    run_case("template filter join", t_template_filter_join)
    
    def t_template_for_loop():
        tmpl = '{% for x in items %}{{ x }} {% endfor %}'
        r = call_stdlib('template_render_string', [tmpl, {'items': ['a', 'b', 'c']}], 0)
        assert_eq(r.strip(), 'a b c')
    run_case("template for loop", t_template_for_loop)
    
    def t_template_for_loop_index():
        tmpl = '{% for x in items %}{{ loop.index }}{% endfor %}'
        r = call_stdlib('template_render_string', [tmpl, {'items': ['a', 'b', 'c']}], 0)
        assert_eq(r, '123')
    run_case("template for loop.index", t_template_for_loop_index)
    
    def t_template_if_true():
        tmpl = '{% if show %}visible{% endif %}'
        r = call_stdlib('template_render_string', [tmpl, {'show': True}], 0)
        assert_eq(r, 'visible')
    run_case("template if true", t_template_if_true)
    
    def t_template_if_false():
        tmpl = '{% if show %}visible{% endif %}'
        r = call_stdlib('template_render_string', [tmpl, {'show': False}], 0)
        assert_eq(r, '')
    run_case("template if false", t_template_if_false)
    
    def t_template_if_else():
        tmpl = '{% if logged_in %}Welcome{% else %}Please login{% endif %}'
        r = call_stdlib('template_render_string', [tmpl, {'logged_in': False}], 0)
        assert_eq(r, 'Please login')
    run_case("template if/else", t_template_if_else)
    
    def t_template_include():
        call_stdlib('template_create', ['_header', '<h1>Header</h1>'], 0)
        tmpl = '{% include "_header" %}<p>Body</p>'
        r = call_stdlib('template_render_string', [tmpl, {}], 0)
        assert_eq(r, '<h1>Header</h1><p>Body</p>')
    run_case("template include", t_template_include)
    
    def t_template_custom_filter():
        call_stdlib('template_add_filter', ['exclaim', lambda s: str(s) + '!!!'], 0)
        r = call_stdlib('template_render_string', ['{{ msg|exclaim }}', {'msg': 'wow'}], 0)
        assert_eq(r, 'wow!!!')
    run_case("template custom filter", t_template_custom_filter)
    
    def t_template_from_file():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write('Hello {{ who }}!')
            fpath = f.name
        try:
            tname = call_stdlib('template_from_file', [fpath], 0)
            assert_true(call_stdlib('template_exists', [tname], 0))
            r = call_stdlib('template_render', [tname, {'who': 'File'}], 0)
            assert_eq(r, 'Hello File!')
        finally:
            os.unlink(fpath)
    run_case("template from file", t_template_from_file)
    
    def t_template_dotted_access():
        tmpl = '{{ user.name }}'
        r = call_stdlib('template_render_string', [tmpl, {'user': {'name': 'Alice'}}], 0)
        assert_eq(r, 'Alice')
    run_case("template dotted access", t_template_dotted_access)
    
    def t_template_filter_safe():
        r = call_stdlib('template_render_string', ['{{ html|safe }}', {'html': '<b>bold</b>'}], 0)
        assert_eq(r, '<b>bold</b>')
    run_case("template filter safe", t_template_filter_safe)
    
    def t_template_if_comparison():
        tmpl = '{% if count == 0 %}empty{% else %}has items{% endif %}'
        r = call_stdlib('template_render_string', [tmpl, {'count': 0}], 0)
        assert_eq(r, 'empty')
    run_case("template if comparison", t_template_if_comparison)
    
    # ═══════════════════════════════════════════════════════════
    #  2. HTML BUILDER (10 functions)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 2. HTML Builder ===")
    
    def t_html_element_basic():
        r = call_stdlib('html_element', ['div', 'Hello'], 0)
        assert_eq(r, '<div>Hello</div>')
    run_case("html_element basic", t_html_element_basic)
    
    def t_html_element_attrs():
        r = call_stdlib('html_element', ['p', 'Text', {'class': 'intro', 'id': 'p1'}], 0)
        assert_in('class="intro"', r)
        assert_in('id="p1"', r)
        assert_in('Text', r)
    run_case("html_element with attrs", t_html_element_attrs)
    
    def t_html_element_void():
        r = call_stdlib('html_element', ['br'], 0)
        assert_eq(r, '<br>')
    run_case("html_element void tag", t_html_element_void)
    
    def t_html_element_input():
        r = call_stdlib('html_element', ['input', None, {'type': 'text', 'name': 'q'}], 0)
        assert_in('type="text"', r)
        assert_true(r.startswith('<input'))
        assert_true('</input>' not in r)
    run_case("html_element input (void)", t_html_element_input)
    
    def t_html_table():
        r = call_stdlib('html_table', [['Name', 'Age'], [['Alice', '30'], ['Bob', '25']]], 0)
        assert_in('<table>', r)
        assert_in('<th>Name</th>', r)
        assert_in('<td>Alice</td>', r)
        assert_in('<td>25</td>', r)
        assert_in('</table>', r)
    run_case("html_table", t_html_table)
    
    def t_html_form():
        fields = [
            {'type': 'text', 'name': 'username', 'label': 'Username', 'required': True},
            {'type': 'submit', 'value': 'Go'}
        ]
        r = call_stdlib('html_form', ['/login', 'POST', fields], 0)
        assert_in('action="/login"', r)
        assert_in('method="POST"', r)
        assert_in('name="username"', r)
        assert_in('required', r)
        assert_in('type="submit"', r)
        assert_in('<label', r)
    run_case("html_form", t_html_form)
    
    def t_html_list_unordered():
        r = call_stdlib('html_list', [['Alpha', 'Beta', 'Gamma']], 0)
        assert_in('<ul>', r)
        assert_in('<li>Alpha</li>', r)
        assert_in('</ul>', r)
    run_case("html_list unordered", t_html_list_unordered)
    
    def t_html_list_ordered():
        r = call_stdlib('html_list', [['First', 'Second'], True], 0)
        assert_in('<ol>', r)
        assert_in('<li>First</li>', r)
    run_case("html_list ordered", t_html_list_ordered)
    
    def t_html_link():
        r = call_stdlib('html_link', ['/about', 'About Us'], 0)
        assert_in('href="/about"', r)
        assert_in('>About Us</a>', r)
    run_case("html_link", t_html_link)
    
    def t_html_link_blocks_js():
        try:
            call_stdlib('html_link', ['javascript:alert(1)', 'Click'], 0)
            assert False, "Should block javascript: URI"
        except EPLError:
            pass
    run_case("html_link blocks javascript:", t_html_link_blocks_js)
    
    def t_html_image():
        r = call_stdlib('html_image', ['/img/logo.png', 'Logo'], 0)
        assert_in('src="/img/logo.png"', r)
        assert_in('alt="Logo"', r)
        assert_true(r.startswith('<img'))
    run_case("html_image", t_html_image)
    
    def t_html_page():
        r = call_stdlib('html_page', ['My App', '<h1>Hello</h1>', 'body{color:red}', 'alert(1)'], 0)
        assert_in('<!DOCTYPE html>', r)
        assert_in('<title>My App</title>', r)
        assert_in('<h1>Hello</h1>', r)
        assert_in('body{color:red}', r)
        assert_in('alert(1)', r)
    run_case("html_page", t_html_page)
    
    def t_html_escape():
        r = call_stdlib('html_escape', ['<script>alert("xss")</script>'], 0)
        assert_in('&lt;', r)
        assert_true('<script>' not in r)
    run_case("html_escape", t_html_escape)
    
    def t_html_unescape():
        r = call_stdlib('html_unescape', ['&lt;b&gt;bold&lt;/b&gt;'], 0)
        assert_eq(r, '<b>bold</b>')
    run_case("html_unescape", t_html_unescape)
    
    def t_html_minify():
        html = '<!-- comment -->\n<div>  <p>  Hello  </p>  </div>'
        r = call_stdlib('html_minify', [html], 0)
        assert_true('<!-- comment -->' not in r)
        assert_true('  ' not in r or len(r) < len(html))
    run_case("html_minify", t_html_minify)
    
    def t_html_form_select():
        fields = [{'type': 'select', 'name': 'color', 'options': ['red', 'green', 'blue']}]
        r = call_stdlib('html_form', ['/pick', 'POST', fields], 0)
        assert_in('<select', r)
        assert_in('value="red"', r)
        assert_in('value="green"', r)
    run_case("html_form select", t_html_form_select)
    
    def t_html_form_textarea():
        fields = [{'type': 'textarea', 'name': 'bio', 'placeholder': 'Tell us...'}]
        r = call_stdlib('html_form', ['/profile', 'POST', fields], 0)
        assert_in('<textarea', r)
        assert_in('name="bio"', r)
    run_case("html_form textarea", t_html_form_textarea)
    
    # ═══════════════════════════════════════════════════════════
    #  3. AUTH & JWT (10 functions)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 3. Auth & JWT ===")
    
    def t_auth_hash_password():
        h = call_stdlib('auth_hash_password', ['secret123'], 0)
        assert_isinstance(h, str)
        assert_in(':', h)
        parts = h.split(':')
        assert_eq(len(parts), 2)
        assert_true(len(parts[0]) == 64)  # 32 bytes hex
        assert_true(len(parts[1]) == 64)
    run_case("auth_hash_password", t_auth_hash_password)
    
    def t_auth_verify_password_correct():
        h = call_stdlib('auth_hash_password', ['mypass'], 0)
        assert_true(call_stdlib('auth_verify_password', ['mypass', h], 0))
    run_case("auth_verify_password correct", t_auth_verify_password_correct)
    
    def t_auth_verify_password_wrong():
        h = call_stdlib('auth_hash_password', ['mypass'], 0)
        assert_eq(call_stdlib('auth_verify_password', ['wrongpass', h], 0), False)
    run_case("auth_verify_password wrong", t_auth_verify_password_wrong)
    
    def t_auth_jwt_create():
        token = call_stdlib('auth_jwt_create', [{'user': 'alice'}, 'secret_key'], 0)
        assert_isinstance(token, str)
        parts = token.split('.')
        assert_eq(len(parts), 3)
    run_case("auth_jwt_create", t_auth_jwt_create)
    
    def t_auth_jwt_verify():
        token = call_stdlib('auth_jwt_create', [{'user': 'bob'}, 'key123'], 0)
        payload = call_stdlib('auth_jwt_verify', [token, 'key123'], 0)
        assert_isinstance(payload, EPLDict)
        assert_eq(payload.data['user'], 'bob')
        assert_in('iat', payload.data)
        assert_in('exp', payload.data)
    run_case("auth_jwt_verify", t_auth_jwt_verify)
    
    def t_auth_jwt_verify_bad_sig():
        token = call_stdlib('auth_jwt_create', [{'user': 'eve'}, 'real_key'], 0)
        try:
            call_stdlib('auth_jwt_verify', [token, 'wrong_key'], 0)
            assert False, "Should fail with wrong key"
        except EPLError:
            pass
    run_case("auth_jwt_verify bad signature", t_auth_jwt_verify_bad_sig)
    
    def t_auth_jwt_decode():
        token = call_stdlib('auth_jwt_create', [{'role': 'admin'}, 'secret'], 0)
        payload = call_stdlib('auth_jwt_decode', [token], 0)
        assert_isinstance(payload, EPLDict)
        assert_eq(payload.data['role'], 'admin')
    run_case("auth_jwt_decode (no verify)", t_auth_jwt_decode)
    
    def t_auth_generate_token():
        t1 = call_stdlib('auth_generate_token', [32], 0)
        t2 = call_stdlib('auth_generate_token', [32], 0)
        assert_isinstance(t1, str)
        assert_true(len(t1) > 10)
        assert_true(t1 != t2)  # randomness
    run_case("auth_generate_token", t_auth_generate_token)
    
    def t_auth_api_key_create():
        r = call_stdlib('auth_api_key_create', ['myapp'], 0)
        assert_isinstance(r, EPLDict)
        key = r.data['key']
        key_hash = r.data['hash']
        assert_true(key.startswith('myapp_'))
        assert_true(len(key_hash) == 64)  # SHA256 hex
    run_case("auth_api_key_create", t_auth_api_key_create)
    
    def t_auth_api_key_verify():
        r = call_stdlib('auth_api_key_create', ['test'], 0)
        key = r.data['key']
        key_hash = r.data['hash']
        assert_true(call_stdlib('auth_api_key_verify', [key, key_hash], 0))
        assert_eq(call_stdlib('auth_api_key_verify', ['wrong_key', key_hash], 0), False)
    run_case("auth_api_key_verify", t_auth_api_key_verify)
    
    def t_auth_basic_decode():
        import base64
        encoded = base64.b64encode(b'admin:password123').decode()
        result = call_stdlib('auth_basic_decode', [f'Basic {encoded}'], 0)
        assert_eq(result, ['admin', 'password123'])
    run_case("auth_basic_decode", t_auth_basic_decode)
    
    def t_auth_jwt_expiry():
        # Create token with very long expiry - should verify fine
        token = call_stdlib('auth_jwt_create', [{'x': 1}, 'key', 9999], 0)
        payload = call_stdlib('auth_jwt_verify', [token, 'key'], 0)
        assert_eq(payload.data['x'], 1)
    run_case("auth_jwt with expiry", t_auth_jwt_expiry)
    
    # ═══════════════════════════════════════════════════════════
    #  4. API HELPERS (8 functions)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 4. API Helpers ===")
    
    def t_api_paginate_basic():
        items = list(range(1, 51))
        r = call_stdlib('api_paginate', [items, 1, 10], 0)
        assert_isinstance(r, EPLDict)
        assert_eq(r.data['page'], 1)
        assert_eq(r.data['per_page'], 10)
        assert_eq(r.data['total'], 50)
        assert_eq(r.data['total_pages'], 5)
        assert_eq(r.data['has_next'], True)
        assert_eq(r.data['has_prev'], False)
        assert_eq(len(r.data['items']), 10)
    run_case("api_paginate basic", t_api_paginate_basic)
    
    def t_api_paginate_last_page():
        items = list(range(1, 51))
        r = call_stdlib('api_paginate', [items, 5, 10], 0)
        assert_eq(r.data['has_next'], False)
        assert_eq(r.data['has_prev'], True)
        assert_eq(r.data['page'], 5)
    run_case("api_paginate last page", t_api_paginate_last_page)
    
    def t_api_validate_valid():
        data = {'name': 'Alice', 'age': 25}
        schema = {'name': {'type': 'string', 'required': True}, 'age': {'type': 'number', 'min': 0}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_isinstance(r, EPLDict)
        assert_eq(r.data['valid'], True)
        assert_eq(r.data['errors'], [])
    run_case("api_validate valid", t_api_validate_valid)
    
    def t_api_validate_missing_required():
        data = {'age': 25}
        schema = {'name': {'type': 'string', 'required': True}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_eq(r.data['valid'], False)
        assert_true(len(r.data['errors']) > 0)
    run_case("api_validate missing required", t_api_validate_missing_required)
    
    def t_api_validate_type_error():
        data = {'age': 'not_a_number'}
        schema = {'age': {'type': 'number'}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_eq(r.data['valid'], False)
    run_case("api_validate type error", t_api_validate_type_error)
    
    def t_api_validate_min_max():
        data = {'score': 150}
        schema = {'score': {'type': 'number', 'min': 0, 'max': 100}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_eq(r.data['valid'], False)
    run_case("api_validate min/max", t_api_validate_min_max)
    
    def t_api_validate_pattern():
        data = {'email': 'not-an-email'}
        schema = {'email': {'type': 'string', 'pattern': r'^[\w.]+@[\w.]+\.\w+$'}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_eq(r.data['valid'], False)
    run_case("api_validate pattern", t_api_validate_pattern)
    
    def t_api_validate_enum():
        data = {'status': 'unknown'}
        schema = {'status': {'type': 'string', 'enum': ['active', 'inactive', 'pending']}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_eq(r.data['valid'], False)
    run_case("api_validate enum", t_api_validate_enum)
    
    def t_api_validate_min_length():
        data = {'password': 'ab'}
        schema = {'password': {'type': 'string', 'min_length': 8}}
        r = call_stdlib('api_validate', [data, schema], 0)
        assert_eq(r.data['valid'], False)
    run_case("api_validate min_length", t_api_validate_min_length)
    
    def t_api_parse_query():
        r = call_stdlib('api_parse_query', ['?name=Alice&age=25'], 0)
        assert_isinstance(r, EPLDict)
        assert_eq(r.data['name'], 'Alice')
        assert_eq(r.data['age'], '25')
    run_case("api_parse_query", t_api_parse_query)
    
    def t_api_link_header():
        r = call_stdlib('api_link_header', ['/api/items', 2, 10, 50], 0)
        assert_isinstance(r, str)
        assert_in('rel="first"', r)
        assert_in('rel="prev"', r)
        assert_in('rel="next"', r)
        assert_in('rel="last"', r)
    run_case("api_link_header", t_api_link_header)
    
    def t_api_link_header_first_page():
        r = call_stdlib('api_link_header', ['/items', 1, 10, 50], 0)
        assert_true('rel="prev"' not in r)
        assert_in('rel="next"', r)
    run_case("api_link_header first page", t_api_link_header_first_page)
    
    def t_api_link_header_last_page():
        r = call_stdlib('api_link_header', ['/items', 5, 10, 50], 0)
        assert_true('rel="next"' not in r)
        assert_in('rel="prev"', r)
    run_case("api_link_header last page", t_api_link_header_last_page)
    
    # ═══════════════════════════════════════════════════════════
    #  5. WEB FRAMEWORK (33 functions — Flask-based)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 5. Web Framework ===")
    
    def t_web_create():
        app_id = call_stdlib('web_create', ['test_app'], 0)
        assert_isinstance(app_id, str)
        assert_true(app_id.startswith('web_'))
    run_case("web_create", t_web_create)
    
    def t_web_route_and_test():
        app_id = call_stdlib('web_create', ['route_test'], 0)
        call_stdlib('web_get', [app_id, '/hello', lambda: 'Hello World'], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/hello'], 0)
        assert_eq(resp.data['status'], 200)
        assert_eq(resp.data['data'], 'Hello World')
    run_case("web_route GET + test_client", t_web_route_and_test)
    
    def t_web_post_route():
        app_id = call_stdlib('web_create', ['post_test'], 0)
        call_stdlib('web_post', [app_id, '/echo', lambda: call_stdlib('web_request_data', [], 0)], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_post', [cid, '/echo', {'msg': 'hi'}], 0)
        assert_eq(resp.data['status'], 200)
        data = _data(resp.data, 'data')
        assert_eq(data['msg'], 'hi')
    run_case("web_post + request_data", t_web_post_route)
    
    def t_web_json_response():
        app_id = call_stdlib('web_create', ['json_test'], 0)
        def handler():
            return call_stdlib('web_json', [{'result': 42}, 200], 0)
        call_stdlib('web_get', [app_id, '/json', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/json'], 0)
        assert_eq(resp.data['status'], 200)
        data = _data(resp.data, 'data')
        assert_eq(data['result'], 42)
    run_case("web_json response", t_web_json_response)
    
    def t_web_html_response():
        app_id = call_stdlib('web_create', ['html_test'], 0)
        def handler():
            return call_stdlib('web_html', ['<h1>Hello</h1>', 200, True], 0)
        call_stdlib('web_get', [app_id, '/page', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/page'], 0)
        assert_eq(resp.data['status'], 200)
        data = resp.data['data'] if isinstance(resp.data['data'], str) else str(resp.data['data'])
        assert_in('<h1>Hello</h1>', data)
    run_case("web_html response", t_web_html_response)
    
    def t_web_redirect():
        app_id = call_stdlib('web_create', ['redir_test'], 0)
        def handler():
            return call_stdlib('web_redirect', ['/destination'], 0)
        call_stdlib('web_get', [app_id, '/go', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/go'], 0)
        assert_eq(resp.data['status'], 302)
    run_case("web_redirect", t_web_redirect)
    
    def t_web_redirect_blocks_external():
        try:
            # We need a request context, but the function itself checks the URL
            call_stdlib('web_redirect', ['https://evil.com'], 0)
            assert False, "Should block external URL"
        except EPLError:
            pass
    run_case("web_redirect blocks external URLs", t_web_redirect_blocks_external)
    
    def t_web_request_args():
        app_id = call_stdlib('web_create', ['args_test'], 0)
        def handler():
            args = call_stdlib('web_request_args', [], 0)
            return call_stdlib('web_json', [args], 0)
        call_stdlib('web_get', [app_id, '/search', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/search?q=hello&page=1'], 0)
        assert_eq(resp.data['status'], 200)
        data = _data(resp.data, 'data')
        assert_eq(data['q'], 'hello')
        assert_eq(data['page'], '1')
    run_case("web_request_args", t_web_request_args)
    
    def t_web_request_method():
        app_id = call_stdlib('web_create', ['method_test'], 0)
        def handler():
            m = call_stdlib('web_request_method', [], 0)
            return m
        call_stdlib('web_get', [app_id, '/method', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/method'], 0)
        assert_eq(resp.data['data'], 'GET')
    run_case("web_request_method", t_web_request_method)
    
    def t_web_request_path():
        app_id = call_stdlib('web_create', ['path_test'], 0)
        def handler():
            return call_stdlib('web_request_path', [], 0)
        call_stdlib('web_get', [app_id, '/mypath', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/mypath'], 0)
        assert_eq(resp.data['data'], '/mypath')
    run_case("web_request_path", t_web_request_path)
    
    def t_web_request_header():
        app_id = call_stdlib('web_create', ['header_test'], 0)
        def handler():
            return call_stdlib('web_request_header', ['X-Custom'], 0)
        call_stdlib('web_get', [app_id, '/hdr', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/hdr', {'X-Custom': 'my-value'}], 0)
        assert_eq(resp.data['data'], 'my-value')
    run_case("web_request_header", t_web_request_header)
    
    def t_web_set_cors():
        app_id = call_stdlib('web_create', ['cors_test'], 0)
        call_stdlib('web_set_cors', [app_id, 'https://example.com'], 0)
        # CORS is applied at start time, not directly testable without starting
        # But we can verify no error occurs
        assert_true(True)
    run_case("web_set_cors", t_web_set_cors)
    
    def t_web_middleware():
        app_id = call_stdlib('web_create', ['mw_test'], 0)
        log = []
        call_stdlib('web_middleware', [app_id, lambda: log.append('mw')], 0)
        call_stdlib('web_get', [app_id, '/mw', lambda: 'ok'], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        call_stdlib('web_test_get', [cid, '/mw'], 0)
        assert_true(len(log) > 0, f"Middleware should have been called, log={log}")
    run_case("web_middleware", t_web_middleware)
    
    def t_web_error_handler():
        app_id = call_stdlib('web_create', ['err_test'], 0)
        call_stdlib('web_error_handler', [app_id, 404, lambda e: 'Custom 404'], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/nonexistent'], 0)
        assert_eq(resp.data['status'], 404)
        assert_in('Custom 404', resp.data['data'])
    run_case("web_error_handler", t_web_error_handler)
    
    def t_web_api_create():
        app_id = call_stdlib('web_api_create', ['my_api'], 0)
        assert_true(app_id.startswith('web_'))
        # Should have default JSON 404 handler
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/missing'], 0)
        assert_eq(resp.data['status'], 404)
        data = _data(resp.data, 'data')
        assert_eq(data['error'], 'Not found')
    run_case("web_api_create", t_web_api_create)
    
    def t_web_api_resource():
        app_id = call_stdlib('web_api_create', ['resource_test'], 0)
        items = [{'id': 1, 'name': 'Widget'}]
        def get_items():
            return call_stdlib('web_json', [items], 0)
        call_stdlib('web_api_resource', [app_id, '/items', get_items], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/items'], 0)
        assert_eq(resp.data['status'], 200)
    run_case("web_api_resource", t_web_api_resource)
    
    def t_web_session():
        app_id = call_stdlib('web_create', ['session_test'], 0)
        def set_session():
            call_stdlib('web_session_set', ['user', 'Alice'], 0)
            return 'set'
        def get_session():
            val = call_stdlib('web_session_get', ['user', 'none'], 0)
            return val
        call_stdlib('web_get', [app_id, '/set', set_session], 0)
        call_stdlib('web_get', [app_id, '/get', get_session], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        call_stdlib('web_test_get', [cid, '/set'], 0)
        resp = call_stdlib('web_test_get', [cid, '/get'], 0)
        assert_eq(resp.data['data'], 'Alice')
    run_case("web_session get/set", t_web_session)
    
    def t_web_session_clear():
        app_id = call_stdlib('web_create', ['session_clear_test'], 0)
        def set_session():
            call_stdlib('web_session_set', ['key', 'value'], 0)
            return 'set'
        def clear_session():
            call_stdlib('web_session_clear', [], 0)
            return 'cleared'
        def get_session():
            return call_stdlib('web_session_get', ['key', 'empty'], 0)
        call_stdlib('web_get', [app_id, '/set', set_session], 0)
        call_stdlib('web_get', [app_id, '/clear', clear_session], 0)
        call_stdlib('web_get', [app_id, '/get', get_session], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        call_stdlib('web_test_get', [cid, '/set'], 0)
        call_stdlib('web_test_get', [cid, '/clear'], 0)
        resp = call_stdlib('web_test_get', [cid, '/get'], 0)
        assert_eq(resp.data['data'], 'empty')
    run_case("web_session_clear", t_web_session_clear)
    
    def t_web_response_custom():
        app_id = call_stdlib('web_create', ['resp_test'], 0)
        def handler():
            return call_stdlib('web_response', ['custom body', 201, {'X-Custom': 'yes'}, 'text/plain'], 0)
        call_stdlib('web_get', [app_id, '/custom', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/custom'], 0)
        assert_eq(resp.data['status'], 201)
        assert_eq(resp.data['data'], 'custom body')
    run_case("web_response custom", t_web_response_custom)
    
    def t_web_put_delete():
        app_id = call_stdlib('web_create', ['put_del_test'], 0)
        call_stdlib('web_put', [app_id, '/item', lambda: 'updated'], 0)
        call_stdlib('web_delete', [app_id, '/item', lambda: 'deleted'], 0)
        # Verify routes were registered (no error)
        assert_true(True)
    run_case("web_put + web_delete routes", t_web_put_delete)
    
    def t_web_upload_config():
        app_id = call_stdlib('web_create', ['upload_test'], 0)
        tmpdir = tempfile.mkdtemp()
        try:
            r = call_stdlib('web_upload_config', [app_id, tmpdir, 5 * 1024 * 1024], 0)
            assert_true(r)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    run_case("web_upload_config", t_web_upload_config)
    
    def t_web_url_params():
        app_id = call_stdlib('web_create', ['params_test'], 0)
        def handler(user_id):
            return f'User: {user_id}'
        call_stdlib('web_get', [app_id, '/users/<user_id>', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/users/42'], 0)
        assert_eq(resp.data['status'], 200)
        assert_eq(resp.data['data'], 'User: 42')
    run_case("web URL params", t_web_url_params)
    
    def t_web_bearer_token():
        app_id = call_stdlib('web_create', ['bearer_test'], 0)
        def handler():
            return call_stdlib('auth_bearer_token', [], 0)
        call_stdlib('web_get', [app_id, '/auth', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/auth', {'Authorization': 'Bearer my_token_123'}], 0)
        assert_eq(resp.data['data'], 'my_token_123')
    run_case("auth_bearer_token in request", t_web_bearer_token)
    
    def t_web_api_error_response():
        app_id = call_stdlib('web_create', ['api_err_test'], 0)
        def handler():
            return call_stdlib('api_error', ['Not found', 404], 0)
        call_stdlib('web_get', [app_id, '/err', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/err'], 0)
        assert_eq(resp.data['status'], 404)
        data = _data(resp.data, 'data')
        assert_eq(data['error'], True)
        assert_eq(data['message'], 'Not found')
    run_case("api_error in web context", t_web_api_error_response)
    
    def t_web_api_success_response():
        app_id = call_stdlib('web_create', ['api_succ_test'], 0)
        def handler():
            return call_stdlib('api_success', [{'items': [1, 2, 3]}, 'Fetched'], 0)
        call_stdlib('web_get', [app_id, '/ok', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/ok'], 0)
        assert_eq(resp.data['status'], 200)
        data = _data(resp.data, 'data')
        assert_eq(data['success'], True)
        assert_eq(data['message'], 'Fetched')
    run_case("api_success in web context", t_web_api_success_response)
    
    def t_web_api_version():
        app_id = call_stdlib('web_create', ['version_test'], 0)
        path = call_stdlib('api_version', [app_id, 'v1'], 0)
        assert_eq(path, '/api/v1')
    run_case("api_version", t_web_api_version)
    
    # ═══════════════════════════════════════════════════════════
    #  6. WEBSOCKET SERVER (12 functions)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 6. WebSocket Server ===")
    
    def t_ws_server_create():
        sid = call_stdlib('ws_server_create', [9100], 0)
        assert_isinstance(sid, str)
        assert_true(sid.startswith('wss_'))
    run_case("ws_server_create", t_ws_server_create)
    
    def t_ws_on_connect():
        sid = call_stdlib('ws_server_create', [9101], 0)
        r = call_stdlib('ws_on_connect', [sid, lambda cid: None], 0)
        assert_true(r)
    run_case("ws_on_connect", t_ws_on_connect)
    
    def t_ws_on_message():
        sid = call_stdlib('ws_server_create', [9102], 0)
        r = call_stdlib('ws_on_message', [sid, lambda cid, msg: None], 0)
        assert_true(r)
    run_case("ws_on_message", t_ws_on_message)
    
    def t_ws_on_disconnect():
        sid = call_stdlib('ws_server_create', [9103], 0)
        r = call_stdlib('ws_on_disconnect', [sid, lambda cid: None], 0)
        assert_true(r)
    run_case("ws_on_disconnect", t_ws_on_disconnect)
    
    def t_ws_clients_empty():
        sid = call_stdlib('ws_server_create', [9104], 0)
        clients = call_stdlib('ws_clients', [sid], 0)
        assert_isinstance(clients, list)
        assert_eq(len(clients), 0)
    run_case("ws_clients empty", t_ws_clients_empty)
    
    def t_ws_room_join():
        sid = call_stdlib('ws_server_create', [9105], 0)
        r = call_stdlib('ws_room_join', [sid, 'client1', 'lobby'], 0)
        assert_true(r)
    run_case("ws_room_join", t_ws_room_join)
    
    def t_ws_room_leave():
        sid = call_stdlib('ws_server_create', [9106], 0)
        call_stdlib('ws_room_join', [sid, 'c1', 'room1'], 0)
        r = call_stdlib('ws_room_leave', [sid, 'c1', 'room1'], 0)
        assert_true(r)
    run_case("ws_room_leave", t_ws_room_leave)
    
    def t_ws_broadcast_no_clients():
        sid = call_stdlib('ws_server_create', [9107], 0)
        count = call_stdlib('ws_broadcast', [sid, 'hello'], 0)
        assert_eq(count, 0)
    run_case("ws_broadcast no clients", t_ws_broadcast_no_clients)
    
    def t_ws_room_broadcast_no_members():
        sid = call_stdlib('ws_server_create', [9108], 0)
        count = call_stdlib('ws_room_broadcast', [sid, 'empty_room', 'msg'], 0)
        assert_eq(count, 0)
    run_case("ws_room_broadcast no members", t_ws_room_broadcast_no_members)
    
    def t_ws_server_stop():
        sid = call_stdlib('ws_server_create', [9109], 0)
        # Stop without starting — should handle gracefully
        r = call_stdlib('ws_server_stop', [sid], 0)
        assert_true(r is True or r is False or r is None)
    run_case("ws_server_stop", t_ws_server_stop)
    
    def t_ws_send_to_invalid():
        sid = call_stdlib('ws_server_create', [9110], 0)
        try:
            call_stdlib('ws_send_to', [sid, 'nonexistent', 'msg'], 0)
            assert False, "Should fail for unknown client"
        except EPLError:
            pass
    run_case("ws_send_to unknown client", t_ws_send_to_invalid)
    
    # ═══════════════════════════════════════════════════════════
    #  7. ORM EXTENSIONS (10 functions + 18 core ORM)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 7. ORM/Database ===")
    
    def t_orm_open_close():
        db_id = call_stdlib('orm_open', ['sqlite', ':memory:'], 0)
        assert_isinstance(db_id, str)
        assert_true(db_id.startswith('orm_'))
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_open + orm_close", t_orm_open_close)
    
    def _setup_db():
        """Helper: create in-memory DB with users table."""
        db_id = call_stdlib('orm_open', ['sqlite', ':memory:'], 0)
        model = call_stdlib('orm_define_model', [db_id, 'user'], 0)
        call_stdlib('orm_add_field', [model, 'name', 'TEXT'], 0)
        call_stdlib('orm_add_field', [model, 'age', 'INTEGER'], 0)
        call_stdlib('orm_add_field', [model, 'email', 'TEXT'], 0)
        call_stdlib('orm_migrate', [db_id], 0)
        return db_id
    
    def t_orm_define_migrate():
        db_id = _setup_db()
        assert_true(call_stdlib('orm_table_exists', [db_id, 'users'], 0))
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_define_model + migrate", t_orm_define_migrate)
    
    def t_orm_create_find():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'Alice', 'age': 30, 'email': 'a@x.com'}], 0)
        call_stdlib('orm_create', [db_id, 'user', {'name': 'Bob', 'age': 25, 'email': 'b@x.com'}], 0)
        results = call_stdlib('orm_find', [db_id, 'user'], 0)
        assert_eq(len(results), 2)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_create + orm_find", t_orm_create_find)
    
    def t_orm_find_by_id():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'Carol', 'age': 28, 'email': 'c@x.com'}], 0)
        record = call_stdlib('orm_find_by_id', [db_id, 'user', 1], 0)
        assert_true(record is not None)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_find_by_id", t_orm_find_by_id)
    
    def t_orm_update():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'Dave', 'age': 35, 'email': 'd@x.com'}], 0)
        call_stdlib('orm_update', [db_id, 'user', 1, {'age': 36}], 0)
        record = call_stdlib('orm_find_by_id', [db_id, 'user', 1], 0)
        # record might be a dict or EPLDict
        age = record.get('age') if isinstance(record, dict) else record.data.get('age', record.get('age') if hasattr(record, 'get') else None)
        assert_eq(age, 36)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_update", t_orm_update)
    
    def t_orm_delete():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'Eve', 'age': 22, 'email': 'e@x.com'}], 0)
        call_stdlib('orm_delete', [db_id, 'user', 1], 0)
        results = call_stdlib('orm_find', [db_id, 'user'], 0)
        assert_eq(len(results), 0)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_delete", t_orm_delete)
    
    def t_orm_delete_where():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'F1', 'age': 20, 'email': 'f1@x.com'}], 0)
        call_stdlib('orm_create', [db_id, 'user', {'name': 'F2', 'age': 20, 'email': 'f2@x.com'}], 0)
        call_stdlib('orm_create', [db_id, 'user', {'name': 'F3', 'age': 30, 'email': 'f3@x.com'}], 0)
        count = call_stdlib('orm_delete_where', [db_id, 'user', {'age': 20}], 0)
        remaining = call_stdlib('orm_find', [db_id, 'user'], 0)
        assert_eq(len(remaining), 1)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_delete_where", t_orm_delete_where)
    
    def t_orm_raw_query():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'Raw', 'age': 40, 'email': 'r@x.com'}], 0)
        results = call_stdlib('orm_raw_query', [db_id, 'SELECT * FROM users WHERE age = ?', [40]], 0)
        assert_true(len(results) >= 1)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_raw_query", t_orm_raw_query)
    
    def t_orm_table_exists():
        db_id = _setup_db()
        assert_true(call_stdlib('orm_table_exists', [db_id, 'users'], 0))
        assert_eq(call_stdlib('orm_table_exists', [db_id, 'nonexistent'], 0), False)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_table_exists", t_orm_table_exists)
    
    def t_orm_seed():
        db_id = _setup_db()
        data = [
            {'name': 'S1', 'age': 21, 'email': 's1@x.com'},
            {'name': 'S2', 'age': 22, 'email': 's2@x.com'},
            {'name': 'S3', 'age': 23, 'email': 's3@x.com'},
        ]
        count = call_stdlib('orm_seed', [db_id, 'user', data], 0)
        assert_eq(count, 3)
        results = call_stdlib('orm_find', [db_id, 'user'], 0)
        assert_eq(len(results), 3)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_seed", t_orm_seed)
    
    def t_orm_count_where():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'A', 'age': 20, 'email': 'a@x'},
            {'name': 'B', 'age': 20, 'email': 'b@x'},
            {'name': 'C', 'age': 30, 'email': 'c@x'},
        ]], 0)
        count = call_stdlib('orm_count_where', [db_id, 'user', {'age': 20}], 0)
        assert_eq(count, 2)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_count_where", t_orm_count_where)
    
    def t_orm_first():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'First', 'age': 10, 'email': 'f@x'},
            {'name': 'Second', 'age': 20, 'email': 's@x'},
        ]], 0)
        first = call_stdlib('orm_first', [db_id, 'user'], 0)
        assert_true(first is not None)
        name = first.data['name'] if isinstance(first, EPLDict) else first['name']
        assert_eq(name, 'First')
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_first", t_orm_first)
    
    def t_orm_last():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'First', 'age': 10, 'email': 'f@x'},
            {'name': 'Last', 'age': 99, 'email': 'l@x'},
        ]], 0)
        last = call_stdlib('orm_last', [db_id, 'user'], 0)
        assert_true(last is not None)
        name = last.data['name'] if isinstance(last, EPLDict) else last['name']
        assert_eq(name, 'Last')
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_last", t_orm_last)
    
    def t_orm_order_by():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'Zoe', 'age': 30, 'email': 'z@x'},
            {'name': 'Amy', 'age': 20, 'email': 'a@x'},
            {'name': 'Max', 'age': 25, 'email': 'm@x'},
        ]], 0)
        results = call_stdlib('orm_order_by', [db_id, 'user', 'age', 'ASC'], 0)
        ages = [r.data['age'] if isinstance(r, EPLDict) else r['age'] for r in results]
        assert_eq(ages, [20, 25, 30])
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_order_by ASC", t_orm_order_by)
    
    def t_orm_order_by_desc():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'A', 'age': 10, 'email': 'a@x'},
            {'name': 'B', 'age': 30, 'email': 'b@x'},
            {'name': 'C', 'age': 20, 'email': 'c@x'},
        ]], 0)
        results = call_stdlib('orm_order_by', [db_id, 'user', 'age', 'DESC'], 0)
        ages = [r.data['age'] if isinstance(r, EPLDict) else r['age'] for r in results]
        assert_eq(ages, [30, 20, 10])
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_order_by DESC", t_orm_order_by_desc)
    
    def t_orm_paginate():
        db_id = _setup_db()
        for i in range(25):
            call_stdlib('orm_create', [db_id, 'user', {'name': f'U{i}', 'age': i, 'email': f'u{i}@x'}], 0)
        r = call_stdlib('orm_paginate', [db_id, 'user', 2, 10], 0)
        assert_isinstance(r, EPLDict)
        assert_eq(r.data['page'], 2)
        assert_eq(r.data['per_page'], 10)
        assert_eq(r.data['total'], 25)
        assert_eq(r.data['total_pages'], 3)
        assert_eq(r.data['has_next'], True)
        assert_eq(r.data['has_prev'], True)
        assert_eq(len(r.data['items']), 10)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_paginate", t_orm_paginate)
    
    def t_orm_add_index():
        db_id = _setup_db()
        r = call_stdlib('orm_add_index', [db_id, 'user', ['name', 'email']], 0)
        assert_true(r)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_add_index", t_orm_add_index)
    
    def t_orm_has_many_belongs_to():
        db_id = call_stdlib('orm_open', ['sqlite', ':memory:'], 0)
        # Define Author model
        author_model = call_stdlib('orm_define_model', [db_id, 'author'], 0)
        call_stdlib('orm_add_field', [author_model, 'name', 'TEXT'], 0)
        # Define Book model
        book_model = call_stdlib('orm_define_model', [db_id, 'book'], 0)
        call_stdlib('orm_add_field', [book_model, 'title', 'TEXT'], 0)
        call_stdlib('orm_add_field', [book_model, 'author_id', 'INTEGER'], 0)
        call_stdlib('orm_migrate', [db_id], 0)
        # Set up relationships
        call_stdlib('orm_has_many', [db_id, 'author', 'book', 'author_id'], 0)
        call_stdlib('orm_belongs_to', [db_id, 'book', 'author', 'author_id'], 0)
        # Insert data
        call_stdlib('orm_create', [db_id, 'author', {'name': 'Tolkien'}], 0)
        call_stdlib('orm_create', [db_id, 'book', {'title': 'The Hobbit', 'author_id': 1}], 0)
        call_stdlib('orm_create', [db_id, 'book', {'title': 'LOTR', 'author_id': 1}], 0)
        # Test has_many (author with books)
        result = call_stdlib('orm_with_related', [db_id, 'author', 1, 'book'], 0)
        assert_isinstance(result, EPLDict)
        assert_eq(result.data['name'], 'Tolkien')
        books = result.data['book']
        assert_eq(len(books), 2)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_has_many + orm_belongs_to + orm_with_related", t_orm_has_many_belongs_to)
    
    def t_orm_with_related_belongs_to():
        db_id = call_stdlib('orm_open', ['sqlite', ':memory:'], 0)
        author_model = call_stdlib('orm_define_model', [db_id, 'author'], 0)
        call_stdlib('orm_add_field', [author_model, 'name', 'TEXT'], 0)
        book_model = call_stdlib('orm_define_model', [db_id, 'book'], 0)
        call_stdlib('orm_add_field', [book_model, 'title', 'TEXT'], 0)
        call_stdlib('orm_add_field', [book_model, 'author_id', 'INTEGER'], 0)
        call_stdlib('orm_migrate', [db_id], 0)
        call_stdlib('orm_belongs_to', [db_id, 'book', 'author', 'author_id'], 0)
        call_stdlib('orm_create', [db_id, 'author', {'name': 'Rowling'}], 0)
        call_stdlib('orm_create', [db_id, 'book', {'title': 'HP', 'author_id': 1}], 0)
        result = call_stdlib('orm_with_related', [db_id, 'book', 1, 'author'], 0)
        assert_isinstance(result, EPLDict)
        assert_eq(result.data['title'], 'HP')
        assert_true(result.data.get('author') is not None)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_with_related belongs_to", t_orm_with_related_belongs_to)
    
    def t_orm_find_with_conditions():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'X', 'age': 20, 'email': 'x@x'},
            {'name': 'Y', 'age': 30, 'email': 'y@x'},
            {'name': 'Z', 'age': 20, 'email': 'z@x'},
        ]], 0)
        results = call_stdlib('orm_find', [db_id, 'user', {'age': 20}], 0)
        assert_eq(len(results), 2)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_find with conditions", t_orm_find_with_conditions)
    
    def t_orm_transaction():
        db_id = _setup_db()
        call_stdlib('orm_create', [db_id, 'user', {'name': 'T1', 'age': 10, 'email': 't@x'}], 0)
        # Start transaction
        txn_id = call_stdlib('orm_transaction_begin', [db_id], 0)
        assert_isinstance(txn_id, str)
        # Commit
        call_stdlib('orm_transaction_commit', [txn_id], 0)
        results = call_stdlib('orm_find', [db_id, 'user'], 0)
        assert_true(len(results) >= 1)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_transaction begin/commit", t_orm_transaction)
    
    def t_orm_first_with_conditions():
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'AA', 'age': 50, 'email': 'aa@x'},
            {'name': 'BB', 'age': 60, 'email': 'bb@x'},
        ]], 0)
        first = call_stdlib('orm_first', [db_id, 'user', {'age': 60}], 0)
        name = first.data['name'] if isinstance(first, EPLDict) else first['name']
        assert_eq(name, 'BB')
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm_first with conditions", t_orm_first_with_conditions)
    
    # ═══════════════════════════════════════════════════════════
    #  8. INTEGRATION TESTS (cross-module)
    # ═══════════════════════════════════════════════════════════
    print("\n=== 8. Integration Tests ===")
    
    def t_web_with_template():
        """Web + Template: serve rendered template via web route."""
        call_stdlib('template_create', ['page', '<h1>{{ title }}</h1><p>{{ body }}</p>'], 0)
        app_id = call_stdlib('web_create', ['tmpl_test'], 0)
        def handler():
            rendered = call_stdlib('template_render', ['page', {'title': 'Home', 'body': 'Welcome'}], 0)
            return call_stdlib('web_html', [rendered, 200, True], 0)
        call_stdlib('web_get', [app_id, '/', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/'], 0)
        assert_eq(resp.data['status'], 200)
        data = resp.data['data'] if isinstance(resp.data['data'], str) else str(resp.data['data'])
        assert_in('<h1>Home</h1>', data)
        assert_in('<p>Welcome</p>', data)
    run_case("web + template integration", t_web_with_template)
    
    def t_web_with_html_builder():
        """Web + HTML Builder: generate HTML via builder functions."""
        app_id = call_stdlib('web_create', ['html_build_test'], 0)
        def handler():
            body = call_stdlib('html_element', ['h1', 'Hello'], 0)
            body += call_stdlib('html_list', [['Item 1', 'Item 2']], 0)
            page = call_stdlib('html_page', ['Test', body], 0)
            return call_stdlib('web_html', [page, 200, True], 0)
        call_stdlib('web_get', [app_id, '/', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/'], 0)
        assert_eq(resp.data['status'], 200)
        data = resp.data['data'] if isinstance(resp.data['data'], str) else str(resp.data['data'])
        assert_in('<!DOCTYPE html>', data)
        assert_in('<h1>Hello</h1>', data)
    run_case("web + html builder integration", t_web_with_html_builder)
    
    def t_web_with_auth_jwt():
        """Web + Auth: JWT auth flow."""
        app_id = call_stdlib('web_create', ['jwt_test'], 0)
        SECRET = 'test_secret_key'
        def login():
            token = call_stdlib('auth_jwt_create', [{'user': 'admin'}, SECRET, 3600], 0)
            return call_stdlib('web_json', [{'token': token}], 0)
        def protected():
            token = call_stdlib('auth_bearer_token', [], 0)
            if not token:
                return call_stdlib('api_error', ['No token', 401], 0)
            try:
                payload = call_stdlib('auth_jwt_verify', [token, SECRET], 0)
                return call_stdlib('web_json', [{'user': payload.data['user']}], 0)
            except:
                return call_stdlib('api_error', ['Invalid token', 401], 0)
        call_stdlib('web_get', [app_id, '/login', login], 0)
        call_stdlib('web_get', [app_id, '/protected', protected], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        # Step 1: Login to get token
        login_resp = call_stdlib('web_test_get', [cid, '/login'], 0)
        login_data = _data(login_resp.data, 'data')
        token = login_data['token']
        # Step 2: Access protected route
        resp = call_stdlib('web_test_get', [cid, '/protected', {'Authorization': f'Bearer {token}'}], 0)
        assert_eq(resp.data['status'], 200)
        resp_data = _data(resp.data, 'data')
        assert_eq(resp_data['user'], 'admin')
    run_case("web + auth JWT flow", t_web_with_auth_jwt)
    
    def t_web_with_validation():
        """Web + API: validate incoming data."""
        app_id = call_stdlib('web_create', ['validate_test'], 0)
        schema = {'name': {'type': 'string', 'required': True, 'min_length': 2},
                  'age': {'type': 'number', 'min': 0, 'max': 150}}
        def handler():
            data = call_stdlib('web_request_data', [], 0)
            # Convert EPLDict to plain dict for validation
            if isinstance(data, EPLDict):
                from epl.stdlib import _from_epl
                data = _from_epl(data)
            result = call_stdlib('api_validate', [data, schema], 0)
            if result.data['valid']:
                return call_stdlib('api_success', [data, 'Valid'], 0)
            else:
                return call_stdlib('api_error', ['Validation failed', 400, {'errors': result.data['errors']}], 0)
        call_stdlib('web_post', [app_id, '/validate', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        # Valid data
        resp = call_stdlib('web_test_post', [cid, '/validate', {'name': 'Alice', 'age': 25}], 0)
        assert_eq(resp.data['status'], 200)
        data = _data(resp.data, 'data')
        assert_eq(data['success'], True)
        # Invalid data
        resp2 = call_stdlib('web_test_post', [cid, '/validate', {'name': 'A', 'age': 200}], 0)
        assert_eq(resp2.data['status'], 400)
    run_case("web + validation integration", t_web_with_validation)
    
    def t_orm_with_web():
        """ORM + Web: CRUD API backed by database."""
        db_id = _setup_db()
        call_stdlib('orm_seed', [db_id, 'user', [
            {'name': 'Alice', 'age': 30, 'email': 'a@x'},
            {'name': 'Bob', 'age': 25, 'email': 'b@x'},
        ]], 0)
        app_id = call_stdlib('web_api_create', ['orm_api_test'], 0)
        def get_users():
            users = call_stdlib('orm_find', [db_id, 'user'], 0)
            return call_stdlib('web_json', [users], 0)
        call_stdlib('web_get', [app_id, '/users', get_users], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/users'], 0)
        assert_eq(resp.data['status'], 200)
        call_stdlib('orm_close', [db_id], 0)
    run_case("orm + web CRUD integration", t_orm_with_web)
    
    def t_fullstack_html_template_web():
        """Full-stack: template + html builder + web."""
        call_stdlib('template_create', ['layout', '<!DOCTYPE html><html><body>{{ content|safe }}</body></html>'], 0)
        app_id = call_stdlib('web_create', ['fullstack_test'], 0)
        def handler():
            table = call_stdlib('html_table', [['Name', 'Score'], [['Alice', '95'], ['Bob', '87']]], 0)
            page = call_stdlib('template_render', ['layout', {'content': table}], 0)
            return call_stdlib('web_html', [page, 200, True], 0)
        call_stdlib('web_get', [app_id, '/', handler], 0)
        cid = call_stdlib('web_test_client', [app_id], 0)
        resp = call_stdlib('web_test_get', [cid, '/'], 0)
        assert_eq(resp.data['status'], 200)
        data = resp.data['data'] if isinstance(resp.data['data'], str) else str(resp.data['data'])
        assert_in('<table>', data)
        assert_in('Alice', data)
    run_case("fullstack html+template+web", t_fullstack_html_template_web)
    
    # ═══════════════════════════════════════════════════════════
    #  SUMMARY
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'=' * 55}")
    print(f"Phase 3 Web & Networking: {PASSED} passed, {FAILED} failed")
    print(f"{'=' * 55}")
    return FAILED == 0


def test_phase3_web_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Phase 3 web suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
    
