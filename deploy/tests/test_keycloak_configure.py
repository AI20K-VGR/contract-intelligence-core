from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASH = None
for _candidate in (
    shutil.which("bash"),
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files\Git\usr\bin\bash.exe",
):
    if not _candidate or not Path(_candidate).is_file():
        continue
    try:
        if subprocess.run(
            [_candidate, "--version"], check=False, capture_output=True, timeout=3
        ).returncode == 0:
            BASH = _candidate
            break
    except (OSError, subprocess.TimeoutExpired):
        continue
HAS_BASH = BASH is not None


def _load_keycloak_configure():
    import importlib.util

    source = ROOT / "deploy" / "keycloak_configure.py"
    spec = importlib.util.spec_from_file_location("keycloak_configure_under_test", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_admin_token_retries_direct_timeout_then_returns_token_without_logging(monkeypatch, capsys):
    module = _load_keycloak_configure()
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "must-not-be-logged")
    request = Mock(side_effect=[TimeoutError("connect timeout"), {"access_token": "opaque-token"}])
    sleep = Mock()
    monkeypatch.setattr(module, "_request", request)
    monkeypatch.setattr(module.time, "sleep", sleep)

    assert module._admin_token() == "opaque-token"
    assert request.call_count == 2
    sleep.assert_called_once()
    output = capsys.readouterr().out
    assert "opaque-token" not in output
    assert "must-not-be-logged" not in output


def test_admin_token_transient_url_timeout_then_success(monkeypatch):
    module = _load_keycloak_configure()
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "secret")
    request = Mock(
        side_effect=[
            urllib.error.URLError(TimeoutError("temporarily unavailable")),
            {"access_token": "ok"},
        ]
    )
    monkeypatch.setattr(module, "_request", request)
    monkeypatch.setattr(module.time, "sleep", Mock())

    assert module._admin_token() == "ok"
    assert request.call_count == 2


def test_admin_token_timeout_at_deadline_is_actionable_and_quick(monkeypatch, capsys):
    module = _load_keycloak_configure()
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "secret")
    monkeypatch.setattr(module, "_request", Mock(side_effect=TimeoutError("late timeout")))
    monkeypatch.setattr(module.time, "monotonic", Mock(side_effect=[0, 301]))
    sleep = Mock()
    monkeypatch.setattr(module.time, "sleep", sleep)

    with pytest.raises(SystemExit, match="not ready after 300s"):
        module._admin_token()

    sleep.assert_not_called()
    output = capsys.readouterr().out
    assert "secret" not in output
    assert "access_token" not in output


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_admin_token_does_not_retry_configuration_or_auth_4xx(monkeypatch, status):
    module = _load_keycloak_configure()
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "secret")
    error = urllib.error.HTTPError("http://keycloak/token", status, "rejected", {}, io.BytesIO())
    request = Mock(side_effect=error)
    monkeypatch.setattr(module.time, "monotonic", Mock(side_effect=[0, 0.1, 301]))
    monkeypatch.setattr(module.time, "sleep", Mock())
    monkeypatch.setattr(module, "_request", request)

    with pytest.raises(SystemExit):
        module._admin_token()

    request.assert_called_once()


def _workflow(name: str) -> dict:
    return yaml.load(
        (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def test_deploy_workflow_has_develop_preflight_and_requires_all_ssh_settings():
    workflow = _workflow("deploy.yml")
    assert workflow["on"]["push"]["branches"] == ["develop"]
    assert workflow["on"]["pull_request"]["branches"] == ["develop"]
    assert workflow["on"]["workflow_dispatch"]["inputs"]["target"]["options"] == [
        "production",
        "staging",
    ]
    jobs = workflow["jobs"]
    assert {"preflight", "staging", "deploy"} <= jobs.keys()
    assert "environment" not in jobs["preflight"]
    assert "secrets." not in json.dumps(jobs["preflight"])

    for job, target in (("staging", "staging"), ("deploy", "production")):
        assert jobs[job]["uses"] == "./.github/workflows/deploy-target.yml"
        assert jobs[job]["with"]["target"] == target
        assert "preflight" in jobs[job]["needs"]
        assert "github.event_name != 'pull_request'" in jobs[job]["if"]
    # Production waits for staging, and is skipped when staging was asked for alone.
    assert "staging" in jobs["deploy"]["needs"]
    assert "needs.staging.result == 'success'" in jobs["deploy"]["if"]
    assert "inputs.target != 'staging'" in jobs["deploy"]["if"]
    assert "vars.STAGING_ENABLED == 'true'" in jobs["staging"]["if"]

    preflight_text = json.dumps(jobs["preflight"])
    assert "workflow_dispatch" in preflight_text
    assert "refs/heads/develop" in preflight_text

    target_job = _workflow("deploy-target.yml")["jobs"]["deploy"]
    assert target_job["environment"] == "${{ inputs.target }}"
    deploy_text = json.dumps(target_job)
    required_names = ["DEPLOY_HOST", "DEPLOY_USER", "DEPLOY_SSH_KEY", "DEPLOY_KNOWN_HOSTS"]
    for name in required_names:
        assert name in deploy_text
        assert f"STAGING_{name}" in deploy_text
    assert "::error::" in deploy_text
    assert "exit 1" in deploy_text


def test_staging_never_falls_back_to_production_settings():
    """`staging && STAGING_X || PROD_X` would deploy to production when STAGING_X
    is empty. Every per-target value must be the two-part form instead."""

    text = (ROOT / ".github" / "workflows" / "deploy-target.yml").read_text(encoding="utf-8")
    picks = [line.split(": ", 1)[1] for line in text.splitlines() if "STAGING_" in line and "${{" in line]
    assert len(picks) == 8  # 4 job settings + key and known hosts in two steps
    for value in picks:
        staging_part, production_part = value.split("}}${{")
        assert staging_part.startswith("${{ inputs.target == 'staging' && ")
        assert staging_part.endswith(" || '' ")
        assert production_part.startswith(" inputs.target != 'staging' && ")
        assert production_part.endswith(" || '' }}")
        assert "STAGING_" not in production_part

@pytest.mark.skipif(not HAS_BASH, reason="bash is available on the GitHub deploy runner")
@pytest.mark.parametrize(
    ("event_name", "ref", "base_ref", "target", "expected_status"),
    [
        ("push", "refs/heads/develop", "", "", 0),
        ("workflow_dispatch", "refs/heads/develop", "", "", 0),
        ("workflow_dispatch", "refs/heads/develop", "", "production", 0),
        ("workflow_dispatch", "refs/heads/feature/example", "", "", 1),
        ("workflow_dispatch", "refs/heads/feature/example", "", "production", 1),
        ("workflow_dispatch", "refs/heads/feature/example", "", "staging", 0),
        ("pull_request", "refs/pull/42/merge", "develop", "", 0),
        ("pull_request", "refs/pull/42/merge", "main", "", 1),
    ],
)
def test_deploy_preflight_allows_develop_push_dispatch_or_pr_validation(
    event_name, ref, base_ref, target, expected_status
):
    step = _workflow("deploy.yml")["jobs"]["preflight"]["steps"][0]
    environment = os.environ.copy()
    environment.update(
        {"EVENT_NAME": event_name, "REF": ref, "BASE_REF": base_ref, "TARGET": target}
    )

    result = subprocess.run(
        [BASH, "-euc", step["run"]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == expected_status
    if expected_status:
        expected_error = (
            "only for PRs targeting develop"
            if event_name == "pull_request"
            else "only from refs/heads/develop"
        )
        assert expected_error in result.stdout


@pytest.mark.skipif(not HAS_BASH, reason="bash is available on the GitHub deploy runner")
@pytest.mark.parametrize(
    "missing_name", ["DEPLOY_HOST", "DEPLOY_USER", "DEPLOY_SSH_KEY", "DEPLOY_KNOWN_HOSTS"]
)
def test_deploy_workflow_fails_for_each_missing_ssh_setting(missing_name):
    workflow = _workflow("deploy-target.yml")
    step = next(
        item
        for item in workflow["jobs"]["deploy"]["steps"]
        if item.get("name") == "Require complete SSH configuration"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DEPLOY_HOST": "deploy.example.com",
            "DEPLOY_USER": "deploy-user",
            "DEPLOY_SSH_KEY": "private-key-placeholder",
            "DEPLOY_KNOWN_HOSTS": "deploy.example.com ssh-ed25519 host-key-placeholder",
        }
    )
    environment.pop(missing_name)

    result = subprocess.run(
        [BASH, "-euc", step["run"]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode != 0
    assert f"Required deployment setting {missing_name} is missing" in result.stdout
    assert "private-key-placeholder" not in result.stdout + result.stderr


@pytest.mark.skipif(not HAS_BASH, reason="bash is available on the GitHub deploy runner")
def test_deploy_workflow_accepts_complete_ssh_configuration():
    workflow = _workflow("deploy-target.yml")
    step = next(
        item
        for item in workflow["jobs"]["deploy"]["steps"]
        if item.get("name") == "Require complete SSH configuration"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DEPLOY_HOST": "deploy.example.com",
            "DEPLOY_USER": "deploy-user",
            "DEPLOY_SSH_KEY": "private-key-placeholder",
            "DEPLOY_KNOWN_HOSTS": "deploy.example.com ssh-ed25519 host-key-placeholder",
        }
    )

    result = subprocess.run(
        [BASH, "-euc", step["run"]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr


def test_deploy_script_waits_for_services_and_fails_before_external_smoke_on_config_error():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    deploy = (ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    assert "condition: service_healthy" in compose
    assert "keycloak-readiness" in compose
    assert "AI2_QUERY_EGRESS_ALLOWED: ${AI2_QUERY_EGRESS_ALLOWED:-true}" in compose
    assert "AI2_QUERY_USE_VECTOR: ${AI2_QUERY_USE_VECTOR:-true}" in compose
    assert "AI2_LLM_BASE_URL is empty" in deploy
    assert '"${COMPOSE[@]}" exec -T' in deploy
    assert "[deploy] smoke test" in deploy
    workflow = (ROOT / ".github" / "workflows" / "deploy-target.yml").read_text(encoding="utf-8")
    assert "$sudo git checkout --detach \"$SHA\"" in workflow
    assert "deployment checkout has local changes" in workflow
    assert "git ls-files --others --exclude-standard" in workflow
