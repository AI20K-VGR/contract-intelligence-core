"""pytest path setup — _docslib không cài như package, import qua sys.path."""
import sys
from pathlib import Path

# .../skills/_docslib/tests/conftest.py → parent[1] = _docslib (chứa package docslib/)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
