# docs.json Configuration Reference

Reference for Mintlify's `docs.json` configuration file.

## Required Fields

```json
{
  "theme": "mint",
  "name": "Documentation Name",
  "colors": {
    "primary": "#0D9373"
  },
  "navigation": []
}
```

## Theme

Choose from 7 available themes:

- `mint` - Default, clean design
- `maple` - Warm, professional
- `palm` - Light, airy
- `willow` - Nature-inspired
- `linden` - Modern, minimal
- `almond` - Soft, neutral
- `aspen` - Bold, contemporary

## Branding

```json
{
  "logo": {
    "light": "/logo/light.svg",
    "dark": "/logo/dark.svg",
    "href": "https://example.com"
  },
  "favicon": "/favicon.svg",
  "name": "Product Name",
  "description": "Brief description for SEO",
  "thumbnails": {
    "og:image": "/images/og.png",
    "twitter:image": "/images/twitter.png"
  }
}
```

## Colors

```json
{
  "colors": {
    "primary": "#0D9373",
    "light": "#55D799",
    "dark": "#007A5A",
    "background": {
      "light": "#FFFFFF",
      "dark": "#0F1117"
    }
  }
}
```

## Styling

```json
{
  "eyebrows": "section",         // "section" | "breadcrumbs"
  "latex": true,                 // Enable LaTeX math rendering
  "codeblocks": {
    "theme": {
      "light": "github-light",
      "dark": "github-dark"
    }
  }
}
```

**Shiki themes:** github-light, github-dark, min-light, min-dark, nord, one-dark-pro, poimandres, rose-pine, slack-dark, slack-ochin, solarized-dark, solarized-light, vitesse-dark, vitesse-light

## Icons

```json
{
  "icon": {
    "library": "fontawesome"     // "fontawesome" | "lucide"
  }
}
```

## Fonts

```json
{
  "font": {
    "headings": "Inter",
    "body": "Inter",
    "code": "Fira Code"
  }
}
```

Use any Google Font name. Custom fonts loaded automatically.

## Appearance

```json
{
  "modeToggle": {
    "default": "light",          // "light" | "dark"
    "isHidden": false
  }
}
```

## Background

```json
{
  "background": {
    "image": "/images/background.png",
    "decoration": "grid",         // "grid" | "gradient" | "none"
    "color": "#FFFFFF"
  }
}
```

## Navbar

```json
{
  "navbar": {
    "links": [
      {
        "name": "Blog",
        "url": "https://example.com/blog"
      }
    ],
    "primary": {
      "type": "button",           // "button" | "github"
      "label": "Get Started",
      "url": "https://example.com/signup"
    }
  }
}
```

For GitHub:
```json
{
  "navbar": {
    "primary": {
      "type": "github",
      "url": "https://github.com/user/repo"
    }
  }
}
```


---

Continued in [docs-json-configuration-reference-cont.md](docs-json-configuration-reference-cont.md)
