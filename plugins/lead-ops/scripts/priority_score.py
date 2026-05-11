"""Config-driven priority scorer for lead-ops.

Reads `lead-ops.config.yaml` for scoring rules (plain-English-ish expressions
under `scoring.priorities` plus optional `scoring.overrides`), evaluates each
expression per lead via a restricted AST evaluator, and writes the matching
priority into the `priority` field of each lead. First-match-wins. Overrides
(e.g. X for `do_not_approach or competitor`) are checked first.

Idempotent: a re-run on unchanged input produces an unchanged output. The
evaluator only allows comparisons, boolean ops, `in`, `not in`, attribute /
item access on the lead dict, numeric literals, string literals, and a fixed
set of helpers (`evidence_count`, `len`).

CLI usage:
    python -m priority_score --config ./lead-ops.config.yaml --leads ./leads.json
    python -m priority_score --config <path> --leads <path> --dry-run

Exit codes:
    0   success
    1   invalid arguments / file missing
    2   rule evaluation error
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Not,
    ast.UnaryOp,
    ast.USub,
    ast.UAdd,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Subscript,
    ast.Attribute,
    ast.Call,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.IfExp,
)

ALLOWED_FUNCS = {"len", "evidence_count", "has", "lower", "any_of", "all_of"}


class RuleError(Exception):
    """Raised when a rule expression is invalid or unsafe."""


def _check_ast(node: ast.AST) -> None:
    for child in ast.walk(node):
        if not isinstance(child, ALLOWED_NODES):
            raise RuleError(f"disallowed expression element: {type(child).__name__}")
        if isinstance(child, ast.Call):
            if not isinstance(child.func, ast.Name) or child.func.id not in ALLOWED_FUNCS:
                raise RuleError("calls limited to: " + ", ".join(sorted(ALLOWED_FUNCS)))


class _LeadProxy:
    """Attribute-style read access to a lead dict, with missing -> None."""

    def __init__(self, lead: dict[str, Any]) -> None:
        self._lead = lead

    def __getattr__(self, name: str) -> Any:
        return self._lead.get(name)

    def __getitem__(self, key: str) -> Any:
        return self._lead.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._lead


def _evidence_count(lead: _LeadProxy | dict) -> int:
    raw = lead._lead if isinstance(lead, _LeadProxy) else lead
    return len(raw.get("evidence", []) or [])


def _has(lead: _LeadProxy | dict, field: str) -> bool:
    raw = lead._lead if isinstance(lead, _LeadProxy) else lead
    value = raw.get(field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return bool(value)
    return True


def _lower(value: Any) -> str:
    return str(value or "").lower()


def _any_of(value: Any, options: Iterable[Any]) -> bool:
    return value in set(options)


def _all_of(values: Iterable[Any], options: Iterable[Any]) -> bool:
    options_set = set(options)
    return all(v in options_set for v in values or [])


def _referenced_names(tree: ast.AST) -> set[str]:
    """Return the set of bare identifiers referenced in `tree`."""
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _eval(expr: str, lead: dict[str, Any]) -> bool:
    """Compile and evaluate a single rule expression against `lead`."""
    if not expr or not expr.strip():
        return False
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise RuleError(f"syntax error in rule: {expr!r} ({exc.msg})") from exc
    _check_ast(tree)

    proxy = _LeadProxy(lead)
    env: dict[str, Any] = {
        # __builtins__ stays empty: sandboxed, AST whitelist already prevents
        # arbitrary calls.
        "__builtins__": {},
        # Field names exposed as bare identifiers, plus the lead itself.
        "lead": proxy,
        "evidence_count": lambda: _evidence_count(proxy),
        "len": len,
        "has": lambda field: _has(proxy, field),
        "lower": _lower,
        "any_of": _any_of,
        "all_of": _all_of,
    }
    # Promote every lead field to a top-level name for ergonomic rules.
    for key, value in lead.items():
        env.setdefault(key, value)
    # Derived convenience: ev_count for compatibility with genesis examples.
    env.setdefault("ev_count", _evidence_count(proxy))
    env.setdefault("reachable", lead.get("linkedin_connection") in {"1st", "2nd"})
    env.setdefault("quotable", bool((lead.get("key_quote") or "").strip()))
    # Default missing identifiers to None so rules can reference optional
    # fields (e.g. `do_not_approach`) without forcing every lead to define them.
    for name in _referenced_names(tree):
        env.setdefault(name, None)

    try:
        return bool(eval(compile(tree, "<rule>", "eval"), env, {}))
    except Exception as exc:  # noqa: BLE001 — surface any rule error uniformly
        raise RuleError(f"error evaluating rule {expr!r}: {exc}") from exc


def score_lead(lead: dict[str, Any], scoring: dict[str, Any]) -> str:
    """Return priority bucket for a single lead. Defaults to 'D' when nothing matches."""
    overrides: dict[str, str] = scoring.get("overrides") or {}
    for bucket, expr in overrides.items():
        if _eval(expr, lead):
            return bucket

    priorities: dict[str, str] = scoring.get("priorities") or {}
    for bucket, expr in priorities.items():
        if _eval(expr, lead):
            return bucket

    return "D"


def score_all(leads: list[dict], scoring: dict[str, Any]) -> list[dict]:
    """Mutate-in-place: write `priority` on each lead and return the list."""
    for lead in leads:
        lead["priority"] = score_lead(lead, scoring)
    return leads


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_leads(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array of lead objects")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="priority_score",
        description="Apply config-driven priority rules to leads.json.",
    )
    parser.add_argument("--config", required=True, help="Path to lead-ops.config.yaml")
    parser.add_argument("--leads", required=True, help="Path to leads.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute priorities and print summary; do not write file.",
    )
    return parser


def _summary(leads: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for lead in leads:
        counts[lead.get("priority", "D")] = counts.get(lead.get("priority", "D"), 0) + 1
    return dict(sorted(counts.items()))


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    config_path = Path(args.config)
    leads_path = Path(args.leads)
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 1
    if not leads_path.exists():
        print(f"leads file not found: {leads_path}", file=sys.stderr)
        return 1

    config = _load_config(config_path)
    scoring = config.get("scoring") or {}
    if not scoring:
        print("config has no `scoring` section; nothing to do", file=sys.stderr)
        return 1

    leads = _load_leads(leads_path)
    try:
        score_all(leads, scoring)
    except RuleError as exc:
        print(f"rule error: {exc}", file=sys.stderr)
        return 2

    summary = _summary(leads)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "by_priority": summary}, indent=2))
        return 0

    leads_path.write_text(json.dumps(leads, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"written": str(leads_path), "by_priority": summary}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
