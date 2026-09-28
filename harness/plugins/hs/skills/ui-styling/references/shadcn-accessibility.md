# shadcn/ui Accessibility Patterns

ARIA patterns, keyboard navigation, screen reader support, and accessible component usage.

## Foundation: Radix UI Primitives

shadcn/ui built on Radix UI primitives - unstyled, accessible components following WAI-ARIA design patterns.

Benefits:
- Keyboard navigation built-in
- Screen reader announcements
- Focus management
- ARIA attributes automatically applied
- Tested against accessibility standards

## Keyboard Navigation

### Focus Management

**Focus visible states:**
```tsx
<Button className="focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
  Accessible Button
</Button>
```

**Skip to content:**
```tsx
<a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2">
  Skip to content
</a>

<main id="main-content">
  {/* Content */}
</main>
```

### Dialog/Modal Navigation

Dialog: Radix traps focus automatically:

```tsx
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog"

<Dialog>
  <DialogTrigger>Open</DialogTrigger>
  <DialogContent>
    {/* Focus trapped here */}
    <input />  {/* Auto-focused */}
    <Button>Action</Button>
    {/* Esc to close, Tab to navigate */}
  </DialogContent>
</Dialog>
```

Features:
- Focus trapped within dialog
- Esc key closes
- Tab cycles through focusable elements
- Focus returns to trigger on close

### Dropdown/Menu Navigation

```tsx
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

<DropdownMenu>
  <DropdownMenuTrigger>Open</DropdownMenuTrigger>
  <DropdownMenuContent>
    <DropdownMenuItem>Profile</DropdownMenuItem>
    <DropdownMenuItem>Settings</DropdownMenuItem>
    <DropdownMenuItem>Logout</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

Keyboard shortcuts:
- `Space/Enter`: Open menu
- `Arrow Up/Down`: Navigate items
- `Esc`: Close menu
- `Tab`: Close and move focus

### Command Palette Navigation

```tsx
import { Command } from "@/components/ui/command"

<Command>
  <CommandInput placeholder="Search..." />
  <CommandList>
    <CommandGroup heading="Suggestions">
      <CommandItem>Calendar</CommandItem>
      <CommandItem>Search</CommandItem>
    </CommandGroup>
  </CommandList>
</Command>
```

Features:
- Type to filter
- Arrow keys to navigate
- Enter to select
- Esc to close

## Screen Reader Support

### Semantic HTML

Use proper HTML elements:

```tsx
// Good: Semantic HTML
<button>Click me</button>
<nav><a href="/">Home</a></nav>

// Avoid: Div soup
<div onClick={handler}>Click me</div>
```

### ARIA Labels

**Label interactive elements:**
```tsx
<Button aria-label="Close dialog">
  <X className="h-4 w-4" />
</Button>

<Input aria-label="Email address" type="email" />
```

**Describe elements:**
```tsx
<Button aria-describedby="delete-description">
  Delete Account
</Button>
<p id="delete-description" className="sr-only">
  This action permanently deletes your account and cannot be undone
</p>
```

### Screen Reader Only Text

Use `sr-only` class for screen reader only content:

```tsx
<Button>
  <Trash className="h-4 w-4" />
  <span className="sr-only">Delete item</span>
</Button>

// CSS for sr-only
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

### Live Regions

Announce dynamic content:

```tsx
<div aria-live="polite" aria-atomic="true">
  {message}
</div>

// For urgent updates
<div aria-live="assertive">
  {error}
</div>
```

Toast component includes live region:
```tsx
const { toast } = useToast()

toast({
  title: "Success",
  description: "Profile updated"
})
// Announced to screen readers automatically
```

## Form Accessibility

### Labels and Descriptions

**Always label inputs:**
```tsx
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"

<div>
  <Label htmlFor="email">Email</Label>
  <Input id="email" type="email" />
</div>
```

**Add descriptions:**
```tsx
import { FormDescription, FormMessage } from "@/components/ui/form"

<FormItem>
  <FormLabel>Username</FormLabel>
  <FormControl>
    <Input {...field} />
  </FormControl>
  <FormDescription>
    Your public display name
  </FormDescription>
  <FormMessage />  {/* Error messages */}
</FormItem>
```

### Error Handling

Announce errors to screen readers:

```tsx
<FormField
  control={form.control}
  name="email"
  render={({ field, fieldState }) => (
    <FormItem>
      <FormLabel>Email</FormLabel>
      <FormControl>
        <Input
          {...field}
          aria-invalid={!!fieldState.error}
          aria-describedby={fieldState.error ? "email-error" : undefined}
        />
      </FormControl>
      <FormMessage id="email-error" />
    </FormItem>
  )}
/>
```

### Required Fields

Indicate required fields:

```tsx
<Label htmlFor="name">
  Name <span className="text-destructive">*</span>
  <span className="sr-only">(required)</span>
</Label>
<Input id="name" required />
```

### Fieldset and Legend

Group related fields:

```tsx
<fieldset>
  <legend className="text-lg font-semibold mb-4">
    Contact Information
  </legend>
  <div className="space-y-4">
    <FormField name="email" />
    <FormField name="phone" />
  </div>
</fieldset>
```

> Continued in `references/shadcn-accessibility-cont.md`.
