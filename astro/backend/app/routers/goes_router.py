from fastapi import APIRouter, Query

from app.services.goes import (
    latest_image_url,
    list_animation_frames,
    list_bands,
    list_sectors,
)

router = APIRouter(prefix="/api/goes", tags=["goes"])


@router.get("/sectors")
def sectors():
    return {"sectors": list_sectors(), "bands": list_bands()}


@router.get("/latest")
def latest(sector: str = "conus", band: str = "GEOCOLOR", resolution: str | None = None):
    return {"url": latest_image_url(sector, band, resolution)}


@router.get("/animation")
async def animation(
    sector: str = "conus",
    band: str = "GEOCOLOR",
    resolution: str | None = None,
    limit: int = 12,
):
    frames = await list_animation_frames(sector, band, resolution, limit)
    return {"sector": sector, "band": band, "frames": frames}
