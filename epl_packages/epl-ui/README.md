# epl-ui

Production-grade UI component library for EPL web applications.

## Installation

```bash
epl install epl-ui
```

## Components

| Component | Props | Description |
|-----------|-------|-------------|
| `Card` | title, content | Elevated card with shadow and rounded corners |
| `Navbar` | brand, links | Sticky navigation bar with brand and link area |
| `Hero` | title, subtitle | Full-width gradient hero section |
| `Footer` | text, links | Dark footer with link sections |
| `Alert` | message, variant | Contextual alert (info, success, warning, error) |
| `Badge` | label | Small status badge (success, warning, danger) |
| `StatCard` | value, label | Dashboard stat with large number and label |

## Styles

All styles are prefixed with `epl-` to avoid conflicts:

- `epl-card`, `epl-card-hover` — Card containers
- `epl-navbar`, `epl-navbar-brand`, `epl-navbar-links`, `epl-navbar-link` — Navigation
- `epl-hero`, `epl-hero-title`, `epl-hero-subtitle` — Hero sections
- `epl-btn`, `epl-btn-primary`, `epl-btn-secondary`, `epl-btn-danger` — Buttons
- `epl-modal-overlay`, `epl-modal`, `epl-modal-header` — Modal dialogs
- `epl-footer`, `epl-footer-links`, `epl-footer-link` — Footer
- `epl-badge`, `epl-badge-success`, `epl-badge-warning`, `epl-badge-danger` — Badges
- `epl-alert-info`, `epl-alert-success`, `epl-alert-warning`, `epl-alert-error` — Alerts
- `epl-table`, `epl-table-header`, `epl-table-cell` — Data tables
- `epl-tabs`, `epl-tab`, `epl-tab-active` — Tab navigation
- `epl-input`, `epl-input-group`, `epl-input-label` — Form inputs
- `epl-sidebar`, `epl-sidebar-item`, `epl-sidebar-item-active` — Sidebar navigation
- `epl-stat-card`, `epl-stat-value`, `epl-stat-label` — Dashboard stats
- `epl-pricing-card`, `epl-pricing-featured`, `epl-pricing-price` — Pricing tables
- `epl-avatar`, `epl-avatar-lg` — User avatars
- `epl-divider` — Section dividers

## Usage

```epl
Import "epl-ui"

Create WebApp called myApp

Route "/" shows
    Page "Dashboard"
        Hero title "Welcome Back" subtitle "Your dashboard overview"

        Grid columns 4 gap "24px"
            StatCard value "1,234" label "Total Users"
            StatCard value "$45.2K" label "Revenue"
            StatCard value "98.5%" label "Uptime"
            StatCard value "3.2s" label "Avg Response"
        End

        Div with style "epl-card"
            Heading "Recent Activity"
            Text "Your latest updates appear here."
        End
    End
End
```
