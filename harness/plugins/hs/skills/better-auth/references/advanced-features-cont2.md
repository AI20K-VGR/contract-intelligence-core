# Advanced Features (continued 3/3)

## Email OTP

One-time password via email (passwordless).

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { emailOTP } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    emailOTP({
      sendVerificationOTP: async ({ email, otp }) => {
        await sendEmail({
          to: email,
          subject: "Your verification code",
          text: `Your code is: ${otp}`
        });
      },
      expiresIn: 300, // 5 minutes
      length: 6 // OTP length
    })
  ]
});
```

### Client Usage

```ts
// Send OTP to email
await authClient.emailOTP.sendOTP({
  email: "user@example.com"
});

// Verify OTP
await authClient.emailOTP.verifyOTP({
  email: "user@example.com",
  otp: "123456"
});
```

## Phone Number Authentication

Requires phone number plugin.

### Server Setup

```ts
import { betterAuth } from "better-auth";
import { phoneNumber } from "better-auth/plugins";

export const auth = betterAuth({
  plugins: [
    phoneNumber({
      sendOTP: async ({ phoneNumber, otp }) => {
        // Use Twilio, AWS SNS, etc.
        await sendSMS(phoneNumber, `Your code: ${otp}`);
      }
    })
  ]
});
```

### Client Usage

```ts
// Sign up with phone
await authClient.signUp.phoneNumber({
  phoneNumber: "+1234567890",
  password: "password123"
});

// Send OTP
await authClient.phoneNumber.sendOTP({
  phoneNumber: "+1234567890"
});

// Verify OTP
await authClient.phoneNumber.verifyOTP({
  phoneNumber: "+1234567890",
  otp: "123456"
});
```

## Best Practices

1. **2FA**: Offer 2FA as optional, make mandatory for admin users
2. **Passkeys**: Implement as progressive enhancement (fallback to password)
3. **Magic Links**: Set short expiration (5-15 minutes)
4. **Organizations**: Implement RBAC for org permissions
5. **Sessions**: Use short expiration for sensitive apps
6. **Rate Limiting**: Enable in production, adjust limits based on usage
7. **Anonymous Sessions**: Clean up old anonymous sessions periodically
8. **Backup Codes**: Force users to save backup codes before enabling 2FA
9. **Multi-Device**: Allow users to manage trusted devices
10. **Audit Logs**: Track sensitive operations (role changes, 2FA changes)

## Regenerate Schema After Plugins

After adding any plugin:

```bash
npx @better-auth/cli generate
npx @better-auth/cli migrate # if using Kysely
```

Or manually apply migrations for your ORM (Drizzle, Prisma).
