# Social Photos — Screenshot Export

Export tooling split out of `social-photos-design.md` to keep that guide bounded.

### Step 5: Screenshot Export

Use Chrome headless, `hs:agent-browser`, or Playwright/Puppeteer to capture exact-size screenshots.

**IMPORTANT:** Always add a delay (3-5s) after page load for fonts/images to fully render before capture.

#### Option A: Chrome Headless CLI (Recommended — zero dependencies)

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DELAY=5  # seconds for fonts/images to load

"$CHROME" \
  --headless \
  --disable-gpu \
  --no-sandbox \
  --hide-scrollbars \
  --window-size="${WIDTH},${HEIGHT}" \
  --virtual-time-budget=$((DELAY * 1000)) \
  --screenshot="output.png" \
  "file:///path/to/file.html"
```

Key flags:
- `--virtual-time-budget=5000` — waits 5s virtual time for assets (Google Fonts, images) to load
- `--hide-scrollbars` — prevents scrollbar artifacts in screenshots
- `--window-size=WxH` — sets exact pixel dimensions

#### Option B: hs:agent-browser

Invoke `/hs:agent-browser` with instructions to:
1. Open each HTML file in browser
2. Set viewport to exact target dimensions
3. Wait 3-5s for fonts/images to fully load
4. Screenshot full page to PNG
5. Save to `output/social-photos/exports/`

#### Option C: Playwright script

```javascript
const { chromium } = require('playwright');

async function captureScreenshots(htmlFiles) {
  const browser = await chromium.launch();

  for (const file of htmlFiles) {
    const [width, height] = file.match(/(\d+)x(\d+)/).slice(1).map(Number);

    const page = await browser.newPage();
    await page.setViewportSize({ width, height });
    await page.goto(`file://${file}`, { waitUntil: 'networkidle' });
    // Wait for fonts/images to fully render
    await page.waitForTimeout(3000);

    const outputPath = file.replace('.html', '.png').replace('social-photos/', 'social-photos/exports/');
    await page.screenshot({ path: outputPath, type: 'png' });
    await page.close();
  }

  await browser.close();
}
```

#### Option D: Puppeteer script

```javascript
const puppeteer = require('puppeteer');

async function captureScreenshots(htmlFiles) {
  const browser = await puppeteer.launch();

  for (const file of htmlFiles) {
    const [width, height] = file.match(/(\d+)x(\d+)/).slice(1).map(Number);

    const page = await browser.newPage();
    await page.setViewport({ width, height, deviceScaleFactor: 2 }); // 2x for retina
    await page.goto(`file://${file}`, { waitUntil: 'networkidle0' });
    // Wait for fonts/images to fully render
    await new Promise(r => setTimeout(r, 3000));

    const outputPath = file.replace('.html', '.png').replace('social-photos/', 'social-photos/exports/');
    await page.screenshot({ path: outputPath, type: 'png' });
    await page.close();
  }

  await browser.close();
}
```

**IMPORTANT:** Use `deviceScaleFactor: 2` for retina-quality output (Puppeteer only).
