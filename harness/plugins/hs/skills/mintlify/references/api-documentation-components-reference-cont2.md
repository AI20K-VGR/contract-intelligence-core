# API Documentation Components Reference (continued 3/4)

## Response Examples

Show API response examples for different scenarios.

### Success and Error Responses

```mdx
<ResponseExample>
```json Success (200)
{
  "id": "usr_abc123",
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2024-01-15T10:30:00Z",
  "is_verified": true
}
```

```json Error (400)
{
  "error": {
    "code": "validation_error",
    "message": "Invalid email format",
    "details": {
      "field": "email",
      "value": "invalid-email"
    }
  }
}
```

```json Error (401)
{
  "error": {
    "code": "unauthorized",
    "message": "Invalid or expired API key"
  }
}
```

```json Error (404)
{
  "error": {
    "code": "not_found",
    "message": "User with ID 'usr_abc123' not found"
  }
}
```
</ResponseExample>
```

### Paginated Response

```mdx
<ResponseExample>
```json Success (200)
{
  "data": [
    {
      "id": "usr_001",
      "name": "Alice Smith",
      "email": "alice@example.com"
    },
    {
      "id": "usr_002",
      "name": "Bob Jones",
      "email": "bob@example.com"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 10,
    "total": 45,
    "total_pages": 5
  },
  "links": {
    "first": "https://api.example.com/users?page=1",
    "last": "https://api.example.com/users?page=5",
    "next": "https://api.example.com/users?page=2",
    "prev": null
  }
}
```
</ResponseExample>
```

## API Playground

Interactive API playground modes.

### Interactive Mode (default)

Full interactive playground with request builder and live testing.

```json
{
  "api": {
    "playground": {
      "display": "interactive"
    }
  }
}
```

Features:
- Live API requests from browser
- Parameter input fields
- Authentication management
- Response preview
- Copy as code snippets

### Simple Mode

Simplified playground with basic request/response display.

```json
{
  "api": {
    "playground": {
      "display": "simple"
    }
  }
}
```

### Disabled Playground

Hide playground completely.

```json
{
  "api": {
    "playground": {
      "display": "none"
    }
  }
}
```

### Playground Proxy

Route API requests through proxy server (bypass CORS).

```json
{
  "api": {
    "playground": {
      "proxy": "https://cors-proxy.example.com"
    }
  }
}
```

## Code Example Languages

Configure supported languages for code examples.

```json
{
  "api": {
    "examples": {
      "languages": [
        "bash",
        "python",
        "javascript",
        "typescript",
        "go",
        "ruby",
        "php",
        "java",
        "swift",
        "csharp",
        "kotlin",
        "rust"
      ]
    }
  }
}
```

### Default Libraries

Set default library/method per language.

```json
{
  "api": {
    "examples": {
      "defaults": {
        "bash": "curl",
        "python": "requests",
        "javascript": "fetch",
        "go": "http"
      }
    }
  }
}
```

### Prefill Values

Pre-fill common values in code examples.

```json
{
  "api": {
    "examples": {
      "prefill": {
        "apiKey": "sk_test_abc123",
        "baseUrl": "https://api.example.com",
        "userId": "usr_example"
      }
    }
  }
}
```

Values replace placeholders in examples:
- `{apiKey}` → `sk_test_abc123`
- `{baseUrl}` → `https://api.example.com`
- `{userId}` → `usr_example`

### Auto-generate Examples

Automatically generate code examples from OpenAPI spec.

```json
{
  "api": {
    "examples": {
      "autogenerate": true
    }
  }
}
```


---

Continued in [api-documentation-components-reference-cont3.md](api-documentation-components-reference-cont3.md)
