# Contributing

These rules are enforced by GitHub rulesets and the `pr-guard` check where possible; the rest is
team discipline and is part of the evaluation (teamwork counts).

## Branches

| branch | purpose | protection |
|---|---|---|
| `main` | releasable code, demoed at sprint reviews | PR only, from `develop`, `release/*` or `hotfix/*`, 2 approvals, squash merge, linear history |
| `develop` | integration branch, default target of PRs | PR only, 2 approvals, any merge method |
| `<type>/<short-description>` | your work | must match the naming rule below |

Branch naming (enforced on push):

```
^(feat|feature|fix|docs|chore|refactor|test|hotfix|release)/[a-z0-9._-]+$
```

Examples: `feature/backend-upload-api`, `feat/ai-clause-extractor`, `fix/bbox-offset-page-2`,
`docs/prd-conflicts`, `hotfix/batch-job-crash`, `release/v0.1.0`. Use lowercase, hyphens, no spaces, no Vietnamese diacritics.

## Pull requests

- Target `develop`. Only release PRs (`develop → main`, `release/* → main`) and `hotfix/*` PRs target `main`.
- Title follows Conventional Commits **with a scope** naming the subsystem:

  ```
  <type>(<scope>): <summary>
  type  = feat | fix | docs | chore | refactor | test | ci
  scope = frontend | backend | ai | docs | infra | repo   (ai = ai-service/)
  ```

  Examples: `feat(ai): clause segmentation for Article > Clause > Point`,
  `fix(backend): batch job status stuck in queued`, `docs(docs): PRD v1`.
- Fill in the PR template: what changed, how to test, screenshots for UI, and which document or
  epic it belongs to.
- Keep PRs small (one feature or fix). A PR that touches two subsystems needs a reviewer from each.
- Requirements to merge: 2 approvals from teammates, all review threads resolved, `pr-guard`
  green, branch up to date with the base. A new push dismisses previous approvals.
- Use **squash merge** into `main`. Into `develop` any method is allowed; prefer squash for
  noisy branches.
- Delete your branch after merge (GitHub does it automatically).

## Reviewing

- Review within one working day. Reviewing is part of your work, not a favour.
- Everyone owns every folder (see `.github/CODEOWNERS`), so any teammate can approve; the
  subsystem's primary should be one of the two reviewers when the change is not trivial.
- Ask questions in review threads and resolve them yourself only after the author answered.
- Approve only when you ran it or read it fully. "LGTM" without a comment on a non-trivial PR
  will be raised at the sprint review.

## Data and secrets

- **Never commit contracts, scans or annexes** (real, test or generated) or any archive of
  them. `pr-guard` fails a PR adding `.pdf .doc .docx .tif .tiff .jpg .jpeg .png .zip .rar .7z`
  outside `docs/assets/` (diagrams and screenshots for documents only).
- Never commit API keys, tokens or `.env` files. GitHub push protection blocks known secret
  formats; anything that slips through must be rotated immediately and reported to the mentor.
- Data used in evaluation lives on the shared OneDrive folder; code reads it from a path given
  by an environment variable, never from inside the repository.

## Issues and labels

- One issue per task or bug, labelled with the subsystem (`frontend`, `backend`, `ai` for `ai-service/`, `docs`,
  `infra`) and the kind (`bug`, `feature`, `task`, `blocked`).
- Link the issue from the PR (`Closes #12`).
- The sprint tracker (Excel on OneDrive) stays the source of truth for planning; GitHub issues
  carry the technical detail.
