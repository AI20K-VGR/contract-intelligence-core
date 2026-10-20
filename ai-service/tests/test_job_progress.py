from app.api import main
from app.pipeline import idp
from app.pipeline.runtime import ProcessingRuntime


def test_run_idp_reports_steps_in_order(monkeypatch):
    from fixtures import envelope
    from fixtures.contract_graph_pair_records import pair_record

    reports = []
    runtime = ProcessingRuntime(egress_allowed=False, max_llm_calls=0, on_progress=reports.append)
    idp.run_idp(pair_record(), envelope(), llm=None, runtime=runtime)

    steps = list(dict.fromkeys(r["step"] for r in reports))
    assert steps == ["S6", "S7", "S10"]
    assert all(0 <= r["done"] <= r["total"] and r["total"] >= 1 for r in reports)
    assert {r["unit"] for r in reports if r["step"] == "S7"} == {"clause"}


def test_a_failing_progress_sink_never_fails_the_job():
    def broken(_progress):
        raise RuntimeError("store down")

    ProcessingRuntime(on_progress=broken).report_progress("S7", 1, 2, "clause")


def test_progress_writer_throttles_within_a_step(monkeypatch):
    written = []

    class Store:
        def set_wire(self, job_id, **kwargs):
            written.append(kwargs["wire"]["progress"])

    now = [0.0]
    monkeypatch.setattr(main, "JOB_STORE", Store())
    monkeypatch.setattr(main.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(main, "_known_wire", lambda job_id: {"job_id": job_id, "status": "RUNNING"})
    write = main._progress_writer("job-1", "t", "d", "token")
    for done in range(5):
        write({"step": "S7", "done": done, "total": 5, "unit": "clause"})
    now[0] = 2.0
    write({"step": "S7", "done": 4, "total": 5, "unit": "clause"})
    write({"step": "S9", "done": 0, "total": 3, "unit": "pair"})
    assert [(p["step"], p["done"]) for p in written] == [("S7", 0), ("S7", 4), ("S9", 0)]
