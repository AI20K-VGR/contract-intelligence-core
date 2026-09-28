# Backend API Design (continued 2/3)

## GraphQL API Design

### Schema Definition

```graphql
type User {
  id: ID!
  email: String!
  name: String!
  posts: [Post!]!
  createdAt: DateTime!
}

type Post {
  id: ID!
  title: String!
  content: String!
  author: User!
  published: Boolean!
  createdAt: DateTime!
}

type Query {
  user(id: ID!): User
  users(limit: Int = 50, offset: Int = 0): [User!]!
  post(id: ID!): Post
  posts(authorId: ID, published: Boolean): [Post!]!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
  deleteUser(id: ID!): Boolean!

  createPost(input: CreatePostInput!): Post!
  publishPost(id: ID!): Post!
}

input CreateUserInput {
  email: String!
  name: String!
  password: String!
}

input UpdateUserInput {
  email: String
  name: String
}
```

### Queries

```graphql
# Flexible data fetching - client specifies exactly what they need
query {
  user(id: "123") {
    id
    name
    email
    posts {
      id
      title
      published
    }
  }
}

# With variables
query GetUser($userId: ID!) {
  user(id: $userId) {
    id
    name
    posts(published: true) {
      title
    }
  }
}
```

### Mutations

```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    id
    email
    name
    createdAt
  }
}

# Variables
{
  "input": {
    "email": "user@example.com",
    "name": "John Doe",
    "password": "SecurePass123!"
  }
}
```

### Resolvers (NestJS Example)

```typescript
@Resolver(() => User)
export class UserResolver {
  constructor(
    private userService: UserService,
    private postService: PostService,
  ) {}

  @Query(() => User, { nullable: true })
  async user(@Args('id') id: string) {
    return this.userService.findById(id);
  }

  @Query(() => [User])
  async users(
    @Args('limit', { defaultValue: 50 }) limit: number,
    @Args('offset', { defaultValue: 0 }) offset: number,
  ) {
    return this.userService.findAll({ limit, offset });
  }

  @Mutation(() => User)
  async createUser(@Args('input') input: CreateUserInput) {
    return this.userService.create(input);
  }

  // Field resolver - lazy load posts
  @ResolveField(() => [Post])
  async posts(@Parent() user: User) {
    return this.postService.findByAuthorId(user.id);
  }
}
```

### GraphQL Best Practices

1. **Avoid N+1 Problem** - Use DataLoader
```typescript
import DataLoader from 'dataloader';

const postLoader = new DataLoader(async (authorIds: string[]) => {
  const posts = await db.posts.findAll({ where: { authorId: authorIds } });
  return authorIds.map(id => posts.filter(p => p.authorId === id));
});

// In resolver
@ResolveField(() => [Post])
async posts(@Parent() user: User) {
  return this.postLoader.load(user.id);
}
```

2. **Pagination** - Relay-style cursor pagination
3. **Error Handling** - Return errors in response
4. **Depth Limiting** - Prevent deeply nested queries
5. **Query Complexity Analysis** - Limit expensive queries

## gRPC API Design

### Protocol Buffers Schema

```protobuf
syntax = "proto3";

package user;

service UserService {
  rpc GetUser (GetUserRequest) returns (User);
  rpc ListUsers (ListUsersRequest) returns (ListUsersResponse);
  rpc CreateUser (CreateUserRequest) returns (User);
  rpc UpdateUser (UpdateUserRequest) returns (User);
  rpc DeleteUser (DeleteUserRequest) returns (DeleteUserResponse);

  // Streaming
  rpc StreamUsers (StreamUsersRequest) returns (stream User);
}

message User {
  string id = 1;
  string email = 2;
  string name = 3;
  int64 created_at = 4;
}

message GetUserRequest {
  string id = 1;
}

message ListUsersRequest {
  int32 limit = 1;
  int32 offset = 2;
}

message ListUsersResponse {
  repeated User users = 1;
  int32 total = 2;
}

message CreateUserRequest {
  string email = 1;
  string name = 2;
  string password = 3;
}
```

### Implementation (Node.js)

```typescript
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';

const packageDefinition = protoLoader.loadSync('user.proto');
const userProto = grpc.loadPackageDefinition(packageDefinition).user;

// Server implementation
const server = new grpc.Server();

server.addService(userProto.UserService.service, {
  async getUser(call, callback) {
    const user = await userService.findById(call.request.id);
    callback(null, user);
  },

  async createUser(call, callback) {
    const user = await userService.create(call.request);
    callback(null, user);
  },

  async streamUsers(call) {
    const users = await userService.findAll();
    for (const user of users) {
      call.write(user);
    }
    call.end();
  },
});

server.bindAsync(
  '0.0.0.0:50051',
  grpc.ServerCredentials.createInsecure(),
  () => server.start()
);
```

### gRPC Benefits

- **Performance:** 7-10x faster than REST (binary protocol)
- **Streaming:** Bi-directional streaming
- **Type Safety:** Strong typing via Protocol Buffers
- **Code Generation:** Auto-generate client/server code
- **Best For:** Internal microservices, high-performance systems

## API Design Decision Matrix

| Feature | REST | GraphQL | gRPC |
|---------|------|---------|------|
| **Use Case** | Public APIs, CRUD | Flexible data fetching | Microservices, performance |
| **Performance** | Moderate | Moderate | Fastest (7-10x REST) |
| **Caching** | HTTP caching built-in | Complex | No built-in caching |
| **Browser Support** | Native | Native | Requires gRPC-Web |
| **Learning Curve** | Easy | Moderate | Steep |
| **Streaming** | Limited (SSE) | Subscriptions | Bi-directional |
| **Tooling** | Excellent | Excellent | Good |
| **Documentation** | OpenAPI/Swagger | Schema introspection | Protobuf definition |

## API Security Checklist

- [ ] HTTPS/TLS only (no HTTP)
- [ ] Authentication (OAuth 2.1, JWT, API keys)
- [ ] Authorization (RBAC, check permissions)
- [ ] Rate limiting (prevent abuse)
- [ ] Input validation (all endpoints)
- [ ] CORS configured properly
- [ ] Security headers (CSP, HSTS, X-Frame-Options)
- [ ] API versioning implemented
- [ ] Error messages don't leak system info
- [ ] Audit logging (who did what, when)


---

Continued in [backend-api-design-cont2.md](backend-api-design-cont2.md)
