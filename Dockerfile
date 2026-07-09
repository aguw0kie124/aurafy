# Aurafy — single-origin image: FastAPI serves the built Svelte app.

# Stage 1: build the frontend. PUBLIC_API_BASE_URL is empty so the app calls
# the API with relative URLs (same origin as the page).
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV PUBLIC_API_BASE_URL=""
RUN npm run build

# Stage 2: python runtime that serves both the API and the built frontend.
FROM python:3.13-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /frontend/dist ./frontend/dist

# Render (and most PaaS) inject $PORT; default to 5057 for local `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-5057}"]
