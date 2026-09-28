---
name: hs:ai-artist
injectable: true
description: "Generate product mockups, marketing assets, brand visuals, and concept art via Nano Banana with 129 curated prompts. Mandatory validation interview refines style/mood/colors (use --skip to bypass). 3 modes: search, creative, wild. Styles: Ukiyo-e, Bento grid, cyberpunk, cinematic, vintage patent."
metadata:
  compliance-tier: workflow
argument-hint: "[concept] [--mode search|creative|wild|all] [--provider auto|google|openrouter] [--skip]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
---

# AI Artist - Nano Banana Image Generation

Generate images from 129 curated awesome-nano-banana-pro-prompts. Routes final rendering through `ai-multimodal` — same prompt workflow, direct Google or OpenRouter-backed Google models.

**Validation interview mandatory** (use `--skip` to bypass).

## Workflow

1. **Parse args** — concept (required), `--mode`, `--skip` (skip → defaults: Photorealistic/Professional/Auto/16:9, jump to step 4).
2. **Interview** — unless `--skip`, run one `AskUserQuestion` call with 4 questions (Style/Mood/Colors/Aspect ratio).
3. **Build prompt** — map answers to keyword template: `[concept], [style], [mood], [colors]. Professional quality. NEVER add watermarks.`
4. **Confirm & generate** — show preview, confirm (yes/edit/start over), then run `scripts/generate.py`.

**IMPORTANT:** Follow `references/validation-workflow.md` for full AskUserQuestion JSON payloads, keyword-mapping tables, and confirm/edit/start-over branch logic.

## Quick Start

```bash
python3 scripts/generate.py "<concept>" -o <output.png> [--mode MODE] [--provider PROVIDER]
```

### Generation Modes

| Mode | Description |
|------|-------------|
| `search` | Find best matching prompt from 129 curated prompts (default) |
| `creative` | Remix elements from top 3 matching prompts |
| `wild` | Out-of-the-box creative interpretation (random style transform) |
| `all` | Generate all 3 variations |

### Examples

```bash
# Default search mode
python3 scripts/generate.py "tech conference banner" -o banner.png -ar 16:9

# Route through OpenRouter while keeping Nano Banana prompt behavior
python3 scripts/generate.py "tech conference banner" -o banner.png --provider openrouter

# Creative remix (combines multiple prompts)
python3 scripts/generate.py "AI workshop" -o workshop.png --mode creative

# Wild/experimental (random artistic transformation)
python3 scripts/generate.py "product showcase" -o product.png --mode wild

# Generate all 3 variations at once
python3 scripts/generate.py "futuristic city" -o city.png --mode all -v
```

### Options

| Flag | Description |
|------|-------------|
| `-o, --output` | Output path (required) |
| `-m, --mode` | search, creative, wild, or all |
| `--provider` | auto (default), google, or openrouter |
| `-ar, --aspect-ratio` | 1:1, 16:9, 9:16, etc. |
| `--model` | flash2 (default, fast+quality), flash (previous), pro (quality/4K) |
| `-v, --verbose` | Show matched prompts and details |
| `--dry-run` | Show prompt without generating |
| `--skip` | Bypass validation interview |

`--provider auto` honors `IMAGE_GEN_PROVIDER=openrouter` when set; otherwise prefers direct Google unless only OpenRouter credentials are configured.

---

## Prompt Database

**129 curated prompts** extracted from awesome-nano-banana-pro-prompts:

```bash
# Search prompts
python3 scripts/search.py "<query>" --domain awesome

# View all prompts
cat data/awesome-prompts.csv
```

### Categories include:
- **Profile/Avatar**: Thought-leader headshots, mirror selfies
- **Infographics**: Bento grid, chalkboard, ingredient labels
- **Social Media**: Quote cards, banners, thumbnails
- **Product**: Commercial shots, e-commerce, Apple-style
- **Artistic**: Ukiyo-e, patent documents, vaporwave, cyberpunk
- **Character**: Anime, chibi, comic storyboards

---

## Wild Mode Transformations

`wild` mode randomly applies one of these transformations:

- Japanese Ukiyo-e woodblock print
- Premium liquid glass Bento grid infographic
- Vintage 1800s patent document
- Surreal dreamscape with volumetric god rays
- Cyberpunk neon aesthetic with holograms
- Hand-drawn chalkboard explanation
- Isometric 3D diorama
- Cinematic movie poster
- Vaporwave aesthetic with glitch effects
- Apple-style product showcase

---

## References

| Topic | File |
|-------|------|
| **Validation Workflow** | `references/validation-workflow.md` |
| All Prompts | `data/awesome-prompts.csv` |
| Nano Banana Guide | `references/nano-banana.md` |
| Image Prompting | `references/image-prompting.md` |
| LLM Prompting | `references/llm-prompting.md` |
| Reasoning Techniques | `references/reasoning-techniques.md` |
| Source | `data/awesome-nano-banana-pro-prompts.md` |

---

## Scripts

| Script | Purpose |
|--------|---------|
| `generate.py` | Main image generation with 3 modes |
| `search.py` | Search prompts database |
| `extract_prompts.py` | Extract prompts from markdown |
| `core.py` | BM25 search engine |
