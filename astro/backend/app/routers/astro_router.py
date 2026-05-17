from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.services import astronomy
from app.services.events import upcoming_meteor_showers, visible_planets

router = APIRouter(prefix="/api/astro", tags=["astronomy"])


@router.get("/sun-moon")
def sun_moon(
    lat: float = Query(...),
    lon: float = Query(...),
    date_str: str | None = Query(None, alias="date"),
):
    target_date = date.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    twilight = astronomy.compute_twilight(lat, lon, target_date)
    midpoint_default = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    moon = astronomy.moon_info(lat, lon, midpoint_default.replace(hour=23))
    return {
        "date": target_date.isoformat(),
        "lat": lat,
        "lon": lon,
        "twilight": twilight.to_dict(),
        "moon": moon,
    }


@router.get("/planets")
def planets(lat: float = Query(...), lon: float = Query(...), when: str | None = None):
    t = datetime.fromisoformat(when) if when else datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return {"when": t.isoformat(), "planets": visible_planets(lat, lon, t)}


@router.get("/meteor-showers")
def meteor_showers(days_ahead: int = 90):
    today = datetime.now(timezone.utc).date()
    return {"today": today.isoformat(), "showers": upcoming_meteor_showers(today, days_ahead)}
