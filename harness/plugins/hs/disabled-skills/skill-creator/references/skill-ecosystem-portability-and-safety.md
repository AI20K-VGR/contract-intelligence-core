# Skill Ecosystem, Portability, and Safety

## Why Use a Skill

A skill is a versioned package of instructions plus optional scripts, references,
and assets. It separates reusable workflow guidance from the always-loaded
system prompt.

| Alternative | Failure mode | Skill response |
|---|---|---|
| System-prompt stuffing | Context cost grows for every task | Load only when the task matches |
| Repeating instructions each session | Guidance drifts and is not reviewable | Version the workflow beside code |
| Fine-tuning for local process | Slow, opaque, and costly to change | Edit and review a small artifact |
| Tools without guidance | Capability exists but usage is inconsistent | Pair tools with a tested workflow |

Use a skill when the gap is repeatable process or context. Do not create one for
general model knowledge, a single user preference, or a workflow with no stable
boundary.

## Cross-Runtime Portability

Keep portable content to a small, conventional folder: SKILL.md plus only the
scripts, references, and assets the workflow needs. Portability is a design goal,
not a promise that every runtime implements every frontmatter field or tool in
the same way.

Before publishing across runtimes:

1. Keep the name, description, relative paths, and basic Markdown workflow
   portable.
2. Isolate runtime-specific commands and capabilities behind an explicit
   availability check.
3. Avoid assuming a particular sandbox, shell, model, install root, or
   authentication method.
4. Test discovery and execution in each runtime that the project claims to
   support.
5. Document a safe fallback or fail clearly when a required runtime feature is
   unavailable.

## Third-Party Skill Safety

Treat unfamiliar skill content as untrusted input, including Markdown prose.

1. Pin the source repository and commit before import.
2. Read every source file before adapting it. Do not execute copied commands,
   scripts, or embedded instructions as part of the review.
3. Inspect scripts for network access, file writes outside their intended scope,
   subprocess execution, and secret handling.
4. Inspect references for instruction override, data exfiltration, and
   typosquatted dependencies.
5. Re-author the minimum useful workflow. Retain attribution and license text
   where substantial source text remains.
6. Test under least privilege with safe fixtures before publishing.

Never put secrets, access tokens, customer data, or machine-specific private
paths in skill text, examples, logs, or bundled assets.
