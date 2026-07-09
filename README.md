## Aurafy

Aurafy is a Spotify playlist builder that uses Gemini AI to generate personalized playlists based on your listening history and mood preferences.

### Features

- AI-powered playlist generation using Gemini API based on your listening history and preferences
- Full-stack web app built with FastAPI backend and Svelte/TypeScript frontend
- Spotify OAuth authentication and real-time data integration via Spotify Web API

## Tech Stack

- Frontend: Svelte + Vite
- Backend: FastAPI
- Auth: Spotify OAuth with an HTTP-only session cookie
- AI: Gemini API for playlist generation and personalized recommendations

## Run Locally

1. Setup Spotify Developer App

   - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an app.
   - Set the Redirect URI to `http://127.0.0.1:5057/api/auth/spotify/callback`.
   - Copy your Client ID and Client Secret.

2. Setup Environment Variables

   - Create `.env` from `.env.example`.
   - Add your Spotify Client ID and Client Secret.

3. Run the Backend

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 127.0.0.1 --port 5057
   ```

4. Run the Frontend

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. Open the app

   ```text
   http://127.0.0.1:5173
   ```

## Deploy (Render, single origin)

The whole app ships as one Docker image: FastAPI serves the API **and** the
built Svelte frontend from the same origin, so the session cookie works with no
CORS setup. Supabase stays as-is (it's already hosted).

1. **Push to GitHub**, then in Render: **New → Blueprint** and select the repo.
   Render reads [`render.yaml`](render.yaml) and builds the [`Dockerfile`](Dockerfile).

2. **Set the secret env vars** (all marked `sync:false`, so you enter them once
   in the dashboard):
   - `FRONTEND_ORIGIN` — your service URL, e.g. `https://aurafy.onrender.com`
     (this also flips cookies to `Secure` because it starts with `https`).
   - `SPOTIFY_REDIRECT_URI` — `https://<your-service>.onrender.com/api/auth/spotify/callback`.
   - `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`.
   - `SUPABASE_DB_URL` — the Supabase **Session pooler** connection string.
   - `TOKEN_ENCRYPTION_KEY` — **must match** the key that encrypted existing
     tokens, or every stored login breaks.
   - `GEMINI_API_KEY` — optional (AI modes); the builder works without it.

3. **In the Spotify dashboard**, add the same `SPOTIFY_REDIRECT_URI` to the
   app's Redirect URIs (Spotify requires HTTPS for non-localhost).

4. Deploy. Render health-checks `/health`.

Notes:
- Spotify apps stay in **development mode** until granted extended quota — only
  users you add under the app's User Management can log in (max 25).
- The Render **free plan sleeps after ~15 min idle**; the first request then
  cold-starts (~30–60s). A paid instance or an uptime pinger avoids this.
- Build the frontend with `PUBLIC_API_BASE_URL=""` (the Dockerfile does this) so
  it calls the API with same-origin relative URLs.
