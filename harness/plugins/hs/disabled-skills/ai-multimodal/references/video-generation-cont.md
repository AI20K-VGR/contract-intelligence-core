# Video Generation (continued 2/2)

## Common Use Cases

### 1. Product Demos

```python
response = client.models.generate_video(
    model='veo-3.0-fast-generate-001',
    prompt='''
    Professional product video:
    - Sleek smartphone rotating on a pedestal
    - Clean white background with soft shadows
    - Slow 360-degree rotation
    - Spotlight highlighting premium design
    - Modern, minimalist aesthetic
    ''',
    config=types.VideoGenerationConfig(
        resolution='1080p',
        aspect_ratio='1:1'
    )
)
```

### 2. Social Media Content

```python
response = client.models.generate_video(
    model='veo-3.1-fast-generate-preview',
    prompt='''
    Trendy social media clip:
    - Text overlay "NEW ARRIVAL" appears
    - Fashion product showcase
    - Quick cuts and dynamic camera
    - Vibrant colors, high energy
    - Upbeat pacing
    ''',
    config=types.VideoGenerationConfig(
        resolution='1080p',
        aspect_ratio='9:16'  # Mobile
    )
)
```

### 3. Explainer Animations

```python
response = client.models.generate_video(
    model='veo-3.1-generate-preview',
    prompt='''
    Educational animation:
    - Simple diagram illustrating data flow
    - Arrows and icons animating in sequence
    - Clean, clear visual hierarchy
    - Smooth transitions between steps
    - Professional corporate style
    ''',
    config=types.VideoGenerationConfig(
        resolution='720p',
        aspect_ratio='16:9'
    )
)
```

## Safety & Content Policy

### Safety Settings

```python
config = types.VideoGenerationConfig(
    safety_settings=[
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        )
    ]
)
```

### Prohibited Content

- Violence, gore, harm
- Sexually explicit content
- Hate speech, harassment
- Copyrighted characters/brands
- Real people (without consent)
- Misleading/deceptive content

## Limitations

- **Duration**: Fixed 8 seconds (as of Sept 2025)
- **Frame Rate**: 24fps only
- **File Size**: ~5-20MB per video
- **Generation Time**: 30s-2min depending on resolution
- **Reference Images**: Max 3 images
- **Preview Status**: API may change (3.1 models)
- **Audio**: Cannot upload custom audio (native only)
- **No real-time**: Pre-generation required

## Troubleshooting

### Long Generation Times

```python
import time

# Track generation progress
start = time.time()
response = client.models.generate_video(...)
duration = time.time() - start
print(f"Generated in {duration:.1f}s")
```

**Expected times**:
- Fast models + 720p: 30-45s
- Standard models + 720p: 45-90s
- Fast models + 1080p: 45-60s
- Standard models + 1080p: 60-120s

### Safety Filter Blocking

```python
try:
    response = client.models.generate_video(...)
except Exception as e:
    if 'safety' in str(e).lower():
        print("Video blocked by safety filters")
        # Modify prompt and retry
```

### Quota Exceeded

```python
# Implement exponential backoff
import time

def generate_with_retry(model, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.models.generate_video(model=model, prompt=prompt)
        except Exception as e:
            if '429' in str(e):  # Rate limit
                wait = 2 ** attempt
                print(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded")
```

## Cost Estimation

**Pricing**: TBD (preview models)

**Estimated based on compute**:
- Fast + 720p: ~$0.05-$0.10 per video
- Standard + 1080p: ~$0.15-$0.25 per video

**Monitor**: https://ai.google.dev/pricing

## Resources

- [Veo API Docs](https://ai.google.dev/gemini-api/docs/video)
- [Video Generation Guide](https://ai.google.dev/gemini-api/docs/video#model-versions)
- [Content Policy](https://ai.google.dev/gemini-api/docs/safety)
- [Get API Key](https://aistudio.google.com/apikey)

---

## Related References

**Current**: Video Generation

**Related Capabilities**:
- [Video Analysis](./video-analysis.md) - Understanding existing videos
- [Image Generation](./image-generation.md) - Creating static images
- [Image Understanding](./vision-understanding.md) - Analyzing reference images

**Back to**: [AI Multimodal Skill](../SKILL.md)
