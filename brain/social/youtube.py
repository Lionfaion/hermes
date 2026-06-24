"""Publicación de videos en YouTube via Data API v3."""

import logging
import json
import mimetypes
from pathlib import Path

import httpx

from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, DATA_DIR

logger = logging.getLogger(__name__)

TOKEN_CACHE = DATA_DIR / "youtube_token.json"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"


def _get_access_token() -> str | None:
    if not YOUTUBE_REFRESH_TOKEN:
        return None

    if TOKEN_CACHE.exists():
        try:
            cached = json.loads(TOKEN_CACHE.read_text())
            if cached.get("access_token"):
                return cached["access_token"]
        except Exception:
            pass

    try:
        resp = httpx.post(TOKEN_URL, data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "refresh_token": YOUTUBE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        TOKEN_CACHE.write_text(json.dumps(data))
        return data.get("access_token")
    except Exception as e:
        logger.error("Error obteniendo access token de YouTube: %s", e)
        return None


def get_auth_url() -> str:
    params = {
        "client_id": YOUTUBE_CLIENT_ID,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{AUTH_URL}?{qs}"


def exchange_code(code: str) -> dict:
    resp = httpx.post(TOKEN_URL, data={
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    TOKEN_CACHE.write_text(json.dumps(data))
    return data


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    privacy: str = "private",
    category_id: str = "22",
) -> dict:
    token = _get_access_token()
    if not token:
        return {"error": "YouTube no configurado. Configurá YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET y YOUTUBE_REFRESH_TOKEN."}

    path = Path(video_path)
    if not path.exists():
        return {"error": f"Video no encontrado: {video_path}"}

    content_type = mimetypes.guess_type(str(path))[0] or "video/mp4"

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": (tags or [])[:500],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Resumable upload: init
        init_resp = httpx.post(
            UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={**headers, "Content-Type": "application/json"},
            content=json.dumps(metadata),
            timeout=30,
        )
        init_resp.raise_for_status()
        upload_url = init_resp.headers["Location"]

        # Upload the file
        file_size = path.stat().st_size
        with open(path, "rb") as f:
            upload_resp = httpx.put(
                upload_url,
                headers={
                    "Content-Type": content_type,
                    "Content-Length": str(file_size),
                },
                content=f,
                timeout=600,
            )
            upload_resp.raise_for_status()

        result = upload_resp.json()
        video_id = result.get("id", "")
        logger.info("Video subido a YouTube: %s", video_id)
        return {
            "success": True,
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "title": title,
            "privacy": privacy,
        }
    except Exception as e:
        logger.error("Error subiendo a YouTube: %s", e)
        return {"error": str(e)}
