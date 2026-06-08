"""ISS and bright satellite pass predictions.

Pulls TLE data from Celestrak (free, no auth) and propagates with sgp4 +
Skyfield to compute upcoming visible passes.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from skyfield.api import EarthSatellite, wgs84

from app.config import settings
from app.services.astronomy import get_ephemeris, get_timescale

CELESTRAK_GROUPS = {
    "stations": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    "visual": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
    "starlink": "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle",
}

# Some groups (Starlink) contain thousands of objects. Propagating all of them
# would take minutes and time out the request, so cap how many we process.
_MAX_SATS = {"starlink": 90}

_tle_cache: dict[str, tuple[datetime, list[tuple[str, str, str]]]] = {}
_TLE_TTL = timedelta(hours=4)


async def _fetch_tles(group: str) -> list[tuple[str, str, str]]:
    cached = _tle_cache.get(group)
    if cached and datetime.now(timezone.utc) - cached[0] < _TLE_TTL:
        return cached[1]

    url = CELESTRAK_GROUPS[group]
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=settings.request_timeout)
        r.raise_for_status()
        lines = [l.strip() for l in r.text.splitlines() if l.strip()]

    tles = []
    for i in range(0, len(lines) - 2, 3):
        name = lines[i]
        l1 = lines[i + 1]
        l2 = lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            tles.append((name, l1, l2))

    _tle_cache[group] = (datetime.now(timezone.utc), tles)
    return tles


async def predict_passes(
    lat: float,
    lon: float,
    group: str = "stations",
    hours: int = 24,
    min_altitude: float = 20.0,
) -> list[dict]:
    tles = await _fetch_tles(group)
    cap = _MAX_SATS.get(group)
    if cap:
        tles = tles[:cap]
    # SGP4 propagation is CPU-bound and synchronous; run it off the event loop
    # so the server stays responsive to other requests.
    return await asyncio.to_thread(
        _compute_passes, tles, lat, lon, hours, min_altitude
    )


def _compute_passes(
    tles: list[tuple[str, str, str]],
    lat: float,
    lon: float,
    hours: int,
    min_altitude: float,
) -> list[dict]:
    ts = get_timescale()
    eph = get_ephemeris()
    observer = wgs84.latlon(lat, lon)
    sun = eph["sun"]

    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=hours)
    t0 = ts.from_datetime(start)
    t1 = ts.from_datetime(end)

    passes = []
    for name, l1, l2 in tles:
        try:
            sat = EarthSatellite(l1, l2, name, ts)
        except Exception:
            continue
        try:
            times, events = sat.find_events(observer, t0, t1, altitude_degrees=min_altitude)
        except Exception:
            continue

        # events: 0=rise, 1=culmination, 2=set
        rise = culm = setting = None
        peak_alt = 0.0
        for t, ev in zip(times, events):
            if ev == 0:
                rise = t
            elif ev == 1:
                culm = t
            elif ev == 2:
                setting = t
                if rise and culm:
                    # Check if visible (satellite sunlit + observer in darkness)
                    alt, az, _ = (sat - observer).at(culm).altaz()
                    peak_alt = float(alt.degrees)

                    sun_alt = (eph["earth"] + observer).at(culm).observe(sun).apparent().altaz()[0].degrees
                    sat_sunlit = sat.at(culm).is_sunlit(eph)

                    visible = sun_alt < -6 and sat_sunlit
                    passes.append({
                        "satellite": name,
                        "rise": rise.utc_datetime().isoformat(),
                        "culmination": culm.utc_datetime().isoformat(),
                        "set": setting.utc_datetime().isoformat(),
                        "peak_altitude_deg": round(peak_alt, 1),
                        "visible": bool(visible),
                    })
                    rise = culm = None

    passes.sort(key=lambda p: p["rise"])
    return passes
