from datetime import date, datetime, timezone

from fastapi import APIRouter, Query

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

    # Report the Moon at the middle of the dark window (most relevant for an
    # imaging session) rather than an arbitrary fixed hour.
    dusk = twilight.astronomical_dusk or twilight.nautical_dusk or twilight.sunset
    dawn = twilight.astronomical_dawn or twilight.nautical_dawn or twilight.sunrise
    if dusk and dawn and dawn > dusk:
        moon_moment = dusk + (dawn - dusk) / 2
    else:
        moon_moment = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=23)
    moon = astronomy.moon_info(lat, lon, moon_moment)
    return {
        "date": target_date.isoformat(),
        "lat": lat,
        "lon": lon,
        "twilight": twilight.to_dict(),
        "moon": moon,
        "moon_moment": moon_moment.isoformat(),
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
