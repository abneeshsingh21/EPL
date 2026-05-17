"""Tests for Kotlin/Android v6.0+v6.1: Style, Layout, 3D & Canvas in Compose."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.kotlin_gen import KotlinGenerator
from epl.lexer import Lexer
from epl.parser import Parser


def parse(src):
    return Parser(Lexer(src).tokenize()).parse()


def gen(src):
    prog = parse(src)
    g = KotlinGenerator()
    return g.generate(prog)


def gen_compose(src):
    prog = parse(src)
    g = KotlinGenerator()
    return g.generate_compose_activity(prog)


class TestStyleDefCompose:
    def test_style_generates_composable(self):
        code = 'Style "card"\n    Background "#ffffff"\n    Padding "16px"\nEnd\n'
        out = gen(code)
        assert '@Composable' in out
        assert 'CardStyle' in out

    def test_style_modifier_background(self):
        code = 'Style "hero"\n    Background "#ff0000"\nEnd\n'
        out = gen(code)
        assert 'Modifier' in out
        assert 'background' in out
        assert '0xFFff0000' in out

    def test_style_modifier_padding(self):
        code = 'Style "padded"\n    Padding "24px"\nEnd\n'
        out = gen(code)
        assert 'padding(24.dp)' in out

    def test_style_modifier_border_radius(self):
        code = 'Style "rounded"\n    BorderRadius "12px"\nEnd\n'
        out = gen(code)
        assert 'RoundedCornerShape(12.dp)' in out


class TestStyledElementCompose:
    def test_div_generates_box(self):
        code = 'Div with style "card"\nEnd\n'
        out = gen(code)
        assert 'Box(' in out

    def test_section_generates_column(self):
        code = 'Section with style "hero"\nEnd\n'
        out = gen(code)
        assert 'Column(' in out


class TestLayoutContainerCompose:
    def test_flex_row(self):
        code = 'Flex direction "row" gap "16px"\nEnd\n'
        out = gen(code)
        assert 'Row(' in out
        assert 'Arrangement.spacedBy(16.dp)' in out

    def test_flex_column(self):
        code = 'Flex direction "column" gap "8px"\nEnd\n'
        out = gen(code)
        assert 'Column(' in out
        assert 'Arrangement.spacedBy(8.dp)' in out

    def test_grid(self):
        code = 'Grid columns 3 gap "24px"\nEnd\n'
        out = gen(code)
        assert 'LazyVerticalGrid' in out
        assert 'GridCells.Fixed(3)' in out
        assert '24.dp' in out


class TestComponentDefCompose:
    def test_component_composable_function(self):
        code = 'Component "MyCard" takes title\nEnd\n'
        out = gen(code)
        assert '@Composable' in out
        assert 'fun MyCard(' in out or 'fun MyCard(' in out
        assert 'title: Any?' in out


class TestAnimateDefCompose:
    def test_animate_infinite(self):
        code = 'Animate "spin"\n    Duration "2s"\n    Easing "linear"\n    Keyframe 0\n        Opacity "0"\n    End\n    Keyframe 100\n        Opacity "1"\n    End\nEnd\n'
        out = gen(code)
        assert 'animateFloat' in out or 'tween' in out


class TestScene3DCompose:
    def test_scene_generates_canvas(self):
        code = 'Scene "demo" width 800 height 600\n    Mesh "cube" position 0, 0, 0 color "#ff0000"\nEnd\n'
        out = gen(code)
        assert 'Canvas(' in out
        assert 'drawRect' in out

    def test_scene_sphere_mesh(self):
        code = 'Scene "s"\n    Mesh "sphere" position 3, 1, 0 color "#00ff00"\nEnd\n'
        out = gen(code)
        assert 'drawCircle' in out


class TestDrawCommandCompose:
    def test_draw_rect(self):
        code = 'Draw "rect" x 10 y 20 width 100 height 50 fill "#ff0000"\n'
        out = gen(code)
        assert 'drawRect(' in out
        assert 'Offset(10f, 20f)' in out
        assert 'Size(100f, 50f)' in out

    def test_draw_circle(self):
        code = 'Draw "circle" x 50 y 50 radius 25 fill "#00ff00"\n'
        out = gen(code)
        assert 'drawCircle(' in out
        assert 'radius = 25f' in out
        assert 'Offset(50f, 50f)' in out

    def test_draw_line(self):
        code = 'Draw "line" x1 0 y1 0 x2 100 y2 100 stroke "#000" width 2\n'
        out = gen(code)
        assert 'drawLine(' in out
        assert 'Offset(0f, 0f)' in out
        assert 'Offset(100f, 100f)' in out
        assert 'strokeWidth = 2f' in out

    def test_draw_path(self):
        code = 'Draw "path" points "M10,10 L100,100" fill "#red"\n'
        out = gen(code)
        assert 'drawPath' in out
        assert 'Path()' in out
