# Next.js Data Fetching

Server-side data fetching, caching strategies, revalidation, and loading patterns.

## Fetch API Extensions

Next.js extends native fetch with caching and revalidation:

```tsx
// Force cache (default) - cache forever
fetch('https://api.example.com/data', { cache: 'force-cache' })

// No cache - fetch on every request
fetch('https://api.example.com/data', { cache: 'no-store' })

// Revalidate - cache with time-based revalidation
fetch('https://api.example.com/data', { next: { revalidate: 3600 } })

// Tag-based revalidation
fetch('https://api.example.com/data', { next: { tags: ['posts'] } })
```

## Caching Strategies

### Static Data (Default)

Fetched at build time, cached indefinitely:

```tsx
// app/posts/page.tsx
async function getPosts() {
  const res = await fetch('https://api.example.com/posts')
  // Same as: fetch(url, { cache: 'force-cache' })
  return res.json()
}

export default async function Posts() {
  const posts = await getPosts()
  return <PostsList posts={posts} />
}
```

Use for: Content that rarely changes, static pages

### Dynamic Data

Fetched on every request:

```tsx
async function getUser() {
  const res = await fetch('https://api.example.com/user', {
    cache: 'no-store'
  })
  return res.json()
}

export default async function Profile() {
  const user = await getUser()
  return <div>{user.name}</div>
}
```

Use for: User-specific data, real-time content

### Incremental Static Regeneration (ISR)

Revalidate cached data after time period:

```tsx
async function getPosts() {
  const res = await fetch('https://api.example.com/posts', {
    next: { revalidate: 60 } // Revalidate every 60 seconds
  })
  return res.json()
}

export default async function Posts() {
  const posts = await getPosts()
  return <PostsList posts={posts} />
}
```

How it works:
1. First request: Generate page, cache it
2. Subsequent requests: Serve cached page
3. After 60s: Next request triggers regeneration in background
4. New page cached, served to subsequent requests

Use for: News sites, blogs, product listings

## Revalidation Strategies

### Time-Based Revalidation

```tsx
// Revalidate every hour
fetch('https://api.example.com/posts', {
  next: { revalidate: 3600 }
})

// Revalidate every 10 seconds
fetch('https://api.example.com/trending', {
  next: { revalidate: 10 }
})
```

### On-Demand Revalidation

Revalidate specific paths or tags programmatically:

```tsx
// app/actions.ts
'use server'

import { revalidatePath, revalidateTag } from 'next/cache'

export async function createPost(formData: FormData) {
  const post = await db.post.create({
    data: {
      title: formData.get('title'),
      content: formData.get('content')
    }
  })

  // Revalidate specific path
  revalidatePath('/posts')
  revalidatePath(`/posts/${post.id}`)

  // Or revalidate by tag
  revalidateTag('posts')
}
```

Tag-based revalidation:
```tsx
// Fetch with tags
async function getPosts() {
  const res = await fetch('https://api.example.com/posts', {
    next: { tags: ['posts', 'content'] }
  })
  return res.json()
}

async function getComments(postId: string) {
  const res = await fetch(`https://api.example.com/comments/${postId}`, {
    next: { tags: ['comments', `post-${postId}`] }
  })
  return res.json()
}

// Revalidate all 'posts' tagged requests
revalidateTag('posts')

// Revalidate specific post comments
revalidateTag(`post-${postId}`)
```

### Route Segment Config

Configure entire route segment:

```tsx
// app/posts/page.tsx
export const revalidate = 3600 // Revalidate every hour

export default async function Posts() {
  const posts = await fetch('https://api.example.com/posts').then(r => r.json())
  return <PostsList posts={posts} />
}
```

Options:
```tsx
export const dynamic = 'auto' // default
export const dynamic = 'force-dynamic' // no caching
export const dynamic = 'error' // error if dynamic
export const dynamic = 'force-static' // force static

export const revalidate = false // never revalidate (default)
export const revalidate = 0 // no cache
export const revalidate = 60 // revalidate every 60s

export const fetchCache = 'auto' // default
export const fetchCache = 'default-cache'
export const fetchCache = 'only-cache'
export const fetchCache = 'force-cache'
export const fetchCache = 'default-no-store'
export const fetchCache = 'only-no-store'
export const fetchCache = 'force-no-store'
```

## Data Fetching Patterns

### Parallel Fetching

Fetch multiple resources simultaneously:

```tsx
async function getData() {
  // Start both requests in parallel
  const [posts, users] = await Promise.all([
    fetch('https://api.example.com/posts').then(r => r.json()),
    fetch('https://api.example.com/users').then(r => r.json())
  ])

  return { posts, users }
}

export default async function Page() {
  const { posts, users } = await getData()
  return (
    <div>
      <PostsList posts={posts} />
      <UsersList users={users} />
    </div>
  )
}
```

### Sequential Fetching

Fetch dependent data:

```tsx
async function getData(postId: string) {
  // Fetch post first
  const post = await fetch(`https://api.example.com/posts/${postId}`).then(r => r.json())

  // Then fetch author based on post data
  const author = await fetch(`https://api.example.com/users/${post.authorId}`).then(r => r.json())

  return { post, author }
}

export default async function Post({ params }: { params: { id: string } }) {
  const { post, author } = await getData(params.id)
  return (
    <article>
      <h1>{post.title}</h1>
      <p>By {author.name}</p>
      <div>{post.content}</div>
    </article>
  )
}
```

### Preloading Data

Optimize sequential waterfalls:

```tsx
// lib/data.ts
import { cache } from 'react'

export const getUser = cache(async (id: string) => {
  const res = await fetch(`https://api.example.com/users/${id}`)
  return res.json()
})

// app/user/[id]/page.tsx
import { getUser } from '@/lib/data'

// Preload before component renders
async function preload(id: string) {
  void getUser(id) // Start fetching immediately
}

export default async function User({ params }: { params: { id: string } }) {
  preload(params.id) // Start fetch
  // Render other UI
  const user = await getUser(params.id) // Will use cached result

  return <div>{user.name}</div>
}
```


---

Continued in [nextjs-data-fetching-cont.md](nextjs-data-fetching-cont.md)
