"""PubMed source module: discover similar articles via NCBI E-utilities.

For each seed PMID, calls elink (pubmed_pubmed) to retrieve related articles,
then esummary in batches to fetch title + authors + year + journal. Optional
title-keyword filter and year-range filter narrow the result set.

Params shape (see config_snippet.yaml for full example):
    seeds                 list[str] of PMIDs OR a single str path to a file
                          with one PMID per line.
    title_filter_keywords list[str], OR-matched case-insensitively against
                          article titles. Empty list = keep all.
    date_min              int year, inclusive lower bound on publication year.
    date_max              int year, inclusive upper bound.
    batch_size            int, esummary batch size (default 200).

This module loads scripts/ncbi_fetch.py from ${CLAUDE_PLUGIN_ROOT}/scripts.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any


def _load_ncbi_fetch():
    """Import scripts/ncbi_fetch.py from ${CLAUDE_PLUGIN_ROOT}/scripts."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        scripts_dir = Path(plugin_root) / "scripts"
    else:
        # Fallback for testing: assume templates/sources/pubmed/discover.py
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    target = scripts_dir / "ncbi_fetch.py"
    if not target.exists():
        raise RuntimeError(f"ncbi_fetch.py not found at {target}")
    spec = importlib.util.spec_from_file_location("ncbi_fetch", target)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ncbi_fetch"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _read_seeds(seeds: Any) -> list[str]:
    if isinstance(seeds, list):
        return [str(s).strip() for s in seeds if str(s).strip()]
    if isinstance(seeds, str):
        path = Path(seeds).expanduser()
        if path.exists():
            return [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        return [seeds.strip()]
    raise ValueError(f"seeds must be list[str] or str path, got {type(seeds).__name__}")


def _year_of(summary: dict) -> int | None:
    pubdate = summary.get("pubdate") or ""
    match = re.search(r"\b(19|20)\d{2}\b", str(pubdate))
    return int(match.group(0)) if match else None


def _title_matches(title: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    t = (title or "").lower()
    return any(k.lower() in t for k in keywords)


def discover(scope: dict[str, Any], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Return PubMed-similar-article candidates seeded from `params.seeds`."""
    seeds = _read_seeds(params.get("seeds") or [])
    if not seeds:
        return []
    title_kw = params.get("title_filter_keywords") or []
    date_min = params.get("date_min")
    date_max = params.get("date_max")
    batch_size = int(params.get("batch_size") or 200)

    ncbi = _load_ncbi_fetch()

    seed_to_related: dict[str, set[str]] = {}
    all_related: set[str] = set()
    for pmid in seeds:
        rels: set[str] = set()
        for rel in ncbi.elink_similar(pmid):
            if rel not in seeds:
                rels.add(rel)
        seed_to_related[pmid] = rels
        all_related.update(rels)

    pmids = sorted(all_related)
    candidates: list[dict[str, Any]] = []

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        summaries = ncbi.esummary(batch)
        for pmid, summary in summaries.items():
            title = summary.get("title") or ""
            if not _title_matches(title, title_kw):
                continue
            year = _year_of(summary)
            if date_min and year and year < int(date_min):
                continue
            if date_max and year and year > int(date_max):
                continue
            candidates.append(
                {
                    "title": title,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "source_id": pmid,
                    "source_type": "pubmed",
                    "raw_metadata": {
                        "pmid": pmid,
                        "authors": summary.get("authors") or [],
                        "journal": summary.get("source") or summary.get("fulljournalname") or "",
                        "year": year,
                        "doi": summary.get("doi") or "",
                        "seed_pmids": [s for s, rels in seed_to_related.items() if pmid in rels],
                    },
                }
            )

    return candidates


def _main() -> int:
    """CLI entry: `python -m <module> --scope <json> --params <json>` prints JSON to stdout."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Run pubmed discover() and print candidates as JSON.")
    parser.add_argument("--scope", default="{}", help="JSON-encoded scope dict")
    parser.add_argument("--params", required=True, help="JSON-encoded params dict")
    args = parser.parse_args()
    candidates = discover(json.loads(args.scope), json.loads(args.params))
    json.dump(candidates, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
