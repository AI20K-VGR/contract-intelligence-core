# API Documentation Components Reference (continued 4/4)

## SDK Integration

### Speakeasy SDK

Integrate Speakeasy-generated SDKs.

```mdx
---
title: "Create User"
openapi: "POST /users"
---

<CodeGroup>
```typescript TypeScript SDK
import { SDK } from '@company/sdk';

const sdk = new SDK({ apiKey: 'YOUR_API_KEY' });

const user = await sdk.users.create({
  email: 'user@example.com',
  name: 'John Doe'
});
```

```python Python SDK
from company_sdk import SDK

sdk = SDK(api_key='YOUR_API_KEY')

user = sdk.users.create(
    email='user@example.com',
    name='John Doe'
)
```
</CodeGroup>
```

### Stainless SDK

Integrate Stainless-generated SDKs.

```mdx
<CodeGroup>
```typescript TypeScript SDK
import { CompanyAPI } from 'company-api';

const client = new CompanyAPI({
  apiKey: process.env.COMPANY_API_KEY
});

const user = await client.users.create({
  email: 'user@example.com',
  name: 'John Doe'
});
```
</CodeGroup>
```

## Complete API Endpoint Example

Full example of documented API endpoint.

```mdx
---
title: "Create User"
description: "Create a new user account"
openapi: "POST /users"
---

Creates a new user with the provided information. Email must be unique.

## Request

<ParamField body="email" type="string" required>
  User's email address (must be unique)
</ParamField>

<ParamField body="name" type="string" required>
  Full name of the user
</ParamField>

<ParamField body="password" type="string" required>
  User's password (minimum 8 characters)
</ParamField>

<ParamField body="role" type="string" default="user" enum={["user", "admin", "moderator"]}>
  User's role in the system
</ParamField>

## Response

<ResponseField name="id" type="string" required>
  Unique identifier of the created user
</ResponseField>

<ResponseField name="email" type="string" required>
  User's email address
</ResponseField>

<ResponseField name="name" type="string" required>
  User's full name
</ResponseField>

<ResponseField name="role" type="string" required>
  User's assigned role
</ResponseField>

<ResponseField name="created_at" type="timestamp" required>
  ISO 8601 timestamp of creation
</ResponseField>

<RequestExample>
```bash cURL
curl -X POST https://api.example.com/users \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "name": "John Doe",
    "password": "SecurePass123",
    "role": "user"
  }'
```

```python Python
import requests

response = requests.post(
    "https://api.example.com/users",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "email": "john@example.com",
        "name": "John Doe",
        "password": "SecurePass123",
        "role": "user"
    }
)
```
</RequestExample>

<ResponseExample>
```json Success (201)
{
  "id": "usr_abc123",
  "email": "john@example.com",
  "name": "John Doe",
  "role": "user",
  "created_at": "2024-01-15T10:30:00Z"
}
```

```json Error (400)
{
  "error": {
    "code": "validation_error",
    "message": "Email already exists",
    "field": "email"
  }
}
```
</ResponseExample>
```
