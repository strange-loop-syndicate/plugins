"""Source module contract for lead-ops.

A source module discovers candidate leads from one upstream system. Every
module MUST expose a single top-level callable named `discover` with this
signature:

    def discover(scope: dict, params: dict) -> list[dict]: ...

Inputs:
    scope   shared project scope from lead-ops.config.yaml under the top-level
            `scope:` block (geography, time_range, success_criteria, etc.).
            Source modules SHOULD respect scope but MAY ignore fields they
            cannot apply.
    params  the per-source `params` block from the config under
            `sources[*].params`. The shape is source-specific (seeds, queries,
            URL patterns, API parameters).

Returns:
    list of candidate dicts. Each candidate dict MUST have:
        title         human-readable summary of the candidate item
        url           canonical URL of the item (will be fetched downstream)
        source_id     identifier unique within this source module (e.g. PMID,
                      NCT id, URL hash)
        source_type   short string matching the source module id (e.g.
                      "pubmed", "web_search", "web_scrape", "clinicaltrials_gov")
        raw_metadata  free-form dict of upstream metadata the extractor may
                      use (authors, dates, journal, study type, etc.)

Conventions:
    - NO content fetch here. Discovery returns lightweight candidates only;
      the extractor agent fetches and persists full content.
    - Use `requests` + stdlib + the plugin's `scripts/` modules. Avoid
      WebFetch / WebSearch tool calls — those are agent-side, not script-side.
    - Honor rate limits via shared file-locks (see scripts/ncbi_fetch.py).
    - Deduplicate within your output if cheap; the build skill dedups globally.
    - Raise on configuration errors (missing required params); return [] on
      empty upstream results.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def discover(scope: dict[str, Any], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list of candidate dicts. See module docstring for contract."""
    raise NotImplementedError("custom source modules must implement discover(scope, params)")


def _main() -> int:
    """CLI entry: `python -m <module> --scope <json> --params <json>` prints JSON to stdout."""
    parser = argparse.ArgumentParser(description="Run discover() and print candidates as JSON.")
    parser.add_argument("--scope", default="{}", help="JSON-encoded scope dict")
    parser.add_argument("--params", required=True, help="JSON-encoded params dict")
    args = parser.parse_args()
    candidates = discover(json.loads(args.scope), json.loads(args.params))
    json.dump(candidates, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
