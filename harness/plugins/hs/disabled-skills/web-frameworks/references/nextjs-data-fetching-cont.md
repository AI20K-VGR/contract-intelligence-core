# Next.js Data Fetching (continued 2/2)

## Loading States

### Loading File

Automatic loading UI:

```tsx
// app/dashboard/loading.tsx
export default function Loading() {
  return <div className="spinner">Loading dashboard...</div>
}

// app/dashboard/page.tsx
export default async function Dashboard() {
  const data = await fetchDashboard()
  return <DashboardView data={data} />
}
```

### Suspense Boundaries

Granular loading states:

```tsx
// app/dashboard/page.tsx
import { Suspense } from 'react'

async function Revenue() {
  const data = await fetchRevenue() // 2s
  return <RevenueChart data={data} />
}

async function Sales() {
  const data = await fetchSales() // 0.5s
  return <SalesTable data={data} />
}

export default function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>

      <Suspense fallback={<RevenueChartSkeleton />}>
        <Revenue />
      </Suspense>

      <Suspense fallback={<SalesTableSkeleton />}>
        <Sales />
      </Suspense>
    </div>
  )
}
```

Sales loads after 0.5s, Revenue after 2s - no blocking.

## Static Generation

### generateStaticParams

Pre-render dynamic routes at build time:

```tsx
// app/posts/[slug]/page.tsx
export async function generateStaticParams() {
  const posts = await fetch('https://api.example.com/posts').then(r => r.json())

  return posts.map(post => ({
    slug: post.slug
  }))
}

export default async function Post({ params }: { params: { slug: string } }) {
  const post = await fetch(`https://api.example.com/posts/${params.slug}`).then(r => r.json())
  return <article>{post.content}</article>
}
```

Generates static pages at build:
- `/posts/hello-world`
- `/posts/nextjs-guide`
- `/posts/react-tips`

### Dynamic Params Handling

```tsx
// app/posts/[slug]/page.tsx
export const dynamicParams = true // default - generate on-demand if not pre-rendered

export const dynamicParams = false // 404 for paths not in generateStaticParams
```

## Error Handling

### Try-Catch in Server Components

```tsx
async function getData() {
  try {
    const res = await fetch('https://api.example.com/data')

    if (!res.ok) {
      throw new Error('Failed to fetch data')
    }

    return res.json()
  } catch (error) {
    console.error('Data fetch error:', error)
    return null
  }
}

export default async function Page() {
  const data = await getData()

  if (!data) {
    return <div>Failed to load data</div>
  }

  return <DataView data={data} />
}
```

### Error Boundaries

```tsx
// app/error.tsx
'use client'

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
      <button onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

## Database Queries

Direct database access in Server Components:

```tsx
// lib/db.ts
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

export async function getPosts() {
  return prisma.post.findMany({
    include: { author: true },
    orderBy: { createdAt: 'desc' }
  })
}

// app/posts/page.tsx
import { getPosts } from '@/lib/db'

export default async function Posts() {
  const posts = await getPosts()
  return <PostsList posts={posts} />
}
```

## Best Practices

1. **Default to static** - Use `cache: 'force-cache'` or default behavior
2. **Use ISR for semi-dynamic content** - Balance freshness and performance
3. **Fetch in parallel** - Use `Promise.all()` for independent requests
4. **Add loading states** - Use Suspense for better UX
5. **Handle errors gracefully** - Provide fallbacks and error boundaries
6. **Use on-demand revalidation** - Trigger updates after mutations
7. **Tag your fetches** - Enable granular cache invalidation
8. **Dedupe automatically** - Next.js dedupes identical fetch requests
9. **Avoid client-side fetching** - Use Server Components when possible
10. **Cache database queries** - Use React cache() for expensive queries
