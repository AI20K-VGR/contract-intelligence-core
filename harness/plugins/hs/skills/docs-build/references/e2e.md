# e2e — kiểm thử render showcase (2 tầng)

Showcase build ra HTML tĩnh; e2e xác minh nó **render đúng** (path, ảnh, tương tác) chứ không chỉ "build chạy". Hai tầng, mục đích khác nhau.

## Tầng 1 — static-assert (`e2e_static.py`) · CHẶN CI

Python thuần, no browser, deterministic. Parse `public/**/*.html`:

- mọi `href`/`src` nội bộ → file tồn tại trong deploy `public/`
- không còn `@key@` chưa resolve (link protocol sót)
- đếm html/img

Phân loại **hard** (chặn CI, exit 1) vs **soft** (báo, không chặn):
- **hard**: asset (css/js/img/lib), page-link `.html`, `@key@` dangling — trong site multipage.
- **soft**: link tới file nguồn `.md`/`.yaml`/`.yml`/`.json` (cross-doc tới doc không host — quyết định nội dung, xem FIX.md); mọi ref trong file portable `vsf-aio-platform-showcase.html` (self-contained, asset-model khác).

```
python3 e2e_static.py [--public public] [--strict] [--quiet]
```
`--public` mặc định top-level `public/` (deploy Pages thật, đã copy `diagram/png`). `--strict` cho soft cũng chặn. Wired vào `.gitlab-ci.yml` job `pages`.

> Lưu ý: chạy SAU `build_all.py`/`build_showcase.py` (Bước C copy `_diagram/png`→`public/diagram/png`).
> Chạy e2e trên `docs/public/` (intermediate, build.py-only) sẽ thiếu png → false hard.

## Tầng 2 — headless Chrome (`e2e_browser.mjs`) · PRE-SHIP local

puppeteer-core + system `google-chrome` (no chromium download). Serve `public/` qua http tạm, mỗi page:

- mọi `<img>` `naturalWidth>0` (ảnh load thật)
- hero `canvas#net` + lang-toggle (`#btn-en`/`#btn-vi`) tồn tại
- toggle EN/VI đổi `html.lang-en`/`.lang-vi`
- sidebar router: click link → điều hướng, không 404
- `console.error == 0` (trừ WebGL benign do headless thiếu GPU — đã filter)

```
# cài 1 lần (gitignored):
npm install --no-save --prefix harness/state/e2e-node puppeteer-core
# chạy:
NODE_PATH=harness/state/e2e-node/node_modules \
  node e2e_browser.mjs --public public [--shots <dir>]
```
Không wire CI mặc định (runner CI thường thiếu chrome); là cổng pre-ship local. `--shots <dir>` lưu screenshot mỗi page (artifact kiểm tay).

## Khi nào chạy
- **static**: mỗi build (CI + local `_selfcheck`).
- **browser**: trước ship / sau đổi theme/asset/router/lang.
