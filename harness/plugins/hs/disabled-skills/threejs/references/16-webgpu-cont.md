# WebGPU Rendering (continued 2/2)

## Browser Support

As of 2025:
- ✅ Chrome 113+
- ✅ Edge 113+
- ✅ Safari 18+ (macOS/iOS)
- ❌ Firefox (in development)

Check support: `WebGPU.isAvailable()`

## Best Practices

- Use compute shaders for particle systems, physics
- Leverage storage buffers for large datasets
- Async compile before rendering
- Use Node materials instead of custom GLSL
- Test on both WebGL and WebGPU
- Provide WebGL fallback for unsupported browsers
