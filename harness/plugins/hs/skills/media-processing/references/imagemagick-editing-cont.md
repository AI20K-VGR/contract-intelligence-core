# ImageMagick Image Editing (continued 2/3)

## Adjustments

### Brightness & Contrast

```bash
# Increase brightness
magick input.jpg -brightness-contrast 10x0 output.jpg

# Increase contrast
magick input.jpg -brightness-contrast 0x20 output.jpg

# Both
magick input.jpg -brightness-contrast 10x20 output.jpg

# Negative values to decrease
magick input.jpg -brightness-contrast -10x-10 output.jpg
```

### Color Adjustments

```bash
# Adjust saturation (HSL modulation)
# Format: brightness,saturation,hue
magick input.jpg -modulate 100,150,100 output.jpg

# Adjust hue
magick input.jpg -modulate 100,100,120 output.jpg

# Combined adjustments
magick input.jpg -modulate 105,120,100 output.jpg

# Adjust specific color channels
magick input.jpg -channel Red -evaluate multiply 1.2 output.jpg
```

### Auto Corrections

```bash
# Auto level (normalize contrast)
magick input.jpg -auto-level output.jpg

# Auto gamma correction
magick input.jpg -auto-gamma output.jpg

# Normalize (stretch histogram)
magick input.jpg -normalize output.jpg

# Enhance (digital enhancement)
magick input.jpg -enhance output.jpg

# Equalize (histogram equalization)
magick input.jpg -equalize output.jpg
```

## Transformations

### Rotation

```bash
# Rotate 90° clockwise
magick input.jpg -rotate 90 output.jpg

# Rotate 180°
magick input.jpg -rotate 180 output.jpg

# Rotate counter-clockwise
magick input.jpg -rotate -90 output.jpg

# Rotate with background
magick input.jpg -background white -rotate 45 output.jpg

# Auto-orient based on EXIF
magick input.jpg -auto-orient output.jpg
```

### Flip & Mirror

```bash
# Flip vertically
magick input.jpg -flip output.jpg

# Flip horizontally (mirror)
magick input.jpg -flop output.jpg

# Both
magick input.jpg -flip -flop output.jpg
```

## Borders & Frames

### Simple Borders

```bash
# Add 10px black border
magick input.jpg -border 10x10 output.jpg

# Colored border
magick input.jpg -bordercolor red -border 10x10 output.jpg

# Different width/height
magick input.jpg -bordercolor blue -border 20x10 output.jpg
```

### Advanced Frames

```bash
# Raised frame
magick input.jpg -mattecolor gray -frame 10x10+5+5 output.jpg

# Shadow effect
magick input.jpg \
  \( +clone -background black -shadow 80x3+5+5 \) \
  +swap -background white -layers merge +repage \
  output.jpg

# Rounded corners
magick input.jpg \
  \( +clone -threshold -1 -draw "fill black polygon 0,0 0,15 15,0 fill white circle 15,15 15,0" \
  \( +clone -flip \) -compose multiply -composite \
  \( +clone -flop \) -compose multiply -composite \
  \) -alpha off -compose copy_opacity -composite \
  output.png
```

## Text & Annotations

### Basic Text

```bash
# Simple text overlay
magick input.jpg -pointsize 30 -fill white -annotate +10+30 "Hello" output.jpg

# Positioned text
magick input.jpg -gravity south -pointsize 20 -fill white \
  -annotate +0+10 "Copyright 2025" output.jpg

# Text with background
magick input.jpg -gravity center -pointsize 40 -fill white \
  -undercolor black -annotate +0+0 "Watermark" output.jpg
```

### Advanced Text

```bash
# Semi-transparent watermark
magick input.jpg \
  \( -background none -fill "rgba(255,255,255,0.5)" \
  -pointsize 50 label:"DRAFT" \) \
  -gravity center -compose over -composite \
  output.jpg

# Text with stroke
magick input.jpg -gravity center \
  -stroke black -strokewidth 2 -fill white \
  -pointsize 60 -annotate +0+0 "Title" \
  output.jpg

# Custom font
magick input.jpg -font Arial-Bold -pointsize 40 \
  -gravity center -fill white -annotate +0+0 "Text" \
  output.jpg
```

## Image Composition

### Overlay Images

```bash
# Basic overlay (top-left)
magick input.jpg overlay.png -composite output.jpg

# Position with gravity
magick input.jpg watermark.png -gravity southeast -composite output.jpg

# Position with offset
magick input.jpg watermark.png -gravity southeast \
  -geometry +10+10 -composite output.jpg

# Center overlay
magick input.jpg logo.png -gravity center -composite output.jpg
```

### Composite Modes

```bash
# Over (default)
magick input.jpg overlay.png -compose over -composite output.jpg

# Multiply
magick input.jpg texture.png -compose multiply -composite output.jpg

# Screen
magick input.jpg light.png -compose screen -composite output.jpg

# Overlay blend mode
magick input.jpg pattern.png -compose overlay -composite output.jpg
```

### Side-by-Side

```bash
# Horizontal append
magick image1.jpg image2.jpg +append output.jpg

# Vertical append
magick image1.jpg image2.jpg -append output.jpg

# With spacing
magick image1.jpg image2.jpg -gravity center \
  -background white -splice 10x0 +append output.jpg
```

## Transparency

### Create Transparency

```bash
# Make color transparent
magick input.jpg -transparent white output.png

# Make similar colors transparent (with fuzz)
magick input.jpg -fuzz 10% -transparent white output.png

# Alpha channel operations
magick input.png -alpha set -channel A -evaluate multiply 0.5 +channel output.png
```

### Remove Transparency

```bash
# Flatten with white background
magick input.png -background white -flatten output.jpg

# Flatten with custom color
magick input.png -background "#ff0000" -flatten output.jpg
```

## Advanced Techniques

### Vignette Effect

```bash
# Default vignette
magick input.jpg -vignette 0x20 output.jpg

# Custom vignette
magick input.jpg -background black -vignette 0x25+10+10 output.jpg
```

### Depth of Field Blur

```bash
# Radial blur from center
magick input.jpg \
  \( +clone -blur 0x8 \) \
  \( +clone -fill white -colorize 100 \
  -fill black -draw "circle %[fx:w/2],%[fx:h/2] %[fx:w/2],%[fx:h/4]" \
  -blur 0x20 \) \
  -composite output.jpg
```

### HDR Effect

```bash
magick input.jpg \
  \( +clone -colorspace gray \) \
  \( -clone 0 -auto-level -modulate 100,150,100 \) \
  -delete 0 -compose overlay -composite \
  output.jpg
```

### Tilt-Shift Effect

```bash
magick input.jpg \
  \( +clone -sparse-color Barycentric '0,%[fx:h*0.3] gray0 0,%[fx:h*0.5] white 0,%[fx:h*0.7] gray0' \) \
  \( +clone -blur 0x20 \) \
  -compose blend -define compose:args=100 -composite \
  output.jpg
```


---
Continued in [imagemagick-editing-cont2.md](imagemagick-editing-cont2.md).
