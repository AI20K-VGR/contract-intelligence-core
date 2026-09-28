# Tailwind CSS Responsive Design

Mobile-first breakpoints, responsive utilities, and adaptive layouts.

## Mobile-First Approach

Mobile-first: base styles apply to all screen sizes; breakpoint prefixes override at larger sizes.

```html
<!-- Base: 1 column (mobile)
     sm: 2 columns (tablet)
     lg: 4 columns (desktop) -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
  <div>Item 4</div>
</div>
```

## Breakpoint System

**Default breakpoints:**

| Prefix | Min Width | CSS Media Query |
|--------|-----------|-----------------|
| `sm:` | 640px | `@media (min-width: 640px)` |
| `md:` | 768px | `@media (min-width: 768px)` |
| `lg:` | 1024px | `@media (min-width: 1024px)` |
| `xl:` | 1280px | `@media (min-width: 1280px)` |
| `2xl:` | 1536px | `@media (min-width: 1536px)` |

## Responsive Patterns

### Layout Changes

```html
<!-- Vertical on mobile, horizontal on desktop -->
<div class="flex flex-col lg:flex-row gap-4">
  <div>Left</div>
  <div>Right</div>
</div>

<!-- 1 column -> 2 columns -> 3 columns -->
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
</div>
```

### Visibility

```html
<!-- Hide on mobile, show on desktop -->
<div class="hidden lg:block">
  Desktop only content
</div>

<!-- Show on mobile, hide on desktop -->
<div class="block lg:hidden">
  Mobile only content
</div>

<!-- Different content per breakpoint -->
<div class="lg:hidden">Mobile menu</div>
<div class="hidden lg:flex">Desktop navigation</div>
```

### Typography

```html
<!-- Responsive text sizes -->
<h1 class="text-2xl md:text-4xl lg:text-6xl font-bold">
  Heading scales with screen size
</h1>

<p class="text-sm md:text-base lg:text-lg">
  Body text scales appropriately
</p>
```

### Spacing

```html
<!-- Responsive padding -->
<div class="p-4 md:p-6 lg:p-8">
  More padding on larger screens
</div>

<!-- Responsive gap -->
<div class="flex gap-2 md:gap-4 lg:gap-6">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

### Width

```html
<!-- Full width on mobile, constrained on desktop -->
<div class="w-full lg:w-1/2 xl:w-1/3">
  Responsive width
</div>

<!-- Responsive max-width -->
<div class="max-w-sm md:max-w-2xl lg:max-w-4xl mx-auto">
  Centered with responsive max width
</div>
```

## Common Responsive Layouts

### Sidebar Layout

```html
<div class="flex flex-col lg:flex-row min-h-screen">
  <!-- Sidebar: Full width on mobile, fixed on desktop -->
  <aside class="w-full lg:w-64 bg-gray-100 p-4">
    Sidebar
  </aside>

  <!-- Main content -->
  <main class="flex-1 p-4 md:p-8">
    Main content
  </main>
</div>
```

### Card Grid

```html
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
  <div class="bg-white rounded-lg shadow p-6">Card 1</div>
  <div class="bg-white rounded-lg shadow p-6">Card 2</div>
  <div class="bg-white rounded-lg shadow p-6">Card 3</div>
  <div class="bg-white rounded-lg shadow p-6">Card 4</div>
</div>
```

### Hero Section

```html
<section class="py-12 md:py-20 lg:py-32">
  <div class="container mx-auto px-4">
    <div class="flex flex-col lg:flex-row items-center gap-8 lg:gap-12">
      <div class="flex-1 text-center lg:text-left">
        <h1 class="text-4xl md:text-5xl lg:text-6xl font-bold mb-4">
          Hero Title
        </h1>
        <p class="text-lg md:text-xl mb-6">
          Hero description
        </p>
        <button class="px-6 py-3 md:px-8 md:py-4">
          CTA Button
        </button>
      </div>
      <div class="flex-1">
        <img src="hero.jpg" class="w-full rounded-lg" />
      </div>
    </div>
  </div>
</section>
```

### Navigation

```html
<nav class="bg-white shadow">
  <div class="container mx-auto px-4">
    <div class="flex items-center justify-between h-16">
      <div class="text-xl font-bold">Logo</div>

      <!-- Desktop navigation -->
      <div class="hidden md:flex gap-6">
        <a href="#">Home</a>
        <a href="#">About</a>
        <a href="#">Services</a>
        <a href="#">Contact</a>
      </div>

      <!-- Mobile menu button -->
      <button class="md:hidden">
        <svg class="w-6 h-6">...</svg>
      </button>
    </div>
  </div>
</nav>
```

> Continued in `references/tailwind-responsive-cont.md`.
