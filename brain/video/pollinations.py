"""Free image and video generation via Pollinations.ai (no API key required)."""

import logging
import os
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://gen.pollinations.ai"


@dataclass
class PollinationsImageResult:
    success: bool
    image_path: str = ""
    error: str = ""


@dataclass
class PollinationsVideoResult:
    success: bool
    video_path: str = ""
    duration: float = 0.0
    error: str = ""


def generate_image(
    prompt: str,
    output_path: str = "",
    width: int = 1080,
    height: int = 1920,
    model: str = "flux",
    seed: int = -1,
) -> PollinationsImageResult:
    """Genera una imagen gratis con Pollinations.ai."""
    if not output_path:
        from config import MEDIA_DOWNLOAD_DIR
        out_dir = Path(MEDIA_DOWNLOAD_DIR) / "pollinations" / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"img_{int(time.time())}.jpg")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    encoded_prompt = urllib.parse.quote(prompt)
    params = {
        "width": width,
        "height": height,
        "model": model,
        "nologo": "true",
        "safe": "true",
    }
    if seed >= 0:
        params["seed"] = seed

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/image/{encoded_prompt}?{query}"

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type and len(resp.content) < 1000:
                return PollinationsImageResult(
                    success=False,
                    error=f"Respuesta no es imagen: {resp.text[:200]}",
                )

            with open(output_path, "wb") as f:
                f.write(resp.content)

        return PollinationsImageResult(success=True, image_path=output_path)

    except Exception as e:
        logger.error("Pollinations image falló: %s", e)
        return PollinationsImageResult(success=False, error=str(e))


def generate_video(
    prompt: str,
    output_path: str = "",
    duration: int = 5,
    aspect_ratio: str = "9:16",
    model: str = "seedance",
) -> PollinationsVideoResult:
    """Genera un video gratis con Pollinations.ai."""
    if not output_path:
        from config import MEDIA_DOWNLOAD_DIR
        out_dir = Path(MEDIA_DOWNLOAD_DIR) / "pollinations" / "videos"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"vid_{int(time.time())}.mp4")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    encoded_prompt = urllib.parse.quote(prompt)
    params = {
        "model": model,
        "duration": duration,
        "aspectRatio": aspect_ratio,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/video/{encoded_prompt}?{query}"

    try:
        with httpx.Client(timeout=300.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "video" not in content_type and len(resp.content) < 5000:
                return PollinationsVideoResult(
                    success=False,
                    error=f"Respuesta no es video: {resp.text[:200]}",
                )

            with open(output_path, "wb") as f:
                f.write(resp.content)

        actual_duration = _get_duration(output_path)
        return PollinationsVideoResult(
            success=True,
            video_path=output_path,
            duration=actual_duration or float(duration),
        )

    except Exception as e:
        logger.error("Pollinations video falló: %s", e)
        return PollinationsVideoResult(success=False, error=str(e))


def generate_scene_images(
    script: str,
    num_scenes: int = 4,
    width: int = 1080,
    height: int = 1920,
    model: str = "flux",
) -> list[str]:
    """Genera imágenes para las escenas de un guión usando Pollinations."""
    from inference_client import chat
    from config import OLLAMA_MODEL

    messages = [
        {"role": "system", "content": (
            "Sos un director de arte. Dado un guión de video, generá prompts descriptivos "
            "en inglés para generar imágenes que acompañen cada escena. "
            "Cada prompt debe ser visual, detallado y cinematográfico."
        )},
        {"role": "user", "content": (
            f"Generá exactamente {num_scenes} prompts de imágenes para este guión. "
            f"Respondé SOLO con los prompts, uno por línea, numerados (1. 2. 3. etc.):\n\n{script}"
        )},
    ]

    response = chat(messages, OLLAMA_MODEL)

    prompts = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            prompt = line.lstrip("0123456789.-) ").strip()
            if prompt:
                prompts.append(prompt)

    if not prompts:
        prompts = [f"Cinematic scene for video about: {script[:100]}"]

    image_paths = []
    for prompt in prompts[:num_scenes]:
        result = generate_image(prompt, width=width, height=height, model=model)
        if result.success:
            image_paths.append(result.image_path)

    return image_paths


def generate_scene_videos(
    script: str,
    num_scenes: int = 3,
    duration: int = 5,
    aspect_ratio: str = "9:16",
) -> list[str]:
    """Genera clips de video para las escenas de un guión usando Pollinations."""
    from inference_client import chat
    from config import OLLAMA_MODEL

    messages = [
        {"role": "system", "content": (
            "Sos un director de arte para videos. Dado un guión, generá prompts "
            "cortos y visuales en inglés para generar clips de video con IA. "
            "Cada prompt debe describir una escena cinematográfica de 5 segundos."
        )},
        {"role": "user", "content": (
            f"Generá exactamente {num_scenes} prompts de video para este guión. "
            f"Respondé SOLO con los prompts, uno por línea, numerados:\n\n{script}"
        )},
    ]

    response = chat(messages, OLLAMA_MODEL)

    prompts = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            prompt = line.lstrip("0123456789.-) ").strip()
            if prompt:
                prompts.append(prompt)

    if not prompts:
        prompts = [f"Cinematic b-roll about: {script[:100]}"]

    paths = []
    for prompt in prompts[:num_scenes]:
        result = generate_video(prompt, duration=duration, aspect_ratio=aspect_ratio)
        if result.success:
            paths.append(result.video_path)

    return paths


def _get_duration(file_path: str) -> float:
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0
