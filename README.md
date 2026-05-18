## Aurafy

Aurafy is a Spotify listening stats app for seeing your music habits throughout the year instead of waiting for Wrapped.

## Tech Stack

- Frontend: SvelteKit
- Backend: ASP.NET Core
- Database: PostgreSQL (Supabase)

## Run Locally

1. Add environment values from `.env.example`.
2. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

3. Start the backend:

   ```bash
   dotnet run --project backend/Statify.Api --launch-profile http
   ```

4. Start the frontend:

   ```bash
   cd frontend
   npm run dev
   ```

5. Open the app:

   ```text
   http://127.0.0.1:5173
   ```
