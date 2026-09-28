#!/usr/bin/env python3
"""pending_decisions_resurface.py — SessionStart hook: after a compaction,
re-surface the most-recent still-open AskUserQuestion so a summary cannot quietly
bury a decision the user was still weighing.

Compaction keeps the conversation's gist but can flatten a pending question into a
settled one (observed: session c87a7230). On SessionStart with source=="compact"
this hook reads the transcript (via transcript_questions, which CC itself wrote —
no model-written marker) for the last AUQ; if it is unanswered or answered with a
typed redirect, it injects a one-shot additionalContext telling the model to
re-ask before acting. A clean option pick, no open question, or any error -> silent.

Mechanism lock — do NOT conflate with the Stop-hook re-inject (reinject_stop_
context): a SessionStart additionalContext only DECORATES the next turn, it does
NOT force one (a /compact is self-healing; binary-verified that only a Stop
additionalContext re-invokes the model). So this hook needs no goal-active gate and
cannot run a loop away — it speaks once into the post-compaction turn the user was
going to take anyway.

Class is `nudge` (advisory, fail-open): it never blocks, never exits 2; disable via
harness-hooks.yaml (pending_decisions_resurface: {enabled: false}) -> silent.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_HERE)
sys.path.append(os.path.join(os.path.dirname(_HERE), "scripts"))

import hook_runtime          # noqa: E402
import transcript_questions  # noqa: E402

HOOK_CLASS = "nudge"
NAME = "pending_decisions_resurface"


def _build_context(res: dict) -> str:
    """The additionalContext nudge: name the open question, its options, and why it
    is still open, then tell the model to re-ask before letting the summary stand."""
    options = res.get("options") or []
    lines = [
        "[Sau khi nén hội-thoại — RÀ LẠI câu hỏi gần nhất TRƯỚC khi viết plan/brief]",
        "Câu hỏi: %s" % res.get("question", ""),
    ]
    if options:
        lines.append("Lựa-chọn đưa ra: %s" % " | ".join(str(o) for o in options))
    if res.get("reason") == "unanswered":
        lines.append("Bạn CHƯA trả lời câu này (nén cắt ngang) → hỏi lại trước khi quyết.")
    elif res.get("reason") == "free_text":
        lines.append('Bạn trả lời tự-do ("%s") — có thể đang đổi hướng/chưa chốt → '
                     "xác-nhận lại." % res.get("answer", ""))
    lines.append("Đừng để tóm-tắt sau nén thay cho một quyết-định chưa đóng.")
    return "\n".join(lines)


def _emit_context(text: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }))
    sys.stdout.flush()


def core(data: dict):
    """The post-compaction re-surface additionalContext (name the still-open question),
    or None. Pure — no emit/exit — so the in-process dispatcher can call it; the caller
    owns the enabled-check + terminal write. Fail-open: any error yields None."""
    try:
        if data.get("source") != "compact":
            return None
        res = transcript_questions.last_unresolved_question(data.get("transcript_path"))
        if res:
            text = _build_context(res)
            if text and text.strip():
                return text
    except Exception as e:  # noqa: BLE001 — a re-surface nudge must never break a session
        hook_runtime.log_hook_error(NAME, e)
    return None


def run(raw=None) -> None:
    """Enabled + source==compact + an open last-AUQ -> inject the re-surface nudge;
    anything else (disabled, other source, no open question, any error) -> silent
    continue. Never raises, never exits 2 (nudge fail-open)."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(NAME, HOOK_CLASS):
            text = core(data)
            if text:
                _emit_context(text)
                return
    except Exception as e:  # noqa: BLE001 — a re-surface nudge must never break a session
        hook_runtime.log_hook_error(NAME, e)
    hook_runtime.emit_continue()


def main(raw=None) -> None:
    run(raw=raw)


if __name__ == "__main__":
    main()
