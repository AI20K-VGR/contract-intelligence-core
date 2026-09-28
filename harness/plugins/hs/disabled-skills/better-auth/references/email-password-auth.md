# Email/Password Authentication

Email/password: built-in auth method. No plugins required.

## Server Configuration

### Basic Setup

```ts
import { betterAuth } from "better-auth";

export const auth = betterAuth({
  emailAndPassword: {
    enabled: true,
    autoSignIn: true, // Auto sign-in after signup (default: true)
    requireEmailVerification: false, // Require email verification before login
    sendResetPasswordToken: async ({ user, url }) => {
      // Send password reset email
      await sendEmail(user.email, url);
    }
  }
});
```

### Custom Password Requirements

```ts
export const auth = betterAuth({
  emailAndPassword: {
    enabled: true,
    password: {
      minLength: 8,
      requireUppercase: true,
      requireLowercase: true,
      requireNumbers: true,
      requireSpecialChars: true
    }
  }
});
```

## Client Usage

### Sign Up

```ts
import { authClient } from "@/lib/auth-client";

const { data, error } = await authClient.signUp.email({
  email: "user@example.com",
  password: "securePassword123",
  name: "John Doe",
  image: "https://example.com/avatar.jpg", // optional
  callbackURL: "/dashboard" // optional
}, {
  onSuccess: (ctx) => {
    // ctx.data contains user and session
    console.log("User created:", ctx.data.user);
  },
  onError: (ctx) => {
    alert(ctx.error.message);
  }
});
```

### Sign In

```ts
const { data, error } = await authClient.signIn.email({
  email: "user@example.com",
  password: "securePassword123",
  callbackURL: "/dashboard",
  rememberMe: true // default: true
}, {
  onSuccess: () => {
    // redirect or update UI
  },
  onError: (ctx) => {
    console.error(ctx.error.message);
  }
});
```

### Sign Out

```ts
await authClient.signOut({
  fetchOptions: {
    onSuccess: () => {
      router.push("/login");
    }
  }
});
```

## Email Verification

### Server Setup

```ts
export const auth = betterAuth({
  emailVerification: {
    sendVerificationEmail: async ({ user, url, token }) => {
      // Send verification email
      await sendEmail({
        to: user.email,
        subject: "Verify your email",
        html: `Click <a href="${url}">here</a> to verify your email.`
      });
    },
    sendOnSignUp: true, // Send verification email on signup
    autoSignInAfterVerification: true // Auto sign-in after verification
  },
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true // Require verification before login
  }
});
```

### Client Usage

```ts
// Send verification email
await authClient.sendVerificationEmail({
  email: "user@example.com",
  callbackURL: "/verify-success"
});

// Verify email with token
await authClient.verifyEmail({
  token: "verification-token-from-email"
});
```

## Password Reset Flow

### Server Setup

```ts
export const auth = betterAuth({
  emailAndPassword: {
    enabled: true,
    sendResetPasswordToken: async ({ user, url, token }) => {
      await sendEmail({
        to: user.email,
        subject: "Reset your password",
        html: `Click <a href="${url}">here</a> to reset your password.`
      });
    }
  }
});
```

### Client Flow

```ts
// Step 1: Request password reset
await authClient.forgetPassword({
  email: "user@example.com",
  redirectTo: "/reset-password"
});

// Step 2: Reset password with token
await authClient.resetPassword({
  token: "reset-token-from-email",
  password: "newSecurePassword123"
});
```

### Change Password (Authenticated)

```ts
await authClient.changePassword({
  currentPassword: "oldPassword123",
  newPassword: "newPassword456",
  revokeOtherSessions: true // Optional: logout other sessions
});
```

## Username Authentication

Requires `username` plugin.

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { username } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    username({
      // Allow sign in with username or email
      allowUsernameOrEmail: true
    })
  ]
});
```

### Client Setup

```ts
import { createAuthClient } from "better-auth/client";
import { usernameClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [usernameClient()]
});
```

### Client Usage

```ts
// Sign up with username
await authClient.signUp.username({
  username: "johndoe",
  password: "securePassword123",
  email: "john@example.com", // optional
  name: "John Doe"
});

// Sign in with username
await authClient.signIn.username({
  username: "johndoe",
  password: "securePassword123"
});

// Sign in with username or email (if allowUsernameOrEmail: true)
await authClient.signIn.username({
  username: "johndoe", // or "john@example.com"
  password: "securePassword123"
});
```


---

Continued in [email-password-auth-cont.md](email-password-auth-cont.md)
