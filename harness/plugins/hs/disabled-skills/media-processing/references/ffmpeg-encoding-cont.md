# FFmpeg Video & Audio Encoding (continued 2/2)

## Codec Selection Guide

### Use Cases

| Use Case | Codec | Settings |
|----------|-------|----------|
| Web video | H.264 | CRF 23, preset medium |
| 4K streaming | H.265 | CRF 24, preset fast |
| YouTube upload | VP9 or H.264 | CRF 23 |
| Archive | H.265 or H.264 | CRF 18, preset slow |
| Low bandwidth | AV1 or H.265 | CRF 30 |
| Fast encoding | H.264 NVENC | preset fast |
| Maximum compatibility | H.264 | profile main, level 4.0 |

### Platform Compatibility

| Platform | Recommended | Supported |
|----------|------------|-----------|
| Web browsers | H.264 | H.264, VP9, AV1 |
| Mobile devices | H.264 | H.264, H.265 |
| Smart TVs | H.264 | H.264, H.265 |
| YouTube | VP9, H.264 | All |
| Social media | H.264 | H.264 |

## Best Practices

1. **Use CRF for most tasks** - Better than bitrate for variable content
2. **Start with CRF 23** - Good balance, adjust based on results
3. **Use slow preset** - For archival and final delivery
4. **Use fast preset** - For previews and testing
5. **Hardware acceleration** - When speed is critical
6. **Two-pass encoding** - When file size is fixed
7. **Match source frame rate** - Don't increase FPS
8. **Don't upscale resolution** - Keep original or downscale
9. **Test on short clips** - Verify settings before full encode
10. **Keep source files** - Original quality for re-encoding

## Troubleshooting

### Poor Quality Output
```bash
# Lower CRF value
ffmpeg -i input.mp4 -c:v libx264 -crf 18 -preset slow output.mp4

# Use slower preset
ffmpeg -i input.mp4 -c:v libx264 -crf 22 -preset veryslow output.mp4

# Increase bitrate (two-pass)
ffmpeg -y -i input.mp4 -c:v libx264 -b:v 5M -pass 1 -an -f null /dev/null
ffmpeg -i input.mp4 -c:v libx264 -b:v 5M -pass 2 -c:a aac output.mp4
```

### Slow Encoding
```bash
# Use faster preset
ffmpeg -i input.mp4 -c:v libx264 -preset ultrafast output.mp4

# Use hardware acceleration
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc output.mp4

# Reduce resolution
ffmpeg -i input.mp4 -vf scale=1280:-1 -c:v libx264 output.mp4
```

### Large File Size
```bash
# Increase CRF
ffmpeg -i input.mp4 -c:v libx264 -crf 26 output.mp4

# Use better codec
ffmpeg -i input.mp4 -c:v libx265 -crf 26 output.mp4

# Two-pass with target bitrate
ffmpeg -y -i input.mp4 -c:v libx264 -b:v 1M -pass 1 -an -f null /dev/null
ffmpeg -i input.mp4 -c:v libx264 -b:v 1M -pass 2 -c:a aac output.mp4
```
