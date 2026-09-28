# Navigation Structure and Organization Reference (continued 3/3)

## Navigation Rules

### Nesting Rules

1. **One root-level element:** Choose tabs OR products OR simple groups
2. **One child type per level:** Groups can contain pages or groups, not both
3. **Max depth:** Limited nesting (typically 2-3 levels)

**Valid nesting:**
```json
{
  "navigation": [
    {
      "group": "API",
      "pages": [
        "api/overview",
        {
          "group": "Resources",
          "pages": ["api/users", "api/posts"]
        }
      ]
    }
  ]
}
```

**Invalid nesting:**
```json
{
  "navigation": [
    {
      "group": "API",
      "pages": [
        "api/overview",
        {
          "group": "Resources",
          "pages": [
            "api/users",
            {
              "group": "Nested too deep",
              "pages": ["api/deep"]
            }
          ]
        }
      ]
    }
  ]
}
```

### Path Consistency

Pages must match their organizational context:

```json
{
  "tabs": [
    {"name": "Docs", "url": "docs"},
    {"name": "API", "url": "api"}
  ],
  "products": [
    {"name": "Platform", "slug": "platform"}
  ],
  "versions": [
    {"name": "v2", "slug": "v2"}
  ],
  "languages": [
    {"name": "English", "slug": "en"}
  ],
  "navigation": [
    {
      "group": "Guide",
      "pages": ["api/platform/v2/en/introduction"],
      "tab": "API",
      "product": "platform",
      "version": "v2",
      "language": "en"
    }
  ]
}
```

Path structure: `{tab}/{product}/{version}/{language}/{page}`

## Drilldown Navigation

Enable multi-level expandable navigation.

```json
{
  "interaction": {
    "drilldown": true
  }
}
```

With drilldown enabled:
- Groups expand/collapse on click
- Deep nesting feels more navigable
- Better for complex documentation structures

## Icons

Use Font Awesome or Lucide icons in navigation.

### Font Awesome Icons

```json
{
  "icon": {
    "library": "fontawesome"
  },
  "navigation": [
    {
      "group": "Getting Started",
      "icon": "rocket",
      "pages": ["intro"]
    },
    {
      "group": "API Reference",
      "icon": "code",
      "pages": ["api"]
    }
  ]
}
```

Common Font Awesome icons:
- `rocket` - Getting started
- `book` - Documentation
- `code` - API reference
- `wrench` - Tools
- `star` - Features
- `shield` - Security
- `users` - Community
- `github` - GitHub
- `discord` - Discord

### Lucide Icons

```json
{
  "icon": {
    "library": "lucide"
  },
  "navigation": [
    {
      "group": "Guides",
      "icon": "book-open",
      "pages": ["guides"]
    },
    {
      "group": "Components",
      "icon": "layout",
      "pages": ["components"]
    }
  ]
}
```

Common Lucide icons:
- `book-open` - Guides
- `layout` - Components
- `terminal` - CLI
- `zap` - Quick start
- `shield-check` - Security
- `code-2` - API

## Complete Navigation Example

Full-featured navigation structure:

```json
{
  "icon": {
    "library": "fontawesome"
  },
  "tabs": [
    {
      "name": "Documentation",
      "url": "docs"
    },
    {
      "name": "API Reference",
      "url": "api",
      "icon": "code",
      "menu": [
        {"name": "v2.0", "url": "api/v2"},
        {"name": "v1.0", "url": "api/v1"}
      ]
    }
  ],
  "anchors": [
    {
      "name": "Community",
      "icon": "discord",
      "url": "https://discord.gg/example"
    },
    {
      "name": "GitHub",
      "icon": "github",
      "url": "https://github.com/example/repo"
    }
  ],
  "dropdowns": [
    {
      "name": "Resources",
      "icon": "book-open",
      "items": [
        {"name": "Blog", "url": "https://blog.example.com"},
        {"name": "Status", "url": "https://status.example.com"}
      ]
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "icon": "rocket",
      "pages": ["docs/introduction", "docs/quickstart"],
      "tab": "Documentation"
    },
    {
      "group": "Core Concepts",
      "icon": "book",
      "expanded": true,
      "pages": [
        "docs/concepts/overview",
        {
          "group": "Advanced",
          "pages": ["docs/concepts/architecture", "docs/concepts/security"]
        }
      ],
      "tab": "Documentation"
    },
    {
      "group": "Authentication",
      "icon": "shield",
      "pages": ["api/v2/auth/overview", "api/v2/auth/oauth"],
      "tab": "API Reference"
    },
    {
      "group": "Endpoints",
      "icon": "code",
      "pages": [
        {
          "group": "Users",
          "pages": ["api/v2/users/list", "api/v2/users/create"]
        },
        {
          "group": "Posts",
          "pages": ["api/v2/posts/list", "api/v2/posts/create"]
        }
      ],
      "tab": "API Reference"
    }
  ],
  "interaction": {
    "drilldown": true
  }
}
```
