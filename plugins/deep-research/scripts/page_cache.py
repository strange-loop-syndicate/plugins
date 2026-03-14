#!/usr/bin/env python3
"""Page cache — fetch web pages and save as markdown.

Stdlib only. No external packages.
Uses urllib for HTTP fetching with Jina Reader API as fallback.
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Allow importing from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAX_CONTENT_SIZE = 50 * 1024  # 50KB
USER_AGENT = "Mozilla/5.0 (compatible; ResearchBot/1.0)"
TIMEOUT = 30


class _HTMLToText(HTMLParser):
    """Minimal HTML to plain text converter."""

    _skip_tags = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._skip_tags:
            self._skip_depth += 1
        elif tag.lower() in ("br", "hr"):
            self._text.append("\n")
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self._text.append("\n\n")

    def handle_endtag(self, tag):
        if tag.lower() in self._skip_tags:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._text.append(data)

    def get_text(self) -> str:
        text = "".join(self._text)
        # Collapse whitespace within lines, preserve paragraph breaks
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html)
    return parser.get_text()


def _fetch_direct(url: str) -> str:
    """Fetch URL directly with urllib, parse HTML to text."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as resp:
        content_type = resp.headers.get("Content-Type", "")
        raw = resp.read(MAX_CONTENT_SIZE + 1024)  # Read slightly more to detect truncation
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        text = raw.decode(charset, errors="replace")

        if "html" in content_type.lower():
            text = _html_to_text(text)

        return text


def _fetch_jina(url: str) -> str:
    """Fetch URL via Jina Reader API (returns markdown)."""
    jina_url = f"https://r.jina.ai/{url}"
    req = Request(jina_url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read(MAX_CONTENT_SIZE + 1024)
        return raw.decode("utf-8", errors="replace")


def _truncate(text: str, max_bytes: int = MAX_CONTENT_SIZE) -> str:
    """Truncate text to max_bytes with notice."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + "\n\n[content truncated at 50KB]"


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.rename(tmp_path, path)


def cmd_fetch(args):
    """Fetch URL content and save as markdown."""
    edir = os.path.join(args.folder, "evidence")
    pages_dir = os.path.join(edir, "pages")
    sources_path = os.path.join(edir, "sources.json")

    os.makedirs(pages_dir, exist_ok=True)

    page_file = os.path.join(pages_dir, f"{args.source_id}.md")
    rel_page_file = f"pages/{args.source_id}.md"

    content = None
    error = None

    # Try direct fetch first
    try:
        content = _fetch_direct(args.url)
    except (URLError, HTTPError, OSError, ValueError) as e:
        # Fallback to Jina Reader
        try:
            content = _fetch_jina(args.url)
        except (URLError, HTTPError, OSError, ValueError) as e2:
            error = f"Direct: {e}; Jina: {e2}"

    # Update sources.json
    if os.path.exists(sources_path):
        sources = _read_json(sources_path)
    else:
        sources = {}

    if content:
        content = _truncate(content)
        with open(page_file, "w", encoding="utf-8") as f:
            f.write(content)

        if args.source_id in sources:
            sources[args.source_id]["page_cached"] = True
            sources[args.source_id]["page_file"] = rel_page_file
            _write_json(sources_path, sources)

        print(json.dumps({"status": "ok", "source_id": args.source_id, "page_file": rel_page_file, "size": len(content)}))
    else:
        if args.source_id in sources:
            sources[args.source_id]["page_cached"] = False
            _write_json(sources_path, sources)

        print(json.dumps({"status": "error", "source_id": args.source_id, "error": error}), file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Page cache — fetch and store web pages")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("fetch")
    p.add_argument("folder")
    p.add_argument("--url", required=True)
    p.add_argument("--source-id", required=True)
    p.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
