# Image Generation (continued 4/5)

## Advanced Techniques

### Iterative Refinement

```python
# Initial generation
response1 = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='A futuristic city skyline'
)

# Save first version
with open('v1.png', 'wb') as f:
    f.write(response1.candidates[0].content.parts[0].inline_data.data)

# Refine
img = PIL.Image.open('v1.png')
response2 = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        'Add flying vehicles and neon signs',
        img
    ]
)
```

### Negative Prompts (Indirect)

```python
# Instead of "no blur", be specific about what you want
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='A crystal clear, sharp photograph of a diamond ring with perfect focus and high detail'
)
```

### Consistent Style Across Images

```python
base_prompt = "Digital art, vibrant colors, cel-shaded style, clean lines"

prompts = [
    f"{base_prompt}, a warrior character",
    f"{base_prompt}, a mage character",
    f"{base_prompt}, a rogue character"
]

for i, prompt in enumerate(prompts):
    response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=prompt
    )
    # Save each character
```

## Safety Settings

### Configure Safety Filters

```python
config = types.GenerateContentConfig(
    response_modalities=['image'],
    safety_settings=[
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        )
    ]
)
```

### Available Categories

- `HARM_CATEGORY_HATE_SPEECH`
- `HARM_CATEGORY_DANGEROUS_CONTENT`
- `HARM_CATEGORY_HARASSMENT`
- `HARM_CATEGORY_SEXUALLY_EXPLICIT`

### Thresholds

- `BLOCK_NONE`: No blocking
- `BLOCK_LOW_AND_ABOVE`: Block low probability and above
- `BLOCK_MEDIUM_AND_ABOVE`: Block medium and above (default)
- `BLOCK_ONLY_HIGH`: Block only high probability

## Common Use Cases

### 1. Marketing Assets

```python
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='''Professional product photography:
    - Sleek smartphone on minimalist white surface
    - Dramatic side lighting creating subtle shadows
    - Shallow depth of field, crisp focus
    - Clean, modern aesthetic
    - 4K quality
    ''',
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='4:3'
    )
)
```

### 2. Concept Art

```python
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='''Fantasy concept art:
    - Ancient floating islands connected by chains
    - Waterfalls cascading into clouds below
    - Magical crystals glowing on the islands
    - Epic scale, dramatic lighting
    - Detailed digital painting style
    ''',
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='16:9'
    )
)
```

### 3. Social Media Graphics

```python
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='''Instagram post design:
    - Pastel gradient background (pink to blue)
    - Motivational quote layout
    - Modern minimalist style
    - Clean typography
    - Mobile-friendly composition
    ''',
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='1:1'
    )
)
```

### 4. Illustration

```python
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='''Children's book illustration:
    - Friendly cartoon dragon reading a book
    - Bright, cheerful colors
    - Soft, rounded shapes
    - Whimsical forest background
    - Warm, inviting atmosphere
    ''',
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='4:3'
    )
)
```

### 5. UI/UX Mockups

```python
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='''Modern mobile app interface:
    - Clean dashboard design
    - Card-based layout
    - Soft shadows and gradients
    - Contemporary color scheme (blue and white)
    - Professional fintech aesthetic
    ''',
    config=types.GenerateContentConfig(
        response_modalities=['image'],
        aspect_ratio='9:16'
    )
)
```

## Best Practices

### Prompt Quality

1. **Be specific**: More detail = better results
2. **Order matters**: Most important elements first
3. **Use examples**: Reference known styles or artists
4. **Avoid contradictions**: Don't ask for opposing styles
5. **Test and iterate**: Refine prompts based on results

### File Management

```python
# Save with descriptive names
timestamp = int(time.time())
filename = f'generated_{timestamp}_{aspect_ratio}.png'

with open(filename, 'wb') as f:
    f.write(image_data)
```

### Cost Optimization

**Nano Banana 2 pricing (per image)**:
| Resolution | Cost/Image | Batch (50% off) |
|-----------|-----------|-----------------|
| 512px | $0.045 | $0.023 |
| 1K | $0.067 | $0.034 |
| 2K | $0.101 | $0.051 |
| 4K | $0.151 | $0.076 |

**Flash Image token costs**:
- 1 image: 1,290 tokens = $0.00129 (Flash Image at $1/1M)
- 10 images: 12,900 tokens = $0.0129
- 100 images: 129,000 tokens = $0.129

**Strategies**:
- Generate fewer iterations
- Use text modality first to validate concept
- Batch similar requests
- Cache prompts for consistent style

## Error Handling

### Safety Filter Blocking

```python
try:
    response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=prompt
    )
except Exception as e:
    # Check block reason
    if hasattr(e, 'prompt_feedback'):
        print(f"Blocked: {e.prompt_feedback.block_reason}")
        # Modify prompt and retry
```

### Token Limit Exceeded

```python
# Keep prompts concise
if len(prompt) > 1000:
    # Truncate or simplify
    prompt = prompt[:1000]
```

## Limitations

### Imagen 4 Constraints
- **Language**: English prompts only
- **Prompt length**: Maximum 480 tokens
- **Output**: 1-4 images per request
- **Watermark**: All images include SynthID watermark
- **Fast model**: No `imageSize` parameter support (fixed resolution)
- **Text rendering**: Limited to ~25 characters for optimal results
- **Regional restrictions**: Child images restricted in EEA, CH, UK
- **Cannot replicate**: Specific people or copyrighted characters

### Nano Banana (Gemini) Constraints
- **Language**: English prompts primary support
- **Context**: 32K token window
- **Multi-image**: Standard models ~3-5 refs; Pro up to 14 refs
- **Text rendering**: Standard limited; Pro supports 4K text
- **Watermark**: All images include SynthID watermark
- **Case sensitivity**: `response_modalities` must be uppercase (`'IMAGE'`, `'TEXT'`)
- **Size format**: `image_size` must have uppercase K (`'1K'`, `'2K'`, `'4K'`)

### General Limitations
- Maximum 14 input images for composition (Pro only)
- No video or animation generation (use Veo for video)
- No real-time generation

> Continued in `references/image-generation-cont4.md`.
