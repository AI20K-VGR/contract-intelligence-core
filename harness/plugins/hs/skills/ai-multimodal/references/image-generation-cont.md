# Image Generation (continued 2/5)

## Quick Start

### Basic Generation (Default - Nano Banana 2)

```python
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Nano Banana 2 - NEW DEFAULT (fastest, near-Pro quality, web grounding)
response = client.models.generate_content(
    model='gemini-3.1-flash-image-preview',
    contents='A serene mountain landscape at sunset with snow-capped peaks',
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],  # Uppercase required
        image_config=types.ImageConfig(
            aspect_ratio='16:9',
            image_size='2K'  # 512px, 1K, 2K, 4K - uppercase K required
        )
    )
)

# Save images
for i, part in enumerate(response.candidates[0].content.parts):
    if part.inline_data:
        with open(f'output-{i}.png', 'wb') as f:
            f.write(part.inline_data.data)
```

### Alternative - Imagen 4 (Production Quality)

```python
# Imagen 4 Standard - alternative for production workflows
response = client.models.generate_images(
    model='imagen-4.0-generate-001',
    prompt='Professional product photography of smartphone',
    config=types.GenerateImagesConfig(
        numberOfImages=1,
        aspectRatio='16:9',
        imageSize='1K'
    )
)

# Save Imagen 4 output
for i, generated_image in enumerate(response.generated_images):
    with open(f'output-{i}.png', 'wb') as f:
        f.write(generated_image.image.image_bytes)
```

### Imagen 4 Quality Variants

```python
# Ultra quality (marketing assets)
response = client.models.generate_images(
    model='imagen-4.0-ultra-generate-001',
    prompt='Professional product photography of smartphone',
    config=types.GenerateImagesConfig(
        numberOfImages=1,
        imageSize='2K'  # Use 2K for ultra (Standard/Ultra only)
    )
)

# Fast generation (bulk)
# Note: Fast model doesn't support imageSize parameter
response = client.models.generate_images(
    model='imagen-4.0-fast-generate-001',
    prompt='Quick concept sketch of robot character',
    config=types.GenerateImagesConfig(
        numberOfImages=4,  # Generate multiple variants (default: 4)
        aspectRatio='1:1'
    )
)
```

### Nano Banana Pro (4K Text, Reasoning)

```python
# Nano Banana Pro - for text rendering and complex prompts
response = client.models.generate_content(
    model='gemini-3-pro-image-preview',
    contents='A futuristic cityscape with neon lights',
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],  # Uppercase required
        image_config=types.ImageConfig(
            aspect_ratio='16:9',
            image_size='4K'  # 4K text rendering
        )
    )
)

# Nano Banana Pro - with Thinking mode and Search grounding
response = client.models.generate_content(
    model='gemini-3-pro-image-preview',
    contents='Current weather in Tokyo visualized as artistic infographic',
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],  # Both text and image
        image_config=types.ImageConfig(
            aspect_ratio='1:1',
            image_size='4K'
        )
    ),
    tools=[{'google_search': {}}]  # Enable search grounding
)

# Save from content parts
for i, part in enumerate(response.candidates[0].content.parts):
    if part.inline_data:
        with open(f'output-{i}.png', 'wb') as f:
            f.write(part.inline_data.data)
```

### Multi-Image Reference (Nano Banana Pro)

```python
from PIL import Image

# Up to 14 reference images (6 objects + 5 humans recommended)
img1 = Image.open('style_ref.png')
img2 = Image.open('color_ref.png')
img3 = Image.open('composition_ref.png')

response = client.models.generate_content(
    model='gemini-3-pro-image-preview',
    contents=[
        'Blend these reference styles into a cohesive hero image for a tech product',
        img1, img2, img3
    ],
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio='16:9',
            image_size='4K'
        )
    )
)
```

### Nano Banana 2 with Web Grounding

```python
# Nano Banana 2 - real-time web integration for brands, landmarks, events
response = client.models.generate_content(
    model='gemini-3.1-flash-image-preview',
    contents='Current Apple Vision Pro product shot with accurate branding',
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio='16:9',
            image_size='2K'
        )
    )
)
```

### Nano Banana 2 with Reasoning Levels

```python
# Use reasoning levels for complex prompts
response = client.models.generate_content(
    model='gemini-3.1-flash-image-preview',
    contents='A photorealistic scene of 5 diverse characters sitting around a campfire, each with distinct clothing and accessories, consistent lighting from the fire',
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio='16:9',
            image_size='4K'
        )
    )
)
# Nano Banana 2 auto-selects reasoning level (Minimal/High/Dynamic)
# For explicit control, check API docs for reasoning_level parameter
```

### Multi-Turn Refinement Chat

```python
# Conversational image refinement (works with any Nano Banana model)
chat = client.chats.create(
    model='gemini-3.1-flash-image-preview',  # or gemini-2.5-flash-image
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE']
    )
)

# Initial generation
response1 = chat.send_message('Create a minimalist logo for a coffee brand called "Brew"')

# Iterative refinement
response2 = chat.send_message('Make the text bolder and add steam rising from the cup')
response3 = chat.send_message('Change the color palette to warm earth tones')
```

## API Differences

### Imagen 4 vs Nano Banana (Gemini Native)

| Feature | Imagen 4 | Nano Banana (Gemini) |
|---------|----------|---------------------|
| Method | `generate_images()` | `generate_content()` |
| Config | `GenerateImagesConfig` | `GenerateContentConfig` |
| Prompt param | `prompt` (string) | `contents` (string/list) |
| Image count | `numberOfImages` (camelCase) | N/A (single per request) |
| Aspect ratio | `aspectRatio` (camelCase) | `aspect_ratio` (snake_case) |
| Size | `imageSize` | `image_size` |
| Response | `generated_images[i].image.image_bytes` | `candidates[0].content.parts[i].inline_data.data` |
| Multi-image input | ❌ | ✅ Up to 14 references |
| Multi-turn chat | ❌ | ✅ Conversational |
| Search grounding | ❌ | ✅ (Pro only) |
| Thinking mode | ❌ | ✅ (Pro only) |
| Text rendering | Limited | 4K (Pro) |

**Imagen 4** uses `generate_images()`:
```python
response = client.models.generate_images(
    model='imagen-4.0-generate-001',
    prompt='...',
    config=types.GenerateImagesConfig(
        numberOfImages=1,      # camelCase
        aspectRatio='16:9',    # camelCase
        imageSize='1K'         # Standard/Ultra only
    )
)
# Access: response.generated_images[0].image.image_bytes
```

**Nano Banana** uses `generate_content()`:
```python
response = client.models.generate_content(
    model='gemini-3.1-flash-image-preview',  # or gemini-2.5-flash-image, gemini-3-pro-image-preview
    contents='...',
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],  # Uppercase required
        image_config=types.ImageConfig(
            aspect_ratio='16:9',        # snake_case
            image_size='2K'             # 1K, 2K, 4K - uppercase K
        )
    )
)
# Access: response.candidates[0].content.parts[0].inline_data.data
```

**Critical Notes**:
1. `response_modalities` values MUST be uppercase: `'IMAGE'`, `'TEXT'`
2. `image_size` value MUST have uppercase K: `'1K'`, `'2K'`, `'4K'`
3. Imagen 4 Fast model doesn't support `imageSize` parameter

## Aspect Ratios

| Ratio | Resolution (1K) | Use Case | Token Cost |
|-------|----------------|----------|------------|
| 1:1 | 1024×1024 | Social media, avatars, icons | 1290 |
| 2:3 | 682×1024 | Vertical portraits | 1290 |
| 3:2 | 1024×682 | Horizontal portraits | 1290 |
| 3:4 | 768×1024 | Vertical posters | 1290 |
| 4:3 | 1024×768 | Traditional media | 1290 |
| 4:5 | 819×1024 | Instagram portrait | 1290 |
| 5:4 | 1024×819 | Horizontal photos | 1290 |
| 9:16 | 576×1024 | Mobile/stories/reels | 1290 |
| 16:9 | 1024×576 | Landscapes, banners, YouTube | 1290 |
| 21:9 | 1024×438 | Ultrawide/cinematic | 1290 |

All ratios cost the same: 1,290 tokens per image (Gemini models).

> Continued in `references/image-generation-cont2.md`.
