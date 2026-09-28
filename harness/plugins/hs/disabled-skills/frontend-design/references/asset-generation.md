# Asset Generation Workflow

Complete workflow for generating design-aligned visual assets using `hs:ai-multimodal` skill.

## Generation Workflow

### Step 1: Define Design Context

Before generating, extract from the design brief:
- **Aesthetic direction**: Minimalist? Maximalist? Brutalist? Organic?
- **Color palette**: Primary colors, accent colors, mood
- **Typography character**: Modern sans-serif? Elegant serif? Bold display?
- **Visual tone**: Professional? Playful? Luxury? Raw?
- **User context**: Who sees this? What problem does it solve?

### Step 2: Craft Contextual Prompts

Translate design thinking into generation prompts.

**Generic (❌ Avoid)**:
```
"Modern website hero image"
```

**Design-Driven (✓ Use)**:
```
"Brutalist architectural photograph, stark concrete textures,
dramatic shadows, high contrast black and white, raw unpolished
surfaces, geometric shapes, monumental scale, inspired by
1960s Bauhaus, 16:9 aspect ratio"
```

**Prompt Components**:
1. **Style/Movement**: "Neo-brutalism", "Art Deco", "Organic modernism"
2. **Visual Elements**: Textures, shapes, composition style
3. **Color Direction**: "Muted earth tones", "Vibrant neon accents", "Monochromatic"
4. **Mood/Atmosphere**: "Serene", "Energetic", "Mysterious"
5. **Technical Specs**: Aspect ratio, composition focus
6. **References**: "Inspired by [artist/movement]"

### Step 3: Generate with Appropriate Model

Use `hs:ai-multimodal` skill's image generation capabilities:

```bash
# Standard quality (most cases)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[your design-driven prompt]" \
  --output docs/assets/hero-image \
  --model imagen-4.0-generate-001 \
  --aspect-ratio 16:9

# Ultra quality (production hero images, marketing)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[your design-driven prompt]" \
  --output docs/assets/hero-ultra \
  --model imagen-4.0-ultra-generate-001 \
  --size 2K

# Fast iteration (exploring concepts)
python scripts/gemini_batch_process.py \
  --task generate \
  --prompt "[your design-driven prompt]" \
  --output docs/assets/concept \
  --model imagen-4.0-fast-generate-001
```

**Model Selection**:
- **imagen-4.0-generate-001**: Default choice, balanced quality/speed
- **imagen-4.0-ultra-generate-001**: Final production assets, marketing materials
- **imagen-4.0-fast-generate-001**: Rapid prototyping, multiple variations

**Aspect Ratios**:
- **16:9**: Hero sections, wide banners
- **9:16**: Mobile-first, vertical content
- **1:1**: Square cards, social media
- **4:3**: Classic layouts, presentations
- **3:4**: Portrait orientations, mobile screens

### Step 4: Evaluate Against Design Standards

Use `hs:ai-multimodal` to analyze the generated asset (see `visual-analysis.md` for complete workflow):

```bash
python scripts/gemini_batch_process.py \
  --files docs/assets/hero-image.png \
  --task analyze \
  --prompt "Evaluate this image for:
1. Visual coherence with [aesthetic direction]
2. Color harmony and contrast
3. Composition and balance
4. Suitability for overlaying text
5. Professional quality (rate 1-10)
6. Specific weaknesses or improvements needed" \
  --output docs/assets/hero-evaluation.md \
  --model gemini-2.5-flash
```

### Step 5: Iterate or Integrate

**If evaluation score < 7/10 or doesn't meet standards**:
1. Identify specific issues (color, composition, mood, technical)
2. Refine prompt with improvements
3. Regenerate with adjusted parameters
4. Consider using `hs:media-processing` skill for post-generation adjustments

**If meets standards**:
1. Optimize for web (compress, format conversion)
2. Create responsive variants if needed
3. Document asset usage guidelines
4. Integrate into frontend implementation

## Design Pattern Examples

### Pattern 1: Minimalist Background Texture

**Design Context**: Clean, refined interface with generous white space

**Prompt Strategy**:
```
"Subtle paper texture, off-white color (#F8F8F8), barely visible
grain pattern, high-end stationery feel, minimal contrast,
professional and clean, 1:1 aspect ratio for tiling"
```

**Use Case**: Background for minimalist product pages, portfolio sites

### Pattern 2: Maximalist Hero Section

**Design Context**: Bold, energetic landing page with vibrant colors

**Prompt Strategy**:
```
"Explosive color gradients, neon pink to electric blue,
holographic reflections, dynamic diagonal composition,
retrofuturistic aesthetic, vaporwave influence, high energy,
layered transparency effects, 16:9 cinematic"
```

**Use Case**: Hero section for creative agencies, entertainment platforms

### Pattern 3: Brutalist Geometric Pattern

**Design Context**: Raw, bold interface with strong typography

**Prompt Strategy**:
```
"Monochromatic geometric pattern, overlapping rectangles,
stark black and white, high contrast, Swiss design influence,
grid-based composition, architectural precision, repeatable
pattern for backgrounds"
```

**Use Case**: Background pattern for design studios, architecture firms

### Pattern 4: Organic Natural Elements

**Design Context**: Wellness brand, calming user experience

**Prompt Strategy**:
```
"Soft botanical watercolor, sage green and cream tones,
gentle leaf shadows, natural light quality, serene atmosphere,
minimal detail for text overlay, 3:4 portrait orientation"
```

**Use Case**: Hero section for wellness brands, eco-friendly products

### Pattern 5: Retro-Futuristic

**Design Context**: Tech product with nostalgic twist

**Prompt Strategy**:
```
"80s computer graphics aesthetic, wireframe grids, cyan and magenta
gradients, digital sunrise, Tron-inspired, geometric precision,
nostalgic future vision, 16:9 widescreen"
```

**Use Case**: SaaS landing pages, tech conferences, gaming platforms

### Pattern 6: Editorial Magazine Style

**Design Context**: Content-heavy site with strong visual hierarchy

**Prompt Strategy**:
```
"High-contrast editorial photography, dramatic side lighting,
stark shadows, black and white, fashion magazine quality,
strong vertical composition, 3:4 portrait for text layout"
```

**Use Case**: Blog headers, news sites, content platforms

> Continued in `references/asset-generation-cont.md`.
