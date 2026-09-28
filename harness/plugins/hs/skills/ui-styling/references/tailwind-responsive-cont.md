# Tailwind Responsive (continued)

## Max-Width Queries

Apply styles only below certain breakpoint using `max-*:` prefix:

```html
<!-- Only on mobile and tablet (below 1024px) -->
<div class="max-lg:text-center">
  Centered on mobile/tablet, left-aligned on desktop
</div>

<!-- Only on mobile (below 640px) -->
<div class="max-sm:hidden">
  Hidden only on mobile
</div>
```

Available: `max-sm:` `max-md:` `max-lg:` `max-xl:` `max-2xl:`

## Range Queries

Apply styles between breakpoints:

```html
<!-- Only on tablets (between md and lg) -->
<div class="md:block lg:hidden">
  Visible only on tablets
</div>

<!-- Between sm and xl -->
<div class="sm:grid-cols-2 xl:grid-cols-4">
  2 columns on tablet, 4 on extra large
</div>
```

## Container Queries

Style elements based on parent container width:

```html
<div class="@container">
  <div class="@md:grid-cols-2 @lg:grid-cols-3">
    Responds to parent width, not viewport
  </div>
</div>
```

Container query breakpoints: `@sm:` `@md:` `@lg:` `@xl:` `@2xl:`

## Custom Breakpoints

Define custom breakpoints in theme:

```css
@theme {
  --breakpoint-3xl: 120rem;  /* 1920px */
  --breakpoint-tablet: 48rem;  /* 768px */
}
```

```html
<div class="tablet:grid-cols-2 3xl:grid-cols-6">
  Uses custom breakpoints
</div>
```

## Responsive State Variants

Combine responsive with hover/focus:

```html
<!-- Hover effect only on desktop -->
<button class="lg:hover:scale-105">
  Scale on hover (desktop only)
</button>

<!-- Different hover colors per breakpoint -->
<a class="hover:text-blue-600 lg:hover:text-purple-600">
  Link
</a>
```

## Best Practices

### 1. Mobile-First Design

Start with mobile styles, add complexity at larger breakpoints:

```html
<!-- Good: Mobile first -->
<div class="text-base md:text-lg lg:text-xl">

<!-- Avoid: Desktop first -->
<div class="text-xl lg:text-base">
```

### 2. Consistent Breakpoint Usage

Use same breakpoints across related elements:

```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6 lg:gap-8">
  Spacing scales with layout
</div>
```

### 3. Test at Breakpoint Boundaries

Test exact breakpoint widths (640/768/1024px, etc.) for edge cases.

### 4. Use Container for Content Width

```html
<div class="container mx-auto px-4 sm:px-6 lg:px-8">
  <div class="max-w-7xl">
    Content with consistent max width
  </div>
</div>
```

### 5. Progressive Enhancement

Ensure core functionality works on mobile, enhance for larger screens:

```html
<!-- Core layout works on mobile -->
<div class="p-4">
  <!-- Enhanced spacing on desktop -->
  <div class="lg:p-8">
    Content
  </div>
</div>
```

### 6. Avoid Too Many Breakpoints

Use 2-3 breakpoints per element for maintainability:

```html
<!-- Good: 2 breakpoints -->
<div class="grid-cols-1 md:grid-cols-2 lg:grid-cols-4">

<!-- Avoid: Too many breakpoints -->
<div class="grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
```

## Common Responsive Utilities

### Responsive Display

```html
<div class="block md:flex lg:grid">
  Changes display type per breakpoint
</div>
```

### Responsive Position

```html
<div class="relative lg:absolute">
  Positioned differently per breakpoint
</div>
```

### Responsive Order

```html
<div class="flex flex-col">
  <div class="order-2 lg:order-1">First on desktop</div>
  <div class="order-1 lg:order-2">First on mobile</div>
</div>
```

### Responsive Overflow

```html
<div class="overflow-auto lg:overflow-visible">
  Scrollable on mobile, expanded on desktop
</div>
```

## Testing Checklist

- [ ] Test at 320px (small mobile)
- [ ] Test at 640px (mobile breakpoint)
- [ ] Test at 768px (tablet breakpoint)
- [ ] Test at 1024px (desktop breakpoint)
- [ ] Test at 1280px (large desktop breakpoint)
- [ ] Test landscape orientation
- [ ] Verify touch targets (min 44x44px)
- [ ] Check text readability at all sizes
- [ ] Verify navigation works on mobile
- [ ] Test with browser zoom
