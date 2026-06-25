"""Generación de imágenes y videos con Google AI (Imagen / Veo)."""

import base64
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
GOOGLE_AI_IMAGE_MODEL = os.getenv("GOOGLE_AI_IMAGE_MODEL", "imagen-3.0-generate-002")
GOOGLE_AI_VIDEO_MODEL = os.getenv("GOOGLE_AI_VIDEO_MODEL", "veo-2.0-generate-001")


@dataclass
class ImageResult:
    success: bool
    image_path: str = ""
    error: str = ""


@dataclass
class VideoResult:
    success: bool
    video_path: str = ""
    duration: float = 0.0
    error: str = ""


def _get_client():
    """Obtiene el cliente de Google GenAI."""
    if not GOOGLE_AI_API_KEY:
        raise RuntimeError(
            "GOOGLE_AI_API_KEY no configurada. "
            "Obtenela en https://aistudio.google.com/apikey"
        )
    try:
        from google import genai
        return genai.Client(api_key=GOOGLE_AI_API_KEY)
    except ImportError:
        raise RuntimeError("google-genai no instalado. Ejecutá: pip install google-genai")


def generate_image(
    prompt: str,
    output_path: str = "",
    aspect_ratio: str = "9:16",
    number_of_images: int = 1,
) -> list[ImageResult]:
    """Genera imágenes con Google Imagen."""
    try:
        client = _get_client()
    except RuntimeError as e:
        return [ImageResult(success=False, error=str(e))]

    if not output_path:
        from config import MEDIA_DOWNLOAD_DIR
        output_dir = Path(MEDIA_DOWNLOAD_DIR) / "google_ai" / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = client.models.generate_images(
            model=GOOGLE_AI_IMAGE_MODEL,
            prompt=prompt,
            config={
                "number_of_images": number_of_images,
                "aspect_ratio": aspect_ratio,
            },
        )

        results = []
        for i, image in enumerate(response.generated_images):
            if output_path and number_of_images == 1:
                img_path = output_path
            else:
                img_path = str(output_dir / f"imagen_{int(time.time())}_{i}.png")

            image.image.save(img_path)
            results.append(ImageResult(success=True, image_path=img_path))
            logger.info("Imagen generada: %s", img_path)

        return results if results else [ImageResult(success=False, error="No se generaron imágenes")]

    except Exception as e:
        logger.error("Google Imagen falló: %s", e)
        return [ImageResult(success=False, error=str(e))]


def generate_video(
    prompt: str,
    output_path: str = "",
    aspect_ratio: str = "9:16",
    reference_image_path: str = "",
) -> VideoResult:
    """Genera un video con Google Veo."""
    try:
        client = _get_client()
    except RuntimeError as e:
        return VideoResult(success=False, error=str(e))

    if not output_path:
        from config import MEDIA_DOWNLOAD_DIR
        output_dir = Path(MEDIA_DOWNLOAD_DIR) / "google_ai" / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"video_{int(time.time())}.mp4")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        from google.genai import types

        config = {"aspect_ratio": aspect_ratio}

        if reference_image_path and Path(reference_image_path).exists():
            with open(reference_image_path, "rb") as f:
                img_bytes = f.read()
            image = types.Image(image_bytes=img_bytes)
            operation = client.models.generate_videos(
                model=GOOGLE_AI_VIDEO_MODEL,
                prompt=prompt,
                image=image,
                config=config,
            )
        else:
            operation = client.models.generate_videos(
                model=GOOGLE_AI_VIDEO_MODEL,
                prompt=prompt,
                config=config,
            )

        # Polling hasta que el video esté listo
        max_wait = 300
        waited = 0
        poll_interval = 10
        while not operation.done and waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval
            operation = client.operations.get(operation)
            logger.info("Generando video... (%ds)", waited)

        if not operation.done:
            return VideoResult(success=False, error=f"Timeout después de {max_wait}s esperando generación de video")

        if operation.response and operation.response.generated_videos:
            video = operation.response.generated_videos[0]
            video.video.save(output_path)
            logger.info("Video generado: %s", output_path)

            duration = 0.0
            try:
                import subprocess
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", output_path],
                    capture_output=True, text=True, timeout=10,
                )
                duration = float(result.stdout.strip())
            except Exception:
                pass

            return VideoResult(success=True, video_path=output_path, duration=duration)

        return VideoResult(success=False, error="No se generó ningún video")

    except Exception as e:
        logger.error("Google Veo falló: %s", e)
        return VideoResult(success=False, error=str(e))


def generate_scene_images(script: str, num_scenes: int = 4, aspect_ratio: str = "9:16") -> list[str]:
    """Genera imágenes para las escenas de un guión.

    Divide el guión en segmentos y genera una imagen para cada uno.
    Retorna lista de paths a las imágenes generadas.
    """
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
    for i, prompt in enumerate(prompts[:num_scenes]):
        results = generate_image(prompt, aspect_ratio=aspect_ratio, number_of_images=1)
        for r in results:
            if r.success:
                image_paths.append(r.image_path)

    return image_paths
