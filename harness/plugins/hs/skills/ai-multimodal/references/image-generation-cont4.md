# Image Generation (continued 5/5)

## Troubleshooting

### aspect_ratio Parameter Error

**Error**: `Extra inputs are not permitted [type=extra_forbidden, input_value='1:1', input_type=str]`

**Cause**: The `aspect_ratio` parameter must be nested inside an `image_config` object, not passed directly to `GenerateContentConfig`.

**Incorrect Usage**:
```python
# ❌ This will fail
config = types.GenerateContentConfig(
    response_modalities=['image'],
    aspect_ratio='16:9'  # Wrong - not a direct parameter
)
```

**Correct Usage**:
```python
# ✅ Correct implementation
config = types.GenerateContentConfig(
    response_modalities=['Image'],  # Note: Capital 'I'
    image_config=types.ImageConfig(
        aspect_ratio='16:9'
    )
)
```

### Response Modality Case Sensitivity

The `response_modalities` parameter expects uppercase values:
- ✅ Correct: `['IMAGE']`, `['TEXT']`, `['IMAGE', 'TEXT']`
- ❌ Wrong: `['image']`, `['text']`, `['Image']`

### Image Size Parameter Not Supported

**Error**: `400 INVALID_ARGUMENT`

**Cause**: The `image_size` parameter in `ImageConfig` is not supported by all Nano Banana models.

**Solution**: Don't pass `image_size` unless explicitly needed. The API uses sensible defaults.

```python
# ✅ Works - no image_size
config=types.GenerateContentConfig(
    response_modalities=['IMAGE'],
    image_config=types.ImageConfig(
        aspect_ratio='16:9'  # Only aspect_ratio
    )
)

# ⚠️ May fail - with image_size (model-dependent)
config=types.GenerateContentConfig(
    response_modalities=['IMAGE'],
    image_config=types.ImageConfig(
        aspect_ratio='16:9',
        image_size='2K'  # Not supported by all models
    )
)
```

### Multi-Image Reference Issues

**Problem**: Poor composition with multiple reference images

**Solutions**:
1. Limit to 3-5 reference images for standard models
2. Use Pro model for up to 14 references
3. Collage multiple style refs into single image
4. Provide clear textual descriptions of how to blend styles

---

## Related References

**Current**: Image Generation

**Related Capabilities**:
- [Image Understanding](./vision-understanding.md) - Analyzing and editing reference images
- [Video Generation](./video-generation.md) - Creating animated video content
- [Audio Processing](./audio-processing.md) - Text-to-speech for multimedia

**Back to**: [AI Multimodal Skill](../SKILL.md)
