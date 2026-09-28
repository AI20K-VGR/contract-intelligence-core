# ImageMagick Batch Processing (continued 3/3)

## Automation Scripts

### Complete Bash Script

```bash
#!/bin/bash

# Configuration
INPUT_DIR="./input"
OUTPUT_DIR="./output"
QUALITY=85
MAX_WIDTH=1920
THUMBNAIL_SIZE=300

# Create output directories
mkdir -p "$OUTPUT_DIR"/{full,thumbnails}

# Process images
echo "Processing images..."
for img in "$INPUT_DIR"/*.{jpg,jpeg,png}; do
  [ -f "$img" ] || continue

  filename=$(basename "$img")
  base="${filename%.*}"

  # Full size
  magick "$img" \
    -resize ${MAX_WIDTH}x\> \
    -quality $QUALITY \
    -strip \
    "$OUTPUT_DIR/full/${base}.jpg"

  # Thumbnail
  magick "$img" \
    -thumbnail ${THUMBNAIL_SIZE}x${THUMBNAIL_SIZE} \
    -quality 80 \
    -strip \
    "$OUTPUT_DIR/thumbnails/${base}_thumb.jpg"

  echo "✓ $filename"
done

echo "Done!"
```

### Python Batch Script

```python
#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

INPUT_DIR = Path("./input")
OUTPUT_DIR = Path("./output")
SIZES = [320, 640, 1024, 1920]

# Create output directories
for size in SIZES:
    (OUTPUT_DIR / f"{size}w").mkdir(parents=True, exist_ok=True)

# Process images
for img in INPUT_DIR.glob("*.jpg"):
    for size in SIZES:
        output = OUTPUT_DIR / f"{size}w" / img.name
        subprocess.run([
            "magick", str(img),
            "-resize", f"{size}x",
            "-quality", "85",
            "-strip",
            str(output)
        ])
        print(f"✓ {img.name} -> {size}w")
```

## Common Batch Recipes

### Social Media Sizes

```bash
# Generate social media image sizes
for img in *.jpg; do
  base="${img%.jpg}"

  # Instagram square (1080×1080)
  magick "$img" -resize 1080x1080^ -gravity center -extent 1080x1080 "${base}_ig_square.jpg"

  # Instagram portrait (1080×1350)
  magick "$img" -resize 1080x1350^ -gravity center -extent 1080x1350 "${base}_ig_portrait.jpg"

  # Facebook post (1200×630)
  magick "$img" -resize 1200x630^ -gravity center -extent 1200x630 "${base}_fb_post.jpg"

  # Twitter post (1200×675)
  magick "$img" -resize 1200x675^ -gravity center -extent 1200x675 "${base}_tw_post.jpg"
done
```

### Email Newsletter Images

```bash
# Optimize images for email
mogrify -path ./email \
  -resize 600x\> \
  -quality 75 \
  -strip \
  -interlace Plane \
  *.jpg
```

### Backup and Archive

```bash
# Create web versions and keep originals
mkdir -p {originals,web}

# Move originals
mv *.jpg originals/

# Create optimized copies
for img in originals/*.jpg; do
  base=$(basename "$img")
  magick "$img" -resize 2000x2000\> -quality 85 -strip "web/$base"
done
```
