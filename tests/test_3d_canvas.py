"""Tests for EPL v6.1: 3D & Canvas System."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl import ast_nodes as ast
from epl.html_gen import _render_scene_3d, _render_draw_command


def parse(code):
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


class TestScene3DParsing:
    def test_basic_scene(self):
        prog = parse('Scene "test" width 800 height 600\nEnd\n')
        assert len(prog.statements) == 1
        scene = prog.statements[0]
        assert isinstance(scene, ast.Scene3D)
        assert scene.name == 'test'
        assert scene.width == 800
        assert scene.height == 600

    def test_scene_defaults(self):
        prog = parse('Scene "default"\nEnd\n')
        scene = prog.statements[0]
        assert scene.width == 800
        assert scene.height == 600

    def test_scene_with_camera(self):
        code = 'Scene "cam-test" width 400 height 300\n    Camera position 0, 5, 10 look_at 0, 0, 0 fov 90\nEnd\n'
        prog = parse(code)
        scene = prog.statements[0]
        assert len(scene.body) == 1
        cam = scene.body[0]
        assert isinstance(cam, ast.CameraSetup)
        assert cam.position == [0, 5, 10]
        assert cam.look_at == [0, 0, 0]
        assert cam.fov == 90

    def test_scene_with_light(self):
        code = 'Scene "light-test"\n    Light "directional" color "#fff" intensity 0.8 position 5, 10, 5\nEnd\n'
        prog = parse(code)
        scene = prog.statements[0]
        light = scene.body[0]
        assert isinstance(light, ast.LightSetup)
        assert light.light_type == 'directional'
        assert light.color == '#fff'
        assert light.intensity == 0.8
        assert light.position == [5, 10, 5]

    def test_scene_with_mesh(self):
        code = 'Scene "mesh-test"\n    Mesh "sphere" position 3, 1, 0 scale 2, 2, 2 color "#ff0000"\nEnd\n'
        prog = parse(code)
        scene = prog.statements[0]
        mesh = scene.body[0]
        assert isinstance(mesh, ast.MeshAdd)
        assert mesh.shape == 'sphere'
        assert mesh.position == [3, 1, 0]
        assert mesh.scale == [2, 2, 2]
        assert mesh.color == '#ff0000'

    def test_full_scene(self):
        code = (
            'Scene "full" width 1024 height 768\n'
            '    Camera position 0, 5, 10 look_at 0, 0, 0\n'
            '    Light "ambient" color "#ffffff" intensity 0.4\n'
            '    Light "directional" color "#ffffff" intensity 0.8 position 5, 10, 5\n'
            '    Mesh "cube" position 0, 0, 0 color "#667eea"\n'
            '    Mesh "sphere" position 3, 1, 0 color "#f093fb"\n'
            'End\n'
        )
        prog = parse(code)
        scene = prog.statements[0]
        assert scene.width == 1024
        assert scene.height == 768
        assert len(scene.body) == 5

    def test_negative_position(self):
        code = 'Scene "neg"\n    Mesh "cube" position -3, -1, -5\nEnd\n'
        prog = parse(code)
        mesh = prog.statements[0].body[0]
        assert mesh.position == [-3, -1, -5]


class TestDrawCommandParsing:
    def test_draw_rect(self):
        prog = parse('Draw "rect" x 10 y 20 width 100 height 50 fill "#ff0000"\n')
        cmd = prog.statements[0]
        assert isinstance(cmd, ast.DrawCommand)
        assert cmd.shape == 'rect'
        assert cmd.properties['x'] == 10
        assert cmd.properties['y'] == 20
        assert cmd.properties['width'] == 100
        assert cmd.properties['height'] == 50
        assert cmd.properties['fill'] == '#ff0000'

    def test_draw_circle(self):
        prog = parse('Draw "circle" x 50 y 50 radius 25 fill "#00ff00"\n')
        cmd = prog.statements[0]
        assert cmd.shape == 'circle'
        assert cmd.properties['radius'] == 25

    def test_draw_line(self):
        prog = parse('Draw "line" x1 0 y1 0 x2 100 y2 100 stroke "#000" width 2\n')
        cmd = prog.statements[0]
        assert cmd.shape == 'line'
        assert cmd.properties['x1'] == 0
        assert cmd.properties['x2'] == 100
        assert cmd.properties['stroke'] == '#000'
        assert cmd.properties['width'] == 2

    def test_draw_text(self):
        prog = parse('Draw "text" x 10 y 30 content "Hello" font "16px Arial" fill "#000"\n')
        cmd = prog.statements[0]
        assert cmd.shape == 'text'
        assert cmd.properties['content'] == 'Hello'
        assert cmd.properties['font'] == '16px Arial'

    def test_draw_path(self):
        prog = parse('Draw "path" points "M10,10 L100,10 L100,100 Z" fill "#blue"\n')
        cmd = prog.statements[0]
        assert cmd.shape == 'path'
        assert cmd.properties['points'] == 'M10,10 L100,10 L100,100 Z'

    def test_draw_negative_coords(self):
        prog = parse('Draw "rect" x -10 y -20 width 50 height 30 fill "#fff"\n')
        cmd = prog.statements[0]
        assert cmd.properties['x'] == -10
        assert cmd.properties['y'] == -20


class TestScene3DHTMLRendering:
    def test_basic_scene_html(self):
        scene = ast.Scene3D('test', 800, 600, [], 1)
        html = _render_scene_3d(scene)
        assert 'id="scene-test"' in html
        assert 'width:800px' in html
        assert 'height:600px' in html
        assert 'three.min.js' in html

    def test_scene_with_camera_html(self):
        cam = ast.CameraSetup([0, 5, 10], [0, 0, 0], 75)
        scene = ast.Scene3D('cam', 800, 600, [cam], 1)
        html = _render_scene_3d(scene)
        assert 'PerspectiveCamera(75' in html
        assert 'position.set(0, 5, 10)' in html
        assert 'lookAt(0, 0, 0)' in html

    def test_scene_with_light_html(self):
        light = ast.LightSetup('ambient', '#ffffff', 0.5)
        scene = ast.Scene3D('lit', 800, 600, [light], 1)
        html = _render_scene_3d(scene)
        assert 'AmbientLight("#ffffff", 0.5)' in html

    def test_scene_with_directional_light_html(self):
        light = ast.LightSetup('directional', '#fff', 0.8, [5, 10, 5])
        scene = ast.Scene3D('dir', 800, 600, [light], 1)
        html = _render_scene_3d(scene)
        assert 'DirectionalLight("#fff", 0.8)' in html
        assert 'position.set(5, 10, 5)' in html

    def test_scene_with_mesh_html(self):
        mesh = ast.MeshAdd('cube', None, [0, 0, 0], [0, 0, 0], [1, 1, 1], None, '#667eea')
        scene = ast.Scene3D('m', 800, 600, [mesh], 1)
        html = _render_scene_3d(scene)
        assert 'BoxGeometry(1,1,1)' in html
        assert 'color: "#667eea"' in html

    def test_sphere_mesh_html(self):
        mesh = ast.MeshAdd('sphere', None, [3, 1, 0], [0, 0, 0], [2, 2, 2], None, '#f093fb')
        scene = ast.Scene3D('s', 800, 600, [mesh], 1)
        html = _render_scene_3d(scene)
        assert 'SphereGeometry(1,32,32)' in html
        assert 'position.set(3, 1, 0)' in html
        assert 'scale.set(2, 2, 2)' in html

    def test_animate_loop(self):
        scene = ast.Scene3D('anim', 800, 600, [], 1)
        html = _render_scene_3d(scene)
        assert 'requestAnimationFrame(animate)' in html
        assert 'renderer.render(scene, camera)' in html


class TestDrawCommandHTMLRendering:
    def test_rect_canvas(self):
        cmd = ast.DrawCommand('rect', {'x': 10, 'y': 20, 'width': 100, 'height': 50, 'fill': '#ff0000'}, 1)
        html = _render_draw_command(cmd)
        assert 'canvas' in html.lower()
        assert 'fillStyle = "#ff0000"' in html
        assert 'fillRect(10, 20, 100, 50)' in html

    def test_circle_canvas(self):
        cmd = ast.DrawCommand('circle', {'x': 50, 'y': 50, 'radius': 25, 'fill': '#00ff00'}, 1)
        html = _render_draw_command(cmd)
        assert 'arc(50, 50, 25, 0, Math.PI * 2)' in html
        assert 'fillStyle = "#00ff00"' in html

    def test_line_canvas(self):
        cmd = ast.DrawCommand('line', {'x1': 0, 'y1': 0, 'x2': 100, 'y2': 100, 'stroke': '#000', 'width': 2}, 1)
        html = _render_draw_command(cmd)
        assert 'moveTo(0, 0)' in html
        assert 'lineTo(100, 100)' in html
        assert 'strokeStyle = "#000"' in html
        assert 'lineWidth = 2' in html

    def test_text_canvas(self):
        cmd = ast.DrawCommand('text', {'x': 10, 'y': 30, 'content': 'Hello', 'font': '16px Arial', 'fill': '#000'}, 1)
        html = _render_draw_command(cmd)
        assert 'font = "16px Arial"' in html
        assert 'fillText("Hello", 10, 30)' in html

    def test_path_canvas(self):
        cmd = ast.DrawCommand('path', {'points': 'M10,10 L100,100', 'fill': '#red'}, 1)
        html = _render_draw_command(cmd)
        assert 'Path2D("M10,10 L100,100")' in html
        assert 'fillStyle = "#red"' in html


class TestInterpreterHandles3DCanvas:
    def test_scene_no_crash(self):
        code = 'Scene "test" width 800 height 600\n    Mesh "cube" position 0, 0, 0\nEnd\n'
        prog = parse(code)
        interp = Interpreter()
        interp.execute(prog)

    def test_draw_no_crash(self):
        code = 'Draw "rect" x 10 y 10 width 100 height 50 fill "#ff0000"\n'
        prog = parse(code)
        interp = Interpreter()
        interp.execute(prog)

    def test_multiple_draws(self):
        code = (
            'Draw "rect" x 0 y 0 width 800 height 600 fill "#1a1a2e"\n'
            'Draw "circle" x 400 y 300 radius 50 fill "#ff0000"\n'
            'Draw "text" x 10 y 30 content "Score: 0" font "20px mono" fill "#fff"\n'
        )
        prog = parse(code)
        interp = Interpreter()
        interp.execute(prog)


class TestDrawInsidePage:
    def test_draw_inside_page(self):
        code = (
            'Page "Game"\n'
            '    Heading "My Game"\n'
            '    Draw "rect" x 0 y 0 width 800 height 600 fill "#000"\n'
            '    Draw "circle" x 400 y 300 radius 25 fill "#0f0"\n'
            'End\n'
        )
        prog = parse(code)
        page = prog.statements[0]
        assert isinstance(page, ast.PageDef)
        assert len(page.elements) == 3

    def test_scene_inside_page(self):
        code = (
            'Page "3D Demo"\n'
            '    Heading "3D Scene"\n'
            '    Scene "demo" width 800 height 600\n'
            '        Mesh "cube" position 0, 0, 0 color "#ff0000"\n'
            '    End\n'
            'End\n'
        )
        prog = parse(code)
        page = prog.statements[0]
        assert len(page.elements) == 2
        scene = page.elements[1]
        assert isinstance(scene, ast.Scene3D)

    def test_div_inside_page(self):
        code = (
            'Page "Styled"\n'
            '    Div with style "container"\n'
            '        Heading "Inside Div"\n'
            '    End\n'
            'End\n'
        )
        prog = parse(code)
        page = prog.statements[0]
        assert len(page.elements) == 1
        div = page.elements[0]
        assert isinstance(div, ast.StyledElement)
        assert div.tag == 'div'


class TestPackagesParse:
    def test_epl_3d_parses(self):
        with open(os.path.join(os.path.dirname(__file__), '..', 'epl_packages', 'epl-3d', 'main.epl')) as f:
            code = f.read()
        prog = parse(code)
        assert len(prog.statements) > 0

    def test_epl_canvas_parses(self):
        with open(os.path.join(os.path.dirname(__file__), '..', 'epl_packages', 'epl-canvas', 'main.epl')) as f:
            code = f.read()
        prog = parse(code)
        assert len(prog.statements) > 0

    def test_game_2d_template_parses(self):
        from epl.cli import _project_template
        _, main_src, _, _ = _project_template('test-game', 'game-2d')
        prog = parse(main_src)
        assert len(prog.statements) > 0
