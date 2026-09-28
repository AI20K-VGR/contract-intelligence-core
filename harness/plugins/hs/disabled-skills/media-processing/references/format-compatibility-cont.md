# Format Compatibility & Conversion Guide (continued 2/2)

## Codec Selection Guide

### Choose H.264 When:
- Maximum compatibility needed
- Targeting older devices
- Streaming to unknown devices
- Social media upload
- Fast encoding required

### Choose H.265 When:
- 4K video encoding
- Storage space limited
- Modern device targets
- Archival quality needed
- Bandwidth constrained

### Choose VP9 When:
- YouTube upload
- Open-source requirement
- Chrome/Firefox primary
- Royalty-free needed

### Choose AV1 When:
- Future-proofing content
- Maximum compression needed
- Encoding time not critical
- Modern platform targets

## Format Migration Strategies

### Archive to Web

```bash
# High-res archive -> Web-optimized
for img in archive/*.tif; do
  base=$(basename "$img" .tif)
  magick "$img" -resize 2000x2000\> -quality 85 -strip "web/${base}.jpg"
  magick "$img" -resize 2000x2000\> -quality 85 "web/${base}.webp"
done
```

### Legacy to Modern

```bash
# Convert old formats to modern codecs
for video in legacy/*.avi; do
  base=$(basename "$video" .avi)
  ffmpeg -i "$video" \
    -c:v libx264 -crf 23 -preset slow \
    -c:a aac -b:a 128k \
    "modern/${base}.mp4"
done
```

### Multi-Format Publishing

```bash
# Create multiple formats for compatibility
input="source.mp4"

# Modern browsers
ffmpeg -i "$input" -c:v libx264 -crf 23 -c:a aac output.mp4
ffmpeg -i "$input" -c:v libvpx-vp9 -crf 30 -c:a libopus output.webm

# Images
ffmpeg -ss 5 -i "$input" -vframes 1 poster.jpg
magick poster.jpg -quality 80 poster.webp
```

## Troubleshooting

### Unsupported Format

```bash
# Check FFmpeg formats
ffmpeg -formats

# Check ImageMagick formats
magick identify -list format

# Install missing codec support
sudo apt-get install libx264-dev libx265-dev libvpx-dev
```

### Compatibility Issues

```bash
# Force compatible encoding
ffmpeg -i input.mp4 \
  -c:v libx264 -profile:v high -level 4.0 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  output.mp4
```

### Quality Loss

```bash
# Avoid multiple conversions
# Bad: source -> edit -> web -> social
# Good: source -> final (single conversion)

# Use lossless intermediate
ffmpeg -i source.mp4 -c:v ffv1 intermediate.mkv
# Edit intermediate
ffmpeg -i intermediate.mkv -c:v libx264 final.mp4
```
