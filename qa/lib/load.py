"""Tiny closed-loop load generator: N requests, C in flight, latency stats."""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import asdict, dataclass

import httpx


@dataclass
class LoadResult:
    name: str
    requests: int
    concurrency: int
    ok: int
    errors: int
    error_rate: float
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    mean_ms: float
    status_codes: dict

    def as_dict(self) -> dict:
        return asdict(self)


def _pct(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = max(0, min(len(sorted_values) - 1, round(pct / 100 * len(sorted_values) + 0.5) - 1))
    return sorted_values[k]


async def _run(
    name: str,
    url: str,
    headers: dict | None,
    requests: int,
    concurrency: int,
    warmup: int,
    method: str = "GET",
) -> LoadResult:
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        for _ in range(warmup):
            await client.request(method, url, headers=headers)
        sem = asyncio.Semaphore(concurrency)
        latencies: list[float] = []
        codes: dict[str, int] = {}

        async def one() -> None:
            async with sem:
                start = time.perf_counter()
                try:
                    r = await client.request(method, url, headers=headers)
                    code = str(r.status_code)
                except httpx.HTTPError as exc:
                    code = type(exc).__name__
                latencies.append((time.perf_counter() - start) * 1000)
                codes[code] = codes.get(code, 0) + 1

        started = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(requests)))
        elapsed = time.perf_counter() - started

    ok = sum(n for c, n in codes.items() if c.isdigit() and int(c) < 400)
    lat = sorted(latencies)
    return LoadResult(
        name=name,
        requests=requests,
        concurrency=concurrency,
        ok=ok,
        errors=requests - ok,
        error_rate=round((requests - ok) / requests, 4),
        rps=round(requests / elapsed, 1),
        p50_ms=round(_pct(lat, 50), 1),
        p95_ms=round(_pct(lat, 95), 1),
        p99_ms=round(_pct(lat, 99), 1),
        max_ms=round(lat[-1], 1),
        mean_ms=round(statistics.fmean(lat), 1),
        status_codes=codes,
    )


def run_load(
    name: str,
    url: str,
    *,
    headers: dict | None = None,
    requests: int = 200,
    concurrency: int = 20,
    warmup: int = 5,
    method: str = "GET",
) -> LoadResult:
    return asyncio.run(_run(name, url, headers, requests, concurrency, warmup, method))
