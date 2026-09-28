# Next.js Server Components

React Server Components (RSC) architecture, patterns, and best practices.

## Core Concepts

### Server Components (Default)

All components in `app/` directory are Server Components by default:

```tsx
// app/posts/page.tsx - Server Component
async function getPosts() {
  const res = await fetch('https://api.example.com/posts')
  return res.json()
}

export default async function PostsPage() {
  const posts = await getPosts()

  return (
    <div>
      {posts.map(post => (
        <article key={post.id}>{post.title}</article>
      ))}
    </div>
  )
}
```

**Benefits:**
- Fetch data on server (direct database access)
- Keep sensitive data/keys on server
- Reduce client-side JavaScript bundle
- Improve initial page load and SEO
- Cache results on server
- Stream content to client

**Limitations:**
- Cannot use React hooks (useState, useEffect, useContext)
- Cannot use browser APIs (window, localStorage)
- Cannot add event listeners (onClick, onChange)
- Cannot use React class components

### Client Components

Mark with `'use client'` directive at top of file:

```tsx
// components/counter.tsx - Client Component
'use client'

import { useState } from 'react'

export function Counter() {
  const [count, setCount] = useState(0)

  return (
    <button onClick={() => setCount(count + 1)}>
      Count: {count}
    </button>
  )
}
```

**Use Client Components for:**
- Interactive UI (event handlers)
- State management (useState, useReducer)
- Effects (useEffect, useLayoutEffect)
- Browser-only APIs (localStorage, geolocation)
- Custom React hooks
- Context consumers

## Composition Patterns

### Server Component as Wrapper

Keep Server Components as parent, Client Components as children:

```tsx
// app/page.tsx - Server Component
import { ClientSidebar } from './sidebar'
import { ClientButton } from './button'

export default async function Page() {
  const data = await fetchData() // Server-side data fetch

  return (
    <div>
      <h1>Server-rendered heading</h1>
      <ClientSidebar />
      <ClientButton />
      <p>More server-rendered content: {data.title}</p>
    </div>
  )
}
```

### Passing Server Components to Client Components

Use children pattern to avoid making entire tree client-side:

```tsx
// app/page.tsx - Server Component
import { ClientProvider } from './client-provider'
import { ServerContent } from './server-content'

export default function Page() {
  return (
    <ClientProvider>
      <ServerContent /> {/* Stays as Server Component */}
    </ClientProvider>
  )
}

// client-provider.tsx - Client Component
'use client'

export function ClientProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState()

  return <div>{children}</div>
}

// server-content.tsx - Server Component
export async function ServerContent() {
  const data = await fetchData()
  return <p>{data.content}</p>
}
```

### Sharing Data Between Server Components

No props/context needed - fetch data where needed:

```tsx
// lib/data.ts
export async function getUser() {
  const res = await fetch('https://api.example.com/user', {
    cache: 'force-cache' // Will dedupe automatically
  })
  return res.json()
}

// app/header.tsx
import { getUser } from '@/lib/data'

export async function Header() {
  const user = await getUser() // Fetch 1
  return <div>Welcome, {user.name}</div>
}

// app/profile.tsx
import { getUser } from '@/lib/data'

export async function Profile() {
  const user = await getUser() // Fetch 2 (deduped automatically)
  return <div>Email: {user.email}</div>
}
```

Next.js automatically dedupes identical fetch requests during render.

## Async Components

Server Components can be async functions:

```tsx
// app/posts/[id]/page.tsx
async function getPost(id: string) {
  const res = await fetch(`https://api.example.com/posts/${id}`)
  return res.json()
}

async function getComments(postId: string) {
  const res = await fetch(`https://api.example.com/posts/${postId}/comments`)
  return res.json()
}

export default async function Post({ params }: { params: { id: string } }) {
  // Parallel data fetching
  const [post, comments] = await Promise.all([
    getPost(params.id),
    getComments(params.id)
  ])

  return (
    <article>
      <h1>{post.title}</h1>
      <p>{post.content}</p>
      <CommentsList comments={comments} />
    </article>
  )
}
```

## Streaming with Suspense

Stream components as they resolve:

```tsx
// app/page.tsx
import { Suspense } from 'react'

async function SlowComponent() {
  await new Promise(resolve => setTimeout(resolve, 3000))
  return <div>Loaded after 3 seconds</div>
}

async function FastComponent() {
  await new Promise(resolve => setTimeout(resolve, 500))
  return <div>Loaded after 0.5 seconds</div>
}

export default function Page() {
  return (
    <div>
      <h1>Instant heading</h1>

      <Suspense fallback={<div>Loading fast...</div>}>
        <FastComponent />
      </Suspense>

      <Suspense fallback={<div>Loading slow...</div>}>
        <SlowComponent />
      </Suspense>
    </div>
  )
}
```

Benefits:
- Fast components render immediately
- Slow components don't block page
- Progressive enhancement
- Better perceived performance


---

Continued in [nextjs-server-components-cont.md](nextjs-server-components-cont.md)
