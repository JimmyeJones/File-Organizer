"""Target ranking for tonight's imaging session.

Scores deep-sky catalog entries by:
  - peak altitude during astronomical darkness
  - visibility window length above min altitude
  - moon separation (penalty when close to a bright moon)
  - magnitude (brighter = more accessible)
  - object type match against requested filter
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.data.catalog import get_catalog
from app.services import astronomy


NARROWBAND_TYPES = {"Emission Nebula", "Planetary Nebula", "Supernova Remnant"}
WIDEFIELD_TYPES = NARROWBAND_TYPES | {"Star Cloud", "Reflection Nebula", "Dark Nebula"}
GALAXY_TYPES = {"Galaxy"}
CLUSTER_TYPES = {"Open Cluster", "Globular Cluster"}


def rank_targets(
    lat: float,
    lon: float,
    target_date,
    min_altitude: float = 30.0,
    type_filter: str | None = None,
    limit: int = 25,
) -> dict:
    twilight = astronomy.compute_twilight(lat, lon, target_date)

    # Window: astronomical dusk → astronomical dawn (fall back if not present)
    start = twilight.astronomical_dusk or twilight.nautical_dusk or twilight.sunset
    end = twilight.astronomical_dawn or twilight.nautical_dawn or twilight.sunrise
    if start is None or end is None:
        # Polar conditions — fall back to a fixed window centered on local midnight
        start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=22)
        end = start + timedelta(hours=8)
    if end <= start:
        end = start + timedelta(hours=8)

    # Sample times across the dark window
    step = timedelta(minutes=20)
    n_steps = max(2, int((end - start) / step))
    sample_times = [start + i * step for i in range(n_steps + 1)]
    midpoint = start + (end - start) / 2

    moon_at_mid = astronomy.moon_info(lat, lon, midpoint)
    moon_alt_mid = moon_at_mid["altitude_deg"]
    moon_illum = moon_at_mid["illumination_fraction"]
    moon_is_up = moon_alt_mid > 0

    results = []
    catalog = get_catalog()
    if type_filter:
        catalog = [c for c in catalog if _matches_filter(c["type"], type_filter)]

    for obj in catalog:
        altitudes = []
        for t in sample_times:
            alt, _ = astronomy.altaz_for_target(obj["ra"], obj["dec"], lat, lon, t)
            altitudes.append(alt)

        peak_alt = max(altitudes)
        if peak_alt < min_altitude:
            continue

        hours_visible = sum(1 for a in altitudes if a >= min_altitude) * (step.total_seconds() / 3600)
        peak_idx = altitudes.index(peak_alt)
        peak_time = sample_times[peak_idx]

        moon_sep = astronomy.moon_separation_for_target(
            obj["ra"], obj["dec"], lat, lon, peak_time
        )

        score = _score(
            peak_alt=peak_alt,
            hours_visible=hours_visible,
            moon_sep=moon_sep,
            moon_illum=moon_illum,
            moon_is_up=moon_is_up,
            obj_type=obj["type"],
            magnitude=obj["mag"],
        )

        results.append({
            **obj,
            "peak_altitude_deg": round(peak_alt, 1),
            "peak_time": peak_time.isoformat(),
            "hours_above_min": round(hours_visible, 1),
            "moon_separation_deg": round(moon_sep, 1),
            "score": round(score, 2),
            "notes": _notes(obj["type"], moon_illum, moon_is_up, moon_sep),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "moon_at_midpoint": moon_at_mid,
        "count": len(results),
        "targets": results[:limit],
    }


def _matches_filter(obj_type: str, filter_name: str) -> bool:
    f = filter_name.lower()
    if f == "narrowband":
        return obj_type in NARROWBAND_TYPES
    if f == "widefield":
        return obj_type in WIDEFIELD_TYPES
    if f == "galaxies":
        return obj_type in GALAXY_TYPES
    if f == "clusters":
        return obj_type in CLUSTER_TYPES
    if f == "nebulae":
        return "Nebula" in obj_type
    return True


def _score(
    *,
    peak_alt: float,
    hours_visible: float,
    moon_sep: float,
    moon_illum: float,
    moon_is_up: bool,
    obj_type: str,
    magnitude: float,
) -> float:
    # Altitude: 30°=0.4, 60°=0.8, 90°=1.0
    alt_score = min(1.0, peak_alt / 90.0 + 0.1)
    # Hours visible: 1=0.1, 4=0.6, 8+=1.0
    hours_score = min(1.0, hours_visible / 8.0)
    # Magnitude: brighter is easier, but not the main driver
    mag_score = max(0.0, 1.0 - (magnitude - 4) / 12)

    base = alt_score * 0.45 + hours_score * 0.35 + mag_score * 0.20

    # Moon penalty: applies only when moon is up
    if moon_is_up and moon_illum > 0.2:
        moon_factor = moon_illum  # 0..1
        # Larger separation → smaller penalty
        sep_relief = min(1.0, moon_sep / 90.0)
        # Narrowband targets less affected by moonlight
        type_resilience = 0.4 if obj_type in NARROWBAND_TYPES else 1.0
        penalty = 0.25 * moon_factor * (1 - sep_relief) * type_resilience
        base = max(0.0, base - penalty)

    return base * 100


def _notes(obj_type: str, moon_illum: float, moon_is_up: bool, moon_sep: float) -> list[str]:
    notes = []
    if moon_is_up and moon_illum > 0.5:
        if obj_type in NARROWBAND_TYPES:
            notes.append("Good narrowband target despite bright moon")
        elif obj_type in GALAXY_TYPES:
            notes.append("Bright moon will degrade galaxy contrast")
    if moon_is_up and moon_sep < 30:
        notes.append(f"Moon within {moon_sep:.0f}° — expect glare")
    if obj_type == "Planetary Nebula":
        notes.append("Small target — long focal length preferred")
    if obj_type == "Galaxy":
        notes.append("Faint extended detail — needs dark skies")
    return notes
