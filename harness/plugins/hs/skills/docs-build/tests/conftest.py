"""pytest path setup cho docs-build tests — _docslib + scripts trên sys.path."""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2] / "_docslib"))        # docslib package
sys.path.insert(0, str(_HERE.parents[1] / "scripts"))          # ssg_engine, build helpers
