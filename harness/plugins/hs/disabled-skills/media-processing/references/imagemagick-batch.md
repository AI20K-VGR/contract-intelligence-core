# ImageMagick Batch Processing

Batch operations, mogrify command, parallel processing, automation.

## Mogrify Command

### Basic Mogrify
Modify files in-place (overwrites originals).

```bash
# Resize all JPEGs
mogrify -resize 800x600 *.jpg

# Convert format (creates new files)
mogrify -format png *.jpg

# Apply effect to all images
mogrify -quality 85 -strip *.jpg
```

**Warning:** mogrify modifies files in-place. Always backup originals or use `-path` to output to different directory.

### Output to Different Directory
Preserve originals.

```bash
# Create output directory first
mkdir output

# Process to output directory
mogrify -path ./output -resize 800x600 *.jpg

# With format conversion
mogrify -path ./optimized -format webp -quality 80 *.png
```

## Common Batch Operations

### Resize All Images

```bash
# Resize to width 800
mogrify -resize 800x *.jpg

# Resize to height 600
mogrify -resize x600 *.jpg

# Fit within 800×600
mogrify -resize 800x600 *.jpg

# Resize to exact dimensions
mogrify -resize 800x600! *.jpg

# Only shrink, never enlarge
mogrify -resize 800x600\> *.jpg
```

### Format Conversion

```bash
# PNG to JPEG
mogrify -path ./jpg -format jpg -quality 85 *.png

# JPEG to WebP
mogrify -path ./webp -format webp -quality 80 *.jpg

# Any format to PNG
mogrify -path ./png -format png *.{jpg,gif,bmp}
```

### Optimize Images

```bash
# Strip metadata from all JPEGs
mogrify -strip *.jpg

# Optimize JPEGs for web
mogrify -quality 85 -strip -interlace Plane *.jpg

# Compress PNGs
mogrify -quality 95 *.png

# Combined optimization
mogrify -quality 85 -strip -interlace Plane -sampling-factor 4:2:0 *.jpg
```

### Apply Effects

```bash
# Add watermark to all images
mogrify -gravity southeast -draw "image over 10,10 0,0 'watermark.png'" *.jpg

# Convert all to grayscale
mogrify -colorspace Gray *.jpg

# Apply sepia tone
mogrify -sepia-tone 80% *.jpg

# Sharpen all images
mogrify -sharpen 0x1 *.jpg
```

### Thumbnail Generation

```bash
# Create square thumbnails
mogrify -path ./thumbnails -resize 200x200^ -gravity center -extent 200x200 *.jpg

# Create thumbnails with max dimension
mogrify -path ./thumbs -thumbnail 300x300 *.jpg

# Thumbnails with quality control
mogrify -path ./thumbs -thumbnail 200x200 -quality 80 -strip *.jpg
```

## Shell Loops

### Basic For Loop
More control than mogrify.

```bash
# Resize with custom naming
for img in *.jpg; do
  magick "$img" -resize 800x600 "resized_$img"
done

# Process to subdirectory
mkdir processed
for img in *.jpg; do
  magick "$img" -resize 1920x1080 "processed/$img"
done
```

### Multiple Operations

```bash
# Complex processing pipeline
for img in *.jpg; do
  magick "$img" \
    -resize 1920x1080^ \
    -gravity center \
    -crop 1920x1080+0+0 +repage \
    -unsharp 0x1 \
    -quality 85 -strip \
    "processed_$img"
done
```

### Format Conversion with Rename

```bash
# Convert PNG to JPEG with new names
for img in *.png; do
  magick "$img" -quality 90 "${img%.png}.jpg"
done

# Add prefix during conversion
for img in *.jpg; do
  magick "$img" -resize 800x "web_${img}"
done
```

### Conditional Processing

```bash
# Only process large images
for img in *.jpg; do
  width=$(identify -format "%w" "$img")
  if [ $width -gt 2000 ]; then
    magick "$img" -resize 2000x "resized_$img"
  fi
done

# Skip existing output files
for img in *.jpg; do
  output="output_$img"
  if [ ! -f "$output" ]; then
    magick "$img" -resize 800x "$output"
  fi
done
```

## Parallel Processing

### GNU Parallel
Process multiple images simultaneously.

```bash
# Install GNU Parallel
# Ubuntu/Debian: sudo apt-get install parallel
# macOS: brew install parallel

# Basic parallel resize
parallel magick {} -resize 800x600 resized_{} ::: *.jpg

# Parallel with function
resize_image() {
  magick "$1" -resize 1920x1080 -quality 85 "processed_$1"
}
export -f resize_image
parallel resize_image ::: *.jpg

# Limit concurrent jobs
parallel -j 4 magick {} -resize 800x {} ::: *.jpg

# Progress indicator
parallel --progress magick {} -resize 800x {} ::: *.jpg
```

### Xargs Parallel

```bash
# Using xargs for parallel processing
ls *.jpg | xargs -I {} -P 4 magick {} -resize 800x processed_{}

# With find
find . -name "*.jpg" -print0 | \
  xargs -0 -I {} -P 4 magick {} -resize 800x {}
```


---
Continued in [imagemagick-batch-cont.md](imagemagick-batch-cont.md).
