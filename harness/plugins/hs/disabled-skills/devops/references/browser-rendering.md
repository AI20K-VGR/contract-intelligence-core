# Cloudflare Browser Rendering

Headless browser automation with Puppeteer/Playwright on Cloudflare Workers.

## Setup

**wrangler.toml:**
```toml
name = "browser-worker"
main = "src/index.ts"
compatibility_date = "2024-01-01"

browser = { binding = "MYBROWSER" }
```

## Basic Screenshot Worker

```typescript
import puppeteer from '@cloudflare/puppeteer';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const browser = await puppeteer.launch(env.MYBROWSER);
    const page = await browser.newPage();

    await page.goto('https://example.com', { waitUntil: 'networkidle2' });
    const screenshot = await page.screenshot({ type: 'png' });

    await browser.close();

    return new Response(screenshot, {
      headers: { 'Content-Type': 'image/png' }
    });
  }
};
```

## Session Reuse (Cost Optimization)

```typescript
// Disconnect instead of close
await browser.disconnect();

// Retrieve and reconnect
const sessions = await puppeteer.sessions(env.MYBROWSER);
const freeSession = sessions.find(s => !s.connectionId);

if (freeSession) {
  const browser = await puppeteer.connect(env.MYBROWSER, freeSession.sessionId);
}
```

## PDF Generation

```typescript
const browser = await puppeteer.launch(env.MYBROWSER);
const page = await browser.newPage();

await page.setContent(`
  <!DOCTYPE html>
  <html>
    <head>
      <style>
        body { font-family: Arial; padding: 50px; }
        h1 { color: #2c3e50; }
      </style>
    </head>
    <body>
      <h1>Certificate</h1>
      <p>Awarded to: <strong>John Doe</strong></p>
    </body>
  </html>
`);

const pdf = await page.pdf({
  format: 'A4',
  printBackground: true,
  margin: { top: '1cm', right: '1cm', bottom: '1cm', left: '1cm' }
});

await browser.close();

return new Response(pdf, {
  headers: { 'Content-Type': 'application/pdf' }
});
```

## Durable Objects for Persistent Sessions

```typescript
export class Browser {
  state: DurableObjectState;
  browser: any;
  lastUsed: number;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.lastUsed = Date.now();
  }

  async fetch(request: Request, env: Env) {
    if (!this.browser) {
      this.browser = await puppeteer.launch(env.MYBROWSER);
    }

    this.lastUsed = Date.now();
    await this.state.storage.setAlarm(Date.now() + 10000);

    const page = await this.browser.newPage();
    const url = new URL(request.url).searchParams.get('url');
    await page.goto(url);
    const screenshot = await page.screenshot();
    await page.close();

    return new Response(screenshot, {
      headers: { 'Content-Type': 'image/png' }
    });
  }

  async alarm() {
    if (Date.now() - this.lastUsed > 60000) {
      await this.browser?.close();
      this.browser = null;
    } else {
      await this.state.storage.setAlarm(Date.now() + 10000);
    }
  }
}
```

## AI-Powered Web Scraper

```typescript
import { Ai } from '@cloudflare/ai';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const browser = await puppeteer.launch(env.MYBROWSER);
    const page = await browser.newPage();
    await page.goto('https://news.ycombinator.com');
    const content = await page.content();
    await browser.close();

    const ai = new Ai(env.AI);
    const response = await ai.run('@cf/meta/llama-3-8b-instruct', {
      messages: [
        {
          role: 'system',
          content: 'Extract top 5 article titles and URLs as JSON'
        },
        { role: 'user', content: content }
      ]
    });

    return Response.json(response);
  }
};
```

> Continued in `references/browser-rendering-cont.md`.
