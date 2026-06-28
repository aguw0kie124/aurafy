## Aurafy

Aurafy is a Spotify listening stats app for seeing your music habits throughout the year instead of waiting for Wrapped.

## Tech Stack

- Frontend: Svelte + Vite
- Backend: FastAPI
- Auth: Spotify OAuth with an HTTP-only session cookie

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
