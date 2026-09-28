#!/usr/bin/env python3
"""Trigger evaluation for a single skill description.

Measures whether ONE skill's description causes Claude to activate that skill
(via a Skill/Read tool call) for a set of queries. For each query it drops a
throwaway command file carrying the candidate description into the project's
``.claude/commands/`` directory so the description appears in Claude's available
catalog, runs ``claude -p`` with stream-json, and detects activation early from
partial stream events.

Bundled under skill-creator and invoked only by its validate/optimize flow — it
never runs in CI, so the structural router check stays LLM-free. A low trigger
rate does not always mean a weak description: ``claude -p`` may do the task
directly instead of activating any skill. Read per-query results alongside the
rate to tell signal from claude-does-it-itself.
"""

import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Optional


def _safe_token(name: str) -> str:
    """Reduce an arbitrary skill name to a path-safe filename token.

    The candidate name is interpolated into a throwaway command-file path; a name
    containing ``/`` or ``..`` would otherwise let the write+unlink escape the
    project's ``.claude/commands/`` directory. Keep only filename-safe characters.
    """
    token = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return token or "skill"


def find_project_root() -> Path:
    """Walk up from cwd to the nearest directory containing ``.claude/``.

    Mirrors how Claude Code discovers its project root, so the throwaway command
    file lands where ``claude -p`` will look for it. Falls back to cwd.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def parse_skill_md(skill_path: Path):
    """Parse a SKILL.md file, returning ``(name, description, full_content)``.

    Handles single-line and YAML block-scalar (``>``/``|``) descriptions.
    """
    content = (Path(skill_path) / "SKILL.md").read_text()
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            if value in (">", "|", ">-", "|-"):
                continuation = []
                i += 1
                while i < len(frontmatter_lines) and (
                        frontmatter_lines[i].startswith("  ")
                        or frontmatter_lines[i].startswith("\t")):
                    continuation.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation)
                continue
            description = value.strip('"').strip("'")
        i += 1

    return name, description, content


def parse_activation(lines: Iterable[str], clean_name: str) -> bool:
    """Decide whether ``clean_name`` was activated from a stream-json line feed.

    Pure: consumes already-decoded stream-json text lines and returns as soon as
    the verdict is known. Mirrors the detection logic of the upstream runner —
    early detection via ``content_block_start``/``content_block_delta`` stream
    events, with a fallback to the full ``assistant`` message tool_use.
    """
    pending_tool_name: Optional[str] = None
    accumulated_json = ""
    triggered = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")

        # Early detection via partial stream events.
        if etype == "stream_event":
            se = event.get("event", {})
            se_type = se.get("type", "")

            if se_type == "content_block_start":
                cb = se.get("content_block", {})
                if cb.get("type") == "tool_use":
                    tool_name = cb.get("name", "")
                    if tool_name in ("Skill", "Read"):
                        pending_tool_name = tool_name
                        accumulated_json = ""
                    else:
                        # A different tool means the model acted directly.
                        return False

            elif se_type == "content_block_delta" and pending_tool_name:
                delta = se.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    accumulated_json += delta.get("partial_json", "")
                    if clean_name in accumulated_json:
                        return True

            elif se_type in ("content_block_stop", "message_stop"):
                if pending_tool_name:
                    return clean_name in accumulated_json
                if se_type == "message_stop":
                    return False

        # Fallback: full assistant message after tool execution.
        elif etype == "assistant":
            message = event.get("message", {})
            for content_item in message.get("content", []):
                if content_item.get("type") != "tool_use":
                    continue
                tool_name = content_item.get("name", "")
                tool_input = content_item.get("input", {})
                if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                    triggered = True
                elif tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                    triggered = True
                return triggered

        elif etype == "result":
            return triggered

    return triggered


def _drain_complete_lines(buffer: str):
    """Split off every COMPLETE (newline-terminated) line, returning the non-blank
    ones plus the trailing partial remainder (kept for the next read). One drain
    routine for both the streaming path and the process-exit path (DRY)."""
    lines = []
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        if line.strip():
            lines.append(line)
    return lines, buffer


def _read_stream_lines(process, timeout: int) -> Iterable[str]:
    """Yield decoded stream-json lines from a running process until EOF/timeout.

    Factored out of run_single_query so the parsing wiring is testable with a
    stubbed line feed instead of a live select()/os.read() loop.
    """
    start_time = time.time()
    buffer = ""
    while time.time() - start_time < timeout:
        if process.poll() is not None:
            remaining = process.stdout.read()
            if remaining:
                buffer += remaining.decode("utf-8", errors="replace")
            # The process already exited: drain the COMPLETE lines still buffered
            # before breaking. A fast/cached run can emit its whole stream-json and
            # exit before the select() loop drains it; dropping those completed
            # lines scored a genuinely-activated skill as a no-trigger.
            lines, buffer = _drain_complete_lines(buffer)
            yield from lines
            break

        ready, _, _ = select.select([process.stdout], [], [], 1.0)
        if not ready:
            continue

        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            break
        buffer += chunk.decode("utf-8", errors="replace")
        lines, buffer = _drain_complete_lines(buffer)
        yield from lines

    # Trailing partial buffer (a newline-less tail) is discarded once the loop
    # exits, matching the upstream runner — detection rides on completed lines that
    # arrive during active streaming via --include-partial-messages.


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    *,
    timeout: int = 30,
    project_root: str,
    model: Optional[str] = None,
) -> bool:
    """Run one query and report whether the candidate skill was activated.

    Writes a throwaway command file under ``<project_root>/.claude/commands/`` so
    the candidate description is visible to ``claude -p``, runs the query, and
    detects activation. The command file and the spawned process are cleaned up
    on every exit path. A hard SIGKILL of this process can leave a uuid-named
    throwaway file behind and may orphan claude -p grandchildren — both safe to
    discard; normal exits (incl. SIGINT) clean up via the finally blocks.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{_safe_token(skill_name)}-skill-{unique_id}"
    commands_dir = Path(project_root) / ".claude" / "commands"
    command_file = commands_dir / f"{clean_name}.md"

    try:
        commands_dir.mkdir(parents=True, exist_ok=True)
        # YAML block scalar avoids breaking on quotes/newlines in the description.
        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_content = (
            "---\n"
            "description: |\n"
            f"  {indented_desc}\n"
            "---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )
        command_file.write_text(command_content)

        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Drop CLAUDECODE so claude -p can nest inside a Claude Code session; the
        # guard is for interactive terminals, programmatic subprocess use is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(project_root),
            env=env,
        )
        try:
            return parse_activation(_read_stream_lines(process, timeout), clean_name)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    finally:
        if command_file.exists():
            command_file.unlink()


def run_eval(
    eval_set: list,
    skill_name: str,
    description: str,
    *,
    num_workers: int = 1,
    timeout: int = 30,
    project_root,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: Optional[str] = None,
) -> dict:
    """Run an eval set for one skill and aggregate per-query pass/fail.

    ``eval_set`` items are ``{"query": str, "should_trigger": bool}``. A query
    passes when its trigger rate is on the expected side of ``trigger_threshold``.
    Runs sequentially when ``num_workers <= 1`` (deterministic, stub-friendly);
    otherwise fans out across a process pool.
    """
    query_triggers: dict = {}
    query_items: dict = {}

    def _record(item, value):
        q = item["query"]
        query_items[q] = item
        query_triggers.setdefault(q, []).append(value)

    if num_workers and num_workers > 1:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_item = {}
            for item in eval_set:
                for _ in range(runs_per_query):
                    future = executor.submit(
                        run_single_query,
                        item["query"],
                        skill_name,
                        description,
                        timeout=timeout,
                        project_root=str(project_root),
                        model=model,
                    )
                    future_to_item[future] = item
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    _record(item, future.result())
                except Exception as exc:  # noqa: BLE001 - report, count as no-trigger
                    print(f"Warning: query failed: {exc}", file=sys.stderr)
                    _record(item, False)
    else:
        for item in eval_set:
            for _ in range(runs_per_query):
                try:
                    value = run_single_query(
                        item["query"],
                        skill_name,
                        description,
                        timeout=timeout,
                        project_root=str(project_root),
                        model=model,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"Warning: query failed: {exc}", file=sys.stderr)
                    value = False
                _record(item, value)

    results = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total) if total else 0.0,
        },
    }


def main(argv: Optional[list] = None) -> int:
    """CLI: evaluate an eval set against a skill description. Added in Phase B."""
    parser = argparse.ArgumentParser(
        description="Trigger evaluation for a single skill description")
    parser.add_argument("--skill", required=True, help="Skill name (used for the throwaway command)")
    parser.add_argument("--description-file", required=True, help="Path to a file holding the description to test")
    parser.add_argument("--eval-set", required=True, help="Path to eval-set JSON: [{query, should_trigger}]")
    parser.add_argument("--project-root", default=None, help="Project root holding .claude/ (default: cwd)")
    parser.add_argument("--num-workers", type=int, default=1,
                        help="Parallel workers (default 1; >1 fans out real claude -p processes)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query (seconds)")
    parser.add_argument("--runs", type=int, default=3, dest="runs_per_query",
                        help="Runs per query (default 3: averages a stable trigger rate)")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger-rate threshold")
    parser.add_argument("--model", default=None, help="Model for claude -p (default: configured)")
    args = parser.parse_args(argv)

    description = Path(args.description_file).read_text()
    eval_set = json.loads(Path(args.eval_set).read_text())
    project_root = args.project_root or os.getcwd()

    planned = len(eval_set) * args.runs_per_query
    print(
        f"trigger_eval: {planned} planned claude -p invocation(s) "
        f"({len(eval_set)} queries x {args.runs_per_query} runs, workers={args.num_workers})",
        file=sys.stderr,
    )

    output = run_eval(
        eval_set,
        args.skill,
        description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
