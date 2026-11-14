#!/usr/bin/env python3
"""Build the Mecris blog: blog/*.md -> a static site.

Posts are plain Markdown named YYYY-MM-DD-slug.md. A post starts with an
`# H1` title, then optional `**Key:** value` lines (Author, Tags, Summary,
Status), then the body. `**Status:** draft` keeps a post out of the build
unless --drafts is given.

Usage: python blog/build.py [--out _site] [--drafts]
Every link in the output is relative, so the site works under any path.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BLOG_DIR = Path(__file__).resolve().parent
SITE_TITLE = "Mecris"
SITE_TAGLINE = (
    "Field notes from a personal accountability system, written by the "
    "agents who work on it and the human who answers for it."
)
SITE_URL = os.environ.get("BLOG_SITE_URL", "https://kingdonb.github.io/mecris").rstrip("/")
REPO_URL = "https://github.com/kingdonb/mecris"

POST_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-([a-z0-9][a-z0-9-]*)\.md$")
META_LINE = re.compile(r"^\*\*([A-Za-z ]+):\*\*\s*(.*?)\s*$")
AUTHOR_KEYS = ("author", "written by")
HIDDEN_KEYS = {"date", "summary", "status", *AUTHOR_KEYS}


@dataclass
class Post:
    slug: str
    day: date
    title: str
    body: str
    meta: dict = field(default_factory=dict)
    source_name: str = ""

    @property
    def author(self) -> str:
        for key in AUTHOR_KEYS:
            if self.meta.get(key):
                return self.meta[key]
        return ""

    @property
    def draft(self) -> bool:
        return self.meta.get("status", "").strip().lower() == "draft"

    @property
    def path(self) -> str:
        return f"posts/{self.day.isoformat()}-{self.slug}/"

    @property
    def summary(self) -> str:
        return self.meta.get("summary") or first_paragraph(self.body)


def plain_text(markdown_text: str) -> str:
    """Strip the Markdown syntax that shows up in a one-paragraph summary."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", markdown_text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def first_paragraph(body: str, limit: int = 240) -> str:
    in_fence = False
    for block in re.split(r"\n\s*\n", body):
        stripped = block.strip()
        if stripped.startswith("```"):
            in_fence = not (stripped.count("```") % 2 == 0)
            continue
        if in_fence or not stripped:
            continue
        if stripped[0] in "#|>-*+" or stripped.startswith("---") or re.match(r"^\d+\.", stripped):
            continue
        # A paragraph may run straight into a list; keep only the prose lines.
        prose = []
        for line in stripped.splitlines():
            if re.match(r"^\s*([-*+]|\d+\.)\s", line):
                break
            prose.append(line)
        text = plain_text(" ".join(prose))
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
        return text
    return ""


def parse_post(name: str, text: str) -> Post:
    match = POST_NAME.match(name)
    if not match:
        raise ValueError(f"{name}: post files must be named YYYY-MM-DD-slug.md")
    year, month, day, slug = match.groups()
    lines = text.splitlines()

    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not lines[i].startswith("# "):
        raise ValueError(f"{name}: a post must start with an '# H1' title")
    title = plain_text(lines[i][2:])
    i += 1

    meta: dict = {}
    while i < len(lines):
        line = lines[i].strip()
        found = META_LINE.match(line)
        if found:
            meta[found.group(1).strip().lower()] = found.group(2).strip()
        elif line and line != "---":
            break
        elif line == "---":
            i += 1
            break
        i += 1

    return Post(
        slug=slug,
        day=date(int(year), int(month), int(day)),
        title=title,
        body="\n".join(lines[i:]).strip() + "\n",
        meta=meta,
        source_name=name,
    )


def load_posts(blog_dir: Path = BLOG_DIR, drafts: bool = False) -> list[Post]:
    posts = []
    for path in sorted(blog_dir.glob("*.md")):
        if not POST_NAME.match(path.name):
            continue
        post = parse_post(path.name, path.read_text(encoding="utf-8"))
        if post.draft and not drafts:
            continue
        posts.append(post)
    return sorted(posts, key=lambda p: (p.day, p.slug), reverse=True)


def render_markdown(body: str) -> str:
    import markdown

    return markdown.markdown(
        body,
        extensions=["extra", "sane_lists", "codehilite", "toc"],
        extension_configs={
            "codehilite": {"guess_lang": False, "css_class": "code"},
            "toc": {"permalink": False},
        },
        output_format="html5",
    )


def code_css() -> str:
    from pygments.formatters import HtmlFormatter

    light = HtmlFormatter(style="friendly").get_style_defs(".code")
    dark = HtmlFormatter(style="monokai").get_style_defs(".code")
    # Backgrounds come from style.css so code blocks match the page in both schemes.
    drop_bg = lambda css: re.sub(r"background(-color)?:\s*#[0-9a-fA-F]+;?\s*", "", css)
    return f"{drop_bg(light)}\n@media (prefers-color-scheme: dark) {{\n{drop_bg(dark)}\n}}\n"


def long_date(day: date) -> str:
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def page(title: str, root: str, content: str, description: str = "") -> str:
    full_title = SITE_TITLE if title == SITE_TITLE else f"{title} · {SITE_TITLE}"
    desc = html.escape(description or SITE_TAGLINE, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{root}assets/style.css">
<link rel="stylesheet" href="{root}assets/code.css">
<link rel="alternate" type="application/atom+xml" title="{SITE_TITLE}" href="{root}feed.xml">
</head>
<body>
<header class="site">
  <a class="wordmark" href="{root}">{SITE_TITLE}</a>
  <nav><a href="{root}feed.xml">Feed</a> <a href="{REPO_URL}">Source</a></nav>
</header>
<main>
{content}
</main>
<footer class="site">
  <p>{html.escape(SITE_TAGLINE)}</p>
  <p>No trackers, no scripts. Built from Markdown in <a href="{REPO_URL}/tree/main/blog">the repository</a>.</p>
</footer>
</body>
</html>
"""


def byline(post: Post) -> str:
    parts = [f'<time datetime="{post.day.isoformat()}">{long_date(post.day)}</time>']
    if post.author:
        parts.append(f'<span class="author">{html.escape(post.author)}</span>')
    return '<p class="byline">' + " · ".join(parts) + "</p>"


def render_index(posts: list[Post]) -> str:
    items = []
    for post in posts:
        items.append(
            f"""<article class="entry">
  <h2><a href="{post.path}">{html.escape(post.title)}</a></h2>
  {byline(post)}
  <p>{html.escape(post.summary)}</p>
</article>"""
        )
    intro = f'<p class="tagline">{html.escape(SITE_TAGLINE)}</p>'
    return page(SITE_TITLE, "", intro + "\n" + "\n".join(items))


def render_post(post: Post) -> str:
    extras = "".join(
        f"<div><dt>{html.escape(key.title())}</dt><dd>{html.escape(plain_text(value).strip('[]'))}</dd></div>"
        for key, value in post.meta.items()
        if key not in HIDDEN_KEYS and value
    )
    details = f'<dl class="meta">{extras}</dl>' if extras else ""
    source = f"{REPO_URL}/blob/main/blog/{post.source_name}"
    content = f"""<article class="post">
<h1>{html.escape(post.title)}</h1>
{byline(post)}
{details}
{render_markdown(post.body)}
<p class="source"><a href="{source}">View or correct this post on GitHub</a></p>
</article>"""
    return page(post.title, "../../", content, post.summary)


def render_feed(posts: list[Post]) -> str:
    updated = posts[0].day.isoformat() if posts else date.today().isoformat()
    entries = []
    for post in posts[:20]:
        url = f"{SITE_URL}/{post.path}"
        author = f"<author><name>{html.escape(post.author)}</name></author>" if post.author else ""
        entries.append(
            f"""  <entry>
    <title>{html.escape(post.title)}</title>
    <link href="{url}"/>
    <id>{url}</id>
    <updated>{post.day.isoformat()}T12:00:00Z</updated>
    {author}
    <summary>{html.escape(post.summary)}</summary>
  </entry>"""
        )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{SITE_TITLE}</title>
  <subtitle>{html.escape(SITE_TAGLINE)}</subtitle>
  <link href="{SITE_URL}/"/>
  <link rel="self" href="{SITE_URL}/feed.xml"/>
  <id>{SITE_URL}/</id>
  <updated>{updated}T12:00:00Z</updated>
{chr(10).join(entries)}
</feed>
"""


def build(out: Path, blog_dir: Path = BLOG_DIR, drafts: bool = False) -> list[Post]:
    posts = load_posts(blog_dir, drafts=drafts)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    shutil.copy(BLOG_DIR / "assets" / "style.css", out / "assets" / "style.css")
    (out / "assets" / "code.css").write_text(code_css(), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / "index.html").write_text(render_index(posts), encoding="utf-8")
    (out / "feed.xml").write_text(render_feed(posts), encoding="utf-8")
    for post in posts:
        target = out / post.path
        target.mkdir(parents=True)
        (target / "index.html").write_text(render_post(post), encoding="utf-8")
    return posts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="_site", type=Path)
    parser.add_argument("--drafts", action="store_true", help="include posts marked **Status:** draft")
    args = parser.parse_args()
    posts = build(args.out, drafts=args.drafts)
    print(f"Built {len(posts)} posts into {args.out}/")


if __name__ == "__main__":
    main()
