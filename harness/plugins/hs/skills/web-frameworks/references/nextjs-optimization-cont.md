# Next.js Optimization (continued 2/2)

## Bundle Optimization

### Analyzing Bundle Size

```bash
# Install bundle analyzer
npm install @next/bundle-analyzer

# Create next.config.js wrapper
```

```js
// next.config.js
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
})

module.exports = withBundleAnalyzer({
  // Your Next.js config
})
```

```bash
# Run analysis
ANALYZE=true npm run build
```

### Dynamic Import (Code Splitting)

Split code and load on-demand:

```tsx
import dynamic from 'next/dynamic'

// Dynamic import with loading state
const DynamicChart = dynamic(() => import('@/components/chart'), {
  loading: () => <div>Loading chart...</div>,
  ssr: false, // Disable SSR for this component
})

export default function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>
      <DynamicChart />
    </div>
  )
}
```

Named exports:
```tsx
const DynamicComponent = dynamic(
  () => import('@/components/hello').then(mod => mod.Hello)
)
```

Multiple components:
```tsx
const DynamicHeader = dynamic(() => import('@/components/header'))
const DynamicFooter = dynamic(() => import('@/components/footer'))
```

### Tree Shaking

Import only what you need:

```tsx
// ❌ Bad - imports entire library
import _ from 'lodash'
const result = _.debounce(fn, 300)

// ✅ Good - imports only debounce
import debounce from 'lodash/debounce'
const result = debounce(fn, 300)

// ❌ Bad
import * as Icons from 'react-icons/fa'
<Icons.FaHome />

// ✅ Good
import { FaHome } from 'react-icons/fa'
<FaHome />
```

## Partial Prerendering (PPR)

Experimental: Combine static and dynamic rendering in same route.

```js
// next.config.js
module.exports = {
  experimental: {
    ppr: true,
  }
}
```

```tsx
// app/page.tsx
import { Suspense } from 'react'

// Static shell
export default function Page() {
  return (
    <div>
      <header>Static Header</header>

      {/* Dynamic content with Suspense boundary */}
      <Suspense fallback={<div>Loading...</div>}>
        <DynamicContent />
      </Suspense>

      <footer>Static Footer</footer>
    </div>
  )
}

// Dynamic component
async function DynamicContent() {
  const data = await fetch('https://api.example.com/data', {
    cache: 'no-store'
  }).then(r => r.json())

  return <div>{data.content}</div>
}
```

Static shell loads instantly, dynamic content streams in.

## Metadata Optimization

### Static Metadata

```tsx
// app/page.tsx
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'My Page',
  description: 'Page description',
  keywords: ['next.js', 'react', 'javascript'],
  openGraph: {
    title: 'My Page',
    description: 'Page description',
    images: ['/og-image.jpg'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'My Page',
    description: 'Page description',
    images: ['/twitter-image.jpg'],
  },
  alternates: {
    canonical: 'https://example.com/page',
  },
  robots: {
    index: true,
    follow: true,
  },
}
```

### Dynamic Metadata

```tsx
// app/blog/[slug]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const post = await getPost(params.slug)

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [post.coverImage],
      type: 'article',
      publishedTime: post.publishedAt,
      authors: [post.author.name],
    },
  }
}
```

### Metadata Files

Create these files in `app/` directory:

- `favicon.ico` - Favicon
- `icon.png` / `icon.jpg` - App icon
- `apple-icon.png` - Apple touch icon
- `opengraph-image.png` - Open Graph image
- `twitter-image.png` - Twitter card image
- `robots.txt` - Robots file
- `sitemap.xml` - Sitemap

Or generate dynamically:
```tsx
// app/sitemap.ts
export default async function sitemap() {
  const posts = await getPosts()

  return [
    {
      url: 'https://example.com',
      lastModified: new Date(),
    },
    ...posts.map(post => ({
      url: `https://example.com/blog/${post.slug}`,
      lastModified: post.updatedAt,
    }))
  ]
}
```

## Performance Best Practices

1. **Use Image component** - Automatic optimization, lazy loading, modern formats
2. **Optimize fonts** - Use next/font to eliminate layout shift
3. **Dynamic imports** - Code split large components and third-party libraries
4. **Analyze bundle** - Identify and eliminate large dependencies
5. **Proper caching** - Use ISR for semi-static content
6. **Streaming with Suspense** - Load fast content first, stream slow content
7. **Minimize JavaScript** - Default to Server Components
8. **Prefetch links** - Next.js prefetches Link components in viewport
9. **Use Script component** - Control third-party script loading
10. **Compress assets** - Enable compression in hosting platform
11. **Use CDN** - Deploy to edge network (Vercel, Cloudflare)
12. **Monitor metrics** - Track Core Web Vitals (LCP, FID, CLS)
