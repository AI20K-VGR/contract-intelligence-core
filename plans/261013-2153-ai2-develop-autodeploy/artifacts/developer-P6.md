# P6 documentation record

- Added `docs/AI2-LOCAL-SETUP.md` with a single-checkout PowerShell and bash setup path, ignored local key files, full Compose defaults, frontend API URL, service URLs, OCR → AI2 → graph → query walkthrough, consent behavior, troubleshooting, shutdown, and backend/frontend/AI-service checks.
- Root README quick start now points to the canonical guide and uses `npm ci`; the old two-checkout `HUONG-DAN-CHAY.md` is now a redirect. `deploy/README.md` reflects push-to-develop autodeploy, exact-SHA deployment, fail-closed SSH configuration, Keycloak readiness and Environment branch-policy setup.
- Verification: all local Markdown links resolve; `git check-ignore` confirms the documented `.env` paths are ignored; Compose configuration validates. No API keys or contract contents were written to documentation.
- Not verified: a clean-clone end-to-end run on Windows PowerShell and Linux/macOS, provider-backed OCR/LLM/vector inference, or production external smoke. This machine is Windows, and P5 production Environment policy/admin access remains blocked. No inference or deployment success is claimed.
