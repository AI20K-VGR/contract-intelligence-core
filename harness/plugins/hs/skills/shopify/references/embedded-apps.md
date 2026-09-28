# Embedded Apps Reference

Guide: authenticating embedded Shopify apps. **Library-first:** use the official Shopify app libraries — do NOT hand-roll OAuth, HMAC validation, or token exchange. The libraries handle managed installation, session-token validation, and token exchange correctly.

## Managed Installation

New embedded apps install via Shopify-managed installation, driven by `[access_scopes]` in `shopify.app.toml`. Shopify renders the install/permission UI, grants scopes — no manual `/admin/oauth/authorize` redirect or authorization-code-grant flow.

```toml
[access_scopes]
scopes = "read_products,write_products,read_orders"
```

Change scopes in config and redeploy; Shopify prompts the merchant to approve scope changes.

## App Bridge v4

Embedded apps load App Bridge v4 from Shopify's CDN. Add this to your app's HTML `<head>` (the script tag is unavoidable markup):

```html
<meta name="shopify-api-key" content="%SHOPIFY_API_KEY%" />
<script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
```

App Bridge v4 auto-configures from the meta tag and automatically attaches a session token to same-origin `fetch` requests from your embedded frontend.

## Session Token Auth

Embedded apps authenticate requests to their own backend with short-lived session tokens (JWTs, ~1 minute lifetime). With App Bridge v4 the token is attached to same-origin requests automatically — so a plain `fetch` to your own backend already carries the `Authorization` header:

```javascript
// In the embedded frontend — App Bridge v4 attaches the session token.
const res = await fetch('/api/orders');
```

If you need the token explicitly (e.g. for a cross-origin request), retrieve it via the App Bridge session-token utility documented at the link below. Validate the token on the backend with `@shopify/shopify-api` (verifies JWT signature, audience, expiry). Never trust an unverified token.

## Token Exchange

To call the Admin API, exchange a validated session token for an access token. This replaces the legacy authorization-code-grant flow. The official libraries do this automatically — you rarely call it by hand. Conceptually:

```text
POST https://{shop}.myshopify.com/admin/oauth/access_token
grant_type         = urn:ietf:params:oauth:grant-type:token-exchange
subject_token      = <session token JWT>
subject_token_type = urn:ietf:params:oauth:token-type:id_token
```

`{shop}` is the bare store handle; the full host is `{shop}.myshopify.com`. Request an online or offline token via the requested token type. Let the library manage exchange, storage, and refresh.

## Official Libraries

Use an official library instead of hand-rolling auth:

- **`@shopify/shopify-app-react-router`** — recommended for new apps (2026+, React Router v7+). Handles managed install, session tokens, and token exchange.
- **`@shopify/shopify-app-remix`** — still supported; use for existing Remix apps.
- **`@shopify/shopify-api`** — the core library. Validates session tokens and performs token exchange; used directly for non-Remix/React-Router backends.

## Expiring Offline Access Tokens

Shopify is moving offline access tokens to expiring tokens (60-minute access token + 90-day refresh token):

- **2026-04-01** — new public apps MUST use expiring offline tokens.
- **2027-01-01** — ALL public apps must use expiring offline tokens or lose API access.

Opt in by requesting expiring tokens (`expiring=1`) during token exchange — a one-time, irreversible migration per app. The official libraries refresh expiring tokens automatically via token exchange; plan for refresh if you manage tokens yourself.

## Resources

- App installation: https://shopify.dev/docs/apps/build/authentication-authorization/app-installation
- Session tokens: https://shopify.dev/docs/apps/build/authentication-authorization/session-tokens
- Token exchange: https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/token-exchange
- App libraries (React Router / Remix): https://shopify.dev/docs/api/shopify-app-remix
- Expiring offline tokens (new apps, 2026-04-01): https://shopify.dev/changelog/expiring-offline-access-tokens-required-for-new-public-apps-april-1-2026
- Expiring offline tokens (all apps, 2027-01-01): https://shopify.dev/changelog/expiring-offline-access-tokens-required-for-all-public-apps-as-of-january-1-2027
