#!/usr/bin/env python3
"""
verify_docs_graph.py — RAG Foundation utility (kingdonb/mecris#202)

Scans the docs/ directory, builds a directed link graph from all markdown
files, and reports:
  - Broken outbound links (links pointing to non-existent files)
  - Orphaned docs (no inbound links from any other doc)

Handles both standard markdown links ([text](path)) and Obsidian-style
wikilinks ([[PageName]]).

Usage:
    python scripts/verify_docs_graph.py [--docs-dir docs] [--json]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Set

# Patterns for link extraction
MD_LINK_RE = re.compile(r'\[(?:[^\[\]]*)\]\(([^)]+)\)')
WIKI_LINK_RE = re.compile(r'\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]')


class LinkReport(NamedTuple):
    source: str
    target: str
    raw: str


def collect_docs(docs_dir: Path) -> List[Path]:
    """Return all .md files under docs_dir."""
    return sorted(docs_dir.rglob('*.md'))


FENCED_CODE_RE = re.compile(r'```.*?```', re.DOTALL)
INLINE_CODE_RE = re.compile(r'`[^`]+`')


def _strip_code_blocks(text: str) -> str:
    """Remove fenced and inline code spans to prevent false-positive link matches."""
    text = FENCED_CODE_RE.sub('', text)
    text = INLINE_CODE_RE.sub('', text)
    return text


def extract_links(file_path: Path, docs_dir: Path) -> List[LinkReport]:
    """Extract all internal doc links from a markdown file."""
    try:
        raw = file_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []

    text = _strip_code_blocks(raw)
    links: List[LinkReport] = []
    source_rel = str(file_path.relative_to(docs_dir.parent))

    # Standard markdown links
    for m in MD_LINK_RE.finditer(text):
        raw_target = m.group(1).strip()
        # Skip external URLs and anchors-only
        if raw_target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        # Strip anchor fragment
        target_path = raw_target.split('#')[0]
        if not target_path:
            continue
        links.append(LinkReport(source=source_rel, target=target_path, raw=raw_target))

    # Obsidian wikilinks
    for m in WIKI_LINK_RE.finditer(text):
        raw_target = m.group(1).strip()
        # Skip external URLs
        if raw_target.startswith(('http://', 'https://')):
            continue
        links.append(LinkReport(source=source_rel, target=raw_target, raw=f'[[{raw_target}]]'))

    return links


def resolve_link(source_file: Path, raw_target: str, docs_dir: Path, all_stems: Dict[str, Path]) -> Path | None:
    """
    Resolve a link target to an absolute Path, returning None if unresolvable.
    Handles:
      - Relative paths from the source file's directory
      - Bare filenames (matched against all .md stems in docs/)
    """
    # Try as a path relative to the source file's parent
    candidate = (source_file.parent / raw_target).resolve()
    if candidate.exists():
        return candidate

    # Try with .md extension appended
    candidate_md = (source_file.parent / (raw_target + '.md')).resolve()
    if candidate_md.exists():
        return candidate_md

    # Try as a bare stem (wikilink style or filename-only link)
    stem = Path(raw_target).stem
    if stem in all_stems:
        return all_stems[stem]

    # Try relative to repo root
    repo_root = docs_dir.parent
    candidate_root = (repo_root / raw_target).resolve()
    if candidate_root.exists():
        return candidate_root
    candidate_root_md = (repo_root / (raw_target + '.md')).resolve()
    if candidate_root_md.exists():
        return candidate_root_md

    return None


def build_graph(docs_dir: Path) -> tuple:
    """
    Build the link graph.

    Returns:
        (doc_files, inbound_counts, broken_links)
        where broken_links is a list of (source_rel, raw_target) tuples.
    """
    doc_files = collect_docs(docs_dir)

    # Build stem → path index for wikilink resolution
    all_stems: Dict[str, Path] = {f.stem: f for f in doc_files}

    inbound: Dict[str, Set[str]] = {str(f.relative_to(docs_dir.parent)): set() for f in doc_files}
    broken: List[tuple] = []

    for doc in doc_files:
        links = extract_links(doc, docs_dir)
        for link in links:
            resolved = resolve_link(doc, link.target, docs_dir, all_stems)
            if resolved is None:
                broken.append((link.source, link.raw))
            else:
                try:
                    target_rel = str(resolved.relative_to(docs_dir.parent))
                    if target_rel in inbound:
                        inbound[target_rel].add(link.source)
                except ValueError:
                    pass  # resolved outside repo root — treat as external

    return doc_files, inbound, broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Verify the Mecris docs link graph.')
    parser.add_argument('--docs-dir', default='docs', help='Path to docs directory (default: docs)')
    parser.add_argument('--json', action='store_true', help='Output report as JSON')
    args = parser.parse_args(argv)

    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.is_dir():
        print(f"ERROR: docs directory not found: {docs_dir}", file=sys.stderr)
        return 1

    doc_files, inbound, broken = build_graph(docs_dir)

    orphaned = [
        rel for rel, sources in inbound.items()
        if not sources and not rel.endswith('NEXT_SESSION.md')
    ]
    orphaned.sort()
    broken.sort()

    if args.json:
        report = {
            'total_docs': len(doc_files),
            'broken_links': [{'source': s, 'target': t} for s, t in broken],
            'orphaned_docs': orphaned,
        }
        print(json.dumps(report, indent=2))
        return 0

    # Human-readable output
    print(f"📂 Docs scanned: {len(doc_files)}")
    print()

    if broken:
        print(f"🔴 Broken links ({len(broken)}):")
        for source, target in broken:
            print(f"  {source} → {target}")
    else:
        print("✅ No broken links found.")
    print()

    if orphaned:
        print(f"⚠️  Orphaned docs ({len(orphaned)}) — no inbound links:")
        for o in orphaned:
            print(f"  {o}")
    else:
        print("✅ No orphaned docs found.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
