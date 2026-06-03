"""
인메모리 job 상태 저장소.
프로덕션에서는 Redis나 DB로 교체 가능.
"""
from typing import Any

_store: dict[str, dict[str, Any]] = {}


def create_job(job_id: str, data: dict) -> None:
    _store[job_id] = {"status": "created", **data}


def get_job(job_id: str) -> dict | None:
    return _store.get(job_id)


def update_job(job_id: str, data: dict) -> None:
    if job_id in _store:
        _store[job_id].update(data)


def list_jobs() -> list[dict]:
    return list(_store.values())
