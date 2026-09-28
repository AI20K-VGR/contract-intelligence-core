---
name: hs:payment-integration
injectable: true
description: Integrate payments with SePay (VietQR), Polar, Stripe, Paddle (MoR subscriptions), Creem.io (licensing). Checkout, webhooks, subscriptions, QR codes, multi-provider orders.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[provider] [task]"
metadata:
  compliance-tier: workflow
---

# Payment Integration

Production-proven: SePay (Vietnamese banks), Polar (global SaaS), Stripe (global infrastructure), Paddle (MoR subscriptions), Creem.io (MoR + licensing).

## When to Use

- Payment gateway integration (checkout, processing)
- Subscription management (trials, upgrades, billing)
- Webhook handling (notifications, idempotency)
- QR code payments (VietQR, NAPAS)
- Software licensing (device activation)
- Multi-provider order management
- Revenue splits and commissions

## Platform Selection

| Platform | Best For |
|----------|----------|
| **SePay** | Vietnamese market, VND, bank transfers, VietQR |
| **Polar** | Global SaaS, subscriptions, automated benefits (GitHub/Discord) |
| **Stripe** | Enterprise payments, Connect platforms, custom checkout |
| **Paddle** | MoR subscriptions, global tax compliance, churn prevention |
| **Creem.io** | MoR + licensing, revenue splits, no-code checkout |

## Quick Reference

### SePay
- `references/sepay/overview.md` - Auth, supported banks
- `references/sepay/api.md` - Endpoints, transactions
- `references/sepay/webhooks.md` - Setup, verification
- `references/sepay/sdk.md` - Node.js, PHP, Laravel
- `references/sepay/qr-codes.md` - VietQR generation
- `references/sepay/best-practices.md` - Production patterns (env, transaction format, QR, checkout API, webhooks); continued in `best-practices-flows.md` (matching, processing, currency, invoice email) and `best-practices-advanced.md` (error handling, testing, schema, production checklist, pitfalls)

### Polar
- `references/polar/overview.md` - Auth, MoR concept
- `references/polar/products.md` - Pricing models
- `references/polar/checkouts.md` - Checkout flows
- `references/polar/subscriptions.md` - Lifecycle management
- `references/polar/webhooks.md` - Event handling
- `references/polar/benefits.md` - Automated delivery
- `references/polar/sdk.md` - Multi-language SDKs
- `references/polar/best-practices.md` - Production patterns (env, checkout flow, webhooks, fees); continued in `best-practices-advanced.md` (discounts, revenue tracking, error handling, schema, metadata, testing, production checklist, pitfalls)

### Stripe
- `references/stripe/stripe-best-practices.md` - Integration design
- `references/stripe/stripe-sdks.md` - Server SDKs
- `references/stripe/stripe-js.md` - Payment Element
- `references/stripe/stripe-cli.md` - Local testing
- `references/stripe/stripe-upgrade.md` - Version upgrades
- External: https://docs.stripe.com/llms.txt

### Paddle
- `references/paddle/overview.md` - MoR, auth, entity IDs
- `references/paddle/api.md` - Products, prices, transactions
- `references/paddle/paddle-js.md` - Checkout overlay/inline
- `references/paddle/subscriptions.md` - Trials, upgrades, pause
- `references/paddle/webhooks.md` - SHA256 verification
- `references/paddle/sdk.md` - Node, Python, PHP, Go
- `references/paddle/best-practices.md` - Production patterns
- External: https://developer.paddle.com/llms.txt

### Creem.io
- `references/creem/overview.md` - MoR, auth, global support
- `references/creem/api.md` - Products, checkout sessions
- `references/creem/checkouts.md` - No-code links, storefronts
- `references/creem/subscriptions.md` - Trials, seat-based
- `references/creem/licensing.md` - Device activation
- `references/creem/webhooks.md` - Signature verification
- `references/creem/sdk.md` - Next.js, Better Auth
- External: https://docs.creem.io/llms.txt

### Multi-Provider
- `references/multi-provider-order-management-patterns.md` - Unified orders, currency conversion

### Scripts
- `scripts/sepay-webhook-verify.js` - SePay webhook verification
- `scripts/polar-webhook-verify.js` - Polar webhook verification
- `scripts/checkout-helper.js` - Checkout session generator (SePay/Polar only)

## Key Capabilities

| Platform | Highlights |
|----------|------------|
| **SePay** | QR/bank/cards, 44+ VN banks, webhooks, 2 req/s |
| **Polar** | MoR, subscriptions, usage billing, benefits, 300 req/min |
| **Stripe** | CheckoutSessions, Billing, Connect, Payment Element |
| **Paddle** | MoR, overlay/inline checkout, Retain (churn prevention), tax |
| **Creem.io** | MoR, licensing, revenue splits, no-code checkout |

## Implementation

See `references/implementation-workflows.md` for step-by-step guides per platform.

**General flow:** auth → products → checkout → webhooks → events

## Boundaries

- **MUST** verify webhook signatures via `scripts/sepay-webhook-verify.js` / `scripts/polar-webhook-verify.js` (or the equivalent per-platform SDK verifier for Stripe/Paddle/Creem.io — see each platform's `webhooks.md`) before processing any webhook payload. A spoofed/replayed webhook moves real money on a fake event — this is safety-critical, not optional hardening.
- **MUST** apply idempotency (dedupe on the provider's event id, record-before-process) per the pattern in each platform's `best-practices.md` — a retried/duplicate webhook must not double-apply the same event.

## Related skills

- `hs:scenario --domain business`: **before** testing a payment flow, enumerate the business-logic (money) edge cases `hs:security-scan` does **not** cover — double-charge, coupon-stack, refund edge, retry-storm, webhook-replay — and feed them into your test checklist. Pre-test enumeration; complements the security follow-on below.
- `hs:security-scan`: run after integrating payment (webhook signature / idempotency / secret handling) — verify-only, non-blocking.
