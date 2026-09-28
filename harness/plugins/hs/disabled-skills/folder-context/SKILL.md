---
name: hs:folder-context
description: Create a compact subfolder CLAUDE.md and linked AGENTS.md for durable local conventions. Use when a folder needs agent context beyond the project root.
user-invocable: true
when_to_use: Invoke for subfolder-scoped agent context, not root project instructions or general docs.
category: utilities
keywords: [claude-md, agents-md, context, folder, conventions]
argument-hint: "<target-folder>"
injectable: false
allowed-tools: [Read, Glob, Grep, Write, Bash]
metadata:
  compliance-tier: workflow
---

# Folder Context

Create durable context only for a subfolder that carries decisions, conventions,
or ongoing work a future agent cannot reliably infer. This skill never edits the
root CLAUDE.md or root AGENTS.md.

## Workflow

1. Confirm the target is a subfolder and inspect its key source, configuration,
   Markdown, and local context files.
2. Apply a sanity gate: do not create files for static reference folders or
   folders whose context can be discovered on demand.
3. Propose a grouped outline and wait for user confirmation before writing.
4. Write a compact target-folder CLAUDE.md using only evidence from the folder
   or explicit user decisions. Omit empty sections.
5. Create target-folder AGENTS.md as a symlink to CLAUDE.md. If symlinks are
   unavailable, create a one-line pointer file that names CLAUDE.md and tell the
   user about the fallback.
6. When the user edits the context file, re-read it and flag contradictions.
   Never revert their edits without instruction.

## Useful Sections

- Purpose and essential files with one-line roles
- Constraints, especially explicit MUST NOT rules
- Conventions and naming
- Locked decisions with dates
- Context needed across sessions

Keep file content compact, specific, and local. Use bullets rather than a file
tree or generic project documentation.

## Boundaries and Safety

- Use hs:docs for project documentation under docs.
- Do not duplicate root instructions, invent constraints, write credentials, or
  create context files outside the confirmed target.
- Respect the user’s existing local instructions before adding new context.
