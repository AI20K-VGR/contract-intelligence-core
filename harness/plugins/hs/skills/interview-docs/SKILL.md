---
name: hs:interview-docs
description: Extract a user's vision and decisions into durable project documents through a guided interview. Use for README, ADR, strategy, principles, and structured-doc authoring.
user-invocable: true
when_to_use: Invoke when the user's answers, not AI proposals or code inspection, should become the document.
category: utilities
keywords: [interview, documentation, adr, strategy, vision]
argument-hint: "<vision | document-path | topic>"
injectable: false
allowed-tools: [Read, Glob, Grep, Write, Bash, AskUserQuestion]
metadata:
  compliance-tier: workflow
---

# Interview Docs

Turn user knowledge, taste, and decisions into maintained documents.
Skill does not invent content, prioritize an unordered list, or derive docs from source code.

## Select a Mode

- Vision mode: project vision, README direction, decision capture.
- Structured-doc mode: one user-authored document (principles, strategy,
  reviews, a framework).
- Fits both modes -> ask one concise question before writing.

## Vision Mode

1. Read README.md and the existing DEC ledger (docs/decisions.md) before asking
   anything.
2. Ask a batch of five high-variety questions unless the user requests another
   number or a focused area.
3. After every answer, re-read the affected document and patch the user’s words
   into README.md before processing the next answer.
4. Keep README.md to vision. A durable decision the user makes belongs in the
   DEC ledger — record it with hs:remember (decision_register.py), not in an
   invented ADR file. Capture only what the user has explicitly decided.
5. Continue until the user ends the interview. Keep replies concise, plain
   English.

## Structured-Doc Mode

1. Read nearby documents; create a minimal skeleton once.
2. Ask exactly one specific, open question.
3. Wait for the answer, re-read the target section, and patch the document
   before the next question.
4. Treat a user-provided list as an unordered set. Ask explicitly before
   assigning rank, sequence, or priority.
5. Preserve user wording and edits. Never overwrite an existing document or
   add speculative sections.

## Boundaries and Safety

- Use hs:brainstorm when the AI should propose options; hs:docs when
  documentation should derive from code.
- Do not write secrets, personal data, or credentials into docs.
- Record only a decision the user has explicitly made; durable decisions belong
  in the DEC ledger (hs:remember), not invented here.
