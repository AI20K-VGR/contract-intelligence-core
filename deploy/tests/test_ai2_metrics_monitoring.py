"""AI2 cost and speed reach Grafana: port, network, scrape job and dashboard agree.

AI2 has its own dashboard (``ai2-cost``), kept apart from AI1's ``ci-overview``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "docker-compose.yml"
PROMETHEUS = ROOT / "infra/monitoring/prometheus/prometheus.yml"
DASHBOARD = ROOT / "infra/monitoring/grafana/dashboards/ai2-cost.json"
OVERVIEW = ROOT / "infra/monitoring/grafana/dashboards/ci-overview.json"
METRICS = ROOT / "ai-service/app/llm/metrics.py"


class _ComposeLoader(yaml.SafeLoader):
    """Accepts Compose merge tags (``!reset``, ``!override``) as plain values."""


def _tagged(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _tagged)


def _ai2_service() -> dict:
    doc = yaml.load(LOCAL.read_text(encoding="utf-8"), Loader=_ComposeLoader)  # noqa: S506
    return doc["services"]["ai2-service"]


def test_ai2_service_serves_metrics_on_the_monitoring_network():
    service = _ai2_service()
    assert service["environment"]["AI2_METRICS_PORT"] == "9109"
    assert "ci-monitoring" in service["networks"]
    assert "ports" not in service or not any("9109" in str(p) for p in service["ports"])


def test_prometheus_scrapes_ai2_service():
    jobs = yaml.safe_load(PROMETHEUS.read_text(encoding="utf-8"))["scrape_configs"]
    targets = {
        job["job_name"]: [t for c in job["static_configs"] for t in c["targets"]] for job in jobs
    }
    assert targets["ai2-service"] == ["ai2-service:9109"]


def test_dashboard_ai2_panels_use_metrics_ai2_exports():
    exported = set(re.findall(r'"(ai2_[a-z_]+)"', METRICS.read_text(encoding="utf-8")))
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    exprs = [t["expr"] for p in dashboard["panels"] for t in p.get("targets", [])]
    used = {
        re.sub(r"_(bucket|count|sum)$", "", name)
        for expr in exprs
        for name in re.findall(r"\bai2_[a-z_]+", expr)
    }
    assert used, "the dashboard has no AI2 panel"
    assert used <= exported, used - exported
    ids = [p["id"] for p in dashboard["panels"]]
    assert len(ids) == len(set(ids))


def _metric_names(path: Path) -> set[str]:
    dashboard = json.loads(path.read_text(encoding="utf-8"))
    exprs = [t["expr"] for p in dashboard["panels"] for t in p.get("targets", [])]
    return {name for expr in exprs for name in re.findall(r"ai[12]_[a-z_]+", expr)}


def test_ai2_and_ai1_dashboards_stay_apart():
    assert not {n for n in _metric_names(OVERVIEW) if n.startswith("ai2_")}
    assert not {n for n in _metric_names(DASHBOARD) if n.startswith("ai1_")}


def test_ai2_dashboard_covers_questions_and_conflict_jobs():
    names = _metric_names(DASHBOARD)
    for metric in (
        "ai2_query_cost_usd_total",
        "ai2_query_duration_seconds_bucket",
        "ai2_idp_cost_usd_total",
        "ai2_idp_job_duration_seconds_bucket",
        "ai2_idp_llm_seconds_total",
        "ai2_idp_findings_total",
    ):
        assert metric in names, metric
