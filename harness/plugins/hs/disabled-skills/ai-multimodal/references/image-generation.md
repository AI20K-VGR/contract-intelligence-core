# Image Generation Reference

Image creation, editing, composition via Imagen 4 and Gemini models ("Nano Banana").

> **Nano Banana** = Google's internal name for native image generation in Gemini API. Three variants:
> - **Nano Banana 2** (`gemini-3.1-flash-image-preview`) - NEW DEFAULT. 3-5x faster, 95% Pro quality, web grounding, 100+ language text rendering, character consistency (5 chars/14 objects). Released Feb 2026.
> - **Nano Banana Flash** (`gemini-2.5-flash-image`) - Previous default, still stable.
> - **Nano Banana Pro** (`gemini-3-pro-image-preview`) - Quality with reasoning, 4K text.

## Core Capabilities

- **Text-to-Image**: Generate images from text prompts
- **Image Editing**: Modify existing images with text instructions
- **Multi-Image Composition**: Combine up to 14 reference images (Pro model)
- **Iterative Refinement**: Multi-turn conversational refinement
- **Aspect Ratios**: 10 formats (1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9)
- **Image Sizes**: 1K, 2K, 4K (uppercase K required)
- **Quality Variants**: Standard/Ultra/Fast for different needs
- **Text in Images**: Up to 25 chars optimal (4K text in Pro)
- **Search Grounding**: Real-time data integration (Pro only)
- **Thinking Mode**: Advanced reasoning for complex prompts (Pro only)

## Models

### Nano Banana 2 (Default - Recommended)

**gemini-3.1-flash-image-preview** - Nano Banana 2 ⭐ NEW DEFAULT
- Best for: General use, fast generation with near-Pro quality
- Quality: High (95% parity with Pro)
- Speed: 3-5x faster than previous Flash
- Cost: ~$0.045/image (512px) to ~$0.151/image (4K); ~25-30% cheaper than Pro
- Resolution: 512px to 4K with expanded aspect ratios
- Text rendering: 100+ languages with proper formatting
- Character consistency: Up to 5 characters and 14 objects
- Reasoning levels: Minimal/High/Dynamic for complex prompts
- Web grounding: Real-time data integration for brands, landmarks, recent events
- Status: Preview (Feb 2026)

### Nano Banana Flash (Previous Default)

**gemini-2.5-flash-image** - Nano Banana Flash
- Best for: Speed, high-volume generation, rapid prototyping
- Quality: High
- Context: 65,536 input / 32,768 output tokens
- Speed: Fast (~5-10s per image)
- Cost: ~$1/1M input tokens
- Aspect Ratios: All 10 supported
- Image Sizes: 1K, 2K, 4K
- Status: Stable (Oct 2025)

**gemini-3-pro-image-preview** - Nano Banana Pro
- Best for: Professional assets, 4K text rendering, complex prompts
- Quality: Ultra (with advanced reasoning)
- Context: 65,536 input / 32,768 output tokens
- Speed: Medium
- Cost: ~$2/1M text input, $0.134/image (resolution-dependent)
- Multi-Image: Up to 14 reference images (6 objects + 5 humans)
- Features: Thinking mode, Google Search grounding
- Status: Preview (Nov 2025)

### Imagen 4 (Alternative - Production)

**imagen-4.0-generate-001** - Standard quality, balanced performance
- Best for: Production workflows, marketing assets
- Quality: High
- Speed: Medium (~5-10s per image)
- Cost: ~$0.02/image (estimated)
- Output: 1-4 images per request
- Resolution: 1K or 2K
- Updated: June 2025

**imagen-4.0-ultra-generate-001** - Maximum quality
- Best for: Final production, marketing assets, detailed artwork
- Quality: Ultra (highest available)
- Speed: Slow (~15-25s per image)
- Cost: ~$0.04/image (estimated)
- Output: 1-4 images per request
- Resolution: 2K preferred
- Updated: June 2025

**imagen-4.0-fast-generate-001** - Fastest generation
- Best for: Rapid iteration, bulk generation, real-time use
- Quality: Good
- Speed: Fast (~2-5s per image)
- Cost: ~$0.01/image (estimated)
- Output: 1-4 images per request
- Resolution: 1K
- Updated: June 2025

### Legacy Models

**gemini-2.0-flash-preview-image-generation** - Legacy
- Status: Deprecated (use Nano Banana or Imagen 4 instead)
- Context: 32,768 input / 8,192 output tokens

## Model Comparison

| Model | Quality | Speed | Cost | Best For |
|-------|---------|-------|------|----------|
| gemini-3.1-flash-image-preview | ⭐⭐⭐⭐½ | 🚀🚀 Fastest | 💵 Low | **NEW DEFAULT** - General use |
| gemini-2.5-flash-image | ⭐⭐⭐⭐ | 🚀 Fast | 💵 Low | Previous default, stable |
| gemini-3-pro-image | ⭐⭐⭐⭐⭐ | 💡 Medium | 💰 Medium | Text/reasoning |
| imagen-4.0-generate | ⭐⭐⭐⭐ | 💡 Medium | 💰 Medium | Production (alternative) |
| imagen-4.0-ultra | ⭐⭐⭐⭐⭐ | 🐢 Slow | 💰💰 High | Marketing assets |
| imagen-4.0-fast | ⭐⭐⭐ | 🚀 Fast | 💵 Low | Bulk generation |

**Selection Guide**:
- **Default/General**: Use `gemini-3.1-flash-image-preview` (fastest, near-Pro quality, web grounding)
- **Stable Alternative**: Use `gemini-2.5-flash-image` (previous default, fully stable)
- **Production Quality**: Use `imagen-4.0-generate-001` (alternative for final assets)
- **Marketing/Ultra Quality**: Use `imagen-4.0-ultra` for maximum quality
- **Text-Heavy Images**: Use `gemini-3-pro-image-preview` for 4K text rendering
- **Complex Prompts with Reasoning**: Use `gemini-3-pro-image-preview` with Thinking mode
- **Real-time Data Integration**: Use `gemini-3.1-flash-image-preview` or `gemini-3-pro-image-preview` with Search grounding

> Continued in `references/image-generation-cont.md`.
