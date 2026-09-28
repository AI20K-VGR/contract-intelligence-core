# Next.js Server Components (continued 2/2)

## Context in Server/Client Components

### Problem: Context Requires Client Components

```tsx
// ❌ Won't work - Server Components can't use context
import { createContext } from 'react'

const ThemeContext = createContext()

export default function Layout({ children }) {
  return (
    <ThemeContext.Provider value="dark">
      {children}
    </ThemeContext.Provider>
  )
}
```

### Solution: Create Client Component Wrapper

```tsx
// app/providers.tsx - Client Component
'use client'

import { createContext, useContext } from 'react'

const ThemeContext = createContext('light')

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ThemeContext.Provider value="dark">
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}

// app/layout.tsx - Server Component
import { ThemeProvider } from './providers'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
```

## Third-Party Component Integration

Many third-party components need client-side features:

```tsx
// components/carousel.tsx
'use client'

import 'slick-carousel/slick/slick.css'
import Slider from 'react-slick'

export function Carousel({ children }) {
  return <Slider>{children}</Slider>
}

// app/page.tsx - Server Component
import { Carousel } from '@/components/carousel'

export default function Page() {
  return (
    <Carousel>
      <div>Slide 1</div>
      <div>Slide 2</div>
    </Carousel>
  )
}
```

## Server Actions

Call server-side functions from Client Components:

```tsx
// app/actions.ts
'use server'

import { revalidatePath } from 'next/cache'
import { db } from '@/lib/db'

export async function createPost(formData: FormData) {
  const title = formData.get('title') as string
  const content = formData.get('content') as string

  await db.post.create({
    data: { title, content }
  })

  revalidatePath('/posts')
}

// app/new-post/page.tsx
import { createPost } from '@/app/actions'

export default function NewPost() {
  return (
    <form action={createPost}>
      <input name="title" required />
      <textarea name="content" required />
      <button type="submit">Create Post</button>
    </form>
  )
}
```

With Client Component:
```tsx
// components/post-form.tsx
'use client'

import { createPost } from '@/app/actions'
import { useFormStatus } from 'react-dom'

function SubmitButton() {
  const { pending } = useFormStatus()
  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Creating...' : 'Create Post'}
    </button>
  )
}

export function PostForm() {
  return (
    <form action={createPost}>
      <input name="title" required />
      <textarea name="content" required />
      <SubmitButton />
    </form>
  )
}
```

## When to Use Each Component Type

### Use Server Components When:
- Fetching data from database or API
- Accessing backend resources directly
- Keeping sensitive information on server (tokens, keys)
- Reducing client-side JavaScript
- Rendering static content
- No interactivity needed

### Use Client Components When:
- Adding interactivity (onClick, onChange)
- Managing state (useState, useReducer)
- Using lifecycle effects (useEffect)
- Using browser-only APIs (localStorage, navigator)
- Using custom React hooks
- Using React Context
- Using third-party libraries requiring client features

## Best Practices

1. **Default to Server Components** - Only use 'use client' when needed
2. **Move Client Components to leaves** - Keep them as deep as possible in tree
3. **Pass Server Components as children** - Avoid turning entire trees client-side
4. **Share data via fetch** - Let Next.js dedupe requests automatically
5. **Use Suspense for streaming** - Improve perceived performance
6. **Separate client logic** - Extract client-only code to separate files
7. **Minimize client bundle** - Less JavaScript = faster page loads

## Common Patterns

### Protected Content

```tsx
// app/dashboard/page.tsx - Server Component
import { redirect } from 'next/navigation'
import { getUser } from '@/lib/auth'

export default async function Dashboard() {
  const user = await getUser()

  if (!user) {
    redirect('/login')
  }

  return <div>Welcome, {user.name}</div>
}
```

### Optimistic Updates

```tsx
// components/like-button.tsx
'use client'

import { useOptimistic } from 'react'
import { likePost } from '@/app/actions'

export function LikeButton({ postId, initialLikes }) {
  const [optimisticLikes, addOptimisticLike] = useOptimistic(
    initialLikes,
    (state, amount) => state + amount
  )

  return (
    <button
      onClick={async () => {
        addOptimisticLike(1)
        await likePost(postId)
      }}
    >
      Likes: {optimisticLikes}
    </button>
  )
}
```

### Loading States with Streaming

```tsx
// app/dashboard/page.tsx
import { Suspense } from 'react'

async function RevenueChart() {
  const data = await fetchRevenue() // Slow query
  return <Chart data={data} />
}

async function RecentSales() {
  const sales = await fetchSales() // Fast query
  return <SalesTable sales={sales} />
}

export default function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>

      <Suspense fallback={<ChartSkeleton />}>
        <RevenueChart />
      </Suspense>

      <Suspense fallback={<TableSkeleton />}>
        <RecentSales />
      </Suspense>
    </div>
  )
}
```
