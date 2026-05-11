"""Name normalization and layered matching utilities.

Strips academic suffixes (MD, PhD, JD, MPH, MBA, MBE, PharmD, DO, FACNM, FASCO,
BCPS, BCCCP, CIP, RN, BSN, RPh, Esq, DNP, PharmB, FNP and common variants),
lowercases, removes middle initials, and exposes layered matching primitives.

CLI usage:
    python -m name_normalize "Bateman-House, Alison MPH"
    python -m name_normalize --compare "Arthur L. Caplan" "Arthur Caplan PhD"
    python -m name_normalize --fuzzy "Subbiah V" "Vivek Subbiah"

Library API:
    normalize(name) -> str
        Strip suffixes, lowercase, strip middle initials, normalize whitespace.
    match_layered(a, b, layer) -> bool
        layer in {full, surname_initial_institution, surname_specialty_location, fuzzy}.
        Caller passes pre-concatenated comparable strings or tuples; see docstring.
    fuzzy_score(a, b) -> float
        Returns 0.0-1.0 similarity via difflib.SequenceMatcher.

Exit codes:
    0   success
    1   missing or invalid arguments
    2   internal error
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable

# Academic / professional suffixes stripped from names. Lowercased for matching.
# Order matters only for documentation; matching is set-based.
SUFFIXES: frozenset[str] = frozenset(
    {
        "md",
        "phd",
        "ph.d",
        "ph.d.",
        "jd",
        "mph",
        "mba",
        "mbe",
        "pharmd",
        "pharmb",
        "do",
        "facnm",
        "fasco",
        "facp",
        "facep",
        "facs",
        "facc",
        "fahn",
        "bcps",
        "bcccp",
        "bcop",
        "cip",
        "rn",
        "bsn",
        "msn",
        "rph",
        "esq",
        "esquire",
        "dnp",
        "fnp",
        "anp",
        "pa",
        "pa-c",
        "np",
        "ms",
        "msc",
        "ma",
        "ba",
        "bs",
        "bsc",
        "edd",
        "dsc",
        "dphil",
        "drph",
        "scd",
        "msw",
        "lcsw",
        "fellow",
        "frcp",
        "frcs",
        "mrcp",
        "mbbs",
        "mbchb",
        "dvm",
        "dds",
        "dmd",
        "od",
    }
)

# Punctuation that should be split on or stripped during tokenization.
_PUNCT_SPLIT_RE = re.compile(r"[,;]+")
_NON_WORD_RE = re.compile(r"[^\w\s'\-]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_MIDDLE_INITIAL_RE = re.compile(r"\b[a-z]\.?\b")


def _strip_accents(text: str) -> str:
    """Fold accented characters to ASCII equivalents where possible."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _split_suffix_tokens(token: str) -> list[str]:
    """Split a token like 'phd,facp' or 'phd.facp' into individual atoms."""
    return [t for t in re.split(r"[.,/]", token) if t]


def _is_suffix(token: str) -> bool:
    """Return True if token (lowercase) is a known suffix, ignoring trailing dots."""
    clean = token.strip(".").strip(",").lower()
    if not clean:
        return False
    if clean in SUFFIXES:
        return True
    # Handle "ph.d." / "ph.d" by re-checking with dots collapsed.
    return clean.replace(".", "") in {s.replace(".", "") for s in SUFFIXES}


def normalize(name: str) -> str:
    """Return a normalized form of `name` suitable for comparison.

    Steps: strip accents, lowercase, replace commas/semicolons with space,
    drop non-word punctuation (keeping hyphens and apostrophes),
    drop suffix tokens, drop single-letter middle initials, collapse whitespace.
    """
    if not name:
        return ""
    text = _strip_accents(name)
    text = _PUNCT_SPLIT_RE.sub(" ", text)
    text = _NON_WORD_RE.sub(" ", text)
    text = text.lower()
    text = _WS_RE.sub(" ", text).strip()

    tokens: list[str] = []
    for raw in text.split(" "):
        for atom in _split_suffix_tokens(raw):
            if _is_suffix(atom):
                continue
            tokens.append(atom)

    # Drop single-letter middle initials (e.g., "arthur l caplan" -> "arthur caplan").
    if len(tokens) >= 3:
        kept: list[str] = [tokens[0]]
        for tok in tokens[1:-1]:
            if _MIDDLE_INITIAL_RE.fullmatch(tok):
                continue
            kept.append(tok)
        kept.append(tokens[-1])
        tokens = kept

    return " ".join(tokens).strip()


def _tokens(name: str) -> list[str]:
    return normalize(name).split()


def surname(name: str) -> str:
    """Return the last token of the normalized name (best-effort surname)."""
    toks = _tokens(name)
    return toks[-1] if toks else ""


def first_initial(name: str) -> str:
    """Return the first letter of the first token of the normalized name."""
    toks = _tokens(name)
    return toks[0][0] if toks and toks[0] else ""


def fuzzy_score(a: str, b: str) -> float:
    """Return similarity ratio in [0.0, 1.0] using difflib.SequenceMatcher."""
    na = normalize(a)
    nb = normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def match_layered(
    a: str | dict,
    b: str | dict,
    layer: str,
    fuzzy_threshold: float = 0.88,
) -> bool:
    """Layered match between two records or name strings.

    Layers:
      - "full": normalized full names match exactly.
      - "surname_initial_institution": surname + first initial + institution.
        a and b must be dicts with keys {name, institution}.
      - "surname_specialty_location": surname + specialty + location.
        a and b must be dicts with keys {name, specialty, location}.
      - "fuzzy": fuzzy_score(name, name) >= fuzzy_threshold.

    For dict-based layers the caller is responsible for providing comparable
    institution / specialty / location values (normalize them upstream if needed).
    """
    if layer == "full":
        return normalize(_extract_name(a)) == normalize(_extract_name(b)) and bool(
            normalize(_extract_name(a))
        )

    if layer == "surname_initial_institution":
        if not (isinstance(a, dict) and isinstance(b, dict)):
            raise ValueError("layer requires dict inputs with 'name' and 'institution'")
        return (
            surname(a["name"]) == surname(b["name"])
            and first_initial(a["name"]) == first_initial(b["name"])
            and _norm_field(a.get("institution")) == _norm_field(b.get("institution"))
            and bool(surname(a["name"]))
            and bool(_norm_field(a.get("institution")))
        )

    if layer == "surname_specialty_location":
        if not (isinstance(a, dict) and isinstance(b, dict)):
            raise ValueError(
                "layer requires dict inputs with 'name', 'specialty', 'location'"
            )
        return (
            surname(a["name"]) == surname(b["name"])
            and _norm_field(a.get("specialty")) == _norm_field(b.get("specialty"))
            and _norm_field(a.get("location")) == _norm_field(b.get("location"))
            and bool(surname(a["name"]))
        )

    if layer == "fuzzy":
        return fuzzy_score(_extract_name(a), _extract_name(b)) >= fuzzy_threshold

    raise ValueError(f"unknown layer: {layer}")


def _extract_name(value: str | dict) -> str:
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return value or ""


def _norm_field(value: str | None) -> str:
    if not value:
        return ""
    text = _strip_accents(value).lower()
    text = _NON_WORD_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="name_normalize",
        description="Normalize names; compare via layered or fuzzy matching.",
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Single name to normalize. Prints the normalized form.",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("A", "B"),
        help="Compare two names: prints fuzzy_score and full-match boolean.",
    )
    parser.add_argument(
        "--fuzzy",
        nargs=2,
        metavar=("A", "B"),
        help="Print only the fuzzy similarity score between A and B.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.88,
        help="Fuzzy match threshold for boolean reporting (default 0.88).",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.fuzzy:
        print(f"{fuzzy_score(args.fuzzy[0], args.fuzzy[1]):.4f}")
        return 0

    if args.compare:
        a, b = args.compare
        score = fuzzy_score(a, b)
        full = match_layered(a, b, "full")
        print(f"normalized_a: {normalize(a)}")
        print(f"normalized_b: {normalize(b)}")
        print(f"fuzzy_score: {score:.4f}")
        print(f"full_match: {full}")
        print(f"fuzzy_match(threshold={args.threshold}): {score >= args.threshold}")
        return 0

    if args.name:
        print(normalize(args.name))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
