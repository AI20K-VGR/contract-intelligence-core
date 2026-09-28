# Browser Rendering (continued)

## Crawler with Queues

```typescript
export default {
  async queue(batch: MessageBatch<any>, env: Env): Promise<void> {
    const browser = await puppeteer.launch(env.MYBROWSER);

    for (const message of batch.messages) {
      const page = await browser.newPage();
      await page.goto(message.body.url);

      const links = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('a')).map(a => a.href);
      });

      for (const link of links) {
        await env.QUEUE.send({ url: link });
      }

      await page.close();
      message.ack();
    }

    await browser.close();
  }
};
```

## Configuration

### Timeout
```typescript
await page.goto(url, {
  timeout: 60000,  // 60 seconds max
  waitUntil: 'networkidle2'
});

await page.waitForSelector('.content', { timeout: 45000 });
```

### Viewport
```typescript
await page.setViewport({ width: 1920, height: 1080 });
```

### Screenshot Options
```typescript
const screenshot = await page.screenshot({
  type: 'png',       // 'png' | 'jpeg' | 'webp'
  quality: 90,       // JPEG/WebP only
  fullPage: true,    // Full scrollable page
  clip: {            // Crop
    x: 0, y: 0,
    width: 800,
    height: 600
  }
});
```

## Limits & Pricing

### Free Plan
- 10 minutes/day
- 3 concurrent browsers
- 3 new browsers/minute

### Paid Plan
- 10 hours/month included
- 30 concurrent browsers
- 30 new browsers/minute
- $0.09/hour overage
- $2.00/concurrent browser overage

### Cost Optimization
1. Use `disconnect()` instead of `close()`
2. Enable Keep-Alive (10 min max)
3. Pool tabs with browser contexts
4. Cache auth state with KV
5. Implement Durable Objects cleanup

## Best Practices

### Session Management
- Always use `disconnect()` for reuse
- Implement session pooling
- Track session IDs and states

### Performance
- Cache content in KV
- Use browser contexts vs multiple browsers
- Choose appropriate `waitUntil` strategy
- Set realistic timeouts

### Error Handling
- Handle timeout errors gracefully
- Check session availability before connecting
- Validate responses before caching

### Security
- Validate user-provided URLs
- Implement authentication
- Sanitize extracted content
- Set appropriate CORS headers

## Troubleshooting

**Timeout Errors:**
```typescript
await page.goto(url, {
  timeout: 60000,
  waitUntil: 'domcontentloaded'  // Faster than networkidle2
});
```

**Memory Issues:**
```typescript
await page.close();  // Close pages
await browser.disconnect();  // Reuse session
```

**Font Rendering:**
Supported fonts (Noto Sans, Roboto, etc.) or inject custom:
```html
<link href="https://fonts.googleapis.com/css2?family=Poppins" rel="stylesheet">
```

## Key Methods

### Puppeteer
- `puppeteer.launch(binding)` - Start browser
- `puppeteer.connect(binding, sessionId)` - Reconnect
- `puppeteer.sessions(binding)` - List sessions
- `browser.newPage()` - Create page
- `browser.disconnect()` - Disconnect (keep alive)
- `browser.close()` - Close (terminate)
- `page.goto(url, options)` - Navigate
- `page.screenshot(options)` - Capture
- `page.pdf(options)` - Generate PDF
- `page.content()` - Get HTML
- `page.evaluate(fn)` - Execute JS

## Resources

- Docs: https://developers.cloudflare.com/browser-rendering/
- Puppeteer: https://pptr.dev/
- Examples: https://developers.cloudflare.com/workers/examples/
