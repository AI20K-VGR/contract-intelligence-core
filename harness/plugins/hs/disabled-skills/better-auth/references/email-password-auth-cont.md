# Email/Password Authentication (continued 2/2)

## Framework Setup

### Next.js (App Router)

```ts
// app/api/auth/[...all]/route.ts
import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { POST, GET } = toNextJsHandler(auth);
```

### Next.js (Pages Router)

```ts
// pages/api/auth/[...all].ts
import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export default toNextJsHandler(auth);
```

### Nuxt

```ts
// server/api/auth/[...all].ts
import { auth } from "~/utils/auth";
import { toWebRequest } from "better-auth/utils/web";

export default defineEventHandler((event) => {
  return auth.handler(toWebRequest(event));
});
```

### SvelteKit

```ts
// hooks.server.ts
import { auth } from "$lib/auth";
import { svelteKitHandler } from "better-auth/svelte-kit";

export async function handle({ event, resolve }) {
  return svelteKitHandler({ event, resolve, auth });
}
```

### Astro

```ts
// pages/api/auth/[...all].ts
import { auth } from "@/lib/auth";

export async function ALL({ request }: { request: Request }) {
  return auth.handler(request);
}
```

### Hono

```ts
import { Hono } from "hono";
import { auth } from "./auth";

const app = new Hono();

app.on(["POST", "GET"], "/api/auth/*", (c) => {
  return auth.handler(c.req.raw);
});
```

### Express

```ts
import express from "express";
import { toNodeHandler } from "better-auth/node";
import { auth } from "./auth";

const app = express();

app.all("/api/auth/*", toNodeHandler(auth));
```

## Protected Routes

### Next.js Middleware

```ts
// middleware.ts
import { auth } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

export async function middleware(request: NextRequest) {
  const session = await auth.api.getSession({
    headers: request.headers
  });

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/profile/:path*"]
};
```

### SvelteKit Hooks

```ts
// hooks.server.ts
import { auth } from "$lib/auth";
import { redirect } from "@sveltejs/kit";

export async function handle({ event, resolve }) {
  const session = await auth.api.getSession({
    headers: event.request.headers
  });

  if (event.url.pathname.startsWith("/dashboard") && !session) {
    throw redirect(303, "/login");
  }

  return resolve(event);
}
```

### Nuxt Middleware

```ts
// middleware/auth.ts
export default defineNuxtRouteMiddleware(async (to) => {
  const { data: session } = await useAuthSession();

  if (!session.value && to.path.startsWith("/dashboard")) {
    return navigateTo("/login");
  }
});
```

## User Profile Management

### Get Current User

```ts
const { data: session } = await authClient.getSession();
console.log(session.user);
```

### Update User Profile

```ts
await authClient.updateUser({
  name: "New Name",
  image: "https://example.com/new-avatar.jpg",
  // Custom fields if defined in schema
});
```

### Delete User Account

```ts
await authClient.deleteUser({
  password: "currentPassword", // Required for security
  callbackURL: "/" // Redirect after deletion
});
```

## Best Practices

1. **Password Security**: Enforce strong password requirements
2. **Email Verification**: Enable for production to prevent spam
3. **Rate Limiting**: Prevent brute force attacks (see advanced-features.md)
4. **HTTPS**: Always use HTTPS in production
5. **Error Messages**: Don't reveal if email exists during login
6. **Session Security**: Use secure, httpOnly cookies
7. **CSRF Protection**: Better Auth handles this automatically
8. **Password Reset**: Set short expiration for reset tokens
9. **Account Lockout**: Consider implementing after N failed attempts
10. **Audit Logs**: Track auth events for security monitoring
