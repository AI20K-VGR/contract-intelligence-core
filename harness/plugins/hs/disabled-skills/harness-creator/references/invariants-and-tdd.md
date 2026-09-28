# Invariants and TDD — checklist and CI contract

## Red->green TDD (required for hooks and scripts)

1. **Write the test FIRST** — run it to FAIL intentionally (ImportError / wrong assert). No skipping, no fake green.
2. **Implement to green** — minimal code to make the test pass.
3. **Run the full suite** — `python3 -m pytest harness/tests/ -q`.
4. **Commit the pair** — test + module together, conventional commit, no AI reference, no plan-ID/phase/audit label in the commit message.

Full rule: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md`.

## CI invariants — `test_bug_class_invariants.py`

`harness/tests/test_bug_class_invariants.py` enforces 5 bug classes that must not recur. New primitives must pass **all** of them before reporting DONE.

### 1. TestHookImportBoundary

Hooks must NOT import from `skills/` (skills are LLM prose, hooks are runtime).
Violation: `from skills.xxx import ...` or `import harness/skills`.

### 2. TestComplianceRegistration

Every hook with `HOOK_CLASS = "compliance"` must have its filename in `harness/install/hooks-registration.yaml`. An unwired gate provides no protection.

```yaml
# harness/install/hooks-registration.yaml — add an entry when creating a compliance hook
hooks:
  - <hook-name>.py
```

### 3. TestOwnershipBoundary

No file in `harness/` may contain a path reference of the form `dot-claude/skills/` or `dot-claude/hooks/` (runtime references into the upstream dot-claude tree are banned; the harness must be self-contained). Lines that explain a learned pattern need a `# learn:` prefix to be whitelisted.

Verify with:
```bash
python3 -m pytest harness/tests/test_bug_class_invariants.py::TestOwnershipBoundary -q
```

### 4. TestStoreWriteDiscipline

Only shared writers may open `state/` files directly: `trace_log.py`, `telemetry_paths.py`, `session_init.py`, `hook_runtime.py`, `harness_paths.py`. All other scripts and hooks must use `trace_log.append_event` or `telemetry_paths.append_event`.

### 5. TestWording

Two wording invariants:

Banned (paraphrase — test_bug_class_invariants.py enforces literal regexes):

- fs_guard: do NOT call it a "fence" (any write+fence combination) — use "script-path containment helper".
- Do not use `blocks` combined with `all`/`every`/`any` + `writes` — describe the actual scope of the mechanism specifically.
- Do not make a positive tamper-resistance claim about config. Only a negated form ("not tamper-proof") may stand; the negation word must sit directly before the term.
- actor = attribution (not authentication/authorization).
- gate = presence gate (not authentication).

## Validation checklist before DONE

### Hook
- [ ] `HOOK_CLASS` is a constant in code (not read from config)
- [ ] Correct wrapper used: `run_telemetry_hook` / `run_nudge_hook` / `run_compliance_hook`
- [ ] Compliance: registered in `hooks-registration.yaml`
- [ ] No import from skills/
- [ ] TDD test passing in `harness/tests/`
- [ ] `pytest harness/tests/test_bug_class_invariants.py -q` -> green

### Script
- [ ] Analyzer: always exit 0, stdout JSON
- [ ] Gate: exit 2 + actionable stderr reason on failure
- [ ] Store writes through shared writers (no direct `state/` opens)
- [ ] TDD test passing in `harness/tests/`
- [ ] `pytest harness/tests/test_bug_class_invariants.py -q` -> green

### Rule
- [ ] Concise, does not repeat `harness-contract.md`
- [ ] No banned wording (see wording invariant table above)

### Schema
- [ ] `actor` field + description "attribution, not authn"
- [ ] `ts` field ISO-8601
- [ ] Standard verdict enum: `PASS | PASS_WITH_RISK | BLOCKED`
- [ ] A real gate/script will read this artifact

### Agent
- [ ] Explicit tool list
- [ ] Team Mode section if spawnable by `hs:team`
- [ ] No runtime code coupling

## Full validation commands

```bash
# 1. All CI invariants
python3 -m pytest harness/tests/test_bug_class_invariants.py -q

# 2. Full test suite
python3 -m pytest harness/tests/ -q

# 3. Catalog check (only needed when creating a skill — not for hook/rule/schema/data)
python3 -c "
import sys; sys.path.insert(0, 'harness/scripts')
from catalog import load_catalog
print('catalog owned:', sorted(load_catalog()['owned']))
"
```

## Hard constraints — non-negotiable

- Do not commit `harness/state/` to git (JSONL runtime data, not source).
- Do not commit secrets or dotenv files.
- Do not put plan IDs, phase numbers, or audit labels in test names, code comments, or commit messages — describe the invariant or behavior directly.
- Conventional commits, no AI reference in the commit message.
