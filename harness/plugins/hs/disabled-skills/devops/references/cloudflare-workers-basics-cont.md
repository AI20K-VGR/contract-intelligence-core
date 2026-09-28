# Cloudflare Workers Basics (continued)

## Context API

### waitUntil (Background Tasks)
```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // Run analytics after response sent
    ctx.waitUntil(
      fetch('https://analytics.example.com/log', {
        method: 'POST',
        body: JSON.stringify({ url: request.url })
      })
    );

    return new Response('OK');
  }
};
```

### passThroughOnException
```typescript
// Continue to origin on error
ctx.passThroughOnException();

// Your code that might throw
const data = await riskyOperation();
```

## Error Handling

```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    try {
      const response = await processRequest(request, env);
      return response;
    } catch (error) {
      console.error('Error:', error);

      // Log to external service
      ctx.waitUntil(
        fetch('https://logging.example.com/error', {
          method: 'POST',
          body: JSON.stringify({
            error: error.message,
            url: request.url
          })
        })
      );

      return new Response('Internal Server Error', { status: 500 });
    }
  }
};
```

## CORS

```typescript
function corsHeaders(origin: string) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400'
  };
}

export default {
  async fetch(request: Request): Promise<Response> {
    const origin = request.headers.get('Origin') || '*';

    // Handle preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders(origin) });
    }

    // Handle request
    const response = await handleRequest(request);
    const headers = new Headers(response.headers);
    Object.entries(corsHeaders(origin)).forEach(([key, value]) => {
      headers.set(key, value);
    });

    return new Response(response.body, {
      status: response.status,
      headers
    });
  }
};
```

## Cache API

```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const cache = caches.default;
    const cacheKey = new Request(request.url);

    // Check cache
    let response = await cache.match(cacheKey);
    if (response) return response;

    // Fetch from origin
    response = await fetch(request);

    // Cache response
    ctx.waitUntil(cache.put(cacheKey, response.clone()));

    return response;
  }
};
```

## Secrets Management

```bash
# Add secret
wrangler secret put API_KEY
# Enter value when prompted

# Use in Worker
const apiKey = env.API_KEY;
```

## Local Development

```bash
# Start local dev server
wrangler dev

# Test with remote edge
wrangler dev --remote

# Custom port
wrangler dev --port 8080

# Access at http://localhost:8787
```

## Deployment

```bash
# Deploy to production
wrangler deploy

# Deploy to specific environment
wrangler deploy --env staging

# Preview deployment
wrangler deploy --dry-run
```

## Common Patterns

### API Gateway
```typescript
import { Hono } from 'hono';

const app = new Hono();

app.get('/api/users', async (c) => {
  const users = await c.env.DB.prepare('SELECT * FROM users').all();
  return c.json(users.results);
});

app.post('/api/users', async (c) => {
  const { name, email } = await c.req.json();
  await c.env.DB.prepare(
    'INSERT INTO users (name, email) VALUES (?, ?)'
  ).bind(name, email).run();
  return c.json({ success: true }, 201);
});

export default app;
```

### Rate Limiting
```typescript
async function rateLimit(ip: string, env: Env): Promise<boolean> {
  const key = `ratelimit:${ip}`;
  const limit = 100;
  const window = 60;

  const current = await env.KV.get(key);
  const count = current ? parseInt(current) : 0;

  if (count >= limit) return false;

  await env.KV.put(key, (count + 1).toString(), {
    expirationTtl: window
  });

  return true;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';

    if (!await rateLimit(ip, env)) {
      return new Response('Rate limit exceeded', { status: 429 });
    }

    return new Response('OK');
  }
};
```

## Resources

- Docs: https://developers.cloudflare.com/workers/
- Examples: https://developers.cloudflare.com/workers/examples/
- Runtime APIs: https://developers.cloudflare.com/workers/runtime-apis/
