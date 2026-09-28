# ImageMagick Batch Processing (continued 2/3)

## Advanced Batch Patterns

### Recursive Processing

```bash
# Process all JPEGs in subdirectories
find . -name "*.jpg" -exec magick {} -resize 800x {} \;

# With output directory structure
find . -name "*.jpg" -type f | while read img; do
  outdir="output/$(dirname "$img")"
  mkdir -p "$outdir"
  magick "$img" -resize 800x "$outdir/$(basename "$img")"
done
```

### Batch with Different Sizes

```bash
# Generate multiple sizes
for size in 320 640 1024 1920; do
  mkdir -p "output/${size}w"
  for img in *.jpg; do
    magick "$img" -resize ${size}x -quality 85 "output/${size}w/$img"
  done
done

# Parallel version
for size in 320 640 1024 1920; do
  mkdir -p "output/${size}w"
  parallel magick {} -resize ${size}x -quality 85 "output/${size}w/{}" ::: *.jpg
done
```

### Responsive Image Set

```bash
# Create responsive image set with srcset
mkdir -p responsive
for img in *.jpg; do
  base="${img%.jpg}"
  for width in 320 640 1024 1920; do
    magick "$img" -resize ${width}x -quality 85 \
      "responsive/${base}-${width}w.jpg"
  done
done
```

### Watermark Batch

```bash
# Add watermark to all images
for img in *.jpg; do
  magick "$img" watermark.png \
    -gravity southeast -geometry +10+10 \
    -composite "watermarked_$img"
done

# Different watermark positions for portrait vs landscape
for img in *.jpg; do
  width=$(identify -format "%w" "$img")
  height=$(identify -format "%h" "$img")

  if [ $width -gt $height ]; then
    # Landscape
    magick "$img" watermark.png -gravity southeast -composite "marked_$img"
  else
    # Portrait
    magick "$img" watermark.png -gravity south -composite "marked_$img"
  fi
done
```

## Error Handling

### Check Before Processing

```bash
# Verify image before processing
for img in *.jpg; do
  if identify "$img" > /dev/null 2>&1; then
    magick "$img" -resize 800x "processed_$img"
  else
    echo "Skipping corrupt image: $img"
  fi
done
```

### Log Processing

```bash
# Log successful and failed operations
log_file="batch_process.log"
error_log="errors.log"

for img in *.jpg; do
  if magick "$img" -resize 800x "output/$img" 2>> "$error_log"; then
    echo "$(date): Processed $img" >> "$log_file"
  else
    echo "$(date): Failed $img" >> "$error_log"
  fi
done
```

### Dry Run Mode

```bash
# Test without modifying files
dry_run=true

for img in *.jpg; do
  cmd="magick $img -resize 800x processed_$img"
  if [ "$dry_run" = true ]; then
    echo "Would run: $cmd"
  else
    eval $cmd
  fi
done
```

## Optimization Workflows

### Web Publishing Pipeline

```bash
# Complete web optimization workflow
mkdir -p web/{original,optimized,thumbnails}

# Copy originals
cp *.jpg web/original/

# Create optimized versions
mogrify -path web/optimized \
  -resize 1920x1080\> \
  -quality 85 \
  -strip \
  -interlace Plane \
  web/original/*.jpg

# Create thumbnails
mogrify -path web/thumbnails \
  -thumbnail 300x300 \
  -quality 80 \
  -strip \
  web/original/*.jpg
```

### Archive to Web Conversion

```bash
# Convert high-res archives to web formats
for img in archives/*.jpg; do
  base=$(basename "$img" .jpg)

  # Full size web version
  magick "$img" -resize 2048x2048\> -quality 90 -strip "web/${base}.jpg"

  # Thumbnail
  magick "$img" -thumbnail 400x400 -quality 85 "web/${base}_thumb.jpg"

  # WebP version
  magick "$img" -resize 2048x2048\> -quality 85 "web/${base}.webp"
done
```

### Print to Web Workflow

```bash
# Convert print-ready images to web
for img in print/*.tif; do
  base=$(basename "$img" .tif)

  # Convert colorspace and optimize
  magick "$img" \
    -colorspace sRGB \
    -resize 2000x2000\> \
    -quality 90 \
    -strip \
    -interlace Plane \
    "web/${base}.jpg"
done
```

## Batch Reporting

### Generate Report

```bash
# Create processing report
report="batch_report.txt"
echo "Batch Processing Report - $(date)" > "$report"
echo "================================" >> "$report"

total=0
success=0
failed=0

for img in *.jpg; do
  ((total++))
  if magick "$img" -resize 800x "output/$img" 2>/dev/null; then
    ((success++))
    echo "✓ $img" >> "$report"
  else
    ((failed++))
    echo "✗ $img" >> "$report"
  fi
done

echo "" >> "$report"
echo "Total: $total, Success: $success, Failed: $failed" >> "$report"
```

### Image Inventory

```bash
# Create inventory of images
inventory="image_inventory.csv"
echo "Filename,Width,Height,Format,Size,ColorSpace" > "$inventory"

for img in *.{jpg,png,gif}; do
  [ -f "$img" ] || continue
  info=$(identify -format "%f,%w,%h,%m,%b,%[colorspace]" "$img")
  echo "$info" >> "$inventory"
done
```

## Performance Tips

### Optimize Loop Performance

```bash
# Bad: Launch mogrify for each file
for img in *.jpg; do
  mogrify -resize 800x "$img"
done

# Good: Process all files in one mogrify call
mogrify -resize 800x *.jpg

# Best: Use parallel processing for complex operations
parallel magick {} -resize 800x -quality 85 processed_{} ::: *.jpg
```

### Memory Management

```bash
# Limit memory for batch processing
for img in *.jpg; do
  magick -limit memory 2GB -limit map 4GB \
    "$img" -resize 50% "output/$img"
done
```

### Progress Tracking

```bash
# Show progress for long batch operations
total=$(ls *.jpg | wc -l)
current=0

for img in *.jpg; do
  ((current++))
  echo "Processing $current/$total: $img"
  magick "$img" -resize 800x "output/$img"
done
```


---
Continued in [imagemagick-batch-cont2.md](imagemagick-batch-cont2.md).
