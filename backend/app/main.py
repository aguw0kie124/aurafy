from __future__ import annotations

import asyncio
import base64
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv()


def env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", "Frontend__Origin", default="http://127.0.0.1:5173")
SPOTIFY_CLIENT_ID = env("SPOTIFY_CLIENT_ID", "Spotify__ClientId")
SPOTIFY_CLIENT_SECRET = env("SPOTIFY_CLIENT_SECRET", "Spotify__ClientSecret")
SPOTIFY_REDIRECT_URI = env(
    "SPOTIFY_REDIRECT_URI",
    "Spotify__RedirectUri",
    default="http://127.0.0.1:5057/api/auth/spotify/callback",
)

SESSION_COOKIE = "Aurafy.Session"
STATE_COOKIE = "spotify_oauth_state"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_SCOPES = "user-read-recently-played user-top-read"
TOKEN_REFRESH_BUFFER_SECONDS = 60

app = FastAPI(title="Aurafy FastAPI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo-simple server-side sessions. They reset when uvicorn restarts.
sessions: dict[str, dict[str, Any]] = {}


def spotify_is_configured() -> bool:
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET and SPOTIFY_REDIRECT_URI)


def get_session(request: Request) -> dict[str, Any] | None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    return sessions.get(session_id)


def require_session(request: Request) -> dict[str, Any]:
    session = get_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def redirect_to_frontend(auth_error: str | None = None) -> RedirectResponse:
    origin = FRONTEND_ORIGIN.rstrip("/")
    target = origin if auth_error is None else f"{origin}/?auth_error={auth_error}"
    response = RedirectResponse(target)
    response.delete_cookie(STATE_COOKIE)
    return response


def basic_auth_header() -> str:
    credentials = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode("utf-8")
    return "Basic " + base64.b64encode(credentials).decode("ascii")


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            headers={"Authorization": basic_auth_header()},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Spotify token exchange failed")

    payload = response.json()
    if not payload.get("access_token"):
        raise HTTPException(status_code=502, detail="Spotify returned an invalid token response")
    return payload


async def refresh_access_token(session: dict[str, Any]) -> str:
    tokens = session["tokens"]
    if tokens["expires_at"] > time.time() + TOKEN_REFRESH_BUFFER_SECONDS:
        return tokens["access_token"]

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Spotify refresh token is missing")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            headers={"Authorization": basic_auth_header()},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Spotify token refresh failed")

    payload = response.json()
    tokens["access_token"] = payload["access_token"]
    tokens["refresh_token"] = payload.get("refresh_token") or refresh_token
    tokens["expires_at"] = time.time() + int(payload.get("expires_in", 3600))
    return tokens["access_token"]


async def spotify_get(
    client: httpx.AsyncClient,
    path: str,
    access_token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}{path}"
    for attempt in range(2):
        response = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
            retry_after = response.headers.get("Retry-After", "1")
            await asyncio.sleep(min(int(retry_after), 5) if retry_after.isdigit() else 1)
            continue

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Spotify request failed with {response.status_code}",
            )

        return response.json()

    raise HTTPException(status_code=502, detail="Spotify request failed after retry")


def normalize_range(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"medium_term", "medium", "6_months", "6months", "six_months"}:
        return "medium_term"
    if normalized in {"long_term", "long", "all_time", "alltime"}:
        return "long_term"
    return "short_term"


def select_image_url(images: list[dict[str, Any]] | None) -> str | None:
    if not images:
        return None
    ordered = sorted(
        images,
        key=lambda image: (image.get("width") or 0) * (image.get("height") or 0),
        reverse=True,
    )
    return next((image.get("url") for image in ordered if image.get("url")), None)


def spotify_external_url(item: dict[str, Any]) -> str | None:
    return (item.get("external_urls") or {}).get("spotify")


def artist_names(track: dict[str, Any]) -> str:
    names = [artist.get("name") for artist in track.get("artists", []) if artist.get("name")]
    return ", ".join(names) if names else "Unknown artist"


def to_track_response(track: dict[str, Any], rank: int) -> dict[str, Any]:
    album = track.get("album") or {}
    return {
        "spotifyTrackId": track.get("id"),
        "title": track.get("name") or "Unknown track",
        "artist": artist_names(track),
        "album": album.get("name") or "Unknown album",
        "coverUrl": select_image_url(album.get("images")),
        "externalUrl": spotify_external_url(track),
        "spotifyRank": rank,
        "source": "spotify",
    }


def to_artist_response(artist: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "spotifyArtistId": artist.get("id"),
        "name": artist.get("name") or "Unknown artist",
        "imageUrl": select_image_url(artist.get("images")),
        "externalUrl": spotify_external_url(artist),
        "spotifyRank": rank,
        "topTrackCount": 0,
        "source": "spotify",
    }


def build_albums(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    albums: dict[str, dict[str, Any]] = {}
    track_count = len(tracks)

    for index, track in enumerate(tracks):
        album = track.get("album") or {}
        title = album.get("name")
        if not title:
            continue

        artist = artist_names(track)
        key = album.get("id") or f"{title}|{artist}"
        score = track_count - index
        aggregate = albums.setdefault(
            key,
            {
                "spotifyAlbumId": album.get("id"),
                "title": title,
                "artist": artist,
                "coverUrl": select_image_url(album.get("images")),
                "externalUrl": spotify_external_url(album),
                "spotifyRank": 0,
                "topTrackCount": 0,
                "source": "spotify_derived",
                "_score": 0,
                "_bestRank": index + 1,
            },
        )
        aggregate["_score"] += score
        aggregate["topTrackCount"] += 1
        aggregate["_bestRank"] = min(aggregate["_bestRank"], index + 1)

    ranked = sorted(albums.values(), key=lambda album: (-album["_score"], album["_bestRank"], album["title"]))
    for rank, album in enumerate(ranked, start=1):
        album["spotifyRank"] = rank
        album.pop("_score", None)
        album.pop("_bestRank", None)
    return ranked


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_spotify_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_time_of_day(playbacks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    windows = {
        "Morning": 0,
        "Afternoon": 0,
        "Evening": 0,
        "Late night": 0,
    }

    for playback in playbacks:
        track = playback.get("track") or {}
        duration = int(track.get("duration_ms") or 0)
        played_at = parse_spotify_time(playback.get("played_at"))
        if played_at is None:
            continue

        hour = played_at.astimezone(timezone.utc).hour
        if 5 <= hour <= 11:
            windows["Morning"] += duration
        elif 12 <= hour <= 16:
            windows["Afternoon"] += duration
        elif 17 <= hour <= 21:
            windows["Evening"] += duration
        else:
            windows["Late night"] += duration

    total_ms = sum(windows.values())
    return [
        {
            "label": label,
            "value": round((duration / total_ms) * 100) if total_ms else 0,
            "listeningMinutes": round(duration / 60000),
        }
        for label, duration in windows.items()
    ]


async def fetch_recently_played(session: dict[str, Any]) -> list[dict[str, Any]]:
    access_token = await refresh_access_token(session)
    async with httpx.AsyncClient(timeout=20) as client:
        payload = await spotify_get(client, "/me/player/recently-played", access_token, {"limit": 50})
    items = payload.get("items") or []
    session["recently_played"] = items
    session["last_synced_at"] = utc_now_iso()
    return items


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "spotifyConfigured": spotify_is_configured()}


@app.get("/api/auth/me")
async def auth_me(request: Request) -> dict[str, Any]:
    session = get_session(request)
    if session is None:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": session["user"]}


@app.post("/api/auth/logout", status_code=204)
async def logout(request: Request) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        sessions.pop(session_id, None)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/auth/spotify/login")
async def spotify_login() -> RedirectResponse:
    if not spotify_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Spotify auth is not configured. Add SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI.",
        )

    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SPOTIFY_SCOPES,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "state": state,
    }
    response = RedirectResponse(f"{SPOTIFY_AUTH_URL}?{urlencode(params)}")
    response.set_cookie(STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600)
    return response


@app.get("/api/auth/spotify/callback")
async def spotify_callback(request: Request) -> RedirectResponse:
    returned_state = request.query_params.get("state")
    expected_state = request.cookies.get(STATE_COOKIE)

    if not returned_state or not expected_state or not secrets.compare_digest(returned_state, expected_state):
        return redirect_to_frontend("state_mismatch")

    if spotify_error := request.query_params.get("error"):
        return redirect_to_frontend(spotify_error)

    code = request.query_params.get("code")
    if not code:
        return redirect_to_frontend("missing_code")

    try:
        token_payload = await exchange_code_for_tokens(code)
        access_token = token_payload["access_token"]
        async with httpx.AsyncClient(timeout=20) as client:
            profile = await spotify_get(client, "/me", access_token)
    except HTTPException:
        return redirect_to_frontend("spotify_auth_failed")

    spotify_user_id = profile.get("id") or "spotify-user"
    display_name = profile.get("display_name") or spotify_user_id
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "user": {
            "spotifyUserId": spotify_user_id,
            "displayName": display_name,
            "imageUrl": select_image_url(profile.get("images")),
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": token_payload.get("refresh_token"),
            "expires_at": time.time() + int(token_payload.get("expires_in", 3600)),
        },
        "recently_played": [],
        "last_synced_at": None,
    }

    response = redirect_to_frontend()
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax", max_age=14 * 24 * 60 * 60)
    return response


@app.get("/api/spotify/top")
async def spotify_top(
    request: Request,
    range: str | None = None,
    limit: int = Query(50, ge=1, le=50),
) -> dict[str, Any]:
    session = require_session(request)
    normalized_range = normalize_range(range)
    access_token = await refresh_access_token(session)

    async with httpx.AsyncClient(timeout=20) as client:
        top_tracks, top_artists = await asyncio.gather(
            spotify_get(client, "/me/top/tracks", access_token, {"time_range": normalized_range, "limit": limit}),
            spotify_get(client, "/me/top/artists", access_token, {"time_range": normalized_range, "limit": limit}),
        )

    track_items = top_tracks.get("items") or []
    artist_items = top_artists.get("items") or []
    return {
        "range": normalized_range,
        "tracks": [to_track_response(track, index + 1) for index, track in enumerate(track_items)],
        "artists": [to_artist_response(artist, index + 1) for index, artist in enumerate(artist_items)],
        "albums": build_albums(track_items),
    }


@app.get("/api/stats/recap")
async def stats_recap(request: Request, range: str | None = None) -> dict[str, Any]:
    session = require_session(request)
    playbacks = session.get("recently_played") or await fetch_recently_played(session)
    valid_playbacks = [item for item in playbacks if item.get("track")]

    artist_duration: defaultdict[str, int] = defaultdict(int)
    artist_images: dict[str, str | None] = {}
    track_ids: set[str] = set()
    total_ms = 0
    last_played_at: str | None = None

    for playback in valid_playbacks:
        track = playback.get("track") or {}
        duration = int(track.get("duration_ms") or 0)
        total_ms += duration
        if track.get("id"):
            track_ids.add(track["id"])

        played_at = playback.get("played_at")
        if played_at and (last_played_at is None or played_at > last_played_at):
            last_played_at = played_at

        primary_artist = (track.get("artists") or [{}])[0]
        artist_name = primary_artist.get("name") or "Unknown artist"
        artist_duration[artist_name] += duration
        album_image = select_image_url((track.get("album") or {}).get("images"))
        artist_images.setdefault(artist_name, album_image)

    current_artist = None
    current_artist_image_url = None
    if artist_duration:
        current_artist = max(artist_duration.items(), key=lambda item: item[1])[0]
        current_artist_image_url = artist_images.get(current_artist)

    return {
        "summary": {
            "totalMinutes": round(total_ms / 60000),
            "artistsDiscovered": len(artist_duration),
            "currentArtist": current_artist,
            "currentRank": 1 if current_artist else None,
            "currentArtistImageUrl": current_artist_image_url,
            "totalPlays": len(valid_playbacks),
            "uniqueTracks": len(track_ids),
            "lastPlayedAt": last_played_at,
            "lastSyncedAt": session.get("last_synced_at"),
        },
        "timeOfDay": build_time_of_day(valid_playbacks),
    }


@app.post("/api/sync/spotify/recently-played")
async def sync_recently_played(
    request: Request,
    force: bool = False,
):
    session = require_session(request)
    sync_id = int(time.time() * 1000)
    started_at = utc_now_iso()

    try:
        items = await fetch_recently_played(session)
        return {
            "id": sync_id,
            "status": "completed",
            "fetchedCount": len(items),
            "insertedCount": len(items),
            "startedAt": started_at,
            "completedAt": utc_now_iso(),
            "errorMessage": None,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "id": sync_id,
                "status": "failed",
                "fetchedCount": 0,
                "insertedCount": 0,
                "startedAt": started_at,
                "completedAt": utc_now_iso(),
                "errorMessage": str(exc),
            },
        )
