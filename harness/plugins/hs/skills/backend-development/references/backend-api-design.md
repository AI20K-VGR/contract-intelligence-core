# Backend API Design

Guide to designing RESTful, GraphQL, gRPC APIs — best practices (2025).

## REST API Design

### Resource-Based URLs

**Good:**
```
GET    /api/v1/users              # List users
GET    /api/v1/users/:id          # Get specific user
POST   /api/v1/users              # Create user
PUT    /api/v1/users/:id          # Update user (full)
PATCH  /api/v1/users/:id          # Update user (partial)
DELETE /api/v1/users/:id          # Delete user

GET    /api/v1/users/:id/posts    # Get user's posts
POST   /api/v1/users/:id/posts    # Create post for user
```

**Bad (Avoid):**
```
GET /api/v1/getUser?id=123        # RPC-style, not RESTful
POST /api/v1/createUser           # Verb in URL
GET /api/v1/user-posts            # Unclear relationship
```

### HTTP Status Codes (Meaningful Responses)

**Success:**
- `200 OK` - Successful GET, PUT, PATCH
- `201 Created` - Successful POST (resource created)
- `204 No Content` - Successful DELETE

**Client Errors:**
- `400 Bad Request` - Invalid input/validation error
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Authenticated but not authorized
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Resource conflict (duplicate email)
- `422 Unprocessable Entity` - Validation error (detailed)
- `429 Too Many Requests` - Rate limit exceeded

**Server Errors:**
- `500 Internal Server Error` - Generic server error
- `502 Bad Gateway` - Upstream service error
- `503 Service Unavailable` - Temporary downtime
- `504 Gateway Timeout` - Upstream service timeout

### Request/Response Format

**Request:**
```typescript
POST /api/v1/users
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "John Doe",
  "age": 30
}
```

**Success Response:**
```typescript
HTTP/1.1 201 Created
Content-Type: application/json
Location: /api/v1/users/123

{
  "id": "123",
  "email": "user@example.com",
  "name": "John Doe",
  "age": 30,
  "createdAt": "2025-01-09T12:00:00Z",
  "updatedAt": "2025-01-09T12:00:00Z"
}
```

**Error Response:**
```typescript
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "value": "invalid-email"
      },
      {
        "field": "age",
        "message": "Age must be between 18 and 120",
        "value": 15
      }
    ],
    "timestamp": "2025-01-09T12:00:00Z",
    "path": "/api/v1/users"
  }
}
```

### Pagination

```typescript
// Request
GET /api/v1/users?page=2&limit=50

// Response
{
  "data": [...],
  "pagination": {
    "page": 2,
    "limit": 50,
    "total": 1234,
    "totalPages": 25,
    "hasNext": true,
    "hasPrev": true
  },
  "links": {
    "first": "/api/v1/users?page=1&limit=50",
    "prev": "/api/v1/users?page=1&limit=50",
    "next": "/api/v1/users?page=3&limit=50",
    "last": "/api/v1/users?page=25&limit=50"
  }
}
```

### Filtering and Sorting

```
GET /api/v1/users?status=active&role=admin&sort=-createdAt,name&limit=20

# Filters: status=active AND role=admin
# Sort: createdAt DESC, name ASC
# Limit: 20 results
```

### API Versioning Strategies

**URL Versioning (Most Common):**
```
/api/v1/users
/api/v2/users
```

**Header Versioning:**
```
GET /api/users
Accept: application/vnd.myapi.v2+json
```

**Query Parameter:**
```
/api/users?version=2
```

**Recommendation:** URL versioning for simplicity and discoverability


---

Continued in [backend-api-design-cont.md](backend-api-design-cont.md)
