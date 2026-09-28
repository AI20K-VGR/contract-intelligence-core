# Poster Design (Built-in)

Comprehensive poster design intelligence for AI agents. Built from vision-clustering 121 reference posters into 4 recombinable axes.

## When to Use

- Event posters (conferences, meetups, launches)
- Editorial / magazine cover style compositions
- Marketing print + digital posters
- Series of related posters that need stylistic consistency with visible variation
- Any image-gen task where "same style, different output each call" matters

## Knowledge Base

Four CSVs in `data/poster/`:

| File | Rows | Purpose |
|------|------|---------|
| `poster-styles.csv` | 20-30 | Curated style clusters with shape pools, mood, era |
| `poster-palettes.csv` | 15-20 | Color systems with mood + contrast level |
| `poster-layouts.csv` | 10-14 | Grid + focal + whitespace patterns |
| `poster-textures.csv` | 8-12 | Material + finish (paper, riso, gradient mesh, etc.) |

Cross-axis `Pairs With Styles` columns let palette/texture filters scope to compatible options for a chosen style.

## Generation Model

Three axes **locked** per call (style, palette, texture) — define the identity.
One axis (layout) + **variation seed** randomized per call — create variety.

Variation seed contributes:
- focal position shuffle
- secondary element positions
- 2-4 shapes sampled from the style's Shape Pool
- density (sparse / medium / dense)
- rotation jitter (-8° to +8°) on secondary elements
- hierarchy order shuffle

Result: 5 calls, same `--style` → 5 visibly distinct posters reading as a cohesive series.

## Usage

### Search the knowledge base

```bash
python3 scripts/poster/search.py --domain style --query "swiss editorial"
python3 scripts/poster/search.py --domain palette --query "warm earthy"
python3 scripts/poster/search.py --domain texture --query "risograph"
```

### Build a design brief

```bash
python3 scripts/poster/search.py --poster-brief --topic "AI Conference" --query "minimal grid"
```

### Generate a prompt for any image model

```bash
python3 scripts/poster/generate.py --topic "AI Conference"
python3 scripts/poster/generate.py --topic "AI Conference" --query "swiss" --aspect a2
python3 scripts/poster/generate.py --topic "AI Conference" --style style-03-swiss-editorial --seed 42
```

Pipe the prompt into the image model of choice (Gemini Nano Banana 2, GPT Image, Imagen, Midjourney, etc.). The skill is model-agnostic — it emits text only.

## Recommendations

- **For a series**: generate 3-5 prompts, same `--style`, unique `--seed` values. Coherence: locked style/palette/texture; variety: randomized layout + variation seed.
- **For exploration**: omit `--style`; picker rotates styles by query relevance.
- **For deterministic repro**: always pass `--seed`.
- **For wide aspect**: use `--aspect landscape` for banners; `--aspect a2` for tall print.

## Rebuilding the Knowledge Base

To add posters or refresh clusters:

```bash
# 1. Run vision analysis (needs GEMINI_API_KEY)
python3 scripts/poster/analyze.py --input-dir /path/to/posters

# 2. Re-cluster + regenerate CSVs
python3 scripts/poster/cluster.py
```

`analyze.py` is resume-safe — re-running skips already-processed images unless `--force`.
