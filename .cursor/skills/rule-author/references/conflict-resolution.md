# Conflict resolution + override file format

Detail for `hs:rule-author`. The skill writes the per-repo override file; this reference is the procedure it follows when a proposed rule collides with a shipped one.

## The three outcomes

When a proposed rule's scope overlaps a shipped operational rule, classify:

### 1. Phantom conflict — narrow the glob

Scopes overlap mechanically, but the proposed rule is meant for a narrower set of files. Example: the shipped `python` rule has scope `**/*.py`; the user wants a stricter rule for handlers only.

- Proposed `**/*.py` overlaps the shipped `**/*.py` — but the intent is `src/handlers/**/*.py`.
- Narrow the proposed scope to `src/handlers/**/*.py`. Re-check with
  `user_override.detect_conflicts` — if it no longer overlaps the broad rule's *intent*, the conflict is resolved; both rules coexist.

Use the glob-intersection helpers directly when reasoning about overlap:

```python
from scope_match import globs_overlap, glob_subsumes
globs_overlap("**/*.py", "src/handlers/**/*.py")    # True  -> they intersect
glob_subsumes("**/*.py", "src/handlers/**/*.py")    # True  -> broad covers narrow
```

### 2. Floor rule — stop

If the colliding shipped rule has `floor: true`, it is the harness's inviolable safety layer. The loader REFUSES:

- an override by id targeting a floor rule, and
- a new-id rule whose scope overlaps a floor rule with a weaker posture (lower severity, or `enabled: false`) — the floor-shadow.

Do not write the override. Explain that the rule is a floor and cannot be relaxed per-repo.

### 3. Real conflict — confirm + reason

The user genuinely wants to override a non-floor rule (e.g. lower its severity, disable it, or change its scope). Confirm via AskUserQuestion, then collect a mandatory, specific `reason:` (it surfaces as a loud warning on every load).

## Override file format and location

Location: see SKILL.md's "Where the override lives" for the write target + precedence order. The folder reads every `*.yaml`, sorted, and merges their `overrides:` lists.

Schema: `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/standards-user-override.json`. Note the schema has no `description`/`title` field: for a NEW-id rule the only human-readable text that survives onto the synthesized rule is `reason`, so pack the full ALWAYS/NEVER directive (and any DEC/rationale ref) into `reason`.

```yaml
overrides:
  # modify an existing rule by its id
  - rule_id: STD-REVIEW-PY-RG1-R1
    reason: "this service intentionally uses bare except at the task boundary"
    severity: info
    enabled: true

  # add a new, repo-specific rule (a new id, non-shadowing scope)
  - rule_id: USER-HANDLERS-STRICT
    reason: "handlers must never log request bodies"
    scope: ["src/handlers/**/*.py"]
    severity: critical
```

Every entry MUST carry a non-empty `reason`. Fields that may be set: `severity` (critical|info), `enabled`, `scope`, `detector`, `relates_to_std`.

## Determinism

These files are read at review time by `rule_view.load_rules_from_tree` → `user_override.load`/`apply`. No LLM runs during a review; authoring judgment lives entirely here, once, at write-time.
