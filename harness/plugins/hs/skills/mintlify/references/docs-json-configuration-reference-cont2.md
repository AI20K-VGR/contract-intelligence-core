# docs.json Configuration Reference (continued 3/3)

## Search

```json
{
  "search": {
    "prompt": "Ask me anything..."
  }
}
```

## Error Pages

```json
{
  "errors": {
    "404": {
      "redirect": "/introduction",
      "title": "Page Not Found",
      "description": "The page you're looking for doesn't exist."
    }
  }
}
```

## Contextual Menu

```json
{
  "contextual": {
    "options": ["copy", "view", "chatgpt", "claude", "perplexity", "mcp", "cursor", "vscode"]
  }
}
```

Options:
- `copy` - Copy page content
- `view` - View raw markdown
- `chatgpt` - Open in ChatGPT
- `claude` - Open in Claude
- `perplexity` - Open in Perplexity
- `mcp` - Model Context Protocol integration
- `cursor` - Open in Cursor editor
- `vscode` - Open in VS Code

## API Configuration

```json
{
  "api": {
    "openapi": "/openapi.yaml",
    "asyncapi": "/asyncapi.yaml",
    "params": {
      "expanded": true
    },
    "playground": {
      "display": "interactive",    // "interactive" | "simple" | "none"
      "proxy": "https://api.example.com"
    },
    "examples": {
      "languages": ["bash", "python", "javascript", "go"],
      "defaults": {
        "bash": "curl",
        "python": "requests"
      },
      "prefill": {
        "apiKey": "your-api-key"
      },
      "autogenerate": true
    }
  }
}
```

## SEO

```json
{
  "seo": {
    "metatags": [
      {
        "name": "keywords",
        "content": "documentation, api, guide"
      }
    ],
    "indexing": "navigable"        // "navigable" | "all"
  }
}
```

## Integrations

### Analytics

```json
{
  "integrations": {
    "ga4": {
      "measurementId": "G-XXXXXXXXXX"
    },
    "posthog": {
      "apiKey": "phc_xxxx",
      "apiHost": "https://app.posthog.com"
    },
    "amplitude": {
      "apiKey": "xxx"
    },
    "clarity": {
      "projectId": "xxx"
    },
    "fathom": {
      "siteId": "xxx"
    },
    "gtm": {
      "tagId": "GTM-XXXXXXX"
    },
    "heap": {
      "appId": "xxx"
    },
    "hotjar": {
      "siteId": "xxx"
    },
    "logrocket": {
      "appId": "xxx/project"
    },
    "mixpanel": {
      "projectToken": "xxx"
    },
    "pirsch": {
      "code": "xxx"
    },
    "plausible": {
      "domain": "docs.example.com"
    }
  }
}
```

### Support

```json
{
  "integrations": {
    "intercom": {
      "appId": "xxx"
    },
    "front": {
      "chatId": "xxx"
    }
  }
}
```

### Marketing

```json
{
  "integrations": {
    "segment": {
      "writeKey": "xxx"
    },
    "hightouch": {
      "sourceId": "xxx"
    },
    "clearbit": {
      "publicKey": "xxx"
    }
  }
}
```

### Privacy

```json
{
  "integrations": {
    "osano": {
      "customerId": "xxx",
      "configId": "xxx"
    },
    "cookies": {
      "necessary": ["analytics"],
      "optional": ["marketing"]
    }
  }
}
```

### Telemetry

```json
{
  "integrations": {
    "telemetry": {
      "enabled": false
    }
  }
}
```

## Redirects

```json
{
  "redirects": [
    {
      "source": "/old-page",
      "destination": "/new-page",
      "permanent": true
    },
    {
      "source": "/docs/:slug*",
      "destination": "/documentation/:slug*"
    }
  ]
}
```

## Complete Example

```json
{
  "theme": "mint",
  "name": "Acme Docs",
  "description": "Documentation for Acme products",
  "logo": {
    "light": "/logo/light.svg",
    "dark": "/logo/dark.svg"
  },
  "favicon": "/favicon.svg",
  "colors": {
    "primary": "#0D9373",
    "light": "#55D799",
    "dark": "#007A5A"
  },
  "navbar": {
    "links": [
      {"name": "Blog", "url": "https://blog.acme.com"}
    ],
    "primary": {
      "type": "github",
      "url": "https://github.com/acme/docs"
    }
  },
  "tabs": [
    {"name": "Docs", "url": "docs"},
    {"name": "API", "url": "api", "icon": "code"}
  ],
  "anchors": [
    {"name": "Community", "icon": "discord", "url": "https://discord.gg/acme"}
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["docs/introduction", "docs/quickstart"],
      "tab": "Docs"
    },
    {
      "group": "Endpoints",
      "pages": ["api/users", "api/posts"],
      "tab": "API"
    }
  ],
  "footer": {
    "socials": {
      "twitter": "https://twitter.com/acme",
      "github": "https://github.com/acme"
    }
  },
  "api": {
    "openapi": "/openapi.yaml",
    "playground": {
      "display": "interactive"
    }
  },
  "integrations": {
    "ga4": {
      "measurementId": "G-XXXXXXXXXX"
    }
  }
}
```
