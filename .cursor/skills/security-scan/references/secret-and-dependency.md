# secret-and-dependency.md — secret scan patterns and dependency audit

Load when you need detail on Step 2 (Secret scan) and Step 3 (Dep audit) of the core workflow.

---

## Secret Scanning (Step 2)

Use the Grep tool with the patterns below. Exclude test/example/dist before reporting.

### High confidence — clear structure, low false-positive rate

| Provider | Pattern |
|---|---|
| AWS access key | `AKIA[0-9A-Z]{16}` |
| GitHub classic / fine-grained | `gh[pousr]_[A-Za-z0-9_]{36,255}` · `github_pat_[A-Za-z0-9_]{22,}` |
| Stripe live | `sk_live_[0-9a-zA-Z]{24,}` · `rk_live_[0-9a-zA-Z]{24,}` |
| Slack | `xox[baprs]-[0-9a-zA-Z-]{10,}` |
| Google Cloud | `AIza[0-9A-Za-z_-]{35}` |
| Anthropic | `sk-ant-[A-Za-z0-9_-]{40,}` |
| Private key PEM | `-----BEGIN (RSA \|EC \|DSA \|OPENSSH )?PRIVATE KEY-----` |
| JWT in code (not in a header) | `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}` |

### Medium confidence — context required to confirm

```
(?i)(api[_-]?key|apikey|api[_-]?secret)\s*[:=]\s*['"][A-Za-z0-9/+=]{16,}['"]
(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@
(?i)(password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]
(?i)(secret|token|credential)\s*[:=]\s*['"][A-Za-z0-9/+=]{16,}['"]
```

### Exclusions — skip matches in

- Files: `*.example`, `*.test.*`, `*.spec.*`, `*.md`, `*.txt`
- Dirs: `node_modules/`, `dist/`, `vendor/`, `__pycache__/`
- Content: lines containing `TODO`, `FIXME`, `YOUR_`, `REPLACE_`, `xxx`, `placeholder`
- Content: variable read from env (`= process.env.`, `= os.getenv(`)

### Severity classification

| Severity | Condition |
|---|---|
| Critical | Real production secret, immediately usable |
| High | Real credential but not confirmed still active |
| Medium | Possibly a credential (needs further confirmation) |

### Credential hygiene — required when reporting

Masking MUST per SKILL.md Credential hygiene (`<REDACTED_TOKEN>` / `<REDACTED_PASSWORD>`). Extra
masking detail by credential shape:

- Connection string: `protocol://user:<REDACTED_PASSWORD>@host/db`
- Env var: name only (`$DATABASE_URL`), do not print the value
- Private key/cert: first 8 chars + `<...REDACTED...>` + last 8 chars
- If a real credential is found: recommend rotating immediately, do not wait for other fixes

---

## .env Exposure Check

```bash
# Check if .env is tracked by git
git ls-files --error-unmatch .env .env.local .env.production 2>/dev/null

# Check whether .gitignore covers .env
grep -n "\.env" .gitignore 2>/dev/null
```

If `.env` is currently tracked → Critical (Information Disclosure, OWASP A02).

---

## Dependency Audit (Step 3)

Detect the stack from manifest files, then run the corresponding tool. Do not hard-code the scanner — use the project's audit tool; if none exists → record `[DEP-AUDIT-SKIPPED]` in the report.

| Stack | Detection file | Audit command |
|---|---|---|
| Node.js | `package.json` | `npm audit --json` |
| Python | `requirements.txt` / `pyproject.toml` | `pip-audit --format json` |
| Go | `go.mod` | `govulncheck ./...` |
| Ruby | `Gemfile` | `bundle audit check --update` |
| Rust | `Cargo.toml` | `cargo audit` |
| Java/Maven | `pom.xml` | `mvn dependency-check:check` |

Parse the output and classify by severity (critical/high/moderate/low). Map to OWASP A06 (Vulnerable and Outdated Components).

If the command fails (`exit ≠ 0`): record the error in the report rather than skipping — `{"error": "npm audit failed", "exit_code": N}`.
