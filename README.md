# Statify

Statify is a year-round Spotify recap app. It pairs Spotify's rolling top-items data with a first-party listening-history pipeline so users can see useful previews immediately and richer long-term stats after connecting.

## Stack

- `frontend/`: SvelteKit app for the dashboard and recap experience
- `backend/Statify.Api/`: ASP.NET Core API for auth, sync orchestration, and stats endpoints
- `supabase/migrations/`: PostgreSQL schema intended for Supabase
- `docs/`: product and architecture notes

## Local start

1. Copy `.env.example` into your preferred secret store or shell environment.
2. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

3. Start the API:

   ```bash
   dotnet run --project backend/Statify.Api --launch-profile http
   ```

4. Start the frontend:

   ```bash
   cd frontend
   npm run dev
   ```

## What exists now

- Product shell with dashboard, artists, songs, albums, genres, and recap routes
- API health, metadata, preview stats, and manual refresh endpoints
- Hosted background worker scaffold for periodic sync
- Initial PostgreSQL schema for users, tokens, play events, sync runs, and daily aggregates
- Roadmap for moving from scaffold to real Spotify-backed behavior

## Next build target

Implement Spotify authorization, persist encrypted refresh tokens, and replace preview fixtures with live `/me/top/{type}` and `/me/player/recently-played` pulls.
