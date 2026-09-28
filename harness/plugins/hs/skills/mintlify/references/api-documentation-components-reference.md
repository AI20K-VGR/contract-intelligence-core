# API Documentation Components Reference

Guide for documenting APIs with Mintlify using OpenAPI/AsyncAPI specs and API components.

## OpenAPI Integration

### Automatic Page Generation

Use OpenAPI frontmatter to auto-generate API docs from OpenAPI specs.

```mdx
---
title: "Get User"
openapi: "GET /users/{id}"
---
```

Mintlify automatically extracts:
- Request parameters (path, query, header, body)
- Request examples in multiple languages
- Response schemas
- Response examples
- Authentication requirements

### OpenAPI Configuration

Configure in `docs.json`:

```json
{
  "api": {
    "openapi": "/openapi.yaml",
    "params": {
      "expanded": true
    },
    "playground": {
      "display": "interactive",
      "proxy": "https://api.example.com"
    },
    "examples": {
      "languages": ["bash", "python", "javascript", "go", "ruby", "php", "java"],
      "defaults": {
        "bash": "curl",
        "python": "requests"
      },
      "prefill": {
        "apiKey": "your-api-key",
        "baseUrl": "https://api.example.com"
      },
      "autogenerate": true
    }
  }
}
```

**Configuration options:**
- `openapi` - Path to OpenAPI spec file (YAML or JSON)
- `params.expanded` - Expand parameter details by default
- `playground.display` - API playground mode (interactive, simple, none)
- `playground.proxy` - Proxy URL for API requests
- `examples.languages` - Supported code example languages
- `examples.defaults` - Default library per language
- `examples.prefill` - Pre-fill values in examples
- `examples.autogenerate` - Auto-generate examples from spec

### Multiple OpenAPI Specs

```json
{
  "api": {
    "openapi": [
      "/specs/v1.yaml",
      "/specs/v2.yaml"
    ]
  }
}
```

### OpenAPI Validation

```bash
mint openapi-check
```

Validates OpenAPI specs for:
- Syntax errors
- Schema compliance
- Missing required fields
- Invalid references

## AsyncAPI Integration

Document asynchronous APIs (WebSockets, message queues, event streams).

```json
{
  "api": {
    "asyncapi": "/asyncapi.yaml"
  }
}
```

Use in frontmatter:

```mdx
---
title: "User Events"
asyncapi: "subscribe user.created"
---
```

## ParamField Component

Document API parameters with detailed type information.

### Path Parameters

```mdx
<ParamField path="userId" type="string" required>
  The unique identifier of the user
</ParamField>

<ParamField path="postId" type="integer" required>
  The ID of the post to retrieve
</ParamField>
```

### Query Parameters

```mdx
<ParamField query="page" type="number" default="1">
  Page number for pagination (1-indexed)
</ParamField>

<ParamField query="limit" type="number" default="10">
  Number of items per page (max 100)
</ParamField>

<ParamField query="sort" type="string" default="created_at">
  Field to sort by
</ParamField>

<ParamField query="order" type="string" default="desc">
  Sort order (asc or desc)
</ParamField>
```

### Body Parameters

```mdx
<ParamField body="email" type="string" required>
  User's email address (must be unique)
</ParamField>

<ParamField body="name" type="string" required>
  Full name of the user
</ParamField>

<ParamField body="age" type="number">
  User's age (must be 18 or older)
</ParamField>

<ParamField body="settings" type="object">
  User preferences and settings
</ParamField>
```

### Header Parameters

```mdx
<ParamField header="Authorization" type="string" required>
  Bearer token for authentication

  Format: `Bearer YOUR_API_KEY`
</ParamField>

<ParamField header="Content-Type" type="string" default="application/json">
  Content type of the request body
</ParamField>

<ParamField header="X-Request-ID" type="string">
  Unique identifier for request tracing
</ParamField>
```

### Enum Parameters

```mdx
<ParamField
  query="status"
  type="string"
  default="active"
  enum={["active", "inactive", "pending", "suspended"]}
  enumDescriptions={{
    active: "User account is active and fully functional",
    inactive: "User account is temporarily disabled",
    pending: "User registration awaiting email verification",
    suspended: "User account suspended due to policy violation"
  }}
>
  Filter users by account status
</ParamField>
```

### Array Parameters

```mdx
<ParamField query="tags" type="array">
  Array of tag IDs to filter by

  Example: `?tags=1,2,3`
</ParamField>

<ParamField body="roles" type="string[]" required>
  Array of role identifiers to assign to the user
</ParamField>
```

### Nested Object Parameters

```mdx
<ParamField body="address" type="object">
  User's address information

  <Expandable title="address properties">
    <ParamField body="street" type="string" required>
      Street address
    </ParamField>
    <ParamField body="city" type="string" required>
      City name
    </ParamField>
    <ParamField body="state" type="string">
      State or province
    </ParamField>
    <ParamField body="postal_code" type="string" required>
      Postal/ZIP code
    </ParamField>
    <ParamField body="country" type="string" required>
      ISO 3166-1 alpha-2 country code
    </ParamField>
  </Expandable>
</ParamField>
```


---

Continued in [api-documentation-components-reference-cont.md](api-documentation-components-reference-cont.md)
