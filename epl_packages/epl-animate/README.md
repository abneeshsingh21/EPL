# epl-animate

Pre-built CSS animations for EPL web applications.

## Installation

```bash
epl install epl-animate
```

## Usage

Apply animations to any element using the `animate` attribute:

```epl
Import "epl-animate"

Create WebApp called app

Route "/" shows
    Page "Animated Page"
        Div with style "card" animate "fadeInUp"
            Heading "I fade in from below!"
        End

        Div animate "bounce"
            Text "I bounce in!"
        End

        Div animate "pulse"
            Text "I pulse continuously"
        End
    End
End
```

## Available Animations

### Fade
| Name | Description |
|------|-------------|
| `fadeIn` | Simple opacity fade in |
| `fadeOut` | Simple opacity fade out |
| `fadeInUp` | Fade in while sliding up |
| `fadeInDown` | Fade in while sliding down |
| `fadeInLeft` | Fade in from left |
| `fadeInRight` | Fade in from right |

### Slide
| Name | Description |
|------|-------------|
| `slideUp` | Slide up from bottom |
| `slideDown` | Slide down from top |
| `slideLeft` | Slide in from right |
| `slideRight` | Slide in from left |

### Bounce & Elastic
| Name | Description |
|------|-------------|
| `bounce` | Bouncy entrance |
| `bounceIn` | Quick bounce entrance |
| `elastic` | Elastic snap-in effect |

### Spin & Rotate
| Name | Description |
|------|-------------|
| `spin` | Continuous rotation (infinite) |
| `spinSlow` | Slow continuous rotation (3s, infinite) |
| `rotateIn` | Rotate in from -180deg |

### Pulse & Heartbeat
| Name | Description |
|------|-------------|
| `pulse` | Subtle scale pulse (infinite) |
| `heartbeat` | Double-beat pulse (infinite) |
| `ping` | Expanding ring effect (infinite) |

### Zoom
| Name | Description |
|------|-------------|
| `zoomIn` | Scale up from 50% |
| `zoomOut` | Scale down to 50% |

### Shake & Wobble
| Name | Description |
|------|-------------|
| `shake` | Horizontal shake |
| `wobble` | Rotational wobble |

### Flip
| Name | Description |
|------|-------------|
| `flipX` | 3D flip on X axis |
| `flipY` | 3D flip on Y axis |
