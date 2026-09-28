# Backend Authentication & Authorization (continued 2/2)

## API Key Authentication

### Best Practices

1. **Prefix keys** - `sk_live_`, `pk_test_` (identify type/environment)
2. **Hash stored keys** - Store SHA-256 hash, not plaintext
3. **Key rotation** - Allow users to rotate keys
4. **Scope limiting** - Separate keys for read/write operations
5. **Rate limiting** - Per API key limits

```typescript
// Generate API key
const apiKey = `sk_${env}_${crypto.randomBytes(24).toString('base64url')}`;

// Store hashed version
const hashedKey = crypto.createHash('sha256').update(apiKey).digest('hex');
await db.apiKeys.create({ userId, hashedKey, scopes: ['read'] });

// Validate API key
const providedHash = crypto.createHash('sha256').update(providedKey).digest('hex');
const keyRecord = await db.apiKeys.findOne({ hashedKey: providedHash });
```

## Authentication Decision Matrix

| Use Case | Recommended Approach |
|----------|---------------------|
| Web application | OAuth 2.1 + JWT |
| Mobile app | OAuth 2.1 + PKCE |
| SPA (Single Page App) | OAuth 2.1 Authorization Code + PKCE |
| Server-to-server | Client credentials grant + mTLS |
| Third-party API access | API keys with scopes |
| High-security | WebAuthn/FIDO2 + MFA |
| Internal admin | JWT + RBAC + MFA |
| Microservices | Service mesh (mTLS) + JWT |

## Security Checklist

- [ ] OAuth 2.1 with PKCE implemented
- [ ] JWT tokens expire in 15 minutes
- [ ] Refresh token rotation enabled
- [ ] RBAC with deny-by-default
- [ ] MFA required for admin accounts
- [ ] Passwords hashed with Argon2id
- [ ] Session cookies: HttpOnly, Secure, SameSite
- [ ] Rate limiting on auth endpoints (10 attempts/15 min)
- [ ] Account lockout after failed attempts
- [ ] Password policy: 12+ chars, breach check
- [ ] Audit logging for authentication events

## Resources

- **OAuth 2.1:** https://oauth.net/2.1/
- **JWT Best Practices:** https://datatracker.ietf.org/doc/html/rfc8725
- **WebAuthn:** https://webauthn.guide/
- **NIST Password Guidelines:** https://pages.nist.gov/800-63-3/
- **OWASP Auth Cheat Sheet:** https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
