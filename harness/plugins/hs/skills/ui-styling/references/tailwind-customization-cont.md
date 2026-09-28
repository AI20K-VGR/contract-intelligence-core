# Tailwind Customization (continued)

## @apply Directive

Extract repeated utility patterns:

```css
.btn-primary {
  @apply bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold px-6 py-3 rounded-lg shadow-md hover:shadow-lg transition-all duration-200 focus:outline-none focus:ring-4 focus:ring-blue-300;
}

.input-field {
  @apply w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed;
}

.section-container {
  @apply container mx-auto px-4 sm:px-6 lg:px-8 max-w-7xl;
}
```

**Usage:**
```html
<button class="btn-primary">Click me</button>
<input class="input-field" />
<div class="section-container">Content</div>
```

## Plugins

### Official Plugins

```bash
npm install -D @tailwindcss/typography @tailwindcss/forms @tailwindcss/container-queries
```

```javascript
// tailwind.config.js
export default {
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries'),
  ],
}
```

**Typography plugin:**
```html
<article class="prose lg:prose-xl">
  <h1>Styled article</h1>
  <p>Automatically styled prose content</p>
</article>
```

**Forms plugin:**
```html
<!-- Automatically styled form elements -->
<input type="text" />
<select></select>
<textarea></textarea>
```

### Custom Plugin

```javascript
// tailwind.config.js
const plugin = require('tailwindcss/plugin')

export default {
  plugins: [
    plugin(function({ addUtilities, addComponents, theme }) {
      // Add utilities
      addUtilities({
        '.text-shadow': {
          textShadow: '2px 2px 4px rgba(0, 0, 0, 0.1)',
        },
        '.text-shadow-lg': {
          textShadow: '4px 4px 8px rgba(0, 0, 0, 0.2)',
        },
      })

      // Add components
      addComponents({
        '.card-custom': {
          backgroundColor: theme('colors.white'),
          borderRadius: theme('borderRadius.lg'),
          padding: theme('spacing.6'),
          boxShadow: theme('boxShadow.md'),
        },
      })
    }),
  ],
}
```

## Configuration Examples

### Complete Tailwind Config

```javascript
// tailwind.config.ts
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        brand: {
          50: '#f0f9ff',
          500: '#3b82f6',
          900: '#1e3a8a',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Playfair Display', 'serif'],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "slide-in": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(0)" },
        },
      },
      animation: {
        "slide-in": "slide-in 0.5s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
```

## Dark Mode Configuration

```javascript
// tailwind.config.js
export default {
  darkMode: ["class"],  // or "media" for automatic
  // ...
}
```

**Usage:**
```html
<!-- Class-based -->
<html class="dark">
  <div class="bg-white dark:bg-gray-900">
    Responds to .dark class
  </div>
</html>

<!-- Media query-based -->
<div class="bg-white dark:bg-gray-900">
  Responds to system preference automatically
</div>
```

## Content Configuration

Specify files to scan for classes:

```javascript
// tailwind.config.js
export default {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
    "./pages/**/*.{js,jsx,ts,tsx}",
  ],
  // ...
}
```

### Safelist

Preserve dynamic classes:

```javascript
export default {
  safelist: [
    'bg-red-500',
    'bg-green-500',
    'bg-blue-500',
    {
      pattern: /bg-(red|green|blue)-(100|500|900)/,
    },
  ],
}
```

## Best Practices

1. **Use @theme for simple customizations**: Prefer CSS-based customization
2. **Extract components sparingly**: Use @apply only for truly repeated patterns
3. **Leverage design tokens**: Define custom tokens in @theme
4. **Layer organization**: Keep base, components, and utilities separate
5. **Plugin for complex logic**: Use plugins for advanced customizations
6. **Test dark mode**: Ensure custom colors work in both themes
7. **Document custom utilities**: Add comments explaining custom classes
8. **Semantic naming**: Use descriptive names (primary not blue)
