---
name: hs:html-video
injectable: true
description: "Create local MP4 videos from HTML/CSS/JS templates with nexu-io/html-video. Covers source checkout setup, template discovery, studio customization, preview, and render verification."
argument-hint: "[video brief, source URL, repo, template id, or project id]"
allowed-tools: [Bash, Read, Write, Edit]
metadata:
  compliance-tier: workflow
  upstream: "nexu-io/html-video"
---

# html-video Skill

Creates local videos via `nexu-io/html-video` CLI + Studio — turns HTML/CSS/JS templates + project assets into real MP4 exports through headless Chromium + ffmpeg.

Use this for template-driven product promos, explainers, data/social clips, article or repo summaries, and HTML-first motion prototypes.

## Route carefully

- Use `/hs:remotion` for React/Remotion compositions, frame math, or Remotion project code.
- Use `/hs:media-processing` when the task is only encoding, trimming, transcoding, thumbnails, HLS/DASH, or batch FFmpeg/ImageMagick work.
- Use `/hs:preview` or `/hs:show-off` for static HTML previews, slides, docs, diagrams, or demos that do not need MP4 rendering.
- Use `/hs:agent-browser` for browser QA or to operate the html-video Studio UI when no real Chrome profile state is needed.
- Use `/hs:chrome-profile` only if the Studio workflow explicitly needs the user's existing Chrome profile or logged-in browser state.

## Setup

Prefer a published `html-video` binary if present; else use a source checkout — do not vendor the upstream engine into the user's project.

As of upstream `main` when authored, `html-video` declares Node `>=20`, pnpm `>=9`, package manager `pnpm@9.15.0`; if `package.json` differs, follow upstream.

```bash
# Source checkout path is a convention, not a requirement.
git clone https://github.com/nexu-io/html-video "$HOME/html-video"
cd "$HOME/html-video"
corepack enable
corepack prepare pnpm@9.15.0 --activate
pnpm install
pnpm -r build

# If source-checkout rendering reports a missing Playwright browser:
pnpm --filter @html-video/adapter-hyperframes exec playwright install chromium
```

Helper for shell sessions — works with a global binary or a source checkout:

```bash
html_video() {
  if command -v html-video >/dev/null 2>&1; then
    html-video "$@"
    return
  fi

  local home="${HTML_VIDEO_HOME:-$HOME/html-video}"
  if [ -f "$home/packages/cli/dist/bin.js" ]; then
    node "$home/packages/cli/dist/bin.js" "$@"
    return
  fi

  echo "html-video CLI not found. Install it or set HTML_VIDEO_HOME to the source checkout." >&2
  return 127
}
```

Always start with diagnostics:

```bash
html_video doctor
html_video list-engines
```

CLI defaults to JSON output; add `--no-color` for logs, `--cwd <path>` when rendering outside the current directory.

## Standard workflow

1. Pin the video brief before creating anything:
   - audience and goal
   - duration and aspect ratio
   - source assets or URLs
   - template preference
   - output path and filename
   - whether the final should be a draft proof or polished export

2. Discover templates:

```bash
html_video search-templates --intent "short product promo for a developer tool" --aspect 16:9 --top 5
html_video inspect-template frame-product-promo
```

Inspect before choosing. Some templates expose variables that can be set by CLI; others rely on Studio/project editing and have no template input schema.

3. Create or locate a project:

```bash
html_video project-create \
  --name "Harness Promo" \
  --intent "Short product promo for SDLC Harness as a maintainer-grade agent engineering stack" \
  --aspect 16:9

html_video project-list
html_video project-show <project-id>
```

4. Select a template and add assets:

```bash
html_video project-set-template <project-id> --template frame-product-promo
html_video project-add-asset <project-id> --inline-text "SDLC Harness: maintainer-grade agent engineering workflows" --caption "core message"
html_video project-add-asset <project-id> --file ./path/to/logo-or-screenshot.png --caption "visual reference"
```

If `inspect-template` shows variables, set them explicitly:

```bash
html_video project-set-var <project-id> --key headline --value '"SDLC Harness"'
html_video project-set-vars <project-id> --vars-file ./video-vars.json
```

5. Preview:

```bash
html_video project-preview <project-id>
```

Open the returned `html_path` in a browser. If the user needs interactive editing, launch Studio:

```bash
html_video studio --port 3071
```

Use Studio for agent-assisted rewrite, layout tuning, and templates with empty variable schemas. Export from Studio, or render the finished project by CLI.

6. Render and verify:

```bash
html_video project-render <project-id> --output ./assets/videos/<slug>.mp4 --stream-progress
ffprobe -v error -show_streams -show_format -of json ./assets/videos/<slug>.mp4
```

The MP4 proof is not complete until `ffprobe` reports a nonzero duration and expected video dimensions.

## Operations

Output-path conventions, maintenance/update guidance, troubleshooting table: [references/operations.md](references/operations.md) — consult before finalizing render paths or when `doctor`/render errors.

## See also

- For hi-fi HTML production (clickable prototypes, animated films, HTML decks, MP4/PPTX), see the
  **huashu-design** pointer (and the wider external design-skill catalog) in `hs:ui-ux`.
- For an end-to-end "any input → vertical social video" pipeline — a GitHub repo, URL, article, or
  raw text turned into a 9:16 narrated clip with word-synced karaoke captions, TTS-measured timing to
  avoid audio/video drift, and human approval gates — see **any2video** (`chanktb/any2video`), an
  autonomous Claude Code skill. Complementary to this template→MP4 engine: any2video plans the
  narrative and screenplay itself, whereas this skill renders from HTML templates you pick. Not
  vendored here (pointer-not-vendor); verify its license and state before depending on it.
- A commercial hosted 9:16 generator (HeyGen HyperFrames, reached through `npx`) was
  considered and **refused**, so the next reader does not read its absence as an
  oversight. It needs three external dependencies and a paid API key for one capability —
  vertical marketing video — that sits outside the software lifecycle this harness serves,
  and the two routes above already reach that output from tools we control. Reconsider if
  the requirement becomes recurring and someone owns the account.
