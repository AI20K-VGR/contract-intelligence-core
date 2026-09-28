# RemixIcon Integration Guide (continued 2/3)

## Common Patterns

### Navigation Menu

```tsx
// Webfont approach
export function Navigation() {
  return (
    <nav>
      <a href="/home">
        <i className="ri-home-line"></i>
        <span>Home</span>
      </a>
      <a href="/search">
        <i className="ri-search-line"></i>
        <span>Search</span>
      </a>
      <a href="/profile">
        <i className="ri-user-line"></i>
        <span>Profile</span>
      </a>
    </nav>
  )
}

// React component approach
import { RiHomeLine, RiSearchLine, RiUserLine } from "@remixicon/react"

export function Navigation() {
  return (
    <nav>
      <a href="/home">
        <RiHomeLine size={20} />
        <span>Home</span>
      </a>
      <a href="/search">
        <RiSearchLine size={20} />
        <span>Search</span>
      </a>
      <a href="/profile">
        <RiUserLine size={20} />
        <span>Profile</span>
      </a>
    </nav>
  )
}
```

### Button with Icon

```tsx
import { RiDownloadLine } from "@remixicon/react"

export function DownloadButton() {
  return (
    <button className="btn-primary">
      <RiDownloadLine size={18} />
      <span>Download</span>
    </button>
  )
}
```

### Status Indicators

```tsx
import {
  RiCheckboxCircleFill,
  RiErrorWarningFill,
  RiAlertFill,
  RiInformationFill
} from "@remixicon/react"

type Status = 'success' | 'error' | 'warning' | 'info'

export function StatusIcon({ status }: { status: Status }) {
  const icons = {
    success: <RiCheckboxCircleFill color="green" size={20} />,
    error: <RiErrorWarningFill color="red" size={20} />,
    warning: <RiAlertFill color="orange" size={20} />,
    info: <RiInformationFill color="blue" size={20} />
  }

  return icons[status]
}
```

### Input with Icon

```tsx
import { RiSearchLine } from "@remixicon/react"

export function SearchInput() {
  return (
    <div className="input-group">
      <RiSearchLine size={20} className="input-icon" />
      <input type="text" placeholder="Search..." />
    </div>
  )
}
```

```css
.input-group {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #666;
}

input {
  padding-left: 40px;
}
```

### Dynamic Icon Selection

```tsx
import { RiHomeLine, RiHeartFill, RiStarLine } from "@remixicon/react"

const iconMap = {
  home: RiHomeLine,
  heart: RiHeartFill,
  star: RiStarLine,
}

export function DynamicIcon({ name, size = 24 }: { name: string; size?: number }) {
  const Icon = iconMap[name]
  return Icon ? <Icon size={size} /> : null
}

// Usage
<DynamicIcon name="home" size={24} />
```

## Styling & Customization

### Color

```tsx
// Inherit from parent
<i className="ri-home-line" style={{ color: 'blue' }}></i>

// React component
<RiHomeLine color="blue" />
<RiHomeLine color="#ff0000" />
<RiHomeLine color="rgb(255, 0, 0)" />
```

### Size

```tsx
// CSS class
<i className="ri-home-line ri-2x"></i>

// Inline style
<i className="ri-home-line" style={{ fontSize: '32px' }}></i>

// React component
<RiHomeLine size={32} />
<RiHomeLine size="2em" />
```

### Responsive Sizing

```css
.icon {
  font-size: 24px;
}

@media (max-width: 768px) {
  .icon {
    font-size: 20px;
  }
}
```

### Animations

```css
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

```tsx
<i className="ri-loader-4-line spin"></i>
```

### Hover Effects

```css
.icon-button {
  transition: color 0.2s;
}

.icon-button:hover {
  color: #007bff;
}
```

## Accessibility

### Provide Labels

**Icon-only buttons:**
```tsx
<button aria-label="Search">
  <i className="ri-search-line"></i>
</button>

// Or with React
<button aria-label="Search">
  <RiSearchLine size={20} />
</button>
```

### Decorative Icons

Hide from screen readers:

```tsx
<span aria-hidden="true">
  <i className="ri-star-fill"></i>
</span>

// React
<span aria-hidden="true">
  <RiStarFill size={16} />
</span>
```

### Icon with Text

```tsx
<button>
  <RiDownloadLine size={18} aria-hidden="true" />
  <span>Download</span>
</button>
```

Text provides context, icon is decorative.


---

Continued in [remix-icon-integration-cont2.md](remix-icon-integration-cont2.md)
