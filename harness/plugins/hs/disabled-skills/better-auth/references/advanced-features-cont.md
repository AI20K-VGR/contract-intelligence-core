# Advanced Features (continued 2/3)

## Organizations (Multi-Tenancy)

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { organization } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    organization({
      allowUserToCreateOrganization: true,
      organizationLimit: 5, // Max orgs per user
      creatorRole: "owner" // Role for org creator
    })
  ]
});
```

### Client Setup

```ts
import { createAuthClient } from "better-auth/client";
import { organizationClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [organizationClient()]
});
```

### Create Organization

```ts
await authClient.organization.create({
  name: "Acme Corp",
  slug: "acme", // Unique slug
  metadata: {
    industry: "Technology"
  }
});
```

### Invite Members

```ts
await authClient.organization.inviteMember({
  organizationId: "org-id",
  email: "user@example.com",
  role: "member", // owner, admin, member
  message: "Join our team!" // Optional
});
```

### Accept Invitation

```ts
await authClient.organization.acceptInvitation({
  invitationId: "invitation-id"
});
```

### List Organizations

```ts
const { data } = await authClient.organization.list();
// Returns user's organizations
```

### Update Member Role

```ts
await authClient.organization.updateMemberRole({
  organizationId: "org-id",
  userId: "user-id",
  role: "admin"
});
```

### Remove Member

```ts
await authClient.organization.removeMember({
  organizationId: "org-id",
  userId: "user-id"
});
```

### Delete Organization

```ts
await authClient.organization.delete({
  organizationId: "org-id"
});
```

## Session Management

### Configure Session Expiration

```ts
export const auth = betterAuth({
  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days (seconds)
    updateAge: 60 * 60 * 24, // Update session every 24 hours
    cookieCache: {
      enabled: true,
      maxAge: 5 * 60 // Cache for 5 minutes
    }
  }
});
```

### Server-Side Session

```ts
// Next.js
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

const session = await auth.api.getSession({
  headers: await headers()
});

if (!session) {
  // Not authenticated
}
```

### Client-Side Session

```tsx
// React
import { authClient } from "@/lib/auth-client";

function UserProfile() {
  const { data: session, isPending, error } = authClient.useSession();

  if (isPending) return <div>Loading...</div>;
  if (error) return <div>Error</div>;
  if (!session) return <div>Not logged in</div>;

  return <div>Hello, {session.user.name}!</div>;
}
```

### List Active Sessions

```ts
const { data: sessions } = await authClient.listSessions();
// Returns all active sessions for current user
```

### Revoke Session

```ts
await authClient.revokeSession({
  sessionId: "session-id"
});
```

### Revoke All Sessions

```ts
await authClient.revokeAllSessions();
```

## Rate Limiting

### Server Configuration

```ts
export const auth = betterAuth({
  rateLimit: {
    enabled: true,
    window: 60, // Time window in seconds
    max: 10, // Max requests per window
    storage: "memory", // "memory" or "database"
    customRules: {
      "/api/auth/sign-in": {
        window: 60,
        max: 5 // Stricter limit for sign-in
      },
      "/api/auth/sign-up": {
        window: 3600,
        max: 3 // 3 signups per hour
      }
    }
  }
});
```

### Custom Rate Limiter

```ts
import { betterAuth } from "better-auth";

export const auth = betterAuth({
  rateLimit: {
    enabled: true,
    customLimiter: async ({ request, limit }) => {
      // Custom rate limiting logic
      const ip = request.headers.get("x-forwarded-for");
      const key = `ratelimit:${ip}`;

      // Use Redis, etc.
      const count = await redis.incr(key);
      if (count === 1) {
        await redis.expire(key, limit.window);
      }

      if (count > limit.max) {
        throw new Error("Rate limit exceeded");
      }
    }
  }
});
```

## Anonymous Sessions

Track users before they sign up.

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { anonymous } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [anonymous()]
});
```

### Client Usage

```ts
// Create anonymous session
const { data } = await authClient.signIn.anonymous();

// Convert to full account
await authClient.signUp.email({
  email: "user@example.com",
  password: "password123",
  linkAnonymousSession: true // Link anonymous data
});
```


---

Continued in [advanced-features-cont2.md](advanced-features-cont2.md)
