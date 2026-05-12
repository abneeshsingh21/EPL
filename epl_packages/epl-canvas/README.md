# epl-canvas

Enhanced 2D canvas drawing system for EPL. Build games, visualizations, and pixel art.

## Installation

```bash
epl install epl-canvas
```

## Usage

```epl
Import "epl-canvas"

Page "My Game"
    Div with style "canvas-game"
        Draw "rect" x 0 y 0 width 800 height 600 fill "#1a1a2e"
        Draw "rect" x 350 y 500 width 100 height 20 fill "#4CAF50"
        Draw "circle" x 400 y 300 radius 10 fill "#ff0000"
        Draw "text" x 10 y 30 content "Score: 100" font "20px monospace" fill "#fff"
    End
End
```

## Draw Commands

| Shape | Properties |
|-------|-----------|
| `rect` | x, y, width, height, fill, stroke |
| `circle` | x, y, radius, fill, stroke |
| `line` | x1, y1, x2, y2, stroke, width |
| `text` | x, y, content, font, fill |
| `path` | points (SVG path), fill, stroke |

## Styles

- **Containers**: `canvas-container`, `canvas-game`, `canvas-pixel-art`, `canvas-fullscreen`
- **Palettes**: `palette-retro`, `palette-neon`, `palette-pastel`, `palette-cyberpunk`
- **Game UI**: `game-hud`, `game-score`, `game-overlay`, `game-button`

## Animations

- `sprite-walk` — Frame-based walk cycle
- `sprite-jump` — Jump arc
- `sprite-idle` — Idle breathing
- `particle-burst` — Particle explosion
- `screen-shake` — Camera shake effect
