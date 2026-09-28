---
name: hs:better-auth
injectable: true
description: Add authentication with Better Auth (TypeScript). Use for email/password, OAuth providers (Google, GitHub), 2FA/MFA, passkeys/WebAuthn, sessions, RBAC, rate limiting.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[auth-method or feature]"
metadata:
  compliance-tier: workflow
---

# Better Auth Skill

Better Auth: framework-agnostic TypeScript auth/authz framework — built-in email/password, social OAuth, plugin ecosystem for advanced features.

## When to Use

- Implementing auth in TypeScript/JavaScript applications
- Adding email/password or social OAuth authentication
- Setting up 2FA, passkeys, magic links, advanced auth features
- Building multi-tenant apps with organization support
- Managing sessions and user lifecycle
- Working with any framework (Next.js, Nuxt, SvelteKit, Remix, Astro, Hono, Express, etc.)

## Quick Start

Installation, env setup, server+client setup, DB schema, API handler mount, basic usage: [`getting-started.md`](./references/getting-started.md).

## Feature Selection Matrix

| Feature | Plugin Required | Use Case | Reference |
|---------|----------------|----------|-----------|
| Email/Password | No (built-in) | Basic auth | [email-password-auth.md](./references/email-password-auth.md) |
| OAuth (GitHub, Google, etc.) | No (built-in) | Social login | [oauth-providers.md](./references/oauth-providers.md) |
| Email Verification | No (built-in) | Verify email addresses | [email-password-auth.md](./references/email-password-auth.md#email-verification) |
| Password Reset | No (built-in) | Forgot password flow | [email-password-auth.md](./references/email-password-auth.md#password-reset) |
| Two-Factor Auth (2FA/TOTP) | Yes (`twoFactor`) | Enhanced security | [advanced-features.md](./references/advanced-features.md#two-factor-authentication) |
| Passkeys/WebAuthn | Yes (`passkey`) | Passwordless auth | [advanced-features.md](./references/advanced-features.md#passkeys-webauthn) |
| Magic Link | Yes (`magicLink`) | Email-based login | [advanced-features.md](./references/advanced-features.md#magic-link) |
| Username Auth | Yes (`username`) | Username login | [email-password-auth.md](./references/email-password-auth.md#username-authentication) |
| Organizations/Multi-tenant | Yes (`organization`) | Team/org features | [advanced-features-cont.md](./references/advanced-features-cont.md#organizations-multi-tenancy) |
| Rate Limiting | No (built-in) | Prevent abuse | [advanced-features-cont.md](./references/advanced-features-cont.md#rate-limiting) |
| Session Management | No (built-in) | User sessions | [advanced-features-cont.md](./references/advanced-features-cont.md#session-management) |

## Auth Method Selection Guide

**Choose Email/Password when:**
- Building standard web app with traditional auth
- Need full control over user credentials
- Targeting users who prefer email-based accounts

**Choose OAuth when:**
- Want quick signup with minimal friction
- Users already have social accounts
- Need access to social profile data

**Choose Passkeys when:**
- Want passwordless experience
- Targeting modern browsers/devices
- Security is top priority

**Choose Magic Link when:**
- Want passwordless without WebAuthn complexity
- Targeting email-first users
- Need temporary access links

**Combine Multiple Methods when:**
- Want flexibility for different user preferences
- Building enterprise apps with various auth requirements
- Need progressive enhancement (start simple, add more options)

## Core Architecture

Client-server architecture:
1. **Server** (`better-auth`): Handles auth logic, database ops, API routes
2. **Client** (`better-auth/client`): Provides hooks/methods for frontend
3. **Plugins**: Extend both server/client functionality

## Implementation Checklist

- [ ] Install `better-auth` package
- [ ] Set environment variables (SECRET, URL)
- [ ] Create auth server instance with database config
- [ ] Run schema migration (`npx @better-auth/cli generate`)
- [ ] Mount API handler in framework
- [ ] Create client instance
- [ ] Implement sign-up/sign-in UI
- [ ] Add session management to components
- [ ] Set up protected routes/middleware
- [ ] Add plugins as needed (regenerate schema after)
- [ ] Test complete auth flow
- [ ] Configure email sending (verification/reset)
- [ ] Enable rate limiting for production
- [ ] Set up error handling

## Current Security Notes

Recent Better Auth releases tightened several security-sensitive plugin paths. When enabling these features, verify the installed version includes the current fixes and keep the default safer settings unless the app has an explicit threat-model exception:

- `oidc-provider` and `mcp` plugins: confidential clients must require `client_secret` on refresh-token grants; use constant-time secret comparison and reject incomplete PKCE parameters.
- `magicLink`: verification tokens are single-use; avoid custom flows that mint multiple sessions from concurrent requests.
- Organizations/invitations: keep `requireEmailVerificationOnInvitation` enabled so unverified email ownership cannot accept or enumerate invitations.
- Device authorization: bind pending device codes to the verifying session so one authenticated user cannot approve another user's device flow.

## Related skills

- `hs:scenario --domain security`: **before** writing auth tests, decompose the flow across edge dimensions (token expiry, privilege escalation, concurrent sessions, provider-down) to seed the "Test complete auth flow" checklist item with real cases — pre-test enumeration, distinct from the security audit below.
- `hs:security-scan`: run after wiring auth (RBAC/MFA/sessions/secret handling) over the surface you just added — a security check, not a blocking gate.

## Reference Documentation

### Core Authentication
- [Getting Started](./references/getting-started.md) - Installation, env setup, server/client setup, database schema, API handler, basic usage
- [Email/Password Authentication](./references/email-password-auth.md) - Email/password setup, verification, password reset, username auth
- [Email/Password Authentication (cont.)](./references/email-password-auth-cont.md) - Framework setup (Next.js, Nuxt, SvelteKit, Astro, Hono, Express), protected routes
- [OAuth Providers](./references/oauth-providers.md) - Social login setup, provider configuration, token management
- [OAuth Providers (cont.)](./references/oauth-providers-cont.md) - Custom scopes, state parameter, PKCE, error handling, callback URLs
- [Database Integration](./references/database-integration.md) - Database adapters, schema setup, migrations
- [Database Integration (cont.)](./references/database-integration-cont.md) - Schema generation CLI, auto-migrate, custom fields, plugin schema extensions
- [Database Integration (cont. 2)](./references/database-integration-cont2.md) - Troubleshooting: connection errors, schema mismatch, migration/performance issues

### Advanced Features
- [Advanced Features](./references/advanced-features.md) - 2FA/MFA, passkeys, magic links, organizations, rate limiting, session management
- [Advanced Features (cont.)](./references/advanced-features-cont.md) - Organizations/multi-tenancy, rate limiting, session management
- [Advanced Features (cont. 2)](./references/advanced-features-cont2.md) - Email OTP, phone number auth, best practices, schema regen after plugins

## Scripts

- `scripts/better_auth_init.py` - Initialize Better Auth configuration with interactive setup

## Resources

- Docs: https://www.better-auth.com/docs
- GitHub: https://github.com/better-auth/better-auth
- Plugins: https://www.better-auth.com/docs/plugins
- Examples: https://www.better-auth.com/docs/examples
