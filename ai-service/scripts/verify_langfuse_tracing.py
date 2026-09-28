"""Run one local PDF through the backend OCR function and flush its Langfuse trace."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from contract_ocr.infrastructure.backend_ocr_job import (
    BackendOcrJobRequest,
    get_backend_job,
    new_backend_job,
    run_backend_ocr,
)
from contract_ocr.infrastructure.observability import flush_langfuse, get_langfuse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--engine", choices=["pymupdf", "mistral"], default="pymupdf")
    args = parser.parse_args()

    source = args.file.resolve()
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        pages = list(range(1, pdf.page_count + 1))

    request = BackendOcrJobRequest(
        task_id=1,
        attempt_id=1,
        tenant_id="local-verification",
        document_id=f"langfuse-check-{digest[:12]}",
        source_blob_get_url=source.as_uri(),
        source_sha256=digest,
        pages_to_process=pages,
        render_target={},
        options={
            "engine": args.engine,
            "dpi": 150,
            "document_role": "contract",
            # Deliberately do not send the original filename into trace metadata.
            "filename": "contract.pdf",
        },
    )
    job_id, _ = new_backend_job("ocr")
    trace_seed = f"langfuse-verification-{digest[:12]}"
    run_backend_ocr(job_id, request, trace_seed=trace_seed)

    client = get_langfuse()
    trace_id = client.create_trace_id(seed=trace_seed) if client else None
    flush_langfuse()
    job = get_backend_job(job_id) or {}
    print(json.dumps({"job_id": job_id, "status": job.get("status"), "trace_id": trace_id}))


if __name__ == "__main__":
    main()
