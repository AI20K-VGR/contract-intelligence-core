# Image Generation (continued 3/5)

## Response Modalities

### Image Only

```python
config = types.GenerateContentConfig(
    response_modalities=['image'],
    aspect_ratio='1:1'
)
```

### Text Only (No Image)

```python
config = types.GenerateContentConfig(
    response_modalities=['text']
)
# Returns text description instead of generating image
```

### Both Image and Text

```python
config = types.GenerateContentConfig(
    response_modalities=['image', 'text'],
    aspect_ratio='16:9'
)
# Returns both generated image and description
```

## Image Editing

### Modify Existing Image

```python
import PIL.Image

# Load original
img = PIL.Image.open('original.png')

# Edit with instructions
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        'Add a red balloon floating in the sky',
        img
    ],
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='16:9'
    )
)
```

### Style Transfer

```python
img = PIL.Image.open('photo.jpg')

response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        'Transform this into an oil painting style',
        img
    ]
)
```

### Object Addition/Removal

```python
# Add object
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        'Add a vintage car parked on the street',
        img
    ]
)

# Remove object
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        'Remove the person on the left side',
        img
    ]
)
```

## Multi-Image Composition

### Combine Multiple Images

```python
img1 = PIL.Image.open('background.png')
img2 = PIL.Image.open('foreground.png')
img3 = PIL.Image.open('overlay.png')

response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        'Combine these images into a cohesive scene',
        img1,
        img2,
        img3
    ],
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='16:9'
    )
)
```

**Note**: Recommended maximum 3 input images for best results.

## Prompt Engineering

### Core Principle: Narrative > Keywords

> **Nano Banana prompting**: Write like you're briefing a photographer, not providing SEO keywords. Narrative paragraphs outperform keyword lists.

❌ **Bad**: "cat, 4k, masterpiece, trending, professional, ultra detailed, cinematic"
✅ **Good**: "A fluffy orange tabby cat with green eyes lounging on a sun-drenched windowsill. Soft morning light creates a warm glow. Shot with a 50mm lens at f/1.8 for shallow depth of field. Natural lighting, documentary photography style."

### Effective Prompt Structure

**Three key elements**:
1. **Subject**: What to generate (be specific)
2. **Context**: Environmental setting (lighting, location, time)
3. **Style**: Artistic treatment (photography, illustration, etc.)

### Quality Modifiers

**Technical terms**:
- "4K", "8K", "high resolution"
- "HDR", "high dynamic range"
- "professional photography"
- "studio lighting"
- "ultra detailed"

**Camera settings**:
- "35mm lens", "50mm lens"
- "shallow depth of field"
- "wide angle shot"
- "macro photography"
- "golden hour lighting"

### Style Keywords

**Art styles**:
- "oil painting", "watercolor", "sketch"
- "digital art", "concept art"
- "photorealistic", "hyperrealistic"
- "minimalist", "abstract"
- "cyberpunk", "steampunk", "fantasy"

**Mood and atmosphere**:
- "dramatic lighting", "soft lighting"
- "moody", "bright and cheerful"
- "mysterious", "whimsical"
- "dark and gritty", "pastel colors"

### Subject Description

**Be specific**:
- ❌ "A cat"
- ✅ "A fluffy orange tabby cat with green eyes"

**Add context**:
- ❌ "A building"
- ✅ "A modern glass skyscraper reflecting sunset clouds"

**Include details**:
- ❌ "A person"
- ✅ "A young woman in a red dress holding an umbrella"

### Composition and Framing

**Camera angles**:
- "bird's eye view", "aerial shot"
- "low angle", "high angle"
- "close-up", "wide shot"
- "centered composition"
- "rule of thirds"

**Perspective**:
- "first person view"
- "third person perspective"
- "isometric view"
- "forced perspective"

### Text in Images

**Limitations**:
- Maximum 25 characters total for optimal results
- Up to 3 distinct text phrases
- For 4K text rendering, use `gemini-3-pro-image-preview`

**Text prompt template**:
```
Image with text "[EXACT TEXT]" in [font style].
Font: [style description].
Color: [hex code like #FF5733].
Position: [top/center/bottom].
Background: [description].
Context: [poster/sign/label].
```

**Example**:
```python
response = client.models.generate_content(
    model='gemini-3-pro-image-preview',  # Use Pro for better text
    contents='''
    Create a vintage travel poster with text "EXPLORE TOKYO" at the top.
    Font: Bold retro sans-serif, slightly condensed.
    Color: #F5E6D3 (cream white).
    Position: Top third of image.
    Background: Stylized Tokyo skyline with Mt. Fuji, sunset colors.
    Style: 1950s travel poster aesthetic, muted warm colors.
    '''
)
```

**Font keywords**:
- "bold sans-serif", "handwritten script", "vintage letterpress"
- "modern minimalist", "art deco", "neon sign"

### Nano Banana Prompt Techniques

| Technique | Example | Purpose |
|-----------|---------|---------|
| ALL CAPS emphasis | `The logo MUST be centered` | Force attention to critical requirements |
| Hex colors | `#9F2B68` instead of "dark magenta" | Exact color control |
| Negative constraints | `NEVER include text/watermarks. DO NOT add labels.` | Explicit exclusions |
| Realism trigger | `Natural lighting, DOF. Captured with Canon EOS 90D DSLR.` | Photography authenticity |
| Structured edits | `Make ALL edits: - [1] - [2] - [3]` | Multi-step changes |
| Complex logic | `Kittens MUST have heterochromatic eyes matching fur colors` | Precise conditions |

**Prompt Templates**:

**Photorealistic**:
```
A [subject] in [location], [lens] lens. [Lighting] creates [mood]. [Details].
[Camera angle]. Professional photography, natural lighting.
```

**Illustration**:
```
[Art style] illustration of [subject]. [Color palette]. [Line style].
[Background]. [Mood].
```

**Product**:
```
[Product] on [surface]. Materials: [finish]. Lighting: [setup].
Camera: [angle]. Background: [type]. Style: [commercial/lifestyle].
```

> Continued in `references/image-generation-cont3.md`.
