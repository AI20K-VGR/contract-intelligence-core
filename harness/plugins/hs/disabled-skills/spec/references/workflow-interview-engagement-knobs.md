# Workflow — Interview & Generate — Engagement Knobs

Split out of [workflow-interview.md](workflow-interview.md) to stay under the reference size cap. Same document, same authority — only the location moved. Covers the two PO-facing preference knobs that shape interview verbosity and rigor: `detail_level` and the `interview_rigor` / `action_prompting` engagement profile.

## Detail-level preference (seed once, then consume every prose turn)

`detail_level` controls **how verbose the product-spec output is** — the vision narrative, PRD prose, story
descriptions, AC, and how many interview follow-ups to ask. It is a closed enum (`concise` / `standard` / `verbose`,
default `standard`) designed to live in a `preferences.yaml`, read/written through `scripts/preferences.py`. **That
script is not shipped in this build** — there is no `--set` CLI and no persisted preferences file, so treat every
knob below as a per-session verbal agreement with the PO, not a durable setting. It is conceptually SEPARATE from
`critique_detail_level` (which sizes an `hs:critique` report) — setting one is not meant to affect the other.

### Seed it (once, early)

On the **first** interview for a project (Init Flow), or whenever `preferences.yaml` has no `detail_level` set yet, ask
ONE `AskUserQuestion` near the start and persist the answer:

- **EN:** "How much detail should I put into the spec I write? **Concise** (short, to-the-point acceptance criteria and
  narrative, fewer follow-up questions), **Standard** (the balanced default), or **Verbose** (fuller narrative, more
  examples and rationale)?"
- **VI:** "Bạn muốn spec tôi viết chi tiết tới đâu? **Gọn** (tiêu chí nghiệm thu và mô tả ngắn gọn, đúng trọng tâm, hỏi
  ít hơn), **Tiêu chuẩn** (mức cân bằng mặc định), hay **Đầy đủ** (mô tả dày hơn, nhiều ví dụ và lý lẽ hơn)?"

Map: Concise/Gọn → `concise`, Standard/Tiêu chuẩn → `standard`, Verbose/Đầy đủ → `verbose`. There is no
`preferences.py` write CLI in this build, so hold the answer for the rest of the live session (e.g. note it in
`.session.md`'s free-text body) rather than promising a persisted setting.

Per `GATE-NEVER-ASSUME`: this is a stylistic seed with a documented fallback, so if the PO skips it, default to
`standard` and say so. Do not re-ask within the same session once answered.

### Consume it (every prose-bearing turn)

Before composing prose — vision narrative, PRD body, story description, AC, or the size of an `AskUserQuestion` batch —
use the `detail_level` held for this session (seeded above; there is no `preferences.py` to read it back from) and size
accordingly (LLM-side guidance, like `lang`, not a script knob):

| `detail_level` | product-spec prose |
|----------------|--------------------|
| `concise` | terse AC + narrative, minimal rationale, fewer interview follow-ups |
| `standard` (default) | the current balanced behaviour |
| `verbose` | fuller narrative, more worked examples, richer rationale |

This shapes prose LENGTH only; it never changes structure, frontmatter facts, or the DRY home of any fact.


## Engagement profile (interview rigor + action density)

Two closed-enum knobs designed for the same `preferences.yaml` modulate **how the AI engages** during the
interview — distinct from `detail_level`'s output verbosity. Both default `standard`. As above,
`scripts/preferences.py` is not shipped in this build, so both knobs are session-only, not persisted.

- `interview_rigor` ∈ `light` / `standard` / `deep` (default `standard`) — how hard the interview
  **challenges claims and probes for gaps / edge cases / acceptance-criteria holes**.
- `action_prompting` ∈ `minimal` / `standard` / `proactive` (default `standard`) — the **density of
  suggested next-actions** the AI offers at turn boundaries.

**`interview_rigor` applies at ALL interview levels** — vision, BRD, PRD, epic, AND story — not just the
detailed story/epic flows.

### Orthogonality with `detail_level` (do not conflate)

`detail_level` sizes **verbosity (how long the prose is)**; `interview_rigor` sizes **rigor (how deep the
challenge is)**. They are independent axes: **"concise but deep"** is a valid, expressible combo —
`detail_level: concise` + `interview_rigor: deep` means *terse output, but hard probing* (short AC, yet the
AI still pushes back on every unproven claim and hunts edge cases). Never read `deep` rigor as "write more".

### Consume the knobs

| `interview_rigor` | interview behaviour (all levels) |
|-------------------|----------------------------------|
| `light` | take claims largely at face value; minimal challenge; surface only blocking gaps |
| `standard` (default) | the current balanced challenge + gap/edge/AC probing |
| `deep` | challenge each unproven claim; actively hunt edge cases, missing AC, and contradictions |

| `action_prompting` | next-action density |
|--------------------|---------------------|
| `minimal` | answer the ask; offer a next step only when one is clearly required |
| `standard` (default) | the current balanced "here's the natural next step" closing |
| `proactive` | surface a short menu of relevant next steps at each turn boundary |

These are LLM-side guidance (like `lang` / `detail_level`), not script knobs — they never change structure,
frontmatter facts, or the DRY home of any fact.

### Seed the engagement profile (once, with `detail_level`)

On the **first** interview (Init Flow), or whenever `preferences.yaml` has these keys unset, offer the
posture as **ONE question folded into the existing `detail_level` Init-Flow `AskUserQuestion` batch**
(detail_level + this = 2 questions, well under the 4-per-batch cap); ask it as a separate batch only if some
other seed pushes the batch over 4.

It is a single **posture** choice that sets BOTH knobs together — deliberately *not* two separate questions —
because at the very first turn the PO has not seen the interview yet (asking them to fine-tune "rigor" vs
"prompting" in the abstract is a decision they lack context to make), and in practice the two correlate (a PO
who wants hard challenge usually also wants proactive guidance). The neutral default keeps it skippable
(GATE-NEVER-ASSUME). The rarer split case (e.g. terse-but-rigorous) is handled by per-knob `--set` below, so
the init batch stays short rather than front-loading three preference questions.

- **EN:** "Two quick things about *how* I run the interview — separate from how long the spec text is
  (`detail_level`). **Balanced** *(default)*: I challenge claims and suggest next steps at a normal level.
  **Push-hard**: I rigorously challenge every claim and actively hunt edge cases / missing acceptance
  criteria (`interview_rigor: deep`), AND proactively offer a short menu of next steps at each turn
  (`action_prompting: proactive`). Which do you want? *(Or, if you're just sketching and want me to go
  lighter than Balanced — fewer challenges, fewer prompts — say "light"; and if you want the two split,
  e.g. concise output but rigorous probing, tell me, or set each one later.)*"
- **VI:** "Hai điều nhanh về *cách* tôi chạy phỏng vấn — tách biệt với độ dài chữ của spec (`detail_level`).
  **Cân bằng** *(mặc định)*: tôi chất vấn và gợi ý bước kế ở mức bình thường. **Đào sâu**: tôi vặn kỹ từng
  khẳng định, chủ động truy ca biên / tiêu chí nghiệm thu còn thiếu (`interview_rigor: deep`), VÀ bày sẵn
  menu bước kế mỗi lượt (`action_prompting: proactive`). Bạn muốn kiểu nào? *(Hoặc, nếu bạn chỉ phác thảo và
  muốn tôi nhẹ hơn Cân bằng — ít vặn, ít gợi ý — cứ nói "nhẹ"; còn nếu muốn tách riêng hai cái, vd chữ ngắn
  gọn nhưng vẫn vặn kỹ, thì nói, hoặc chỉnh từng cái sau.)*"

Map: **Balanced / Cân bằng** → leave both at `standard`; **Push-hard / Đào sâu** → both knobs go to their
rigorous end (`interview_rigor=deep`, `action_prompting=proactive`); **"light" / "nhẹ"** (the relax opt-in
surfaced by the hint) → both go to their relaxed end (`interview_rigor=light`, `action_prompting=minimal`).
There is no `preferences.py --set` CLI in this build, so this choice holds for the rest of the live
session only — say so rather than promising it survives to the next session.

For the split case, hold either knob alone — e.g. concise-but-rigorous is `interview_rigor=deep` with
`action_prompting` left at `standard`; quieter next-step prompts is `action_prompting=minimal` alone. The
end-of-session adjustment (`workflow-interview.md` → Closing the Loop) is the *evidence-driven* relax path
(it may propose `light`/`minimal` after seeing the PO wave off probing); this init hint is the *upfront*
relax opt-in for a PO who already knows they're only sketching.

Per `GATE-NEVER-ASSUME`: defaults are neutral `standard`, so if the PO skips the question, default to
`standard` and **say so** — never silently assume a strict posture. Do not re-ask within the same session
once answered.

