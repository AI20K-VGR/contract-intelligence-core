# ImageMagick Image Editing (continued 3/3)

## Color Management

### Color Profiles

```bash
# Strip color profile
magick input.jpg -strip output.jpg

# Assign color profile
magick input.jpg -profile sRGB.icc output.jpg

# Convert between profiles
magick input.jpg -profile AdobeRGB.icc -profile sRGB.icc output.jpg
```

### Color Space Conversion

```bash
# Convert to sRGB
magick input.jpg -colorspace sRGB output.jpg

# Convert to CMYK (print)
magick input.jpg -colorspace CMYK output.tif

# Convert to LAB
magick input.jpg -colorspace LAB output.jpg
```

## Performance Optimization

### Memory Management

```bash
# Limit memory usage
magick -limit memory 2GB -limit map 4GB input.jpg -resize 50% output.jpg

# Set thread count
magick -limit thread 4 input.jpg -resize 50% output.jpg

# Streaming for large files
magick -define stream:buffer-size=0 huge.jpg -resize 50% output.jpg
```

### Quality vs Size

```bash
# Maximum quality (large file)
magick input.jpg -quality 95 output.jpg

# Balanced (recommended)
magick input.jpg -quality 85 -strip output.jpg

# Smaller file (acceptable quality)
magick input.jpg -quality 70 -sampling-factor 4:2:0 -strip output.jpg

# Progressive JPEG
magick input.jpg -quality 85 -interlace Plane -strip output.jpg
```

## Common Recipes

### Avatar/Profile Picture

```bash
# Square thumbnail
magick input.jpg -resize 200x200^ -gravity center -extent 200x200 avatar.jpg

# Circular avatar (PNG)
magick input.jpg -resize 200x200^ -gravity center -extent 200x200 \
  \( +clone -threshold -1 -negate -fill white -draw "circle 100,100 100,0" \) \
  -alpha off -compose copy_opacity -composite avatar.png
```

### Responsive Images

```bash
# Generate multiple sizes
for size in 320 640 1024 1920; do
  magick input.jpg -resize ${size}x -quality 85 -strip "output-${size}w.jpg"
done
```

### Photo Enhancement

```bash
# Auto-enhance workflow
magick input.jpg \
  -auto-level \
  -unsharp 0x1 \
  -brightness-contrast 5x10 \
  -modulate 100,110,100 \
  -quality 90 -strip \
  output.jpg
```
