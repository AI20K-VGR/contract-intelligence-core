# Video Analysis Reference

Video understanding, temporal analysis, YouTube processing via Gemini API.

> **Note**: This guide covers video *analysis* (understanding existing videos). For video *generation* (creating new videos), see [Video Generation Reference](./video-generation.md).

## Core Capabilities

- **Video Summarization**: Create concise summaries
- **Question Answering**: Answer specific questions about content
- **Transcription**: Audio transcription with visual descriptions
- **Timestamp References**: Query specific moments (MM:SS format)
- **Video Clipping**: Process specific segments
- **Scene Detection**: Identify scene changes and transitions
- **Multiple Videos**: Compare up to 10 videos (2.5+)
- **YouTube Support**: Analyze YouTube videos directly
- **Custom Frame Rate**: Adjust FPS sampling

## Supported Formats

- MP4, MPEG, MOV, AVI, FLV, MPG, WebM, WMV, 3GPP

## Model Selection

### Gemini 3 Series (Latest)
- **gemini-3.1-pro-preview**: Latest, agentic workflows, 1M context, dynamic thinking
- **gemini-3-flash-preview**: Latest flash preview, fast inference

### Gemini 2.5 Series (Recommended)
- **gemini-2.5-pro**: Best quality, 1M context (2M extended-context available in some configs)
- **gemini-2.5-flash**: Balanced, 1M context (recommended)

### Context Windows
- **2M token models**: ~2 hours (default) or ~6 hours (low-res)
- **1M token models**: ~1 hour (default) or ~3 hours (low-res)

## Basic Video Analysis

### Local Video

```python
from google import genai
import os

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Upload video (File API for >20MB)
myfile = client.files.upload(file='video.mp4')

# Wait for processing
import time
while myfile.state.name == 'PROCESSING':
    time.sleep(1)
    myfile = client.files.get(name=myfile.name)

if myfile.state.name == 'FAILED':
    raise ValueError('Video processing failed')

# Analyze
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['Summarize this video in 3 key points', myfile]
)
print(response.text)
```

### YouTube Video

```python
from google.genai import types

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Summarize the main topics discussed',
        types.Part.from_uri(
            uri='https://www.youtube.com/watch?v=VIDEO_ID',
            mime_type='video/mp4'
        )
    ]
)
```

### Inline Video (<20MB)

```python
with open('short-clip.mp4', 'rb') as f:
    video_bytes = f.read()

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'What happens in this video?',
        types.Part.from_bytes(data=video_bytes, mime_type='video/mp4')
    ]
)
```

## Advanced Features

### Video Clipping

```python
# Analyze specific time range
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Summarize this segment',
        types.Part.from_video_metadata(
            file_uri=myfile.uri,
            start_offset='40s',
            end_offset='80s'
        )
    ]
)
```

### Custom Frame Rate

```python
# Lower FPS for static content (saves tokens)
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Analyze this presentation',
        types.Part.from_video_metadata(
            file_uri=myfile.uri,
            fps=0.5  # Sample every 2 seconds
        )
    ]
)

# Higher FPS for fast-moving content
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Analyze rapid movements in this sports video',
        types.Part.from_video_metadata(
            file_uri=myfile.uri,
            fps=5  # Sample 5 times per second
        )
    ]
)
```

### Multiple Videos (2.5+)

```python
video1 = client.files.upload(file='demo1.mp4')
video2 = client.files.upload(file='demo2.mp4')

# Wait for processing
for video in [video1, video2]:
    while video.state.name == 'PROCESSING':
        time.sleep(1)
        video = client.files.get(name=video.name)

response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=[
        'Compare these two product demos. Which explains features better?',
        video1,
        video2
    ]
)
```

## Temporal Understanding

### Timestamp-Based Questions

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'What happens at 01:15 and how does it relate to 02:30?',
        myfile
    ]
)
```

### Timeline Creation

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Create a timeline with timestamps:
        - Key events
        - Scene changes
        - Important moments
        Format: MM:SS - Description
        ''',
        myfile
    ]
)
```

### Scene Detection

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Identify all scene changes with timestamps and describe each scene',
        myfile
    ]
)
```

## Transcription

### Basic Transcription

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Transcribe the audio from this video',
        myfile
    ]
)
```

### With Visual Descriptions

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Transcribe with visual context:
        - Audio transcription
        - Visual descriptions of important moments
        - Timestamps for salient events
        ''',
        myfile
    ]
)
```

### Speaker Identification

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Transcribe with speaker labels and timestamps',
        myfile
    ]
)
```

> Continued in `references/video-analysis-cont.md`.
