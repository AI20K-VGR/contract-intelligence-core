"""Sample container CPU/RAM (docker stats) and DB connections while a load runs.

Local only — it shells out to `docker stats` and queries Postgres via the
backend-db container. Returns peak/avg so a load scenario can report what it cost
the host, not just client-side latency.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass, field


@dataclass
class ResourceSample:
    containers: dict[str, dict] = field(default_factory=dict)
    db_connections_peak: int = 0
    samples: int = 0


_WATCH = ["ci-backend", "ci-backend-worker", "ci-ai2-service", "ci-backend-db", "ci-kafka"]


def _docker() -> str | None:
    return shutil.which("docker")


def _parse_pct(value: str) -> float:
    try:
        return float(value.strip().rstrip("%"))
    except ValueError:
        return 0.0


def _parse_mem(value: str) -> float:
    # "341.9MiB / 7.485GiB" -> MiB
    used = value.split("/")[0].strip()
    num = "".join(c for c in used if c.isdigit() or c == ".")
    try:
        mib = float(num)
    except ValueError:
        return 0.0
    if "GiB" in used:
        mib *= 1024
    return mib


class ResourceMonitor:
    """Context manager: samples docker stats + DB connections on a background thread."""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.result = ResourceSample()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.available = bool(_docker())

    def _sample_once(self) -> None:
        fmt = "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
        out = subprocess.run(
            [_docker(), "stats", "--no-stream", "--format", fmt, *_WATCH],
            capture_output=True, text=True, timeout=20,
        )
        for line in out.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            name, cpu, mem = parts[0], _parse_pct(parts[1]), _parse_mem(parts[2])
            c = self.result.containers.setdefault(name, {"cpu_peak": 0.0, "cpu_sum": 0.0, "mem_peak": 0.0, "n": 0})
            c["cpu_peak"] = max(c["cpu_peak"], cpu)
            c["cpu_sum"] += cpu
            c["mem_peak"] = max(c["mem_peak"], mem)
            c["n"] += 1
        conns = subprocess.run(
            [_docker(), "exec", "ci-backend-db", "sh", "-lc",
             'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from pg_stat_activity where state is not null"'],
            capture_output=True, text=True, timeout=15,
        )
        try:
            self.result.db_connections_peak = max(self.result.db_connections_peak, int(conns.stdout.strip() or 0))
        except ValueError:
            pass
        self.result.samples += 1

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sample_once()
            except Exception:
                pass
            self._stop.wait(self.interval)

    def __enter__(self) -> "ResourceMonitor":
        if self.available:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def as_dict(self) -> dict:
        containers = {
            name: {
                "cpu_peak_pct": round(c["cpu_peak"], 1),
                "cpu_avg_pct": round(c["cpu_sum"] / c["n"], 1) if c["n"] else 0.0,
                "mem_peak_mib": round(c["mem_peak"], 1),
            }
            for name, c in self.result.containers.items()
        }
        return {"containers": containers, "db_connections_peak": self.result.db_connections_peak,
                "samples": self.result.samples}
