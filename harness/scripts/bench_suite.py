#!/usr/bin/env python3
"""bench_suite.py — controlled wall-clock benchmark harness for pytest reps.

A single-shot `time pytest ...` is noise: the SAME command measured 246.99s then
102.77s back to back under thermal throttle. This script controls the 3 variables
that actually move wall-clock — CPU (cooldown-poll before each rep), RAM (a
discarded warmup rep for a consistent warm page-cache — NOT drop_caches, which
needs root), disk I/O (record before/after counters per rep, do not control them)
— runs N reps, and reports the MEDIAN plus a per-suite noise band (max-min spread)
so callers compare `abs(delta) > noise_band` instead of trusting a raw number.

Every reader here degrades to `None` on a missing sysfs/procfs source (non-Linux,
containers, CI) rather than raising — a bench run must still complete without
thermal data, it just loses the cooldown signal. Every seam (glob pattern, file
text, the subprocess runner) is a plain function parameter so unit tests can feed
fixtures without touching the real filesystem or spawning a real pytest.
"""
import argparse
import glob
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_THERMAL_GLOB = "/sys/class/thermal/thermal_zone*/temp"
_CPUFREQ_GLOB = "/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq"
_CPUINFO_PATH = "/proc/cpuinfo"
_MEMINFO_PATH = "/proc/meminfo"
_DISKSTATS_PATH = "/proc/diskstats"

_PYTEST_SUMMARY_RE = re.compile(
    r"=+\s*(?:(?P<failed>\d+)\s+failed,\s*)?(?P<passed>\d+)\s+passed[^=]*?\bin\s+(?P<wall>[\d.]+)s"
    r"(?:\s*\(\d+:\d{2}:\d{2}\))?\s*=+"
)


def median(vals: List[float]) -> float:
    """Median-of-N. Raises on empty input — a bench run with 0 reps is a caller bug,
    not a value we should silently paper over with 0.0."""
    if not vals:
        raise ValueError("median() arg is an empty sequence")
    ordered = sorted(vals)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def noise_band(wall_reps: List[float]) -> float:
    """Per-suite spread (max - min), NOT a global constant — a 13s band from the
    `unit` suite is meaningless for a ~1s or ~45s suite. Single/empty rep -> 0."""
    if not wall_reps:
        return 0.0
    return float(max(wall_reps) - min(wall_reps))


def parse_pytest_wall(stdout: str) -> Optional[Tuple[float, int, int]]:
    """Extract (wall_s, passed, failed) from a pytest summary line. pytest orders
    the summary failed-before-passed (`1 failed, 11 passed in 3.4s`); a pure-pass
    line omits the failed clause entirely. No match -> None, never raise (the
    caller may be benchmarking a non-pytest command)."""
    match = _PYTEST_SUMMARY_RE.search(stdout)
    if not match:
        return None
    wall = float(match.group("wall"))
    passed = int(match.group("passed"))
    failed = int(match.group("failed")) if match.group("failed") else 0
    return (wall, passed, failed)


def read_thermal(glob_pattern: str = _THERMAL_GLOB) -> Optional[float]:
    """Max temp (°C) across matching thermal zones; milli-°C on the wire. Degrades
    to None on a missing/unreadable sysfs (macOS, containers, permission denial) —
    the glob pattern is the seam a test points at an empty directory."""
    temps = []
    for path in glob.glob(glob_pattern):
        try:
            raw = Path(path).read_text(encoding="utf-8").strip()
            temps.append(int(raw) / 1000.0)
        except (OSError, ValueError):
            continue
    return max(temps) if temps else None


def _read_text_or_none(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _read_cpu_freq_khz(cpufreq_glob: str, cpuinfo_path: str) -> Optional[int]:
    """Prefer the live scaling_cur_freq (already kHz); fall back to /proc/cpuinfo's
    `cpu MHz` (converted). Either source can be absent depending on governor/VM."""
    freqs = []
    for path in glob.glob(cpufreq_glob):
        try:
            freqs.append(int(Path(path).read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            continue
    if freqs:
        return max(freqs)
    text = _read_text_or_none(cpuinfo_path)
    if text is None:
        return None
    match = re.search(r"cpu MHz\s*:\s*([\d.]+)", text)
    return int(float(match.group(1)) * 1000) if match else None


def _parse_meminfo(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    match = re.search(r"^MemFree:\s*(\d+)\s*kB", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def _parse_diskstats(text: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """Sum sectors read/written across every line (all block devices + partitions
    reported by /proc/diskstats) — a per-rep aggregate counter, not a per-device
    breakdown; field positions per the kernel's diskstats doc (sectors at index 5
    and 9, 0-based)."""
    if text is None:
        return (None, None)
    total_read = 0
    total_write = 0
    found = False
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 10:
            continue
        try:
            total_read += int(fields[5])
            total_write += int(fields[9])
        except ValueError:
            continue
        found = True
    return (total_read, total_write) if found else (None, None)


def read_snapshot(
    thermal_glob: str = _THERMAL_GLOB,
    cpufreq_glob: str = _CPUFREQ_GLOB,
    cpuinfo_path: str = _CPUINFO_PATH,
    meminfo_path: str = _MEMINFO_PATH,
    diskstats_path: str = _DISKSTATS_PATH,
    meminfo_text: Optional[str] = None,
    diskstats_text: Optional[str] = None,
) -> Dict[str, Optional[float]]:
    """Point-in-time system state for a bench rep. Every field independently
    degrades to None — a missing cpufreq sysfs must not blank out mem/disk too.
    `meminfo_text`/`diskstats_text` bypass the filesystem read entirely (the fixture
    seam); when absent, the paths are read for real."""
    if meminfo_text is None:
        meminfo_text = _read_text_or_none(meminfo_path)
    if diskstats_text is None:
        diskstats_text = _read_text_or_none(diskstats_path)
    disk_read, disk_write = _parse_diskstats(diskstats_text)
    return {
        "temp_c": read_thermal(thermal_glob),
        "cpu_freq_khz": _read_cpu_freq_khz(cpufreq_glob, cpuinfo_path),
        "mem_free_kb": _parse_meminfo(meminfo_text),
        "disk_read_sectors": disk_read,
        "disk_write_sectors": disk_write,
    }


def should_cooldown(temp_c: Optional[float], threshold_c: float) -> bool:
    return temp_c is not None and temp_c > threshold_c


def _default_runner(cmd) -> float:
    """Run `cmd` for real and time it. Prefers pytest's own reported wall (from its
    summary line) over our wrapper's monotonic delta — the wrapper adds process-spawn
    overhead pytest's own number does not carry; falls back to the wrapper's timing
    when the command is not pytest or its summary does not match."""
    argv = cmd if isinstance(cmd, (list, tuple)) else shlex.split(cmd)
    start = time.monotonic()
    completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    elapsed = time.monotonic() - start
    parsed = parse_pytest_wall(completed.stdout or "")
    return parsed[0] if parsed is not None else elapsed


def run_bench(
    cmd,
    reps: int = 3,
    warmup: int = 1,
    cooldown_threshold_c: float = 60.0,
    cooldown_max_s: float = 60.0,
    runner=None,
    sleep_fn=None,
    thermal_reader=None,
    snapshot_reader=None,
) -> Dict[str, Any]:
    """Discard `warmup` reps (warms the page cache so every measured rep sees the
    same RAM state — draining `drop_caches` needs root we do not have), then run
    `reps` measured reps: cooldown-poll (capped at `cooldown_max_s` — a rep that
    never cools is marked "hot" and proceeds rather than hanging forever) ->
    snapshot-before -> `runner(cmd)` -> snapshot-after. Returns median + noise_band
    (this suite's own spread, not a global constant) + every rep record.

    `runner`/`sleep_fn`/`thermal_reader`/`snapshot_reader` are the injectable seams —
    tests supply fakes so no real pytest subprocess or real sysfs read is needed to
    exercise this control-flow.
    """
    runner = runner or _default_runner
    sleep_fn = sleep_fn or time.sleep
    thermal_reader = thermal_reader or read_thermal
    snapshot_reader = snapshot_reader or read_snapshot

    for _ in range(warmup):
        runner(cmd)

    records = []
    for _ in range(reps):
        cooldown_waited = 0.0
        hot = False
        while should_cooldown(thermal_reader(), cooldown_threshold_c):
            if cooldown_waited >= cooldown_max_s:
                hot = True
                break
            sleep_fn(1.0)
            cooldown_waited += 1.0

        snapshot_before = snapshot_reader()
        wall_s = runner(cmd)
        snapshot_after = snapshot_reader()

        records.append({
            "wall_s": wall_s,
            "hot": hot,
            "cooldown_waited_s": cooldown_waited,
            "snapshot_before": snapshot_before,
            "snapshot_after": snapshot_after,
        })

    walls = [r["wall_s"] for r in records]
    return {
        "cmd": cmd,
        "warmup": warmup,
        "reps": records,
        "median_wall": median(walls),
        "noise_band": noise_band(walls),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cmd", required=True, help="command to benchmark, e.g. 'python3 -m pytest harness/tests/ -q'")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--json", default=None, help="write the full bench record to this path")
    parser.add_argument("--label", default=None, help="tag stamped into the JSON record, e.g. the suite name")
    parser.add_argument("--cooldown-threshold-c", type=float, default=60.0)
    parser.add_argument("--cooldown-max-s", type=float, default=60.0)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_bench(
        args.cmd,
        reps=args.reps,
        warmup=args.warmup,
        cooldown_threshold_c=args.cooldown_threshold_c,
        cooldown_max_s=args.cooldown_max_s,
    )
    if args.label:
        result["label"] = args.label
    print(json.dumps({"median_wall": result["median_wall"], "noise_band": result["noise_band"]}, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
