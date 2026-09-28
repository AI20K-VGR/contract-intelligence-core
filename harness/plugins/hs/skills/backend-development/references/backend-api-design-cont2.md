# Backend API Design (continued 3/3)

## API Documentation

### OpenAPI/Swagger (REST)

```yaml
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /api/v1/users:
    get:
      summary: List users
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/User'
components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
        email:
          type: string
        name:
          type: string
```

## Resources

- **REST Best Practices:** https://restfulapi.net/
- **GraphQL:** https://graphql.org/learn/
- **gRPC:** https://grpc.io/docs/
- **OpenAPI:** https://swagger.io/specification/
