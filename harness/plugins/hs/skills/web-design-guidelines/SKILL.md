---
name: hs:web-design-guidelines
injectable: true
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[file-or-pattern]"
metadata:
  compliance-tier: knowledge
  keywords: [ui-review, accessibility, ux-audit]
---

# Web Interface Guidelines

Review files for Web Interface Guidelines compliance.

## How It Works

1. Fetch latest guidelines from source URL below
2. Read specified files (or, if no file/pattern arg given, ask user which files to review)
3. Check against all rules in fetched guidelines
4. Output findings in terse `file:line` format

## Guidelines Source

Fetch fresh guidelines before each review:

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Use WebFetch to retrieve latest rules. Fetched content contains all rules and output format instructions.
