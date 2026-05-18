FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Build context is the astro/ project root, so paths are relative to it.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download ephemeris at BUILD time so no internet access is needed at runtime.
# Stored inside the image; sites data (user content) stays on a volume.
RUN python3 -c "\
import urllib.request, os, sys; \
os.makedirs('/ephemeris', exist_ok=True); \
url = 'https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp'; \
print('Downloading JPL de421.bsp (~17 MB)...', flush=True); \
urllib.request.urlretrieve(url, '/ephemeris/de421.bsp'); \
size = os.path.getsize('/ephemeris/de421.bsp'); \
print(f'Ephemeris ready: {size // 1024 // 1024} MB', flush=True) \
"

COPY backend/app ./app
COPY frontend /frontend

RUN mkdir -p /data/sites
ENV ASTRO_DATA_DIR=/data \
    ASTRO_EPHEMERIS_DIR=/ephemeris

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
