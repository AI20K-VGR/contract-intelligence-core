# Video Analysis (continued 2/2)

## Common Use Cases

### 1. Video Summarization

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Summarize this video:
        1. Main topic and purpose
        2. Key points with timestamps
        3. Conclusion or call-to-action
        ''',
        myfile
    ]
)
```

### 2. Educational Content

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Create educational materials:
        1. List key concepts taught
        2. Create 5 quiz questions with answers
        3. Provide timestamp for each concept
        ''',
        myfile
    ]
)
```

### 3. Action Detection

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'List all actions performed in this tutorial with timestamps',
        myfile
    ]
)
```

### 4. Content Moderation

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Review video content:
        1. Identify any problematic content
        2. Note timestamps of concerns
        3. Provide content rating recommendation
        ''',
        myfile
    ]
)
```

### 5. Interview Analysis

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Analyze interview:
        1. Questions asked (timestamps)
        2. Key responses
        3. Candidate body language and demeanor
        4. Overall assessment
        ''',
        myfile
    ]
)
```

### 6. Sports Analysis

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Analyze sports video:
        1. Key plays with timestamps
        2. Player movements and positioning
        3. Game strategy observations
        ''',
        types.Part.from_video_metadata(
            file_uri=myfile.uri,
            fps=5  # Higher FPS for fast action
        )
    ]
)
```

## YouTube Specific Features

### Public Video Requirements

- Video must be public (not private or unlisted)
- No age-restricted content
- Valid video ID required

### Usage Example

```python
# YouTube URL
youtube_uri = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        'Create chapter markers with timestamps',
        types.Part.from_uri(uri=youtube_uri, mime_type='video/mp4')
    ]
)
```

### Rate Limits

- **Free tier**: 8 hours of YouTube video per day
- **Paid tier**: No length-based limits
- Public videos only

## Token Calculation

Video tokens depend on resolution and FPS:

**Default resolution** (~300 tokens/second):
- 1 minute = 18,000 tokens
- 10 minutes = 180,000 tokens
- 1 hour = 1,080,000 tokens

**Low resolution** (~100 tokens/second):
- 1 minute = 6,000 tokens
- 10 minutes = 60,000 tokens
- 1 hour = 360,000 tokens

**Context windows**:
- 2M tokens ≈ 2 hours (default) or 6 hours (low-res)
- 1M tokens ≈ 1 hour (default) or 3 hours (low-res)

## Best Practices

### File Management

1. Use File API for videos >20MB (most videos)
2. Wait for ACTIVE state before analysis
3. Files auto-delete after 48 hours
4. Clean up manually:
   ```python
   client.files.delete(name=myfile.name)
   ```

### Optimization Strategies

**Reduce token usage**:
- Process specific segments using start/end offsets
- Use lower FPS for static content
- Use low-resolution mode for long videos
- Split very long videos into chunks

**Improve accuracy**:
- Provide context in prompts
- Use higher FPS for fast-moving content
- Use Pro model for complex analysis
- Be specific about what to extract

### Prompt Engineering

**Effective prompts**:
- "Summarize key points with timestamps in MM:SS format"
- "Identify all scene changes and describe each scene"
- "Extract action items mentioned with timestamps"
- "Compare these two videos on: X, Y, Z criteria"

**Structured output**:
```python
from pydantic import BaseModel
from typing import List

class VideoEvent(BaseModel):
    timestamp: str  # MM:SS format
    description: str
    category: str

class VideoAnalysis(BaseModel):
    summary: str
    events: List[VideoEvent]
    duration: str

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['Analyze this video', myfile],
    config=genai.types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=VideoAnalysis
    )
)
```

### Error Handling

```python
import time

def upload_and_process_video(file_path, max_wait=300):
    """Upload video and wait for processing"""
    myfile = client.files.upload(file=file_path)

    elapsed = 0
    while myfile.state.name == 'PROCESSING' and elapsed < max_wait:
        time.sleep(5)
        myfile = client.files.get(name=myfile.name)
        elapsed += 5

    if myfile.state.name == 'FAILED':
        raise ValueError(f'Video processing failed: {myfile.state.name}')

    if myfile.state.name == 'PROCESSING':
        raise TimeoutError(f'Processing timeout after {max_wait}s')

    return myfile
```

## Cost Optimization

**Token costs** (Gemini 2.5 Flash at $1/1M):
- 1 minute video (default): 18,000 tokens = $0.018
- 10 minute video: 180,000 tokens = $0.18
- 1 hour video: 1,080,000 tokens = $1.08

**Strategies**:
- Use video clipping for specific segments
- Lower FPS for static content
- Use low-resolution mode for long videos
- Batch related queries on same video
- Use context caching for repeated queries

## Limitations

- Maximum 6 hours (low-res) or 2 hours (default)
- YouTube videos must be public
- No live streaming analysis
- Files expire after 48 hours
- Processing time varies by video length
- No real-time processing
- Limited to 10 videos per request (2.5+)

---

## Related References

**Current**: Video Analysis

**Related Capabilities**:
- [Video Generation](./video-generation.md) - Creating videos from text/images
- [Audio Processing](./audio-processing.md) - Extract and analyze audio tracks
- [Image Understanding](./vision-understanding.md) - Analyze individual frames

**Back to**: [AI Multimodal Skill](../SKILL.md)
