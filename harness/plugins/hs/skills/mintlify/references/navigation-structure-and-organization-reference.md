# Navigation Structure and Organization Reference

Guide for organizing documentation with Mintlify's navigation system.

## Navigation Hierarchy

Mintlify supports complex navigation with multiple organizational patterns.

### Basic Navigation

Simple page groups:

```json
{
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["introduction", "quickstart", "installation"]
    },
    {
      "group": "Core Concepts",
      "pages": ["concepts/overview", "concepts/architecture"]
    }
  ]
}
```

### Group Properties

```json
{
  "navigation": [
    {
      "group": "API Reference",
      "icon": "code",
      "tag": "New",
      "expanded": false,
      "pages": ["api/overview", "api/authentication"]
    }
  ]
}
```

**Properties:**
- `group` - Group title (required)
- `icon` - Icon from Font Awesome or Lucide
- `tag` - Badge text (e.g., "New", "Beta", "Deprecated")
- `expanded` - Expand group by default (boolean)
- `pages` - Array of page paths or nested groups (required)

## Pages

Reference MDX files without extension.

```json
{
  "navigation": [
    {
      "group": "Guides",
      "pages": [
        "guides/getting-started",
        "guides/authentication",
        "guides/deployment"
      ]
    }
  ]
}
```

**File mapping:**
- `"introduction"` → `/introduction.mdx`
- `"api/users"` → `/api/users.mdx`
- `"guides/quickstart"` → `/guides/quickstart.mdx`

## Nested Groups

Groups can contain nested groups (one level of nesting).

```json
{
  "navigation": [
    {
      "group": "API Reference",
      "pages": [
        "api/overview",
        {
          "group": "Users",
          "pages": ["api/users/list", "api/users/create", "api/users/get"]
        },
        {
          "group": "Posts",
          "pages": ["api/posts/list", "api/posts/create", "api/posts/get"]
        }
      ]
    }
  ]
}
```

## Tabs

Organize documentation into major sections with tabs.

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
    },
    {
      "name": "Guides",
      "url": "guides",
      "icon": "book"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["docs/introduction", "docs/quickstart"],
      "tab": "Documentation"
    },
    {
      "group": "Endpoints",
      "pages": ["api/users", "api/posts"],
      "tab": "API Reference"
    },
    {
      "group": "Tutorials",
      "pages": ["guides/auth", "guides/deploy"],
      "tab": "Guides"
    }
  ]
}
```

**Tab properties:**
- `name` - Tab display name (required)
- `url` - URL path segment (required)
- `icon` - Tab icon

**Important:** Page paths must match tab URL:
- Tab `"url": "api"` → pages must start with `api/`
- Tab `"url": "docs"` → pages must start with `docs/`

## Menus

Dropdown menus within tabs for version/variant switching.

```json
{
  "tabs": [
    {
      "name": "Documentation",
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

## Anchors

Global navigation anchors for external links.

### Global Anchors

Appear in top-level navigation:

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
    },
    {
      "name": "GitHub",
      "icon": "github",
      "url": "https://github.com/example/repo"
    },
    {
      "name": "Status",
      "icon": "activity",
      "url": "https://status.example.com"
    }
  ]
}
```

### Local Anchors

Anchors within specific tabs:

```json
{
  "tabs": [
    {
      "name": "API Reference",
      "url": "api"
    }
  ],
  "anchors": [
    {
      "name": "API Status",
      "icon": "activity",
      "url": "https://status.example.com/api",
      "tab": "API Reference"
    }
  ]
}
```

## Dropdowns

Top-level dropdown menus for resources.

```json
{
  "dropdowns": [
    {
      "name": "Resources",
      "icon": "book-open",
      "items": [
        {
          "name": "Blog",
          "url": "https://blog.example.com"
        },
        {
          "name": "Changelog",
          "url": "https://example.com/changelog"
        },
        {
          "name": "Status Page",
          "url": "https://status.example.com"
        },
        {
          "name": "Support",
          "url": "https://support.example.com"
        }
      ]
    },
    {
      "name": "Tools",
      "icon": "wrench",
      "items": [
        {
          "name": "API Explorer",
          "url": "https://api-explorer.example.com"
        },
        {
          "name": "SDK Generator",
          "url": "https://sdk.example.com"
        }
      ]
    }
  ]
}
```


---

Continued in [navigation-structure-and-organization-reference-cont.md](navigation-structure-and-organization-reference-cont.md)
