# Aurafy

If you're always getting bored of your playlists, this is for you.

Aurafy gives you a **For You** feed of new songs picked to match your Spotify
taste, plus a **Recap** of your recent listening. Anything it surfaces can be
saved straight to your Spotify account as a playlist.

## How it works

Spotify no longer exposes audio features to new apps, so Aurafy can't compare
songs by sound. Instead it compares them by **text** — title, artist, album,
genres — embedded into 768-dim vectors with Gemini and stored in Postgres via
`pgvector`.

For the feed: your top artists/genres seed a discovery pool (Gemini suggests
names → live Spotify search resolves them to real tracks → new tracks are
persisted and embedded, growing a shared catalog). Candidates are then scored
by a **kNN taste-fit** against your library's embeddings, blended with vibe
similarity and popularity, and sliced into rows/playlists.

The natural-language playlist builder runs the same pieces as a **RAG**
pipeline: interpret the request → retrieve candidates (pgvector ANN + kNN
rerank) → have Gemini curate/order the final list *from that retrieved set
only*. Returned track ids are validated against what was retrieved, so the
model can't hallucinate a track into the playlist.

Gemini is optional throughout — without a key, both the feed and builder fall
back to a deterministic taste-ranked sort instead of LLM curation.

## Tech stack

- **Frontend:** Svelte + Vite (TypeScript)
- **Backend:** FastAPI (Python)
- **Database:** Supabase Postgres with the `pgvector` extension for storing and
  searching embeddings
- **Auth:** Spotify OAuth, with a server-side session behind an HTTP-only cookie;
  Spotify tokens are encrypted at rest
- **AI:** Google Gemini for both embeddings and the natural-language layer

## Run it locally

**You'll need:** Python 3.11+, Node 18+, a Supabase project (free tier is fine),
and a Spotify developer app. A Gemini key is optional.

1. **Create a Spotify app**
   - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an app.
   - Set the Redirect URI to `http://127.0.0.1:5057/api/auth/spotify/callback`.
   - Copy your Client ID and Client Secret.
   - Under **User Management**, add your own Spotify email (dev-mode apps only let
     users you've added log in).

2. **Set up the database**
   - Create a Supabase project.
   - Open the SQL editor and run [`db/dbschema.sql`](db/dbschema.sql) once.
   - Grab the **Session pooler** connection string for `SUPABASE_DB_URL`.

3. **Set environment variables**
   - Copy `.env.example` to `.env` and fill it in: Spotify client ID/secret,
     `SUPABASE_DB_URL`, a `TOKEN_ENCRYPTION_KEY` (the file shows the one-liner to
     generate one), and optionally `GEMINI_API_KEY`
     (free from [Google AI Studio](https://aistudio.google.com/apikey)).

4. **Run the backend**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 127.0.0.1 --port 5057
   ```

5. **Run the frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Open** [http://127.0.0.1:5173](http://127.0.0.1:5173) and sign in with Spotify.

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
   - `GEMINI_API_KEY` — optional (AI modes); the feed and builder work without it.

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
