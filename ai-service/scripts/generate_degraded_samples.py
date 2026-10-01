"""CLI wrapper; install the package before running."""

import sys

from contract_ocr.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main(["generate-degraded", *sys.argv[1:]]))
