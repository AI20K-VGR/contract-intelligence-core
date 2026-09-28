# Advanced Features

Plugins extend functionality beyond basic auth.

## Two-Factor Authentication

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { twoFactor } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    twoFactor({
      issuer: "YourAppName", // TOTP issuer name
      otpOptions: {
        period: 30, // OTP validity period (seconds)
        digits: 6, // OTP length
      }
    })
  ]
});
```

### Client Setup

```ts
import { createAuthClient } from "better-auth/client";
import { twoFactorClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [
    twoFactorClient({
      twoFactorPage: "/two-factor", // Redirect to 2FA verification page
      redirect: true // Auto-redirect if 2FA required
    })
  ]
});
```

### Enable 2FA for User

```ts
// Enable TOTP
const { data } = await authClient.twoFactor.enable({
  password: "userPassword" // Verify user identity
});

// data contains QR code URI for authenticator app
const qrCodeUri = data.totpURI;
const backupCodes = data.backupCodes; // Save these securely
```

### Verify TOTP Code

```ts
await authClient.twoFactor.verifyTOTP({
  code: "123456",
  trustDevice: true // Skip 2FA on this device for 30 days
});
```

### Disable 2FA

```ts
await authClient.twoFactor.disable({
  password: "userPassword"
});
```

### Backup Codes

```ts
// Generate new backup codes
const { data } = await authClient.twoFactor.generateBackupCodes({
  password: "userPassword"
});

// Use backup code instead of TOTP
await authClient.twoFactor.verifyBackupCode({
  code: "backup-code-123"
});
```

## Passkeys (WebAuthn)

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { passkey } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    passkey({
      rpName: "YourApp", // Relying Party name
      rpID: "yourdomain.com" // Your domain
    })
  ]
});
```

### Client Setup

```ts
import { createAuthClient } from "better-auth/client";
import { passkeyClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [passkeyClient()]
});
```

### Register Passkey

```ts
// User must be authenticated first
await authClient.passkey.register({
  name: "My Laptop" // Optional: name for this passkey
});
```

### Sign In with Passkey

```ts
await authClient.passkey.signIn();
```

### List User Passkeys

```ts
const { data } = await authClient.passkey.list();
// data contains array of registered passkeys
```

### Delete Passkey

```ts
await authClient.passkey.delete({
  id: "passkey-id"
});
```

## Magic Link

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { magicLink } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    magicLink({
      sendMagicLink: async ({ email, url, token }) => {
        await sendEmail({
          to: email,
          subject: "Sign in to YourApp",
          html: `Click <a href="${url}">here</a> to sign in.`
        });
      },
      expiresIn: 300, // Link expires in 5 minutes (seconds)
    })
  ]
});
```

### Client Setup

```ts
import { createAuthClient } from "better-auth/client";
import { magicLinkClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [magicLinkClient()]
});
```

### Send Magic Link

```ts
await authClient.magicLink.sendMagicLink({
  email: "user@example.com",
  callbackURL: "/dashboard"
});
```

### Verify Magic Link

```ts
// Called automatically when user clicks link
// Token in URL query params handled by Better Auth
await authClient.magicLink.verify({
  token: "token-from-url"
});
```


---

Continued in [advanced-features-cont.md](advanced-features-cont.md)
