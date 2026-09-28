# scan-dimensions.md — scan dimensions and attacker personas

Load when you need detail on: (a) code pattern analysis, (b) the red-team persona loop.

---

## Code Pattern Analysis (Step 6 of core workflow)

Use the Grep tool with the patterns below. Read 5-10 lines of context around each match. Use reasoning to distinguish real vulnerabilities from false positives.

For the full pattern catalog — SQLi/XSS/command-injection/path-traversal/insecure-randomness plus Dangerous-Functions, Auth, Info-Disclosure, and the False-Positive-Indicators table — load `references/vulnerability-patterns.md`. That file is the single source of truth for the regex text; the categories below point into it instead of re-copying the patterns.

### Injection

High-signal categories — regex lives in `references/vulnerability-patterns.md`:
- SQL injection — string-concat + template-literal queries (§ SQL Injection)
- Command injection — exec/spawn/os.system/subprocess with unsanitized input (§ Command Injection)
- Path traversal — user input in file paths (§ Path Traversal)

**Template injection / eval** (not in vulnerability-patterns.md's Dangerous Functions/Deserialization sections as one group — kept here as a combined quick-check):
```
\beval\s*\(
new\s+Function\s*\(
setTimeout\s*\(\s*['"]
(?i)(pickle\.loads|yaml\.load\(|unserialize\()
```

### XSS

Regex lives in `references/vulnerability-patterns.md` § XSS (Cross-Site Scripting) — dangerous DOM manipulation + unescaped-output-in-template-engines categories.

### Authz / Access Control

- **Disabled security / TLS bypass** — regex in `references/vulnerability-patterns.md` § Authentication / Authorization → Disabled security.
- **Debug output in production** — regex in `references/vulnerability-patterns.md` § Information Disclosure → Debug/verbose in production.

**SSRF — server-side fetch with unvalidated input** (not in vulnerability-patterns.md — kept here):
```
(?i)(fetch|axios|request|urllib|httpx)\s*\(.*req\.(params|query|body)
(?i)(fetch|axios|request)\s*\(.*\+
```

### False positive indicators

Same list as `references/vulnerability-patterns.md` § False Positive Indicators: `test`/`spec`/`mock`/`fixture`/`example`/`sample`/`demo`, `TODO`/`FIXME`/`HACK`, env-read variables, comment lines.

---

## Red-Team Personas (--red-team flag)

4 personas in order. Each persona = 1 iteration phase before the STRIDE/OWASP sweep.

### Phase 1 — Security Adversary

**Mindset**: outside attacker with no prior access.
**Goal**: auth bypass, data exfiltration, RCE.

Probe:
- Trace every input from entry point to sink — missing validation?
- Every route parameter (`:id`, `:slug`, `:uuid`) → IDOR?
- JWT: algorithm confusion (`none`/`HS256→RS256`), missing `exp`, weak secret?
- Unguarded admin route? Middleware ordering that allows bypass?

### Phase 2 — Supply Chain Attacker

**Mindset**: does not breach the app directly; poisons an upstream artifact.
**Goal**: CVEs in dependencies, typosquatting, CI/CD compromise.

Probe:
- `npm audit` / `pip-audit` / project dep-audit tool — all CVEs
- Any package unmaintained (last publish > 2 years)?
- CI workflow with `permissions: write-all` or `pull_request_target` without a trust gate?
- Dockerfile/CI using `curl | sh` or `apt-get` without checksum verification?

### Phase 3 — Insider Threat

**Mindset**: legitimate internal user, low privilege, goal is escalation.
**Goal**: horizontal/vertical escalation, bulk export, audit trail deletion.

Probe:
- Does the admin endpoint enforce authz server-side or only in the UI?
- Queries missing `WHERE user_id = current_user`?
- Endpoints returning unbounded lists (no `LIMIT` / cursor)?
- Audit log coverage: auth events, data exports, config changes?

### Phase 4 — Infrastructure Attacker

**Mindset**: already has a foothold inside the container/runtime.
**Goal**: container escape, lateral movement, harvest secrets from env.

Probe:
- `Dockerfile`, `docker-compose.yml`, K8s manifests: `--privileged`, mounted host paths?
- Secrets passed via build arg (exposed in image layers)?
- SSRF to cloud metadata API (`169.254.169.254`, `metadata.google.internal`)?
- Health/debug endpoints exposed internally without auth?

### Phase 5 — STRIDE/OWASP Sweep (standard)

After 4 personas, fill remaining coverage gaps through the STRIDE + OWASP A01-A10 checklist.
Reference: `references/threat-model.md`.

### Per-persona iteration protocol

```
1. Select — choose the next untested attack vector
2. Assume persona — reason as an attacker, not a defender
3. Probe — read relevant code, trace data flow, find missing guards
4. Validate — proof: file:line, attack scenario, impact
5. Log — severity, OWASP category, STRIDE dimension, confidence
6. Chain — compound prior-phase findings into current phase
```

### Coverage summary at end of red-team

```
Personas: Security Adversary[✓] Supply Chain[✓] Insider[✓] Infrastructure[✓/partial]
STRIDE: S[✓] T[✓] R[?] I[✓] D[✓] E[✓]
OWASP: A01[✓] A02[?] A03[✓] ... A10[✓]
Findings: X Critical, Y High, Z Medium, W Low
```
