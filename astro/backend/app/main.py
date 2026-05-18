from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    astro_router,
    goes_router,
    sats_router,
    sites_router,
    skyview_router,
    targets_router,
    weather_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load ephemeris so the first request isn't slow.
    # Non-fatal: if ephemeris is missing the server still starts;
    # astronomy endpoints will return 503 until it becomes available.
    import logging
    from app.services.astronomy import get_ephemeris, get_timescale
    try:
        get_timescale()
        get_ephemeris()
        logging.info("Ephemeris loaded OK")
    except Exception as exc:
        logging.warning("Ephemeris not available at startup: %s", exc)
    yield


app = FastAPI(
    title="AstroPlanner",
    version="0.1.0",
    description="Astrophotography planning: weather, targets, GOES, sites.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(astro_router.router)
app.include_router(weather_router.router)
app.include_router(targets_router.router)
app.include_router(goes_router.router)
app.include_router(sats_router.router)
app.include_router(sites_router.router)
app.include_router(skyview_router.router)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "astro-planner"}


# Static frontend — try container path first, then local dev path.
def _find_frontend() -> Path | None:
    candidates = [
        Path("/frontend"),
        Path(__file__).parent.parent.parent / "frontend",
    ]
    for c in candidates:
        if c.exists() and (c / "index.html").exists():
            return c
    return None


FRONTEND_DIR = _find_frontend()
if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
