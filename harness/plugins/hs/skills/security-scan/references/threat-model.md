# threat-model.md — STRIDE + OWASP checklist and output format

Load when you need Step 1 (Threat-model) and Step 5 (STRIDE+OWASP sweep) of the core workflow.

---

## Step 1 — Threat-model before scanning

Establish the following before grepping anything:

1. **Assets**: what data is stored or processed? (PII, credentials, payments, sessions)
2. **Trust boundaries**: where does input come from? (HTTP, file upload, env var, IPC, webhook)
3. **Attack surface**: which endpoints are exposed? what auth protects them?
4. **Actual scope**: code + config tracked in git — no runtime or external infrastructure

Evidence filter: every finding requires a `file:line` anchor or a reproduction command. No anchor → tag `[ASSUMED]` (or `[PRIOR]` if it rests on prior/training knowledge), do not include in Critical/High.

---

## STRIDE Checklist (Step 5)

### S — Spoofing (Authentication)

- [ ] Every endpoint requires auth except those intentionally public
- [ ] Passwords hashed with bcrypt/argon2 — not MD5/SHA1
- [ ] JWTs have `exp` and are validated server-side
- [ ] Session cookies: `Secure`, `HttpOnly`, `SameSite`
- [ ] OAuth/OIDC uses `state` parameter to prevent CSRF
- [ ] MFA available for sensitive operations (admin, payment, account recovery)
- [ ] No default credentials remaining

### T — Tampering (Integrity)

- [ ] Input validation at every boundary (type, length, format)
- [ ] Parameterized queries — no string concatenation for SQL/NoSQL
- [ ] CSRF token on state-changing forms
- [ ] Request signing for API-to-API calls (HMAC or mTLS)
- [ ] File uploads validate type (magic bytes), size, and content
- [ ] HTTP methods restricted per endpoint (no GET for mutations)

### R — Repudiation (Logging)

- [ ] Auth events logged: login, logout, failure
- [ ] Authz failures logged with user/resource context
- [ ] Data modifications logged with attribution + timestamp
- [ ] Logs do not contain secrets/tokens/PII
- [ ] Logs are append-only or go to a centralized sink
- [ ] Logs retained per compliance requirement (90 days minimum)

### I — Information Disclosure

- [ ] Error messages do not leak stack traces in production
- [ ] API responses do not expose internal IDs, system paths, or version strings
- [ ] Sensitive data is encrypted at rest
- [ ] Transport: TLS 1.2+ — no HTTP for sensitive endpoints
- [ ] No hardcoded secrets in source (→ Step 2)
- [ ] `.env` and credential files are in `.gitignore`

### D — Denial of Service

- [ ] Rate limits on auth endpoints and sensitive endpoints
- [ ] Request body size limit enforced
- [ ] Pagination enforced on list endpoints (no unbounded queries)
- [ ] Timeouts on all external API and DB calls
- [ ] Connection pools sized and cleaned up (no leak under load)
- [ ] Background jobs have concurrency limits and dead-letter queues
- [ ] No regexes with catastrophic backtracking (ReDoS)

### E — Elevation of Privilege

- [ ] RBAC enforced server-side, not client-side
- [ ] Horizontal check: user A cannot read user B's resources (IDOR)
- [ ] Admin endpoints have a dedicated, stricter auth middleware
- [ ] Privilege-escalation paths require re-auth (step-up before elevation)
- [ ] Service accounts use least privilege
- [ ] Third-party integration scopes are minimum necessary

---

## OWASP Top 10 Quick Reference (Step 5)

| # | Category | Check |
|---|---|---|
| A01 | Broken Access Control | Missing auth, IDOR, CORS misconfig, path traversal |
| A02 | Cryptographic Failures | Weak hash (MD5/SHA1), plaintext storage, missing TLS |
| A03 | Injection | SQL, NoSQL, OS cmd, LDAP, template injection |
| A04 | Insecure Design | Missing threat model, business logic flaw |
| A05 | Security Misconfiguration | Default credentials, verbose errors, unnecessary ports |
| A06 | Vulnerable Components | Dep CVE, outdated library (→ Step 3) |
| A07 | Auth Failures | Brute force, session fixation, weak token |
| A08 | Data Integrity Failures | Unsigned updates, unverified deserialization, CI poisoning |
| A09 | Logging Failures | Missing security event log, no alerting |
| A10 | SSRF | Unvalidated user-supplied URL, internal service fetch |

---

## Output Format — Security Scan Report

```markdown
# Security Scan Report

**Project:** {name}
**Scanned:** {date}
**Files checked:** {count}
**Scope:** {path or full}

## Summary

| Category | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|
| Secrets | X | X | X | - | - |
| Dependencies | X | X | X | X | - |
| Code patterns | X | X | X | - | - |
| STRIDE/OWASP | X | X | X | X | X |

## Findings

### CRITICAL

1. **[SECRET]** Hardcoded credential at `src/config.py:42`
   - Pattern: `sk-ant-…`
   - OWASP: A02 · STRIDE: I
   - Fix: move to env var; rotate credential immediately

### HIGH
...

## Dep Audit Output

{output from dep audit tool or "[DEP-AUDIT-SKIPPED]: reason"}

## Priority recommendations

1. ...

## Unresolved / [ASSUMED]

- ...
```

Report saved to `plans/reports/security-scan-{date}-{scope}.md`.

---

## Fix Mode (--fix) — guard pattern

```
For each finding (Critical → High → Medium → Low):
  1. Apply 1 targeted fix
  2. Guard: run the project's tests or linter
  3. Guard fail → stop, report the failure, do not continue
  4. Guard pass → commit: `security: <short description>`
  5. Advance to next finding
```

No guard script in the project → stop `--fix` and ask the user to configure a guard first.
