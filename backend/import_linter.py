"""CLI entrypoint for running import-linter via `python -m import_linter`."""

import sys

from importlinter.cli import lint_imports_command

if __name__ == "__main__":
    sys.exit(lint_imports_command())
