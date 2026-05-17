"""Tests for JS transpiler v6.1: Scene3D and DrawCommand."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.js_transpiler import transpile_to_js
from epl.lexer import Lexer
from epl.parser import Parser


def to_js(src):
    return transpile_to_js(Parser(Lexer(src).tokenize()).parse())


class TestScene3DJS:
    def test_scene_generates_threejs_init(self):
        js = to_js('Scene "test" width 800 height 600\nEnd\n')
        assert 'THREE.Scene()' in js
        assert 'THREE.WebGLRenderer' in js

    def test_scene_container(self):
        js = to_js('Scene "demo" width 1024 height 768\nEnd\n')
        assert 'scene-demo' in js
        assert '1024' in js
        assert '768' in js

    def test_scene_camera(self):
        js = to_js('Scene "cam"\n    Camera position 0, 5, 10 look_at 0, 0, 0 fov 90\nEnd\n')
        assert 'PerspectiveCamera(90' in js
        assert 'position.set(0, 5, 10)' in js
        assert 'lookAt(0, 0, 0)' in js

    def test_scene_ambient_light(self):
        js = to_js('Scene "lit"\n    Light "ambient" color "#ffffff" intensity 0.5\nEnd\n')
        assert 'AmbientLight("#ffffff", 0.5)' in js

    def test_scene_directional_light(self):
        js = to_js(
            'Scene "dir"\n    Light "directional" color "#fff" intensity 0.8 position 5, 10, 5\nEnd\n'
        )
        assert 'DirectionalLight("#fff", 0.8)' in js
        assert 'position.set(5, 10, 5)' in js

    def test_scene_mesh_cube(self):
        js = to_js('Scene "m"\n    Mesh "cube" position 0, 0, 0 color "#ff0000"\nEnd\n')
        assert 'BoxGeometry(1,1,1)' in js
        assert 'color: "#ff0000"' in js

    def test_scene_mesh_sphere(self):
        js = to_js(
            'Scene "s"\n    Mesh "sphere" position 3, 1, 0 scale 2, 2, 2 color "#00ff00"\nEnd\n'
        )
        assert 'SphereGeometry(1,32,32)' in js
        assert 'position.set(3, 1, 0)' in js
        assert 'scale.set(2, 2, 2)' in js

    def test_scene_animate_loop(self):
        js = to_js('Scene "anim"\nEnd\n')
        assert 'requestAnimationFrame(animate)' in js
        assert 'renderer.render(scene, camera)' in js


class TestDrawCommandJS:
    def test_draw_rect(self):
        js = to_js('Draw "rect" x 10 y 20 width 100 height 50 fill "#ff0000"\n')
        assert 'fillRect(10, 20, 100, 50)' in js
        assert 'fillStyle = "#ff0000"' in js

    def test_draw_circle(self):
        js = to_js('Draw "circle" x 50 y 50 radius 25 fill "#00ff00"\n')
        assert 'arc(50, 50, 25, 0, Math.PI * 2)' in js
        assert 'fillStyle = "#00ff00"' in js

    def test_draw_line(self):
        js = to_js('Draw "line" x1 0 y1 0 x2 100 y2 100 stroke "#000" width 2\n')
        assert 'moveTo(0, 0)' in js
        assert 'lineTo(100, 100)' in js
        assert 'strokeStyle = "#000"' in js
        assert 'lineWidth = 2' in js

    def test_draw_text(self):
        js = to_js('Draw "text" x 10 y 30 content "Hello" font "16px Arial" fill "#000"\n')
        assert 'fillText("Hello", 10, 30)' in js
        assert 'font = "16px Arial"' in js

    def test_draw_path(self):
        js = to_js('Draw "path" points "M10,10 L100,100" fill "#red"\n')
        assert 'Path2D("M10,10 L100,100")' in js
        assert 'fillStyle = "#red"' in js

    def test_draw_creates_canvas(self):
        js = to_js('Draw "rect" x 0 y 0 width 800 height 600 fill "#000"\n')
        assert 'createElement("canvas")' in js
        assert 'getContext("2d")' in js
