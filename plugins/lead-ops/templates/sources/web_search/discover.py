"""Web search source: run a list of queries and return candidate result URLs.

Two engines are supported and selected via `params.engine`:

    brave     Brave Search API. Requires BRAVE_SEARCH_API_KEY env var.
              Quota- and quality-controlled; preferred when available.
    duckduckgo  DuckDuckGo HTML endpoint (no key). Free but rate-limited;
                avoid for large batches. The plugin's audit phase should
                verify URLs before treating them as evidence.

Params shape:
    engine               "brave" | "duckduckgo" (default "duckduckgo").
    queries              list[str], one search query per element.
    max_results_per_query int, default 10.
    request_delay_s      float, between-query sleep (default 1.5).
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.parse
from typing import Any

import requests

BRAVE_API = "https://api.search.brave.com/res/v1/web/search"
DDG_HTML = "https://html.duckduckgo.com/html/"
USER_AGENT = "lead-ops/0.1 (+https://github.com/strange-loop-syndicate/lead-ops)"
DEFAULT_TIMEOUT = 30

_DDG_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _brave(query: str, n: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("engine=brave requires BRAVE_SEARCH_API_KEY env var")
    resp = requests.get(
        BRAVE_API,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": USER_AGENT,
        },
        params={"q": query, "count": n},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    results: list[dict[str, Any]] = []
    for item in (payload.get("web") or {}).get("results", []) or []:
        url = item.get("url")
        if not url:
            continue
        results.append(
            {
                "title": item.get("title") or url,
                "url": url,
                "source_id": _stable_id(url),
                "source_type": "web_search",
                "raw_metadata": {
                    "engine": "brave",
                    "query": query,
                    "snippet": item.get("description") or "",
                    "age": item.get("age") or "",
                },
            }
        )
    return results


def _duckduckgo(query: str, n: int) -> list[dict[str, Any]]:
    resp = requests.post(
        DDG_HTML,
        data={"q": query},
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    results: list[dict[str, Any]] = []
    for match in _DDG_LINK_RE.finditer(resp.text):
        raw_url, html_title = match.groups()
        # DDG wraps target URLs in a redirect; unwrap `uddg=` if present.
        parsed = urllib.parse.urlparse(raw_url)
        qs = urllib.parse.parse_qs(parsed.query)
        url = qs.get("uddg", [raw_url])[0]
        title = _strip_html(html_title) or url
        results.append(
            {
                "title": title,
                "url": url,
                "source_id": _stable_id(url),
                "source_type": "web_search",
                "raw_metadata": {"engine": "duckduckgo", "query": query},
            }
        )
        if len(results) >= n:
            break
    return results


def discover(scope: dict[str, Any], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Run each configured query, return deduped candidates by URL."""
    engine = (params.get("engine") or "duckduckgo").lower()
    queries: list[str] = params.get("queries") or []
    n = int(params.get("max_results_per_query") or 10)
    delay = float(params.get("request_delay_s") or 1.5)
    if not queries:
        return []

    seen: dict[str, dict[str, Any]] = {}
    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(delay)
        batch = _brave(query, n) if engine == "brave" else _duckduckgo(query, n)
        for cand in batch:
            seen.setdefault(cand["url"], cand)

    return list(seen.values())


def _main() -> int:
    """CLI entry: `python -m <module> --scope <json> --params <json>` prints JSON to stdout."""
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="Run web_search discover() and print candidates as JSON.")
    parser.add_argument("--scope", default="{}", help="JSON-encoded scope dict")
    parser.add_argument("--params", required=True, help="JSON-encoded params dict")
    args = parser.parse_args()
    candidates = discover(json.loads(args.scope), json.loads(args.params))
    json.dump(candidates, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
