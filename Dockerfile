# One image, one service: FastAPI serves both the API and the built React bundle. Same
# origin means no CORS, one URL to send a prospect, and one thing to deploy on a free tier.
#
# Note what is NOT installed: the `[geo]` extra (rasterio, xarray, scipy). Hazard rasters are
# converted offline by scripts/prepare_xws_footprints.py on a developer machine, which writes
# the result to the database — so the server never needs a geospatial stack, and the image
# stays small enough for a 512 MB instance.

# ---------------------------------------------------------------- frontend build
FROM node:22-alpine AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY engine/ ./engine/
COPY data/ ./data/
COPY backend/ ./backend/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir ".[api]"

COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 8000
# Render (and most free-tier hosts) inject $PORT.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
