#!/usr/bin/env python3
"""
Extract Writing Styles from assets/writing-styles/ directory.

Supports multiple file types:
- Text: .md, .txt
- Documents: .pdf, .docx, .xlsx, .pptx (via document_converter.py)
- Media: .jpg, .jpeg, .png, .webp, .mp4, .mov (via gemini_batch_process.py)

Usage:
    python extract-writing-styles.py --list         # List available style files
    python extract-writing-styles.py --style <name> # Extract specific style
    python extract-writing-styles.py --all          # Extract all styles
    python extract-writing-styles.py --all --json   # Output as JSON
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from markdown_it import MarkdownIt


# File type categories
TEXT_FORMATS = {'.md', '.txt'}
DOC_FORMATS = {'.pdf', '.docx', '.xlsx', '.pptx'}
IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
VIDEO_FORMATS = {'.mp4', '.mov', '.avi', '.mkv'}
ALL_FORMATS = TEXT_FORMATS | DOC_FORMATS | IMAGE_FORMATS | VIDEO_FORMATS


def find_project_root(start_dir: Path) -> Path:
    """Find project root by looking for .claude directory."""
    for parent in [start_dir] + list(start_dir.parents):
        if (parent / '.claude').exists():
            return parent
    return start_dir


PROJECT_ROOT = find_project_root(Path(__file__).parent)
STYLES_DIR = PROJECT_ROOT / 'assets' / 'writing-styles'
# ai-multimodal lives as a sibling skill in the same skills tree; resolve it
# relative to this script (…/skills/copywriting/scripts/…), not a .claude path.
AI_MULTIMODAL_SCRIPTS = Path(__file__).resolve().parents[2] / 'ai-multimodal' / 'scripts'


def get_style_files() -> Dict[str, Any]:
    """List all style files in the writing-styles directory."""
    if not STYLES_DIR.exists():
        return {'error': f'Directory not found: {STYLES_DIR}', 'files': []}

    files = []
    for f in STYLES_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in ALL_FORMATS:
            files.append({
                'name': f.stem,
                'path': str(f),
                'type': get_file_type(f),
                'size': f.stat().st_size
            })

    return {'files': sorted(files, key=lambda x: x['name']), 'directory': str(STYLES_DIR)}


def get_file_type(file_path: Path) -> str:
    """Categorize file by type."""
    ext = file_path.suffix.lower()
    if ext in TEXT_FORMATS:
        return 'text'
    if ext in DOC_FORMATS:
        return 'document'
    if ext in IMAGE_FORMATS:
        return 'image'
    if ext in VIDEO_FORMATS:
        return 'video'
    return 'unknown'


def extract_text_content(file_path: Path) -> str:
    """Extract content from text files (.md, .txt)."""
    try:
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        return f'Error reading file: {e}'


def extract_document_content(file_path: Path, verbose: bool = False) -> str:
    """Extract content from documents using document_converter.py."""
    converter = AI_MULTIMODAL_SCRIPTS / 'document_converter.py'
    if not converter.exists():
        return f'Error: document_converter.py not found at {converter}'

    output_file = STYLES_DIR / f'.temp_{file_path.stem}_extraction.md'

    try:
        cmd = [
            sys.executable, str(converter),
            '--input', str(file_path),
            '--output', str(output_file),
            '--prompt', '''Extract the writing style characteristics from this document.
Identify: tone, vocabulary, sentence structure, rhetorical devices, formatting patterns.
Output as structured markdown with clear sections.'''
        ]
        if verbose:
            cmd.append('--verbose')

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if output_file.is_file():
            content = output_file.read_text(encoding='utf-8')
            output_file.unlink()  # Clean up temp file
            return content
        else:
            return f'Conversion failed: {result.stderr}'

    except subprocess.TimeoutExpired:
        return 'Error: Document conversion timed out'
    except Exception as e:
        return f'Error: {e}'


def extract_media_content(file_path: Path, verbose: bool = False) -> str:
    """Extract writing style from media using gemini_batch_process.py."""
    processor = AI_MULTIMODAL_SCRIPTS / 'gemini_batch_process.py'
    if not processor.exists():
        return f'Error: gemini_batch_process.py not found at {processor}'

    try:
        prompt = '''Analyze this content and identify any writing style characteristics visible.
Look for: text overlays, captions, typography choices, messaging tone, branding voice.
Describe the writing style in terms of: tone, vocabulary level, sentence structure, key phrases.
Output as structured analysis.'''

        cmd = [
            sys.executable, str(processor),
            '--files', str(file_path),
            '--task', 'analyze',
            '--prompt', prompt
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.stdout if result.stdout else result.stderr

    except subprocess.TimeoutExpired:
        return 'Error: Media analysis timed out'
    except Exception as e:
        return f'Error: {e}'


# Reads structure (thead/tbody, heading level) from the CommonMark token
# stream instead of guessing "header vs data" / "heading vs code-comment"
# from surrounding text — see plans/260726-1837-sequence-ownership-hs-cli/
# library/evidences/markdown-it-py-b3.md for the two live bugs this
# replaced: a table header row was misread as a data row whenever it did
# not contain the literal word "Style", and a fenced code line starting
# with `#`/`##` was misread as a title/section heading.
_MD = MarkdownIt("commonmark", {"linkify": False}).enable("table")


def _title_from_markdown(content: str) -> str:
    """The document's first H1 heading text, or '' when absent."""
    tokens = _MD.parse(content)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h1":
            return tokens[i + 1].content.strip()
    return ""


def _sections_from_markdown(content: str) -> List[Dict[str, Any]]:
    """Every H2 heading as {'title', 'lineNumber'} (1-indexed), in document order."""
    tokens = _MD.parse(content)
    sections: List[Dict[str, Any]] = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h2":
            line_no = (tok.map[0] + 1) if tok.map else None
            sections.append({"title": tokens[i + 1].content.strip(), "lineNumber": line_no})
    return sections


# CommonMark ends a table the instant an HTML block interrupts it (a `tbody`
# never re-opens for rows after the interruption — see the b3 evidence cited
# above). A bare `<!--...-->` line is a real HTML block by the same rule, so
# three files in this skill tree lose 44%/16/1 rows to a mid-table comment
# used purely as a phase marker (harness/plugins/hs/skills/cti-expert/
# references/activation-matrix-and-tooling.md:23-26,69-81,
# command-reference.md:32-35, techniques-and-workflows.md:18-21) — none of
# that comment text is meant to be visible content, so dropping the whole
# line before parsing (not just the `<!--...-->` substring) rejoins the
# table exactly as if the marker were never there.
#
# Rejected alternatives:
#  - Rejoining table-token fragments after parsing: markdown-it never emits
#    a second `table_open`/`tbody_open` pair for the continuation — the
#    rows after the comment become a bare paragraph, so there is no table
#    token to rejoin; would need re-tokenizing raw lines by hand, which is
#    what the earlier regex parser did and is exactly the class of bug this
#    module replaced it to avoid.
#  - Stripping ANY `<!--...-->` substring (not just whole-line comments):
#    would also eat an inline comment sitting next to real content and,
#    without fence-tracking, corrupt literal `<!-- ... -->` example text
#    inside a fenced code block (real case:
#    harness/plugins/hs/skills/drawio/references/style-extraction-sample.md
#    uses standalone comment lines as XML sample content inside ```xml).
#    Pre-stripping only whole comment LINES, and only outside a fence,
#    avoids both.
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_STANDALONE_HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")


def _strip_standalone_html_comments(content: str) -> str:
    """Drop whole-line HTML comments outside fenced code blocks so they
    cannot split a table; a comment sharing a line with real content, an
    unterminated (multi-line) comment, or any comment inside a fence is
    left untouched — see the module-level note above `_styles_from_markdown`."""
    in_fence = False
    kept: List[str] = []
    for line in content.split("\n"):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            kept.append(line)
            continue
        if not in_fence and _STANDALONE_HTML_COMMENT_RE.match(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def _styles_from_markdown(content: str) -> List[Dict[str, str]]:
    """Style entries from every markdown table's DATA rows (thead/tbody are read
    from the real table structure, not guessed from column text) — a header row
    is excluded because it is a `thead` row, regardless of what it says."""
    tokens = _MD.parse(_strip_standalone_html_comments(content))
    styles: List[Dict[str, str]] = []
    in_tbody = False
    row: List[str] = []
    for tok in tokens:
        if tok.type == "tbody_open":
            in_tbody = True
        elif tok.type == "tbody_close":
            in_tbody = False
        elif tok.type == "tr_open" and in_tbody:
            row = []
        elif tok.type == "inline" and in_tbody:
            row.append(tok.content.strip())
        elif tok.type == "tr_close" and in_tbody:
            if len(row) >= 2:
                styles.append({
                    "name": re.sub(r"\*+", "", row[0]),
                    "keywords": row[1],
                    "description": " | ".join(row[2:]) if len(row) > 2 else "",
                })
    return styles


def extract_style_content(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Extract writing style content from any supported file type."""
    if not file_path.exists():
        return {'error': f'File not found: {file_path}'}

    file_type = get_file_type(file_path)

    if file_type == 'text':
        content = extract_text_content(file_path)
    elif file_type == 'document':
        content = extract_document_content(file_path, verbose)
    elif file_type in ('image', 'video'):
        content = extract_media_content(file_path, verbose)
    else:
        return {'error': f'Unsupported file type: {file_path.suffix}'}

    # Parse the content for style information
    result = {
        'file': str(file_path),
        'type': file_type,
        'title': '',
        'sections': [],
        'styles': [],
        'rawContent': content
    }

    # Extract title from first H1, sections from H2 headings, and style
    # entries from table DATA rows — all via the real CommonMark structure.
    result['title'] = _title_from_markdown(content)
    result['sections'] = _sections_from_markdown(content)
    result['styles'] = _styles_from_markdown(content)

    return result


def format_output(data: Dict[str, Any], as_json: bool = False) -> str:
    """Format output for display."""
    if as_json:
        return json.dumps(data, indent=2, ensure_ascii=False)

    if 'error' in data:
        return f"Error: {data['error']}"

    output = []

    if 'files' in data:
        # List mode
        output.append('# Available Writing Styles\n')
        output.append(f"Directory: {data['directory']}\n")

        if not data['files']:
            output.append('\nNo style files found. Add files to assets/writing-styles/')
        else:
            output.append('\n| Style | Type | Size |')
            output.append('|---|---|---|')
            for f in data['files']:
                size_kb = f['size'] / 1024
                output.append(f"| {f['name']} | {f['type']} | {size_kb:.1f}KB |")

    elif 'title' in data:
        # Single style extraction
        if data.get('title'):
            output.append(f"# {data['title']}\n")

        output.append(f"**File Type:** {data.get('type', 'unknown')}\n")

        if data.get('styles'):
            output.append(f"\n## Extracted Styles ({len(data['styles'])})\n")
            for s in data['styles'][:30]:  # Limit to 30 styles
                output.append(f"### {s['name']}")
                output.append(f"**Keywords:** {s['keywords']}\n")

        if data.get('sections'):
            output.append('\n## Sections\n')
            for s in data['sections']:
                output.append(f"- {s['title']} (line {s['lineNumber']})")

    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(
        description='Extract writing styles from assets/writing-styles/ directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Supported formats:
  Text:      .md, .txt
  Documents: .pdf, .docx, .xlsx, .pptx (requires GEMINI_API_KEY)
  Images:    .jpg, .jpeg, .png, .webp (requires GEMINI_API_KEY)
  Videos:    .mp4, .mov (requires GEMINI_API_KEY)

Examples:
  python extract-writing-styles.py --list
  python extract-writing-styles.py --style default
  python extract-writing-styles.py --all --json
        '''
    )

    parser.add_argument('--list', action='store_true', help='List available style files')
    parser.add_argument('--style', type=str, help='Extract specific style by name')
    parser.add_argument('--all', action='store_true', help='Extract all styles')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.list or (not args.style and not args.all):
        result = get_style_files()
    elif args.style:
        # Find the file with matching name
        style_files = get_style_files()
        if 'error' in style_files:
            result = style_files
        else:
            matching = [f for f in style_files['files'] if f['name'] == args.style]
            if matching:
                result = extract_style_content(Path(matching[0]['path']), args.verbose)
            else:
                result = {'error': f"Style '{args.style}' not found"}
    elif args.all:
        style_files = get_style_files()
        if 'error' in style_files:
            result = style_files
        else:
            result = {
                'title': 'All Writing Styles',
                'files': []
            }
            for f in style_files['files']:
                extracted = extract_style_content(Path(f['path']), args.verbose)
                result['files'].append({'name': f['name'], **extracted})
    else:
        result = get_style_files()

    print(format_output(result, args.json))


if __name__ == '__main__':
    main()
