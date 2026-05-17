# AstroPlanner

A dockerized astrophotography planning web app: multi-source weather, ranked
deep-sky targets for tonight, live GOES satellite imagery, ISS/satellite pass
predictions, planet positions, meteor shower calendar, and persistent site
profiles.

## Quick start

```bash
cd astro
docker compose up --build
```

Then open <http://localhost:8000>.

The first request after startup downloads JPL ephemeris (~17 MB) into the
`astro-data` Docker volume; subsequent boots reuse it.

## Configuration

| Env var          | Default          | Purpose                                |
|------------------|------------------|----------------------------------------|
| `ASTRO_PORT`     | `8000`           | Host port mapped to the container      |
| `ASTRO_DATA_DIR` | `/data`          | Where ephemeris + saved sites are kept |

Set them in a `.env` file next to `docker-compose.yml`, e.g.:

```env
ASTRO_PORT=9000
```

## What's inside

### Backend (`backend/`)

- FastAPI, Skyfield for ephemeris, httpx for upstream calls
- Endpoints:
  - `GET /api/astro/sun-moon?lat=&lon=&date=`
  - `GET /api/astro/planets?lat=&lon=`
  - `GET /api/astro/meteor-showers`
  - `GET /api/weather?lat=&lon=` — aggregates Open-Meteo + 7Timer + NWS
  - `GET /api/targets?lat=&lon=&date=&min_altitude=&type_filter=&limit=`
  - `GET /api/targets/{id}/altitude-curve?lat=&lon=&date=`
  - `GET /api/goes/sectors` / `GET /api/goes/latest` / `GET /api/goes/animation`
  - `GET /api/satellites/passes?lat=&lon=&group=stations|visual|starlink`
  - `GET|POST|DELETE /api/sites`

### Frontend (`frontend/`)

Vanilla HTML/CSS/JS — no build step. Served from the FastAPI container at `/`.
Uses Chart.js + Leaflet via CDN. Tabs:

- **Tonight** — at-a-glance summary, moon, twilight timeline, cloud + seeing charts, top targets
- **Weather** — side-by-side source cards, temperature/dew point chart, wind chart
- **Targets** — ranked catalog with filters and per-target altitude curve
- **Sky View** — live GOES imagery with animated cloud loops across sectors/bands
- **Satellites** — upcoming ISS / bright sat / Starlink passes, visibility-flagged
- **Events** — naked-eye planet positions, upcoming meteor showers (next 90 days)
- **Sites** — saved observing sites with map picker, switchable from the topbar

## Data sources (all no-auth, free)

- Open-Meteo (weather)
- 7Timer! Astro (seeing, transparency, cloud cover)
- NWS api.weather.gov (US-only official forecast)
- NOAA STAR CDN (GOES-18/19 imagery)
- Celestrak (TLE data for satellite passes)
- JPL DE421 (ephemeris, downloaded on first start)

## Skipped (for future)

- Phone-camera AR sky scanner for horizon obstructions — would need a native
  mobile shell and was intentionally deferred. The data model in
  `app/services/sites.py` already includes a `horizon_profile` field so this
  can be added later without backend changes.
