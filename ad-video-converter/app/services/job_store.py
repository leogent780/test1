import json
from pathlib import Path
from typing import Any
from app.config import BASE_DIR

_JOBS_DIR = BASE_DIR / "uploads" / "jobs"
_JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _path(job_id: str) -> Path:
    return _JOBS_DIR / f"{job_id}.json"


def create_job(job_id: str, data: dict) -> None:
    job = {"status": "created", **data}
    _path(job_id).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")


def get_job(job_id: str) -> dict | None:
    p = _path(job_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def update_job(job_id: str, data: dict) -> None:
    p = _path(job_id)
    if not p.exists():
        return
    job = json.loads(p.read_text(encoding="utf-8"))
    job.update(data)
    p.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")


def list_jobs() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in _JOBS_DIR.glob("*.json")]
