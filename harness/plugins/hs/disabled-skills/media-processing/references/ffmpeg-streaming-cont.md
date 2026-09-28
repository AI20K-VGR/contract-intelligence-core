# FFmpeg Streaming & Live Video (continued 2/2)

## Streaming Parameters

### Important RTMP Parameters

**Real-time reading:**
- `-re` - Read input at native frame rate

**Low latency:**
- `-tune zerolatency` - Optimize for minimal latency
- `-preset ultrafast` or `veryfast` - Fast encoding

**Keyframes:**
- `-g 50` - Keyframe interval (GOP size)
- Recommended: 2 seconds (fps * 2)

**Rate control:**
- `-maxrate` - Maximum bitrate (e.g., 3000k)
- `-bufsize` - Buffer size (typically 2x maxrate)

**Compatibility:**
- `-pix_fmt yuv420p` - Compatible pixel format

### Bitrate Recommendations

**1080p 60fps:**
- 4500-6000 kbps video
- 160 kbps audio

**1080p 30fps:**
- 3000-4500 kbps video
- 128 kbps audio

**720p 60fps:**
- 2500-4000 kbps video
- 128 kbps audio

**720p 30fps:**
- 1500-2500 kbps video
- 128 kbps audio

**480p:**
- 500-1000 kbps video
- 128 kbps audio

## UDP/RTP Streaming

### UDP Stream
Simple network streaming.

```bash
# Sender
ffmpeg -re -i input.mp4 -c copy -f mpegts udp://192.168.1.100:1234

# Receiver
ffplay udp://192.168.1.100:1234
```

### RTP Stream
Real-Time Protocol for low latency.

```bash
# Audio only
ffmpeg -re -i audio.mp3 -c:a libopus -f rtp rtp://192.168.1.100:5004

# Video + audio
ffmpeg -re -i input.mp4 \
  -c:v libx264 -preset ultrafast \
  -c:a aac -f rtp rtp://192.168.1.100:5004
```

### Multicast Stream
Stream to multiple receivers.

```bash
# Sender (multicast address)
ffmpeg -re -i input.mp4 -c copy -f mpegts udp://239.255.0.1:1234

# Receiver
ffplay udp://239.255.0.1:1234
```

## Advanced Streaming

### Hardware-Accelerated Streaming
Use GPU for faster encoding.

```bash
# NVIDIA NVENC
ffmpeg -re -i input.mp4 \
  -c:v h264_nvenc -preset fast -maxrate 3000k -bufsize 6000k \
  -c:a aac -b:a 128k \
  -f flv rtmp://live.twitch.tv/app/STREAM_KEY

# Intel QSV
ffmpeg -re -hwaccel qsv -i input.mp4 \
  -c:v h264_qsv -preset fast -maxrate 3000k -bufsize 6000k \
  -c:a aac -b:a 128k \
  -f flv rtmp://live.twitch.tv/app/STREAM_KEY
```

### Stream with Overlay
Add graphics during stream.

```bash
ffmpeg -re -i input.mp4 -i logo.png \
  -filter_complex "[0:v][1:v]overlay=10:10" \
  -c:v libx264 -preset veryfast -maxrate 3000k \
  -c:a copy \
  -f flv rtmp://live.twitch.tv/app/STREAM_KEY
```

### Loop Stream
Continuously loop video for 24/7 stream.

```bash
ffmpeg -stream_loop -1 -re -i input.mp4 \
  -c:v libx264 -preset veryfast -maxrate 2500k \
  -c:a aac -b:a 128k \
  -f flv rtmp://live.twitch.tv/app/STREAM_KEY
```

## Troubleshooting

### Buffering Issues
```bash
# Reduce buffer size
ffmpeg -re -i input.mp4 -maxrate 2000k -bufsize 2000k -c:v libx264 -f flv rtmp://...

# Use faster preset
ffmpeg -re -i input.mp4 -preset ultrafast -c:v libx264 -f flv rtmp://...
```

### Audio/Video Desync
```bash
# Force constant frame rate
ffmpeg -re -i input.mp4 -r 30 -c:v libx264 -f flv rtmp://...

# Use -vsync 1
ffmpeg -re -i input.mp4 -vsync 1 -c:v libx264 -f flv rtmp://...
```

### Connection Drops
```bash
# Increase timeout
ffmpeg -timeout 5000000 -re -i input.mp4 -c:v libx264 -f flv rtmp://...

# Reconnect on failure (use wrapper script)
while true; do
  ffmpeg -re -i input.mp4 -c:v libx264 -f flv rtmp://...
  sleep 5
done
```
