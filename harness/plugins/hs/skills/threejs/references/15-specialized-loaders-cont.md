# Specialized Loaders (continued 2/2)

## RGBE/HDR Loader

HDR environment maps:

```javascript
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

const loader = new RGBELoader();
loader.load('env.hdr', (texture) => {
  texture.mapping = THREE.EquirectangularReflectionMapping;

  scene.background = texture;
  scene.environment = texture;

  // Use with PMREM generator for better quality
  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  const envMap = pmremGenerator.fromEquirectangular(texture).texture;
  scene.environment = envMap;
  texture.dispose();
  pmremGenerator.dispose();
});
```

## Basis/KTX2 Texture Loader

GPU-optimized texture compression:

```javascript
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';

const loader = new KTX2Loader();
loader.setTranscoderPath('basis/');
loader.detectSupport(renderer);

loader.load('texture.ktx2', (texture) => {
  material.map = texture;
  material.needsUpdate = true;
});
```

## Common Patterns

```javascript
// Load with progress
loader.load(
  'file.ext',
  (result) => { /* success */ },
  (xhr) => {
    const percent = (xhr.loaded / xhr.total * 100);
    console.log(`${percent}% loaded`);
  },
  (error) => { /* error */ }
);

// Center imported model
const box = new THREE.Box3().setFromObject(model);
const center = box.getCenter(new THREE.Vector3());
model.position.sub(center);

// Scale to fit
const size = box.getSize(new THREE.Vector3());
const maxDim = Math.max(size.x, size.y, size.z);
const scale = 10 / maxDim;
model.scale.setScalar(scale);
```
