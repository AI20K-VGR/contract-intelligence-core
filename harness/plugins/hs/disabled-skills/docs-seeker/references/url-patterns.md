# URL patterns — context7.com

## Priority 1: Topic-specific

**Pattern:** `https://context7.com/{org}/{repo}/llms.txt?topic={keyword}`

Use when the user asks about a specific feature/component — 10x faster, fewer tokens than the general pattern.

**Examples:**
```
shadcn/ui date picker
→ https://context7.com/shadcn-ui/ui/llms.txt?topic=date

Next.js caching
→ https://context7.com/vercel/next.js/llms.txt?topic=cache

Better Auth OAuth
→ https://context7.com/better-auth/better-auth/llms.txt?topic=oauth
```

## Priority 2: General library

**GitHub repos:** `https://context7.com/{org}/{repo}/llms.txt`

**Websites / non-GitHub:** `https://context7.com/websites/{normalized-name}/llms.txt`

## Common name to GitHub path mapping

```
next.js / nextjs      → vercel/next.js
astro                 → withastro/astro
remix                 → remix-run/remix
shadcn / shadcn/ui    → shadcn-ui/ui
better-auth           → better-auth/better-auth
sveltekit             → sveltejs/kit
```

## Official site fallbacks (use when context7.com returns 404)

```
Astro:     https://docs.astro.build/llms.txt
Next.js:   https://nextjs.org/llms.txt
Remix:     https://remix.run/llms.txt
SvelteKit: https://kit.svelte.dev/llms.txt
```

## Normalizing the topic keyword

- Lowercase; strip special chars; take first word of multi-word phrases; max 20 chars.

```
"date picker"         → "date"
"OAuth"               → "oauth"
"Server-Side Render"  → "server"
"caching strategies"  → "caching"
```

## Version-specific docs

- Latest (default): base URL, no version specifier needed.
- Specific version: WebSearch `"[library] v[version] llms.txt"` or try paths `/v{version}/llms.txt`, `/docs/v{version}/llms.txt`.
