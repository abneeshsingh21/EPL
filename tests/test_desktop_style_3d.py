"""Tests for Desktop/Compose v6.0+v6.1: Style, Layout, 3D & Canvas."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.desktop import DesktopComposeGenerator


def parse(src):
    return Parser(Lexer(src).tokenize()).parse()


def to_desktop(src):
    prog = parse(src)
    gen = DesktopComposeGenerator('com.epl.test', 'Test App')
    return gen.generate(prog)


class TestStyleDefDesktop:
    def test_style_generates_composable(self):
        out = to_desktop('Style "card"\n    Background "#ffffff"\n    Padding "16px"\nEnd\n')
        assert '@Composable' in out
        assert 'CardStyle' in out
        assert 'Modifier' in out

    def test_style_background(self):
        out = to_desktop('Style "hero"\n    Background "#ff0000"\nEnd\n')
        assert 'background(' in out
        assert '0xFFff0000' in out

    def test_style_padding(self):
        out = to_desktop('Style "padded"\n    Padding "24px"\nEnd\n')
        assert 'padding(24.dp)' in out

    def test_style_border_radius(self):
        out = to_desktop('Style "rounded"\n    BorderRadius "12px"\nEnd\n')
        assert 'RoundedCornerShape(12.dp)' in out


class TestStyledElementDesktop:
    def test_div_generates_box(self):
        out = to_desktop('Div with style "card"\nEnd\n')
        assert 'Box(' in out

    def test_section_generates_column(self):
        out = to_desktop('Section with style "main"\nEnd\n')
        assert 'Column(' in out


class TestLayoutContainerDesktop:
    def test_flex_row(self):
        out = to_desktop('Flex direction "row" gap "16px"\nEnd\n')
        assert 'Row(' in out
        assert 'Arrangement.spacedBy(16.dp)' in out

    def test_flex_column(self):
        out = to_desktop('Flex direction "column" gap "8px"\nEnd\n')
        assert 'Column(' in out
        assert 'Arrangement.spacedBy(8.dp)' in out

    def test_grid(self):
        out = to_desktop('Grid columns 3 gap "24px"\nEnd\n')
        assert 'LazyVerticalGrid' in out
        assert 'GridCells.Fixed(3)' in out


class TestComponentDefDesktop:
    def test_component_composable(self):
        out = to_desktop('Component "MyCard" takes title\nEnd\n')
        assert '@Composable' in out
        assert 'fun MyCard(' in out


class TestAnimateDefDesktop:
    def test_animate_generates_state(self):
        out = to_desktop(
            'Animate "fadeIn"\n    Duration "1s"\n    Easing "ease"\n    Keyframe 0\n        Opacity "0"\n    End\n    Keyframe 100\n        Opacity "1"\n    End\nEnd\n'
        )
        assert 'animateFloatAsState' in out or 'tween' in out


class TestScene3DDesktop:
    def test_scene_generates_canvas(self):
        out = to_desktop(
            'Scene "demo" width 800 height 600\n    Mesh "cube" position 0, 0, 0 color "#ff0000"\nEnd\n'
        )
        assert 'Canvas(' in out
        assert 'drawRect' in out

    def test_scene_sphere(self):
        out = to_desktop('Scene "s"\n    Mesh "sphere" position 3, 1, 0 color "#00ff00"\nEnd\n')
        assert 'drawCircle' in out


class TestDrawCommandDesktop:
    def test_draw_rect(self):
        out = to_desktop('Draw "rect" x 10 y 20 width 100 height 50 fill "#ff0000"\n')
        assert 'drawRect(' in out
        assert 'Offset(10f, 20f)' in out
        assert 'Size(100f, 50f)' in out

    def test_draw_circle(self):
        out = to_desktop('Draw "circle" x 50 y 50 radius 25 fill "#00ff00"\n')
        assert 'drawCircle(' in out
        assert 'radius = 25f' in out

    def test_draw_line(self):
        out = to_desktop('Draw "line" x1 0 y1 0 x2 100 y2 100 stroke "#000" width 2\n')
        assert 'drawLine(' in out
        assert 'Offset(0f, 0f)' in out
        assert 'Offset(100f, 100f)' in out

    def test_draw_path(self):
        out = to_desktop('Draw "path" points "M10,10 L100,100" fill "#red"\n')
        assert 'drawPath' in out
        assert 'Path()' in out
