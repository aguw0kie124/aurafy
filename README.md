## Aurafy

Aurafy is a Spotify listening stats app for seeing your music habits throughout the year instead of waiting for Wrapped.

## Tech Stack

- Frontend: Svelte + Vite
- Backend: ASP.NET Core
- Database: PostgreSQL (Supabase)

## Run Locally

1. Setup Spotify Developer App

   - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an app.
   - Set the Redirect URI to `http://127.0.0.1:5057/api/auth/spotify/callback`.
   - Copy your Client ID and Client Secret.

2. Setup Environment Variables

   - Create .env and copy `.env.example`.
   - Add your Spotify Client ID and Client Secret.
   - For Supabase, add your Postgres connection string (in key-value format) to `.env`:
     ```text
     ConnectionStrings__Postgres=Host=db.<project-ref>.supabase.co;Port=5432;Database=postgres;Username=postgres;Password=<database-password>;SSL Mode=Require;Trust Server Certificate=true
     ```
   - Run `db/dbschema.sql` in the Supabase SQL editor.

3. Run the Frontend

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Run the Backend

   ```bash
   dotnet run --project backend/Statify.Api --launch-profile http
   ```

5. Open the app

   ```text
   http://127.0.0.1:5173
   ```
