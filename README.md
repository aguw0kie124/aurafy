# Aurafy

A "For You" feed and playlist curator for Spotify. Aurafy learns your taste, finds distinct
listening modes in your library, and surfaces new songs matching each one —
plus a Recap of what you've been playing. Anything it finds can be saved
straight back to Spotify as a playlist.

## Features

- **For You feed** — one row per distinct taste mode in your library, filled
  with new tracks that match it
- **Recap** — a look back at your recent listening
- **Playlist builder** — describe what you want in plain English, get a
  playlist back
- **One-click save** — turn any row or generated playlist into a real
  Spotify playlist

## Setup

1. **Create a Spotify app** in the [developer dashboard](https://developer.spotify.com/dashboard)
   - Redirect URI: `http://127.0.0.1:5057/api/auth/spotify/callback`
   - Under **User Management**, add your own Spotify email (dev-mode apps
     only allow added users to log in)

2. **Create a Supabase project** (free tier works), then run
   [`db/dbschema.sql`](db/dbschema.sql) in the SQL editor. Grab the **Session
   pooler** connection string.

3. **Configure environment variables** — copy `.env.example` to `.env` and
   fill in your Spotify credentials, `SUPABASE_DB_URL`, and a
   `TOKEN_ENCRYPTION_KEY` (see the file for the one-liner to generate one). A
   `GEMINI_API_KEY` is optional but recommended — get one free from
   [Google AI Studio](https://aistudio.google.com/apikey).

4. **Run the backend**
   ```bash
   cd backend
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 127.0.0.1 --port 5057
   ```

5. **Run the frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. Open [http://127.0.0.1:5173](http://127.0.0.1:5173) and sign in with Spotify.

## Environment Variables

| Variable               | Required | Description                              |
| ----------------------- | -------- | ----------------------------------------- |
| `SPOTIFY_CLIENT_ID`     | Yes      | From your Spotify app                     |
| `SPOTIFY_CLIENT_SECRET` | Yes      | From your Spotify app                     |
| `SUPABASE_DB_URL`       | Yes      | Session pooler connection string          |
| `TOKEN_ENCRYPTION_KEY`  | Yes      | Encrypts stored Spotify tokens at rest    |
| `GEMINI_API_KEY`        | No       | Enables AI-generated recs; falls back to a deterministic taste-ranked sort without it |

## Technologies Used

- **Frontend:** Svelte, Vite, TypeScript
- **Backend:** FastAPI (Python)
- **Database:** Supabase Postgres with `pgvector` (HNSW index)
- **Embeddings:** Google Gemini `gemini-embedding-001`
- **Generation:** Gemini `gemini-3.6-flash`, grounded and constrained to
  retrieved candidates only
- **Clustering:** scikit-learn k-means for taste-mode detection
- **Auth:** Spotify OAuth via an HTTP-only session cookie

## Deploy

Ships as a single Docker image ([`Dockerfile`](Dockerfile),
[`render.yaml`](render.yaml)) — FastAPI serves the API and the built
frontend from one origin.
