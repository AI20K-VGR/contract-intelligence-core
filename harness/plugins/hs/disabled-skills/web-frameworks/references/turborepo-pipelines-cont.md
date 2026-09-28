# Turborepo Task Pipelines (continued 2/2)

## Concurrency Control

### Parallel Execution (Default)

Turborepo runs tasks in parallel when safe:

```bash
# Run with default parallelism
turbo run build
```

### Limit Concurrency

```bash
# Max 3 tasks at once
turbo run build --concurrency=3

# 50% of CPU cores
turbo run build --concurrency=50%

# No parallelism (sequential)
turbo run build --concurrency=1
```

### Continue on Error

```bash
# Don't stop on first error
turbo run test --continue
```

## Task Execution Order

Example monorepo:
```
apps/
├── web (depends on @repo/ui, @repo/utils)
└── docs (depends on @repo/ui)
packages/
├── ui (depends on @repo/utils)
└── utils (no dependencies)
```

With config:
```json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"]
    }
  }
}
```

Execution order for `turbo run build`:
1. **Wave 1** (parallel): `@repo/utils` (no dependencies)
2. **Wave 2** (parallel): `@repo/ui` (depends on utils)
3. **Wave 3** (parallel): `web` and `docs` (both depend on ui)

## Complex Pipeline Examples

### Full-Stack Application

```json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "dist/**"]
    },
    "test": {
      "dependsOn": ["^build"],
      "outputs": ["coverage/**"]
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "typecheck": {
      "dependsOn": ["^build"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "deploy": {
      "dependsOn": ["build", "test", "lint", "typecheck"]
    }
  }
}
```

### Monorepo with Code Generation

```json
{
  "pipeline": {
    "generate": {
      "cache": false,
      "outputs": ["src/generated/**"]
    },
    "build": {
      "dependsOn": ["^build", "generate"],
      "outputs": ["dist/**"]
    },
    "test": {
      "dependsOn": ["generate"],
      "outputs": ["coverage/**"]
    }
  }
}
```

### Database-Dependent Pipeline

```json
{
  "pipeline": {
    "db:generate": {
      "cache": false
    },
    "db:migrate": {
      "cache": false
    },
    "build": {
      "dependsOn": ["^build", "db:generate"],
      "outputs": ["dist/**"]
    },
    "test:unit": {
      "dependsOn": ["build"]
    },
    "test:integration": {
      "dependsOn": ["db:migrate"],
      "cache": false
    }
  }
}
```

## Dry Run

Preview execution without running:

```bash
# See what would run
turbo run build --dry-run

# JSON output for scripts
turbo run build --dry-run=json

# Show full task graph
turbo run build --graph
```

## Force Execution

Ignore cache and run tasks:

```bash
# Force rebuild everything
turbo run build --force

# Force specific package
turbo run build --filter=web --force
```

## Output Control

```bash
# Show only errors
turbo run build --output-logs=errors-only

# Show new logs only
turbo run build --output-logs=new-only

# Show cache hash only
turbo run build --output-logs=hash-only

# Show full output
turbo run build --output-logs=full
```

## Best Practices

1. **Use topological dependencies** - `^build` ensures correct build order
2. **Cache build outputs** - Define `outputs` for faster rebuilds
3. **Disable cache for dev** - Set `cache: false` for dev servers
4. **Mark persistent tasks** - Use `persistent: true` for long-running tasks
5. **Filter strategically** - Use filters to run only affected tasks
6. **Control concurrency** - Limit parallelism for resource-intensive tasks
7. **Configure env vars** - Include vars that affect output in `env`
8. **Use dry-run** - Preview execution plan before running
9. **Continue on error in CI** - Use `--continue` to see all errors
10. **Leverage git filtering** - Run only on changed packages in CI

## Common Patterns

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
jobs:
  build:
    steps:
      - run: turbo run build test lint --filter='...[origin/main]'
```

Only build/test/lint changed packages and their dependents.

### Development Workflow

```bash
# Start all dev servers
turbo run dev

# Start specific app with dependencies
turbo run dev --filter=web...
```

### Pre-commit Hook

```json
// package.json
{
  "scripts": {
    "pre-commit": "turbo run lint test --filter='...[HEAD]'"
  }
}
```

Only lint/test changed packages.

### Deployment

```bash
# Build and test specific app
turbo run build test --filter=web...

# Deploy if successful
turbo run deploy --filter=web
```

Build app and its dependencies, then deploy.
