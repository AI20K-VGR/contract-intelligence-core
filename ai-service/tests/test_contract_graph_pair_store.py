import json
from contextlib import nullcontext

from sqlalchemy.exc import IntegrityError
from test_contract_graph_pair_projection import relation

from app.contracts.contract_graph import PairLabel
from app.db.tables import CONTRACT_PAIR_LABELS, contract_pair_relations
from app.tools.pair_relation_store import relation_digest, relation_row
from app.tools.persist import record_to_dict
from fixtures.contract_graph_pair_records import pair_record


def test_relation_row_columns_match_table():
    r = relation(pair_record())
    row = relation_row(r, tenant_id="t", dossier_id="d", job_id="j", now_ms=1)
    assert set(row) == {c.name for c in contract_pair_relations.columns}
    assert row["directed"] == 0 and row["review_state"] == "NEEDS_REVIEW"


def test_relation_row_strips_nul():
    r = relation(pair_record())
    r.span_a += "\x00"
    r.citation_a.text_span += "\x00"
    row = relation_row(r, tenant_id="t", dossier_id="d", job_id="j", now_ms=1)
    assert not any("\x00" in v for v in row.values() if isinstance(v, str))
    assert "\x00" not in json.loads(row["citation_a_json"])["text_span"]


def test_relation_digest_stable():
    r = relation(pair_record())
    assert relation_digest(r) == relation_digest(r.model_copy(deep=True))
    changed = r.model_copy(update={"span_a": "different text"})
    assert relation_digest(r) != relation_digest(changed)


def test_sqlite_store_ignores_pairs():
    rec = pair_record()
    rec.pair_relations = [relation(rec)]
    rec.pair_relations_ran = True
    assert not {"pair_relations", "pair_relations_ran"} & record_to_dict(rec).keys()
    from app.tools.jobs import SQLiteJobStore
    assert not hasattr(SQLiteJobStore, "_replace_pair_relations")


def test_check_constraint_labels_match_enum():
    assert set(CONTRACT_PAIR_LABELS) == {label.value for label in PairLabel}


def test_pair_write_failure_logs_metadata_without_source_payload(monkeypatch, caplog):
    from app.tools import pair_relation_store
    from app.tools.jobs import PostgresJobStore

    sentinel = "SENSITIVE_CONTRACT_SPAN_SENTINEL"
    rec = pair_record()
    rec.pair_relations = [relation(rec)]

    def fail(*args, **kwargs):
        raise IntegrityError("INSERT INTO ai2.contract_pair_relations", {"span_a": sentinel},
                             RuntimeError(sentinel))

    class Connection:
        def begin_nested(self):
            return nullcontext()

    monkeypatch.setattr(pair_relation_store, "replace_pair_relations", fail)
    store = PostgresJobStore.__new__(PostgresJobStore)
    monkeypatch.setattr(store, "_now_ms", lambda: 1)
    store._replace_pair_relations(Connection(), rec, "job_log_test")
    assert "ai2.contract_pair_relations_write_failed" in caplog.text
    assert "job_log_test" in caplog.text and "IntegrityError" in caplog.text
    assert sentinel not in caplog.text
    assert "INSERT INTO" not in caplog.text
