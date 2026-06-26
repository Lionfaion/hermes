"""B-Roll generation via Replicate (Seedance) with local fallback."""

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
SEEDANCE_MODEL = os.getenv("SEEDANCE_MODEL", "seedance-2-lite")


@dataclass
class BrollResult:
    success: bool
    video_path: str = ""
    duration: float = 0.0
    source: str = ""
    error: str = ""


def generate_broll_replicate(
    prompt: str,
    output_path: str = "",
    duration: int = 5,
    aspect_ratio: str = "9:16",
    seed: int = -1,
) -> BrollResult:
    """Genera un clip de b-roll usando Seedance 2.0 via Replicate."""
    if not REPLICATE_API_TOKEN:
        return BrollResult(
            success=False,
            error="REPLICATE_API_TOKEN no configurada",
        )

    try:
        import replicate
    except ImportError:
        return BrollResult(success=False, error="replicate no instalado: pip install replicate")

    if not output_path:
        from config import MEDIA_DOWNLOAD_DIR
        out_dir = Path(MEDIA_DOWNLOAD_DIR) / "broll"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"broll_{int(time.time())}.mp4")

    try:
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

        input_data = {
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }
        if seed >= 0:
            input_data["seed"] = seed

        output = replicate.run(
            f"bytedance/{SEEDANCE_MODEL}",
            input=input_data,
        )

        if hasattr(output, "read"):
            video_bytes = output.read()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(video_bytes)
        elif isinstance(output, str) and output.startswith("http"):
            import urllib.request
            urllib.request.urlretrieve(output, output_path)
        else:
            return BrollResult(success=False, error=f"Formato de output inesperado: {type(output)}")

        return BrollResult(
            success=True,
            video_path=output_path,
            duration=float(duration),
            source="replicate_seedance",
        )

    except Exception as e:
        logger.error("Replicate Seedance falló: %s", e)
        return BrollResult(success=False, error=str(e))


def generate_broll_local(
    topic: str,
    output_path: str = "",
    num_frames: int = 90,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
) -> BrollResult:
    """Genera b-roll local con animaciones procedurales (fallback sin API)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return BrollResult(success=False, error="Pillow no instalado: pip install Pillow")

    import subprocess
    import math
    import tempfile

    if not output_path:
        from config import MEDIA_DOWNLOAD_DIR
        out_dir = Path(MEDIA_DOWNLOAD_DIR) / "broll"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"broll_local_{int(time.time())}.mp4")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i in range(num_frames):
                img = Image.new("RGB", (width, height), (15, 15, 25))
                draw = ImageDraw.Draw(img)

                t = i / num_frames
                phase = t * math.pi * 4

                for j in range(8):
                    y_base = height * (j + 1) / 9
                    amplitude = 40 + j * 10
                    points = []
                    for x in range(0, width, 4):
                        y = y_base + math.sin(x * 0.01 + phase + j * 0.5) * amplitude
                        points.append((x, y))
                    if len(points) > 1:
                        r = min(255, 40 + j * 25)
                        g = min(255, 80 + j * 15)
                        b = min(255, 180 + j * 10)
                        alpha = max(40, 200 - j * 20)
                        draw.line(points, fill=(r, g, b, alpha), width=2)

                cx, cy = width // 2, height // 3
                radius = 60 + math.sin(phase * 0.5) * 20
                draw.ellipse(
                    [cx - radius, cy - radius, cx + radius, cy + radius],
                    outline=(100, 150, 255),
                    width=3,
                )

                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                except Exception:
                    font = ImageFont.load_default()

                words = topic.split()[:4]
                text = " ".join(words).upper()
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                draw.text(
                    ((width - tw) // 2, height // 2),
                    text,
                    fill=(255, 255, 255),
                    font=font,
                )

                frame_path = Path(tmp_dir) / f"frame_{i:04d}.png"
                img.save(str(frame_path))

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(Path(tmp_dir) / "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                output_path,
            ]
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)

        duration = num_frames / fps
        return BrollResult(
            success=True,
            video_path=output_path,
            duration=duration,
            source="local_procedural",
        )

    except Exception as e:
        logger.error("B-roll local falló: %s", e)
        return BrollResult(success=False, error=str(e))


def generate_scene_broll(
    script: str,
    num_scenes: int = 3,
    aspect_ratio: str = "9:16",
    use_replicate: bool = True,
) -> list[str]:
    """Genera múltiples clips de b-roll para las escenas de un guión."""
    from inference_client import chat
    from config import OLLAMA_MODEL

    messages = [
        {"role": "system", "content": (
            "Sos un director de arte para videos. Dado un guión, generá prompts "
            "cortos y visuales en inglés para generar clips de b-roll con IA. "
            "Cada prompt debe describir una escena cinematográfica de 5 segundos."
        )},
        {"role": "user", "content": (
            f"Generá exactamente {num_scenes} prompts de b-roll para este guión. "
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
        if use_replicate and REPLICATE_API_TOKEN:
            result = generate_broll_replicate(prompt, aspect_ratio=aspect_ratio)
        else:
            result = generate_broll_local(prompt)

        if result.success:
            paths.append(result.video_path)

    return paths
