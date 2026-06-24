"""Integración con Google Calendar API v3."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from config import DATA_DIR

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = DATA_DIR / "google_credentials.json"
CALENDAR_TOKEN_FILE = DATA_DIR / "google_calendar_token.json"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPES = "https://www.googleapis.com/auth/calendar"


def _load_credentials() -> dict | None:
    if not CREDENTIALS_FILE.exists():
        return None
    data = json.loads(CREDENTIALS_FILE.read_text())
    return data.get("installed", data.get("web", data))


def _get_access_token() -> str | None:
    if not CALENDAR_TOKEN_FILE.exists():
        return None
    token_data = json.loads(CALENDAR_TOKEN_FILE.read_text())
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return token_data.get("access_token")

    creds = _load_credentials()
    if not creds:
        return None

    try:
        resp = httpx.post(TOKEN_URL, data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)
        resp.raise_for_status()
        new_data = resp.json()
        new_data["refresh_token"] = refresh_token
        CALENDAR_TOKEN_FILE.write_text(json.dumps(new_data))
        return new_data["access_token"]
    except Exception as e:
        logger.error("Error refreshing calendar token: %s", e)
        return None


def _headers() -> dict:
    token = _get_access_token()
    if not token:
        raise RuntimeError("Google Calendar no autenticado. Ejecutá el flujo OAuth primero.")
    return {"Authorization": f"Bearer {token}"}


def get_auth_url() -> str:
    creds = _load_credentials()
    if not creds:
        return "Error: no se encontró google_credentials.json en brain/data/"
    params = {
        "client_id": creds["client_id"],
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"


def exchange_code(code: str) -> dict:
    creds = _load_credentials()
    resp = httpx.post(TOKEN_URL, data={
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    CALENDAR_TOKEN_FILE.write_text(json.dumps(data))
    return data


def get_events_today() -> str:
    return _get_events_range(0, 1, "Hoy")


def get_events_week() -> str:
    return _get_events_range(0, 7, "Esta semana")


def _get_events_range(offset_days: int, span_days: int, label: str) -> str:
    now = datetime.now()
    start = (now + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0)
    end = start + timedelta(days=span_days)

    try:
        resp = httpx.get(
            f"{CALENDAR_API}/calendars/primary/events",
            headers=_headers(),
            params={
                "timeMin": start.isoformat() + "Z",
                "timeMax": end.isoformat() + "Z",
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 20,
            },
            timeout=30,
        )
        resp.raise_for_status()
        events = resp.json().get("items", [])

        if not events:
            return f"**{label}:** No hay eventos programados."

        lines = [f"**{label}:**"]
        for ev in events:
            start_dt = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
            summary = ev.get("summary", "Sin título")
            try:
                t = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                time_str = t.strftime("%H:%M")
            except Exception:
                time_str = start_dt
            lines.append(f"- {time_str} — {summary}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error obteniendo eventos: {e}"


def create_event(
    title: str,
    date: str = "",
    time: str = "",
    duration_minutes: int = 60,
    description: str = "",
) -> str:
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    if not time:
        time = "09:00"

    start = datetime.fromisoformat(f"{date}T{time}:00")
    end = start + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
        "end": {"dateTime": end.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
    }

    try:
        resp = httpx.post(
            f"{CALENDAR_API}/calendars/primary/events",
            headers={**_headers(), "Content-Type": "application/json"},
            json=event_body,
            timeout=30,
        )
        resp.raise_for_status()
        ev = resp.json()
        return f"Evento creado: **{title}** el {date} a las {time} ({duration_minutes} min)"
    except Exception as e:
        return f"Error creando evento: {e}"


def delete_event(event_id: str) -> str:
    try:
        resp = httpx.delete(
            f"{CALENDAR_API}/calendars/primary/events/{event_id}",
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return f"Evento {event_id} eliminado."
    except Exception as e:
        return f"Error eliminando evento: {e}"
