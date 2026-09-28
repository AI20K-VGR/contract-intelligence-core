# Turborepo Setup & Configuration (continued 2/3)

## Shared Configuration Packages

### TypeScript Config Package

```
packages/typescript-config/
├── base.json
├── nextjs.json
├── react-library.json
└── package.json
```

```json
// packages/typescript-config/package.json
{
  "name": "@repo/typescript-config",
  "version": "0.0.0",
  "main": "base.json",
  "files": [
    "base.json",
    "nextjs.json",
    "react-library.json"
  ]
}
```

```json
// packages/typescript-config/base.json
{
  "compilerOptions": {
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleResolution": "bundler",
    "target": "ES2020",
    "module": "ESNext"
  },
  "exclude": ["node_modules"]
}
```

```json
// packages/typescript-config/nextjs.json
{
  "extends": "./base.json",
  "compilerOptions": {
    "jsx": "preserve",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "noEmit": true,
    "incremental": true,
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### ESLint Config Package

```
packages/eslint-config/
├── library.js
├── next.js
└── package.json
```

```json
// packages/eslint-config/package.json
{
  "name": "@repo/eslint-config",
  "version": "0.0.0",
  "main": "library.js",
  "files": ["library.js", "next.js"],
  "dependencies": {
    "eslint-config-next": "latest",
    "eslint-config-prettier": "^9.0.0",
    "eslint-plugin-react": "latest"
  }
}
```

```js
// packages/eslint-config/library.js
module.exports = {
  extends: ['eslint:recommended', 'prettier'],
  env: {
    node: true,
    es2020: true,
  },
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
  },
  rules: {
    'no-console': 'warn',
  },
}
```

```js
// packages/eslint-config/next.js
module.exports = {
  extends: ['next', 'prettier'],
  rules: {
    '@next/next/no-html-link-for-pages': 'off',
  },
}
```

## Dependency Management

### Internal Dependencies

Use workspace protocol:

**pnpm:**
```json
{
  "dependencies": {
    "@repo/ui": "workspace:*"
  }
}
```

**npm/yarn:**
```json
{
  "dependencies": {
    "@repo/ui": "*"
  }
}
```

### Version Syncing

Keep dependencies in sync across packages:

```json
// Root package.json
{
  "devDependencies": {
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "typescript": "5.0.0"
  }
}
```

Packages inherit from root or specify versions explicitly.

## Turbo.json Configuration

Basic configuration file:

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": [
    "**/.env.*local",
    "tsconfig.json"
  ],
  "globalEnv": [
    "NODE_ENV"
  ],
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": ["coverage/**"]
    },
    "clean": {
      "cache": false
    }
  }
}
```

## Environment Variables

### Global Environment Variables

```json
// turbo.json
{
  "globalEnv": [
    "NODE_ENV",
    "CI"
  ]
}
```

### Package-Specific Environment Variables

```json
{
  "pipeline": {
    "build": {
      "env": ["NEXT_PUBLIC_API_URL", "DATABASE_URL"],
      "passThroughEnv": ["CUSTOM_VAR"]
    }
  }
}
```

### .env Files

```
my-monorepo/
├── .env                    # Global env vars
├── .env.local             # Local overrides (gitignored)
├── apps/
│   └── web/
│       ├── .env           # App-specific
│       └── .env.local     # Local overrides
```

## Gitignore Configuration

```gitignore
# Dependencies
node_modules/
.pnp
.pnp.js

# Turbo
.turbo

# Build outputs
dist/
.next/
out/
build/

# Environment
.env.local
.env.*.local

# Testing
coverage/

# Misc
.DS_Store
*.log
```

## NPM Scripts

Common scripts in root package.json:

```json
{
  "scripts": {
    "build": "turbo run build",
    "dev": "turbo run dev",
    "lint": "turbo run lint",
    "test": "turbo run test",
    "format": "prettier --write \"**/*.{ts,tsx,md}\"",
    "clean": "turbo run clean && rm -rf node_modules",
    "typecheck": "turbo run typecheck"
  }
}
```


---

Continued in [turborepo-setup-cont2.md](turborepo-setup-cont2.md)
