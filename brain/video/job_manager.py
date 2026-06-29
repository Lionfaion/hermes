"""Video job state persistence: tracks pipeline runs with intermediate artifacts."""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from config import MEDIA_DOWNLOAD_DIR

logger = logging.getLogger(__name__)

JOBS_DIR = Path(MEDIA_DOWNLOAD_DIR) / "video_jobs"


@dataclass
class VideoJob:
    job_id: str
    stage: str = "intake"
    status: str = "pending"
    topic: str = ""
    script: str = ""
    config: dict = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)
    steps_completed: list[str] = field(default_factory=list)
    error: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


def _job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file(job_id: str) -> Path:
    return _job_dir(job_id) / "state.json"


def create_job(topic: str, config: dict = None) -> VideoJob:
    job_id = f"video_{int(time.time())}_{hash(topic) % 10000:04d}"
    now = time.time()
    job = VideoJob(
        job_id=job_id,
        topic=topic,
        config=config or {},
        created_at=now,
        updated_at=now,
    )
    save_job(job)
    logger.info("Video job creado: %s", job_id)
    return job


def save_job(job: VideoJob):
    job.updated_at = time.time()
    state_path = _state_file(job.job_id)
    with open(state_path, "w") as f:
        json.dump(asdict(job), f, indent=2)


def load_job(job_id: str) -> VideoJob | None:
    state_path = _state_file(job_id)
    if not state_path.exists():
        return None
    try:
        with open(state_path) as f:
            data = json.load(f)
        return VideoJob(**data)
    except Exception as e:
        logger.error("Error cargando job %s: %s", job_id, e)
        return None


def update_stage(job: VideoJob, stage: str, status: str = "in_progress"):
    job.stage = stage
    job.status = status
    save_job(job)


def add_artifact(job: VideoJob, artifact_type: str, path: str, metadata: dict = None):
    job.artifacts.append({
        "type": artifact_type,
        "path": path,
        "metadata": metadata or {},
        "timestamp": time.time(),
    })
    save_job(job)


def complete_step(job: VideoJob, step: str):
    job.steps_completed.append(step)
    save_job(job)


def fail_job(job: VideoJob, error: str):
    job.status = "failed"
    job.error = error
    save_job(job)


def complete_job(job: VideoJob):
    job.status = "completed"
    job.stage = "done"
    save_job(job)


def list_jobs(limit: int = 20) -> list[VideoJob]:
    if not JOBS_DIR.exists():
        return []
    jobs = []
    for d in sorted(JOBS_DIR.iterdir(), reverse=True):
        if d.is_dir():
            job = load_job(d.name)
            if job:
                jobs.append(job)
            if len(jobs) >= limit:
                break
    return jobs


def get_job_dir(job_id: str) -> str:
    return str(_job_dir(job_id))
