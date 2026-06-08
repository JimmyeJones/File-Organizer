"""Persistent observing-site profiles stored as a JSON file."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.config import settings

_lock = Lock()


def _ensure_file() -> Path:
    path = settings.sites_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]")
    return path


def list_sites() -> list[dict]:
    with _lock:
        return json.loads(_ensure_file().read_text())


def get_site(site_id: str) -> dict | None:
    for s in list_sites():
        if s["id"] == site_id:
            return s
    return None


def create_site(payload: dict) -> dict:
    with _lock:
        path = _ensure_file()
        sites = json.loads(path.read_text())
        site = {
            "id": str(uuid.uuid4()),
            "name": payload["name"],
            "lat": float(payload["lat"]),
            "lon": float(payload["lon"]),
            "elevation_m": float(payload.get("elevation_m", 0)),
            "bortle": payload.get("bortle"),
            "sqm": payload.get("sqm"),
            "notes": payload.get("notes", ""),
            "horizon_profile": payload.get("horizon_profile", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        sites.append(site)
        path.write_text(json.dumps(sites, indent=2))
        return site


def update_site(site_id: str, payload: dict) -> dict | None:
    with _lock:
        path = _ensure_file()
        sites = json.loads(path.read_text())
        for i, s in enumerate(sites):
            if s["id"] == site_id:
                sites[i] = {**s, **{k: v for k, v in payload.items() if k != "id"}}
                path.write_text(json.dumps(sites, indent=2))
                return sites[i]
        return None


def delete_site(site_id: str) -> bool:
    with _lock:
        path = _ensure_file()
        sites = json.loads(path.read_text())
        new_sites = [s for s in sites if s["id"] != site_id]
        if len(new_sites) == len(sites):
            return False
        path.write_text(json.dumps(new_sites, indent=2))
        return True
