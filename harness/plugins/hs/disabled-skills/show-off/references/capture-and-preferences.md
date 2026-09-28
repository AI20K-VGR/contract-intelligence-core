# show-off — Preferences, Capture, and Fallback

Detailed CLI usage split from `SKILL.md` to keep the core thin.

## Preference Helper

Preference helper at `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/preferences.js`:

```bash
# Print resolved user preferences as JSON
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/preferences.js get

# Persist workflow opt-outs
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/preferences.js set --no-screenshots --no-publish --languages en

# Re-enable defaults
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/preferences.js reset
```

Options for `set`:
- `--screenshots on|off`, `--no-screenshots`
- `--publishing on|off`, `--publish on|off`, `--no-publishing`, `--no-publish`
- `--languages en|vi|en,vi`, `--language en|vi`
- `--dual-language on|off`, `--no-dual-language`

Preferences persist at `~/.claude/show-off/preferences.json` by default; `SHOW_OFF_PREFS_PATH` overrides the path (tests/advanced one-off use).

## Capture Script

Parallel capture script at `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/capture-sections.js`:

```bash
# Capture all sections in parallel across multiple ratios
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/capture-sections.js \
  --url "file:///path/to/page.html" \
  --output-dir "./assets/showoff/my-mission/images" \
  --sections "#hero,#about,#features,#footer" \
  --ratios "horizontal,vertical,square" \
  --settle-delay 1500 \
  --format png \
  --quality 90

# Single ratio capture
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/show-off/scripts/capture-sections.js \
  --url "http://localhost:3000" \
  --output-dir "./output" \
  --sections "#hero" \
  --ratios "horizontal"
```

Options:
- `--url` (required): Page URL to capture
- `--output-dir` (required): Output directory for images
- `--sections` (required): Comma-separated CSS selectors for sections
- `--ratios` (default: "horizontal,vertical,square"): Capture ratios
- `--settle-delay` (default: 1500): Ms to wait AFTER the page is visually ready. Alias: `--delay`.
- `--render-timeout` (default: 15000): Max ms to wait for any single readiness signal.
- `--format` (default: "png"): Image format (png/jpg/webp)
- `--quality` (default: 90): Image quality (1-100, for jpg/webp)
- `--max-size` (default: 5): Max file size in MB before compression
- `--executable-path`: Optional Chrome/Chromium path. Also reads `CHROME_EXECUTABLE_PATH` / `PUPPETEER_EXECUTABLE_PATH`.

### Readiness chain before each capture

1. `networkidle0` (no in-flight requests)
2. `document.fonts.ready` (web fonts loaded)
3. Every `<img>` complete (or errored)
4. Every CSS `background-image` URL preloaded
5. Double `requestAnimationFrame` (layout + compositor settle)
6. `--settle-delay` ms (animations / JS-triggered reveals)

Same chain reruns after `scrollIntoView()` per section, so reveal-on-scroll animations capture correctly.

## `rws` Publish Fallback

If `publishing=true` and the local capture script fails (puppeteer missing, headless Chrome unavailable, sandbox error, non-zero exit) AND `rws` is on PATH AND `$RWEB_API_KEY` is set, fall back to the ReviewWeb screenshot API. The HTML must be publicly reachable (publish via `agentwiki` first, then use the public URL + `#section-id` anchors).

Detection:

```bash
command -v rws >/dev/null && [ -n "$RWEB_API_KEY" ] && echo "rws fallback available"
```

Per (section, ratio) capture loop:

```bash
# Viewports: horizontal=1920x1080, vertical=1080x1920, square=1080x1080
rws screenshot \
  --url "https://public-host/mission/#hero" \
  --width 1920 --height 1080 \
  --delay 1500 \
  --format json \
  | jq -r '.imageUrl' \
  | xargs -I{} curl -sSL {} -o "assets/showoff/<mission-name>/images/horizontal-hero.png"
```

Fallback rules:
- Run per (section, ratio) combo; parallelise with `xargs -P` or shell `&`.
- `--delay` passes the same settle-delay value used by the local script.
- Skip `rws` whenever `publishing=false` — the user chose a local-only flow.
- Skip `rws` if the HTML is only reachable via `file://` and cannot be published yet — surface the local script error and stop.
- Never pass `$RWEB_API_KEY` on the command line; `rws` reads it from the env automatically.
- On `rws` exit code 2 (auth error) or missing `$RWEB_API_KEY`, stop and report — do not silently skip capture.
