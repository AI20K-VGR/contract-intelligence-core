# Audio Processing (continued 2/2)

## Common Use Cases

### 1. Meeting Transcription

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Transcribe this meeting with:
        1. Speaker labels
        2. Timestamps for topic changes
        3. Action items highlighted
        ''',
        myfile
    ]
)
```

### 2. Podcast Summary

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Create podcast summary with:
        1. Main topics with timestamps
        2. Key quotes from each speaker
        3. Recommended episode highlights
        ''',
        myfile
    ]
)
```

### 3. Interview Analysis

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Analyze interview:
        1. Questions asked with timestamps
        2. Key responses from interviewee
        3. Overall sentiment and tone
        ''',
        myfile
    ]
)
```

### 4. Content Verification

```python
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        '''Verify audio content:
        1. Check for specific keywords or phrases
        2. Identify any compliance issues
        3. Note any concerning statements with timestamps
        ''',
        myfile
    ]
)
```

### 5. Multilingual Transcription

```python
# Gemini auto-detects language
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=['Transcribe this audio and translate to English if needed.', myfile]
)
```

## Token Costs

**Audio Input** (32 tokens/second):
- 1 minute = 1,920 tokens
- 10 minutes = 19,200 tokens
- 1 hour = 115,200 tokens
- 9.5 hours = 1,094,400 tokens

**Example costs** (Gemini 2.5 Flash at $1/1M):
- 1 hour audio: 115,200 tokens = $0.12
- Full day podcast (8 hours): 921,600 tokens = $0.92

## Limitations

- Maximum 9.5 hours per request
- Auto-downsampled to 16 Kbps mono (quality loss)
- Files expire after 48 hours
- No real-time streaming support
- Non-speech audio less accurate than speech

---

## Related References

**Current**: Audio Processing

**Related Capabilities**:
- [Video Analysis](./video-analysis.md) - Extract audio from videos
- [Video Generation](./video-generation.md) - Generate videos with native audio
- [Image Understanding](./vision-understanding.md) - Analyze audio with visual context

**Back to**: [AI Multimodal Skill](../SKILL.md)
