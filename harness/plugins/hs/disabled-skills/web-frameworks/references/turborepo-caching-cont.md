# Turborepo Caching Strategies (continued 2/3)

## Environment Variables

### Cached Environment Variables

Include in cache signature:

```json
{
  "pipeline": {
    "build": {
      "env": [
        "NODE_ENV",           // Must match for cache hit
        "NEXT_PUBLIC_API_URL",
        "DATABASE_URL"
      ]
    }
  }
}
```

Cache invalidated when values change.

### Pass-Through Environment Variables

Don't affect cache:

```json
{
  "pipeline": {
    "build": {
      "passThroughEnv": [
        "DEBUG",        // Different values use same cache
        "LOG_LEVEL",
        "VERBOSE"
      ]
    }
  }
}
```

Use for: Debug flags, log levels, non-production settings

### Global Environment Variables

Available to all tasks:

```json
{
  "globalEnv": [
    "NODE_ENV",
    "CI",
    "VERCEL"
  ]
}
```

## Cache Optimization Strategies

### 1. Granular Outputs

Define precise outputs to minimize cache size:

```json
// ❌ Bad - caches too much
{
  "build": {
    "outputs": ["**"]
  }
}

// ✅ Good - specific outputs
{
  "build": {
    "outputs": ["dist/**", "!dist/**/*.map"]
  }
}
```

### 2. Exclude Unnecessary Files

```json
{
  "build": {
    "outputs": [
      ".next/**",
      "!.next/cache/**",      // Exclude Next.js cache
      "!.next/server/**/*.js.map",  // Exclude source maps
      "!.next/static/**/*.map"
    ]
  }
}
```

### 3. Separate Cacheable Tasks

```json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "cache": true
    },
    "test": {
      "dependsOn": ["build"],
      "cache": true  // Separate from build
    },
    "dev": {
      "cache": false  // Never cache
    }
  }
}
```

### 4. Use Input Filters

Only track relevant files:

```json
{
  "build": {
    "inputs": [
      "src/**/*.{ts,tsx}",
      "!src/**/*.{test,spec}.{ts,tsx}",
      "public/**",
      "package.json"
    ]
  }
}
```

## Cache Analysis

### Inspect Cache Hits/Misses

```bash
# Dry run with JSON output
turbo run build --dry-run=json | jq '.tasks[] | {package: .package, task: .task, cache: .cache}'
```

### View Task Graph

```bash
# Generate task graph
turbo run build --graph

# Output: graph.html (open in browser)
```

### Cache Statistics

```bash
# Run with summary
turbo run build --summarize

# Output: .turbo/runs/[hash].json
```

## CI/CD Cache Configuration

### GitHub Actions

```yaml
name: CI
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 18

      - name: Install dependencies
        run: npm install

      - name: Build and test
        run: turbo run build test lint
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}

      # Optional: Cache node_modules
      - uses: actions/cache@v3
        with:
          path: node_modules
          key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
```

### GitLab CI

```yaml
image: node:18

cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - node_modules/
    - .turbo/

build:
  stage: build
  script:
    - npm install
    - turbo run build test
  variables:
    TURBO_TOKEN: $TURBO_TOKEN
    TURBO_TEAM: $TURBO_TEAM
```

## Troubleshooting

### Cache Not Working

**Check outputs are defined:**
```bash
turbo run build --dry-run=json | jq '.tasks[] | {task: .task, outputs: .outputs}'
```

**Verify cache location:**
```bash
ls -la ./node_modules/.cache/turbo
```

**Check environment variables:**
```bash
echo $TURBO_TOKEN
echo $TURBO_TEAM
```

### Cache Too Large

**Analyze cache size:**
```bash
du -sh ./node_modules/.cache/turbo
```

**Reduce outputs:**
```json
{
  "build": {
    "outputs": [
      "dist/**",
      "!dist/**/*.map",      // Exclude source maps
      "!dist/**/*.test.js"   // Exclude test files
    ]
  }
}
```

**Clear old cache:**
```bash
# Turborepo doesn't auto-clean, manually remove:
rm -rf ./node_modules/.cache/turbo
```

### Remote Cache Connection Issues

**Test connection:**
```bash
curl -I https://cache.example.com
```

**Verify token:**
```bash
turbo link
# Should show: "Remote caching enabled"
```

**Check logs:**
```bash
turbo run build --output-logs=full
```


---

Continued in [turborepo-caching-cont2.md](turborepo-caching-cont2.md)
