"""Astronomical calculations using Skyfield.

Centralizes ephemeris loading and provides helpers for sun/moon position,
twilight times, and altitude/azimuth conversions for sky targets.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from skyfield import almanac
from skyfield.api import Loader, Star, wgs84

from app.config import settings

_loader: Loader | None = None
_ephemeris = None
_timescale = None


def _ensure_loader() -> Loader:
    global _loader
    if _loader is None:
        eph_dir = settings.data_dir / "ephemeris"
        eph_dir.mkdir(parents=True, exist_ok=True)
        _loader = Loader(str(eph_dir))
    return _loader


def get_ephemeris():
    global _ephemeris
    if _ephemeris is None:
        loader = _ensure_loader()
        _ephemeris = loader(settings.ephemeris_file)
    return _ephemeris


def get_timescale():
    global _timescale
    if _timescale is None:
        loader = _ensure_loader()
        _timescale = loader.timescale()
    return _timescale


@dataclass
class TwilightEvents:
    sunset: datetime | None
    civil_dusk: datetime | None
    nautical_dusk: datetime | None
    astronomical_dusk: datetime | None
    astronomical_dawn: datetime | None
    nautical_dawn: datetime | None
    civil_dawn: datetime | None
    sunrise: datetime | None

    def to_dict(self) -> dict:
        return {
            "sunset": _iso(self.sunset),
            "civil_dusk": _iso(self.civil_dusk),
            "nautical_dusk": _iso(self.nautical_dusk),
            "astronomical_dusk": _iso(self.astronomical_dusk),
            "astronomical_dawn": _iso(self.astronomical_dawn),
            "nautical_dawn": _iso(self.nautical_dawn),
            "civil_dawn": _iso(self.civil_dawn),
            "sunrise": _iso(self.sunrise),
        }


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _night_window(target_date: date) -> tuple[datetime, datetime]:
    """Window centered on local night: noon UTC of target_date → noon UTC next day.

    Good enough for finding twilight events for the upcoming night across
    most longitudes when paired with a sensible local date.
    """
    start = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
    end = start + timedelta(days=1, hours=12)
    start = start - timedelta(hours=12)
    return start, end


def compute_twilight(lat: float, lon: float, target_date: date) -> TwilightEvents:
    eph = get_ephemeris()
    ts = get_timescale()
    location = wgs84.latlon(lat, lon)

    start, end = _night_window(target_date)
    t0 = ts.from_datetime(start)
    t1 = ts.from_datetime(end)

    # almanac.dark_twilight_day returns 0-4 for darkness levels
    f = almanac.dark_twilight_day(eph, location)
    times, events = almanac.find_discrete(t0, t1, f)

    # Sequence: transitions in order through the window.
    sunset = civil_dusk = nautical_dusk = astro_dusk = None
    astro_dawn = nautical_dawn = civil_dawn = sunrise = None

    prev_state = None
    for t, e in zip(times, events):
        dt = t.utc_datetime()
        if prev_state is not None:
            # Transition from prev_state -> e
            if prev_state == 4 and e == 3:
                sunset = dt
            elif prev_state == 3 and e == 2:
                civil_dusk = dt
            elif prev_state == 2 and e == 1:
                nautical_dusk = dt
            elif prev_state == 1 and e == 0:
                astro_dusk = dt
            elif prev_state == 0 and e == 1:
                astro_dawn = dt
            elif prev_state == 1 and e == 2:
                nautical_dawn = dt
            elif prev_state == 2 and e == 3:
                civil_dawn = dt
            elif prev_state == 3 and e == 4:
                sunrise = dt
        prev_state = e

    return TwilightEvents(
        sunset=sunset,
        civil_dusk=civil_dusk,
        nautical_dusk=nautical_dusk,
        astronomical_dusk=astro_dusk,
        astronomical_dawn=astro_dawn,
        nautical_dawn=nautical_dawn,
        civil_dawn=civil_dawn,
        sunrise=sunrise,
    )


def moon_info(lat: float, lon: float, when: datetime) -> dict:
    eph = get_ephemeris()
    ts = get_timescale()
    location = eph["earth"] + wgs84.latlon(lat, lon)
    t = ts.from_datetime(when.astimezone(timezone.utc))

    moon = eph["moon"]
    sun = eph["sun"]

    astrometric = location.at(t).observe(moon).apparent()
    alt, az, _ = astrometric.altaz()

    # Phase: separation between sun and moon as seen from earth
    e = eph["earth"].at(t)
    s = e.observe(sun).apparent()
    m = e.observe(moon).apparent()
    phase_angle = s.separation_from(m).degrees
    illumination = (1 - math.cos(math.radians(phase_angle))) / 2

    # Rise/set on the day containing `when`
    day = when.date()
    start = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    t0 = ts.from_datetime(start)
    t1 = ts.from_datetime(end)
    f = almanac.risings_and_settings(eph, moon, wgs84.latlon(lat, lon))
    times, kinds = almanac.find_discrete(t0, t1, f)
    rise = next((t.utc_datetime() for t, k in zip(times, kinds) if k == 1), None)
    setting = next((t.utc_datetime() for t, k in zip(times, kinds) if k == 0), None)

    return {
        "altitude_deg": float(alt.degrees),
        "azimuth_deg": float(az.degrees),
        "phase_angle_deg": float(phase_angle),
        "illumination_fraction": float(illumination),
        "phase_name": _phase_name(phase_angle, when, eph, ts),
        "rise": _iso(rise),
        "set": _iso(setting),
    }


def _phase_name(phase_angle: float, when: datetime, eph, ts) -> str:
    # Determine waxing vs waning by comparing illumination to a few hours later
    later = when + timedelta(hours=6)
    t_now = ts.from_datetime(when.astimezone(timezone.utc))
    t_later = ts.from_datetime(later.astimezone(timezone.utc))
    sun = eph["sun"]
    moon = eph["moon"]
    e = eph["earth"]
    a_now = e.at(t_now).observe(sun).apparent().separation_from(
        e.at(t_now).observe(moon).apparent()
    ).degrees
    a_later = e.at(t_later).observe(sun).apparent().separation_from(
        e.at(t_later).observe(moon).apparent()
    ).degrees
    waxing = a_later > a_now

    if phase_angle < 10:
        return "New Moon"
    if phase_angle > 170:
        return "Full Moon"
    if phase_angle < 80:
        return "Waxing Crescent" if waxing else "Waning Crescent"
    if phase_angle < 100:
        return "First Quarter" if waxing else "Last Quarter"
    return "Waxing Gibbous" if waxing else "Waning Gibbous"


def altaz_for_target(
    ra_hours: float,
    dec_deg: float,
    lat: float,
    lon: float,
    when: datetime,
) -> tuple[float, float]:
    eph = get_ephemeris()
    ts = get_timescale()
    location = eph["earth"] + wgs84.latlon(lat, lon)
    star = Star(ra_hours=ra_hours, dec_degrees=dec_deg)
    t = ts.from_datetime(when.astimezone(timezone.utc))
    alt, az, _ = location.at(t).observe(star).apparent().altaz()
    return float(alt.degrees), float(az.degrees)


def altitude_curve(
    ra_hours: float,
    dec_deg: float,
    lat: float,
    lon: float,
    start: datetime,
    end: datetime,
    step_minutes: int = 15,
) -> list[dict]:
    eph = get_ephemeris()
    ts = get_timescale()
    location = eph["earth"] + wgs84.latlon(lat, lon)
    star = Star(ra_hours=ra_hours, dec_degrees=dec_deg)

    n = int((end - start).total_seconds() / (step_minutes * 60)) + 1
    times = [start + timedelta(minutes=step_minutes * i) for i in range(n)]
    t = ts.from_datetimes([dt.astimezone(timezone.utc) for dt in times])
    alt, az, _ = location.at(t).observe(star).apparent().altaz()
    return [
        {"t": times[i].isoformat(), "alt": float(alt.degrees[i]), "az": float(az.degrees[i])}
        for i in range(n)
    ]


def moon_separation_for_target(
    ra_hours: float, dec_deg: float, lat: float, lon: float, when: datetime
) -> float:
    eph = get_ephemeris()
    ts = get_timescale()
    location = eph["earth"] + wgs84.latlon(lat, lon)
    star = Star(ra_hours=ra_hours, dec_degrees=dec_deg)
    t = ts.from_datetime(when.astimezone(timezone.utc))
    a_star = location.at(t).observe(star).apparent()
    a_moon = location.at(t).observe(eph["moon"]).apparent()
    return float(a_star.separation_from(a_moon).degrees)
