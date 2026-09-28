# Turborepo Task Pipelines

Task orchestration, dependencies, and parallel execution strategies.

## Pipeline Configuration

Define tasks in `turbo.json`:

```json
{
  "$schema": "https://turbo.build/schema.json",
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**"]
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": ["coverage/**"]
    },
    "lint": {},
    "dev": {
      "cache": false,
      "persistent": true
    }
  }
}
```

## Task Dependencies

### Topological Dependencies (^)

`^` means "run this task in dependencies first":

```json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"]
    }
  }
}
```

Example flow:
```
packages/ui (dependency)
  ↓ builds first
apps/web (depends on @repo/ui)
  ↓ builds second
```

### Internal Dependencies

Run tasks in same package first:

```json
{
  "pipeline": {
    "deploy": {
      "dependsOn": ["build", "test"]
    }
  }
}
```

Execution order in same package:
1. Run `build`
2. Run `test`
3. Run `deploy`

### Combined Dependencies

Mix topological and internal:

```json
{
  "pipeline": {
    "test": {
      "dependsOn": ["^build", "lint"]
    }
  }
}
```

Execution order:
1. Build all dependencies (`^build`)
2. Lint current package (`lint`)
3. Run tests (`test`)

## Task Configuration Options

### outputs

Define what gets cached:

```json
{
  "build": {
    "outputs": [
      "dist/**",           // All files in dist
      ".next/**",          // Next.js build
      "!.next/cache/**",   // Exclude Next.js cache
      "build/**",          // Build directory
      "public/dist/**"     // Public assets
    ]
  }
}
```

### cache

Enable/disable caching:

```json
{
  "dev": {
    "cache": false        // Don't cache dev server
  },
  "build": {
    "cache": true         // Cache build (default)
  }
}
```

### persistent

Keep task running (for dev servers):

```json
{
  "dev": {
    "cache": false,
    "persistent": true    // Don't kill after completion
  }
}
```

### env

Environment variables affecting output:

```json
{
  "build": {
    "env": [
      "NODE_ENV",
      "NEXT_PUBLIC_API_URL",
      "DATABASE_URL"
    ]
  }
}
```

### passThroughEnv

Pass env vars without affecting cache:

```json
{
  "build": {
    "passThroughEnv": [
      "DEBUG",            // Pass through but don't invalidate cache
      "LOG_LEVEL"
    ]
  }
}
```

### inputs

Override default input detection:

```json
{
  "build": {
    "inputs": [
      "src/**/*.ts",
      "!src/**/*.test.ts", // Exclude test files
      "package.json"
    ]
  }
}
```

### outputMode

Control output display:

```json
{
  "build": {
    "outputMode": "full"        // Show all output
  },
  "dev": {
    "outputMode": "hash-only"   // Show cache hash only
  },
  "test": {
    "outputMode": "new-only"    // Show new output only
  },
  "lint": {
    "outputMode": "errors-only" // Show errors only
  }
}
```

## Running Tasks

### Basic Execution

```bash
# Run build in all packages
turbo run build

# Run multiple tasks
turbo run build test lint

# Run with specific package manager
pnpm turbo run build
```

### Filtering

Run tasks in specific packages:

```bash
# Single package
turbo run build --filter=web
turbo run build --filter=@repo/ui

# Multiple packages
turbo run build --filter=web --filter=api

# All apps
turbo run build --filter='./apps/*'

# Pattern matching
turbo run test --filter='*-api'
```

### Dependency Filtering

```bash
# Package and its dependencies
turbo run build --filter='...web'

# Package's dependencies only (exclude package itself)
turbo run build --filter='...^web'

# Package and its dependents
turbo run test --filter='ui...'

# Package's dependents only
turbo run test --filter='^ui...'
```

### Git-Based Filtering

Run only on changed packages:

```bash
# Changed since main branch
turbo run build --filter='[main]'

# Changed since HEAD~1
turbo run build --filter='[HEAD~1]'

# Changed in working directory
turbo run test --filter='...[HEAD]'

# Package and dependencies, only if changed
turbo run build --filter='...[origin/main]'
```


---

Continued in [turborepo-pipelines-cont.md](turborepo-pipelines-cont.md)
