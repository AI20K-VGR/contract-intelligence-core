# Markdown Body Templates — general docs

Templates for general documentation types. SDLC-artifact templates (plan/phase/report/journal): `markdown-body-templates.md`.

## Doc (docs/*.md)

```markdown
# {Document Title}

## Overview
{brief description of what this document covers}

## {Section 1}
{content}

## {Section 2}
{content}

## References
- {link or reference}
```

No frontmatter needed for simple docs. Keep sections logical, scannable.

## ADR (docs/decisions/)

```markdown
# ADR-{NNN}: {Decision Title}

- **Status:** proposed | accepted | deprecated | superseded
- **Date:** YYYY-MM-DD
- **Deciders:** {who made this decision}

## Context
{what is the issue that motivates this decision}

## Decision
{what is the change being proposed/made}

## Consequences
### Positive
- {benefit}
### Negative
- {trade-off}

## Alternatives Considered
### {Alternative 1}
- **Pros:** {pros}
- **Cons:** {cons}
- **Why rejected:** {reason}
```

## Changelog

```markdown
# Changelog

## [{version}] - YYYY-MM-DD

### Added
- {new feature}

### Changed
- {modification to existing feature}

### Fixed
- {bug fix}

### Removed
- {removed feature}

### Deprecated
- {feature marked for future removal}
```

Follow [Keep a Changelog](https://keepachangelog.com) format.

## README

```markdown
# {Project Name}

{one-line description}

## Quick Start

{minimal steps to get running}

## Usage

{how to use the project}

## Development

{setup for contributors}

## Contributing

{contribution guidelines}

## License

{license info}
```

## Guide

```markdown
# {Guide Title}

## Prerequisites
- {requirement}

## Steps

### Step 1: {Name}
{instructions}

### Step 2: {Name}
{instructions}

## Troubleshooting

### {Common issue}
**Problem:** {description}
**Solution:** {fix}

## FAQ

### {Question}
{Answer}
```

## Spec / Requirements

```markdown
# {Spec Title}

## Overview
{what this spec defines}

## Requirements

### Functional
| ID | Requirement | Priority |
|----|------------|----------|
| F1 | {requirement} | must | should | could |

### Non-functional
| ID | Requirement | Metric |
|----|------------|--------|
| NF1 | {requirement} | {measurable target} |

## Constraints
- {constraint}

## API / Interface
{interface definitions, endpoints, schemas}

## Acceptance Criteria
- [ ] {criterion}
- [ ] {criterion}
```
