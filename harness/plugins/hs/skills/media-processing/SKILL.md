---
name: hs:media-processing
injectable: true
description: Process media with FFmpeg (video/audio), ImageMagick (images), RMBG (AI background removal). Use for encoding, format conversion, filters, thumbnails, batch processing, HLS/DASH streaming.
argument-hint: "[input-file] [operation]"
allowed-tools: [Bash, Read, Write, Edit, Glob]
metadata:
  compliance-tier: workflow
---

# Media Processing Skill

Process video/audio/images via FFmpeg, ImageMagick, RMBG CLI.

**MUST:** Invoke "/hs:project-organization" skill to organize the outputs.

## Tool Selection

| Task | Tool | Reason |
|------|------|--------|
| Video encoding/conversion | FFmpeg | Native codec support, streaming |
| Audio extraction/conversion | FFmpeg | Direct stream manipulation |
| Image resize/effects | ImageMagick | Optimized for still images |
| Background removal | RMBG | AI-powered, local processing |
| Batch images | ImageMagick | mogrify for in-place edits |
| Video thumbnails | FFmpeg | Frame extraction built-in |
| GIF creation | FFmpeg/ImageMagick | FFmpeg for video, ImageMagick for images |

## Installation

```bash
# macOS
brew install ffmpeg imagemagick
npm install -g rmbg-cli

# Ubuntu/Debian
sudo apt-get install ffmpeg imagemagick
npm install -g rmbg-cli

# Verify
ffmpeg -version && magick -version && rmbg --version
```

## Essential Commands

```bash
# Video: Convert/re-encode
ffmpeg -i input.mkv -c copy output.mp4
ffmpeg -i input.avi -c:v libx264 -crf 22 -c:a aac output.mp4

# Video: Extract audio
ffmpeg -i video.mp4 -vn -c:a copy audio.m4a

# Image: Convert/resize
magick input.png output.jpg
magick input.jpg -resize 800x600 output.jpg

# Image: Batch resize
mogrify -resize 800x -quality 85 *.jpg

# Background removal
rmbg input.jpg                          # Basic (modnet)
rmbg input.jpg -m briaai -o output.png  # High quality
rmbg input.jpg -m u2netp -o output.png  # Fast
```

## Key Parameters

**FFmpeg:**
- `-c:v libx264` - H.264 codec
- `-crf 22` - Quality (0-51, lower=better)
- `-preset slow` - Speed/compression balance
- `-c:a aac` - Audio codec

**ImageMagick:**
- `800x600` - Fit within (maintains aspect)
- `800x600^` - Fill (may crop)
- `-quality 85` - JPEG quality
- `-strip` - Remove metadata

**RMBG:**
- `-m briaai` - High quality model
- `-m u2netp` - Fast model
- `-r 4096` - Max resolution

## References

Detailed guides in `references/`:
- `references/ffmpeg-encoding.md` - Codecs, quality, hardware acceleration
- `references/ffmpeg-streaming.md` - HLS/DASH, live streaming
- `references/ffmpeg-filters.md` - Filters, complex filtergraphs
- `references/imagemagick-editing.md` - Effects, transformations
- `references/imagemagick-batch.md` - Batch processing, parallel ops
- `references/rmbg-background-removal.md` - AI models, CLI usage
- `references/common-workflows.md` - Video optimization, responsive images, GIF creation
- `references/troubleshooting.md` - Error fixes, performance tips
- `references/format-compatibility.md` - Format support, codec recommendations

## Related skills

- `hs:ai-multimodal`: AI vision / transcription / OCR counterpart when media work needs model analysis.
