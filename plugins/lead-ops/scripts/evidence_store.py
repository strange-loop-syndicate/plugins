"""Persist, retrieve, and verify raw evidence content for lead-ops pipelines.

Files land under `./pipeline/evidence_store/<type>/<id>.<ext>` (relative to the
current working directory, which is the user project root). Re-fetching a URL
and comparing SHA-256 against the stored copy lets the auditor catch silent
upstream changes or stale captures.

CLI usage:
    python -m evidence_store store --type pubmed --id 29714573 --ext xml --url <url>
    python -m evidence_store retrieve --type pubmed --id 29714573
    python -m evidence_store verify --url <url> --type pubmed --id 29714573
    python -m evidence_store verify --leads ./leads.json
    python -m evidence_store stats

Library API:
    store(url, content, type, id, ext) -> Path
    retrieve(type, id, ext=None) -> bytes | None
    verify(url, type=None, id=None, ext=None) -> dict
    stats(root=None) -> dict[str, int]

Exit codes:
    0   success
    1   item missing or hash mismatch (verify failures)
    2   invalid arguments
    3   network or filesystem error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

import requests

DEFAULT_ROOT = Path("./pipeline/evidence_store")
DEFAULT_TIMEOUT = 30


def _root(override: Path | None = None) -> Path:
    return Path(override) if override else DEFAULT_ROOT


def _path_for(type_: str, id_: str, ext: str, root: Path | None = None) -> Path:
    if not type_ or not id_:
        raise ValueError("type and id are required")
    safe_id = id_.replace("/", "_").replace("\\", "_")
    return _root(root) / type_ / f"{safe_id}.{ext.lstrip('.')}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store(
    url: str,
    content: bytes | str,
    type_: str,
    id_: str,
    ext: str = "html",
    root: Path | None = None,
) -> Path:
    """Write `content` to the evidence store. Returns the absolute path written."""
    if isinstance(content, str):
        payload = content.encode("utf-8")
    else:
        payload = content
    path = _path_for(type_, id_, ext, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)

    sidecar = path.with_suffix(path.suffix + ".meta.json")
    sidecar.write_text(
        json.dumps(
            {"url": url, "sha256": _sha256(payload), "bytes": len(payload)},
            indent=2,
        ),
        encoding="utf-8",
    )
    return path.resolve()


def retrieve(
    type_: str,
    id_: str,
    ext: str | None = None,
    root: Path | None = None,
) -> bytes | None:
    """Read stored bytes. If `ext` is None, find any file matching id within type."""
    if ext is not None:
        path = _path_for(type_, id_, ext, root)
        if path.exists():
            return path.read_bytes()
        return None
    base = _root(root) / type_
    if not base.exists():
        return None
    for child in base.iterdir():
        if child.is_file() and not child.name.endswith(".meta.json") and child.stem == id_:
            return child.read_bytes()
    return None


def _read_meta(type_: str, id_: str, root: Path | None = None) -> dict | None:
    base = _root(root) / type_
    if not base.exists():
        return None
    for child in base.iterdir():
        if child.name.endswith(".meta.json") and child.name.startswith(f"{id_}."):
            try:
                return json.loads(child.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
    return None


def verify(
    url: str,
    type_: str | None = None,
    id_: str | None = None,
    ext: str | None = None,
    root: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Fetch `url`, compare SHA-256 against the stored copy.

    Returns a dict with keys: ok, status, reason, stored_sha, fetched_sha.
    `ok` is True only when stored bytes exist AND fetched hash matches.
    """
    if type_ is None or id_ is None:
        return {
            "ok": False,
            "status": "invalid_args",
            "reason": "type and id required",
            "stored_sha": None,
            "fetched_sha": None,
        }

    stored = retrieve(type_, id_, ext, root)
    if stored is None:
        return {
            "ok": False,
            "status": "missing",
            "reason": "no stored content",
            "stored_sha": None,
            "fetched_sha": None,
        }
    stored_sha = _sha256(stored)

    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": "fetch_error",
            "reason": str(exc),
            "stored_sha": stored_sha,
            "fetched_sha": None,
        }

    if resp.status_code >= 400:
        return {
            "ok": False,
            "status": f"http_{resp.status_code}",
            "reason": f"upstream returned {resp.status_code}",
            "stored_sha": stored_sha,
            "fetched_sha": None,
        }

    fetched_sha = _sha256(resp.content)
    return {
        "ok": stored_sha == fetched_sha,
        "status": "match" if stored_sha == fetched_sha else "drift",
        "reason": None if stored_sha == fetched_sha else "hash mismatch",
        "stored_sha": stored_sha,
        "fetched_sha": fetched_sha,
    }


def stats(root: Path | None = None) -> dict[str, int]:
    """Return per-type file counts in the evidence store."""
    base = _root(root)
    out: dict[str, int] = {}
    if not base.exists():
        return out
    for type_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        count = sum(
            1
            for child in type_dir.iterdir()
            if child.is_file() and not child.name.endswith(".meta.json")
        )
        out[type_dir.name] = count
    return out


def _bulk_verify_leads(
    leads_path: Path,
    root: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Walk `leads.json`, check each evidence entry that has a stored copy."""
    leads = json.loads(leads_path.read_text(encoding="utf-8"))
    results = {"checked": 0, "ok": 0, "missing": 0, "drift": 0, "errors": 0, "items": []}
    for lead in leads:
        for ev in lead.get("evidence", []) or []:
            url = ev.get("url")
            type_ = ev.get("type") or ev.get("source_type")
            id_ = ev.get("pmid") or ev.get("id") or ev.get("source_id")
            if not (url and type_ and id_):
                continue
            results["checked"] += 1
            outcome = verify(url, type_, str(id_), root=root, timeout=timeout)
            if outcome["ok"]:
                results["ok"] += 1
            elif outcome["status"] == "missing":
                results["missing"] += 1
            elif outcome["status"] == "drift":
                results["drift"] += 1
            else:
                results["errors"] += 1
            results["items"].append(
                {
                    "lead": lead.get("name"),
                    "url": url,
                    "type": type_,
                    "id": id_,
                    **outcome,
                }
            )
    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidence_store",
        description="Persist, retrieve, and verify raw evidence content.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    s_store = sub.add_parser("store", help="Write content into the store.")
    s_store.add_argument("--type", dest="type_", required=True)
    s_store.add_argument("--id", dest="id_", required=True)
    s_store.add_argument("--ext", default="html")
    s_store.add_argument("--url", required=True)
    s_store.add_argument(
        "--content-file",
        help="Path to file containing the body. If absent, reads stdin.",
    )
    s_store.add_argument("--root", default=None)

    s_get = sub.add_parser("retrieve", help="Print stored bytes to stdout.")
    s_get.add_argument("--type", dest="type_", required=True)
    s_get.add_argument("--id", dest="id_", required=True)
    s_get.add_argument("--ext", default=None)
    s_get.add_argument("--root", default=None)

    s_ver = sub.add_parser("verify", help="Fetch URL and compare hashes.")
    s_ver.add_argument("--url", default=None)
    s_ver.add_argument("--type", dest="type_", default=None)
    s_ver.add_argument("--id", dest="id_", default=None)
    s_ver.add_argument("--ext", default=None)
    s_ver.add_argument("--leads", help="Bulk-check evidence entries in this leads.json.")
    s_ver.add_argument("--root", default=None)
    s_ver.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)

    s_stats = sub.add_parser("stats", help="Show per-type counts.")
    s_stats.add_argument("--root", default=None)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.root) if getattr(args, "root", None) else None

    if args.cmd == "store":
        if args.content_file:
            content = Path(args.content_file).read_bytes()
        else:
            content = sys.stdin.buffer.read()
        path = store(args.url, content, args.type_, args.id_, args.ext, root)
        print(str(path))
        return 0

    if args.cmd == "retrieve":
        data = retrieve(args.type_, args.id_, args.ext, root)
        if data is None:
            print(f"not found: {args.type_}/{args.id_}", file=sys.stderr)
            return 1
        sys.stdout.buffer.write(data)
        return 0

    if args.cmd == "verify":
        if args.leads:
            results = _bulk_verify_leads(Path(args.leads), root, args.timeout)
            summary = {k: v for k, v in results.items() if k != "items"}
            print(json.dumps(summary, indent=2))
            non_ok = results["missing"] + results["drift"] + results["errors"]
            return 0 if non_ok == 0 else 1
        if not (args.url and args.type_ and args.id_):
            print("verify requires --url --type --id (or --leads)", file=sys.stderr)
            return 2
        outcome = verify(args.url, args.type_, args.id_, args.ext, root, args.timeout)
        print(json.dumps(outcome, indent=2))
        return 0 if outcome["ok"] else 1

    if args.cmd == "stats":
        counts = stats(root)
        total = sum(counts.values())
        print(json.dumps({"total": total, "by_type": counts}, indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
