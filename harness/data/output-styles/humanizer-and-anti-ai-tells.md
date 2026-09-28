# humanizer-and-anti-ai-tells — write so it does not read like a machine

Apply this when the harness GENERATES human-facing prose: research reports,
brainstorm write-ups, review findings, plan narration, docs. It does not apply
to instruction files (skills, references, rules) — those are English by design.
Resolve the output knobs first with `python3 harness/scripts/output_config.py --resolved`
(see `harness/rules/output-rendering.md`): when `language: vi`, the Vietnamese
translation-tell table below is the highest-value section; when `language: en`,
lean on the banned-vocabulary list.

**Default off.** `humanize` defaults to OFF (token-spend). Run this cosmetic pass
only when the resolved `humanize` is true, or when publishing a report externally,
or when the user asks. The readability layer (the Vietnamese calque table) is still
worth a soft internal pass, but the full anti-AI-tell cleanup is opt-in.

Binding vs advisory: for internal reports and files (the `plans/` and `docs/`
trees the team and agents read) this rule is advisory, a note rather than a gate.
The cosmetic anti-AI layer, above all the em/en dash ban, only matters when prose
is published outside the repo or must pass as human-written; apply it in full
only when (a) a report is published externally or (b) the user asks. The
readability layer (the Vietnamese calque table, robotic rhythm) is worth a soft
pass even internally because it makes reports clearer, but it still never blocks.
Stripping em and en dashes is mechanical, so run the fixer instead of rewriting
by hand: `python3 harness/scripts/humanize_dashes.py <report> --fix`.

The rule humanizes *prose only*. It never touches the substance: every finding,
every evidence reference (`file:line`, IDs, SHAs), every number, and every
verbatim quote survives unchanged. You are removing machine-stiffness and
translationese, not softening the conclusion.

**Audience fence:** `audience` (0–5) adjusts the prose register of the explanation
layer only — how plain or dense the surrounding prose is. It never alters evidence:
`file:line` anchors, IDs, SHAs, numbers, verbatim quotes, and code blocks are
invariant at every audience level. A report written for audience 0 and the same
report written for audience 5 must contain identical evidence tokens; only the
prose scaffolding changes. This rule, like `language`, humanizes prose only — it
does not touch the evidence layer that the fence protects.

---

## Vietnamese translation tells (đừng dịch sống)

When the output language is Vietnamese, these word-for-word calques are the most
common way generated text reads machine-made. Replace them:

| Đừng viết | Viết thế này |
|---|---|
| làm tươi, quét tươi, dữ liệu tươi | quét lại từ đầu, kiểm tra ngay tại chỗ, số liệu mới nhất |
| đường gốc, trải nghiệm gốc | ứng dụng riêng, trải nghiệm trên ứng dụng |
| đảm bảo rằng / đảm bảo là | để chắc chắn, cho chắc |
| nhằm mục đích / với mục đích | để |
| một cách + tính từ ("một cách rõ ràng") | bỏ "một cách", viết thẳng "rõ ràng" |
| điều này cho phép / việc này giúp | nhờ đó, như vậy |
| nó đóng vai trò như / nó hoạt động như | nó là, nó làm |
| tận dụng, tối ưu hóa, mạnh mẽ, liền mạch, toàn diện | dùng từ cụ thể đúng nghĩa, đừng sáo rỗng |
| việc + động từ hóa lê thê ("việc đăng nhập của người dùng") | rút gọn ("người dùng đăng nhập") |

Vietnamese prose still gets a voice: vary the rhythm, state a real opinion, sound
like a sharp engineer, not a textbook.

---

## The human-voice layer (check FOR this, not just against tells)

Prose can be free of every banned word and still read like a report engine:
every sentence the same long even cadence, abstract where it could be concrete,
the verdict buried under qualifiers. Push it the other way — a concrete image
the reader can see, a short blunt sentence before the long one, the verdict
stated flat and then backed. Have an opinion and stand behind it. Let a little
mess in; perfect uniform structure is what feels algorithmic.

## Content patterns

1. Undue emphasis on significance. Cut: "stands as", "is a testament", "plays a
   pivotal/crucial/key role", "underscores its importance", "marks a shift",
   "evolving landscape".
2. Superficial "-ing" analyses. Replace "symbolizing X, reflecting Y,
   contributing to Z" with direct statements.
3. Promotional language. Cut: "boasts", "vibrant", "rich", "seamless",
   "robust", "groundbreaking", "powerful".
4. Vague attribution / weasel words. Replace "experts argue", "it is widely
   believed" with a named source, a file, or a measured number.
5. Overused AI vocabulary. Avoid: additionally, align with, crucial, delve,
   emphasize, enhance, foster, garner, highlight (verb), interplay, intricate,
   key (adj), landscape (abstract), leverage, pivotal, showcase, tapestry,
   testament, underscore, valuable, vibrant.
6. Copula avoidance. Use "is"/"has", not "serves as", "stands as", "boasts",
   "features".
7. Negative parallelisms. Cut "not only X but also Y", "it's not just X, it's
   Y". State the point as a real clause.
8. Rule-of-three overuse. Do not force ideas into groups of three to look
   comprehensive.
9. Elegant variation (synonym cycling). Pick one term and repeat it; do not
   cycle "the loader / the reader / the parser" for one thing.
10. Passive voice and subjectless fragments. Name the actor: "you don't need a
    config file", not "no config needed".

## Style patterns

11. Em and en dashes: cut them all. The final text contains no `—` and no `–`.
    Replace each with a period, comma, colon, parentheses, or a restructure.
    Catch spaced em dashes and double hyphens used the same way. Scan the final
    output for `—` and `–`; any hit means it is not done. This step is mechanical:
    when the dash ban applies (external publish or on request), run `python3
    harness/scripts/humanize_dashes.py <report> --fix` rather than editing each by
    hand, then eyeball the few spots that wanted a colon.
12. Overuse of boldface, especially around acronyms. Remove mechanical emphasis.
13. Inline-header vertical lists ("- **Thing:** sentence") piled up where
    flowing prose reads better. Merge them.
14. Title Case headings → sentence case.
15. Decorative emojis in headings and lists. Remove them. (A fixed status marker
    that a gate or report format requires is a signal, not decoration; leave it.)
16. Curly quotation marks → straight quotes.

## Filler, hedging, signposting

17. Filler phrases. "In order to" → "to". "Due to the fact that" → "because".
    "At this point in time" → "now". "Has the ability to" → "can".
18. Excessive hedging. "Could potentially possibly be argued" → "may be".
19. Generic positive conclusions. Replace "the future looks bright" with a
    specific fact or a concrete next step.
20. Persuasive authority tropes. Cut "the real question is", "at its core",
    "what really matters", "fundamentally".
21. Signposting. Cut "let's dive in", "here's what you need to know", "without
    further ado". Just say the thing.
22. Fragmented headers. Do not follow a heading with a one-line sentence that
    only restates the heading.

## What NOT to flag

A clean human can hit several patterns with no AI involvement. Do not gut
legitimate prose. On their own these are not tells: perfect grammar; mixed
casual and formal registers; plain dry prose without the specific tells; formal
vocabulary not on the list above; a single transition word; one em dash alone.
Look for clusters, not isolated hits. Never "fix" a verbatim quote, an evidence
ID, a file path, or a config key — those are the citation, not a tell.

## Signs of human writing (preserve these)

Specific, hard-to-fabricate detail. Mixed feelings and unresolved tension.
First-person editorial choices the writer can defend. Variety in sentence
length. Genuine asides and self-corrections. When you see these, lean toward
leaving the prose alone; over-editing destroys what makes it sound human.

## Process (run both passes)

1. Read the draft and mark every instance of the patterns above.
2. Rewrite. Check it reads naturally aloud, varies sentence length, prefers
   concrete detail and simple "is/has" constructions, and keeps the configured
   output language.
3. Ask once: "what here still reads obviously AI or obviously translated?" Name
   the remaining tells (a banned word, an em dash, a calqued Vietnamese phrase,
   a robotic rhythm, a forced triple) and fix them.
4. Produce the final text in the configured language with the same substance. For
   an external publish or an explicit request, also strip em/en dashes with
   `python3 harness/scripts/humanize_dashes.py <report> --fix` and confirm none remain.

Two tools back this up. `humanize_dashes.py <report> --fix` deterministically
removes em/en dashes (dry-run by default; `--replacement {comma,colon,period}`).
`check_report_language.py <report> [--expected en|vi]` flags language mismatch,
banned vocabulary, dashes, and Vietnamese calque tells by line; it is advisory
(exits 0, never edits) and, with `--base-ref`, blocks in CI only on a language
mismatch — tells stay advisory.

`audience_fence.py a.md b.md` is the on-demand checker for evidence-token
invariance across audience levels: it extracts evidence tokens (file:line, IDs,
SHAs, numbers, backtick spans) from two report variants and exits non-zero when
they differ. On-demand advisory only — not a gate, not a CI blocker; run it when
you have produced a simplified summary alongside the full report and need to
confirm no evidence was dropped or altered.

## Source

Based on the `blader/humanizer` skill (MIT) and [Wikipedia: Signs of AI
writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).
