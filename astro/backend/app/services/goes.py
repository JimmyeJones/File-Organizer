"""GOES satellite imagery from NOAA STAR.

Uses the publicly accessible CDN, which has pre-rendered JPEGs for many
sectors and bands. We expose URLs the frontend can render directly, plus
animation frame lists.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

CDN_BASE = "https://cdn.star.nesdis.noaa.gov"

# Common sector configs. Each maps to a directory under CDN_BASE/<sat>/ABI/<sector>/<band>/
SECTORS = {
    "conus": {
        "label": "CONUS (Continental US)",
        "satellite": "GOES19",
        "path": "GOES19/ABI/CONUS",
        "resolutions": ["1250x750", "2500x1500", "5000x3000"],
    },
    "fulldisk": {
        "label": "Full Disk",
        "satellite": "GOES19",
        "path": "GOES19/ABI/FD",
        "resolutions": ["678x678", "1808x1808", "5424x5424"],
    },
    "ne": {
        "label": "Northeast US",
        "satellite": "GOES19",
        "path": "GOES19/ABI/SECTOR/ne",
        "resolutions": ["600x600", "1200x1200", "2400x2400"],
    },
    "se": {
        "label": "Southeast US",
        "satellite": "GOES19",
        "path": "GOES19/ABI/SECTOR/se",
        "resolutions": ["600x600", "1200x1200", "2400x2400"],
    },
    "pnw": {
        "label": "Pacific NW",
        "satellite": "GOES18",
        "path": "GOES18/ABI/SECTOR/pnw",
        "resolutions": ["600x600", "1200x1200", "2400x2400"],
    },
    "psw": {
        "label": "Pacific SW",
        "satellite": "GOES18",
        "path": "GOES18/ABI/SECTOR/psw",
        "resolutions": ["600x600", "1200x1200", "2400x2400"],
    },
}

# Band selections useful for astrophotographers (cloud detection)
BANDS = {
    "GEOCOLOR": "True-color composite (daytime)",
    "13": "Clean IR (cloud cover, day/night)",
    "08": "Upper-level water vapor",
    "02": "Visible (daytime, high-res)",
}


def list_sectors() -> list[dict]:
    return [
        {"id": k, "label": v["label"], "satellite": v["satellite"]}
        for k, v in SECTORS.items()
    ]


def list_bands() -> list[dict]:
    return [{"id": k, "label": v} for k, v in BANDS.items()]


def latest_image_url(sector: str, band: str = "GEOCOLOR", resolution: str | None = None) -> str:
    cfg = SECTORS.get(sector)
    if not cfg:
        raise ValueError(f"unknown sector: {sector}")
    res = resolution or cfg["resolutions"][0]
    # NOAA STAR CDN serves the most-recent frame as "<resolution>.jpg" in each
    # band directory, e.g. .../GOES19/ABI/CONUS/GEOCOLOR/1250x750.jpg
    return f"{CDN_BASE}/{cfg['path']}/{band}/{res}.jpg"


async def list_animation_frames(
    sector: str, band: str = "GEOCOLOR", resolution: str | None = None, limit: int = 12
) -> list[dict]:
    """Scrape the directory listing to get recent frame filenames.

    Returns most-recent-first list of {timestamp, url}.
    """
    cfg = SECTORS.get(sector)
    if not cfg:
        raise ValueError(f"unknown sector: {sector}")
    res = resolution or cfg["resolutions"][0]
    listing_url = f"{CDN_BASE}/{cfg['path']}/{band}/"

    async with httpx.AsyncClient(headers={"User-Agent": settings.user_agent}) as client:
        try:
            r = await client.get(listing_url, timeout=settings.request_timeout)
            r.raise_for_status()
            text = r.text
        except Exception:
            return [
                {"timestamp": None, "url": latest_image_url(sector, band, res)}
            ]

    # Filenames look like: 20251352145_GOES19-ABI-CONUS-GEOCOLOR-1250x750.jpg
    pattern = re.compile(
        rf'(\d{{11}})_[^"]*-{re.escape(band)}-{re.escape(res)}\.jpg'
    )
    seen = set()
    frames = []
    for m in pattern.finditer(text):
        fname = m.group(0)
        if fname in seen:
            continue
        seen.add(fname)
        ts_raw = m.group(1)  # YYYYDDDHHMM (year, day-of-year, hour, minute)
        try:
            year = int(ts_raw[:4])
            doy = int(ts_raw[4:7])
            hour = int(ts_raw[7:9])
            minute = int(ts_raw[9:11])
            dt = datetime(year, 1, 1, hour, minute, tzinfo=timezone.utc) + timedelta(days=doy - 1)
        except Exception:
            dt = None
        frames.append({
            "timestamp": dt.isoformat() if dt else None,
            "url": f"{listing_url}{fname}",
        })

    frames.sort(key=lambda f: f["timestamp"] or "", reverse=True)
    return frames[:limit]
