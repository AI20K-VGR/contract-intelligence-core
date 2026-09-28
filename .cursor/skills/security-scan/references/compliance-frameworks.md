# compliance-frameworks.md — map a compliance regime to the controls that evidence it

Load when a scan is run for compliance prep (SOC2 / GDPR / PCI-DSS / HIPAA) or when a finding needs to be tied to a regulatory control. This drawer does **not** certify compliance — it points each framework's requirements at the STRIDE/OWASP controls this scan already checks, so a finding can be reported as "evidence for / gap against control X".

The scan is a code+config audit. It cannot judge org-level controls (vendor contracts, physical security, staff training, incident-response runbooks) — those are out of scope and must be marked `[OUT-OF-SCOPE: process control]` rather than passed or failed silently.

---

## How to use

1. The user names a framework (or `--compliance <fw>`); default is all four when unspecified.
2. For each in-scope requirement, find the STRIDE/OWASP control below and report: evidence (`file:line`) if satisfied, or a gap finding at the mapped severity if not.
3. Anything the code cannot show → `[OUT-OF-SCOPE: process control]`, never a silent pass.

---

## SOC 2 (Trust Services Criteria)

| TSC | Requirement | Maps to control | OWASP · STRIDE |
|---|---|---|---|
| CC6.1 | Logical access — auth on every boundary | Spoofing checklist (auth on all endpoints, MFA) | A01/A07 · S |
| CC6.1 | Least privilege / RBAC | Elevation checklist (RBAC server-side, IDOR) | A01 · E |
| CC6.6 | Encryption in transit | Info-Disclosure (TLS 1.2+, no plaintext) | A02 · I |
| CC6.7 | Encryption at rest | Info-Disclosure (AES-256 at rest) | A02 · I |
| CC7.2 | Security monitoring / audit log | Repudiation (auth+authz events logged, retention) | A09 · R |
| CC7.1 | Vulnerability management | Dependency audit (CVE scan) | A06 · — |

## GDPR (data-protection by design)

| Article | Requirement | Maps to control | OWASP · STRIDE |
|---|---|---|---|
| Art.32 | Encryption of personal data | at-rest + in-transit checks | A02 · I |
| Art.32 | Confidentiality / access control | RBAC + horizontal-access (IDOR) checks | A01 · E |
| Art.25 | Data minimisation in responses | Info-Disclosure (response field filtering) | A01 · I |
| Art.30 | Records of processing / audit trail | Repudiation (data-modification logging w/ actor) | A09 · R |
| Art.33 | Breach detection readiness | logging + alerting coverage | A09 · R |
| Art.17 | Right to erasure (deletion path exists) | `[OUT-OF-SCOPE: process control]` unless a delete endpoint is in scope | — |

## PCI-DSS (cardholder data)

| Req | Requirement | Maps to control | OWASP · STRIDE |
|---|---|---|---|
| 3 | Protect stored cardholder data | encryption-at-rest + no-PAN-in-logs | A02 · I |
| 4 | Encrypt transmission over open networks | TLS 1.2+ checks | A02 · I |
| 6.2 | Patch known vulnerabilities | Dependency audit (CVE) | A06 · — |
| 6.5 | Secure coding (injection, XSS, CSRF) | Code-pattern + Tampering checklist | A03 · T |
| 8 | Strong auth (MFA, no shared creds) | Spoofing checklist (MFA, no default creds) | A07 · S |
| 10 | Track + monitor all access | Repudiation (audit log, retention ≥ requirement) | A09 · R |

## HIPAA (PHI safeguards)

| Safeguard | Requirement | Maps to control | OWASP · STRIDE |
|---|---|---|---|
| §164.312(a) | Access control / unique user ID | auth + RBAC checks | A01 · E |
| §164.312(b) | Audit controls | Repudiation (access logging) | A09 · R |
| §164.312(c) | Integrity of PHI | Tampering (input validation, request signing) | A03/A08 · T |
| §164.312(e) | Transmission security | TLS 1.2+ checks | A02 · I |
| §164.308 | Risk analysis | the STRIDE threat-model step itself | A04 · — |

---

## Reporting

Add a `## Compliance` section to the scan report when a framework was requested:

```markdown
## Compliance — <framework>

| Requirement | Status | Evidence / Gap | Severity |
|---|---|---|---|
| SOC2 CC6.6 (TLS in transit) | PASS | api/server.ts:30 forces TLS 1.2 | — |
| PCI-DSS 8 (MFA) | GAP | no MFA on admin login (auth/login.ts:12) | High |
| GDPR Art.17 (erasure) | OUT-OF-SCOPE | process control, no delete endpoint in scope | — |
```

Do not claim "compliant" — claim "no in-scope code gap found against <requirement>". The human and their auditor own the certification decision.
