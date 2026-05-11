"""Bulk Google Sheets writer with OAuth + RAW + targeted diff.

Reads `lead-ops.config.yaml` for the working surface block (spreadsheet ID, tab,
column ordering, OAuth credentials path), pulls the current sheet state, backs
it up to ./exports/sheet_backup_<ts>.json, computes per-cell diffs between
leads.json and the live sheet, and writes ONLY the changed cells via the
Sheets v4 batchUpdate endpoint with `valueInputOption=RAW`. This avoids
the "+27" cell being parsed as a formula, prevents column reorders, and keeps
quota usage proportional to actual changes.

CLI usage:
    python -m sheet_upload --config ./lead-ops.config.yaml --leads ./leads.json
    python -m sheet_upload --config <path> --leads <path> --dry-run
    python -m sheet_upload --config <path> --leads <path> --backup-only

Exit codes:
    0   success
    1   invalid arguments / file missing
    2   OAuth / API failure
    3   credentials file missing or expired
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_CREDS_DIR = Path("~/.google_workspace_mcp/credentials").expanduser()
DEFAULT_TIMEOUT = 60


class AuthError(Exception):
    """Raised when credentials are missing, expired, or refresh fails."""


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_leads(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected JSON array of lead objects")
    return data


def _resolve_creds_path(config: dict) -> Path:
    surface = (config.get("working_surface") or {}).get("config") or {}
    explicit = surface.get("oauth_credentials_path")
    if explicit:
        return Path(explicit).expanduser()
    email = surface.get("oauth_email") or config.get("project", {}).get("owner_email")
    if not email:
        raise AuthError(
            "no oauth credentials path and no oauth_email/owner_email in config"
        )
    return DEFAULT_CREDS_DIR / f"{email}.json"


def _load_credentials(path: Path) -> dict:
    if not path.exists():
        raise AuthError(f"credentials file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _access_token(creds: dict) -> str:
    """Return a valid access token, refreshing if necessary."""
    token = creds.get("access_token")
    expiry = creds.get("expiry") or 0
    if token and time.time() < float(expiry) - 60:
        return token

    refresh = creds.get("refresh_token")
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    if not (refresh and client_id and client_secret):
        raise AuthError("credentials missing refresh_token / client_id / client_secret")

    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code != 200:
        raise AuthError(f"token refresh failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    return payload["access_token"]


def _surface(config: dict) -> dict:
    surface = config.get("working_surface") or {}
    if surface.get("type") != "google_sheets":
        raise ValueError(
            f"sheet_upload requires working_surface.type=google_sheets (got {surface.get('type')})"
        )
    return surface.get("config") or {}


def _columns(config: dict) -> list[str]:
    """Return ordered column list from working_surface.config.columns,
    falling back to schema.core_fields + custom_fields names."""
    surface_cfg = _surface(config)
    if cols := surface_cfg.get("columns"):
        return list(cols)
    schema = config.get("schema") or {}
    cols = list(schema.get("core_fields") or [])
    for f in schema.get("custom_fields") or []:
        cols.append(f["name"] if isinstance(f, dict) else f)
    return cols


def _read_sheet(spreadsheet_id: str, range_: str, token: str) -> list[list[str]]:
    url = f"{SHEETS_API}/{spreadsheet_id}/values/{range_}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"valueRenderOption": "UNFORMATTED_VALUE"},
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"GET {url} failed: {resp.status_code} {resp.text}")
    return resp.json().get("values", [])


def _backup_sheet(rows: list[list[str]], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"sheet_backup_{ts}.json"
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _stringify(value: Any) -> str:
    """Render a cell value for RAW write. Lists join with newlines."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and "url" in item for item in value):
            # Evidence-style array: newline-join URLs (NO semicolons — sheets auto-link).
            return "\n".join(str(item.get("url", "")) for item in value if item.get("url"))
        return "\n".join(str(v) for v in value)
    return str(value)


def _build_rows(leads: list[dict], columns: list[str]) -> list[list[str]]:
    """Render leads to a 2D matrix, one row per lead, columns in given order."""
    matrix: list[list[str]] = []
    for lead in leads:
        matrix.append([_stringify(lead.get(col)) for col in columns])
    return matrix


def _col_letter(idx: int) -> str:
    """Zero-indexed column -> A1 letter (0 -> A, 25 -> Z, 26 -> AA)."""
    out = ""
    n = idx
    while True:
        out = chr(ord("A") + (n % 26)) + out
        n = n // 26 - 1
        if n < 0:
            break
    return out


def _diff(
    current: list[list[str]],
    desired: list[list[str]],
    header: list[str],
    tab: str,
    header_present: bool,
) -> tuple[list[dict], int]:
    """Compute per-cell diffs. Returns (batch_data, append_count).

    `current` includes the header row if `header_present`. The data starts at
    row 2 (1-indexed) in that case, otherwise row 1.
    """
    data: list[dict] = []
    data_start_row = 2 if header_present else 1
    current_data = current[1:] if header_present else current

    appends = max(0, len(desired) - len(current_data))

    for r, new_row in enumerate(desired):
        sheet_row_idx = data_start_row + r
        if r < len(current_data):
            old_row = current_data[r]
        else:
            old_row = []
        for c, new_val in enumerate(new_row):
            old_val = old_row[c] if c < len(old_row) else ""
            if str(old_val) != str(new_val):
                a1 = f"{tab}!{_col_letter(c)}{sheet_row_idx}"
                data.append({"range": a1, "values": [[new_val]]})

    # Ensure header is correct if missing or mismatched.
    if not header_present or (current and current[0] != header):
        data.append({"range": f"{tab}!A1", "values": [header]})

    return data, appends


def _batch_update(
    spreadsheet_id: str, token: str, data: list[dict], dry_run: bool
) -> dict:
    if dry_run:
        return {"dry_run": True, "cells_to_write": len(data)}
    if not data:
        return {"cells_written": 0}
    url = f"{SHEETS_API}/{spreadsheet_id}/values:batchUpdate"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"valueInputOption": "RAW", "data": data},
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"batchUpdate failed: {resp.status_code} {resp.text}")
    body = resp.json()
    return {"cells_written": len(data), "api_response": body.get("totalUpdatedCells")}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sheet_upload",
        description="Backup + targeted RAW write of leads.json to Google Sheets.",
    )
    parser.add_argument("--config", required=True, help="Path to lead-ops.config.yaml")
    parser.add_argument("--leads", required=True, help="Path to leads.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute diff and print summary; do not write the sheet.",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="Read current sheet and write a backup; do not upload changes.",
    )
    parser.add_argument(
        "--export-dir",
        default="./exports",
        help="Where to write backups (default ./exports).",
    )
    return parser


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
    leads = _load_leads(leads_path)

    try:
        surface = _surface(config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    spreadsheet_id = surface.get("spreadsheet_id")
    tab = surface.get("tab") or "Sheet1"
    if not spreadsheet_id:
        print("config.working_surface.config.spreadsheet_id is required", file=sys.stderr)
        return 1

    try:
        creds = _load_credentials(_resolve_creds_path(config))
        token = _access_token(creds)
    except AuthError as exc:
        print(f"auth error: {exc}", file=sys.stderr)
        return 3

    columns = _columns(config)
    if not columns:
        print("no columns configured; set working_surface.config.columns or schema", file=sys.stderr)
        return 1

    try:
        current = _read_sheet(spreadsheet_id, f"{tab}!A1:ZZ", token)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    backup_path = _backup_sheet(current, Path(args.export_dir))

    if args.backup_only:
        print(json.dumps({"backup": str(backup_path), "rows": len(current)}, indent=2))
        return 0

    header_present = bool(current) and current[0] == columns
    desired = _build_rows(leads, columns)
    data, appends = _diff(current, desired, columns, tab, header_present)

    try:
        result = _batch_update(spreadsheet_id, token, data, args.dry_run)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "backup": str(backup_path),
                "diff_cells": len(data),
                "appends": appends,
                "result": result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
