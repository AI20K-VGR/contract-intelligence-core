# Solution Design

## Core Principles

Follow these fundamental principles:
- **YAGNI** (You Aren't Gonna Need It) - Don't add functionality until necessary
- **KISS** (Keep It Simple, Stupid) - Prefer simple solutions over complex ones
- **DRY** (Don't Repeat Yourself) - Avoid code duplication

## Design Activities

### Technical Trade-off Analysis
- Evaluate multiple approaches for each requirement
- Compare pros and cons of different solutions
- Consider short-term vs long-term implications
- Balance complexity with maintainability
- Assess implementation complexity vs benefit
- Recommend optimal solution based on current best practices

### Security Assessment
- Identify potential vulnerabilities during design phase
- Consider authentication and authorization requirements
- Assess data protection needs
- Evaluate input validation requirements
- Plan for secure configuration management
- Address OWASP Top 10 concerns
- Consider API security (rate limiting, CORS, etc.)

### Performance & Scalability
- Identify potential bottlenecks early
- Consider database query optimization needs
- Plan for caching strategies
- Assess resource usage (memory, CPU, network)
- Design for horizontal/vertical scaling
- Plan for load distribution
- Consider asynchronous processing where appropriate

### Edge Cases & Failure Modes
- Think through error scenarios
- Plan for network failures
- Consider partial failure handling
- Design retry and fallback mechanisms
- Plan for data consistency
- Consider race conditions
- Design for graceful degradation

### Architecture Design
- Create scalable system architectures
- Design for maintainability
- Plan component interactions
- Design data flow
- Consider microservices vs monolith trade-offs
- Plan API contracts
- Design state management

## A decision that must satisfy several hard constraints at once

When a design call has to hold ≥2 hard constraints that trade off against each other — perf vs back-compat vs a fixed schema —
do NOT settle it in one linear pass. Route to `hs:sequential-thinking` FIRST and lock the call only after an externalized,
revisable Thought trace. Hard route, not a see-also: a wrong multi-constraint call does not stay local, it propagates into
every phase built on top of it, and by then the reasoning that produced it is gone.

Build the plan's verification design on evidence a third party can re-derive — a file:line, a command that reproduces, a
stored artifact — never on the model's own report that a step was done. A model cannot inspect its own execution, and a gate
that only checks whether an artifact is PRESENT cannot tell a real one from a hand-written one. That is why the anchor has to
sit outside the thing being verified.

## Best Practices

- Document design decisions and rationale
- Consider both technical and business requirements
- Think through the entire user journey
- Plan for monitoring and observability
- Design with testing in mind
- Consider deployment and rollback strategies

## Backing

This checklist is a thinking aid for Step 5's solution-design walkthrough (SKILL.md hard-wires it in for a non-trivial design) — it has no gate/script of its own. Load-bearing items route to real harness anchors, not this file, once a decision is made:

- **Security Assessment** — the Security Adversary persona in `references/red-team-gate.md` is the actual gate; findings there need `file:line` evidence (Evidence Filter).
- **Architecture / location decisions** — anchor to existing config via `references/constraint-scan.md` (Step 4), not analogy.
- Every finalized decision still needs a `file:line` anchor per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`; an item on this checklist with no evidence is `[ASSUMED]` (or `[PRIOR]` if it rests on prior/training knowledge), not a settled design choice.
