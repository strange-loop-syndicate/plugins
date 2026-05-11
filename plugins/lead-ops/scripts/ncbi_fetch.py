"""File-locked rate-limited NCBI E-utilities wrapper.

Wraps elink (similar articles), esummary, and efetch. A single shared lockfile
at /tmp/ncbi_rate.lock enforces a minimum interval between requests so multiple
parallel agents can hit the API without breaching the 3-req/sec public limit
(0.35s between calls). Raw XML is persisted to ./pipeline/evidence_store/pubmed/
so downstream agents can re-read content without re-fetching.

CLI usage:
    python -m ncbi_fetch elink-similar <pmid>
    python -m ncbi_fetch esummary <pmid> [<pmid> ...]
    python -m ncbi_fetch efetch <pmid>

Library API:
    elink_similar(pmid) -> list[str]    # related PMIDs
    esummary(pmids) -> dict[str, dict]  # PMID -> summary record
    efetch(pmid) -> str                 # raw XML, also persisted

Env vars (optional):
    NCBI_API_KEY        raises rate limit to 10 req/sec; if set, MIN_INTERVAL=0.11
    NCBI_EMAIL          included in requests per NCBI guidance

Exit codes:
    0   success
    1   invalid arguments
    2   network or API error
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import requests

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
LOCK_FILE = "/tmp/ncbi_rate.lock"
TS_FILE = "/tmp/ncbi_rate_ts"
STORE_DIR = Path("./pipeline/evidence_store/pubmed")
DEFAULT_TIMEOUT = 30


def _min_interval() -> float:
    return 0.11 if os.environ.get("NCBI_API_KEY") else 0.35


def _wait_for_slot() -> None:
    """Block until at least MIN_INTERVAL has elapsed since the last call."""
    Path(LOCK_FILE).touch(exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            last = 0.0
            if os.path.exists(TS_FILE):
                try:
                    last = float(Path(TS_FILE).read_text().strip() or "0")
                except ValueError:
                    last = 0.0
            now = time.time()
            wait = _min_interval() - (now - last)
            if wait > 0:
                time.sleep(wait)
            Path(TS_FILE).write_text(f"{time.time()}")
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _common_params() -> dict[str, str]:
    params: dict[str, str] = {"tool": "lead-ops", "retmode": "xml"}
    if email := os.environ.get("NCBI_EMAIL"):
        params["email"] = email
    if api_key := os.environ.get("NCBI_API_KEY"):
        params["api_key"] = api_key
    return params


def _get(url: str, params: dict, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    _wait_for_slot()
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp


def _store_xml(pmid: str, xml_text: str) -> Path:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    path = STORE_DIR / f"{pmid}.xml"
    path.write_text(xml_text, encoding="utf-8")
    return path


def elink_similar(pmid: str) -> list[str]:
    """Return PMIDs of articles similar to `pmid` (pubmed_pubmed_refs link)."""
    params = _common_params() | {
        "dbfrom": "pubmed",
        "db": "pubmed",
        "id": str(pmid),
        "linkname": "pubmed_pubmed",
        "cmd": "neighbor",
    }
    resp = _get(f"{EUTILS_BASE}/elink.fcgi", params)
    root = ET.fromstring(resp.text)
    pmids: list[str] = []
    for link in root.iter("Link"):
        node = link.find("Id")
        if node is not None and node.text and node.text != str(pmid):
            pmids.append(node.text)
    return pmids


def esummary(pmids: Iterable[str]) -> dict[str, dict]:
    """Return PMID -> minimal summary dict (title, source, pubdate, authors)."""
    pmids_list = [str(p) for p in pmids if p]
    if not pmids_list:
        return {}
    params = _common_params() | {
        "db": "pubmed",
        "id": ",".join(pmids_list),
    }
    resp = _get(f"{EUTILS_BASE}/esummary.fcgi", params)
    root = ET.fromstring(resp.text)
    out: dict[str, dict] = {}
    for doc in root.findall("DocSum"):
        id_node = doc.find("Id")
        if id_node is None or not id_node.text:
            continue
        pmid = id_node.text
        record: dict[str, object] = {"pmid": pmid}
        for item in doc.findall("Item"):
            name = item.attrib.get("Name", "")
            if name == "AuthorList":
                record["authors"] = [a.text for a in item.findall("Item") if a.text]
            elif name in {"Title", "Source", "PubDate", "FullJournalName", "DOI"}:
                record[name.lower()] = item.text or ""
        out[pmid] = record
    return out


def efetch(pmid: str) -> str:
    """Fetch full PubmedArticle XML for `pmid`. Persist to evidence store."""
    params = _common_params() | {
        "db": "pubmed",
        "id": str(pmid),
        "rettype": "xml",
    }
    resp = _get(f"{EUTILS_BASE}/efetch.fcgi", params)
    _store_xml(str(pmid), resp.text)
    return resp.text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ncbi_fetch",
        description="Rate-limited NCBI E-utilities wrapper.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_elink = sub.add_parser(
        "elink-similar", help="Print PMIDs related to <pmid> via pubmed_pubmed link."
    )
    p_elink.add_argument("pmid")

    p_sum = sub.add_parser("esummary", help="Print JSON summary records for PMIDs.")
    p_sum.add_argument("pmids", nargs="+")

    p_fetch = sub.add_parser("efetch", help="Fetch and store full XML for <pmid>.")
    p_fetch.add_argument("pmid")
    p_fetch.add_argument(
        "--print",
        action="store_true",
        help="Also print XML to stdout (default: store only and print path).",
    )

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.cmd == "elink-similar":
            pmids = elink_similar(args.pmid)
            print("\n".join(pmids))
            return 0
        if args.cmd == "esummary":
            print(json.dumps(esummary(args.pmids), indent=2))
            return 0
        if args.cmd == "efetch":
            xml_text = efetch(args.pmid)
            path = STORE_DIR / f"{args.pmid}.xml"
            if args.print:
                sys.stdout.write(xml_text)
            else:
                print(str(path.resolve()))
            return 0
    except requests.RequestException as exc:
        print(f"network error: {exc}", file=sys.stderr)
        return 2
    except ET.ParseError as exc:
        print(f"xml parse error: {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
