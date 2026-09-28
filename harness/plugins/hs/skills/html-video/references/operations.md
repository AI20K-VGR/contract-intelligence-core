# html-video — operations

Output organization, maintenance guidance, troubleshooting for the html-video skill.

## Output organization

Invoke `/hs:project-organization` before choosing final paths in a repo with existing asset conventions. In a new or simple project, use:

- `assets/videos/<slug>.mp4` for finished local exports
- `plans/<plan-slug>/visuals/<slug>.mp4` for implementation proof artifacts
- `tmp/html-video/<slug>/` for disposable preview or Studio scratch state

Do not commit large generated MP4 files unless the user explicitly wants it versioned.

## Maintenance guidance

`nexu-io/html-video` iterates fast — before trusting memorized commands, run:

```bash
html_video --help
html_video project-render --help
html_video studio --help
```

If a first-party `html-video` agent skill package becomes available, prefer its live instructions and update this wrapper to point at that package instead of duplicating command reference.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `html-video CLI not found` | Install a global binary if available, or set `HTML_VIDEO_HOME` to a built source checkout. |
| `doctor` reports missing browser | Install Playwright/Chromium using upstream instructions, then rerun `doctor`. |
| Render reports `Executable doesn't exist` for Playwright Chromium | From the source checkout, run `pnpm --filter @html-video/adapter-hyperframes exec playwright install chromium`. |
| `doctor` reports ffmpeg missing | Install ffmpeg with the platform package manager and verify `ffmpeg -version`. |
| Template has no variables | Use Studio to customize copy/layout; CLI variable commands cannot theme an empty schema. |
| Render starts but MP4 is blank | Preview first, inspect browser console if Studio exposes it, then rerun `project-render` with `--stream-progress`. |
| Output path is wrong | Re-render with an explicit `--output` path; do not move only partial render directories. |
