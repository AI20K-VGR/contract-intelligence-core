# Cloudflare Workers Apis (continued)

## FormData API

```typescript
// Parse form data
const formData = await request.formData();
const name = formData.get('name');
const file = formData.get('file');

// Create form data
const form = new FormData();
form.append('name', 'value');
form.append('file', blob, 'filename.txt');
```

## Response Types

```typescript
// Text
return new Response('Hello');

// JSON
return Response.json({ message: 'Hello' });

// Stream
return new Response(readable);

// Redirect
return Response.redirect('https://example.com', 302);

// Error
return new Response('Not Found', { status: 404 });
```

## Request Cloning

```typescript
// Clone for multiple reads
const clone = request.clone();
const body1 = await request.json();
const body2 = await clone.json();
```

## AbortController

```typescript
const controller = new AbortController();
const { signal } = controller;

setTimeout(() => controller.abort(), 5000);

try {
  const response = await fetch('https://slow-api.com', { signal });
} catch (error) {
  if (error.name === 'AbortError') {
    console.log('Request timed out');
  }
}
```

## Scheduling APIs

```typescript
// setTimeout
const timeoutId = setTimeout(() => {
  console.log('Delayed');
}, 1000);

// setInterval
const intervalId = setInterval(() => {
  console.log('Repeated');
}, 1000);

// Clear
clearTimeout(timeoutId);
clearInterval(intervalId);
```

## Console API

```typescript
console.log('Info message');
console.error('Error message');
console.warn('Warning message');
console.debug('Debug message');

// Structured logging
console.log(JSON.stringify({
  level: 'info',
  message: 'Request processed',
  url: request.url,
  timestamp: new Date().toISOString()
}));
```

## Performance API

```typescript
const start = performance.now();
await processRequest();
const duration = performance.now() - start;
console.log(`Processed in ${duration}ms`);
```

## Bindings Reference

### KV Operations
```typescript
await env.KV.put(key, value, { expirationTtl: 3600, metadata: { userId: '123' } });
const value = await env.KV.get(key, 'json');
const { value, metadata } = await env.KV.getWithMetadata(key);
await env.KV.delete(key);
const list = await env.KV.list({ prefix: 'user:' });
```

### D1 Operations
```typescript
const result = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(userId).first();
const { results } = await env.DB.prepare('SELECT * FROM users').all();
await env.DB.prepare('INSERT INTO users (name) VALUES (?)').bind(name).run();
await env.DB.batch([stmt1, stmt2, stmt3]);
```

### R2 Operations
```typescript
await env.R2.put(key, value, { httpMetadata: { contentType: 'image/jpeg' } });
const object = await env.R2.get(key);
await env.R2.delete(key);
const list = await env.R2.list({ prefix: 'uploads/' });
const multipart = await env.R2.createMultipartUpload(key);
```

### Queue Operations
```typescript
await env.QUEUE.send({ type: 'email', to: 'user@example.com' });
await env.QUEUE.sendBatch([{ body: msg1 }, { body: msg2 }]);
```

### Workers AI
```typescript
const response = await env.AI.run('@cf/meta/llama-3-8b-instruct', {
  messages: [{ role: 'user', content: 'What is edge computing?' }]
});
```

## Resources

- Runtime APIs: https://developers.cloudflare.com/workers/runtime-apis/
- Web Standards: https://developers.cloudflare.com/workers/runtime-apis/web-standards/
- Bindings: https://developers.cloudflare.com/workers/runtime-apis/bindings/
