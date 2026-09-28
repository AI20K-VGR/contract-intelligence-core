# Animejs (continued)

## 📝 Code Formatting Guidelines

### ALWAYS Use Single-Line Format for Simple Animations
**This is mandatory for readability** - Use for animations with ≤4 properties:
```javascript
// ✅ GOOD - Clean, readable, one line
animate('.element', { x: 250, duration: 1, ease: 'outQuad' });
animate('.box', { opacity: 0.5, scale: 0.8, duration: 0.3 });

// ❌ BAD - Unnecessary multi-line for simple tweens
animate('.element', {
  x: 250,
  duration: 1,
  ease: 'outQuad'
});
```

### Multi-Line Format (Only for Complex Animations)
Use for animations with >4 properties or callbacks:
```javascript
// Complex animation with callbacks - multi-line is appropriate
animate('.element', {
  x: { to: [0, 100, 50], duration: 2 },
  y: { to: [0, -50, 0], duration: 2 },
  scale: [0, 1.2, 1],
  ease: 'outElastic(1, 0.5)',
  onComplete: () => console.log('Done!')
});
```

## 🎨 Common Animation Patterns

### Hover Animation (single line per animation)
```javascript
element.addEventListener('mouseenter', () => animate(element, { scale: 1.1, duration: 0.3, ease: 'outQuad' }));
element.addEventListener('mouseleave', () => animate(element, { scale: 1, duration: 0.3, ease: 'outQuad' }));
```

### Sequential Timeline
```javascript
const tl = createTimeline({ defaults: { duration: 0.5 } });
tl.add('.step1', { x: 100 })
  .add('.step2', { y: 100 })
  .add('.step3', { scale: 2 });
```

### Scroll-triggered Animation
```javascript
import { createScrollObserver } from 'animejs';

createScrollObserver({
  target: '.scroll-element',
  root: document.querySelector('.scroll-container'),
  play: () => animate('.element', { x: 250, duration: 1 }),
  visibility: 0.5
});
```

## 🔧 Advanced Features

### SVG Animations
```javascript
import { animate, svg } from 'animejs';

// Morph path (single line)
animate('#path1', { d: svg.morphTo('#path2'), duration: 1 });

// Draw SVG line
const drawable = svg.createDrawable('.svg-path');
animate(drawable, { draw: '0% 100%', duration: 2 });

// Motion path (single line for simple usage)
const motionPath = svg.createMotionPath('#motion-path');
animate('.element', { x: motionPath.translateX, y: motionPath.translateY, rotate: motionPath.rotate });
```

### Utility Functions
```javascript
import { utils } from 'animejs';

// DOM selection
const elements = utils.$('.elements');

// Get current value
const currentX = utils.get('.element', 'translateX');

// Set values immediately
utils.set('.element', { x: 100, opacity: 0.5 });

// Remove animations
utils.remove('.element');

// Math utilities
utils.random(0, 100);
utils.shuffle([1, 2, 3, 4]);
utils.lerp(0, 100, 0.5); // 50
utils.clamp(150, 0, 100); // 100
```

### TypeScript Support
```typescript
import { animate, createTimeline, JSAnimation, Timeline, AnimationParams, TimelineParams } from 'animejs';

// Single line for simple animations
const animation: JSAnimation = animate('.element', { x: 250, duration: 1 } as AnimationParams);

const timeline: Timeline = createTimeline({ defaults: { duration: 0.8 } } as TimelineParams);
```

## ⚡ Performance Tips

1. **Use transforms over position properties**
   ```javascript
   // ✅ Good - uses transform
   animate('.element', { x: 100 });
   
   // ❌ Avoid - triggers layout
   animate('.element', { left: 100 });
   ```

2. **Batch animations in timelines**
   ```javascript
   // ✅ Good - single timeline
   const tl = createTimeline();
   elements.forEach(el => tl.add(el, { x: 100 }));
   
   // ❌ Avoid - multiple animations
   elements.forEach(el => animate(el, { x: 100 }));
   ```

3. **Use will-change CSS property for complex animations**
   ```css
   .animated-element {
     will-change: transform, opacity;
   }
   ```

## 🚫 How to Identify V3 Code (DON'T USE)

If you see ANY of these patterns, it's v3 and MUST be updated:

```javascript
// All of these are V3 - NEVER USE:
anime({ ... })
anime.timeline()
anime.stagger()
anime.random()
anime.remove()
anime.get()
anime.set()
anime.running
{ targets: '...' }
{ easing: '...' }
{ value: ... }
{ direction: 'alternate' }
```

## 💡 AI Code Generation Rules

When asked to create animations with anime.js:

1. **ONLY** set `engine.timeUnit = 's'` ONCE in the app's main entry point (App.js, main.js, index.js) - NEVER in components
2. **ALWAYS** use seconds for all durations (1 = 1 second)
3. **ALWAYS** format simple animations on ONE LINE
4. **ALWAYS** start with v4 imports
5. **NEVER** use `anime()` function
6. **ALWAYS** use `animate()` for animations
7. **NEVER** include `targets` property
8. **ALWAYS** use `ease` not `easing`
9. **NEVER** use `value`, use `to` instead
10. **ALWAYS** prefix callbacks with `on`
11. **NEVER** use `direction`, use `alternate` and `reversed`
12. **ALWAYS** use `createTimeline()` for timelines
13. **PREFER** shorthand (`x`) over explicit (`translateX`)
14. **FORMAT** short animations on single line (≤4 properties)
15. **NEVER** generate v3 syntax under any circumstances

## NPM Installation
```bash
npm install animejs
```

## Version Check
```javascript
// Current version: 4.x.x
// If you see any code using anime({ targets: ... }), it's v3 and needs updating!
```