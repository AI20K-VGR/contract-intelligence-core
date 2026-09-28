---
name: hs:techstack
injectable: true
description: "Detect the target repo's tech stack (languages, test command, package manager, CI) so the harness adapts instead of assuming pytest. Use when the harness is installed into a non-Python repo, or before hs:test/hs:setup so commands match the real stack. Read-only; never mutates."
allowed-tools: [Bash, Read, Grep, Glob]
argument-hint: "[--root <dir>]"
metadata:
  compliance-tier: workflow
---

# hs:techstack — read-only tech-stack detection

The harness verifies with **pytest** by default, but it installs *into other repos* (`sh install.sh <tarball> <repo>`) that may be Node, Go, Rust, or Java. This skill detects the target's real stack so the rest of the harness adapts instead of running the wrong command. It **only reads** — it never edits config, never installs, never runs the test command. The Shape-A self-learning surface:
observe the repo, propose the right commands, leave the decision to the human (paired with `hs:setup` to act).

## Flow

1. **Detect** (read-only):

   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/detect_techstack.py --root <target-repo>
   ```

   Emits a JSON profile, e.g.:

   ```json
   {
     "root": "/path/to/repo",
     "stacks": [
       {"language": "typescript", "marker": "package.json", "test_cmd": "pnpm test", "pkg_mgr": "pnpm"}
     ],
     "ci": ["github-actions"],
     "primary": "typescript"
   }
   ```

2. **Read the profile**:
   - `stacks[]` — one entry per detected stack (a polyglot repo lists all); each
     carries `test_cmd` + `pkg_mgr` read from the lockfile.
   - `test_cmd` is `null` when the stack declares no test runner (e.g. a Node repo
     with no `scripts.test`) — that is honest, not a gap to paper over.
   - `primary` — the first stack by fixed precedence (python → js/ts → go → rust → java).
   - `ci` — `github-actions` / `gitlab-ci` / `circleci` if a workflow file is present.

3. **Propose, don't impose**. Surface what the harness *would* run for this stack:
   - test command for `hs:test` (e.g. `go test ./...` instead of `pytest`);
   - the package manager for any install/preflight step;
   - the CI system, if a hook or gate needs to know it.
   Then hand the decision to the user — apply real config changes through `hs:setup`, which writes via validated config CLIs.

## What it detects

| Stack | Marker(s) | test_cmd | pkg_mgr source |
|---|---|---|---|
| python | pyproject.toml / setup.py / requirements.txt | `pytest` | `[tool.poetry]` → poetry; uv.lock → uv; Pipfile → pipenv; else pip |
| javascript / typescript | package.json (+ tsconfig.json → ts) | `<pkg> test` if `scripts.test` declared, else `null` | pnpm-lock / yarn.lock / bun.lockb → that; else npm |
| go | go.mod | `go test ./...` | go |
| rust | Cargo.toml | `cargo test` | cargo |
| java | pom.xml / build.gradle[.kts] | `mvn test` / `gradle test` | maven / gradle |

## Boundaries

- **Read-only.** Touches no file; never writes config, installs deps, or runs the test command. Acting on the profile is `hs:setup`'s job.
- **Fail-soft.** A missing or unreadable root yields an empty profile (no stacks), never an error — the detector must not crash the host.
- **Presence-based, not deep.** It reads marker existence + a lockfile/`scripts.test`; it does not parse full build graphs. Trust the markers; confirm anything surprising by eye before changing a command.

## Wiring

| Backing | Role |
|---|---|
| `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/detect_techstack.py` | the read-only detector (`detect(root)` + CLI) |
| `hs:setup` | acts on the proposal — writes posture/config via validated CLIs |
| `hs:test` | the consumer that should run the detected `test_cmd` on a non-Python repo |
