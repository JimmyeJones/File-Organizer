from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.data.catalog import find_by_id, get_catalog
from app.services import astronomy
from app.services.targets import rank_targets

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.get("")
def targets(
    lat: float = Query(...),
    lon: float = Query(...),
    date_str: str | None = Query(None, alias="date"),
    min_altitude: float = 30.0,
    type_filter: str | None = None,
    limit: int = 25,
):
    target_date = date.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    return rank_targets(lat, lon, target_date, min_altitude, type_filter, limit)


@router.get("/catalog")
def catalog():
    return {"count": len(get_catalog()), "objects": get_catalog()}


@router.get("/{obj_id}/altitude-curve")
def altitude_curve(
    obj_id: str,
    lat: float = Query(...),
    lon: float = Query(...),
    date_str: str | None = Query(None, alias="date"),
    step_minutes: int = 15,
):
    obj = find_by_id(obj_id)
    if not obj:
        raise HTTPException(404, f"Object {obj_id} not found")

    target_date = date.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    twilight = astronomy.compute_twilight(lat, lon, target_date)
    start = twilight.sunset or datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = twilight.sunrise or (start + __import__("datetime").timedelta(hours=14))
    curve = astronomy.altitude_curve(obj["ra"], obj["dec"], lat, lon, start, end, step_minutes)
    return {
        "object": obj,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "twilight": twilight.to_dict(),
        "curve": curve,
    }
