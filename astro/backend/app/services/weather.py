"""Multi-source weather aggregation tailored for astrophotography.

Sources (all free, no API key required):
  - Open-Meteo: hourly cloud cover, temperature, humidity, wind, dew point
  - 7Timer! Astro: seeing, transparency, cloud cover (astronomy-specific)
  - US NWS (api.weather.gov): official US forecast hourly grid
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings


async def _http_get_json(client: httpx.AsyncClient, url: str, **kwargs: Any) -> dict:
    r = await client.get(url, timeout=settings.request_timeout, **kwargs)
    r.raise_for_status()
    return r.json()


async def fetch_open_meteo(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "cloud_cover",
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "visibility",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "precipitation",
            "precipitation_probability",
        ]),
        "forecast_days": 3,
        "timezone": "UTC",
    }
    try:
        data = await _http_get_json(client, url, params=params)
    except Exception as e:
        return {"source": "open-meteo", "ok": False, "error": str(e)}

    h = data.get("hourly", {})
    times = h.get("time", [])
    hourly = []
    for i, t in enumerate(times):
        hourly.append({
            "time": t + "+00:00" if not t.endswith("Z") else t,
            "temperature_c": _get(h, "temperature_2m", i),
            "humidity_pct": _get(h, "relative_humidity_2m", i),
            "dew_point_c": _get(h, "dew_point_2m", i),
            "cloud_cover_pct": _get(h, "cloud_cover", i),
            "cloud_cover_low_pct": _get(h, "cloud_cover_low", i),
            "cloud_cover_mid_pct": _get(h, "cloud_cover_mid", i),
            "cloud_cover_high_pct": _get(h, "cloud_cover_high", i),
            "visibility_m": _get(h, "visibility", i),
            "wind_speed_kmh": _get(h, "wind_speed_10m", i),
            "wind_gusts_kmh": _get(h, "wind_gusts_10m", i),
            "wind_dir_deg": _get(h, "wind_direction_10m", i),
            "precip_mm": _get(h, "precipitation", i),
            "precip_prob_pct": _get(h, "precipitation_probability", i),
        })

    return {
        "source": "open-meteo",
        "ok": True,
        "label": "Open-Meteo",
        "hourly": hourly,
    }


async def fetch_7timer(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    url = "https://www.7timer.info/bin/api.pl"
    params = {
        "lon": lon,
        "lat": lat,
        "product": "astro",
        "output": "json",
    }
    try:
        data = await _http_get_json(client, url, params=params)
    except Exception as e:
        return {"source": "7timer", "ok": False, "error": str(e)}

    init_str = data.get("init")
    if not init_str:
        return {"source": "7timer", "ok": False, "error": "no init time"}

    init = datetime.strptime(init_str, "%Y%m%d%H").replace(tzinfo=timezone.utc)

    hourly = []
    for entry in data.get("dataseries", []):
        t = init + timedelta(hours=entry["timepoint"])
        cc_octa = entry.get("cloudcover")  # 1-9, 1=clear 9=overcast
        seeing = entry.get("seeing")  # 1-8, 1=excellent 8=bad
        transparency = entry.get("transparency")  # 1-8
        hourly.append({
            "time": t.isoformat(),
            "cloud_cover_pct": _octa_to_pct(cc_octa),
            "seeing_index": seeing,
            "seeing_label": _seeing_label(seeing),
            "transparency_index": transparency,
            "transparency_label": _transparency_label(transparency),
            "humidity_pct": _rh_index_to_pct(entry.get("rh2m")),
            "temperature_c": entry.get("temp2m"),
            "wind_speed_kmh": _wind_index_to_kmh(entry.get("wind10m", {}).get("speed")),
            "precip_type": entry.get("prec_type"),
        })

    return {
        "source": "7timer",
        "ok": True,
        "label": "7Timer! Astro",
        "hourly": hourly,
    }


async def fetch_nws(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    """US National Weather Service. Only works for US locations."""
    try:
        points = await _http_get_json(
            client,
            f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
            headers={"User-Agent": settings.user_agent, "Accept": "application/geo+json"},
        )
        forecast_url = points["properties"]["forecastHourly"]
        forecast = await _http_get_json(
            client,
            forecast_url,
            headers={"User-Agent": settings.user_agent, "Accept": "application/geo+json"},
        )
    except Exception as e:
        return {"source": "nws", "ok": False, "error": str(e)}

    hourly = []
    for p in forecast.get("properties", {}).get("periods", []):
        hourly.append({
            "time": p.get("startTime"),
            "temperature_c": _f_to_c(p.get("temperature")) if p.get("temperatureUnit") == "F" else p.get("temperature"),
            "humidity_pct": (p.get("relativeHumidity") or {}).get("value"),
            "dew_point_c": (p.get("dewpoint") or {}).get("value"),
            "wind_speed_kmh": _parse_wind(p.get("windSpeed")),
            "wind_dir": p.get("windDirection"),
            "precip_prob_pct": (p.get("probabilityOfPrecipitation") or {}).get("value"),
            "short_forecast": p.get("shortForecast"),
        })

    return {
        "source": "nws",
        "ok": True,
        "label": "NWS (US)",
        "hourly": hourly,
    }


async def aggregate(lat: float, lon: float) -> dict:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            fetch_open_meteo(client, lat, lon),
            fetch_7timer(client, lat, lon),
            fetch_nws(client, lat, lon),
            return_exceptions=True,
        )

    sources = []
    for r in results:
        if isinstance(r, Exception):
            sources.append({"ok": False, "error": str(r)})
        else:
            sources.append(r)

    consensus = _build_consensus(sources)
    return {
        "lat": lat,
        "lon": lon,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "consensus": consensus,
    }


# Fields that must not be naively averaged across sources (e.g. circular
# quantities like wind direction, where mean(350°, 10°) would be 180°).
_NON_AVERAGEABLE = {"wind_dir_deg"}


def _build_consensus(sources: list[dict]) -> list[dict]:
    """Merge all sources into one hourly consensus series.

    Times from different sources use different offsets (Open-Meteo/7Timer are
    UTC; NWS is local-with-offset), so normalize every timestamp to a UTC hour
    before bucketing. For each hour bucket, average numeric fields across the
    sources that provide them.
    """
    bucket: dict[str, dict[str, list[float]]] = {}
    for src in sources:
        if not src.get("ok"):
            continue
        for h in src.get("hourly", []):
            t = h.get("time")
            if not t:
                continue
            hour_key = _utc_hour_key(t)
            if hour_key is None:
                continue
            b = bucket.setdefault(hour_key, {})
            for k, v in h.items():
                if k == "time" or v is None or k in _NON_AVERAGEABLE:
                    continue
                if isinstance(v, (int, float)):
                    b.setdefault(k, []).append(float(v))

    consensus = []
    for hour_key in sorted(bucket.keys()):
        b = bucket[hour_key]
        entry = {"time": hour_key + ":00:00+00:00"}
        for k, vals in b.items():
            entry[k] = round(sum(vals) / len(vals), 2)
        consensus.append(entry)
    return consensus


def _utc_hour_key(t: str) -> str | None:
    """Parse an ISO timestamp (any offset) and return its UTC 'YYYY-MM-DDTHH'."""
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def _get(h: dict, key: str, idx: int):
    arr = h.get(key)
    if arr is None or idx >= len(arr):
        return None
    return arr[idx]


def _octa_to_pct(octa: int | None) -> float | None:
    if octa is None:
        return None
    # 7timer uses 1-9 buckets representing 0-6%..94-100% cloud cover.
    mapping = {1: 6, 2: 19, 3: 31, 4: 44, 5: 56, 6: 69, 7: 81, 8: 94, 9: 100}
    return float(mapping.get(int(octa), 0))


def _seeing_label(s: int | None) -> str | None:
    if s is None:
        return None
    labels = {1: "<0.5\"", 2: "0.5\"-0.75\"", 3: "0.75\"-1\"", 4: "1\"-1.25\"",
              5: "1.25\"-1.5\"", 6: "1.5\"-2\"", 7: "2\"-2.5\"", 8: ">2.5\""}
    return labels.get(int(s))


def _transparency_label(t: int | None) -> str | None:
    if t is None:
        return None
    labels = {1: "<0.3", 2: "0.3-0.4", 3: "0.4-0.5", 4: "0.5-0.6",
              5: "0.6-0.7", 6: "0.7-0.85", 7: "0.85-1.0", 8: ">1.0"}
    return labels.get(int(t))


def _rh_index_to_pct(idx) -> float | None:
    if idx is None:
        return None
    # 7timer rh2m is a coded string like "-4", "0", "4" etc.
    mapping = {"-4": 5, "-3": 10, "-2": 17, "-1": 27, "0": 40, "1": 55,
               "2": 70, "3": 82, "4": 95}
    return float(mapping.get(str(idx), 50))


def _wind_index_to_kmh(idx: int | None) -> float | None:
    if idx is None:
        return None
    # 1: <0.3m/s, 2: 0.3-3.4, 3: 3.4-8, 4: 8-10.8, 5: 10.8-17.2, 6: 17.2-24.5, 7: 24.5-32.6, 8: >32.6
    mapping = {1: 0.5, 2: 7, 3: 21, 4: 34, 5: 50, 6: 75, 7: 102, 8: 130}
    return float(mapping.get(int(idx), 0))


def _f_to_c(f) -> float | None:
    if f is None:
        return None
    return round((f - 32) * 5 / 9, 1)


def _parse_wind(s: str | None) -> float | None:
    if not s:
        return None
    # "10 mph" or "5 to 10 mph"
    parts = s.split()
    nums = [int(p) for p in parts if p.isdigit()]
    if not nums:
        return None
    mph = sum(nums) / len(nums)
    return round(mph * 1.609, 1)
