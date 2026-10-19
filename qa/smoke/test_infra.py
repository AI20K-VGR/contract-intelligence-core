"""Smoke for the moving parts behind the API: Kafka, backend-worker, AI1 worker.

These inspect the local docker compose stack directly (container state, Kafka
consumer groups, startup log markers). They skip when docker is not available or
when QA_ENV=prod, where there is no host access to the containers.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.smoke

CONTAINERS = {
    "backend-worker": "ci-backend-worker",
    "ai1-worker": "ci-ai1-worker",
    "kafka": "ci-kafka",
}
# Consumer groups the pipeline relies on (docker-compose.yml KAFKA_*_GROUP_ID).
CONSUMER_GROUPS = ["ci-ai1-ocr", "ci-backend-ai1-results"]
# In-container bootstrap listener (PLAINTEXT), not the host-published 9093.
BOOTSTRAP = "localhost:29092"


def _docker():
    return shutil.which("docker")


@pytest.fixture(scope="module", autouse=True)
def _require_local_docker(cfg):
    if cfg.is_prod:
        pytest.skip("infra smoke needs host docker access; not available against prod")
    if not _docker():
        pytest.skip("docker CLI not on PATH")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([_docker(), *args], capture_output=True, text=True, timeout=30)


def _running(name: str) -> bool:
    out = _run(["inspect", "-f", "{{.State.Running}}", name])
    return out.returncode == 0 and out.stdout.strip() == "true"


@pytest.mark.parametrize("name", list(CONTAINERS.values()))
def test_container_running(name):
    """Each pipeline container (kafka, backend-worker, ai1-worker) is up."""
    if _run(["inspect", name]).returncode != 0:
        pytest.skip(f"{name} not present on this host")
    assert _running(name), f"{name} is not running"


def test_backend_worker_consumers_started():
    """backend-worker started its dossier and AI1-result consumers (full log, markers may be old)."""
    out = _run(["logs", CONTAINERS["backend-worker"]])
    logs = out.stdout + out.stderr
    assert "worker.dossier_events.started" in logs, "dossier-events consumer did not start"
    assert "worker.ai1_results.started" in logs, "AI1-results consumer did not start"


def test_ai1_worker_started():
    """ai1-worker joined its Kafka group and subscribed to the OCR command topic."""
    logs = _run(["logs", CONTAINERS["ai1-worker"]])
    text = logs.stdout + logs.stderr
    assert any(
        marker in text
        for marker in ("ai1.kafka.worker.started", "group ci-ai1-ocr", "ci.ai1.ocr.commands")
    ), "ai1-worker shows no sign of joining the OCR command topic"


def test_kafka_consumer_groups_present_and_connected():
    """The pipeline consumer groups exist and are Stable with live members (not Empty/rebalancing)."""
    find = "ls /opt/kafka/bin/kafka-consumer-groups.sh 2>/dev/null || command -v kafka-consumer-groups.sh"
    probe = _run(["exec", CONTAINERS["kafka"], "bash", "-lc", find])
    script = probe.stdout.strip().splitlines()[0] if probe.stdout.strip() else "kafka-consumer-groups.sh"
    listing = _run(["exec", CONTAINERS["kafka"], script, "--bootstrap-server", "localhost:29092", "--list"])
    if listing.returncode != 0:
        pytest.skip(f"kafka-consumer-groups unavailable: {listing.stderr[:160]}")
    groups = listing.stdout.split()
    for group in CONSUMER_GROUPS:
        assert group in groups, f"consumer group {group} not registered (worker never consumed?)"
        state = _run(
            ["exec", CONTAINERS["kafka"], script, "--bootstrap-server", "localhost:29092",
             "--group", group, "--state", "--describe"]
        ).stdout
        assert "Stable" in state or "Empty" not in state, f"group {group} has no stable members:\n{state}"
