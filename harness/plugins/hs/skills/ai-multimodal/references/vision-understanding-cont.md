# Vision Understanding (continued 2/2)

## Multi-Image Analysis

### Batch Processing

```python
images = [
    PIL.Image.open(f'image{i}.jpg')
    for i in range(10)
]

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['Analyze these images and find common themes'] + images
)
```

### Image Comparison

```python
before = PIL.Image.open('before.jpg')
after = PIL.Image.open('after.jpg')

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Compare before and after. List all visible changes.',
        before,
        after
    ]
)
```

### Visual Search

```python
reference = PIL.Image.open('target.jpg')
candidates = [PIL.Image.open(f'option{i}.jpg') for i in range(5)]

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Find which candidate images contain objects similar to the reference',
        reference
    ] + candidates
)
```

## Best Practices

### Image Quality

1. **Resolution**: Use clear, non-blurry images
2. **Rotation**: Verify correct orientation
3. **Lighting**: Ensure good contrast and lighting
4. **Size optimization**: Balance quality vs token cost
5. **Format**: JPEG for photos, PNG for graphics

### Prompt Engineering

**Specific instructions**:
- "Identify all vehicles with their colors and positions"
- "Count people wearing blue shirts"
- "Extract text from the sign in the top-left corner"

**Output format**:
- "Return results as JSON with fields: category, count, description"
- "Format as markdown table"
- "List findings as numbered items"

**Few-shot examples**:
```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Example: For an image of a cat on a sofa, respond: "Object: cat, Location: sofa"',
        'Now analyze this image:',
        img_part
    ]
)
```

### File Management

1. Use File API for images >20MB
2. Use File API for repeated queries (saves tokens)
3. Files auto-delete after 48 hours
4. Clean up manually:
   ```python
   client.files.delete(name=myfile.name)
   ```

### Cost Optimization

**Token-efficient strategies**:
- Resize large images before upload
- Use File API for repeated queries
- Batch multiple images when related
- Use appropriate model (Flash vs Pro)

**Token costs** (Gemini 2.5 Flash at $1/1M):
- Small image (258 tokens): $0.000258
- HD image (1,548 tokens): $0.001548
- 4K image (6,192 tokens): $0.006192

## Common Use Cases

### 1. Product Analysis

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Analyze this product image:
        1. Identify the product
        2. List visible features
        3. Assess condition
        4. Estimate value range
        ''',
        img_part
    ]
)
```

### 2. Screenshot Analysis

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Extract all text and UI elements from this screenshot',
        img_part
    ]
)
```

### 3. Medical Imaging (Informational Only)

```python
response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=[
        'Describe visible features in this medical image. Note: This is for informational purposes only.',
        img_part
    ]
)
```

### 4. Chart/Graph Reading

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Extract data from this chart and format as JSON',
        img_part
    ]
)
```

### 5. Scene Understanding

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Analyze this scene:
        1. Location type
        2. Time of day
        3. Weather conditions
        4. Activities happening
        5. Mood/atmosphere
        ''',
        img_part
    ]
)
```

## Error Handling

```python
import time

def analyze_image_with_retry(image_path, prompt, max_retries=3):
    """Analyze image with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            with open(image_path, 'rb') as f:
                img_bytes = f.read()

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    prompt,
                    genai.types.Part.from_bytes(
                        data=img_bytes,
                        mime_type='image/jpeg'
                    )
                ]
            )
            return response.text
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            print(f"Retry {attempt + 1} after {wait_time}s: {e}")
            time.sleep(wait_time)
```

## Limitations

- Maximum 3,600 images per request
- OCR accuracy varies with text quality
- Object detection requires 2.0+ models
- Segmentation requires 2.5+ models
- No video frame extraction (use video API)
- Regional restrictions on child images (EEA, CH, UK)

---

## Related References

**Current**: Image Understanding

**Related Capabilities**:
- [Image Generation](./image-generation.md) - Create and edit images
- [Video Analysis](./video-analysis.md) - Analyze video frames
- [Video Generation](./video-generation.md) - Reference images for video generation

**Back to**: [AI Multimodal Skill](../SKILL.md)
