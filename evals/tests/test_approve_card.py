from __future__ import annotations

import hashlib
import json

from evals.scripts import approve_card


def test_approve_card_moves_proposal(tmp_path, monkeypatch, capsys) -> None:
    proposal = tmp_path / "proposed" / "domain.v2.json"
    proposal.parent.mkdir()
    proposal.write_bytes(b'{"schema_version":"ai2.eval.strategy.v2","metrics":{}}\r\n')
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")

    assert approve_card.main(["--proposal", str(proposal)]) == 2
    assert proposal.exists()
    assert approve_card.main(["--proposal", str(proposal), "--approved-by", "Reviewer"]) == 0

    card = tmp_path / "cards" / "domain.json"
    sidecar = tmp_path / "cards" / "domain.sha256"
    assert not proposal.exists()
    body = card.read_bytes()
    assert b"\r\n" not in body
    assert json.loads(body)["approved_by"] == "Reviewer"
    assert sidecar.read_text(encoding="utf-8").strip() == hashlib.sha256(body).hexdigest()
    assert "threshold" in capsys.readouterr().out.lower()


def test_approve_card_refuses_ci(tmp_path, monkeypatch) -> None:
    proposal = tmp_path / "domain.v2.json"
    proposal.write_text('{"schema_version":"ai2.eval.strategy.v2","metrics":{}}\n', encoding="utf-8")
    monkeypatch.setenv("CI", "true")
    assert approve_card.main(["--proposal", str(proposal), "--approved-by", "Reviewer"]) == 2
    assert proposal.exists()
    assert not (tmp_path / "cards" / "domain.json").exists()


def test_approve_card_rejects_non_json_proposal_name(tmp_path, monkeypatch, capsys) -> None:
    proposal = tmp_path / "domain.txt"
    proposal.write_text('{"schema_version":"ai2.eval.strategy.v2"}', encoding="utf-8")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    assert approve_card.main(["--proposal", str(proposal), "--approved-by", "Reviewer"]) == 2
    assert proposal.exists()
    assert "filename" in capsys.readouterr().err


def test_config_integrity_crlf(tmp_path) -> None:
    import importlib.util

    for domain in ("ai2_grounded_query", "ai2_contract_package"):
        card_dir = tmp_path / "cards"
        card_dir.mkdir(exist_ok=True)
        card = card_dir / f"{domain}.json"
        sidecar = card_dir / f"{domain}.sha256"
        raw = b'{"schema_version":"ai2.eval.strategy.v2"}\r\n'
        card.write_bytes(raw)
        sidecar.write_text(hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), encoding="ascii")
        module_path = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "eval_types"
            / domain
            / "config_integrity.py"
        )
        spec = importlib.util.spec_from_file_location(f"{domain}_integrity", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        assert module.load_verified_config(tmp_path)["schema_version"] == "ai2.eval.strategy.v2"
