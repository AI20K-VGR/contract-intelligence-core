#!/usr/bin/env python3
"""Improve a skill description based on trigger-eval results.

Takes eval results (from trigger_eval.run_eval) and asks a model for a better
description. Adapted from the upstream improve_description to call ``claude -p``
instead of the anthropic SDK, so the harness stays self-contained (no extra
dependency, no API-key surface).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from trigger_eval import parse_skill_md


def _claude_text(prompt: str, model: str, *, timeout: int = 120) -> str:
    """Run ``claude -p`` once and return its final text result.

    Scrubs ``CLAUDECODE`` so it can nest inside a Claude Code session. Raises
    ``RuntimeError`` on every failure mode of the CLI — timeout, non-zero exit,
    an ``is_error`` result envelope, non-JSON output, or an empty result. The
    upstream SDK raised on API failure; ``claude -p`` signals failure in-band
    (exit 0 + ``is_error`` JSON), so the caller must never mistake a broken call
    for a valid empty description.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"claude -p timed out after {timeout}s") from exc
    except OSError as exc:
        raise RuntimeError(f"claude -p could not be launched: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-500:]
        raise RuntimeError(f"claude -p exited {proc.returncode}: {tail}")
    out = (proc.stdout or "").strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude -p returned non-JSON output: {out[:200]!r}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"claude -p returned unexpected JSON shape: {type(data).__name__}")
    if data.get("is_error") or str(data.get("subtype", "")).startswith("error"):
        raise RuntimeError(
            f"claude -p reported an error: {data.get('result') or data.get('subtype')}")
    result = data.get("result", "") or ""
    if not result.strip():
        raise RuntimeError("claude -p returned an empty result")
    return result


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list,
    model: str,
    *,
    test_results: dict = None,
    log_dir: Path = None,
    iteration: int = None,
) -> str:
    """Ask the model for an improved description based on eval results."""
    failed_triggers = [
        r for r in eval_results["results"]
        if r["should_trigger"] and not r["pass"]
    ]
    false_triggers = [
        r for r in eval_results["results"]
        if not r["should_trigger"] and not r["pass"]
    ]

    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    if test_results:
        test_score = f"{test_results['summary']['passed']}/{test_results['summary']['total']}"
        scores_summary = f"Train: {train_score}, Test: {test_score}"
    else:
        scores_summary = f"Train: {train_score}"

    prompt = f"""You are optimizing a skill description for a Claude Code skill called "{skill_name}". A "skill" is sort of like a prompt, but with progressive disclosure -- there's a title and description that Claude sees when deciding whether to use the skill, and then if it does use the skill, it reads the .md file which has lots more details and potentially links to other resources in the skill folder like helper files and scripts and additional documentation or examples.

The description appears in Claude's "available_skills" list. When a user sends a query, Claude decides whether to invoke the skill based solely on the title and on this description. Your goal is to write a description that triggers for relevant queries, and doesn't trigger for irrelevant ones.

Here's the current description:
<current_description>
"{current_description}"
</current_description>

Current scores ({scores_summary}):
<scores_summary>
"""
    if failed_triggers:
        prompt += "FAILED TO TRIGGER (should have triggered but didn't):\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if false_triggers:
        prompt += "FALSE TRIGGERS (triggered but shouldn't have):\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if history:
        prompt += "PREVIOUS ATTEMPTS (do NOT repeat these — try something structurally different):\n\n"
        for h in history:
            train_s = f"{h.get('train_passed', h.get('passed', 0))}/{h.get('train_total', h.get('total', 0))}"
            test_s = f"{h.get('test_passed', '?')}/{h.get('test_total', '?')}" if h.get('test_passed') is not None else None
            score_str = f"train={train_s}" + (f", test={test_s}" if test_s else "")
            prompt += f'<attempt {score_str}>\n'
            prompt += f'Description: "{h["description"]}"\n'
            if "results" in h:
                prompt += "Train results:\n"
                for r in h["results"]:
                    status = "PASS" if r["pass"] else "FAIL"
                    prompt += f'  [{status}] "{r["query"][:80]}" (triggered {r["triggers"]}/{r["runs"]})\n'
            if h.get("note"):
                prompt += f'Note: {h["note"]}\n'
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

Skill content (for context on what the skill does):
<skill_content>
{skill_content}
</skill_content>

Based on the failures, write a new and improved description that is more likely to trigger correctly. When I say "based on the failures", it's a bit of a tricky line to walk because we don't want to overfit to the specific cases you're seeing. So what I DON'T want you to do is produce an ever-expanding list of specific queries that this skill should or shouldn't trigger for. Instead, try to generalize from the failures to broader categories of user intent and situations where this skill would be useful or not useful. The reason for this is twofold:

1. Avoid overfitting
2. The list might get loooong and it's injected into ALL queries and there might be a lot of skills, so we don't want to blow too much space on any given description.

Concretely, keep the description within the harness cap of 512 characters (roughly 60-90 words), even if that comes at the cost of accuracy.

Here are some tips that we've found to work well in writing these descriptions:
- The skill should be phrased in the imperative -- "Use this skill for" rather than "this skill does"
- The skill description should focus on the user's intent, what they are trying to achieve, vs. the implementation details of how the skill works.
- The description competes with other skills for Claude's attention — make it distinctive and immediately recognizable.
- If you're getting lots of failures after repeated attempts, change things up. Try different sentence structures or wordings.

I'd encourage you to be creative and mix up the style in different iterations since you'll have multiple opportunities to try different approaches and we'll just grab the highest-scoring one at the end.

Please respond with only the new description text in <new_description> tags, nothing else."""

    text = _claude_text(prompt, model)

    # Require the explicit <new_description> tag the prompt asks for. An untagged
    # response is a refusal / malformed answer, not a description — fall back to the
    # current one rather than adopting raw model text (which could be "I can't help
    # with that"). This hardens past the upstream, which adopted bare text.
    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    description = match.group(1).strip().strip('"') if match else ""
    adopted = bool(description)
    if not adopted:
        description = current_description

    transcript = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "adopted": adopted,
        "char_count": len(description),
        "over_limit": len(description) > 512,
    }

    # If over 512 chars, ask the model to shorten it (claude -p is single-shot,
    # so the follow-up restates the prior answer instead of a multi-turn message).
    if len(description) > 512:
        shorten_prompt = (
            prompt
            + "\n\nYour previous answer was:\n"
            + text
            + f"\n\nThat description is {len(description)} characters, which exceeds the harness "
            "512 character cap. Rewrite it to be under 512 characters while preserving the "
            "most important trigger words and intent coverage. Respond with only the new "
            "description in <new_description> tags."
        )
        shorten_text = _claude_text(shorten_prompt, model)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        shortened = match.group(1).strip().strip('"') if match else ""

        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = shortened
        transcript["rewrite_char_count"] = len(shortened)
        # Only swap in the shortened text if the model actually produced one; never
        # blank a usable (if over-limit) description on a failed shorten.
        if shortened:
            description = shortened
            if len(shortened) > 512:
                print(f"Warning: shortened description is still {len(shortened)} chars "
                      "(>512); applying as-is", file=sys.stderr)
            transcript["rewrite_still_over_limit"] = len(shortened) > 512

    transcript["final_description"] = description

    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"improve_iter_{iteration or 'unknown'}.json").write_text(
            json.dumps(transcript, indent=2))

    return description


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Improve a skill description based on eval results")
    parser.add_argument("--eval-results", required=True, help="Path to eval results JSON")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--history", default=None, help="Path to history JSON (previous attempts)")
    parser.add_argument("--model", required=True, help="Model for improvement")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args(argv)

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        return 1

    eval_results = json.loads(Path(args.eval_results).read_text())
    history = json.loads(Path(args.history).read_text()) if args.history else []
    name, _, content = parse_skill_md(skill_path)
    current_description = eval_results["description"]

    try:
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=eval_results,
            history=history,
            model=args.model,
        )
    except RuntimeError as exc:
        print(f"Error: improvement failed: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Improved: {new_description}", file=sys.stderr)

    output = {
        "description": new_description,
        "history": history + [{
            "description": current_description,
            "passed": eval_results["summary"]["passed"],
            "failed": eval_results["summary"]["failed"],
            "total": eval_results["summary"]["total"],
            "results": eval_results["results"],
        }],
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
