# Physics & VR/XR (continued 2/2)

## Common VR Patterns

```javascript
// Detect if in VR
if (renderer.xr.isPresenting) {
  // In VR mode
}

// Get VR camera (for raycasting)
const vrCamera = renderer.xr.getCamera(camera);

// Different behavior for VR vs desktop
renderer.setAnimationLoop(() => {
  if (renderer.xr.isPresenting) {
    // VR rendering logic
  } else {
    // Desktop rendering logic
  }
  renderer.render(scene, camera);
});
```
