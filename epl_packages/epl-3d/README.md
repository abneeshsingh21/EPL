# epl-3d

Declarative 3D scene system for EPL, powered by Three.js.

## Installation

```bash
epl install epl-3d
```

## Usage

```epl
Import "epl-3d"

Page "3D Demo"
    Div with style "scene-container"
        Scene "myScene" width 800 height 600
            Camera position 0, 5, 10 look_at 0, 0, 0 fov 75
            Light "ambient" color "#ffffff" intensity 0.4
            Light "directional" color "#ffffff" intensity 0.8 position 5, 10, 5
            Mesh "cube" position 0, 0, 0 color "#667eea"
            Mesh "sphere" position 3, 1, 0 color "#f093fb"
        End
    End
End
```

## Features

- **Scene Styles**: `scene-container`, `scene-fullscreen`, `scene-card`
- **Material Presets**: `material-metallic`, `material-glass`, `material-neon`, `material-gold`, `material-hologram`
- **Lighting Presets**: `lighting-studio`, `lighting-sunset`, `lighting-night`, `lighting-underwater`
- **3D Animations**: `rotate3d`, `float3d`, `pulse3d`, `orbit`
- **Demo Scenes**: `demo-cube`, `demo-solar`, `demo-landscape`

## Mesh Types

- `cube` — Box geometry
- `sphere` — Sphere geometry
- `plane` — Flat plane
- `cylinder` — Cylinder geometry
- `cone` — Cone geometry
- `torus` — Donut shape

## Properties

Each mesh supports: `position`, `rotation`, `scale`, `color`, `material`
