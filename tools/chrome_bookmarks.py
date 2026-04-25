"""tools/chrome_bookmarks.py — Chrome Bookmarks parser for Mecris MCP.

Parses Chrome's JSON bookmarks file, flattens the nested tree into a
searchable list, and provides keyword filtering for the MCP endpoint
get_bookmarks_by_topic (kingdonb/mecris#201).
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Chrome stores date_added as microseconds since 1601-01-01 (WebKit/Windows FILETIME epoch).
_WEBKIT_EPOCH_OFFSET_US = 11_644_473_600 * 1_000_000  # seconds → microseconds


def _webkit_to_datetime(webkit_us: int) -> Optional[datetime]:
    """Convert Chrome's WebKit timestamp (µs since 1601-01-01) to UTC datetime.

    Returns None if the value is out of the platform's representable range.
    """
    try:
        unix_us = int(webkit_us) - _WEBKIT_EPOCH_OFFSET_US
        return datetime.fromtimestamp(unix_us / 1_000_000, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _default_bookmarks_path() -> str:
    """Return the platform-appropriate Chrome Bookmarks file path."""
    if sys.platform == "darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Google/Chrome/Default/Bookmarks"
        )
    # Linux fallback — check Chromium too for CI environments
    for candidate in (
        "~/.config/google-chrome/Default/Bookmarks",
        "~/.config/chromium/Default/Bookmarks",
    ):
        expanded = os.path.expanduser(candidate)
        if os.path.exists(expanded):
            return expanded
    return os.path.expanduser("~/.config/google-chrome/Default/Bookmarks")


def _flatten_node(node: Dict, results: List[Dict], folder_path: str = "") -> None:
    """Recursively flatten a Chrome bookmark tree node into *results*."""
    node_type = node.get("type")
    name = node.get("name", "")

    if node_type == "url":
        date_added_raw = node.get("date_added", "0")
        dt = _webkit_to_datetime(int(date_added_raw))
        results.append(
            {
                "title": name,
                "url": node.get("url", ""),
                "date_added": dt.isoformat() if dt else None,
                "folder": folder_path,
            }
        )
    elif node_type == "folder":
        new_path = f"{folder_path}/{name}" if folder_path else name
        for child in node.get("children", []):
            _flatten_node(child, results, new_path)


def load_bookmarks(path: Optional[str] = None) -> Dict:
    """Load the raw Chrome Bookmarks JSON dict.

    Returns an empty dict on FileNotFoundError, PermissionError, or JSON parse errors
    so callers never have to handle exceptions.
    """
    bookmarks_path = path or _default_bookmarks_path()
    try:
        with open(bookmarks_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {}


def flatten_bookmarks(raw: Dict) -> List[Dict]:
    """Flatten a raw Chrome bookmarks dict into a list of bookmark dicts.

    Each dict has:
      - title (str): bookmark display name
      - url (str): target URL
      - date_added (str | None): ISO 8601 UTC string, or None if unparseable
      - folder (str): slash-delimited ancestor folder path (empty for top-level)
    """
    results: List[Dict] = []
    roots = raw.get("roots", {})
    for root_name in ("bookmark_bar", "other", "synced"):
        root_node = roots.get(root_name)
        if root_node:
            _flatten_node(root_node, results, folder_path="")
    return results


def filter_by_keyword(bookmarks: List[Dict], keyword: str) -> List[Dict]:
    """Case-insensitive keyword filter across title, url, and folder fields."""
    kw = keyword.lower().strip()
    if not kw:
        return bookmarks
    return [
        b
        for b in bookmarks
        if kw in b.get("title", "").lower()
        or kw in b.get("url", "").lower()
        or kw in b.get("folder", "").lower()
    ]


def get_bookmarks_by_topic(keyword: str, path: Optional[str] = None) -> Dict:
    """Load Chrome bookmarks and return those matching *keyword*.

    Args:
        keyword: Search term matched case-insensitively against title, url, and folder.
        path: Optional override for the bookmarks file path (used in tests).

    Returns a dict with:
      - keyword: the search term used
      - total_bookmarks: count of all bookmarks before filtering
      - match_count: number of matching bookmarks
      - matches: list of matching bookmark dicts
      - source: resolved path to the bookmarks file, or "not found"
    """
    bookmarks_path = path or _default_bookmarks_path()
    raw = load_bookmarks(bookmarks_path)
    if not raw:
        return {
            "keyword": keyword,
            "total_bookmarks": 0,
            "match_count": 0,
            "matches": [],
            "source": "not found",
        }
    all_bookmarks = flatten_bookmarks(raw)
    matches = filter_by_keyword(all_bookmarks, keyword)
    return {
        "keyword": keyword,
        "total_bookmarks": len(all_bookmarks),
        "match_count": len(matches),
        "matches": matches,
        "source": bookmarks_path,
    }
