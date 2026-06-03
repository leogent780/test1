import os
import httpx
from pathlib import Path
from app.config import HIGGSFIELD_TOKEN

BASE_URL = "https://fnf.higgsfield.ai"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {HIGGSFIELD_TOKEN}",
        "Accept": "application/json",
    }


def _create_media() -> str:
    """새 미디어 ID 생성 → UUID 반환"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE_URL}/video", headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        # 응답에서 id 필드 추출 (키 이름이 다를 수 있음)
        return data.get("id") or data.get("media_id") or data.get("uuid")


def _upload_file(media_id: str, file_path: str) -> str:
    """파일 업로드 → CloudFront URL 반환"""
    path = Path(file_path)
    mime = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"
    headers = _headers()

    # Step 1: 업로드 요청 (force check payload)
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{BASE_URL}/video/{media_id}/upload",
            headers=headers,
            json={"force_nsfw_check": True, "force_ip_check": True},
        )
        resp.raise_for_status()
        upload_info = resp.json()

    # Step 2: 실제 파일 PUT (presigned URL이 있는 경우)
    upload_url = upload_info.get("upload_url") or upload_info.get("url")
    if upload_url:
        with open(file_path, "rb") as f:
            data = f.read()
        with httpx.Client(timeout=120) as client:
            resp = client.put(upload_url, content=data, headers={"Content-Type": mime})
            resp.raise_for_status()

    # CloudFront URL 반환
    cdn_url = (
        upload_info.get("cdn_url")
        or upload_info.get("cloudfront_url")
        or upload_info.get("media_url")
        or upload_info.get("url")
        or f"https://cdn.higgsfield.ai/{media_id}"
    )
    return cdn_url


def upload_video(file_path: str) -> str:
    media_id = _create_media()
    return _upload_file(media_id, file_path)


def upload_image(file_path: str) -> str:
    media_id = _create_media()
    return _upload_file(media_id, file_path)


def submit_job(clip_url: str, image_url: str, prompt: str, duration: int = 5) -> str:
    """Higgsfield seedance 2.0 job 제출 → job_id 반환"""
    payload = {
        "prompt": prompt,
        "video_url": clip_url,
        "image_url": image_url,
        "duration": duration,
        "resolution": "480p",
        "aspect_ratio": "9:16",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{BASE_URL}/jobs/v2/seedance_2_0",
            headers={**_headers(), "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("id") or data.get("job_id")


def check_status(job_id: str) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{BASE_URL}/jobs/{job_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return {"status": data.get("status", "unknown"), "job_id": job_id, "raw": data}


def get_result(job_id: str) -> str:
    """완료된 job에서 결과 영상 URL 반환"""
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{BASE_URL}/jobs/{job_id}", headers=_headers())
        resp.raise_for_status()
        data = resp.json()
    return (
        data.get("output_url")
        or data.get("video_url")
        or data.get("result", {}).get("url")
        or data.get("result", {}).get("video_url")
    )


def get_clip_duration(clip_path: str) -> int:
    import subprocess, json
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", clip_path
    ], capture_output=True, text=True)
    info = json.loads(result.stdout)
    secs = float(info["format"]["duration"])
    return max(4, min(15, round(secs)))


def submit_all_clips(clips: list[dict], product_image_path: str) -> list[dict]:
    image_url = upload_image(product_image_path)
    for clip in clips:
        clip_url = upload_video(clip["clip_path"])
        duration = get_clip_duration(clip["clip_path"])
        job_id = submit_job(clip_url, image_url, clip["prompt"], duration)
        clip["request_id"] = job_id
        clip["output_status"] = "queued"
    return clips
