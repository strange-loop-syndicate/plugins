"""Web scrape source: fetch listing pages and extract links matching a pattern.

Designed for conference speaker pages, pharma program rosters, association
directories, and similar "list of people" pages. Each configured page is
fetched once; HTML hrefs are filtered by a regex `link_pattern`. CAPTCHA-
protected pages can be routed through r.jina.ai by enabling `use_jina`.

Params shape:
    pages         list of objects:
                    url           required, the listing page URL
                    link_pattern  required, regex matched against each href
                    base_url      optional, used to resolve relative hrefs
                                  (defaults to the page URL)
                    label         optional, free-form tag stored in raw_metadata
    use_jina      bool, when true prefixes every fetch with "https://r.jina.ai/"
                  to bypass CAPTCHA / JS-only pages. Defaults to false.
    timeout       int seconds (default 30).
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from typing import Any

import requests

USER_AGENT = "lead-ops/0.1 (+https://github.com/strange-loop-syndicate/lead-ops)"
JINA_PREFIX = "https://r.jina.ai/"
DEFAULT_TIMEOUT = 30

_HREF_RE = re.compile(
    r'<a[^>]+href="([^"#?]+)(?:[?#][^"]*)?"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def _fetch(url: str, use_jina: bool, timeout: int) -> str:
    target = f"{JINA_PREFIX}{url}" if use_jina else url
    resp = requests.get(
        target,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


def _scrape_page(
    page: dict[str, Any], use_jina: bool, timeout: int
) -> list[dict[str, Any]]:
    url = page.get("url")
    pattern = page.get("link_pattern")
    if not (url and pattern):
        raise ValueError("each page requires 'url' and 'link_pattern'")
    base = page.get("base_url") or url
    label = page.get("label") or ""
    regex = re.compile(pattern)

    html = _fetch(url, use_jina, timeout)
    seen: dict[str, dict[str, Any]] = {}
    for match in _HREF_RE.finditer(html):
        href, anchor_html = match.groups()
        absolute = urllib.parse.urljoin(base, href)
        if not regex.search(absolute):
            continue
        title = _strip_html(anchor_html) or absolute
        seen.setdefault(
            absolute,
            {
                "title": title,
                "url": absolute,
                "source_id": _stable_id(absolute),
                "source_type": "web_scrape",
                "raw_metadata": {
                    "source_page": url,
                    "label": label,
                    "anchor_text": title,
                },
            },
        )
    return list(seen.values())


def discover(scope: dict[str, Any], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Visit each `pages[i].url`, extract hrefs matching its `link_pattern`."""
    pages = params.get("pages") or []
    if not pages:
        return []
    use_jina = bool(params.get("use_jina"))
    timeout = int(params.get("timeout") or DEFAULT_TIMEOUT)

    out: dict[str, dict[str, Any]] = {}
    for page in pages:
        for cand in _scrape_page(page, use_jina, timeout):
            out.setdefault(cand["url"], cand)
    return list(out.values())


def _main() -> int:
    """CLI entry: `python -m <module> --scope <json> --params <json>` prints JSON to stdout."""
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="Run web_scrape discover() and print candidates as JSON.")
    parser.add_argument("--scope", default="{}", help="JSON-encoded scope dict")
    parser.add_argument("--params", required=True, help="JSON-encoded params dict")
    args = parser.parse_args()
    candidates = discover(json.loads(args.scope), json.loads(args.params))
    json.dump(candidates, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
