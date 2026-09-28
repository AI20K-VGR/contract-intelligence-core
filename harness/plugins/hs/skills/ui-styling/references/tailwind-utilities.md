# Tailwind CSS Utility Reference

Core utility classes for layout, spacing, typography, colors, borders, and shadows.

## Layout Utilities

### Display

```html
<div class="block">Block</div>
<div class="inline-block">Inline Block</div>
<div class="inline">Inline</div>
<div class="flex">Flexbox</div>
<div class="inline-flex">Inline Flex</div>
<div class="grid">Grid</div>
<div class="inline-grid">Inline Grid</div>
<div class="hidden">Hidden</div>
```

### Flexbox

**Container:**
```html
<div class="flex flex-row">Row (default)</div>
<div class="flex flex-col">Column</div>
<div class="flex flex-row-reverse">Reverse row</div>
<div class="flex flex-col-reverse">Reverse column</div>
```

**Justify (main axis):**
```html
<div class="flex justify-start">Start</div>
<div class="flex justify-center">Center</div>
<div class="flex justify-end">End</div>
<div class="flex justify-between">Space between</div>
<div class="flex justify-around">Space around</div>
<div class="flex justify-evenly">Space evenly</div>
```

**Align (cross axis):**
```html
<div class="flex items-start">Start</div>
<div class="flex items-center">Center</div>
<div class="flex items-end">End</div>
<div class="flex items-baseline">Baseline</div>
<div class="flex items-stretch">Stretch</div>
```

**Gap:**
```html
<div class="flex gap-4">All sides</div>
<div class="flex gap-x-6 gap-y-2">X and Y</div>
```

**Wrap:**
```html
<div class="flex flex-wrap">Wrap</div>
<div class="flex flex-nowrap">No wrap</div>
```

### Grid

**Columns:**
```html
<div class="grid grid-cols-1">1 column</div>
<div class="grid grid-cols-2">2 columns</div>
<div class="grid grid-cols-3">3 columns</div>
<div class="grid grid-cols-4">4 columns</div>
<div class="grid grid-cols-12">12 columns</div>
<div class="grid grid-cols-[1fr_500px_2fr]">Custom</div>
```

**Rows:**
```html
<div class="grid grid-rows-3">3 rows</div>
<div class="grid grid-rows-[auto_1fr_auto]">Custom</div>
```

**Span:**
```html
<div class="col-span-2">Span 2 columns</div>
<div class="row-span-3">Span 3 rows</div>
```

**Gap:**
```html
<div class="grid gap-4">All sides</div>
<div class="grid gap-x-8 gap-y-4">X and Y</div>
```

### Positioning

```html
<div class="static">Static (default)</div>
<div class="relative">Relative</div>
<div class="absolute">Absolute</div>
<div class="fixed">Fixed</div>
<div class="sticky">Sticky</div>

<!-- Position values -->
<div class="absolute top-0 right-0">Top right</div>
<div class="absolute inset-0">All sides 0</div>
<div class="absolute inset-x-4">Left/right 4</div>
<div class="absolute inset-y-8">Top/bottom 8</div>
```

### Z-Index

```html
<div class="z-0">z-index: 0</div>
<div class="z-10">z-index: 10</div>
<div class="z-20">z-index: 20</div>
<div class="z-50">z-index: 50</div>
```

## Spacing Utilities

### Padding

```html
<div class="p-4">All sides</div>
<div class="px-6">Left and right</div>
<div class="py-3">Top and bottom</div>
<div class="pt-8">Top</div>
<div class="pr-4">Right</div>
<div class="pb-2">Bottom</div>
<div class="pl-6">Left</div>
```

### Margin

```html
<div class="m-4">All sides</div>
<div class="mx-auto">Center horizontally</div>
<div class="my-6">Top and bottom</div>
<div class="mt-8">Top</div>
<div class="-mt-4">Negative top</div>
<div class="ml-auto">Push to right</div>
```

### Space Between

```html
<div class="space-x-4">Horizontal spacing</div>
<div class="space-y-6">Vertical spacing</div>
```

### Spacing Scale

- `0`: 0px
- `px`: 1px
- `0.5`: 0.125rem (2px)
- `1`: 0.25rem (4px)
- `2`: 0.5rem (8px)
- `3`: 0.75rem (12px)
- `4`: 1rem (16px)
- `6`: 1.5rem (24px)
- `8`: 2rem (32px)
- `12`: 3rem (48px)
- `16`: 4rem (64px)
- `24`: 6rem (96px)

## Typography

### Font Size

```html
<p class="text-xs">Extra small (12px)</p>
<p class="text-sm">Small (14px)</p>
<p class="text-base">Base (16px)</p>
<p class="text-lg">Large (18px)</p>
<p class="text-xl">XL (20px)</p>
<p class="text-2xl">2XL (24px)</p>
<p class="text-3xl">3XL (30px)</p>
<p class="text-4xl">4XL (36px)</p>
<p class="text-5xl">5XL (48px)</p>
```

### Font Weight

```html
<p class="font-thin">Thin (100)</p>
<p class="font-light">Light (300)</p>
<p class="font-normal">Normal (400)</p>
<p class="font-medium">Medium (500)</p>
<p class="font-semibold">Semibold (600)</p>
<p class="font-bold">Bold (700)</p>
<p class="font-black">Black (900)</p>
```

### Text Alignment

```html
<p class="text-left">Left</p>
<p class="text-center">Center</p>
<p class="text-right">Right</p>
<p class="text-justify">Justify</p>
```

### Line Height

```html
<p class="leading-none">1</p>
<p class="leading-tight">1.25</p>
<p class="leading-normal">1.5</p>
<p class="leading-relaxed">1.75</p>
<p class="leading-loose">2</p>
```

### Combined Font Utilities

```html
<h1 class="text-4xl/tight font-bold">
  Font size 4xl with tight line height
</h1>
```

### Text Transform

```html
<p class="uppercase">UPPERCASE</p>
<p class="lowercase">lowercase</p>
<p class="capitalize">Capitalize</p>
<p class="normal-case">Normal</p>
```

### Text Decoration

```html
<p class="underline">Underline</p>
<p class="line-through">Line through</p>
<p class="no-underline">No underline</p>
```

### Text Overflow

```html
<p class="truncate">Truncate with ellipsis...</p>
<p class="line-clamp-3">Clamp to 3 lines...</p>
<p class="text-ellipsis overflow-hidden">Ellipsis</p>
```

> Continued in `references/tailwind-utilities-cont.md`.
