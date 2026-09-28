# Asset Generation (continued)

## Prompt Engineering Best Practices

### 1. Be Specific About Style
❌ "Modern design"
✓ "Bauhaus-inspired geometric abstraction with primary colors"

### 2. Define Color Precisely
❌ "Colorful"
✓ "Vibrant sunset palette: coral (#FF6B6B), amber (#FFB84D), violet (#A66FF0)"

### 3. Specify Composition
❌ "Nice layout"
✓ "Rule of thirds composition, subject left-aligned, negative space right for text overlay"

### 4. Reference Movements/Artists
❌ "Artistic"
✓ "Inspired by Bauhaus geometric abstraction and Swiss International Style"

### 5. Technical Requirements First
Always include: aspect ratio, resolution needs, intended use case

### 6. Iterate Strategically
- First generation: Broad aesthetic exploration
- Second generation: Refine color and composition
- Third generation: Fine-tune details and mood

## Common Pitfalls to Avoid

### ❌ Generic Stock Photo Aesthetics
Don't prompt: "Professional business team working together"
Instead: Design-specific, contextual imagery that serves the interface

### ❌ Overcomplex Generated Images
Generated assets that compete with UI elements create visual chaos Keep backgrounds subtle enough for text/button overlay

### ❌ Inconsistent Visual Language
Each generated asset should feel part of the same design system Maintain color palette, visual style, mood consistency

### ❌ Ignoring Integration Context
Assets aren't standalone—consider how they work with:
- Typography overlays
- Interactive elements (buttons, forms)
- Navigation and UI chrome
- Responsive behavior across devices

## Responsive Asset Strategy

### Desktop-First Approach
1. Generate primary asset at 16:9 (desktop hero)
2. Generate mobile variant at 9:16 with same prompt
3. Ensure focal point works in both orientations

### Mobile-First Approach
1. Generate primary asset at 9:16 (mobile hero)
2. Generate desktop variant at 16:9 with same prompt
3. Test that composition scales effectively

### Variant Generation
```bash
# Desktop (16:9)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[prompt]" \
  --output docs/assets/hero-desktop \
  --model imagen-4.0-generate-001 \
  --aspect-ratio 16:9

# Mobile (9:16)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[same prompt]" \
  --output docs/assets/hero-mobile \
  --model imagen-4.0-generate-001 \
  --aspect-ratio 9:16

# Square (1:1)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[same prompt]" \
  --output docs/assets/hero-square \
  --model imagen-4.0-generate-001 \
  --aspect-ratio 1:1
```

## Model Cost Optimization

**Imagen 4 Pricing** (as of 2024):
- Standard: ~$0.04 per image
- Ultra: ~$0.08 per image
- Fast: ~$0.02 per image

**Optimization Strategy**:
1. Use Fast model for exploration (3-5 variations)
2. Select best direction, generate with Standard model
3. Use Ultra only for final production assets
4. Batch generate variations in single session

## Complete Example Workflow

```bash
# 1. Fast exploration (3 variations)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "Minimalist mountain landscape, muted blue-gray tones,
  fog layers, serene morning atmosphere, clean for text overlay, 16:9" \
  --output docs/assets/concept-1 \
  --model imagen-4.0-fast-generate-001 \
  --aspect-ratio 16:9

# 2. Analyze best variation
python scripts/gemini_batch_process.py \
  --files docs/assets/concept-1.png \
  --task analyze \
  --prompt "Rate 1-10 for aesthetic quality, color harmony, text overlay suitability" \
  --output docs/assets/analysis-1.md \
  --model gemini-2.5-flash

# 3. If score ≥ 7/10, generate production version
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[refined prompt based on analysis]" \
  --output docs/assets/hero-final \
  --model imagen-4.0-generate-001 \
  --aspect-ratio 16:9

# 4. Generate mobile variant
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[same refined prompt]" \
  --output docs/assets/hero-mobile \
  --model imagen-4.0-generate-001 \
  --aspect-ratio 9:16
```

## Next Steps

- **Verify quality**: See `visual-analysis.md` for comprehensive analysis workflow
- **Optimize assets**: See `technical-guide.md` for file optimization and integration
- **Extract inspiration**: See `design-extraction.md` to learn from existing designs
