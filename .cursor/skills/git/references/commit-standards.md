# Commit message standards

## Format

```
type(scope): description
```

## Types (in order of preference)

- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation only
- `style` — formatting, no logic change
- `refactor` — restructuring, no behavior change
- `test` — tests
- `chore` — maintenance, deps, config
- `perf` — performance
- `build` — build system
- `ci` — CI/CD

## Rules

- **< 72 characters**
- **Present tense, imperative** ("add" not "added")
- **No trailing period**
- **Scope is optional but recommended**
- **Focus on WHAT, not HOW**

## Never

- AI attribution: "Generated with Claude", "Co-Authored-By: Claude", any AI ref
- Unnecessary implementation detail descriptions

## Good examples

```
feat(auth): add login validation
fix(api): resolve query timeout
docs(readme): update install guide
refactor(utils): simplify date logic
test(hooks): add gate_stage edge cases
chore(deps): bump pyyaml to 6.0.2
```

## Bad examples

```
Updated files              <- no description
feat(auth): added login using bcrypt with salt  <- too long, describes HOW
Fix bug                    <- not specific
```

## When splitting commits

Group by type so each commit is atomic:
- `chore(config):` -> config changes
- `chore(deps):` -> dependency updates
- `test:` -> test additions/fixes
- `feat|fix:` -> code changes
- `docs:` -> documentation only
