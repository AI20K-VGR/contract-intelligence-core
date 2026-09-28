# docs.json Configuration Reference (continued 2/3)

## Navigation

### Basic Structure

```json
{
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["introduction", "quickstart"]
    },
    {
      "group": "API Reference",
      "pages": [
        "api/overview",
        {
          "group": "Endpoints",
          "pages": ["api/users", "api/posts"]
        }
      ]
    }
  ]
}
```

### Tabs

```json
{
  "tabs": [
    {
      "name": "Documentation",
      "url": "docs"
    },
    {
      "name": "API Reference",
      "url": "api",
      "icon": "code"
    }
  ],
  "navigation": [
    {
      "group": "Docs",
      "pages": ["docs/intro"],
      "tab": "Documentation"
    },
    {
      "group": "Endpoints",
      "pages": ["api/users"],
      "tab": "API Reference"
    }
  ]
}
```

### Anchors

Global navigation anchors:

```json
{
  "anchors": [
    {
      "name": "Community",
      "icon": "discord",
      "url": "https://discord.gg/example"
    },
    {
      "name": "Blog",
      "icon": "newspaper",
      "url": "https://blog.example.com"
    }
  ]
}
```

### Dropdowns

```json
{
  "dropdowns": [
    {
      "name": "Resources",
      "icon": "book",
      "items": [
        {
          "name": "Blog",
          "url": "https://blog.example.com"
        },
        {
          "name": "Community",
          "url": "https://discord.gg/example"
        }
      ]
    }
  ]
}
```

### Products

Partition documentation into multiple products:

```json
{
  "products": [
    {
      "name": "Product A",
      "slug": "product-a",
      "icon": "rocket"
    },
    {
      "name": "Product B",
      "slug": "product-b",
      "icon": "star"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["intro"],
      "product": "product-a"
    },
    {
      "group": "Setup",
      "pages": ["setup"],
      "product": "product-b"
    }
  ]
}
```

### Versions

Manage multiple documentation versions:

```json
{
  "versions": [
    {
      "name": "v2.0",
      "slug": "v2"
    },
    {
      "name": "v1.0",
      "slug": "v1"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["v2/intro"],
      "version": "v2"
    },
    {
      "group": "Getting Started",
      "pages": ["v1/intro"],
      "version": "v1"
    }
  ]
}
```

### Languages

Support 28+ locales:

```json
{
  "languages": [
    {
      "name": "English",
      "slug": "en"
    },
    {
      "name": "Español",
      "slug": "es"
    },
    {
      "name": "Français",
      "slug": "fr"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["en/intro"],
      "language": "en"
    },
    {
      "group": "Primeros Pasos",
      "pages": ["es/intro"],
      "language": "es"
    }
  ]
}
```

**Supported locales:** en, es, fr, de, it, pt, pt-BR, zh, zh-TW, ja, ko, ru, ar, hi, nl, pl, tr, sv, da, no, fi, cs, hu, ro, th, vi, id, ms

### Menus

Dropdown menus within tabs:

```json
{
  "tabs": [
    {
      "name": "Docs",
      "url": "docs",
      "menu": [
        {
          "name": "v2.0",
          "url": "docs/v2"
        },
        {
          "name": "v1.0",
          "url": "docs/v1"
        }
      ]
    }
  ]
}
```

## Interaction

```json
{
  "interaction": {
    "drilldown": true              // Enable multi-level navigation
  }
}
```

## Metadata

```json
{
  "metadata": {
    "timestamp": "last-modified"   // Show last modified date
  }
}
```

## Footer

```json
{
  "footer": {
    "socials": {
      "twitter": "https://twitter.com/example",
      "github": "https://github.com/example",
      "discord": "https://discord.gg/example",
      "linkedin": "https://linkedin.com/company/example"
    },
    "links": [
      {
        "name": "Privacy Policy",
        "url": "https://example.com/privacy"
      },
      {
        "name": "Terms of Service",
        "url": "https://example.com/terms"
      }
    ]
  }
}
```

## Banner

```json
{
  "banner": {
    "content": "We're launching v2.0! [Read more →](/blog/v2)",
    "dismissible": true
  }
}
```

Supports MDX formatting in content.


---

Continued in [docs-json-configuration-reference-cont2.md](docs-json-configuration-reference-cont2.md)
