"""Tests for iOS/SwiftUI v6.0+v6.1: Style, Layout, 3D & Canvas."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.ios_gen import SwiftUIGenerator


def parse(src):
    return Parser(Lexer(src).tokenize()).parse()


def to_swift(src):
    prog = parse(src)
    gen = SwiftUIGenerator('TestApp', 'com.test.app')
    return gen.generate(prog)


class TestStyleDefSwiftUI:
    def test_style_generates_view_modifier(self):
        out = to_swift('Style "card"\n    Background "#ffffff"\n    Padding "16px"\nEnd\n')
        assert 'ViewModifier' in out
        assert 'CardStyle' in out

    def test_style_background_modifier(self):
        out = to_swift('Style "hero"\n    Background "#ff0000"\nEnd\n')
        assert '.background(' in out
        assert 'Color(red:' in out

    def test_style_padding_modifier(self):
        out = to_swift('Style "padded"\n    Padding "24px"\nEnd\n')
        assert '.padding(24)' in out

    def test_style_corner_radius(self):
        out = to_swift('Style "rounded"\n    BorderRadius "12px"\nEnd\n')
        assert '.cornerRadius(12)' in out

    def test_style_shadow(self):
        out = to_swift('Style "elevated"\n    BoxShadow "8px"\nEnd\n')
        assert '.shadow(radius: 8)' in out


class TestStyledElementSwiftUI:
    def test_div_generates_vstack(self):
        out = to_swift('Div with style "card"\nEnd\n')
        assert 'VStack' in out

    def test_section_generates_vstack(self):
        out = to_swift('Section with style "hero"\nEnd\n')
        assert 'VStack' in out


class TestLayoutContainerSwiftUI:
    def test_flex_row_hstack(self):
        out = to_swift('Flex direction "row" gap "16px"\nEnd\n')
        assert 'HStack' in out
        assert 'spacing: 16' in out

    def test_flex_column_vstack(self):
        out = to_swift('Flex direction "column" gap "8px"\nEnd\n')
        assert 'VStack' in out
        assert 'spacing: 8' in out

    def test_grid_lazyvgrid(self):
        out = to_swift('Grid columns 3 gap "24px"\nEnd\n')
        assert 'LazyVGrid' in out
        assert 'GridItem(.flexible())' in out
        assert 'count: 3' in out


class TestComponentSwiftUI:
    def test_component_generates_view_struct(self):
        out = to_swift('Component "MyCard" takes title\nEnd\n')
        assert 'struct' in out
        assert 'View' in out
        assert 'var title' in out


class TestScene3DSwiftUI:
    def test_scene_generates_scenekit(self):
        out = to_swift(
            'Scene "demo" width 800 height 600\n    Mesh "cube" position 0, 0, 0 color "#ff0000"\nEnd\n'
        )
        assert 'SCNScene' in out
        assert 'SCNBox' in out

    def test_scene_camera(self):
        out = to_swift('Scene "cam"\n    Camera position 0, 5, 10 look_at 0, 0, 0\nEnd\n')
        assert 'SCNCamera' in out
        assert 'SCNVector3(0, 5, 10)' in out

    def test_scene_light(self):
        out = to_swift('Scene "lit"\n    Light "ambient" color "#fff" intensity 0.5\nEnd\n')
        assert 'SCNLight' in out
        assert '.ambient' in out

    def test_scene_sphere_mesh(self):
        out = to_swift('Scene "s"\n    Mesh "sphere" position 3, 1, 0 color "#00ff00"\nEnd\n')
        assert 'SCNSphere' in out

    def test_scene_imports_scenekit(self):
        out = to_swift('Scene "s"\nEnd\n')
        assert 'import SceneKit' in out


class TestDrawCommandSwiftUI:
    def test_draw_rect(self):
        out = to_swift('Draw "rect" x 10 y 20 width 100 height 50 fill "#ff0000"\n')
        assert 'Canvas' in out
        assert 'context.fill' in out
        assert 'CGRect(x: 10, y: 20, width: 100, height: 50)' in out

    def test_draw_circle(self):
        out = to_swift('Draw "circle" x 50 y 50 radius 25 fill "#00ff00"\n')
        assert 'Canvas' in out
        assert 'Circle()' in out

    def test_draw_line(self):
        out = to_swift('Draw "line" x1 0 y1 0 x2 100 y2 100 stroke "#000" width 2\n')
        assert 'Canvas' in out
        assert 'path.move(to:' in out
        assert 'path.addLine(to:' in out
        assert 'context.stroke' in out

    def test_draw_text(self):
        out = to_swift('Draw "text" x 10 y 30 content "Hello" font "16px Arial" fill "#000"\n')
        assert 'Canvas' in out
        assert 'context.draw' in out
        assert 'Text("Hello")' in out
