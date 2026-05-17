from fastapi import APIRouter, Query

from app.services.weather import aggregate

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("")
async def weather(lat: float = Query(...), lon: float = Query(...)):
    return await aggregate(lat, lon)
