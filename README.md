## Aurafy

Aurafy is a Spotify listening stats app for seeing your music habits throughout the year instead of waiting for Wrapped.

## Tech Stack

- Frontend: Svelte + Vite
- Backend: ASP.NET Core
- Database: PostgreSQL (Supabase)

## Run Locally

1. Add environment values from `.env.example`.

   For Supabase, copy a Postgres connection string from Project Settings -> Database -> Connection string and set:

   ```bash
   ConnectionStrings__Postgres="Host=...;Port=6543;Database=postgres;Username=postgres.<project-ref>;Password=...;SSL Mode=Require;Trust Server Certificate=true"
   ```

   Then run `supabase/migrations/0001_initial_schema.sql` in the Supabase SQL editor if the tables are not already created.

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
