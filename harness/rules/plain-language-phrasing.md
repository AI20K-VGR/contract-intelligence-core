# Plain-language phrasing (on-demand)

Load whenever `hs:plan`/`hs:discover` phrase a question back to a non-technical user —
AskUserQuestion prose the user reads as a specialist would rather not.

### jargon-swap table

| Jargon | Plain swap |
|---|---|
| idempotent | safe to run twice, same result |
| race condition | two things trying to happen at once, first one wins by luck |
| schema | the shape/fields a record must have |
| rollback | undo back to the last known-good state |
| latency | how long a response takes to come back |
| throughput | how much work gets done per second |
| regression | something that used to work broke |
| migration | moving data/structure from the old shape to the new one |

Swap every jargon term the table covers before the question reaches the user; extend the
table (do not hand-edit `docs/glossary.yaml` from here) when a new recurring term shows up.

### 25-word cap

The QUESTION SENTENCE itself (the literal thing AskUserQuestion asks) stays under 25
words — the cap does not apply to surrounding context/options/rationale, only the
question. A 25+-word question reads as a wall of text the user skims past instead of
answering precisely.

### scenario-before-question

Ground an abstract choice in one concrete example BEFORE asking — "if a user uploads a
10MB file while offline, should it queue or fail immediately?" beats "what's the offline
upload behavior?" cold. The scenario carries the meaning; the question just picks a side.

### rephrase-fallback

If the user's answer shows the question was misunderstood (answers a different axis
than asked), do not re-ask the same phrasing louder — rephrase using a NEW
scenario/analogy, since repeating unclear wording produces the same confusion twice.

## Examples

<!-- evidence: vi sample -->
Ví dụ câu hỏi: "Khi mất mạng giữa lúc tải file lên, hệ thống nên xếp hàng chờ hay báo lỗi
ngay?" — everything else in this rule stays English; this is the one narrow exception.
