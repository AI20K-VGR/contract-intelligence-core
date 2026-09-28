# AI Features and Integrations Reference (continued 2/3)

## MCP (Model Context Protocol)

Expose documentation via MCP for AI tools.

### What is MCP?

Protocol that allows AI tools to access and interact with documentation:
- Standardized interface
- Real-time doc access
- Function calling support
- Resource discovery

### Configuration

Enable MCP in `docs.json`:

```json
{
  "contextual": {
    "options": ["mcp"]
  },
  "ai": {
    "mcp": {
      "enabled": true,
      "endpoint": "/mcp",
      "capabilities": ["read", "search", "navigate"]
    }
  }
}
```

### MCP Capabilities

**Resources:**
- List all documentation pages
- Read page content
- Access metadata

**Search:**
- Full-text search
- Semantic search
- Filter by section

**Navigation:**
- Get navigation structure
- Find related pages
- Access breadcrumbs

### MCP Client Integration

**Claude Desktop:**
```json
{
  "mcpServers": {
    "docs": {
      "url": "https://docs.example.com/mcp",
      "apiKey": "optional-key"
    }
  }
}
```

**VSCode with Continue:**
```json
{
  "contextProviders": [
    {
      "name": "docs",
      "type": "mcp",
      "url": "https://docs.example.com/mcp"
    }
  ]
}
```

## Contextual Menu Options

Quick access to AI tools from doc pages.

### Configuration

```json
{
  "contextual": {
    "options": [
      "copy",
      "view",
      "chatgpt",
      "claude",
      "perplexity",
      "mcp",
      "cursor",
      "vscode"
    ]
  }
}
```

### Available Options

**copy** - Copy page content to clipboard
```
Copies: Markdown content with frontmatter
Use: Paste into any editor or tool
```

**view** - View raw markdown source
```
Opens: Raw .mdx file content
Use: See exact markdown structure
```

**chatgpt** - Open in ChatGPT
```
Action: Opens ChatGPT with page context
Prompt: "Explain this documentation: [content]"
```

**claude** - Open in Claude
```
Action: Opens Claude.ai with page context
Prompt: "Help me understand: [content]"
```

**perplexity** - Open in Perplexity
```
Action: Search Perplexity with page topic
Query: Key concepts from page
```

**mcp** - Copy MCP resource URI
```
Copies: MCP resource identifier
Use: Reference in MCP-enabled tools
```

**cursor** - Open in Cursor editor
```
Action: cursor://open?url=[page-url]
Use: Edit in Cursor IDE
```

**vscode** - Open in VS Code
```
Action: vscode://file/[local-path]
Use: Edit in VS Code
```

### Custom Options

Add custom contextual menu items:

```json
{
  "contextual": {
    "custom": [
      {
        "name": "Open in Notion",
        "icon": "notion",
        "url": "https://notion.so/import?url={pageUrl}"
      },
      {
        "name": "Translate",
        "icon": "language",
        "url": "https://translate.google.com/?text={content}"
      }
    ]
  }
}
```

## Discord Bot

AI-powered Discord bot for doc queries.

### Setup

1. **Enable Bot:**
   - Go to Mintlify dashboard
   - Navigate to Integrations > Discord
   - Click "Enable Discord Bot"

2. **Add to Server:**
   - Copy bot invite URL
   - Open in browser
   - Select Discord server
   - Authorize permissions

3. **Configure:**
   ```json
   {
     "integrations": {
       "discord": {
         "enabled": true,
         "channelIds": ["123456789", "987654321"],
         "prefix": "!docs",
         "permissions": ["read", "search"]
       }
     }
   }
   ```

### Usage

**Search Documentation:**
```
!docs search authentication
!docs how to create API key
!docs what is rate limiting
```

**Get Page:**
```
!docs page introduction
!docs link api/users
```

**Ask Questions:**
```
!docs What authentication methods are supported?
!docs How do I paginate results?
!docs Show me example of creating a user
```

### Bot Features

- Natural language search
- Code example formatting
- Inline documentation links
- Contextual answers
- Source citations
- Slash commands support


---

Continued in [ai-features-and-integrations-reference-cont2.md](ai-features-and-integrations-reference-cont2.md)
