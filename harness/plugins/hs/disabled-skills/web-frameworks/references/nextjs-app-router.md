# Next.js App Router Architecture

Modern file-system based routing with React Server Components support.

## File Conventions

Special files define route behavior:

- `page.tsx` - Page UI, makes route publicly accessible
- `layout.tsx` - Shared UI wrapper for segment and children
- `loading.tsx` - Loading UI, automatically wraps page in Suspense
- `error.tsx` - Error UI, wraps page in Error Boundary
- `not-found.tsx` - 404 UI for route segment
- `route.ts` - API endpoint (Route Handler)
- `template.tsx` - Re-rendered layout (doesn't preserve state)
- `default.tsx` - Fallback for parallel routes

## Basic Routing

### Static Routes

```
app/
├── page.tsx              → /
├── about/
│   └── page.tsx         → /about
├── blog/
│   └── page.tsx         → /blog
└── contact/
    └── page.tsx         → /contact
```

### Dynamic Routes

Single parameter:
```tsx
// app/blog/[slug]/page.tsx
export default function BlogPost({ params }: { params: { slug: string } }) {
  return <h1>Post: {params.slug}</h1>
}
// Matches: /blog/hello-world, /blog/my-post
```

Catch-all segments:
```tsx
// app/shop/[...slug]/page.tsx
export default function Shop({ params }: { params: { slug: string[] } }) {
  return <h1>Category: {params.slug.join('/')}</h1>
}
// Matches: /shop/clothes, /shop/clothes/shirts, /shop/clothes/shirts/red
```

Optional catch-all:
```tsx
// app/docs/[[...slug]]/page.tsx
// Matches: /docs, /docs/getting-started, /docs/api/reference
```

## Layouts

### Root Layout (Required)

Must include `<html>` and `<body>` tags:

```tsx
// app/layout.tsx
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <header>Global Header</header>
        {children}
        <footer>Global Footer</footer>
      </body>
    </html>
  )
}
```

### Nested Layouts

```tsx
// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div>
      <nav>Dashboard Navigation</nav>
      <main>{children}</main>
    </div>
  )
}
```

Layout characteristics:
- Preserve state during navigation
- Do not re-render on navigation between child routes
- Can fetch data
- Cannot access pathname or searchParams (use Client Component)

## Route Groups

Organize routes without affecting URL structure:

```
app/
├── (marketing)/          # Group without URL segment
│   ├── about/page.tsx   → /about
│   ├── blog/page.tsx    → /blog
│   └── layout.tsx       # Marketing layout
├── (shop)/
│   ├── products/page.tsx → /products
│   ├── cart/page.tsx     → /cart
│   └── layout.tsx       # Shop layout
└── layout.tsx           # Root layout
```

Use cases:
- Multiple root layouts
- Organize code by feature/team
- Different layouts for different sections

## Parallel Routes

Render multiple pages simultaneously in same layout:

```
app/
├── @team/               # Named slot
│   └── page.tsx
├── @analytics/          # Named slot
│   └── page.tsx
├── page.tsx             # Default children
└── layout.tsx           # Consumes slots
```

```tsx
// app/layout.tsx
export default function Layout({
  children,
  team,
  analytics,
}: {
  children: React.ReactNode
  team: React.ReactNode
  analytics: React.ReactNode
}) {
  return (
    <>
      {children}
      <div className="grid grid-cols-2">
        {team}
        {analytics}
      </div>
    </>
  )
}
```

Use cases:
- Split views (dashboards)
- Modals
- Conditional rendering based on auth state

## Intercepting Routes

Intercept navigation to show content in different context:

```
app/
├── feed/
│   └── page.tsx
├── photo/
│   └── [id]/
│       └── page.tsx      # Full photo page
└── (..)photo/            # Intercepts /photo/[id]
    └── [id]/
        └── page.tsx      # Modal photo view
```

Matching conventions:
- `(.)` - Match same level
- `(..)` - Match one level above
- `(..)(..)` - Match two levels above
- `(...)` - Match from app root

Use case: Display modal when navigating from feed, show full page when URL accessed directly

## Loading States

### Loading File

Automatically wraps page in Suspense:

```tsx
// app/dashboard/loading.tsx
export default function Loading() {
  return <div className="spinner">Loading dashboard...</div>
}
```

### Manual Suspense

Fine-grained control:

```tsx
// app/page.tsx
import { Suspense } from 'react'

async function Posts() {
  const posts = await fetchPosts()
  return <PostsList posts={posts} />
}

export default function Page() {
  return (
    <div>
      <h1>My Blog</h1>
      <Suspense fallback={<div>Loading posts...</div>}>
        <Posts />
      </Suspense>
    </div>
  )
}
```


---

Continued in [nextjs-app-router-cont.md](nextjs-app-router-cont.md)
