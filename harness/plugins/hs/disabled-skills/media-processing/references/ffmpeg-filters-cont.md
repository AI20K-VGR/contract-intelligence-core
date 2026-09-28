# FFmpeg Filters & Effects (continued 2/2)

## Audio Filters

### Volume
Adjust audio level.

```bash
# Increase by 10dB
ffmpeg -i input.mp4 -af volume=10dB output.mp4

# Decrease to 50%
ffmpeg -i input.mp4 -af volume=0.5 output.mp4

# Double volume
ffmpeg -i input.mp4 -af volume=2.0 output.mp4
```

### Normalize
Balance audio levels.

```bash
# Loudness normalization (EBU R128)
ffmpeg -i input.mp4 -af loudnorm output.mp4

# With specific target
ffmpeg -i input.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11 output.mp4

# Two-pass normalization (better quality)
# Pass 1: analyze
ffmpeg -i input.mp4 -af loudnorm=print_format=json -f null -

# Pass 2: normalize with measured values
ffmpeg -i input.mp4 -af loudnorm=measured_I=-23:measured_LRA=7:measured_TP=-2:measured_thresh=-33 output.mp4
```

### Equalizer
Adjust frequency bands.

```bash
# Bass boost
ffmpeg -i input.mp4 -af equalizer=f=100:width_type=h:width=200:g=10 output.mp4

# Treble boost
ffmpeg -i input.mp4 -af equalizer=f=10000:width_type=h:width=2000:g=5 output.mp4

# Multiple bands
ffmpeg -i input.mp4 -af "equalizer=f=100:g=5,equalizer=f=1000:g=-3" output.mp4
```

### Compressor
Dynamic range compression.

```bash
# Basic compression
ffmpeg -i input.mp4 -af acompressor output.mp4

# Custom settings
ffmpeg -i input.mp4 -af acompressor=threshold=-20dB:ratio=4:attack=200:release=1000 output.mp4
```

### Noise Reduction
Remove background noise.

```bash
# High-pass filter (remove low frequency noise)
ffmpeg -i input.mp4 -af highpass=f=200 output.mp4

# Low-pass filter (remove high frequency noise)
ffmpeg -i input.mp4 -af lowpass=f=3000 output.mp4

# Band-pass filter
ffmpeg -i input.mp4 -af "highpass=f=200,lowpass=f=3000" output.mp4
```

### Fade Audio
Smooth audio transitions.

```bash
# Fade in (2 seconds)
ffmpeg -i input.mp4 -af afade=t=in:st=0:d=2 output.mp4

# Fade out (last 3 seconds)
ffmpeg -i input.mp4 -af afade=t=out:st=27:d=3 output.mp4

# Both
ffmpeg -i input.mp4 -af "afade=t=in:st=0:d=2,afade=t=out:st=27:d=3" output.mp4
```

### Audio Mixing
Combine multiple audio tracks.

```bash
# Mix two audio files
ffmpeg -i audio1.mp3 -i audio2.mp3 \
  -filter_complex amix=inputs=2:duration=longest output.mp3

# Mix with volume adjustment
ffmpeg -i audio1.mp3 -i audio2.mp3 \
  -filter_complex "[0:a]volume=0.8[a1];[1:a]volume=0.5[a2];[a1][a2]amix=inputs=2" \
  output.mp3
```

## Complex Filtergraphs

### Multiple Outputs
Create multiple versions simultaneously.

```bash
# Generate 3 resolutions at once
ffmpeg -i input.mp4 \
  -filter_complex "[0:v]split=3[v1][v2][v3]; \
    [v1]scale=1920:1080[out1]; \
    [v2]scale=1280:720[out2]; \
    [v3]scale=640:360[out3]" \
  -map "[out1]" -c:v libx264 -crf 22 output_1080p.mp4 \
  -map "[out2]" -c:v libx264 -crf 23 output_720p.mp4 \
  -map "[out3]" -c:v libx264 -crf 24 output_360p.mp4 \
  -map 0:a -c:a copy
```

### Picture-in-Picture
Overlay small video on main video.

```bash
ffmpeg -i main.mp4 -i small.mp4 \
  -filter_complex "[1:v]scale=320:180[pip]; \
    [0:v][pip]overlay=W-w-10:H-h-10" \
  output.mp4
```

### Side-by-Side Comparison
Compare two videos.

```bash
# Horizontal
ffmpeg -i left.mp4 -i right.mp4 \
  -filter_complex "[0:v][1:v]hstack=inputs=2" \
  output.mp4

# Vertical
ffmpeg -i top.mp4 -i bottom.mp4 \
  -filter_complex "[0:v][1:v]vstack=inputs=2" \
  output.mp4
```

### Crossfade Transition
Smooth transition between videos.

```bash
ffmpeg -i video1.mp4 -i video2.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=fade:duration=2:offset=8" \
  output.mp4
```

**Transition types:** fade, wipeleft, wiperight, wipeup, wipedown, slideleft, slideright, slideup, slidedown, circlecrop, rectcrop, distance, fadeblack, fadewhite, radial, smoothleft, smoothright, smoothup, smoothdown

### Color Correction Pipeline
Professional color grading.

```bash
ffmpeg -i input.mp4 \
  -filter_complex "[0:v]eq=contrast=1.1:brightness=0.05:saturation=1.2[v1]; \
    [v1]curves=vintage[v2]; \
    [v2]vignette[v3]; \
    [v3]unsharp=5:5:1.0[out]" \
  -map "[out]" -c:v libx264 -crf 18 output.mp4
```

## Filter Performance

### GPU Acceleration
Use hardware filters when available.

```bash
# NVIDIA CUDA scale
ffmpeg -hwaccel cuda -i input.mp4 \
  -vf scale_cuda=1280:720 \
  -c:v h264_nvenc output.mp4

# Multiple GPU filters
ffmpeg -hwaccel cuda -i input.mp4 \
  -vf "scale_cuda=1280:720,hwdownload,format=nv12" \
  -c:v h264_nvenc output.mp4
```

### Optimize Filter Order
More efficient filter chains.

```bash
# Bad: scale after complex operations
ffmpeg -i input.mp4 -vf "hqdn3d,unsharp=5:5:1.0,scale=1280:720" output.mp4

# Good: scale first (fewer pixels to process)
ffmpeg -i input.mp4 -vf "scale=1280:720,hqdn3d,unsharp=5:5:1.0" output.mp4
```

## Common Filter Recipes

### YouTube Optimized
```bash
ffmpeg -i input.mp4 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -preset slow -crf 18 -c:a aac -b:a 192k \
  output.mp4
```

### Instagram Portrait
```bash
ffmpeg -i input.mp4 \
  -vf "scale=1080:1350:force_original_aspect_ratio=decrease,pad=1080:1350:(ow-iw)/2:(oh-ih)/2:color=white" \
  -c:v libx264 -preset fast -crf 23 -c:a aac \
  output.mp4
```

### Vintage Film Look
```bash
ffmpeg -i input.mp4 \
  -vf "curves=vintage,vignette=angle=PI/4,eq=saturation=0.8,noise=alls=10:allf=t" \
  -c:v libx264 -crf 20 output.mp4
```

### Clean & Enhance
```bash
ffmpeg -i input.mp4 \
  -vf "hqdn3d=4:3:6:4.5,unsharp=5:5:1.0,eq=contrast=1.05:saturation=1.1" \
  -c:v libx264 -crf 20 output.mp4
```
