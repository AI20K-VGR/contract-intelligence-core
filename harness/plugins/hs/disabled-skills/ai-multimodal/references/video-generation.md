# Video Generation Reference

Video creation via Veo models, Gemini API.

## Core Capabilities

- **Text-to-Video**: Generate 8-second videos from text prompts
- **Image-to-Video**: Animate images with text direction
- **Video Extension**: Continue previously generated videos
- **Frame Control**: Precise camera movements and effects
- **Native Audio**: Synchronized audio generation
- **Multiple Resolutions**: 720p and 1080p output
- **Aspect Ratios**: 16:9, 9:16, 1:1

## Models

### Veo 3.1 Preview (Latest)

**veo-3.1-generate-preview** - Latest with advanced controls
- Frame-specific generation
- Up to 3 reference images for image-to-video
- Video extension capability
- Native audio generation
- Resolution: 720p, 1080p
- Duration: 8 seconds at 24fps
- Status: Preview (API may change)
- Updated: September 2025

**veo-3.1-fast-generate-preview** - Speed-optimized
- Optimized for business use cases
- Programmatic ad creation
- Social media content
- Same features as standard but faster
- Status: Preview
- Updated: September 2025

### Veo 3.0 Stable

**veo-3.0-generate-001** - Production-ready
- Native audio generation
- Text-to-video and image-to-video
- 720p and 1080p (16:9 only)
- 8 seconds at 24fps
- Status: Stable
- Updated: July 2025

**veo-3.0-fast-generate-001** - Stable fast variant
- Speed-optimized stable version
- Same reliability as 3.0
- Status: Stable
- Updated: July 2025

## Model Comparison

| Model | Speed | Features | Audio | Status | Best For |
|-------|-------|----------|-------|--------|----------|
| veo-3.1-preview | Medium | All | ✓ | Preview | Latest features |
| veo-3.1-fast | Fast | All | ✓ | Preview | Business/speed |
| veo-3.0-001 | Medium | Standard | ✓ | Stable | Production |
| veo-3.0-fast | Fast | Standard | ✓ | Stable | Production/speed |

## Quick Start

### Text-to-Video

```python
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Basic generation
response = client.models.generate_video(
    model='veo-3.1-generate-preview',
    prompt='A serene beach at sunset with gentle waves rolling onto the shore',
    config=types.VideoGenerationConfig(
        resolution='1080p',
        aspect_ratio='16:9'
    )
)

# Save video
with open('output.mp4', 'wb') as f:
    f.write(response.video.data)
```

### Image-to-Video

```python
import PIL.Image

# Load reference image
ref_image = PIL.Image.open('beach.jpg')

# Animate the image
response = client.models.generate_video(
    model='veo-3.1-generate-preview',
    prompt='Camera slowly pans across the scene from left to right',
    reference_images=[ref_image],
    config=types.VideoGenerationConfig(
        resolution='1080p'
    )
)
```

### Multiple Reference Images

```python
# Use up to 3 reference images for complex scenes
img1 = PIL.Image.open('foreground.jpg')
img2 = PIL.Image.open('background.jpg')
img3 = PIL.Image.open('subject.jpg')

response = client.models.generate_video(
    model='veo-3.1-generate-preview',
    prompt='Combine these elements into a cohesive animated scene',
    reference_images=[img1, img2, img3],
    config=types.VideoGenerationConfig(
        resolution='1080p',
        aspect_ratio='16:9'
    )
)
```

## Advanced Features

### Video Extension

```python
# Continue from previously generated video
previous_video = open('part1.mp4', 'rb').read()

response = client.models.extend_video(
    model='veo-3.1-generate-preview',
    video=previous_video,
    prompt='The scene transitions to nighttime with stars appearing'
)
```

### Frame Control

```python
# Precise camera movements
response = client.models.generate_video(
    model='veo-3.1-generate-preview',
    prompt='A mountain landscape',
    config=types.VideoGenerationConfig(
        resolution='1080p',
        camera_motion='zoom_in',  # Options: zoom_in, zoom_out, pan_left, pan_right, tilt_up, tilt_down, static
        motion_speed='slow'  # Options: slow, medium, fast
    )
)
```

## Prompt Engineering

### Effective Video Prompts

**Structure**:
1. **Subject**: What's in the scene
2. **Action**: What's happening
3. **Camera**: How it's filmed
4. **Style**: Visual treatment
5. **Timing**: Pacing details

**Example**:
```
"A hummingbird [subject] hovers near a red flower, then flies away [action].
Slow-motion close-up shot [camera] with vibrant colors and soft focus background [style].
Gentle, peaceful pacing [timing]."
```

### Action Verbs

**Movement**:
- "walks", "runs", "flies", "swims", "dances"
- "rotates", "spins", "rolls", "bounces"
- "emerges", "disappears", "transforms"

**Camera**:
- "zoom in on", "pull back from", "follow"
- "orbit around", "track alongside"
- "tilt up to reveal", "pan across"

**Transitions**:
- "gradually changes from... to..."
- "morphs into", "dissolves into"
- "cuts to", "fades to"

### Timing Control

```python
# Explicit timing in prompt
prompt = '''
0-2s: Close-up of a seed in soil
2-4s: Time-lapse of sprout emerging
4-6s: Growing into a small plant
6-8s: Zoom out to show garden context
'''
```

## Configuration Options

### Resolution

```python
config = types.VideoGenerationConfig(
    resolution='1080p'  # Options: 720p, 1080p
)
```

**Considerations**:
- 1080p: Higher quality, longer generation time, larger file
- 720p: Faster generation, smaller file, good for drafts

### Aspect Ratios

```python
config = types.VideoGenerationConfig(
    aspect_ratio='16:9'  # Options: 16:9, 9:16, 1:1
)
```

**Use Cases**:
- 16:9: Landscape, YouTube, traditional video
- 9:16: Mobile, TikTok, Instagram Stories
- 1:1: Square, Instagram feed, versatile

### Audio Control

```python
config = types.VideoGenerationConfig(
    include_audio=True  # Default: True
)
```

Native audio auto-generates, synced to video content.

## Best Practices

### 1. Prompt Quality

**Be specific**:
- ❌ "A person walking"
- ✅ "A young woman in a red coat walking through a park in autumn"

**Include motion**:
- ❌ "A city street"
- ✅ "A busy city street with cars passing and people crossing"

**Specify camera**:
- ❌ "A mountain"
- ✅ "Aerial drone shot slowly ascending over a snow-capped mountain"

### 2. Reference Images

**Quality**:
- Use high-resolution images (1080p+)
- Clear, well-lit subjects
- Minimal motion blur

**Composition**:
- Match desired final aspect ratio
- Leave room for motion/movement
- Consider camera angle in prompt

### 3. Performance Optimization

**Generation Time**:
- 720p: ~30-60 seconds
- 1080p: ~60-120 seconds
- Fast models: 30-50% faster

**Strategies**:
- Use 720p for iteration/drafts
- Use fast models for rapid feedback
- Batch multiple requests
- Use async processing for UI responsiveness

> Continued in `references/video-generation-cont.md`.
