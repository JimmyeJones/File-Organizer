"""Annual astronomical events: meteor showers and planet visibility."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from skyfield.api import wgs84

from app.services.astronomy import get_ephemeris, get_timescale

METEOR_SHOWERS = [
    {"name": "Quadrantids",       "peak_month": 1,  "peak_day": 3,  "zhr": 110, "duration_days": 4,
     "radiant_ra": 15.3, "radiant_dec": 49.7},
    {"name": "Lyrids",            "peak_month": 4,  "peak_day": 22, "zhr": 18,  "duration_days": 7,
     "radiant_ra": 18.1, "radiant_dec": 33.0},
    {"name": "Eta Aquariids",     "peak_month": 5,  "peak_day": 6,  "zhr": 50,  "duration_days": 10,
     "radiant_ra": 22.5, "radiant_dec": -1.0},
    {"name": "Delta Aquariids",   "peak_month": 7,  "peak_day": 30, "zhr": 25,  "duration_days": 14,
     "radiant_ra": 22.7, "radiant_dec": -16.4},
    {"name": "Perseids",          "peak_month": 8,  "peak_day": 12, "zhr": 100, "duration_days": 14,
     "radiant_ra": 3.2,  "radiant_dec": 58.0},
    {"name": "Draconids",         "peak_month": 10, "peak_day": 8,  "zhr": 10,  "duration_days": 4,
     "radiant_ra": 17.5, "radiant_dec": 54.0},
    {"name": "Orionids",          "peak_month": 10, "peak_day": 21, "zhr": 20,  "duration_days": 10,
     "radiant_ra": 6.3,  "radiant_dec": 15.6},
    {"name": "Leonids",           "peak_month": 11, "peak_day": 17, "zhr": 15,  "duration_days": 6,
     "radiant_ra": 10.1, "radiant_dec": 21.6},
    {"name": "Geminids",          "peak_month": 12, "peak_day": 14, "zhr": 150, "duration_days": 7,
     "radiant_ra": 7.5,  "radiant_dec": 32.6},
    {"name": "Ursids",            "peak_month": 12, "peak_day": 22, "zhr": 10,  "duration_days": 4,
     "radiant_ra": 14.5, "radiant_dec": 75.0},
]


def upcoming_meteor_showers(today: date, days_ahead: int = 90) -> list[dict]:
    end = today + timedelta(days=days_ahead)
    showers = []
    for s in METEOR_SHOWERS:
        for year in {today.year, today.year + 1}:
            try:
                peak = date(year, s["peak_month"], s["peak_day"])
            except ValueError:
                continue
            if today <= peak <= end:
                showers.append({
                    **s,
                    "peak_date": peak.isoformat(),
                    "active_start": (peak - timedelta(days=s["duration_days"] // 2)).isoformat(),
                    "active_end": (peak + timedelta(days=s["duration_days"] // 2)).isoformat(),
                })
    showers.sort(key=lambda s: s["peak_date"])
    return showers


def visible_planets(lat: float, lon: float, when: datetime) -> list[dict]:
    """Compute current altitude/azimuth for all naked-eye planets."""
    eph = get_ephemeris()
    ts = get_timescale()
    location = eph["earth"] + wgs84.latlon(lat, lon)
    t = ts.from_datetime(when.astimezone(timezone.utc))

    targets = [
        ("Mercury", "mercury"),
        ("Venus", "venus"),
        ("Mars", "mars"),
        ("Jupiter", "jupiter barycenter"),
        ("Saturn", "saturn barycenter"),
        ("Uranus", "uranus barycenter"),
        ("Neptune", "neptune barycenter"),
    ]

    results = []
    for name, key in targets:
        try:
            body = eph[key]
        except KeyError:
            continue
        app = location.at(t).observe(body).apparent()
        alt, az, dist = app.altaz()
        results.append({
            "name": name,
            "altitude_deg": round(float(alt.degrees), 1),
            "azimuth_deg": round(float(az.degrees), 1),
            "distance_au": round(float(dist.au), 3),
            "above_horizon": alt.degrees > 0,
        })
    return results
