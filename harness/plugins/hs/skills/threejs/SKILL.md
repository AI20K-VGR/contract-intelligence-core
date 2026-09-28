---
name: hs:threejs
injectable: true
description: "Build 3D web experiences with Three.js. Use for WebGL/WebGPU scenes, GLTF models, animations, physics, VR/XR. Supports 556 searchable examples."
argument-hint: "[3D scene or feature]"
allowed-tools: [Bash, Read, Write, Edit]
metadata:
  compliance-tier: knowledge
---

# Three.js Development

High-performance 3D web apps via Three.js. 556 searchable examples: 13 categories, 60 API classes, 20 use-case templates.

## When to Use

- Building 3D scenes, games, or visualizations
- Loading 3D models (GLTF, FBX, OBJ)
- Implementing animations, physics, or VR/XR
- Creating particle effects or custom shaders
- Optimizing rendering performance

## Search Examples & API

Use the search CLI to find relevant examples and API references:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/threejs/scripts/search.py "<query>" [--domain <domain>] [-n <max_results>]
```

### Search Domains

| Domain | Use For | Example Query |
|--------|---------|---------------|
| `examples` | Find code examples | `"particle effects gpu"` |
| `api` | Class/method reference | `"PerspectiveCamera"` |
| `use-cases` | Project recommendations | `"product configurator"` |
| `categories` | Browse categories | `"webgpu"` |

### Quick Examples

```bash
# Find particle/compute examples
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/threejs/scripts/search.py "particle compute webgpu"

# Search API for camera classes
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/threejs/scripts/search.py "camera" --domain api

# Get examples for a use case
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/threejs/scripts/search.py "product configurator" --use-case

# Filter by category
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/threejs/scripts/search.py --category webgpu -n 10

# Filter by complexity
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/threejs/scripts/search.py --complexity high -n 5
```

## Example Categories

| Category | Count | Description |
|----------|-------|-------------|
| `webgl` | 216 | Standard WebGL rendering |
| `webgpu (wip)` | 190 | Modern WebGPU + compute shaders |
| `webgl / advanced` | 48 | Low-level GPU, custom shaders |
| `webgl / postprocessing` | 27 | Bloom, SSAO, SSR, DOF |
| `webxr` | 26 | VR/AR experiences |
| `physics` | 13 | Physics simulation |

## Common Use Cases

| Use Case | Recommended | Complexity |
|----------|-------------|------------|
| Product Configurator | GLTF, PBR, EnvMaps | Medium |
| Game Development | Animation, Physics, Controls | High |
| Data Visualization | BufferGeometry, Points | Medium |
| 360 Panorama | Equirectangular, WebXR | Low |
| Architectural Viz | GLTF, HDR, CSM Shadows | High |

## Quick Start

See `references/01-getting-started.md` for minimal scene setup (Scene/Camera/Renderer/Lights/animation loop); `references/02-loaders.md` for GLTF model loading.

## Progressive Reference Files

### Level 1: Fundamentals
- `references/00-fundamentals.md` - Core concepts, scene graph
- `references/01-getting-started.md` - Setup, basic rendering

### Level 2: Common Tasks
- `references/02-loaders.md` - GLTF, FBX, OBJ loaders
- `references/03-textures.md` - Texture types, mapping
- `references/04-cameras.md` - Camera types, controls
- `references/05-lights.md` - Light types, shadows
- `references/06-animations.md` - AnimationMixer, clips
- `references/07-math.md` - Vector/Matrix/Quaternion/Euler utilities
- `references/11-materials.md` - PBR, standard materials
- `references/18-geometry.md` - BufferGeometry, primitives

### Level 3: Interactive
- `references/08-interaction.md` - Raycasting, picking
- `references/09-postprocessing.md` - Bloom, SSAO, SSR
- `references/10-controls.md` - OrbitControls, etc.

### Level 4: Advanced
- `references/12-performance.md` - Instancing, LOD, batching
- `references/11-materials-advanced.md` - Transmission, clearcoat, physical materials
- `references/13-node-materials.md` - TSL shader graphs
- `references/15-specialized-loaders.md` - Draco, KTX2, USDZ and other loaders
- `references/17-shader.md` - Custom GLSL shaders

### Level 5: Specialized
- `references/14-physics-vr.md` - Physics, WebXR
- `references/16-webgpu.md` - WebGPU, compute shaders

## External Resources

- Docs: https://threejs.org/docs/
- Examples: https://threejs.org/examples/
- Editor: https://threejs.org/editor/
- Discord: https://discord.gg/56GBJwAnUS

## Related skills

- `hs:frontend-design`: design-side counterpart for immersive/3D interface work.
