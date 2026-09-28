# Tailwind Utilities (continued)

## Colors

### Text Colors

```html
<p class="text-black">Black</p>
<p class="text-white">White</p>
<p class="text-gray-500">Gray 500</p>
<p class="text-red-600">Red 600</p>
<p class="text-blue-500">Blue 500</p>
<p class="text-green-600">Green 600</p>
```

### Background Colors

```html
<div class="bg-white">White</div>
<div class="bg-gray-100">Gray 100</div>
<div class="bg-blue-500">Blue 500</div>
<div class="bg-red-600">Red 600</div>
```

### Color Scale

Each color has 11 shades (50-950):
- `50`: Lightest
- `100-400`: Light variations
- `500`: Base color
- `600-800`: Dark variations
- `950`: Darkest

### Opacity Modifiers

```html
<div class="bg-black/75">75% opacity</div>
<div class="text-blue-500/30">30% opacity</div>
<div class="bg-purple-500/[0.87]">87% opacity</div>
```

### Gradients

```html
<div class="bg-gradient-to-r from-blue-500 to-purple-600">
  Left to right gradient
</div>
<div class="bg-gradient-to-br from-pink-500 via-red-500 to-yellow-500">
  With via color
</div>
```

Directions: `to-t | to-tr | to-r | to-br | to-b | to-bl | to-l | to-tl`

## Borders

### Border Width

```html
<div class="border">1px all sides</div>
<div class="border-2">2px all sides</div>
<div class="border-t">Top only</div>
<div class="border-r-4">Right 4px</div>
<div class="border-b-2">Bottom 2px</div>
<div class="border-l">Left only</div>
<div class="border-0">No border</div>
```

### Border Color

```html
<div class="border border-gray-300">Gray</div>
<div class="border-2 border-blue-500">Blue</div>
<div class="border border-red-600/50">Red with opacity</div>
```

### Border Radius

```html
<div class="rounded">0.25rem</div>
<div class="rounded-md">0.375rem</div>
<div class="rounded-lg">0.5rem</div>
<div class="rounded-xl">0.75rem</div>
<div class="rounded-2xl">1rem</div>
<div class="rounded-full">9999px</div>

<!-- Individual corners -->
<div class="rounded-t-lg">Top corners</div>
<div class="rounded-br-xl">Bottom right</div>
```

### Border Style

```html
<div class="border border-solid">Solid</div>
<div class="border-2 border-dashed">Dashed</div>
<div class="border border-dotted">Dotted</div>
```

## Shadows

```html
<div class="shadow-sm">Small</div>
<div class="shadow">Default</div>
<div class="shadow-md">Medium</div>
<div class="shadow-lg">Large</div>
<div class="shadow-xl">Extra large</div>
<div class="shadow-2xl">2XL</div>
<div class="shadow-none">No shadow</div>
```

### Colored Shadows

```html
<div class="shadow-lg shadow-blue-500/50">Blue shadow</div>
```

## Width & Height

### Width

```html
<div class="w-full">100%</div>
<div class="w-1/2">50%</div>
<div class="w-1/3">33.333%</div>
<div class="w-64">16rem</div>
<div class="w-[500px]">500px</div>
<div class="w-screen">100vw</div>

<!-- Min/Max width -->
<div class="min-w-0">min-width: 0</div>
<div class="max-w-md">max-width: 28rem</div>
<div class="max-w-screen-xl">max-width: 1280px</div>
```

### Height

```html
<div class="h-full">100%</div>
<div class="h-screen">100vh</div>
<div class="h-64">16rem</div>
<div class="h-[500px]">500px</div>

<!-- Min/Max height -->
<div class="min-h-screen">min-height: 100vh</div>
<div class="max-h-96">max-height: 24rem</div>
```

## Arbitrary Values

Use square brackets for custom values:

```html
<!-- Spacing -->
<div class="p-[17px]">Custom padding</div>
<div class="top-[117px]">Custom position</div>

<!-- Colors -->
<div class="bg-[#bada55]">Hex color</div>
<div class="text-[rgb(123,45,67)]">RGB</div>

<!-- Sizes -->
<div class="w-[500px]">Custom width</div>
<div class="text-[22px]">Custom font size</div>

<!-- CSS variables -->
<div class="bg-[var(--brand-color)]">CSS var</div>

<!-- Complex values -->
<div class="grid-cols-[1fr_500px_2fr]">Custom grid</div>
```

## Aspect Ratio

```html
<div class="aspect-square">1:1</div>
<div class="aspect-video">16:9</div>
<div class="aspect-[4/3]">4:3</div>
```

## Overflow

```html
<div class="overflow-auto">Auto scroll</div>
<div class="overflow-hidden">Hidden</div>
<div class="overflow-scroll">Always scroll</div>
<div class="overflow-x-auto">Horizontal scroll</div>
<div class="overflow-y-hidden">No vertical scroll</div>
```

## Opacity

```html
<div class="opacity-0">0%</div>
<div class="opacity-50">50%</div>
<div class="opacity-75">75%</div>
<div class="opacity-100">100%</div>
```

## Cursor

```html
<div class="cursor-pointer">Pointer</div>
<div class="cursor-wait">Wait</div>
<div class="cursor-not-allowed">Not allowed</div>
<div class="cursor-default">Default</div>
```

## User Select

```html
<div class="select-none">No select</div>
<div class="select-text">Text selectable</div>
<div class="select-all">Select all</div>
```
