# Cloudflare Workers Basics

Cloudflare Workers: serverless functions on edge network, 300+ cities.

## Handler Types

### Fetch Handler (HTTP Requests)
```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    return new Response('Hello World!');
  }
};
```

### Scheduled Handler (Cron Jobs)
```typescript
export default {
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    await fetch('https://api.example.com/cleanup');
  }
};
```

**Configure in wrangler.toml:**
```toml
[triggers]
crons = ["0 0 * * *"]  # Daily at midnight
```

### Queue Handler (Message Processing)
```typescript
export default {
  async queue(batch: MessageBatch, env: Env, ctx: ExecutionContext): Promise<void> {
    for (const message of batch.messages) {
      await processMessage(message.body);
      message.ack();  // Acknowledge success
    }
  }
};
```

### Email Handler (Email Routing)
```typescript
export default {
  async email(message: ForwardableEmailMessage, env: Env, ctx: ExecutionContext): Promise<void> {
    await message.forward('destination@example.com');
  }
};
```

## Request/Response Basics

### Parsing Request
```typescript
const url = new URL(request.url);
const method = request.method;
const headers = request.headers;

// Query parameters
const name = url.searchParams.get('name');

// JSON body
const data = await request.json();

// Text body
const text = await request.text();

// Form data
const formData = await request.formData();
```

### Creating Response
```typescript
// Text response
return new Response('Hello', { status: 200 });

// JSON response
return new Response(JSON.stringify({ message: 'Hello' }), {
  status: 200,
  headers: { 'Content-Type': 'application/json' }
});

// Stream response
return new Response(readable, {
  headers: { 'Content-Type': 'text/plain' }
});

// Redirect
return Response.redirect('https://example.com', 302);
```

## Routing Patterns

### URL-Based Routing
```typescript
export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    switch (url.pathname) {
      case '/':
        return new Response('Home');
      case '/about':
        return new Response('About');
      default:
        return new Response('Not Found', { status: 404 });
    }
  }
};
```

### Using Hono Framework (Recommended)
```typescript
import { Hono } from 'hono';

const app = new Hono();

app.get('/', (c) => c.text('Home'));
app.get('/api/users/:id', async (c) => {
  const id = c.req.param('id');
  const user = await getUser(id);
  return c.json(user);
});

export default app;
```

## Working with Bindings

### Environment Variables
```toml
# wrangler.toml
[vars]
API_URL = "https://api.example.com"
```

```typescript
const apiUrl = env.API_URL;
```

### KV Namespace
```typescript
// Put with TTL
await env.KV.put('session:token', JSON.stringify(data), {
  expirationTtl: 3600
});

// Get
const data = await env.KV.get('session:token', 'json');

// Delete
await env.KV.delete('session:token');

// List with prefix
const list = await env.KV.list({ prefix: 'user:123:' });
```

### D1 Database
```typescript
// Query
const result = await env.DB.prepare(
  'SELECT * FROM users WHERE id = ?'
).bind(userId).first();

// Insert
await env.DB.prepare(
  'INSERT INTO users (name, email) VALUES (?, ?)'
).bind('Alice', 'alice@example.com').run();

// Batch (atomic)
await env.DB.batch([
  env.DB.prepare('UPDATE accounts SET balance = balance - 100 WHERE id = ?').bind(1),
  env.DB.prepare('UPDATE accounts SET balance = balance + 100 WHERE id = ?').bind(2)
]);
```

### R2 Bucket
```typescript
// Put object
await env.R2_BUCKET.put('path/to/file.jpg', fileBuffer, {
  httpMetadata: {
    contentType: 'image/jpeg'
  }
});

// Get object
const object = await env.R2_BUCKET.get('path/to/file.jpg');
if (!object) {
  return new Response('Not found', { status: 404 });
}

// Stream response
return new Response(object.body, {
  headers: {
    'Content-Type': object.httpMetadata?.contentType || 'application/octet-stream'
  }
});

// Delete
await env.R2_BUCKET.delete('path/to/file.jpg');
```

> Continued in `references/cloudflare-workers-basics-cont.md`.
