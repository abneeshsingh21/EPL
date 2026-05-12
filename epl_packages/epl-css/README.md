# epl-css

Tailwind-inspired utility CSS classes for EPL web applications.

## Installation

```bash
epl install epl-css
```

## Usage

```epl
Import "epl-css"

Create WebApp called app

Route "/" shows
    Page "Home"
        Div class "p-8 bg-white rounded-xl shadow-lg"
            Heading "Hello World"
            Text "Styled with utility classes"
        End
        
        Flex direction "row" gap "16px"
            Div class "flex-1 p-4 bg-gray-50 rounded-lg"
                Text "Column 1"
            End
            Div class "flex-1 p-4 bg-gray-50 rounded-lg"
                Text "Column 2"
            End
        End
    End
End
```

## Available Utilities

### Spacing
`p-0` through `p-12`, `px-4`, `py-4`, `m-0` through `m-6`, `m-auto`, `mb-2` through `mb-8`, `mt-4`, `mt-8`

### Typography
`text-xs` through `text-5xl`, `font-light` through `font-extrabold`, `text-center`, `text-left`, `text-right`, `uppercase`, `capitalize`, `italic`, `underline`, `truncate`

### Colors
Text: `text-white`, `text-black`, `text-gray-*`, `text-blue-*`, `text-green-*`, `text-red-*`, `text-purple-*`
Background: `bg-white`, `bg-gray-*`, `bg-blue-*`, `bg-green-*`, `bg-red-*`, `bg-gradient-*`

### Layout
`w-full`, `h-full`, `h-screen`, `max-w-*`, `hidden`, `block`, `inline-block`, `flex-row`, `flex-col`, `items-center`, `justify-center`, `justify-between`, `gap-*`, `flex-wrap`, `flex-1`, `relative`, `absolute`, `fixed`, `sticky`

### Borders & Shadows
`rounded` through `rounded-full`, `border`, `border-2`, `border-none`, `shadow-sm` through `shadow-xl`

### Transitions
`transition`, `transition-fast`, `transition-slow`, `cursor-pointer`, `select-none`, `opacity-*`
