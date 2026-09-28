# OAuth Providers (continued 2/2)

## Advanced OAuth Configuration

### Custom Scopes

```ts
export const auth = betterAuth({
  socialProviders: {
    github: {
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
      scope: [
        "user:email",
        "read:user",
        "repo", // Access repositories
        "gist" // Access gists
      ]
    }
  }
});
```

### State Parameter

Auto-handles OAuth state param (CSRF protection).

```ts
// Custom state validation
export const auth = betterAuth({
  advanced: {
    generateState: async () => {
      // Custom state generation
      return crypto.randomUUID();
    },
    validateState: async (state: string) => {
      // Custom state validation
      return true;
    }
  }
});
```

### PKCE Support

Auto-uses PKCE (Proof Key for Code Exchange) for supported providers.

```ts
export const auth = betterAuth({
  socialProviders: {
    customProvider: {
      pkce: true, // Enable PKCE
      // ... other config
    }
  }
});
```

## Error Handling

### Client-Side

```ts
await authClient.signIn.social({
  provider: "github",
  errorCallbackURL: "/auth/error"
}, {
  onError: (ctx) => {
    console.error("OAuth error:", ctx.error);
    // Handle specific errors
    if (ctx.error.code === "OAUTH_ACCOUNT_ALREADY_LINKED") {
      alert("This account is already linked to another user");
    }
  }
});
```

### Server-Side

```ts
export const auth = betterAuth({
  callbacks: {
    async onOAuthError({ error, provider }) {
      console.error(`OAuth error with ${provider}:`, error);
      // Log to monitoring service
      await logError(error);
    }
  }
});
```

## Callback URLs

### Development

```
http://localhost:3000/api/auth/callback/{provider}
```

### Production

```
https://yourdomain.com/api/auth/callback/{provider}
```

**Important:** Add all callback URLs to OAuth provider settings.

## UI Components

### Sign In Button (React)

```tsx
import { authClient } from "@/lib/auth-client";

export function SocialSignIn() {
  const handleOAuth = async (provider: string) => {
    await authClient.signIn.social({
      provider,
      callbackURL: "/dashboard"
    });
  };

  return (
    <div className="space-y-2">
      <button onClick={() => handleOAuth("github")}>
        Sign in with GitHub
      </button>
      <button onClick={() => handleOAuth("google")}>
        Sign in with Google
      </button>
      <button onClick={() => handleOAuth("discord")}>
        Sign in with Discord
      </button>
    </div>
  );
}
```

## Best Practices

1. **Callback URLs**: Add all environments (dev, staging, prod) to OAuth app
2. **Scopes**: Request minimum scopes needed
3. **Token Storage**: Better Auth stores tokens securely in database
4. **Token Refresh**: Implement automatic token refresh for long-lived sessions
5. **Account Linking**: Enable for better UX when user signs in with different providers
6. **Error Handling**: Provide clear error messages for OAuth failures
7. **Provider Icons**: Use official brand assets for OAuth buttons
8. **Mobile Deep Links**: Configure deep links for mobile OAuth flows
9. **Email Matching**: Consider auto-linking accounts with same email
10. **Privacy**: Inform users what data you access from OAuth providers

## Common Issues

### Redirect URI Mismatch

Ensure callback URL in OAuth app matches exactly:
```
http://localhost:3000/api/auth/callback/github
```

### Missing Scopes

Add required scopes for email access:
```ts
scope: ["user:email"] // GitHub
scope: ["email"] // Google
```

### HTTPS Required

Some providers (Apple, Microsoft) require HTTPS callbacks. Use ngrok for local development:
```bash
ngrok http 3000
```

### CORS Errors

Configure CORS if frontend/backend on different domains:
```ts
export const auth = betterAuth({
  advanced: {
    corsOptions: {
      origin: ["https://yourdomain.com"],
      credentials: true
    }
  }
});
```
