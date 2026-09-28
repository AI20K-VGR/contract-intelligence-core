# Web Frameworks Playbook

Quick-start setup, full-stack/monorepo patterns, best practices, implementation checklist for Next.js + Turborepo + RemixIcon. Companion detail for `web-frameworks`.

## Quick Start

### Next.js Application

```bash
# Create new project
npx create-next-app@latest my-app
cd my-app

# Install RemixIcon
npm install remixicon

# Import in layout
# app/layout.tsx
import 'remixicon/fonts/remixicon.css'

# Start development
npm run dev
```

### Turborepo Monorepo

```bash
# Create monorepo
npx create-turbo@latest my-monorepo
cd my-monorepo

# Structure:
# apps/web/          - Next.js application
# apps/docs/         - Documentation site
# packages/ui/       - Shared components with RemixIcon
# packages/config/   - Shared configs
# turbo.json         - Pipeline configuration

# Run all apps
npm run dev

# Build all packages
npm run build
```

### RemixIcon Integration

```tsx
// Webfont (HTML/CSS)
<i className="ri-home-line"></i>
<i className="ri-search-fill ri-2x"></i>

// React component
import { RiHomeLine, RiSearchFill } from "@remixicon/react"
<RiHomeLine size={24} />
<RiSearchFill size={32} color="blue" />
```


## Common Patterns & Workflows

### Pattern 1: Full-Stack Monorepo

```
my-monorepo/
├── apps/
│   ├── web/              # Customer-facing Next.js app
│   ├── admin/            # Admin dashboard Next.js app
│   └── docs/             # Documentation site
├── packages/
│   ├── ui/               # Shared UI with RemixIcon
│   ├── api-client/       # API client library
│   ├── config/           # ESLint, TypeScript configs
│   └── types/            # Shared TypeScript types
└── turbo.json            # Build pipeline
```

**turbo.json:**
```json
{
  "$schema": "https://turbo.build/schema.json",
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {},
    "test": {
      "dependsOn": ["build"]
    }
  }
}
```

### Pattern 2: Shared Component Library

```tsx
// packages/ui/src/button.tsx
import { RiLoader4Line } from "@remixicon/react"

export function Button({ children, loading, icon }) {
  return (
    <button>
      {loading ? <RiLoader4Line className="animate-spin" /> : icon}
      {children}
    </button>
  )
}

// apps/web/app/page.tsx
import { Button } from "@repo/ui/button"
import { RiHomeLine } from "@remixicon/react"

export default function Page() {
  return <Button icon={<RiHomeLine />}>Home</Button>
}
```

### Pattern 3: Optimized Data Fetching

```tsx
// app/posts/[slug]/page.tsx
import { notFound } from 'next/navigation'

// Static generation at build time
export async function generateStaticParams() {
  const posts = await getPosts()
  return posts.map(post => ({ slug: post.slug }))
}

// Revalidate every hour
async function getPost(slug: string) {
  const res = await fetch(`https://api.example.com/posts/${slug}`, {
    next: { revalidate: 3600 }
  })
  if (!res.ok) return null
  return res.json()
}

export default async function Post({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug)
  if (!post) notFound()

  return <article>{post.content}</article>
}
```

### Pattern 4: Monorepo CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: ck:CI
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 18
      - run: npm install
      - run: npx turbo run build test lint
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}
```


## Best Practices

**Next.js:**
- Default to Server Components, use Client Components only when needed
- Implement proper loading and error states
- Use Image component for automatic optimization
- Set proper metadata for SEO
- Leverage caching strategies (force-cache, revalidate, no-store)
- Track stable Next.js security releases separately from canary framework drift. Production apps should stay on a patched stable release line and avoid canary-only pins unless testing a specific upstream issue.

**Turborepo:**
- Structure monorepo with clear separation (apps/, packages/)
- Define task dependencies correctly (^build for topological)
- Configure outputs for proper caching
- Enable remote caching for team collaboration
- Use filters to run tasks on changed packages only

**RemixIcon:**
- Use line style for minimal interfaces, fill for emphasis
- Maintain 24x24 grid alignment for crisp rendering
- Provide aria-labels for accessibility
- Use currentColor for flexible theming
- Prefer webfonts for multiple icons, SVG for single icons


## Implementation Checklist

Building with this stack:

- [ ] Create project structure (single app or monorepo)
- [ ] Configure TypeScript and ESLint
- [ ] Set up Next.js with App Router
- [ ] Configure Turborepo pipeline (if monorepo)
- [ ] Install and configure RemixIcon
- [ ] Implement routing and layouts
- [ ] Add loading and error states
- [ ] Configure image and font optimization
- [ ] Set up data fetching patterns
- [ ] Configure caching strategies
- [ ] Add API routes as needed
- [ ] Implement shared component library (if monorepo)
- [ ] Configure remote caching (if monorepo)
- [ ] Set up CI/CD pipeline
- [ ] Configure deployment platform
