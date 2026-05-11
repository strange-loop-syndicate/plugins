"""CSV working surface.

Writes one row per lead to a CSV file with headers from the configured column
order (or the schema fields when no explicit columns are given). UTF-8 output.
List-valued fields (e.g. evidence URLs) are joined with newlines inside the
cell — Excel and Sheets both handle this when the cell is quoted by csv.writer.

Surface contract:
    setup(config)        -> dict   ensure target directory exists.
    upsert(config, leads) -> dict  write full file (CSV doesn't support diffs).
    read(config)         -> list[list[str]]  rows including header.
    backup(config)       -> Path   copy current file to ./exports/<ts>.csv.
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _surface_cfg(config: dict) -> dict:
    surface = config.get("working_surface") or {}
    if surface.get("type") != "csv":
        raise ValueError(f"csv surface called for type={surface.get('type')}")
    return surface.get("config") or {}


def _target(config: dict) -> Path:
    cfg = _surface_cfg(config)
    file_path = cfg.get("file_path") or "./leads.csv"
    return Path(file_path).expanduser()


def _columns(config: dict) -> list[str]:
    cfg = _surface_cfg(config)
    if cols := cfg.get("columns"):
        return list(cols)
    schema = config.get("schema") or {}
    cols = list(schema.get("core_fields") or [])
    for f in schema.get("custom_fields") or []:
        cols.append(f["name"] if isinstance(f, dict) else f)
    return cols


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and "url" in item for item in value):
            return "\n".join(str(item.get("url", "")) for item in value if item.get("url"))
        return "\n".join(str(v) for v in value)
    return str(value)


def setup(config: dict[str, Any]) -> dict[str, Any]:
    """Ensure the parent directory of the output file exists."""
    target = _target(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "target": str(target)}


def upsert(config: dict[str, Any], leads: list[dict[str, Any]]) -> dict[str, Any]:
    """Overwrite the CSV file in full with header + one row per lead."""
    target = _target(config)
    columns = _columns(config)
    if not columns:
        raise ValueError("csv surface requires either working_surface.config.columns or schema fields")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        for lead in leads:
            writer.writerow([_stringify(lead.get(col)) for col in columns])
    return {"target": str(target), "rows": len(leads)}


def read(config: dict[str, Any]) -> list[list[str]]:
    """Return rows including header. Empty list if file doesn't exist yet."""
    target = _target(config)
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as fh:
        return [row for row in csv.reader(fh)]


def backup(config: dict[str, Any]) -> Path:
    """Copy current CSV to ./exports/<basename>_<ts>.csv. Returns the path."""
    target = _target(config)
    if not target.exists():
        raise FileNotFoundError(f"nothing to back up: {target}")
    exports = Path("./exports")
    exports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = exports / f"{target.stem}_{ts}.csv"
    shutil.copy2(target, dest)
    return dest
