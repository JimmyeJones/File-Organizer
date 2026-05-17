from fastapi import APIRouter, Query

from app.services.satellites import predict_passes

router = APIRouter(prefix="/api/satellites", tags=["satellites"])


@router.get("/passes")
async def passes(
    lat: float = Query(...),
    lon: float = Query(...),
    group: str = Query("stations"),
    hours: int = 24,
    min_altitude: float = 20.0,
):
    data = await predict_passes(lat, lon, group, hours, min_altitude)
    return {"count": len(data), "passes": data}
