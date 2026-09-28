---
name: hs:web-frameworks
injectable: true
description: Build with Next.js (App Router, RSC, SSR, ISR), Turborepo monorepos. Use for React apps, server rendering, build optimization, caching strategies, shared dependencies.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[framework] [feature]"
metadata:
  compliance-tier: workflow
---

# Web Frameworks Skill Group

Modern full-stack web apps with Next.js, Turborepo, RemixIcon.

## Overview

This skill group combines three powerful tools for web development:

**Next.js** - React framework with SSR, SSG, RSC, and optimization features
**Turborepo** - High-performance monorepo build system for JavaScript/TypeScript
**RemixIcon** - Icon library with 3,100+ outlined and filled style icons


## When to Use This Skill Group

- Building new full-stack web applications with modern React
- Setting up monorepos with multiple apps and shared packages
- Implementing server-side rendering and static generation
- Optimizing build performance with intelligent caching
- Creating consistent UI with professional iconography
- Managing workspace dependencies across multiple projects
- Deploying production-ready applications with proper optimization


## Stack Selection Guide

### Single Application: Next.js + RemixIcon

Use when building a standalone application:
- E-commerce sites
- Marketing websites
- SaaS applications
- Documentation sites
- Blogs and content platforms

**Setup:** see [`web-frameworks-playbook.md`](./references/web-frameworks-playbook.md) Quick Start → Next.js Application.

### Monorepo: Next.js + Turborepo + RemixIcon

Use when building multiple applications with shared code:
- Microfrontends
- Multi-tenant platforms
- Internal tools with shared component library
- Multiple apps (web, admin, mobile-web) sharing logic
- Design system with documentation site

**Setup:** see [`web-frameworks-playbook.md`](./references/web-frameworks-playbook.md) Quick Start → Turborepo Monorepo.

### Framework Features Comparison

| Feature | Next.js | Turborepo | RemixIcon |
|---------|---------|-----------|-----------|
| Primary Use | Web framework | Build system | UI icons |
| Best For | SSR/SSG apps | Monorepos | Consistent iconography |
| Performance | Built-in optimization | Caching & parallel tasks | Lightweight fonts/SVG |
| TypeScript | Full support | Full support | Type definitions available |


## Reference Navigation

**Next.js References:**
- [App Router Architecture](./references/nextjs-app-router.md) - Routing, layouts, pages, parallel routes
- [Server Components](./references/nextjs-server-components.md) - RSC patterns, client vs server, streaming
- [Data Fetching](./references/nextjs-data-fetching.md) - fetch API, caching, revalidation, loading states
- [Optimization](./references/nextjs-optimization.md) - Images, fonts, scripts, bundle analysis, PPR

**Turborepo References:**
- [Setup & Configuration](./references/turborepo-setup.md) - Installation, workspace config, package structure
- [Task Pipelines](./references/turborepo-pipelines.md) - Dependencies, parallel execution, task ordering
- [Caching Strategies](./references/turborepo-caching.md) - Local cache, remote cache, cache invalidation

**RemixIcon References:**
- [Integration Guide](./references/remix-icon-integration.md) - Installation, usage, customization, accessibility

- [`web-frameworks-playbook.md`](./references/web-frameworks-playbook.md) - Quick start, full-stack/monorepo patterns, best practices, implementation checklist

## Playbook

Quick Start (Next.js / Turborepo / RemixIcon setup), common full-stack & monorepo patterns, best practices, and the implementation checklist: [`web-frameworks-playbook.md`](./references/web-frameworks-playbook.md).

## Boundaries

Reference-catalog skill (stack selection + patterns), not a gated workflow — nothing enforced by hook/script; guidance, not MUST rules.

## Utility Scripts

Python utilities in `scripts/` directory:

**nextjs_init.py** - Initialize Next.js project with best practices
**turborepo_migrate.py** - Convert existing monorepo to Turborepo

Usage examples:
```bash
# Initialize new Next.js app with TypeScript and recommended setup
python scripts/nextjs_init.py my-app --tailwind

# Migrate existing monorepo to Turborepo with dry-run
python scripts/turborepo_migrate.py --path ./my-monorepo --dry-run

# Run tests
cd scripts/tests
pytest
```


## Resources

- Next.js: https://nextjs.org/docs/llms.txt
- Turborepo: https://turbo.build/repo/docs
- RemixIcon: https://remixicon.com

## Related skills

- `hs:deploy`: publish the built Next.js app (auto-detects Vercel/Netlify/Pages) — the next step after building.
