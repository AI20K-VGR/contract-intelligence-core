---
name: hs:shopify
injectable: true
description: Build Shopify apps, extensions, and themes with Shopify CLI, GraphQL Admin API, Polaris UI, Liquid, webhooks, billing, and app configuration workflows.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[extension-type] [feature]"
paths: ["**/*.liquid", "shopify.app.toml", "shopify.theme.toml"]
metadata:
  compliance-tier: workflow
---

# Shopify Development

Build Shopify apps, extensions, themes, API integrations — current Shopify CLI workflows + GraphQL-first Admin API guidance.

## Platform Overview

**Core Components:**
- **Shopify CLI** - Official app, extension, and theme workflow tool
- **GraphQL Admin API** - Default API for new app data operations
- **REST Admin API** - Legacy/migration-only for new development
- **Polaris UI** - Merchant-facing design system
- **Liquid** - Theme template language

New public apps created after 2025-04-01 must use the GraphQL Admin API. Use REST only for legacy maintenance or migration work.

**Extension Points:**
- Checkout UI - Customize checkout and thank-you surfaces
- Admin UI - Extend admin resource pages
- POS UI - Point of Sale customization
- Customer Account - Account and order status pages
- Theme App Extensions - Embedded storefront functionality
- Shopify Functions - Discount, delivery, payment, and validation logic


## Quick Start

### Prerequisites

```bash
npm install -g @shopify/cli@latest
shopify version
```

### App Workflow

```bash
# Create an app from official Shopify templates
shopify app init
cd my-app

# Link/select the app configuration used by this checkout
shopify app config link
shopify app config use

# Start local development against the selected config/store
shopify app dev

# Generate an extension (interactive picker selects the type)
shopify app generate extension

# Release Shopify-managed app config and extensions
shopify app deploy
```

`shopify app deploy` deploys Shopify-managed app configuration and extensions. Deploy your hosted web app/server separately on your hosting platform.

### Theme Workflow

```bash
shopify theme init
shopify theme dev
shopify theme pull --live
shopify theme push --development
```


## Workflow & Patterns

Development workflow (CLI scaffolding, dev/deploy cycle), essential implementation patterns, and troubleshooting: [`workflow-and-patterns.md`](references/workflow-and-patterns.md).

## When to Build What

### Build an App When
- Integrating external services
- Managing store data programmatically
- Building merchant-facing admin tools
- Implementing complex backend logic
- Charging for functionality

### Build an Extension When
- Customizing checkout, admin, POS, or customer-account surfaces
- Adding theme app blocks/snippets to storefronts
- Implementing Shopify Functions for discounts, delivery, payment, or validation

### Build a Theme When
- Creating or customizing storefront presentation
- Building product, collection, cart, or content page layouts
- Implementing brand-specific Liquid sections and snippets


## Official Docs

- Apps: https://shopify.dev/docs/apps
- GraphQL Admin API: https://shopify.dev/docs/api/admin-graphql
- Shopify CLI: https://shopify.dev/docs/api/shopify-cli
- Polaris (web components): https://shopify.dev/docs/api/app-home/polaris-web-components
- Themes & Liquid: https://shopify.dev/docs/themes · https://shopify.dev/docs/api/liquid
- Functions: https://shopify.dev/docs/apps/build/functions


## References

- `references/app-development.md` (+ `references/app-development-cont.md`) - GraphQL Admin API, webhooks, billing, metafields, rate limits
- `references/embedded-apps.md` - Embedded app auth: managed install, App Bridge v4, session tokens, token exchange, official libraries
- `references/extensions.md` (+ `references/extensions-cont.md`) - UI extensions (Preact + web components) and Shopify Functions
- `references/themes.md` (+ `references/themes-cont.md`) - Liquid theme development
- `scripts/shopify_init.py` - Thin wrapper around official Shopify CLI commands
- [`workflow-and-patterns.md`](references/workflow-and-patterns.md) - Development workflow, essential patterns, troubleshooting
