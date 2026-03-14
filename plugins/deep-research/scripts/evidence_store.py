#!/usr/bin/env python3
"""Evidence store management — CLI for JSON evidence files.

Stdlib only. No external packages.
Each command reads/writes only the file it needs.
Atomic writes via tmp file + os.rename.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Allow importing dedup from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedup import normalize_url, url_hash


def _evidence_dir(folder: str) -> str:
    return os.path.join(folder, "evidence")


def _read_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data) -> None:
    """Atomic write: write to .tmp then rename."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.rename(tmp_path, path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Commands ---


def cmd_init(args):
    """Create evidence/ subdirectory with empty JSON files."""
    edir = _evidence_dir(args.folder)
    os.makedirs(edir, exist_ok=True)
    os.makedirs(os.path.join(edir, "pages"), exist_ok=True)

    files = {
        "sources.json": {},
        "claims.json": {},
        "hypotheses.json": {},
        "scope.json": {},
        "search_log.json": [],
    }
    for fname, default in files.items():
        path = os.path.join(edir, fname)
        if not os.path.exists(path):
            _write_json(path, default)

    print(json.dumps({"status": "ok", "evidence_dir": edir}))


def cmd_add_source(args):
    """Add a source to sources.json with dedup by URL hash."""
    path = os.path.join(_evidence_dir(args.folder), "sources.json")
    sources = _read_json(path)

    sid = "s_" + url_hash(args.url)

    if sid in sources:
        # Already exists — print id but don't duplicate
        print(sid)
        return

    source = {
        "url": args.url,
        "title": args.title,
        "snippet": args.snippet,
        "source_type": args.source_type or "unknown",
        "wave": args.wave if args.wave is not None else 1,
        "search_query": args.search_query or "",
        "publication_date": args.publication_date or "",
        "authors": json.loads(args.authors) if args.authors else [],
        "retrieved_at": _now_iso(),
        "page_cached": False,
        "page_file": None,
        "rating": None,
    }

    sources[sid] = source
    _write_json(path, sources)
    print(sid)


def cmd_update_rating(args):
    """Update source rating."""
    path = os.path.join(_evidence_dir(args.folder), "sources.json")
    sources = _read_json(path)

    if args.source_id not in sources:
        print(json.dumps({"error": f"Source {args.source_id} not found"}), file=sys.stderr)
        sys.exit(1)

    bias_flags = json.loads(args.bias_flags) if args.bias_flags else []

    sources[args.source_id]["rating"] = {
        "reliability": args.reliability,
        "credibility": args.credibility,
        "bias_flags": bias_flags,
        "rationale": args.rationale or "",
        "rated_by": "source-evaluator agent",
    }

    _write_json(path, sources)
    print(json.dumps({"status": "ok", "source_id": args.source_id}))


def cmd_add_claim(args):
    """Add a claim to claims.json."""
    path = os.path.join(_evidence_dir(args.folder), "claims.json")
    claims = _read_json(path)

    # Sequential ID
    if claims:
        max_num = max(int(k.split("_")[1]) for k in claims)
        next_num = max_num + 1
    else:
        next_num = 1

    cid = f"c_{next_num:04d}"

    source_ids = json.loads(args.source_ids) if args.source_ids else []

    claim = {
        "text": args.text,
        "category": args.category or "general",
        "supporting_source_ids": source_ids,
        "contradicting_source_ids": [],
        "confidence": args.confidence or "medium",
        "verification_status": "unverified",
    }

    claims[cid] = claim
    _write_json(path, claims)
    print(cid)


def cmd_add_hypothesis(args):
    """Add a hypothesis to hypotheses.json."""
    path = os.path.join(_evidence_dir(args.folder), "hypotheses.json")
    hypotheses = _read_json(path)

    if hypotheses:
        max_num = max(int(k.split("_")[1]) for k in hypotheses)
        next_num = max_num + 1
    else:
        next_num = 1

    hid = f"h_{next_num:03d}"

    hypothesis = {
        "text": args.text,
        "status": "active",
        "evidence_assessments": {},
        "assumptions": [],
    }

    hypotheses[hid] = hypothesis
    _write_json(path, hypotheses)
    print(hid)


def cmd_update_assessment(args):
    """Update ACH assessment for a hypothesis-claim pair."""
    path = os.path.join(_evidence_dir(args.folder), "hypotheses.json")
    hypotheses = _read_json(path)

    if args.hypothesis_id not in hypotheses:
        print(json.dumps({"error": f"Hypothesis {args.hypothesis_id} not found"}), file=sys.stderr)
        sys.exit(1)

    valid = {"consistent", "inconsistent", "neutral"}
    if args.assessment not in valid:
        print(json.dumps({"error": f"Assessment must be one of {valid}"}), file=sys.stderr)
        sys.exit(1)

    hypotheses[args.hypothesis_id]["evidence_assessments"][args.claim_id] = args.assessment
    _write_json(path, hypotheses)
    print(json.dumps({"status": "ok", "hypothesis_id": args.hypothesis_id, "claim_id": args.claim_id}))


def cmd_log_search(args):
    """Append a search entry to search_log.json."""
    path = os.path.join(_evidence_dir(args.folder), "search_log.json")
    log = _read_json(path)

    entry = {
        "query": args.query,
        "results_count": args.results_count,
        "wave": args.wave,
        "timestamp": _now_iso(),
    }

    log.append(entry)
    _write_json(path, log)
    print(json.dumps({"status": "ok", "entries": len(log)}))


def cmd_get_unrated(args):
    """Print JSON of sources without ratings."""
    path = os.path.join(_evidence_dir(args.folder), "sources.json")
    sources = _read_json(path)

    unrated = {sid: s for sid, s in sources.items() if s.get("rating") is None}
    print(json.dumps(unrated, indent=2, ensure_ascii=False))


def cmd_get_by_rating(args):
    """Print JSON of sources rated at or above min_reliability."""
    path = os.path.join(_evidence_dir(args.folder), "sources.json")
    sources = _read_json(path)

    rating_order = ["A", "B", "C", "D", "E", "F"]
    min_r = args.min_reliability.upper()
    if min_r not in rating_order:
        print(json.dumps({"error": f"Invalid reliability: {min_r}"}), file=sys.stderr)
        sys.exit(1)

    max_idx = rating_order.index(min_r)
    acceptable = set(rating_order[: max_idx + 1])

    filtered = {
        sid: s
        for sid, s in sources.items()
        if s.get("rating") and s["rating"].get("reliability", "F").upper() in acceptable
    }
    print(json.dumps(filtered, indent=2, ensure_ascii=False))


def cmd_get_uncorroborated(args):
    """Print JSON of claims with fewer than N supporting sources."""
    path = os.path.join(_evidence_dir(args.folder), "claims.json")
    claims = _read_json(path)

    min_sources = args.min_sources

    uncorroborated = {
        cid: c
        for cid, c in claims.items()
        if len(c.get("supporting_source_ids", [])) < min_sources
    }
    print(json.dumps(uncorroborated, indent=2, ensure_ascii=False))


def cmd_stats(args):
    """Print aggregate statistics."""
    edir = _evidence_dir(args.folder)

    sources = _read_json(os.path.join(edir, "sources.json"))
    claims = _read_json(os.path.join(edir, "claims.json"))
    hypotheses = _read_json(os.path.join(edir, "hypotheses.json"))
    search_log = _read_json(os.path.join(edir, "search_log.json"))

    rated = [s for s in sources.values() if s.get("rating")]
    cached = [s for s in sources.values() if s.get("page_cached")]

    # Rating distribution
    rating_dist = {}
    for s in rated:
        r = s["rating"].get("reliability", "?")
        rating_dist[r] = rating_dist.get(r, 0) + 1

    # Claims by confidence
    confidence_dist = {}
    for c in claims.values():
        conf = c.get("confidence", "unknown")
        confidence_dist[conf] = confidence_dist.get(conf, 0) + 1

    # Uncorroborated (< 3 sources)
    uncorroborated = sum(
        1 for c in claims.values() if len(c.get("supporting_source_ids", [])) < 3
    )

    stats = {
        "sources_total": len(sources),
        "sources_rated": len(rated),
        "sources_unrated": len(sources) - len(rated),
        "sources_cached": len(cached),
        "rating_distribution": rating_dist,
        "claims_total": len(claims),
        "claims_by_confidence": confidence_dist,
        "claims_uncorroborated": uncorroborated,
        "hypotheses_total": len(hypotheses),
        "searches_total": len(search_log),
    }

    print(json.dumps(stats, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Evidence store management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p = subparsers.add_parser("init")
    p.add_argument("folder")
    p.set_defaults(func=cmd_init)

    # add-source
    p = subparsers.add_parser("add-source")
    p.add_argument("folder")
    p.add_argument("--url", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--snippet", required=True)
    p.add_argument("--source-type")
    p.add_argument("--wave", type=int)
    p.add_argument("--search-query")
    p.add_argument("--publication-date")
    p.add_argument("--authors", help="JSON array string")
    p.set_defaults(func=cmd_add_source)

    # update-rating
    p = subparsers.add_parser("update-rating")
    p.add_argument("folder")
    p.add_argument("--source-id", required=True)
    p.add_argument("--reliability", required=True)
    p.add_argument("--credibility", required=True, type=int)
    p.add_argument("--bias-flags", help="JSON array string")
    p.add_argument("--rationale")
    p.set_defaults(func=cmd_update_rating)

    # add-claim
    p = subparsers.add_parser("add-claim")
    p.add_argument("folder")
    p.add_argument("--text", required=True)
    p.add_argument("--source-ids", required=True, help="JSON array string")
    p.add_argument("--category")
    p.add_argument("--confidence")
    p.set_defaults(func=cmd_add_claim)

    # add-hypothesis
    p = subparsers.add_parser("add-hypothesis")
    p.add_argument("folder")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_add_hypothesis)

    # update-assessment
    p = subparsers.add_parser("update-assessment")
    p.add_argument("folder")
    p.add_argument("--hypothesis-id", required=True)
    p.add_argument("--claim-id", required=True)
    p.add_argument("--assessment", required=True)
    p.set_defaults(func=cmd_update_assessment)

    # log-search
    p = subparsers.add_parser("log-search")
    p.add_argument("folder")
    p.add_argument("--query", required=True)
    p.add_argument("--results-count", required=True, type=int)
    p.add_argument("--wave", required=True, type=int)
    p.set_defaults(func=cmd_log_search)

    # get-unrated
    p = subparsers.add_parser("get-unrated")
    p.add_argument("folder")
    p.set_defaults(func=cmd_get_unrated)

    # get-by-rating
    p = subparsers.add_parser("get-by-rating")
    p.add_argument("folder")
    p.add_argument("--min-reliability", required=True)
    p.set_defaults(func=cmd_get_by_rating)

    # get-uncorroborated
    p = subparsers.add_parser("get-uncorroborated")
    p.add_argument("folder")
    p.add_argument("--min-sources", type=int, default=3)
    p.set_defaults(func=cmd_get_uncorroborated)

    # stats
    p = subparsers.add_parser("stats")
    p.add_argument("folder")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
