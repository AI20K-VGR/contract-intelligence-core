# Vision Understanding Reference

Image analysis, object detection, visual understanding via Gemini API.

## Core Capabilities

- **Captioning**: Generate descriptive text for images
- **Classification**: Categorize and identify content
- **Visual Q&A**: Answer questions about images
- **Object Detection**: Locate objects with bounding boxes (2.0+)
- **Segmentation**: Create pixel-level masks (2.5+)
- **Multi-image**: Compare up to 3,600 images
- **OCR**: Extract text from images
- **Document Understanding**: Process PDFs with vision

## Supported Formats

- **Images**: PNG, JPEG, WEBP, HEIC, HEIF
- **Documents**: PDF (up to 1,000 pages)
- **Size Limits**:
  - Inline: 20MB max total request
  - File API: 2GB per file
  - Max images: 3,600 per request

## Model Selection

### Gemini 2.5 Series
- **gemini-2.5-pro**: Best quality, segmentation + detection
- **gemini-2.5-flash**: Fast, efficient, all features
- **gemini-2.5-flash-lite**: Lightweight, all features

### Feature Requirements
- **Segmentation**: Requires 2.5+ models
- **Object Detection**: Requires 2.0+ models
- **Multi-image**: All models (up to 3,600 images)

## Basic Image Analysis

### Image Captioning

```python
from google import genai
import os

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Local file
with open('image.jpg', 'rb') as f:
    img_bytes = f.read()

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Describe this image in detail',
        genai.types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
    ]
)
print(response.text)
```

### Image Classification

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Classify this image. Provide category and confidence level.',
        img_part
    ]
)
```

### Visual Question Answering

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'How many people are in this image and what are they doing?',
        img_part
    ]
)
```

## Advanced Features

### Object Detection (2.5+)

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Detect all objects in this image and provide bounding boxes',
        img_part
    ]
)

# Returns bounding box coordinates: [ymin, xmin, ymax, xmax]
# Normalized to [0, 1000] range
```

### Segmentation (2.5+)

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Create a segmentation mask for all people in this image',
        img_part
    ]
)

# Returns pixel-level masks for requested objects
```

### Multi-Image Comparison

```python
import PIL.Image

img1 = PIL.Image.open('photo1.jpg')
img2 = PIL.Image.open('photo2.jpg')

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Compare these two images. What are the differences?',
        img1,
        img2
    ]
)
```

### OCR and Text Extraction

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Extract all visible text from this image',
        img_part
    ]
)
```

## Input Methods

### Inline Data (<20MB)

```python
from google.genai import types

# From file
with open('image.jpg', 'rb') as f:
    img_bytes = f.read()

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Analyze this image',
        types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
    ]
)
```

### PIL Image

```python
import PIL.Image

img = PIL.Image.open('photo.jpg')

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['What is in this image?', img]
)
```

### File API (>20MB or Reuse)

```python
# Upload once
myfile = client.files.upload(file='large-image.jpg')

# Use multiple times
response1 = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['Describe this image', myfile]
)

response2 = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['What colors dominate this image?', myfile]
)
```

### URL (Public Images)

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Analyze this image',
        types.Part.from_uri(
            uri='https://example.com/image.jpg',
            mime_type='image/jpeg'
        )
    ]
)
```

## Token Calculation

Images consume tokens based on size:

**Small images** (≤384px both dimensions): 258 tokens

**Large images**: Tiled into 768×768 chunks, 258 tokens each

**Formula**:
```
crop_unit = floor(min(width, height) / 1.5)
tiles = (width / crop_unit) × (height / crop_unit)
total_tokens = tiles × 258
```

**Examples**:
- 256×256: 258 tokens (small)
- 512×512: 258 tokens (small)
- 960×540: 6 tiles = 1,548 tokens
- 1920×1080: 6 tiles = 1,548 tokens
- 3840×2160 (4K): 24 tiles = 6,192 tokens

## Structured Output

### JSON Schema Output

```python
from pydantic import BaseModel
from typing import List

class ObjectDetection(BaseModel):
    object_name: str
    confidence: float
    bounding_box: List[int]  # [ymin, xmin, ymax, xmax]

class ImageAnalysis(BaseModel):
    description: str
    objects: List[ObjectDetection]
    scene_type: str

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['Analyze this image', img_part],
    config=genai.types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=ImageAnalysis
    )
)

result = ImageAnalysis.model_validate_json(response.text)
```

> Continued in `references/vision-understanding-cont.md`.
