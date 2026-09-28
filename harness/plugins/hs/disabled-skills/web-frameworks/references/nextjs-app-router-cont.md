# Next.js App Router Architecture (continued 2/2)

## Error Handling

### Error File

Wraps segment in Error Boundary:

```tsx
// app/error.tsx
'use client' // Error components must be Client Components

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <p>{error.message}</p>
      <button onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

### Global Error

Catches errors in root layout:

```tsx
// app/global-error.tsx
'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <h2>Application Error!</h2>
        <button onClick={() => reset()}>Try again</button>
      </body>
    </html>
  )
}
```

### Not Found

```tsx
// app/blog/[slug]/page.tsx
import { notFound } from 'next/navigation'

export default async function Post({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug)

  if (!post) {
    notFound() // Triggers not-found.tsx
  }

  return <article>{post.content}</article>
}

// app/blog/[slug]/not-found.tsx
export default function NotFound() {
  return <h2>Post not found</h2>
}
```

## Navigation

### Link Component

```tsx
import Link from 'next/link'

// Basic link
<Link href="/about">About</Link>

// Dynamic route
<Link href={`/blog/${post.slug}`}>Read Post</Link>

// With object
<Link href={{
  pathname: '/blog/[slug]',
  query: { slug: 'hello-world' },
}}>
  Read Post
</Link>

// Prefetch control
<Link href="/dashboard" prefetch={false}>
  Dashboard
</Link>

// Replace history
<Link href="/search" replace>
  Search
</Link>
```

### useRouter Hook (Client)

```tsx
'use client'

import { useRouter } from 'next/navigation'

export function NavigateButton() {
  const router = useRouter()

  return (
    <>
      <button onClick={() => router.push('/dashboard')}>Dashboard</button>
      <button onClick={() => router.replace('/login')}>Login</button>
      <button onClick={() => router.refresh()}>Refresh</button>
      <button onClick={() => router.back()}>Back</button>
      <button onClick={() => router.forward()}>Forward</button>
    </>
  )
}
```

### Programmatic Navigation (Server)

```tsx
import { redirect } from 'next/navigation'

export default async function Page() {
  const session = await getSession()

  if (!session) {
    redirect('/login')
  }

  return <div>Protected content</div>
}
```

## Accessing Route Information

### searchParams (Server)

```tsx
// app/shop/page.tsx
export default function Shop({
  searchParams,
}: {
  searchParams: { sort?: string; filter?: string }
}) {
  const sort = searchParams.sort || 'newest'
  const filter = searchParams.filter

  return <div>Showing: {filter}, sorted by {sort}</div>
}
// Accessed via: /shop?sort=price&filter=shirts
```

### useSearchParams (Client)

```tsx
'use client'

import { useSearchParams } from 'next/navigation'

export function SearchFilter() {
  const searchParams = useSearchParams()
  const query = searchParams.get('q')

  return <div>Search query: {query}</div>
}
```

### usePathname (Client)

```tsx
'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'

export function Navigation() {
  const pathname = usePathname()

  return (
    <nav>
      <Link href="/" className={pathname === '/' ? 'active' : ''}>
        Home
      </Link>
      <Link href="/about" className={pathname === '/about' ? 'active' : ''}>
        About
      </Link>
    </nav>
  )
}
```

## Project Structure Best Practices

```
app/
├── (auth)/                 # Route group for auth pages
│   ├── login/
│   ├── signup/
│   └── layout.tsx         # Auth layout
├── (dashboard)/           # Route group for dashboard
│   ├── dashboard/
│   ├── settings/
│   └── layout.tsx         # Dashboard layout
├── api/                   # API routes
│   ├── auth/
│   └── posts/
├── _components/           # Private folder (not routes)
│   ├── header.tsx
│   └── footer.tsx
├── _lib/                  # Private utilities
│   ├── auth.ts
│   └── db.ts
├── layout.tsx             # Root layout
├── page.tsx               # Home page
├── loading.tsx
├── error.tsx
└── not-found.tsx
```

Use underscore prefix for folders that shouldn't be routes.
