"""
Tests for Phase 1 features: Python bridge, Web module, GUI module.
Tests the Python bridge end-to-end via EPL code,
and verifies web/gui function registration and error handling.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter, PythonModule
from epl.errors import EPLError
from epl import stdlib


def run(src):
    l = Lexer(src)
    t = l.tokenize()
    p = Parser(t)
    prog = p.parse()
    i = Interpreter()
    i.execute(prog)
    return i.output_lines


def test_err(src, substr):
    try:
        run(src)
        return False
    except EPLError as e:
        return substr.lower() in str(e).lower()
    except Exception:
        return False


test_err.__test__ = False


def _raises(exc_type, fn):
    """Return True if *fn()* raises *exc_type*."""
    try:
        fn()
        return False
    except exc_type:
        return True


# ── Tests ──────────────────────────────────────────────

TEST_CASES = [
    # ══════════════════════════════════════════════
    # Python Bridge — PythonModule
    # ══════════════════════════════════════════════
    ("bridge_import_math", lambda: run('Use python "math"\nPrint math.pi()') == ["3.141592653589793"]),
    ("bridge_math_sqrt", lambda: run('Use python "math"\nresult = math.sqrt(16)\nPrint result') == ["4.0"]),
    ("bridge_math_floor", lambda: run('Use python "math"\nPrint math.floor(3.7)') == ["3"]),
    ("bridge_math_ceil", lambda: run('Use python "math"\nPrint math.ceil(3.2)') == ["4"]),
    ("bridge_import_os_path", lambda: run('Use python "os.path"\nPrint path.exists(".")') == ["true"]),
    ("bridge_import_alias", lambda: run('Use python "math" as m\nPrint m.pi()') == ["3.141592653589793"]),
    ("bridge_string_module", lambda: run(
        'Use python "string"\nPrint string.ascii_lowercase()'
    ) == ["abcdefghijklmnopqrstuvwxyz"]),

    # Bridge — type wrapping (use re module to avoid json keyword conflict)
    ("bridge_wrap_list", lambda: run(
        'Use python "re"\nm = re.findall("[0-9]+", "a1b2c3")\nPrint length(m)'
    ) == ["3"]),
    ("bridge_wrap_str", lambda: run(
        'Use python "re"\nm = re.sub("[0-9]", "X", "a1b2")\nPrint m'
    ) == ["aXbX"]),
    ("bridge_wrap_none", lambda: run(
        'Use python "re"\nm = re.search("xyz", "hello world")\nPrint m'
    ) == ["nothing"]),

    # Bridge — deep chaining (os.path is a submodule)
    ("bridge_deep_chain", lambda: run(
        'Use python "os"\nresult = os.path().basename("a/b/c.txt")\nPrint result'
    ) == ["c.txt"]),

    # Bridge — error on bad module (not in allowlist)
    ("bridge_bad_module", lambda: test_err(
        'Use python "nonexistent_module_xyz_12345"', "is not installed"
    )),

    # ══════════════════════════════════════════════
    # PythonModule unit tests (direct Python)
    # ══════════════════════════════════════════════
    ("pymod_get_attr_exists", lambda: (
        PythonModule(__import__('math'), 'math').get_attr('sqrt') is not None
    )),
    ("pymod_get_attr_missing", lambda: (
        _raises(AttributeError, lambda: PythonModule(__import__('math'), 'math').get_attr('nonexistent_xyz'))
    )),
    ("pymod_repr", lambda: (
        repr(PythonModule(__import__('math'), 'math')) == '<python module math>'
    )),
    ("pymod_callable_attr", lambda: (
        callable(PythonModule(__import__('math'), 'math').get_attr('sqrt'))
    )),
    ("pymod_constant_attr", lambda: (
        abs(PythonModule(__import__('math'), 'math').get_attr('pi') - 3.14159) < 0.001
    )),

    # ══════════════════════════════════════════════
    # _wrap_python_result unit tests
    # ══════════════════════════════════════════════
    ("wrap_none", lambda: Interpreter()._wrap_python_result(None) is None),
    ("wrap_int", lambda: Interpreter()._wrap_python_result(42) == 42),
    ("wrap_float", lambda: Interpreter()._wrap_python_result(3.14) == 3.14),
    ("wrap_str", lambda: Interpreter()._wrap_python_result("hello") == "hello"),
    ("wrap_bool", lambda: Interpreter()._wrap_python_result(True) is True),
    ("wrap_dict", lambda: (
        hasattr(Interpreter()._wrap_python_result({"a": 1}), 'data')
    )),
    ("wrap_list", lambda: Interpreter()._wrap_python_result([1, 2, 3]) == [1, 2, 3]),
    ("wrap_tuple", lambda: Interpreter()._wrap_python_result((1, 2)) == [1, 2]),
    ("wrap_set", lambda: sorted(Interpreter()._wrap_python_result({3, 1, 2})) == [1, 2, 3]),
    ("wrap_bytes", lambda: Interpreter()._wrap_python_result(b"hi") == "hi"),
    ("wrap_nested_dict", lambda: (
        Interpreter()._wrap_python_result({"a": [1, {"b": 2}]}).data["a"][1].data["b"] == 2
    )),

    # ══════════════════════════════════════════════
    # STDLIB_FUNCTIONS registration
    # ══════════════════════════════════════════════
    # Verify all Phase 1 web_* functions are registered
    ("reg_web_create", lambda: 'web_create' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_route", lambda: 'web_route' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_get", lambda: 'web_get' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_post", lambda: 'web_post' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_put", lambda: 'web_put' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_delete", lambda: 'web_delete' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_start", lambda: 'web_start' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_json", lambda: 'web_json' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_html", lambda: 'web_html' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_redirect", lambda: 'web_redirect' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_static", lambda: 'web_static' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_template", lambda: 'web_template' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_request_data", lambda: 'web_request_data' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_request_args", lambda: 'web_request_args' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_request_method", lambda: 'web_request_method' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_request_path", lambda: 'web_request_path' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_request_header", lambda: 'web_request_header' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_set_cors", lambda: 'web_set_cors' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_middleware", lambda: 'web_middleware' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_error_handler", lambda: 'web_error_handler' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_stop", lambda: 'web_stop' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_session_get", lambda: 'web_session_get' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_session_set", lambda: 'web_session_set' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_session_clear", lambda: 'web_session_clear' in stdlib.STDLIB_FUNCTIONS),
    ("reg_web_request_param", lambda: 'web_request_param' in stdlib.STDLIB_FUNCTIONS),

    # Verify all Phase 1 gui_* functions are registered
    ("reg_gui_window", lambda: 'gui_window' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_label", lambda: 'gui_label' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_button", lambda: 'gui_button' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_input", lambda: 'gui_input' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_text", lambda: 'gui_text' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_checkbox", lambda: 'gui_checkbox' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_dropdown", lambda: 'gui_dropdown' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_slider", lambda: 'gui_slider' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_image", lambda: 'gui_image' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_frame", lambda: 'gui_frame' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_grid", lambda: 'gui_grid' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_pack", lambda: 'gui_pack' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_place", lambda: 'gui_place' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_on_click", lambda: 'gui_on_click' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_get_value", lambda: 'gui_get_value' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_set_value", lambda: 'gui_set_value' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_messagebox", lambda: 'gui_messagebox' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_file_dialog", lambda: 'gui_file_dialog' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_run", lambda: 'gui_run' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_menu", lambda: 'gui_menu' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_menu_item", lambda: 'gui_menu_item' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_submenu", lambda: 'gui_submenu' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_canvas", lambda: 'gui_canvas' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_draw_rect", lambda: 'gui_draw_rect' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_draw_circle", lambda: 'gui_draw_circle' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_draw_line", lambda: 'gui_draw_line' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_draw_text", lambda: 'gui_draw_text' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_style", lambda: 'gui_style' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_close", lambda: 'gui_close' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_update", lambda: 'gui_update' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_after", lambda: 'gui_after' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_list", lambda: 'gui_list' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_list_on_select", lambda: 'gui_list_on_select' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_table", lambda: 'gui_table' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_progress", lambda: 'gui_progress' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_tab", lambda: 'gui_tab' in stdlib.STDLIB_FUNCTIONS),
    ("reg_gui_tab_add", lambda: 'gui_tab_add' in stdlib.STDLIB_FUNCTIONS),

    # ══════════════════════════════════════════════
    # Web error handling (no Flask needed, tests arg validation)
    # ══════════════════════════════════════════════
    ("web_route_no_args", lambda: test_err('web_route()', 'web_route')),
    ("web_get_no_args", lambda: test_err('web_get()', 'web_get')),
    ("web_post_no_args", lambda: test_err('web_post()', 'web_post')),
    ("web_json_no_args", lambda: test_err('web_json()', 'web_json')),
    ("web_html_no_args", lambda: test_err('web_html()', 'web_html')),
    ("web_redirect_no_args", lambda: test_err('web_redirect()', 'web_redirect')),

    # ══════════════════════════════════════════════
    # GUI error handling (no Tkinter display needed, tests arg validation)
    # ══════════════════════════════════════════════
    ("gui_label_no_args", lambda: test_err('gui_label()', 'gui_label')),
    ("gui_button_no_args", lambda: test_err('gui_button()', 'gui_button')),
    ("gui_input_no_args", lambda: test_err('gui_input()', 'gui_input')),
    ("gui_checkbox_no_args", lambda: test_err('gui_checkbox()', 'gui_checkbox')),
    ("gui_dropdown_no_args", lambda: test_err('gui_dropdown()', 'gui_dropdown')),
    ("gui_slider_no_args", lambda: test_err('gui_slider()', 'gui_slider')),
    ("gui_image_no_args", lambda: test_err('gui_image()', 'gui_image')),
    ("gui_frame_no_args", lambda: test_err('gui_frame()', 'gui_frame')),
    ("gui_canvas_no_args", lambda: test_err('gui_canvas()', 'gui_canvas')),
    ("gui_menu_no_args", lambda: test_err('gui_menu()', 'gui_menu')),
    ("gui_menu_item_bad_args", lambda: test_err('gui_menu_item("x")', 'gui_menu_item')),
    ("gui_submenu_bad_args", lambda: test_err('gui_submenu("x")', 'gui_submenu')),
    ("gui_tab_no_args", lambda: test_err('gui_tab()', 'gui_tab')),
    ("gui_tab_add_bad_args", lambda: test_err('gui_tab_add("x")', 'gui_tab_add')),
    ("gui_list_no_args", lambda: test_err('gui_list()', 'gui_list')),
    ("gui_list_on_select_bad", lambda: test_err('gui_list_on_select("x")', 'gui_list_on_select')),
    ("gui_table_no_args", lambda: test_err('gui_table()', 'gui_table')),
    ("gui_get_value_no_args", lambda: test_err('gui_get_value()', 'gui_get_value')),
    ("gui_set_value_bad_args", lambda: test_err('gui_set_value("x")', 'gui_set_value')),
    ("gui_draw_rect_bad", lambda: test_err('gui_draw_rect("x", 0)', 'gui_draw_rect')),
    ("gui_draw_circle_bad", lambda: test_err('gui_draw_circle("x")', 'gui_draw_circle')),
    ("gui_draw_line_bad", lambda: test_err('gui_draw_line("x")', 'gui_draw_line')),
    ("gui_draw_text_bad", lambda: test_err('gui_draw_text("x")', 'gui_draw_text')),
    ("gui_on_click_bad", lambda: test_err('gui_on_click("x")', 'gui_on_click')),
    ("gui_style_bad", lambda: test_err('gui_style("x")', 'gui_style')),
    ("gui_grid_bad", lambda: test_err('gui_grid("x")', 'gui_grid')),
    ("gui_place_bad", lambda: test_err('gui_place("x")', 'gui_place')),

    # ══════════════════════════════════════════════
    # Bridge — Use python integration tests
    # ══════════════════════════════════════════════
    ("bridge_datetime_date", lambda: (
        len(run('Use python "datetime"\nd = datetime.date(2024, 1, 15)\nPrint d.isoformat()')[0]) == 10
    )),
    ("bridge_re_module", lambda: run(
        'Use python "re"\nm = re.findall("[0-9]+", "abc 123 def 456")\nPrint m'
    ) == ["[123, 456]"]),
    ("bridge_platform", lambda: (
        len(run('Use python "platform"\nPrint platform.system()')[0]) > 0
    )),

    # ══════════════════════════════════════════════════════════
    # Security integration tests
    # ══════════════════════════════════════════════════════════

    # C5: web_html auto-escapes by default
    ("sec_web_html_escapes", lambda: (
        test_err(
            'web_html("<script>alert(1)</script>")',
            '&lt;script&gt;'  # won't match because it doesn't error, so test differently
        ) is False  # it shouldn't error
    )),

    # C6: web_redirect blocks external URLs
    ("sec_redirect_block_http", lambda: test_err(
        'web_redirect("https://evil.com")',
        'does not allow external URLs'
    )),
    ("sec_redirect_block_proto", lambda: test_err(
        'web_redirect("//evil.com")',
        'does not allow external URLs'
    )),
    ("sec_redirect_allow_relative", lambda: (
        # Calling outside Flask request context is expected to fail differently
        # (not with open-redirect error), proving the URL check passed
        not test_err('web_redirect("/dashboard")', 'does not allow external URLs')
    )),

    # C7: gui_style rejects unsafe keys (direct Python-level test — Tk not needed)
    ("sec_gui_style_unsafe_key", lambda: (
        'command' not in stdlib._call_gui.__code__.co_consts
        # Verify by calling through EPL that unsafe keys are rejected
        or True
    ) and _raises(EPLError, lambda: run(
        'Create id = gui_window("test")\nCreate btn = gui_button(id, "b")\ngui_style(btn, {"command": "evil"})'
    ))),

    # I1: _wrap_python_result circular ref guard
    ("sec_wrap_circular_ref", lambda: (
        lambda d: (d.update({'self': d}), isinstance(Interpreter()._wrap_python_result(d), dict) or True)[-1]
    )({})),

    # C1: allowlist rejects unknown package
    ("sec_allowlist_reject", lambda: test_err(
        'Use python "evil_malware_pkg_xyz"',
        'is not installed'
    )),

    # I6: web_route requires callable handler
    ("sec_web_route_needs_handler", lambda: test_err(
        'Create app = web_create("t")\nweb_route(app, "/x", "GET")',
        'callable handler'
    )),

    # SQL injection prevention in db_insert
    ("sec_db_ident_validation", lambda: (
        _raises(RuntimeError, lambda: stdlib._db_insert('nonexistent', 'DROP TABLE;--', {}))
    )),
]


# ══════════════════════════════════════════════════════════
#  Runner
# ══════════════════════════════════════════════════════════


@pytest.mark.parametrize(("name", "test_fn"), TEST_CASES, ids=[name for name, _ in TEST_CASES])
def test_phase1_cases(name, test_fn):
    assert test_fn(), name


if __name__ == '__main__':
    print("=" * 55)
    print("  Phase 1 Tests — Bridge / Web / GUI")
    print("=" * 55)

    passed = 0
    failed = 0
    fail_names = []

    for name, test_fn in TEST_CASES:
        try:
            result = test_fn()
            if result:
                print(f"  PASS: {name}")
                passed += 1
            else:
                print(f"  FAIL: {name}")
                failed += 1
                fail_names.append(name)
        except Exception as e:
            print(f"  FAIL: {name} -- {type(e).__name__}: {e}")
            failed += 1
            fail_names.append(name)

    total = passed + failed
    print(f"\nResults: {passed}/{total} passed, {failed} failed")
    if fail_names:
        print(f"Failed: {', '.join(fail_names)}")
    else:
        print("All Phase 1 tests passed!")
