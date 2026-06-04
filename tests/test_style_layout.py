"""Tests for EPL v6.0 Style & Layout System.

Tests parser, HTML generation, and JS transpilation of:
- StyleDef (custom CSS classes)
- StyledElement (div, section, nav, etc.)
- LayoutContainer (Flex/Grid)
- ComponentDef / ComponentUse
- AnimateDef with Keyframes
- ResponsiveBlock
- TransitionDef
"""

import pytest
from epl import ast_nodes as ast
from epl.html_gen import _generate_animation_css, _generate_custom_css, generate_html
from epl.js_transpiler import transpile_to_js
from epl.lexer import Lexer
from epl.parser import Parser


def _parse(code):
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


# ─── Parser Tests ─────────────────────────────────────────


class TestStyleDefParsing:
    def test_basic_style(self):
        prog = _parse('Style "card"\n    Background "#fff"\nEnd\n')
        assert len(prog.statements) == 1
        style = prog.statements[0]
        assert isinstance(style, ast.StyleDef)
        assert style.name == 'card'
        assert len(style.properties) == 1
        assert style.properties[0].property_name == 'background'
        assert style.properties[0].value == '#fff'

    def test_multi_word_property(self):
        prog = _parse(
            'Style "box"\n    Border radius "12px"\n    Box shadow "0 2px 8px rgba(0,0,0,0.1)"\nEnd\n'
        )
        style = prog.statements[0]
        assert style.properties[0].property_name == 'border-radius'
        assert style.properties[0].value == '12px'
        assert style.properties[1].property_name == 'box-shadow'

    def test_multiple_properties(self):
        prog = _parse(
            'Style "hero"\n'
            '    Background "linear-gradient(135deg, #667eea, #764ba2)"\n'
            '    Color "#ffffff"\n'
            '    Padding "80px 40px"\n'
            '    Text align "center"\n'
            'End\n'
        )
        style = prog.statements[0]
        assert len(style.properties) == 4
        assert style.properties[3].property_name == 'text-align'


class TestStyledElementParsing:
    def test_div_basic(self):
        prog = _parse('Div\n    Say "hello"\nEnd\n')
        assert len(prog.statements) == 1
        elem = prog.statements[0]
        assert isinstance(elem, ast.StyledElement)
        assert elem.tag == 'div'
        assert len(elem.children) == 1

    def test_div_with_style(self):
        prog = _parse('Div with style "card"\n    Say "content"\nEnd\n')
        elem = prog.statements[0]
        assert elem.styles == ['card']

    def test_div_with_class(self):
        prog = _parse('Div class "my-class"\n    Say "content"\nEnd\n')
        elem = prog.statements[0]
        assert elem.class_names == ['my-class']

    def test_div_with_id(self):
        prog = _parse('Div id "main-content"\n    Say "content"\nEnd\n')
        elem = prog.statements[0]
        assert elem.attributes.get('id') == 'main-content'

    def test_section_element(self):
        prog = _parse('Section with style "hero"\n    Say "Welcome"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'section'
        assert elem.styles == ['hero']

    def test_nav_element(self):
        prog = _parse('Nav\n    Say "Navigation"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'nav'

    def test_header_element(self):
        prog = _parse('Header with style "top-bar"\n    Say "Logo"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'header'

    def test_footer_element(self):
        prog = _parse('Footer\n    Say "Copyright"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'footer'

    def test_article_element(self):
        prog = _parse('Article\n    Say "Post content"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'article'

    def test_aside_element(self):
        prog = _parse('Aside\n    Say "Sidebar"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'aside'

    def test_main_element(self):
        prog = _parse('Main\n    Say "Body"\nEnd\n')
        elem = prog.statements[0]
        assert elem.tag == 'main'

    def test_div_with_animate(self):
        prog = _parse('Div with style "card" animate "fadeIn"\n    Say "content"\nEnd\n')
        elem = prog.statements[0]
        assert elem.attributes.get('data-animate') == 'fadeIn'


class TestLayoutContainerParsing:
    def test_flex_basic(self):
        prog = _parse('Flex direction "row" gap "16px"\n    Say "item"\nEnd\n')
        assert len(prog.statements) == 1
        layout = prog.statements[0]
        assert isinstance(layout, ast.LayoutContainer)
        assert layout.layout_type == 'flex'
        assert layout.properties['direction'] == 'row'
        assert layout.properties['gap'] == '16px'

    def test_grid_columns(self):
        prog = _parse('Grid columns 3 gap "24px"\n    Say "item"\nEnd\n')
        layout = prog.statements[0]
        assert layout.layout_type == 'grid'
        assert layout.properties['columns'] == 3
        assert layout.properties['gap'] == '24px'

    def test_flex_with_align(self):
        prog = _parse(
            'Flex direction "column" align "center" justify "space-between"\n    Say "a"\nEnd\n'
        )
        layout = prog.statements[0]
        assert layout.properties['align'] == 'center'
        assert layout.properties['justify'] == 'space-between'


class TestComponentDefParsing:
    def test_component_basic(self):
        prog = _parse(
            'Component "Card" takes title, description\n    Say title\n    Say description\nEnd\n'
        )
        comp = prog.statements[0]
        assert isinstance(comp, ast.ComponentDef)
        assert comp.name == 'Card'
        assert len(comp.params) >= 2
        assert len(comp.body) == 2

    def test_component_no_params(self):
        prog = _parse('Component "Footer"\n    Say "Built with EPL"\nEnd\n')
        comp = prog.statements[0]
        assert comp.name == 'Footer'
        assert comp.params == []


class TestResponsiveBlockParsing:
    def test_responsive_mobile(self):
        prog = _parse('Responsive "mobile"\n    Say "Mobile view"\nEnd\n')
        resp = prog.statements[0]
        assert isinstance(resp, ast.ResponsiveBlock)
        assert resp.breakpoint == 'mobile'
        assert len(resp.body) == 1


class TestAnimateDefParsing:
    def test_animate_with_keyframes(self):
        prog = _parse(
            'Animate "fadeIn"\n'
            '    Duration "1s"\n'
            '    Easing "ease-out"\n'
            '    Keyframe 0\n'
            '        Opacity "0"\n'
            '    End\n'
            '    Keyframe 100\n'
            '        Opacity "1"\n'
            '    End\n'
            'End\n'
        )
        anim = prog.statements[0]
        assert isinstance(anim, ast.AnimateDef)
        assert anim.name == 'fadeIn'
        assert anim.duration == '1s'
        assert anim.easing == 'ease-out'
        assert len(anim.keyframes) == 2
        assert anim.keyframes[0].percentage == 0
        assert anim.keyframes[1].percentage == 100

    def test_animate_minimal(self):
        prog = _parse(
            'Animate "spin"\n'
            '    Duration "2s"\n'
            '    Keyframe 0\n'
            '        Transform "rotate(0deg)"\n'
            '    End\n'
            '    Keyframe 100\n'
            '        Transform "rotate(360deg)"\n'
            '    End\n'
            'End\n'
        )
        anim = prog.statements[0]
        assert anim.name == 'spin'
        assert anim.duration == '2s'


class TestTransitionDefParsing:
    def test_transition(self):
        prog = _parse('Transition "all" duration "0.3s" easing "ease"\n')
        trans = prog.statements[0]
        assert isinstance(trans, ast.TransitionDef)
        assert trans.property_name == 'all'
        assert trans.duration == '0.3s'
        assert trans.easing == 'ease'


# ─── HTML Generation Tests ────────────────────────────────


class TestCustomCSSGeneration:
    def test_generate_css_from_style_def(self):
        styles = [
            ast.StyleDef(
                'card',
                [
                    ast.StyleProperty('background', '#ffffff'),
                    ast.StyleProperty('border-radius', '12px'),
                    ast.StyleProperty('padding', '24px'),
                ],
            ),
        ]
        css = _generate_custom_css(styles)
        assert '.card {' in css
        assert 'background: #ffffff;' in css
        assert 'border-radius: 12px;' in css
        assert 'padding: 24px;' in css

    def test_multiple_styles(self):
        styles = [
            ast.StyleDef('card', [ast.StyleProperty('padding', '20px')]),
            ast.StyleDef('hero', [ast.StyleProperty('color', '#fff')]),
        ]
        css = _generate_custom_css(styles)
        assert '.card {' in css
        assert '.hero {' in css


class TestAnimationCSSGeneration:
    def test_keyframes_generation(self):
        animations = [
            ast.AnimateDef(
                'fadeIn',
                '1s',
                'ease-out',
                None,
                [
                    ast.KeyframeDef(0, [ast.StyleProperty('opacity', '0')]),
                    ast.KeyframeDef(100, [ast.StyleProperty('opacity', '1')]),
                ],
            ),
        ]
        css = _generate_animation_css(animations)
        assert '@keyframes fadeIn' in css
        assert '0%' in css
        assert '100%' in css
        assert 'opacity: 0;' in css
        assert 'opacity: 1;' in css
        assert '.animate-fadeIn' in css
        assert 'animation: fadeIn 1s ease-out 1;' in css


class TestStyledElementHTMLRendering:
    def test_div_renders(self):
        page = ast.PageDef(
            'Test',
            [
                ast.StyledElement(
                    'div',
                    ['card'],
                    [],
                    {},
                    [
                        ast.HtmlElement('heading', 'Hello', {}, [], 0),
                    ],
                    [],
                    0,
                ),
            ],
            0,
        )
        html = generate_html(page)
        assert '<div class="card">' in html
        assert '<h1>Hello</h1>' in html
        assert '</div>' in html

    def test_section_with_id(self):
        page = ast.PageDef(
            'Test',
            [
                ast.StyledElement(
                    'section',
                    [],
                    [],
                    {'id': 'hero'},
                    [
                        ast.HtmlElement('text', 'Welcome', {}, [], 0),
                    ],
                    [],
                    0,
                ),
            ],
            0,
        )
        html = generate_html(page)
        assert '<section id="hero">' in html


class TestLayoutContainerHTMLRendering:
    def test_flex_container(self):
        page = ast.PageDef(
            'Test',
            [
                ast.LayoutContainer(
                    'flex',
                    {'direction': 'row', 'gap': '16px'},
                    [
                        ast.HtmlElement('text', 'Item 1', {}, [], 0),
                        ast.HtmlElement('text', 'Item 2', {}, [], 0),
                    ],
                    0,
                ),
            ],
            0,
        )
        html = generate_html(page)
        assert 'display: flex' in html
        assert 'flex-direction: row' in html
        assert 'gap: 16px' in html

    def test_grid_container(self):
        page = ast.PageDef(
            'Test',
            [
                ast.LayoutContainer(
                    'grid',
                    {'columns': 3, 'gap': '24px'},
                    [
                        ast.HtmlElement('text', 'Grid item', {}, [], 0),
                    ],
                    0,
                ),
            ],
            0,
        )
        html = generate_html(page)
        assert 'display: grid' in html
        assert 'grid-template-columns: repeat(3, 1fr)' in html
        assert 'gap: 24px' in html


# ─── JS Transpiler Tests ─────────────────────────────────


class TestJSTranspilerStyleLayout:
    def test_style_def_generates_css_injection(self):
        prog = _parse('Style "card"\n    Background "#fff"\n    Padding "20px"\nEnd\n')
        js = transpile_to_js(prog)
        assert 'document.createElement("style")' in js
        assert '.card' in js
        assert 'background: #fff' in js

    def test_animate_def_generates_keyframes(self):
        prog = _parse(
            'Animate "fadeIn"\n'
            '    Duration "1s"\n'
            '    Easing "ease-out"\n'
            '    Keyframe 0\n'
            '        Opacity "0"\n'
            '    End\n'
            '    Keyframe 100\n'
            '        Opacity "1"\n'
            '    End\n'
            'End\n'
        )
        js = transpile_to_js(prog)
        assert '@keyframes fadeIn' in js
        assert '.animate-fadeIn' in js
        assert 'animation: fadeIn 1s ease-out 1' in js


# ─── Integration Tests ────────────────────────────────────


class TestFullPipeline:
    def test_style_with_page(self):
        """Full pipeline: Style + Page with styled elements."""
        prog = _parse(
            'Style "card"\n'
            '    Background "#ffffff"\n'
            '    Padding "20px"\n'
            '    Border radius "12px"\n'
            'End\n'
        )
        styles = [s for s in prog.statements if isinstance(s, ast.StyleDef)]
        page = ast.PageDef(
            'Test',
            [
                ast.StyledElement(
                    'div',
                    ['card'],
                    [],
                    {},
                    [
                        ast.HtmlElement('heading', 'Product', {}, [], 0),
                        ast.HtmlElement('text', '$9.99', {}, [], 0),
                    ],
                    [],
                    0,
                ),
            ],
            0,
        )
        html = generate_html(page, styles=styles)
        assert '.card {' in html
        assert 'background: #ffffff;' in html
        assert '<div class="card">' in html
        assert '<h1>Product</h1>' in html

    def test_animation_with_styled_element(self):
        """Animation CSS class applied to a styled element."""
        animations = [
            ast.AnimateDef(
                'slideUp',
                '0.5s',
                'ease',
                None,
                [
                    ast.KeyframeDef(0, [ast.StyleProperty('transform', 'translateY(20px)')]),
                    ast.KeyframeDef(100, [ast.StyleProperty('transform', 'translateY(0)')]),
                ],
            ),
        ]
        page = ast.PageDef(
            'Test',
            [
                ast.StyledElement(
                    'div',
                    ['card'],
                    [],
                    {'data-animate': 'slideUp'},
                    [
                        ast.HtmlElement('text', 'Animated', {}, [], 0),
                    ],
                    [],
                    0,
                ),
            ],
            0,
        )
        html = generate_html(page, animations=animations)
        assert '@keyframes slideUp' in html
        assert '.animate-slideUp' in html
        assert 'class="card animate-slideUp"' in html

    def test_interpreter_handles_new_nodes(self):
        """Interpreter should not crash on new v6.0 nodes."""
        from epl.interpreter import Interpreter

        prog = _parse(
            'Style "card"\n'
            '    Background "#fff"\n'
            'End\n'
            'Component "Box" takes content\n'
            '    Say content\n'
            'End\n'
            'Animate "fade"\n'
            '    Duration "1s"\n'
            '    Keyframe 0\n'
            '        Opacity "0"\n'
            '    End\n'
            '    Keyframe 100\n'
            '        Opacity "1"\n'
            '    End\n'
            'End\n'
            'Div with style "card"\n'
            '    Say "Hello"\n'
            'End\n'
            'Flex direction "row"\n'
            '    Say "item"\n'
            'End\n'
            'Grid columns 2\n'
            '    Say "cell"\n'
            'End\n'
            'Responsive "mobile"\n'
            '    Say "mobile"\n'
            'End\n'
            'Say "Done"\n'
        )
        interp = Interpreter()
        interp.execute(prog)
        # Should not raise — new nodes are no-ops in interpreter

    def test_complex_page_generation(self):
        """Test a production-like page with multiple features."""
        prog = _parse(
            'Style "navbar"\n'
            '    Background "#333"\n'
            '    Color "#fff"\n'
            '    Padding "16px"\n'
            'End\n\n'
            'Style "product-card"\n'
            '    Background "#fff"\n'
            '    Border "1px solid #ddd"\n'
            '    Border radius "8px"\n'
            '    Padding "20px"\n'
            'End\n\n'
            'Animate "fadeIn"\n'
            '    Duration "0.5s"\n'
            '    Easing "ease-out"\n'
            '    Keyframe 0\n'
            '        Opacity "0"\n'
            '    End\n'
            '    Keyframe 100\n'
            '        Opacity "1"\n'
            '    End\n'
            'End\n'
        )
        styles = [s for s in prog.statements if isinstance(s, ast.StyleDef)]
        animations = [s for s in prog.statements if isinstance(s, ast.AnimateDef)]

        page = ast.PageDef(
            'E-Commerce',
            [
                ast.StyledElement(
                    'nav',
                    ['navbar'],
                    [],
                    {},
                    [
                        ast.HtmlElement('link', 'Home', {'href': '/'}, [], 0),
                        ast.HtmlElement('link', 'Shop', {'href': '/shop'}, [], 0),
                    ],
                    [],
                    0,
                ),
                ast.LayoutContainer(
                    'grid',
                    {'columns': 3, 'gap': '20px'},
                    [
                        ast.StyledElement(
                            'div',
                            ['product-card'],
                            [],
                            {'data-animate': 'fadeIn'},
                            [
                                ast.HtmlElement('heading', 'Widget', {}, [], 0),
                                ast.HtmlElement('text', '$9.99', {}, [], 0),
                            ],
                            [],
                            0,
                        ),
                        ast.StyledElement(
                            'div',
                            ['product-card'],
                            [],
                            {'data-animate': 'fadeIn'},
                            [
                                ast.HtmlElement('heading', 'Gadget', {}, [], 0),
                                ast.HtmlElement('text', '$19.99', {}, [], 0),
                            ],
                            [],
                            0,
                        ),
                    ],
                    0,
                ),
            ],
            0,
        )

        html = generate_html(page, styles=styles, animations=animations)
        assert '.navbar {' in html
        assert '.product-card {' in html
        assert '@keyframes fadeIn' in html
        assert '<nav class="navbar">' in html
        assert 'display: grid' in html
        assert 'grid-template-columns: repeat(3, 1fr)' in html
        assert 'class="product-card animate-fadeIn"' in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
