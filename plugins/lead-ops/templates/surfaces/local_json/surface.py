"""Local JSON working surface.

The canonical lead store is already ./leads.json (the build skill writes
there directly), so this surface is effectively a no-op exporter that
guarantees the file exists, with a backup-on-demand option for parity with
the Sheets and CSV surfaces.

Surface contract:
    setup(config)        -> dict   ensure parent directory exists.
    upsert(config, leads) -> dict  write ./leads.json (full rewrite).
    read(config)         -> list[dict]  load ./leads.json.
    backup(config)       -> Path   copy current file to ./exports/<ts>.json.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _target(config: dict) -> Path:
    surface = config.get("working_surface") or {}
    if surface.get("type") != "local_json":
        raise ValueError(f"local_json surface called for type={surface.get('type')}")
    cfg = surface.get("config") or {}
    return Path(cfg.get("file_path") or "./leads.json").expanduser()


def setup(config: dict[str, Any]) -> dict[str, Any]:
    """Make sure the parent directory exists; do not create the file."""
    target = _target(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "target": str(target)}


def upsert(config: dict[str, Any], leads: list[dict[str, Any]]) -> dict[str, Any]:
    """Write the leads list to ./leads.json with indent=2 UTF-8."""
    target = _target(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(leads, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"target": str(target), "rows": len(leads)}


def read(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the parsed lead list. Empty list if file doesn't exist."""
    target = _target(config)
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{target}: expected JSON array of lead objects")
    return data


def backup(config: dict[str, Any]) -> Path:
    """Copy current JSON to ./exports/<basename>_<ts>.json. Returns the path."""
    target = _target(config)
    if not target.exists():
        raise FileNotFoundError(f"nothing to back up: {target}")
    exports = Path("./exports")
    exports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = exports / f"{target.stem}_{ts}.json"
    shutil.copy2(target, dest)
    return dest
