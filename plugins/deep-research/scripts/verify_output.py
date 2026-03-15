#!/usr/bin/env python3
"""Verify deep-research output folder against mode-specific quality thresholds.

Standalone stdlib-only script. Exit code 0 = all checks pass, 1 = one or more fail.

Usage:
    python3 verify_output.py <folder> --mode <quick|standard|deep|ultradeep> [--json]
"""

import argparse
import json
import os
import sys

THRESHOLDS = {
    "quick": {
        "sources_min": 100,
        "rated_pct": 90,
        "pages_cached_min": 10,
        "claims_min": 20,
        "hypotheses_min": 3,
        "report_words_min": 2000,
    },
    "standard": {
        "sources_min": 250,
        "rated_pct": 90,
        "pages_cached_min": 30,
        "claims_min": 40,
        "hypotheses_min": 3,
        "report_words_min": 4000,
    },
    "deep": {
        "sources_min": 400,
        "rated_pct": 90,
        "pages_cached_min": 50,
        "claims_min": 60,
        "hypotheses_min": 3,
        "report_words_min": 6000,
    },
    "ultradeep": {
        "sources_min": 500,
        "rated_pct": 95,
        "pages_cached_min": 80,
        "claims_min": 80,
        "hypotheses_min": 5,
        "report_words_min": 10000,
    },
}


def load_json(path):
    """Load a JSON file, return empty dict/list on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def count_words_in_md(folder):
    """Find the first research_report*.md in folder root and count words."""
    for name in os.listdir(folder):
        if name.startswith("research_report") and name.endswith(".md"):
            path = os.path.join(folder, name)
            with open(path) as f:
                return len(f.read().split()), name
    return 0, None


def check_non_empty_pages(pages_dir):
    """Count cached pages and how many are non-empty (>100 bytes)."""
    if not os.path.isdir(pages_dir):
        return 0, 0
    total = 0
    non_empty = 0
    for name in os.listdir(pages_dir):
        if name.endswith(".md"):
            total += 1
            path = os.path.join(pages_dir, name)
            if os.path.getsize(path) > 100:
                non_empty += 1
    return total, non_empty


def check_wave_reports(waves_dir):
    """Count wave report files in evidence/waves/."""
    if not os.path.isdir(waves_dir):
        return 0
    return sum(1 for f in os.listdir(waves_dir) if f.endswith(".md"))


def run_checks(folder, mode):
    """Run all verification checks. Returns list of (name, passed, detail) tuples."""
    t = THRESHOLDS[mode]
    evidence = os.path.join(folder, "evidence")
    results = []

    # --- Sources ---
    sources = load_json(os.path.join(evidence, "sources.json"))
    total_sources = len(sources)
    results.append((
        "source_count",
        total_sources >= t["sources_min"],
        f"{total_sources} (need >= {t['sources_min']})",
    ))

    # --- Rated % ---
    rated = sum(
        1 for s in sources.values()
        if isinstance(s, dict) and s.get("rating") is not None
    )
    rated_pct = (rated / total_sources * 100) if total_sources > 0 else 0
    results.append((
        "rated_pct",
        rated_pct >= t["rated_pct"],
        f"{rated_pct:.1f}% ({rated}/{total_sources}, need >= {t['rated_pct']}%)",
    ))

    # --- Pages cached ---
    pages_dir = os.path.join(evidence, "pages")
    pages_total, pages_non_empty = check_non_empty_pages(pages_dir)
    results.append((
        "pages_cached",
        pages_total >= t["pages_cached_min"],
        f"{pages_total} files ({pages_non_empty} non-empty, need >= {t['pages_cached_min']})",
    ))
    results.append((
        "pages_non_empty",
        pages_non_empty >= t["pages_cached_min"],
        f"{pages_non_empty} non-empty (need >= {t['pages_cached_min']})",
    ))

    # --- Claims ---
    claims = load_json(os.path.join(evidence, "claims.json"))
    claims_count = len(claims)
    results.append((
        "claims_count",
        claims_count >= t["claims_min"],
        f"{claims_count} (need >= {t['claims_min']})",
    ))

    # --- Hypotheses ---
    hypotheses = load_json(os.path.join(evidence, "hypotheses.json"))
    hyp_count = len(hypotheses)
    results.append((
        "hypotheses_count",
        hyp_count >= t["hypotheses_min"],
        f"{hyp_count} (need >= {t['hypotheses_min']})",
    ))

    # --- Report ---
    word_count, report_name = count_words_in_md(folder)
    results.append((
        "report_exists",
        report_name is not None,
        report_name or "no research_report*.md found",
    ))
    results.append((
        "report_words",
        word_count >= t["report_words_min"],
        f"{word_count} words (need >= {t['report_words_min']})",
    ))

    # --- Analysis artifacts ---
    for artifact in ["triangulation.md", "ach_matrix.md", "CRITIQUE.md"]:
        path = os.path.join(evidence, artifact)
        exists = os.path.isfile(path)
        results.append((
            f"artifact_{artifact}",
            exists,
            "exists" if exists else "MISSING",
        ))

    # --- Wave reports ---
    waves_dir = os.path.join(evidence, "waves")
    wave_count = check_wave_reports(waves_dir)
    results.append((
        "wave_reports",
        wave_count > 0,
        f"{wave_count} wave reports in evidence/waves/",
    ))

    return results


def main():
    parser = argparse.ArgumentParser(description="Verify deep-research output quality")
    parser.add_argument("folder", help="Path to research output folder")
    parser.add_argument(
        "--mode",
        required=True,
        choices=list(THRESHOLDS.keys()),
        help="Research mode (determines thresholds)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    folder = os.path.expanduser(args.folder)
    if not os.path.isdir(folder):
        print(f"ERROR: Folder not found: {folder}", file=sys.stderr)
        sys.exit(1)

    results = run_checks(folder, args.mode)
    overall_pass = all(passed for _, passed, _ in results)

    if args.json_output:
        output = {
            "folder": folder,
            "mode": args.mode,
            "overall": "PASS" if overall_pass else "FAIL",
            "checks": [
                {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
                for name, passed, detail in results
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Deep Research Output Verification — mode: {args.mode}")
        print(f"Folder: {folder}")
        print("-" * 60)
        for name, passed, detail in results:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}: {detail}")
        print("-" * 60)
        print(f"Overall: {'PASS' if overall_pass else 'FAIL'}")

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
