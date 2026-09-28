# Architecture & Customization

## Architecture

```
scripts/
├── server.cjs               # Main entry point
└── lib/
    ├── port-finder.cjs      # Dynamic port allocation
    ├── process-mgr.cjs      # PID file management
    ├── http-server.cjs      # Core HTTP routing (/view, /browse)
    ├── markdown-renderer.cjs # MD→HTML conversion
    └── plan-navigator.cjs   # Plan detection & nav

assets/
├── template.html            # Markdown viewer template
├── reader.js                # Client-side interactivity
├── novel-theme.css          # Main theme file (imports modules)
├── directory-browser.css    # Directory browser styles
└── styles/                  # Modular CSS architecture
    ├── novel-theme-variables.css  # CSS custom properties (colors, spacing)
    ├── novel-theme-base.css       # Base colors, fonts, reset
    ├── novel-theme-header.css     # Auto-hide header, progress bar
    ├── novel-theme-sidebar.css    # Accordion sidebar, status badges
    ├── novel-theme-content.css    # Headings, paragraphs, lists, code, tables, links
    ├── novel-theme-components.css # Reusable UI components
    ├── novel-theme-mermaid.css    # Mermaid diagram styling
    ├── novel-theme-overlays.css   # Toast, cheatsheet modal
    └── novel-theme-responsive.css # Responsive/breakpoint rules
```


## Customization

### Theme Colors (CSS Variables)

Light mode variables in `assets/novel-theme.css`:
```css
--bg-primary: #faf8f3;      /* Warm cream */
--accent: #8b4513;          /* Saddle brown */
```

Dark mode:
```css
--bg-primary: #1a1a1a;      /* Near black */
--accent: #d4a574;          /* Warm gold */
```

### Content Width
```css
--content-width: 720px;
```

## Remote Access

From another device on your network:

```bash
# Start with 0.0.0.0 to bind to all interfaces
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/markdown-novel-viewer/scripts/server.cjs --file ./README.md --host 0.0.0.0 --port 3456
```

With `--host 0.0.0.0`, server auto-detects local network IP, includes it in output:

```json
{
  "success": true,
  "url": "http://localhost:3456/view?file=...",
  "networkUrl": "http://192.168.2.75:3456/view?file=...",
  "port": 3456
}
```

Use `networkUrl` for other devices on the same network.

