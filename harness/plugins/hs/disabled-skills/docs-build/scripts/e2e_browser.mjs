// e2e tầng 2 — headless Chrome (puppeteer-core + system google-chrome).
// Load mọi page trong public/, assert: img naturalWidth>0, console.error==0,
// lang-toggle vi↔en, sidebar router điều hướng không vỡ. Exit 1 nếu có lỗi.
//
//   NODE_PATH=harness/state/e2e-node/node_modules \
//     node e2e_browser.mjs [--public public] [--shots <dir>]
//
// Cần: harness/state/e2e-node/node_modules/puppeteer-core + /usr/bin/google-chrome.
import { createRequire } from "module";
import { createServer } from "http";
import { readFileSync, existsSync, mkdirSync, readdirSync } from "fs";
import { join, extname, resolve } from "path";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");

const CHROME = process.env.CHROME_BIN || "/usr/bin/google-chrome";
const args = process.argv.slice(2);
const pubArg = args.includes("--public") ? args[args.indexOf("--public") + 1] : "public";
const shotsArg = args.includes("--shots") ? args[args.indexOf("--shots") + 1] : null;
const PUBLIC = resolve(pubArg);

const MIME = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript",
  ".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".json": "application/json",
  ".woff2": "font/woff2", ".ico": "image/x-icon" };

function serve(root) {
  return new Promise((res) => {
    const srv = createServer((req, rq) => {
      let p = decodeURIComponent(req.url.split("?")[0]);
      if (p.endsWith("/")) p += "index.html";
      const fp = join(root, p);
      if (!fp.startsWith(root) || !existsSync(fp)) { rq.writeHead(404); return rq.end("404"); }
      rq.writeHead(200, { "content-type": MIME[extname(fp)] || "application/octet-stream" });
      rq.end(readFileSync(fp));
    });
    srv.listen(0, "127.0.0.1", () => res(srv));
  });
}

function pages(root) {
  const out = ["index.html"];
  const pdir = join(root, "pages");
  if (existsSync(pdir)) for (const f of readdirSync(pdir)) if (f.endsWith(".html")) out.push("pages/" + f);
  return out;
}

const fails = [];
function fail(pg, msg) { fails.push(`${pg}: ${msg}`); }

// Lỗi benign do headless KHÔNG có GPU (showcase có 2D fallback) — bỏ qua, không phải bug.
const BENIGN = [/WebGLRenderer.*Error creating WebGL context/i, /Failed to create WebGL/i,
  /WebGL.*context.*lost/i, /THREE.WebGLRenderer: Context Lost/i, /SwiftShader/i];
function realErrors(errs) { return errs.filter((e) => !BENIGN.some((re) => re.test(e))); }

const srv = await serve(PUBLIC);
const port = srv.address().port;
const base = `http://127.0.0.1:${port}`;
if (shotsArg) mkdirSync(shotsArg, { recursive: true });

let browser;
try {
  browser = await puppeteer.launch({
    executablePath: CHROME, headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage",
           "--enable-unsafe-swiftshader", "--use-gl=swiftshader"],
  });
} catch (e) {
  console.error("E2E-BROWSER: không khởi động được Chrome:", e.message);
  srv.close(); process.exit(2);
}

for (const pg of pages(PUBLIC)) {
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  try {
    const resp = await page.goto(`${base}/${pg}`, { waitUntil: "networkidle0", timeout: 30000 });
    if (!resp || !resp.ok()) fail(pg, `HTTP ${resp ? resp.status() : "no-response"}`);

    // ảnh: mọi <img> phải naturalWidth>0 (đã load)
    const badImgs = await page.$$eval("img", (imgs) =>
      imgs.filter((i) => !i.complete || i.naturalWidth === 0).map((i) => i.getAttribute("src")));
    for (const s of badImgs) fail(pg, `img KHÔNG load: ${s}`);

    // hero canvas#net + lang-toggle tồn tại (shell)
    const hasNet = await page.$("#net");
    if (!hasNet) fail(pg, "thiếu hero canvas#net");
    const hasLang = await page.$("#btn-en") && await page.$("#btn-vi");
    if (!hasLang) fail(pg, "thiếu lang-toggle (btn-en/btn-vi)");

    // lang toggle: click EN → html.lang-en; VI → lang-vi
    if (hasLang) {
      await page.click("#btn-en");
      const en = await page.evaluate(() => document.documentElement.classList.contains("lang-en"));
      if (!en) fail(pg, "toggle EN không đổi html.lang-en");
      await page.click("#btn-vi");
      const vi = await page.evaluate(() => document.documentElement.classList.contains("lang-vi"));
      if (!vi) fail(pg, "toggle VI không đổi html.lang-vi");
    }

    const real = realErrors(errors);
    if (real.length) fail(pg, `console.error×${real.length}: ${real.slice(0, 3).join(" | ")}`);
    if (shotsArg) await page.screenshot({ path: join(shotsArg, pg.replace(/\//g, "_") + ".png") });
  } catch (e) {
    fail(pg, `exception: ${e.message}`);
  } finally {
    await page.close();
  }
}

// router: điều hướng tới page đầu tiên trong pages/ (có sidebar), kiểm .side-link
try {
  const page = await browser.newPage();
  // index.html là view-home — KHÔNG có sidebar; lấy page đầu tiên trong pages/
  const pdir = join(PUBLIC, "pages");
  const firstPage = existsSync(pdir)
    ? readdirSync(pdir).filter((f) => f.endsWith(".html")).sort()[0]
    : null;
  const routerStart = firstPage ? `pages/${firstPage}` : "index.html";
  await page.goto(`${base}/${routerStart}`, { waitUntil: "networkidle0" });
  const links = await page.$$eval(".side-link[href]", (as) => as.map((a) => a.getAttribute("href")));
  if (links.length === 0) fail("router", "no .side-link found — selector/sidebar vỡ");
  for (const href of links.slice(0, 30)) {
    if (!href || href.startsWith("#") || href.startsWith("http")) continue;
    const r = await page.goto(`${base}/${href.replace(/^\.\//, "")}`, { waitUntil: "domcontentloaded" }).catch(() => null);
    if (!r || !r.ok()) fail("router", `sidebar link vỡ: ${href} (${r ? r.status() : "err"})`);
  }
  await page.close();
} catch (e) { fail("router", e.message); }

await browser.close();
srv.close();

console.log(`e2e-browser: ${pages(PUBLIC).length} page · ${PUBLIC}`);
if (fails.length) {
  console.error(`E2E-BROWSER: FAIL (${fails.length})`);
  for (const f of fails) console.error("  ✗ " + f);
  process.exit(1);
}
console.log("E2E-BROWSER: PASS");
