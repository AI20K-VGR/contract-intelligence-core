# API Documentation Components Reference (continued 2/4)

## ResponseField Component

Document API response fields with type information.

### Basic Response Fields

```mdx
<ResponseField name="id" type="string" required>
  Unique identifier of the user
</ResponseField>

<ResponseField name="email" type="string" required>
  User's email address
</ResponseField>

<ResponseField name="created_at" type="timestamp" required>
  ISO 8601 timestamp of when the user was created
</ResponseField>

<ResponseField name="is_verified" type="boolean" default="false">
  Whether the user's email has been verified
</ResponseField>
```

### Nested Response Objects

```mdx
<ResponseField name="user" type="object">
  User information object

  <Expandable title="user properties">
    <ResponseField name="id" type="string" required>
      User ID
    </ResponseField>
    <ResponseField name="name" type="string" required>
      Full name
    </ResponseField>
    <ResponseField name="email" type="string" required>
      Email address
    </ResponseField>
    <ResponseField name="profile" type="object">
      Extended profile information

      <Expandable title="profile properties">
        <ResponseField name="bio" type="string">
          User biography
        </ResponseField>
        <ResponseField name="avatar_url" type="string">
          Profile picture URL
        </ResponseField>
        <ResponseField name="location" type="string">
          User's location
        </ResponseField>
      </Expandable>
    </ResponseField>
  </Expandable>
</ResponseField>
```

### Array Responses

```mdx
<ResponseField name="users" type="array">
  Array of user objects

  <Expandable title="user object properties">
    <ResponseField name="id" type="string">
      User ID
    </ResponseField>
    <ResponseField name="name" type="string">
      User name
    </ResponseField>
    <ResponseField name="email" type="string">
      Email address
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="meta" type="object">
  Pagination metadata

  <Expandable title="meta properties">
    <ResponseField name="page" type="number">
      Current page number
    </ResponseField>
    <ResponseField name="per_page" type="number">
      Items per page
    </ResponseField>
    <ResponseField name="total" type="number">
      Total number of items
    </ResponseField>
  </Expandable>
</ResponseField>
```

## Request Examples

Show API request examples in multiple programming languages.

### Basic Request Example

```mdx
<RequestExample>
```bash cURL
curl -X GET https://api.example.com/users/123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

```python Python
import requests

response = requests.get(
    "https://api.example.com/users/123",
    headers={"Authorization": "Bearer YOUR_API_KEY"}
)

print(response.json())
```

```javascript JavaScript
const response = await fetch("https://api.example.com/users/123", {
  method: "GET",
  headers: {
    "Authorization": "Bearer YOUR_API_KEY"
  }
});

const data = await response.json();
console.log(data);
```

```go Go
package main

import (
    "fmt"
    "io"
    "net/http"
)

func main() {
    client := &http.Client{}
    req, _ := http.NewRequest("GET", "https://api.example.com/users/123", nil)
    req.Header.Set("Authorization", "Bearer YOUR_API_KEY")

    resp, _ := client.Do(req)
    defer resp.Body.Close()

    body, _ := io.ReadAll(resp.Body)
    fmt.Println(string(body))
}
```
</RequestExample>
```

### POST Request with Body

```mdx
<RequestExample>
```bash cURL
curl -X POST https://api.example.com/users \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "name": "John Doe",
    "age": 30
  }'
```

```python Python
import requests

data = {
    "email": "user@example.com",
    "name": "John Doe",
    "age": 30
}

response = requests.post(
    "https://api.example.com/users",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json=data
)

print(response.json())
```

```javascript JavaScript
const data = {
  email: "user@example.com",
  name: "John Doe",
  age: 30
};

const response = await fetch("https://api.example.com/users", {
  method: "POST",
  headers: {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
  },
  body: JSON.stringify(data)
});

const result = await response.json();
console.log(result);
```

```ruby Ruby
require 'net/http'
require 'json'

uri = URI('https://api.example.com/users')
request = Net::HTTP::Post.new(uri)
request['Authorization'] = 'Bearer YOUR_API_KEY'
request['Content-Type'] = 'application/json'
request.body = {
  email: 'user@example.com',
  name: 'John Doe',
  age: 30
}.to_json

response = Net::HTTP.start(uri.hostname, uri.port, use_ssl: true) do |http|
  http.request(request)
end

puts response.body
```
</RequestExample>
```


---

Continued in [api-documentation-components-reference-cont2.md](api-documentation-components-reference-cont2.md)
