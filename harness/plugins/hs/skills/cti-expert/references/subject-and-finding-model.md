# Subject, Connection & Finding Model

## 4. Subject & Connection Model

Reference: `engine/case-schema.json`, `engine/subject-registry.md`

### Subject Types

| Type | Emoji | Examples |
|------|-------|---------|
| Person | 👤 | Full name, alias |
| Username | @ | Social handle |
| Email | 📧 | Address, domain |
| Domain | 🌐 | Site, subdomain |
| IP Address | 🖥 | IPv4, IPv6 |
| Organization | 🏢 | Company, group |
| Phone | 📱 | E.164 format |
| Location | 📍 | GPS, address |
| Asset | 📦 | Document, image |
| Event | 📅 | Dated occurrence |
| Device | 🖥️ | IoT device, server, workstation |
| Image | 🖼️ | Photograph, screenshot |
| Crypto Address | 💰 | Bitcoin, Ethereum wallet |
| Custom | 🏷️ | User-defined entity type |

### Connection Types

```
owns         — domain, email, or asset ownership
uses         — platform account or tool usage
works_at     — employment or affiliation
linked_to    — general association
alias        — same identity, different handle
communicated_with — observed contact
```

### Finding Trust Scores

| Score | Label | Meaning |
|-------|-------|---------|
| 5 | PRIMARY | Authoritative or official source |
| 4 | DERIVED | Confirmed by 2+ independent sources |
| 3 | CONFIRMED | Single reliable source, verified |
| 2 | ANECDOTAL | Reported but unverified |
| 1 | CONTESTED | Conflicting data exists |

### Source Reliability Scale

Complements numeric trust scores with source-level grading. Trust score rates finding content; source reliability rates the source itself.

| Grade | Label | Typical Sources |
|-------|-------|-----------------|
| A | Completely Reliable | Official registries, government records |
| B | Usually Reliable | Established outlets, corporate sources |
| C | Fairly Reliable | Known blogs, industry publications |
| D | Not Usually Reliable | Anonymous forums, unverified claims |
| E | Unreliable | Known disinformation, fabricated content |
| F | Cannot Be Judged | Insufficient information to assess |

### Confidence Levels

| Level | Label | Use When |
|-------|-------|---------|
| VERIFIED | Direct observation, primary source | |
| STRONG | Multiple corroborating sources | |
| MODERATE | Single reliable source | |
| WEAK | Circumstantial or inferred | |
| TENTATIVE | Analyst deduction only | |
| CHALLENGED | Contradicted by other findings | |

### Map Rendering (ASCII Mandatory)

**ALL visualization commands produce ASCII box-drawing art by default.** This includes `/graph`, `/render entities`, `/render network`, `/render timeline`, `/render risk`, `/pathfind`, and `/show-connections`. Mermaid available only with explicit `--mermaid` flag.

**Why ASCII-first:** Universal terminal compatibility, renders correctly in .md and .docx exports, no external renderer dependency.

```
┌─────────────────────────────┐   owns   ┌───────────────────────────┐
│ 👤 John Doe          [3/5] │══════════▶│ 🌐 example.com     [4/5] │
└─────────────────────────────┘           └───────────────────────────┘
         │ works_at                       │ hosted_on
         ▼                                ▼
┌─────────────────────────────┐  ┌───────────────────────────┐
│ 🏢 Acme Corp         [4/5] │  │ 🖥 203.0.113.10    [4/5] │
└─────────────────────────────┘  └───────────────────────────┘
```

**Connection arrows:** `═══▶` owns · `───▶` confirmed · `···▶` inferred · `←─▶` bidirectional · `─·─▶` alias · `╌╌▶` works_at
**Box styles:** `┌──┐` confirmed · `┌ ─ ┐` unverified · `╔══╗` target
**Badge:** `[n/5]` trust score · emoji prefix = entity type

---

## 5. Finding Framework

Reference: `engine/finding-framework.md`, `engine/conflict-resolver.md`

Every finding logged via `/record-finding` captures:

```
Source URL / method
Collection method (browser | search | fetch | manual)
Trust score (1–5)
Confidence level (VERIFIED → CHALLENGED)
Timestamp
Linked subjects
```

**Conflict detection** (`engine/conflict-resolver.md`): When two findings about the same subject contradict each other, the system flags a CONTESTED state. Both findings are preserved. Resolution options: accept one, mark both TENTATIVE, or log the conflict as its own finding.

**Deviation detection** (`analysis/deviation-detector.md`): Flags behavioral anomalies — account creation gaps, platform presence inconsistencies, metadata mismatches.

**Weight engine** (`analysis/weight-engine.md`): Aggregates trust scores across findings to compute subject-level confidence.

---

