from __future__ import annotations

import subprocess
import sys


def _run_import(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )


def test_gateway_can_be_imported_first_in_a_fresh_process():
    result = _run_import("import app.tools.gateway; print('ok')")
    assert result.returncode == 0, result.stderr


def test_pipeline_and_tools_public_exports_remain_lazy_and_compatible():
    result = _run_import(
        "from app.pipeline import TablePipeline; from app.tools import ToolGateway; "
        "assert TablePipeline.__name__ == 'TablePipeline'; "
        "assert ToolGateway.__name__ == 'ToolGateway'"
    )
    assert result.returncode == 0, result.stderr


def test_pipeline_and_gateway_import_in_both_orders():
    for code in (
        "import app.pipeline.outline; import app.tools.gateway",
        "import app.tools.gateway; import app.pipeline.outline",
    ):
        result = _run_import(code)
        assert result.returncode == 0, result.stderr
