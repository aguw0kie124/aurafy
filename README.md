# Aurafy

If you're always getting bored of your playlists, this is for you.

Aurafy gives you a **For You** feed of new songs picked to match your Spotify
taste, plus a **Recap** of your recent listening. Anything it surfaces can be
saved straight to your Spotify account as a playlist.

## How it works

Spotify no longer exposes audio features to new apps, so Aurafy can't compare
songs by sound. Instead it compares them by text. Each track's title, artist,
album, and genres are embedded into a 768-dim vector with Gemini and stored in
Postgres using `pgvector`.

For the feed, your top artists and genres seed a discovery pool. Gemini
suggests artist and track names, live Spotify search resolves those into real
tracks, and new tracks get persisted and embedded, growing a shared catalog
over time. Candidates are then scored with a kNN taste-fit lookup against your
library's embeddings, blended with vibe similarity and popularity, and sliced
into feed rows and playlists.

The natural-language playlist builder runs the same pieces as a RAG pipeline.
It interprets the request, retrieves candidates with a pgvector ANN search and
a kNN rerank, and has Gemini curate and order the final list from that
retrieved set only. Returned track ids are validated against what was
retrieved, so the model can't hallucinate a track into the playlist.

Gemini is optional throughout. Without a key, both the feed and builder fall
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

## Deploy

The project deploys as a single Docker image (see [`Dockerfile`](Dockerfile) and
[`render.yaml`](render.yaml)) to Render, with FastAPI serving both the API and
the built frontend from one origin.
