# RemixIcon Integration Guide (continued 3/3)

## Framework Integration

### Next.js

```tsx
// app/layout.tsx
import 'remixicon/fonts/remixicon.css'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>{children}</body>
    </html>
  )
}

// app/page.tsx
import { RiHomeLine } from "@remixicon/react"

export default function Page() {
  return <RiHomeLine size={24} />
}
```

### Tailwind CSS

```tsx
<i className="ri-home-line text-2xl text-blue-500"></i>

<RiHomeLine size={24} className="text-blue-500 hover:text-blue-600" />
```

### CSS Modules

```tsx
import styles from './component.module.css'
import 'remixicon/fonts/remixicon.css'

export function Component() {
  return <i className={`ri-home-line ${styles.icon}`}></i>
}
```

## Performance Considerations

### Webfont (Recommended for Multiple Icons)

**Pros:**
- Single HTTP request
- All icons available
- Easy to use

**Cons:**
- 179KB WOFF2 file
- Loads all icons even if unused

**Best for:** Apps using 10+ different icons

### Individual SVG (Recommended for Few Icons)

**Pros:**
- Only load what you need
- Smallest bundle size
- Tree-shakeable with React package

**Cons:**
- Multiple imports

**Best for:** Apps using 1-5 icons

### React/Vue Package

**Pros:**
- Tree-shakeable (only imports used icons)
- TypeScript support
- Component API

**Cons:**
- Slightly larger than raw SVG
- Requires React/Vue

**Best for:** React/Vue apps with TypeScript

## Troubleshooting

### Icons Not Displaying

**Check CSS import:**
```tsx
import 'remixicon/fonts/remixicon.css'
```

**Verify class name:**
```html
<!-- Correct -->
<i className="ri-home-line"></i>

<!-- Incorrect -->
<i className="ri-home"></i>
<i className="home-line"></i>
```

**Check font loading:**
```css
/* Ensure font-family is applied */
[class^="ri-"], [class*=" ri-"] {
  font-family: "remixicon" !important;
}
```

### Icons Look Blurry

Use multiples of 24px for crisp rendering:

```tsx
// Good
<RiHomeLine size={24} />
<RiHomeLine size={48} />

// Bad (breaks pixel grid)
<RiHomeLine size={20} />
<RiHomeLine size={30} />
```

### Wrong Icon Size

**Set parent font-size:**
```css
.icon-container {
  font-size: 24px;
}
```

**Or use size prop:**
```tsx
<RiHomeLine size={24} />
```

## Best Practices

1. **Choose style consistently** - Use line or fill throughout app
2. **Maintain 24px grid** - Use sizes: 24, 48, 72, 96px
3. **Provide accessibility** - Add aria-labels to icon-only buttons
4. **Use currentColor** - Icons inherit text color by default
5. **Optimize bundle** - Use React package for tree-shaking
6. **Cache webfonts** - CDN or long cache headers
7. **Lazy load icons** - Dynamic import for heavy icon sets
8. **Test on devices** - Ensure icons scale properly
9. **Document usage** - Create icon component library
10. **Version lock** - Pin RemixIcon version for consistency

## Resources

- Website: https://remixicon.com
- GitHub: https://github.com/Remix-Design/RemixIcon
- React Package: @remixicon/react
- Vue Package: @remixicon/vue
- License: Apache 2.0
- Total Icons: 3,100+
- Current Version: 4.7.0
