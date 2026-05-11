"""Google Sheets working surface.

Thin wrapper around scripts/sheet_upload.py. The heavy lifting (OAuth refresh,
backup, per-cell diff, RAW write) lives there; this module exposes the
standard surface contract so /lead-ops:build can call it uniformly.

Surface contract:
    setup(config)        -> dict   sanity-check spreadsheet access; no writes.
    upsert(config, leads) -> dict  backup-then-diff-then-write.
    read(config)         -> list[list[str]]  current sheet rows.
    backup(config)       -> Path   write a JSON snapshot under ./exports/.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def _load_sheet_upload():
    """Import scripts/sheet_upload.py from ${CLAUDE_PLUGIN_ROOT}/scripts."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        scripts_dir = Path(plugin_root) / "scripts"
    else:
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    target = scripts_dir / "sheet_upload.py"
    if not target.exists():
        raise RuntimeError(f"sheet_upload.py not found at {target}")
    spec = importlib.util.spec_from_file_location("sheet_upload", target)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sheet_upload"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def setup(config: dict[str, Any]) -> dict[str, Any]:
    """Verify credentials and spreadsheet are reachable. Returns sheet metadata."""
    su = _load_sheet_upload()
    surface_cfg = su._surface(config)
    creds = su._load_credentials(su._resolve_creds_path(config))
    token = su._access_token(creds)
    spreadsheet_id = surface_cfg.get("spreadsheet_id")
    tab = surface_cfg.get("tab") or "Sheet1"
    rows = su._read_sheet(spreadsheet_id, f"{tab}!A1:B1", token)
    return {"ok": True, "spreadsheet_id": spreadsheet_id, "tab": tab, "header_sample": rows}


def upsert(config: dict[str, Any], leads: list[dict[str, Any]]) -> dict[str, Any]:
    """Backup the sheet, compute per-cell diff, write only changed cells."""
    su = _load_sheet_upload()
    surface_cfg = su._surface(config)
    spreadsheet_id = surface_cfg["spreadsheet_id"]
    tab = surface_cfg.get("tab") or "Sheet1"
    columns = su._columns(config)

    creds = su._load_credentials(su._resolve_creds_path(config))
    token = su._access_token(creds)

    current = su._read_sheet(spreadsheet_id, f"{tab}!A1:ZZ", token)
    backup_path = su._backup_sheet(current, Path("./exports"))

    header_present = bool(current) and current[0] == columns
    desired = su._build_rows(leads, columns)
    data, appends = su._diff(current, desired, columns, tab, header_present)
    result = su._batch_update(spreadsheet_id, token, data, dry_run=False)
    return {
        "backup": str(backup_path),
        "diff_cells": len(data),
        "appends": appends,
        "result": result,
    }


def read(config: dict[str, Any]) -> list[list[str]]:
    """Return current rows from the sheet (raw, including header)."""
    su = _load_sheet_upload()
    surface_cfg = su._surface(config)
    creds = su._load_credentials(su._resolve_creds_path(config))
    token = su._access_token(creds)
    spreadsheet_id = surface_cfg["spreadsheet_id"]
    tab = surface_cfg.get("tab") or "Sheet1"
    return su._read_sheet(spreadsheet_id, f"{tab}!A1:ZZ", token)


def backup(config: dict[str, Any]) -> Path:
    """Write a JSON snapshot of the current sheet to ./exports/. Returns the path."""
    su = _load_sheet_upload()
    rows = read(config)
    return su._backup_sheet(rows, Path("./exports"))
