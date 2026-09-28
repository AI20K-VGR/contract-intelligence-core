# AI Features and Integrations Reference

Guide for Mintlify's AI-powered features: AI assistant, llms.txt, MCP, automation.

## AI Assistant

Built-in AI assistant for doc search and Q&A.

### Configuration

Enable AI assistant in `docs.json`:

```json
{
  "search": {
    "prompt": "Ask me anything about our documentation..."
  }
}
```

### Features

**Conversational Search:**
- Natural language queries
- Context-aware responses
- Source citations from docs
- Follow-up questions

**Capabilities:**
- Search across all documentation
- Answer technical questions
- Provide code examples
- Navigate to relevant pages
- Suggest related content

### Customization

**Custom Prompt:**
```json
{
  "search": {
    "prompt": "How can I help you with the API?",
    "placeholder": "Ask about authentication, endpoints, or SDKs..."
  }
}
```

**Search Scope:**
```json
{
  "search": {
    "scope": ["api", "guides"],
    "exclude": ["internal", "deprecated"]
  }
}
```

## llms.txt

Optimize docs for LLM consumption and indexing.

### What is llms.txt?

File format that makes documentation machine-readable for AI models:
- Structured content for LLMs
- Optimized token usage
- Hierarchical organization
- Metadata for context

### Auto-Generation

Mintlify automatically generates `llms.txt` from your documentation.

**Access:** `https://docs.example.com/llms.txt`

### Manual Configuration

Customize llms.txt generation:

```json
{
  "ai": {
    "llmsTxt": {
      "enabled": true,
      "include": ["introduction", "api/*", "guides/*"],
      "exclude": ["internal/*", "deprecated/*"],
      "format": "structured"
    }
  }
}
```

### llms.txt Format

Generated file structure:

```
# Product Name Documentation

## Overview
Brief description of product and documentation

## Getting Started
> /introduction
Quick introduction to get started

> /quickstart
Step-by-step quickstart guide

## API Reference
> /api/authentication
Authentication methods and API keys

> /api/users
User management endpoints

> /api/posts
Post creation and management

## Guides
> /guides/deployment
Deployment guide for production

> /guides/security
Security best practices
```

### Use Cases

**Feed to LLMs:**
- Provide entire docs context to ChatGPT, Claude, etc.
- Enable AI to answer questions about your product
- Generate code examples based on documentation

**RAG Systems:**
- Index for retrieval-augmented generation
- Build custom AI assistants
- Create documentation chatbots

## skill.md

Make docs agent-ready with skill definitions.

### What is skill.md?

Defines your API/product as a "skill" that AI agents can execute:
- Function signatures
- Parameter schemas
- Authentication requirements
- Example usage

### Generation

Mintlify auto-generates `skill.md` from OpenAPI specs.

**Access:** `https://docs.example.com/skill.md`

### Format

```markdown
# API Skills

## Create User

Create a new user account

**Function:** `createUser`

**Parameters:**
- `email` (string, required) - User email address
- `name` (string, required) - Full name
- `password` (string, required) - Password (min 8 chars)

**Returns:** User object with ID and timestamps

**Example:**
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "SecurePass123"
}
```

**Response:**
```json
{
  "id": "usr_abc123",
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## List Users

Retrieve paginated list of users

**Function:** `listUsers`

**Parameters:**
- `page` (number, optional) - Page number (default: 1)
- `limit` (number, optional) - Items per page (default: 10)
- `sort` (string, optional) - Sort field (default: created_at)

**Returns:** Array of user objects with pagination metadata
```

### Configuration

Customize skill.md generation:

```json
{
  "ai": {
    "skillMd": {
      "enabled": true,
      "includeExamples": true,
      "includeErrors": true,
      "format": "agent-ready"
    }
  }
}
```

### Use Cases

**AI Agents:**
- Claude Code, Cursor, Windsurf
- Auto-discover API capabilities
- Generate correct API calls
- Handle errors appropriately

**Documentation Tools:**
- Auto-complete in IDEs
- API client generation
- Testing frameworks


---

Continued in [ai-features-and-integrations-reference-cont.md](ai-features-and-integrations-reference-cont.md)
