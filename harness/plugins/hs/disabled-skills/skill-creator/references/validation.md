# Validation — checklist and grep patterns

## Grep clean check (required before DONE)

```bash
# Get patterns from TestOwnershipBoundary in test_bug_class_invariants.py
# then run: grep -rnE '<pattern>' harness/plugins/hs/skills/<name>/
python3 -m pytest harness/tests/test_bug_class_invariants.py::TestOwnershipBoundary -q
```

Patterns checked: dot-claude path refs + external brand names + old invoke prefixes + dev-trace labels. For full pattern details see `"${HARNESS_BIN_ROOT:-.}"/harness/tests/test_bug_class_invariants.py` -> `banned` regex. Grep output **must be empty** and pytest **must be green** before reporting DONE.

## Quick checklist

### Frontmatter
- [ ] `name: hs:<dir>` — the plugin-namespaced name whose segment after `hs:` matches the skill dir (plugin skills are invoked by this frontmatter name, e.g. `name: hs:ask` in `ask/`, not by a bare dir name)
- [ ] `description` <=512 chars, has trigger phrase, third-person
- [ ] `metadata.compliance-tier` correct tier
- [ ] No retired fields (`category`, `keywords`, `license`, `user-invocable`, `metadata.owner`)

### Size and structure
- [ ] SKILL.md body <=15,000 chars (harness standard)
- [ ] Each references file <=15,000 chars
- [ ] No content duplicated between SKILL.md and references (no-duplication)
- [ ] Dir name = kebab-case, matching `name:` suffix

### Thin-core blocks
- [ ] Has **Boundaries** block (what NOT to do, what is returned on completion)
- [ ] Has **HARD-GATE** or **Backing** block (points to a real file, not phantom)
- [ ] Process with numbered steps
- [ ] Quick reference table pointing to drawers

### Backing-or-cut
- [ ] Every directive has named backing (gate/script/rule/schema)
- [ ] Directives without backing -> cut or moved to advisory in references

### Brand / path leaks (see TestOwnershipBoundary)
- [ ] No path references of the form `dot-claude/skills/` or `dot-claude/hooks/` (only lines with `# learn:` are whitelisted)
- [ ] No external brand names (source toolset name)
- [ ] No old invoke prefix (namespace `ck` instead of `hs`) — all frontmatter `name:` and invocations must use the `hs` namespace
- [ ] No dev-trace labels of the form DEC followed by digits

### Catalog resolve
- [ ] `load_catalog()['owned']` contains the new dir after file creation

```bash
python3 -c "
import sys; sys.path.insert(0, 'harness/scripts')
from catalog import load_catalog
c = load_catalog()
print('owned:', sorted(c['owned']))
"
```

### STANDARDIZE row
- [ ] Line added to `docs/STANDARDIZE.md`:

```
| ADAPT | hs:<name> skill (native thin-core + references) | <source> (origin, MIT) | harness/plugins/hs/skills/<name>/ | <notes> | grep-clean invariant + SKILL.md |
```

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Skill not in `owned` | SKILL.md not placed under `harness/plugins/*/skills/<dir>/` | Move it into the plugin's skills/ dir (ownership is location-based, not name-based) |
| Grep finds old invoke prefix | Copied from upstream source without renaming | Change invocations to `/hs:X` and `name: X` (bare) in all files |
| Grep finds dot-claude path ref | Path referenced instead of skill name | Replace with `hs:<name>` |
| SKILL.md body > 15,000 chars | Too much detail in the core | Move to references drawer |
| Phantom backing | No real file referenced | Find a real gate/script/rule or cut the directive |

## Validate mode

When using `hs:skill-creator validate`:

1. Read the target skill's SKILL.md
2. Run the grep clean check
3. Check `load_catalog()['owned']`
4. Count chars in SKILL.md body and each references file
5. Report pass/fail for each checklist item above
6. Do not edit files — report only
