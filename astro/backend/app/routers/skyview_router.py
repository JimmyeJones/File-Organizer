"""Sky view endpoints: planet positions across the night, satellite current positions."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.services import astronomy
from app.services.events import visible_planets

router = APIRouter(prefix="/api/skyview", tags=["skyview"])


@router.get("/planet-track")
def planet_track(
    lat: float = Query(...),
    lon: float = Query(...),
    date_str: str | None = Query(None, alias="date"),
    step_minutes: int = 20,
):
    """Return alt/az for each planet at intervals across tonight's dark window."""
    target_date = date.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    twilight = astronomy.compute_twilight(lat, lon, target_date)

    start = twilight.sunset or datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=20)
    end = twilight.sunrise or (start + timedelta(hours=14))
    if end <= start:
        end = start + timedelta(hours=14)

    n = int((end - start).total_seconds() / (step_minutes * 60)) + 1
    times = [start + timedelta(minutes=step_minutes * i) for i in range(n)]

    planet_tracks: dict[str, list[dict]] = {}
    for t in times:
        for p in visible_planets(lat, lon, t):
            planet_tracks.setdefault(p["name"], []).append({
                "t": t.isoformat(),
                "alt": p["altitude_deg"],
                "az": p["azimuth_deg"],
            })

    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "step_minutes": step_minutes,
        "times": [t.isoformat() for t in times],
        "planet_tracks": planet_tracks,
    }


@router.get("/dso-track")
def dso_track(
    lat: float = Query(...),
    lon: float = Query(...),
    date_str: str | None = Query(None, alias="date"),
    step_minutes: int = 20,
):
    """Return alt/az curves for all catalog objects across tonight's dark window."""
    from app.data.catalog import get_catalog

    target_date = date.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    twilight = astronomy.compute_twilight(lat, lon, target_date)
    start = twilight.sunset or datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=20)
    end = twilight.sunrise or (start + timedelta(hours=14))
    if end <= start:
        end = start + timedelta(hours=14)

    n = int((end - start).total_seconds() / (step_minutes * 60)) + 1
    times = [start + timedelta(minutes=step_minutes * i) for i in range(n)]

    catalog = get_catalog()
    dso_tracks = []
    for obj in catalog:
        curve = []
        for t in times:
            alt, az = astronomy.altaz_for_target(obj["ra"], obj["dec"], lat, lon, t)
            curve.append({"t": t.isoformat(), "alt": round(alt, 1), "az": round(az, 1)})
        dso_tracks.append({
            "id": obj["id"],
            "name": obj["name"],
            "type": obj["type"],
            "mag": obj["mag"],
            "size": obj["size"],
            "ra": obj["ra"],
            "dec": obj["dec"],
            "curve": curve,
        })

    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "times": [t.isoformat() for t in times],
        "dso_tracks": dso_tracks,
    }
