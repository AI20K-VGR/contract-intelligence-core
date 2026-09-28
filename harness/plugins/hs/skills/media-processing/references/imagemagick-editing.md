# ImageMagick Image Editing

Format conversion, resizing, effects, transformations, composition.

## Format Conversion

### Basic Conversion
Convert between image formats.

```bash
# PNG to JPEG
magick input.png output.jpg

# JPEG to WebP
magick input.jpg output.webp

# Multiple outputs simultaneously
magick input.png output.jpg output.webp output.gif

# Convert with quality setting
magick input.png -quality 85 output.jpg
```

### Quality Settings

**JPEG Quality (0-100):**
- 95-100: Archival, minimal compression
- 85-94: High quality, web publishing
- 75-84: Medium quality, web optimized
- 60-74: Lower quality, smaller files
- Below 60: Visible artifacts

```bash
# High quality
magick input.png -quality 95 output.jpg

# Web optimized (recommended)
magick input.png -quality 85 -strip output.jpg

# Smaller file size
magick input.png -quality 75 -sampling-factor 4:2:0 -strip output.jpg
```

**PNG Quality (0-9 = compression level):**
```bash
# Maximum compression (slower)
magick input.jpg -quality 95 output.png

# Faster compression
magick input.jpg -quality 75 output.png
```

**WebP Quality:**
```bash
# Lossy with quality
magick input.jpg -quality 80 output.webp

# Lossless
magick input.png -define webp:lossless=true output.webp
```

### Progressive & Optimization

```bash
# Progressive JPEG (better web loading)
magick input.png -quality 85 -interlace Plane output.jpg

# Strip metadata (reduce file size)
magick input.jpg -strip output.jpg

# Combined optimization
magick input.png -quality 85 -interlace Plane -strip output.jpg
```

## Resizing Operations

### Basic Resize
Maintain aspect ratio.

```bash
# Fit within 800×600
magick input.jpg -resize 800x600 output.jpg

# Resize to specific width (auto height)
magick input.jpg -resize 800x output.jpg

# Resize to specific height (auto width)
magick input.jpg -resize x600 output.jpg

# Scale by percentage
magick input.jpg -resize 50% output.jpg
```

### Advanced Resize

```bash
# Resize only if larger (shrink only)
magick input.jpg -resize 800x600\> output.jpg

# Resize only if smaller (enlarge only)
magick input.jpg -resize 800x600\< output.jpg

# Force exact dimensions (ignore aspect ratio)
magick input.jpg -resize 800x600! output.jpg

# Fill dimensions (may crop)
magick input.jpg -resize 800x600^ output.jpg

# Minimum dimensions
magick input.jpg -resize 800x600^ output.jpg
```

### Resize Algorithms

```bash
# High quality (Lanczos)
magick input.jpg -filter Lanczos -resize 50% output.jpg

# Fast resize (Box)
magick input.jpg -filter Box -resize 50% output.jpg

# Mitchel filter (good balance)
magick input.jpg -filter Mitchell -resize 50% output.jpg
```

**Filter comparison:**
- `Lanczos` - Highest quality, slower
- `Mitchell` - Good quality, fast
- `Catrom` - Sharp, good for downscaling
- `Box` - Fastest, acceptable quality
- `Cubic` - Smooth results

## Cropping

### Basic Crop
Extract region from image.

```bash
# Crop width×height+x+y
magick input.jpg -crop 400x400+100+100 output.jpg

# Remove virtual canvas after crop
magick input.jpg -crop 400x400+100+100 +repage output.jpg

# Crop from center
magick input.jpg -gravity center -crop 400x400+0+0 output.jpg

# Crop to aspect ratio
magick input.jpg -gravity center -crop 16:9 +repage output.jpg
```

### Smart Crop
Content-aware cropping.

```bash
# Trim transparent/same-color borders
magick input.png -trim +repage output.png

# Trim with fuzz tolerance
magick input.jpg -fuzz 10% -trim +repage output.jpg
```

### Thumbnail Generation
Create square thumbnails from any aspect ratio.

```bash
# Resize and crop to square
magick input.jpg -resize 200x200^ -gravity center -extent 200x200 thumb.jpg

# Alternative method
magick input.jpg -thumbnail 200x200^ -gravity center -crop 200x200+0+0 +repage thumb.jpg

# With background (no crop)
magick input.jpg -resize 200x200 -background white -gravity center -extent 200x200 thumb.jpg
```

## Effects & Filters

### Blur Effects

```bash
# Standard blur (radius 0 = auto)
magick input.jpg -blur 0x8 output.jpg

# Gaussian blur (radius×sigma)
magick input.jpg -gaussian-blur 5x3 output.jpg

# Motion blur (angle)
magick input.jpg -motion-blur 0x20+45 output.jpg

# Radial blur
magick input.jpg -radial-blur 10 output.jpg
```

### Sharpen

```bash
# Basic sharpen
magick input.jpg -sharpen 0x1 output.jpg

# Stronger sharpen
magick input.jpg -sharpen 0x3 output.jpg

# Unsharp mask (advanced)
magick input.jpg -unsharp 0x1 output.jpg
```

### Color Effects

```bash
# Grayscale
magick input.jpg -colorspace Gray output.jpg

# Sepia tone
magick input.jpg -sepia-tone 80% output.jpg

# Negate (invert colors)
magick input.jpg -negate output.jpg

# Posterize (reduce colors)
magick input.jpg -posterize 8 output.jpg

# Solarize
magick input.jpg -solarize 50% output.jpg
```

### Artistic Effects

```bash
# Edge detection
magick input.jpg -edge 3 output.jpg

# Emboss
magick input.jpg -emboss 2 output.jpg

# Oil painting
magick input.jpg -paint 4 output.jpg

# Charcoal drawing
magick input.jpg -charcoal 2 output.jpg

# Sketch
magick input.jpg -sketch 0x20+120 output.jpg

# Swirl
magick input.jpg -swirl 90 output.jpg
```


---
Continued in [imagemagick-editing-cont.md](imagemagick-editing-cont.md).
