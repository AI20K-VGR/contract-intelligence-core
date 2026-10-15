# P5 implementation record

- Deploy workflow now triggers only on pushes to `develop` and workflow dispatch; preflight rejects every other ref before the `production` environment or secrets are in scope.
- Added deploy tests to the preflight job so YAML/policy tests run before production deployment. Missing any of four SSH secret values fails with the setting name and never prints secret contents.
- Deployment checks out and verifies the triggering SHA, preserving SSH host-key pinning and serial deployment. External HTTPS/API and OIDC/exposure checks remain mandatory.
- Compose now enables a curl sidecar health probe for Keycloak `/health/ready`; Backend waits for that probe to become healthy. The Backend query egress/vector caps are passed through Compose with default `true` and can be narrowed by operator env.
- Keycloak token acquisition retries direct/network timeouts and retryable server errors within a bounded 300-second deadline; auth/config 4xx and malformed successful responses fail promptly without printing credentials/token.
- TDD: regression tests were run red before implementation; after changes deploy tests report 17 passed. `docker compose config --quiet`, Bash syntax check for `deploy/deploy.sh`, and `git diff --check` passed.
- GitHub read-only checks: deploy secret names exist (values not read); account permission is `write`; production Environment has no protection rules and no deployment branch policy; develop ruleset requires only `pr-guard`. Attempt to create the `develop` Environment policy was rejected by GitHub with HTTP 403 because repository admin rights are required. No repository settings were changed and no production deployment was run.
- P5 remains blocked on administrator configuration of the production deployment branch policy and required CI checks, plus the plan's separately approved real deployment smoke. Code-level local verification is green; this does not establish live deploy or AI2 provider inference.
