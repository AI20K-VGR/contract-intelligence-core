# invocation-patterns — example commands for hs:repomix

Load this file when you need specific commands for a given situation.

## Pack subtree (implement / debug)

```bash
# Specific module — context for implementation
repomix --include "src/auth/**,src/api/**" -o /tmp/auth-context.xml

# All harness scripts + hooks
repomix --include "harness/scripts/**,harness/hooks/**" --style markdown \
  -o /tmp/harness-core.md

# Pack then check token distribution
repomix --include "src/**" --token-count-tree 500
```

## Pack entire repo (onboard / review)

```bash
# Full repo, markdown, strip comments to save tokens
repomix --remove-comments --style markdown -o /tmp/repo-full.md

# Full repo XML (LLM consumption)
repomix --style xml -o /tmp/repo-full.xml

# Full + token tree to decide whether to narrow scope
repomix --token-count-tree
```

## Remote repo (external library / audit)

```bash
# Pack a GitHub library without cloning
npx repomix --remote owner/repo --style xml -o /tmp/lib-audit.xml

# Specific commit
npx repomix --remote https://github.com/owner/repo/commit/abc123 -o /tmp/snapshot.xml

# Compare 2 libraries
npx repomix --remote owner/lib-a -o /tmp/lib-a.xml
npx repomix --remote owner/lib-b -o /tmp/lib-b.xml
```

> Remote repo must be public. Private repo -> clone first, then pack locally.

## Security audit

```bash
# Security check is on by default — check warnings in output
repomix --include "src/**,config/**" --style xml -o /tmp/pre-deploy-audit.xml

# Audit a suspect dependency
repomix --include "node_modules/package-name/**" -o /tmp/dep-audit.xml

# Disable security check (confirmed false positive)
repomix --no-security-check --include "src/**" -o /tmp/context.xml
```

## Doc context / architecture

```bash
# Code + docs for AI documentation generation
repomix --include "src/**,docs/**,*.md" --style markdown -o /tmp/doc-context.md

# Architecture — exclude tests to reduce noise
repomix --include "src/**/*.py,*.md" -i "**/*_test.py,tests/" \
  --style markdown -o /tmp/arch-context.md
```

## Token optimization

```bash
# Maximum reduction: strip comments + line numbers
repomix --include "src/**" --remove-comments --no-line-numbers -o /tmp/compact.xml

# View token distribution, files >1000 tokens only
repomix --token-count-tree 1000

# Ignore build artifacts
repomix -i "dist/**,build/**,node_modules/**,*.min.js,coverage/**"
```

## Safe output paths (no commit)

```bash
# Use /tmp — cleaned on reboot
repomix --include "src/**" -o /tmp/context-$(date +%Y%m%d).xml

# Use harness/state/ — git-safe (in .gitignore)
repomix --include "harness/**" -o harness/state/context-dump.xml
```

## CLI detection / fallback

```bash
# Check before running
if ! command -v repomix &>/dev/null; then
  echo "repomix not installed. Install: npm install -g repomix"
  echo "Fallback: use hs:scout + Read files manually"
  exit 1
fi
repomix "$@"
```

## .repomixignore (permanent ignores)

Create `.repomixignore` at the repo root for repeated patterns:

```
# Build artifacts
dist/
build/
*.min.js

# Test / coverage
coverage/
**/__pycache__/
**/*.pyc

# Sensitive
.env*
*.key
*.pem
secrets/

# Harness state (never pack)
harness/state/
```

## Quick stack-specific commands

| Stack | Command |
|---|---|
| Python | `repomix --include "**/*.py,requirements*.txt" -i "**/__pycache__/,venv/"` |
| Node.js | `repomix --include "src/**/*.js,config/**" -i "node_modules/,logs/"` |
| TypeScript | `repomix --include "**/*.ts,**/*.tsx" -i "dist/,**/*.test.ts"` |
| Monorepo | `repomix --include "packages/*/src/**" -i "packages/*/dist/"` |
| Harness | `repomix --include "harness/**" -i "harness/state/,harness/tests/**"` |
