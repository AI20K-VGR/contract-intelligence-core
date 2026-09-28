# 3D Design Workflow

Create immersive interactive 3D designs with Three.js.

## Prerequisites
- Activate `hs:ui-ux` skill first
- Activate `hs:threejs` skill for 3D and WebGL expertise
- Have `hs:ai-multimodal` skill ready for asset generation

## Initial Research
Run `hs:ui-ux` searches:
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-ux/scripts/search.py "<product-type>" --domain product
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-ux/scripts/search.py "immersive 3d" --domain style
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/ui-ux/scripts/search.py "animation" --domain ux
```

## Workflow Steps

### 1. Create Implementation Plan
Use `hs:ui-ux-designer` + `hs:researcher` subagents:
- Create plan directory (use `## Naming` pattern)
- Write `plan.md` (<80 lines overview)
- Add `phases/phase-N-name.md` files
- Keep research reports under 150 lines

### 2. Implement with Three.js
Use `hs:ui-ux-designer` subagent to build:
- Three.js scene setup
- Custom GLSL shaders
- GPU particle systems
- Cinematic camera controls
- Post-processing effects
- Interactive elements

### 3. Generate 3D Assets
Use `hs:ai-multimodal` skill for:
- Textures and materials
- Skyboxes and environment maps
- Particle sprites
- Video backgrounds

Use `hs:media-processing` skill for:
- Texture optimization for WebGL
- Normal/height map generation
- Sprite sheet creation
- Background removal
- Asset optimization

### 4. Verify & Report
- Test across devices
- Optimize for 60fps
- Report to user
- Request approval

### 5. Document
Update `./docs/design-guidelines.md` with:
- 3D design patterns
- Shader libraries
- Reusable components

## Technical Requirements

### Three.js Implementation
- Proper scene optimization
- Efficient draw calls
- LOD (Level of Detail) where needed
- Responsive canvas behavior
- Memory management

### Shader Development
- Custom vertex shaders
- Custom fragment shaders
- Uniform management
- Performance optimization

### Particle Systems
- GPU-accelerated rendering
- Efficient buffer geometry
- Point sprite optimization

### Post-Processing
- Render pipeline setup
- Effect composition
- Performance budgeting

## Implementation Stack
- Three.js - 3D rendering
- GLSL - Custom shaders
- HTML/CSS/JS - UI integration
- WebGL - GPU graphics

## Performance Targets
- 60fps minimum
- < 100ms initial load
- Responsive to viewport
- Mobile-friendly fallbacks

## Related
- `animejs.md` - UI animation patterns
- `technical-optimization.md` - Performance tips
- `asset-generation.md` - Asset creation
