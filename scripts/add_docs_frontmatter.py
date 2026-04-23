#!/usr/bin/env python3
"""
add_docs_frontmatter.py — RAG Foundation utility (kingdonb/mecris#202)

Stamps all docs/**/*.md files with a YAML front-matter block containing:
  - title: derived from the first H1 heading or the filename stem
  - description: derived from the first non-heading paragraph
  - tags: list inferred from the filename stem (split on _ and -)
  - date: ISO date from git log (file addition) or file mtime

Idempotent: files that already start with a YAML front-matter block (---)
are skipped unless --force is passed.

Usage:
    python scripts/add_docs_frontmatter.py [--docs-dir docs] [--dry-run] [--force]
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Regex to detect existing front-matter
FM_START_RE = re.compile(r'^---\s*\n', re.MULTILINE)

# Heading regex (any H1)
H1_RE = re.compile(r'^#{1}\s+(.+)', re.MULTILINE)

# Paragraph extraction — first block of non-empty, non-heading, non-fence text
PARA_RE = re.compile(r'(?:^(?!#|```|---|\|)(.+)\n)+', re.MULTILINE)

# Words to exclude when building tags from filename stems
_STOP = frozenset({
    'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'for',
    'with', 'by', 'from', 'is', 'it', 'its', 'be', 'as', 'vs', 'api',
})


def _get_git_date(file_path: Path) -> Optional[str]:
    """Return ISO date of the commit that first introduced the file, or None."""
    try:
        result = subprocess.run(
            ['git', 'log', '--follow', '--diff-filter=A', '--format=%ai', '--', str(file_path)],
            capture_output=True, text=True, timeout=5,
        )
        line = result.stdout.strip().split('\n')[-1].strip()
        if line:
            # Parse 'YYYY-MM-DD HH:MM:SS +ZZZZ' → 'YYYY-MM-DD'
            return line[:10]
    except Exception:
        pass
    return None


def _get_mtime_date(file_path: Path) -> str:
    """Return ISO date from file mtime."""
    ts = file_path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')


def _extract_title(text: str, stem: str) -> str:
    """Extract the first H1 heading, stripping markdown formatting."""
    m = H1_RE.search(text)
    if m:
        # Remove inline markup (bold, italic, backticks, links)
        title = re.sub(r'[*_`]', '', m.group(1))
        title = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', title)
        return title.strip()
    # Fallback: title-case the stem
    return stem.replace('_', ' ').replace('-', ' ').title()


def _extract_description(text: str) -> str:
    """Extract the first substantial paragraph (>= 20 chars), stripping markdown."""
    # Remove front-matter block if present
    body = re.sub(r'^---.*?---\s*', '', text, count=1, flags=re.DOTALL)
    # Remove H1 line
    body = re.sub(r'^#+\s+.+\n', '', body, count=1, flags=re.MULTILINE)
    # Remove blockquotes intro lines (common in this codebase)
    body = re.sub(r'^>.*\n', '', body, flags=re.MULTILINE)
    # Remove horizontal rules
    body = re.sub(r'^---+\s*\n', '', body, flags=re.MULTILINE)
    # Remove fenced code blocks
    body = re.sub(r'```.*?```', '', body, flags=re.DOTALL)

    for line in body.split('\n'):
        line = line.strip()
        if len(line) >= 20 and not line.startswith(('#', '|', '-', '*', '!')):
            # Strip inline markdown
            line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
            line = re.sub(r'[*_`]', '', line)
            return line[:200].strip()
    return 'Mecris project documentation.'


def _extract_tags(stem: str) -> list[str]:
    """Build a tag list from the filename stem."""
    words = re.split(r'[_\-]+', stem.lower())
    # Filter stop words and very short tokens, deduplicate preserving order
    seen: set[str] = set()
    tags: list[str] = []
    for w in words:
        if w and w not in _STOP and len(w) > 2 and w not in seen:
            tags.append(w)
            seen.add(w)
    return tags


def build_frontmatter(title: str, description: str, tags: list[str], date: str) -> str:
    """Render a YAML front-matter block."""
    tag_str = ', '.join(f'"{t}"' for t in tags)
    # Escape quotes in title/description for YAML safety
    safe_title = title.replace('"', "'")
    safe_desc = description.replace('"', "'")
    return (
        f'---\n'
        f'title: "{safe_title}"\n'
        f'description: "{safe_desc}"\n'
        f'tags: [{tag_str}]\n'
        f'date: "{date}"\n'
        f'---\n\n'
    )


def process_file(file_path: Path, docs_root: Path, dry_run: bool, force: bool) -> str:
    """
    Stamp a single file with front-matter.

    Returns one of: 'skipped', 'would_update', 'updated', 'error'.
    """
    try:
        text = file_path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        print(f"  ERROR reading {file_path}: {exc}", file=sys.stderr)
        return 'error'

    has_fm = text.startswith('---')
    if has_fm and not force:
        return 'skipped'

    stem = file_path.stem
    title = _extract_title(text, stem)
    description = _extract_description(text)
    tags = _extract_tags(stem)
    date = _get_git_date(file_path) or _get_mtime_date(file_path)

    fm_block = build_frontmatter(title, description, tags, date)

    if dry_run:
        rel = file_path.relative_to(docs_root.parent)
        print(f"  would update: {rel}")
        return 'would_update'

    if has_fm and force:
        # Strip existing front-matter before prepending new one
        body = re.sub(r'^---.*?---\s*\n?', '', text, count=1, flags=re.DOTALL)
        new_text = fm_block + body
    else:
        new_text = fm_block + text

    file_path.write_text(new_text, encoding='utf-8')
    rel = file_path.relative_to(docs_root.parent)
    print(f"  updated: {rel}")
    return 'updated'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Add YAML front-matter to all docs/ markdown files.'
    )
    parser.add_argument('--docs-dir', default='docs', help='Path to docs directory (default: docs)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would change without writing')
    parser.add_argument('--force', action='store_true', help='Overwrite existing front-matter')
    args = parser.parse_args(argv)

    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.is_dir():
        print(f"ERROR: docs directory not found: {docs_dir}", file=sys.stderr)
        return 1

    files = sorted(docs_dir.rglob('*.md'))
    if not files:
        print("No .md files found.", file=sys.stderr)
        return 1

    counts = {'skipped': 0, 'updated': 0, 'would_update': 0, 'error': 0}
    mode = 'DRY RUN — ' if args.dry_run else ''
    print(f"📝 {mode}Processing {len(files)} docs files...")
    for f in files:
        result = process_file(f, docs_dir, dry_run=args.dry_run, force=args.force)
        counts[result] += 1

    print()
    if args.dry_run:
        print(f"Would update: {counts['would_update']}  |  Already have front-matter: {counts['skipped']}  |  Errors: {counts['error']}")
    else:
        print(f"Updated: {counts['updated']}  |  Already have front-matter (skipped): {counts['skipped']}  |  Errors: {counts['error']}")

    return 0 if counts['error'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
