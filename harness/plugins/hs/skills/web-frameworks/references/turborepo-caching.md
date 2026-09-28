# Turborepo Caching Strategies

Local caching, remote caching, cache invalidation, and optimization techniques.

## Local Caching

### How It Works

Turborepo caches task outputs based on inputs:

1. **Hash inputs**: Source files, dependencies, environment variables, config
2. **Run task**: If hash not in cache
3. **Save outputs**: Store in `.turbo/cache`
4. **Restore on match**: Instant completion on cache hit

Default cache location: `./node_modules/.cache/turbo`

### Cache Configuration

```json
// turbo.json
{
  "pipeline": {
    "build": {
      "outputs": ["dist/**", ".next/**", "!.next/cache/**"],
      "cache": true  // default
    },
    "dev": {
      "cache": false  // don't cache dev servers
    }
  }
}
```

### Outputs Configuration

Specify what gets cached:

```json
{
  "build": {
    "outputs": [
      "dist/**",              // All files in dist
      "build/**",             // Build directory
      ".next/**",             // Next.js output
      "!.next/cache/**",      // Exclude Next.js cache
      "storybook-static/**",  // Storybook build
      "*.tsbuildinfo"         // TypeScript build info
    ]
  }
}
```

**Best practices:**
- Include all build artifacts
- Exclude nested caches
- Include type definitions
- Include generated files

### Clear Local Cache

```bash
# Remove cache directory
rm -rf ./node_modules/.cache/turbo

# Or use turbo command with --force
turbo run build --force

# Clear and rebuild
turbo run clean && turbo run build
```

## Remote Caching

Share cache across team and CI/CD.

### Vercel Remote Cache (Recommended)

**Setup:**
```bash
# Login to Vercel
turbo login

# Link repository
turbo link
```

**Use in CI:**
```yaml
# .github/workflows/ci.yml
env:
  TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
  TURBO_TEAM: ${{ secrets.TURBO_TEAM }}

steps:
  - run: turbo run build test
```

Get tokens from Vercel dashboard:
1. Go to https://vercel.com/account/tokens
2. Create new token
3. Add as GitHub secrets

### Custom Remote Cache

Configure custom remote cache server:

```json
// .turbo/config.json
{
  "teamid": "team_xxx",
  "apiurl": "https://cache.example.com",
  "token": "your-token"
}
```

Or use environment variables:
```bash
export TURBO_API="https://cache.example.com"
export TURBO_TOKEN="your-token"
export TURBO_TEAM="team_xxx"
```

### Remote Cache Verification

```bash
# Check cache status
turbo run build --output-logs=hash-only

# Output shows:
# • web:build: cache hit, replaying logs [hash]
# • api:build: cache miss, executing [hash]
```

## Cache Signatures

Cache invalidated when these change:

### 1. Source Files

All tracked Git files in package:
```
packages/ui/
├── src/
│   ├── button.tsx     # Tracked
│   └── input.tsx      # Tracked
├── dist/              # Ignored (in .gitignore)
└── node_modules/      # Ignored
```

### 2. Package Dependencies

Changes in package.json:
```json
{
  "dependencies": {
    "react": "18.2.0"  // Version change invalidates cache
  }
}
```

### 3. Environment Variables

Configured in pipeline:
```json
{
  "build": {
    "env": ["NODE_ENV", "API_URL"]  // Changes invalidate cache
  }
}
```

### 4. Global Dependencies

Files affecting all packages:
```json
{
  "globalDependencies": [
    "**/.env.*local",
    "tsconfig.json",
    ".eslintrc.js"
  ]
}
```

### 5. Task Configuration

Changes to turbo.json pipeline:
```json
{
  "build": {
    "dependsOn": ["^build"],
    "outputs": ["dist/**"]  // Config changes invalidate cache
  }
}
```

## Input Control

### Override Input Detection

Explicitly define what affects cache:

```json
{
  "build": {
    "inputs": [
      "src/**/*.ts",           // Include TS files
      "src/**/*.tsx",          // Include TSX files
      "!src/**/*.test.ts",     // Exclude tests
      "!src/**/*.stories.tsx", // Exclude stories
      "package.json",          // Include package.json
      "tsconfig.json"          // Include config
    ]
  }
}
```

Use cases:
- Exclude test files from build cache
- Exclude documentation from production builds
- Include only source files, not generated files

### Global vs Package Inputs

**Global inputs** (affect all packages):
```json
{
  "globalDependencies": [".env", "tsconfig.json"]
}
```

**Package inputs** (affect specific tasks):
```json
{
  "pipeline": {
    "build": {
      "inputs": ["src/**"]
    }
  }
}
```


---

Continued in [turborepo-caching-cont.md](turborepo-caching-cont.md)
