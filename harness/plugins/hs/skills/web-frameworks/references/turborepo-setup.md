# Turborepo Setup & Configuration

Installation, workspace configuration, and project structure for monorepos.

## Installation

### Create New Monorepo

Using official starter:
```bash
npx create-turbo@latest my-monorepo
cd my-monorepo
```

Interactive prompts:
- Project name
- Package manager (npm, yarn, pnpm, bun)
- Example template

### Manual Installation

Install in existing project:
```bash
# npm
npm install turbo --save-dev

# yarn
yarn add turbo --dev

# pnpm
pnpm add turbo --save-dev

# bun
bun add turbo --dev
```

## Workspace Configuration

### Package Manager Setup

**pnpm (recommended):**
```yaml
# pnpm-workspace.yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

**npm/yarn:**
```json
// package.json (root)
{
  "name": "my-monorepo",
  "private": true,
  "workspaces": [
    "apps/*",
    "packages/*"
  ]
}
```

### Root Package.json

```json
{
  "name": "my-monorepo",
  "private": true,
  "workspaces": ["apps/*", "packages/*"],
  "scripts": {
    "build": "turbo run build",
    "dev": "turbo run dev",
    "lint": "turbo run lint",
    "test": "turbo run test",
    "clean": "turbo run clean"
  },
  "devDependencies": {
    "turbo": "latest",
    "typescript": "^5.0.0"
  },
  "packageManager": "pnpm@8.0.0"
}
```

## Project Structure

### Recommended Directory Structure

```
my-monorepo/
├── apps/                    # Applications
│   ├── web/                # Next.js web app
│   │   ├── app/
│   │   ├── package.json
│   │   └── next.config.js
│   ├── docs/               # Documentation site
│   │   ├── app/
│   │   └── package.json
│   └── api/                # Backend API
│       ├── src/
│       └── package.json
├── packages/               # Shared packages
│   ├── ui/                 # UI component library
│   │   ├── src/
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── config/             # Shared configs
│   │   ├── eslint/
│   │   └── typescript/
│   ├── utils/              # Utility functions
│   │   ├── src/
│   │   └── package.json
│   └── types/              # Shared TypeScript types
│       ├── src/
│       └── package.json
├── turbo.json              # Turborepo config
├── package.json            # Root package.json
├── pnpm-workspace.yaml     # Workspace config (pnpm)
└── .gitignore
```

## Application Package Setup

### Next.js App

```json
// apps/web/package.json
{
  "name": "web",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "@repo/ui": "*",
    "@repo/utils": "*",
    "next": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {
    "@repo/typescript-config": "*",
    "@repo/eslint-config": "*",
    "typescript": "^5.0.0"
  }
}
```

### Backend API App

```json
// apps/api/package.json
{
  "name": "api",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsup src/index.ts",
    "start": "node dist/index.js",
    "lint": "eslint src/"
  },
  "dependencies": {
    "@repo/utils": "*",
    "@repo/types": "*",
    "express": "^4.18.0"
  },
  "devDependencies": {
    "@repo/typescript-config": "*",
    "@types/express": "^4.17.0",
    "tsx": "^4.0.0",
    "tsup": "^8.0.0"
  }
}
```

## Shared Package Setup

### UI Component Library

```json
// packages/ui/package.json
{
  "name": "@repo/ui",
  "version": "0.0.0",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    },
    "./button": {
      "types": "./dist/button.d.ts",
      "default": "./dist/button.js"
    }
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "lint": "eslint src/",
    "clean": "rm -rf dist"
  },
  "dependencies": {
    "react": "latest"
  },
  "devDependencies": {
    "@repo/typescript-config": "*",
    "typescript": "^5.0.0"
  }
}
```

```json
// packages/ui/tsconfig.json
{
  "extends": "@repo/typescript-config/react-library.json",
  "compilerOptions": {
    "outDir": "dist",
    "declarationDir": "dist"
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

### Utility Library

```json
// packages/utils/package.json
{
  "name": "@repo/utils",
  "version": "0.0.0",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "test": "jest"
  },
  "devDependencies": {
    "@repo/typescript-config": "*",
    "jest": "^29.0.0",
    "typescript": "^5.0.0"
  }
}
```


---

Continued in [turborepo-setup-cont.md](turborepo-setup-cont.md)
