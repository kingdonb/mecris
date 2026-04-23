#!/usr/bin/env python3
"""
chunk_session_logs.py — RAG Foundation utility (kingdonb/mecris#202)

Splits the monolithic session_log.md into per-day chunk files with YAML
front-matter metadata, written to attic/session-chunks/.

Each chunk file contains all session entries recorded on that date.
The initial preamble (before the first dated section) is saved as
attic/session-chunks/PREAMBLE.md.

Usage:
    python scripts/chunk_session_logs.py [--input session_log.md] [--output-dir attic/session-chunks] [--dry-run]
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

# Matches section headers like:
#   ## 2026-04-02 — Ghost Presence Phase 1 (session 16)
#   ## 🏛️ 2026-04-01 — Session 5: ...
DATE_HEADER_RE = re.compile(
    r'^(#{1,3})\s*(?:🏛️\s*)?(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.+)$'
)


def parse_log(text: str) -> tuple[str, Dict[str, List[tuple]]]:
    """
    Parse session_log.md into a preamble and a date-keyed dict of sections.

    Returns:
        (preamble_text, {date_str: [(heading_level, title, body), ...]})
    """
    lines = text.splitlines(keepends=True)
    preamble_lines: List[str] = []
    sections: Dict[str, List[tuple]] = {}
    current_date: str | None = None
    current_entry: List[str] = []
    current_meta: tuple | None = None

    def flush():
        nonlocal current_date, current_entry, current_meta
        if current_meta and current_date:
            level, title, _ = current_meta
            body = ''.join(current_entry).rstrip()
            sections.setdefault(current_date, []).append((level, title, body))
        current_entry = []
        current_meta = None

    in_preamble = True

    for line in lines:
        m = DATE_HEADER_RE.match(line.rstrip('\n'))
        if m:
            flush()
            in_preamble = False
            level = m.group(1)
            date_str = m.group(2)
            title = m.group(3).strip()
            current_date = date_str
            current_meta = (level, title, date_str)
            current_entry = [line]
        elif in_preamble:
            preamble_lines.append(line)
        else:
            current_entry.append(line)

    flush()
    return ''.join(preamble_lines), sections


def extract_primary_activity(entries: List[tuple]) -> str:
    """Derive a one-line primary activity label from the session entries."""
    if not entries:
        return 'unknown'
    # Use the title of the first entry
    return entries[0][1]


def write_chunk(output_dir: Path, date_str: str, entries: List[tuple], dry_run: bool) -> Path:
    """Write a per-day chunk file with YAML front-matter."""
    primary = extract_primary_activity(entries)
    entry_count = len(entries)

    front_matter = (
        f"---\n"
        f"date: {date_str}\n"
        f"primary_activity: \"{primary}\"\n"
        f"entry_count: {entry_count}\n"
        f"source: session_log.md\n"
        f"---\n\n"
    )

    body_parts = []
    for _, _, entry_body in entries:
        body_parts.append(entry_body)

    content = front_matter + '\n\n'.join(body_parts) + '\n'
    out_path = output_dir / f'{date_str}.md'

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding='utf-8')

    return out_path


def write_preamble(output_dir: Path, preamble: str, dry_run: bool) -> Path | None:
    if not preamble.strip():
        return None
    front_matter = (
        "---\n"
        "date: preamble\n"
        "primary_activity: \"Initial debugging and setup narrative\"\n"
        "source: session_log.md\n"
        "---\n\n"
    )
    content = front_matter + preamble
    out_path = output_dir / 'PREAMBLE.md'
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding='utf-8')
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Split session_log.md into per-day chunk files.')
    parser.add_argument('--input', default='session_log.md', help='Path to session_log.md (default: session_log.md)')
    parser.add_argument('--output-dir', default='attic/session-chunks', help='Output directory (default: attic/session-chunks)')
    parser.add_argument('--dry-run', action='store_true', help='Parse and report without writing files')
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1

    text = input_path.read_text(encoding='utf-8', errors='replace')
    preamble, sections = parse_log(text)

    dates_sorted = sorted(sections.keys())
    total_entries = sum(len(v) for v in sections.values())

    print(f"📓 Parsed {total_entries} session entries across {len(dates_sorted)} dates.")
    if preamble.strip():
        print(f"   + preamble ({len(preamble.splitlines())} lines)")
    print()

    if args.dry_run:
        print("🔍 Dry run — no files written.")
        for date_str in dates_sorted:
            entries = sections[date_str]
            print(f"  {output_dir}/{date_str}.md  ({len(entries)} entries)")
        return 0

    written = 0
    for date_str in dates_sorted:
        out_path = write_chunk(output_dir, date_str, sections[date_str], dry_run=False)
        print(f"  ✅ {out_path}")
        written += 1

    preamble_path = write_preamble(output_dir, preamble, dry_run=False)
    if preamble_path:
        print(f"  ✅ {preamble_path} (preamble)")

    print()
    print(f"📦 Done. {written} chunk files written to {output_dir}/")
    return 0


if __name__ == '__main__':
    sys.exit(main())
