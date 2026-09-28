# RemixIcon Integration Guide

Installation, usage, customization, and accessibility for RemixIcon library.

## Overview

RemixIcon provides 3,100+ icons in outlined (-line) and filled (-fill) styles, built on 24x24px grid.

**Icon naming:** `ri-{name}-{style}`
- Examples: `ri-home-line`, `ri-heart-fill`, `ri-search-line`

## Installation

### NPM Package

```bash
# npm
npm install remixicon

# yarn
yarn add remixicon

# pnpm
pnpm install remixicon

# bun
bun add remixicon
```

### React Package

```bash
npm install @remixicon/react
```

### Vue 3 Package

```bash
npm install @remixicon/vue
```

### CDN

```html
<link
  href="https://cdn.jsdelivr.net/npm/remixicon@4.7.0/fonts/remixicon.css"
  rel="stylesheet"
/>
```

## Usage Methods

### 1. Webfont (HTML/CSS)

Import CSS and use class names:

```tsx
// Next.js - app/layout.tsx
import 'remixicon/fonts/remixicon.css'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>{children}</body>
    </html>
  )
}

// Use in components
<i className="ri-home-line"></i>
<i className="ri-search-fill"></i>
```

**With sizing classes:**
```html
<i className="ri-home-line ri-2x"></i>    <!-- 2em -->
<i className="ri-search-line ri-lg"></i>  <!-- 1.33em -->
<i className="ri-heart-fill ri-xl"></i>   <!-- 1.5em -->
```

**Available sizes:**
- `ri-xxs` (0.5em)
- `ri-xs` (0.75em)
- `ri-sm` (0.875em)
- `ri-1x` (1em)
- `ri-lg` (1.33em)
- `ri-xl` (1.5em)
- `ri-2x` through `ri-10x`
- `ri-fw` (fixed width)

### 2. React Components

```tsx
import { RiHomeLine, RiSearchFill, RiHeartLine } from "@remixicon/react"

export function MyComponent() {
  return (
    <div>
      <RiHomeLine size={24} />
      <RiSearchFill size={32} color="blue" />
      <RiHeartLine size="1.5em" className="icon" />
    </div>
  )
}
```

**Props:**
- `size` - Number (pixels) or string (em, rem)
- `color` - CSS color value
- `className` - CSS class
- Standard SVG props (onClick, style, etc.)

### 3. Vue 3 Components

```vue
<script setup lang="ts">
import { RiHomeLine, RiSearchFill } from "@remixicon/vue"
</script>

<template>
  <div>
    <RiHomeLine :size="24" />
    <RiSearchFill :size="32" color="blue" />
  </div>
</template>
```

### 4. Direct SVG

```tsx
// Download SVG file and import
import HomeIcon from '@/icons/home-line.svg'

export function Component() {
  return <img src={HomeIcon} alt="Home" width={24} height={24} />
}
```

### 5. SVG Sprite

```html
<svg className="icon">
  <use xlinkHref="path/to/remixicon.symbol.svg#ri-home-line"></use>
</svg>
```

```css
.icon {
  width: 24px;
  height: 24px;
  fill: currentColor;
}
```

## Icon Categories

20 semantic categories with 3,100+ icons:

**Navigation & UI:**
- Arrows (arrow-left, arrow-right, arrow-up-down)
- System (settings, delete, add, close, more)
- Editor (bold, italic, link, list, code)

**Communication:**
- Communication (chat, phone, mail, message)
- User (user, account, team, contacts)

**Media & Content:**
- Media (play, pause, volume, camera, video)
- Document (file, folder, article, draft)
- Design (brush, palette, magic, crop)

**Business & Commerce:**
- Business (briefcase, pie-chart, bar-chart)
- Finance (money, wallet, bank-card, coin)
- Map (map, pin, compass, navigation)

**Objects & Places:**
- Buildings (home, bank, hospital, store)
- Device (phone, laptop, tablet, printer)
- Food (restaurant, cake, cup, knife)
- Weather (sun, cloud, rain, moon)

**Development & Logos:**
- Development (code, terminal, bug, git-branch)
- Logos (github, twitter, facebook, google)

**Health & Medical:**
- Health (heart-pulse, capsule, stethoscope)


---

Continued in [remix-icon-integration-cont.md](remix-icon-integration-cont.md)
