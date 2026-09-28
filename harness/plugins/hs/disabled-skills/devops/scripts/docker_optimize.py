#!/usr/bin/env python3
"""
Dockerfile Optimization Analyzer

Analyzes Dockerfiles for optimization opportunities including multi-stage builds,
security issues, size reduction, and best practices.

Instructions are read via `dockerfile_parse.DockerfileParser` (fileobj mode — the
analyzer accepts an arbitrary path/filename, not necessarily named `Dockerfile`,
so the path-based mode `DockerfileParser(path=...)` is unusable: it treats any
path NOT literally ending in `Dockerfile` as a directory). This replaces a
hand-rolled per-physical-line scan, which read backslash-continued
instructions (`RUN a && \\` / `    b`) as separate lines: a cleanup command on a
continuation line of the SAME RUN was reported as missing (false positive), and
a secret split across a continuation could be missed entirely (false negative).
`self.instructions` gives one entry per LOGICAL instruction with continuations
already joined (`content`), which every analyze_* method below reads instead of
`self.lines` (kept only for the raw physical-line count).

Usage:
    python docker-optimize.py Dockerfile
    python docker-optimize.py --json Dockerfile
    python docker-optimize.py --verbose Dockerfile
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict

from dockerfile_parse import DockerfileParser

# Windows UTF-8 compatibility (works for both local and global installs)
CLAUDE_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(CLAUDE_ROOT / 'scripts'))
try:
    from win_compat import ensure_utf8_stdout
    ensure_utf8_stdout()
except ImportError:
    if sys.platform == 'win32':
        import io
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class DockerfileAnalyzer:
    """Analyze Dockerfile for optimization opportunities."""

    def __init__(self, dockerfile_path: Path, verbose: bool = False):
        """
        Initialize analyzer.

        Args:
            dockerfile_path: Path to Dockerfile
            verbose: Enable verbose output
        """
        self.dockerfile_path = Path(dockerfile_path)
        self.verbose = verbose
        self.lines = []
        self.instructions = []
        self.issues = []
        self.suggestions = []

    def load_dockerfile(self) -> bool:
        """
        Load and parse Dockerfile.

        Returns:
            True if loaded successfully

        Raises:
            FileNotFoundError: If Dockerfile doesn't exist
        """
        if not self.dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {self.dockerfile_path}")

        with open(self.dockerfile_path, 'r') as f:
            self.lines = f.readlines()

        # fileobj mode (not path=) so an arbitrary filename works — path mode
        # treats anything not literally ending in "Dockerfile" as a directory.
        # Read-only: DockerfileParser only truncates on an explicit content
        # write, never on parsing .structure.
        with open(self.dockerfile_path, 'rb') as f:
            parser = DockerfileParser(fileobj=f, env_replace=False)
            # 1-based `line` (matching the old enumerate(self.lines, 1)
            # convention) alongside the raw 0-based startline/endline the
            # gap-detection in analyze_combine_run needs.
            self.instructions = [
                {**ins, 'line': ins['startline'] + 1}
                for ins in parser.structure
            ]

        return True

    def analyze_base_image(self) -> None:
        """Check base image for optimization opportunities."""
        for ins in self.instructions:
            if ins['instruction'] != 'FROM':
                continue
            line = ins['content'].strip()
            # `value` is the FROM argument alone (no "FROM " prefix, from
            # dockerfile_parse) — e.g. "node:20-alpine AS build" or "node".
            # Drop a trailing " AS alias" before reading the image reference so
            # a multi-stage alias never gets mistaken for part of the tag.
            image_ref = ins['value'].split()[0] if ins['value'] else ''
            has_digest = '@' in image_ref
            has_tag = ':' in image_ref and not has_digest
            tag = image_ref.split(':', 1)[1] if has_tag else None

            # Flag `:latest` or a fully bare reference (no tag, no digest) —
            # checking the parsed tag/digest instead of raw substrings like
            # `': ' not in line` (a colon+space never appears in `image:tag`,
            # so that old check flagged every correctly-tagged image too).
            if not has_digest and (tag == 'latest' or not has_tag):
                self.issues.append({
                    'line': ins['line'],
                    'severity': 'warning',
                    'category': 'base_image',
                    'message': 'Base image uses :latest or no tag',
                    'suggestion': 'Use specific version tags for reproducibility'
                })

            # Check for non-alpine/slim variants
            if 'node' in line.lower() and 'alpine' not in line.lower():
                self.suggestions.append({
                    'line': ins['line'],
                    'category': 'size',
                    'message': 'Consider using Alpine variant',
                    'suggestion': 'node:20-alpine is ~10x smaller than node:20'
                })

    def analyze_multi_stage(self) -> None:
        """Check if multi-stage build is used."""
        from_count = sum(1 for ins in self.instructions if ins['instruction'] == 'FROM')

        if from_count == 1:
            # Check if build tools are installed — `content` joins any
            # backslash continuation, so a tool named only on a continuation
            # line of a RUN is still caught.
            has_build_tools = any(
                any(tool in ins['content'].lower()
                    for tool in ['gcc', 'make', 'build-essential', 'npm install', 'pip install'])
                for ins in self.instructions
            )

            if has_build_tools:
                self.issues.append({
                    'line': 0,
                    'severity': 'warning',
                    'category': 'optimization',
                    'message': 'Single-stage build with build tools',
                    'suggestion': 'Use multi-stage build to exclude build dependencies from final image'
                })

    def analyze_layer_caching(self) -> None:
        """Check for optimal layer caching order."""
        copy_lines = [ins['content'].strip() for ins in self.instructions
                     if ins['instruction'] == 'COPY']

        # Check if dependency files copied before source
        has_package_copy = any('package.json' in line or 'requirements.txt' in line or 'go.mod' in line
                               for line in copy_lines)
        has_source_copy = any('COPY . .' in line or 'COPY ./' in line
                              for line in copy_lines)

        if has_source_copy and not has_package_copy:
            self.issues.append({
                'line': 0,
                'severity': 'warning',
                'category': 'caching',
                'message': 'Source copied before dependencies',
                'suggestion': 'Copy dependency files first (package.json, requirements.txt) then run install, then copy source'
            })

    def analyze_security(self) -> None:
        """Check for security issues."""
        has_user = any(
            ins['instruction'] == 'USER' and 'root' not in ins['value'].lower()
            and not (ins['value'].split() and ins['value'].split()[0] in ('0', 'root'))
            for ins in self.instructions
        )

        if not has_user:
            self.issues.append({
                'line': 0,
                'severity': 'error',
                'category': 'security',
                'message': 'Container runs as root',
                'suggestion': 'Create and use non-root user with USER instruction'
            })

        # Check for secrets in build — instruction-typed (ENV/ARG), not a
        # substring scan, so a comment mentioning "ENV" no longer false-flags,
        # and a secret split across a continuation line is still caught since
        # `content` joins it.
        for ins in self.instructions:
            if ins['instruction'] not in ('ENV', 'ARG'):
                continue
            if any(secret in ins['content'].upper()
                  for secret in ['PASSWORD', 'SECRET', 'TOKEN', 'API_KEY']):
                self.issues.append({
                    'line': ins['line'],
                    'severity': 'error',
                    'category': 'security',
                    'message': 'Potential secret in Dockerfile',
                    'suggestion': 'Use build-time arguments or runtime environment variables'
                })

    def analyze_apt_cache(self) -> None:
        """Check for apt cache cleanup.

        Reads the joined `content` of each RUN instruction rather than one
        physical line at a time: a `RUN apt-get install ... && \\` continued
        onto the NEXT physical line with `rm -rf /var/lib/apt/lists/*` used to
        be reported as "not cleaned" (each physical line checked in
        isolation), even though the cleanup is in the same layer.
        """
        for ins in self.instructions:
            if ins['instruction'] != 'RUN':
                continue
            content_lower = ins['content'].lower()
            if 'apt-get install' in content_lower or 'apt install' in content_lower:
                if 'rm -rf /var/lib/apt/lists/*' not in ins['content']:
                    self.suggestions.append({
                        'line': ins['line'],
                        'category': 'size',
                        'message': 'apt cache not cleaned in same layer',
                        'suggestion': 'Add && rm -rf /var/lib/apt/lists/* to reduce image size'
                    })

    def analyze_combine_run(self) -> None:
        """Check for multiple consecutive RUN commands."""
        consecutive_runs = 0
        first_run_line = 0
        prev_endline = None

        def flush():
            nonlocal consecutive_runs
            if consecutive_runs > 1:
                self.suggestions.append({
                    'line': first_run_line,
                    'category': 'layers',
                    'message': f'{consecutive_runs} consecutive RUN commands',
                    'suggestion': 'Combine related RUN commands with && to reduce layers'
                })
            consecutive_runs = 0

        for ins in self.instructions:
            # A blank source line between two RUNs is invisible in
            # `.structure` (only real instructions/comments are entries), so a
            # startline gap vs the previous instruction's endline stands in
            # for the physical-line break the old per-line scan saw.
            if prev_endline is not None and ins['startline'] > prev_endline + 1:
                flush()
            if ins['instruction'] == 'RUN':
                if consecutive_runs == 0:
                    first_run_line = ins['line']
                consecutive_runs += 1
            else:
                flush()
            prev_endline = ins['endline']

        # A trailing streak of RUNs (Dockerfile ends on RUN, nothing after to
        # trigger the else-branch flush() above) was never reported — flush
        # once more after the loop.
        flush()

    def analyze_workdir(self) -> None:
        """Check for WORKDIR usage."""
        has_workdir = any(ins['instruction'] == 'WORKDIR' for ins in self.instructions)

        if not has_workdir:
            self.suggestions.append({
                'line': 0,
                'category': 'best_practice',
                'message': 'No WORKDIR specified',
                'suggestion': 'Use WORKDIR to set working directory instead of cd commands'
            })

    def analyze(self) -> Dict:
        """
        Run all analyses.

        Returns:
            Analysis results dictionary
        """
        self.load_dockerfile()

        self.analyze_base_image()
        self.analyze_multi_stage()
        self.analyze_layer_caching()
        self.analyze_security()
        self.analyze_apt_cache()
        self.analyze_combine_run()
        self.analyze_workdir()

        return {
            'dockerfile': str(self.dockerfile_path),
            'total_lines': len(self.lines),
            'issues': self.issues,
            'suggestions': self.suggestions,
            'summary': {
                'errors': len([i for i in self.issues if i.get('severity') == 'error']),
                'warnings': len([i for i in self.issues if i.get('severity') == 'warning']),
                'suggestions': len(self.suggestions)
            }
        }

    def print_results(self, results: Dict) -> None:
        """
        Print analysis results in human-readable format.

        Args:
            results: Analysis results from analyze()
        """
        print(f"\nDockerfile Analysis: {results['dockerfile']}")
        print(f"Total lines: {results['total_lines']}")
        print(f"\nSummary:")
        print(f"  Errors: {results['summary']['errors']}")
        print(f"  Warnings: {results['summary']['warnings']}")
        print(f"  Suggestions: {results['summary']['suggestions']}")

        if results['issues']:
            print(f"\n{'='*60}")
            print("ISSUES:")
            print('='*60)
            for issue in results['issues']:
                severity = issue.get('severity', 'info').upper()
                line_info = f"Line {issue['line']}" if issue['line'] > 0 else "General"
                print(f"\n[{severity}] {line_info} - {issue['category']}")
                print(f"  {issue['message']}")
                print(f"  → {issue['suggestion']}")

        if results['suggestions']:
            print(f"\n{'='*60}")
            print("SUGGESTIONS:")
            print('='*60)
            for sugg in results['suggestions']:
                line_info = f"Line {sugg['line']}" if sugg['line'] > 0 else "General"
                print(f"\n{line_info} - {sugg['category']}")
                print(f"  {sugg['message']}")
                print(f"  → {sugg['suggestion']}")

        print()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Dockerfile for optimization opportunities",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "dockerfile",
        type=str,
        help="Path to Dockerfile"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    try:
        analyzer = DockerfileAnalyzer(
            dockerfile_path=args.dockerfile,
            verbose=args.verbose
        )

        results = analyzer.analyze()

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            analyzer.print_results(results)

        # Exit with error code if issues found
        if results['summary']['errors'] > 0:
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
