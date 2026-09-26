"""Import-lock regression test (Phase 2, repo-hygiene-restructure).

Locks the current import surface of the four packages the ai-service wheel
ships (`ai-service/pyproject.toml:49` -> `packages = ["src/contract_ocr",
"src/benchmark", "app", "fixtures"]`) so a later restructure cannot silently
break resolution. Does NOT call `git` and does NOT import
`contract_intelligence` (the backend package).

Grep decision record (Phase 2, Implement step 1):
    git grep -n -e contract_ocr -e "from app" -e "import app" \
        -- ai-service/frontend ai-service/ocr-benchmark
    -> Result: 1 hit, NOT a runtime import:
         ai-service/ocr-benchmark/config.yaml:14:
           "# step in contract_ocr/infrastructure/image/preprocessing.py
           crashes with ..."
       That line is a YAML comment documenting a known bug by file path;
       it is not a Python `import`/`from` statement and this file is not
       executable Python. No other matches. No runtime import from
       `ai-service/frontend` or `ai-service/ocr-benchmark` into
       `contract_ocr` or `app`. Decision: leave both trees in place, no
       move performed (see phase-2-restructure.md "Quyet dinh da kiem").
"""

import contract_ocr  # noqa: F401
import app  # noqa: F401
import benchmark  # noqa: F401
import fixtures  # noqa: F401


def test_contract_ocr_importable() -> None:
    assert contract_ocr is not None


def test_app_importable() -> None:
    assert app is not None


def test_benchmark_importable() -> None:
    assert benchmark is not None


def test_fixtures_importable() -> None:
    assert fixtures is not None
