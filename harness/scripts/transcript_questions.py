#!/usr/bin/env python3
"""transcript_questions.py — find the most-recent still-open AskUserQuestion in a
Claude Code session transcript.

A compaction summary keeps the conversation's gist but can flatten a question the
user was still weighing into a settled decision. The fix needs no model-written
marker: CC already records every turn to a jsonl transcript. This helper reverse-
scans the transcript tail for the LAST AskUserQuestion (AUQ) tool_use and decides
whether it is still open:

  - no answer recorded (AUQ was the last thing before compaction) -> unanswered
  - answered with text that matches an offered option label       -> clean (skip)
  - answered with free text that matches no label (a redirect)    -> free_text

Only the most-recent AUQ matters — earlier questions are trusted as settled. The
read is bounded to the last 256 KiB (mirrors emit_session_summary / reinject_stop_
context); the answer is almost never the last line (hooks + assistant turns fire
after it, before compaction), hence the reverse scan rather than a tail-line peek.

Transcript shape pinned from real transcripts on CC v2.1.195 (see the module test
for the exact records). This format is CC-internal and version-fragile — "scripts
parsing these can break on any release" — so EVERY path fails open: a missing
file, a torn line, an unfamiliar shape, or any exception yields None. The caller
(pending_decisions_resurface) treats None as "stay silent", so shape drift in a
future CC release degrades to today's behavior, never to a crash.
"""
import json
import os

# Sentinel for "a tool_result exists for this AUQ but no usable structured
# answers map was found" — distinct from both None (no answer at all) and any
# real answer string/list, so _classify can tell "answered opaquely" (settled,
# skip) apart from "typed something that isn't an offered label" (free_text).
_ANSWERED_OPAQUE = object()

# Bounded tail read — the most-recent interview fits well within this; we never
# slurp a multi-MB transcript. Same constant as emit_session_summary.read_tail /
# reinject_stop_context._TAIL_BYTES.
TAIL_BYTES = 256 * 1024


def read_tail(path):
    """Return the last TAIL_BYTES of `path` decoded with errors='replace', or ""
    on any failure (missing/unreadable file). Never raises."""
    if not path:
        return ""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            chunk = fh.read()
        return chunk.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — missing/huge/unreadable transcript -> silent
        return ""


def _iter_records(text):
    """Yield each parseable JSON object from the tail text; skip torn/partial lines
    (the first line of a mid-file tail is frequently truncated)."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:  # noqa: BLE001 — a torn/partial tail line is non-fatal
            continue
        if isinstance(rec, dict):
            yield rec


def _content_blocks(rec):
    """The message.content list of a record, or [] when absent/odd-shaped."""
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return []
    content = msg.get("content")
    return content if isinstance(content, list) else []


def _find_last_auq(records):
    """Reverse-scan for the most-recent AskUserQuestion tool_use. Return
    (tool_use_id, auq_input) or (None, None). auq_input is the tool_use `input`
    dict (carries `questions`)."""
    for rec in reversed(records):
        for blk in _content_blocks(rec):
            if (isinstance(blk, dict)
                    and blk.get("type") == "tool_use"
                    and blk.get("name") == "AskUserQuestion"):
                inp = blk.get("input")
                if isinstance(inp, dict):
                    return blk.get("id"), inp
    return None, None


def _find_answer(records, tool_use_id, question_text):
    """Find the answer to the AUQ identified by tool_use_id. Prefer the structured
    top-level toolUseResult.answers dict (keyed by question text); that is the
    clean source. Returns the answer (str or list for multiSelect), or None when
    no answer record is present (AUQ still open)."""
    if not tool_use_id:
        return None
    for rec in records:
        # The answer record carries a tool_result block with the matching id...
        matched = any(
            isinstance(blk, dict)
            and blk.get("type") == "tool_result"
            and blk.get("tool_use_id") == tool_use_id
            for blk in _content_blocks(rec)
        )
        if not matched:
            continue
        # ...and a sibling toolUseResult.answers dict keyed by question text.
        tur = rec.get("toolUseResult")
        if isinstance(tur, dict) and isinstance(tur.get("answers"), dict):
            answers = tur["answers"]
            if question_text in answers:
                return answers[question_text]
            # single-question AUQ: fall back to the lone answer value
            if len(answers) == 1:
                return next(iter(answers.values()))
        # tool_result present but no structured answers -> treat as answered-opaque;
        # a present-but-unparseable answer is safer read as "answered" than as
        # "unanswered" (avoids re-surfacing a question the user already closed).
        # Use the dedicated sentinel, not "" — an empty string is itself a value
        # _classify would compare against the offered labels and (finding no
        # match) misclassify as a typed free-text redirect.
        return _ANSWERED_OPAQUE
    return None


def _option_labels(auq_input):
    """The option labels of the FIRST question in an AUQ input dict."""
    questions = auq_input.get("questions") if isinstance(auq_input, dict) else None
    if not isinstance(questions, list) or not questions:
        return None, []
    q0 = questions[0]
    if not isinstance(q0, dict):
        return None, []
    labels = [o.get("label") for o in q0.get("options", [])
              if isinstance(o, dict) and isinstance(o.get("label"), str)]
    return q0.get("question"), labels


def _classify(auq_input, answer):
    """Pure decision (no I/O). Given an AUQ input dict and its answer (None = no
    answer recorded), return the open-question dict or None when settled.

    None      -> the AUQ is settled (clean option pick) — no re-surface.
    dict      -> {"question", "options", "answer", "reason"} with reason in
                 {"unanswered", "free_text"}.
    """
    question, labels = _option_labels(auq_input)
    if question is None:
        return None  # shape we don't recognize -> fail open (silent)

    base = {"question": question, "options": labels}

    if answer is None:
        return {**base, "answer": None, "reason": "unanswered"}

    if answer is _ANSWERED_OPAQUE:
        return None  # answered but opaque -> settled, skip (never re-surface)

    if _is_clean_pick(answer, labels):
        return None  # clean option pick -> settled, skip

    # answered, but the answer matches no offered label -> a typed redirect.
    return {**base, "answer": answer, "reason": "free_text"}


def _is_clean_pick(answer, labels):
    """True when the answer is exactly one (single-select) or only (multiSelect)
    offered labels — the clean-pick signature confirmed across real transcripts."""
    label_set = set(labels)
    if isinstance(answer, list):
        return bool(answer) and all(a in label_set for a in answer)
    return answer in label_set


def last_unresolved_question(transcript_path):
    """Public entry. Return the open-question dict for the most-recent AUQ when it
    is still open, else None. Any error / missing file / unknown shape -> None
    (fail-safe silent)."""
    try:
        records = list(_iter_records(read_tail(transcript_path)))
        if not records:
            return None
        tool_use_id, auq_input = _find_last_auq(records)
        if auq_input is None:
            return None
        question, _ = _option_labels(auq_input)
        answer = _find_answer(records, tool_use_id, question)
        return _classify(auq_input, answer)
    except Exception:  # noqa: BLE001 — extractor must never raise into a hook
        return None
