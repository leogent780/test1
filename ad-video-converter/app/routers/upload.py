import uuid
import re
import shutil
import httpx
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.config import DIRS
from app.services.scene_detector import detect_scenes, split_clips
from app.services.job_store import create_job, update_job, get_job

router = APIRouter(prefix="/api", tags=["upload"])


def _safe_filename(filename: str) -> str:
    """한글/특수문자를 제거하고 영숫자+확장자만 남김"""
    ext = Path(filename).suffix
    name = re.sub(r'[^\w]', '_', Path(filename).stem, flags=re.ASCII)
    name = re.sub(r'_+', '_', name).strip('_') or 'file'
    return f"{name}{ext}"


@router.post("/upload")
async def upload_files(
    reference_video: UploadFile = File(...),
    product_description: str = Form(...),
    mode: str = Form("product"),
    product_image: UploadFile = File(None),
):
    job_id = str(uuid.uuid4())[:8]

    ref_path = DIRS["reference"] / f"{job_id}_{_safe_filename(reference_video.filename)}"
    with open(ref_path, "wb") as f:
        shutil.copyfileobj(reference_video.file, f)

    prod_path = None
    if mode == "product" and product_image and product_image.filename:
        prod_path = DIRS["product"] / f"{job_id}_{_safe_filename(product_image.filename)}"
        with open(prod_path, "wb") as f:
            shutil.copyfileobj(product_image.file, f)

    create_job(job_id, {
        "job_id": job_id,
        "reference_video": str(ref_path),
        "product_image": str(prod_path) if prod_path else None,
        "product_description": product_description,
        "mode": mode,
        "status": "detecting_scenes",
    })

    # 장면 감지 & 클립 분할
    try:
        scenes = detect_scenes(str(ref_path))
        clips = split_clips(str(ref_path), scenes, job_id)
        update_job(job_id, {"clips": clips, "status": "review_clips"})

    except Exception as e:
        update_job(job_id, {"status": "error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse({"job_id": job_id, "clip_count": len(clips)})


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/job/{job_id}/confirm-clips")
async def confirm_clips(job_id: str, kept_indices: list[int]):
    """사용자가 클립 검토 후 유지할 클립 인덱스 확정"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    all_clips = job.get("clips", [])
    kept_clips = [c for c in all_clips if c["index"] in kept_indices]
    update_job(job_id, {"clips": kept_clips, "status": "generating_prompts"})

    return {"kept": len(kept_clips)}


@router.post("/job/{job_id}/update-prompts")
async def update_prompts(job_id: str, prompts: dict[str, str]):
    """사용자가 수정한 프롬프트 저장 {clip_index: prompt_text}"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    clips = job.get("clips", [])
    for clip in clips:
        idx = str(clip["index"])
        if idx in prompts:
            clip["prompt"] = prompts[idx]

    update_job(job_id, {"clips": clips, "status": "ready_to_submit"})
    return {"updated": len(prompts)}


@router.post("/job/{job_id}/generate")
async def generate_videos(job_id: str):
    """fal.ai에 모든 클립 제출"""
    from app.services.fal_client import submit_all_clips
    import traceback

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    update_job(job_id, {"status": "generating"})

    try:
        clips = job.get("clips", [])
        product_image_path = job.get("product_image") or ""
        clips = submit_all_clips(clips, product_image_path)
        update_job(job_id, {"clips": clips, "status": "generating"})
    except Exception as e:
        update_job(job_id, {"status": "error", "error": traceback.format_exc()})
        raise HTTPException(status_code=500, detail=f"제출 오류: {str(e)}")

    return {"status": "generating", "clip_count": len(clips)}


@router.get("/job/{job_id}/poll")
async def poll_results(job_id: str):
    """각 클립의 생성 상태 확인 및 완료된 클립 결과 수집"""
    from app.services.fal_client import check_status, get_result

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    clips = job.get("clips", [])
    all_done = True

    for clip in clips:
        if "request_id" not in clip:
            continue
        if clip.get("output_status") == "completed":
            continue

        status = check_status(clip["request_id"])
        s = status["status"]
        if s == "Completed":
            clip["output_url"] = get_result(clip["request_id"])
            clip["output_status"] = "completed"
        elif s == "Failed":
            clip["output_status"] = "failed"
        else:
            all_done = False

    if all_done and all(c.get("output_status") in ("completed", "failed") for c in clips if "request_id" in c):
        update_job(job_id, {"clips": clips, "status": "completed"})
    else:
        update_job(job_id, {"clips": clips})

    completed = sum(1 for c in clips if c.get("output_status") == "completed")
    total = sum(1 for c in clips if "request_id" in c)

    return {"completed": completed, "total": total, "all_done": all_done}


@router.get("/higgsfield/debug")
async def higgsfield_debug():
    """Higgsfield 토큰 & create-media 응답 확인용 디버그 엔드포인트"""
    import os, uuid as _uuid
    from app.config import HIGGSFIELD_TOKEN
    BASE = "https://fnf.higgsfield.ai"
    headers = {"Authorization": f"Bearer {HIGGSFIELD_TOKEN}", "Accept": "application/json"}
    results = {
        "token_preview": HIGGSFIELD_TOKEN[:30] + "..." if HIGGSFIELD_TOKEN else "EMPTY",
        "token_length": len(HIGGSFIELD_TOKEN),
    }
    # 여러 후보 엔드포인트 테스트
    candidates = [
        ("POST", "/video"),
        ("POST", "/videos"),
        ("POST", "/media"),
        ("POST", "/video/create"),
        ("POST", "/api/video"),
        ("POST", "/api/media"),
        ("GET",  "/video"),
        ("GET",  "/user"),
    ]
    with httpx.Client(timeout=10) as client:
        for method, path in candidates:
            try:
                req = client.request(method, f"{BASE}{path}", headers=headers, json={})
                results[f"{method} {path}"] = f"{req.status_code} | {req.text[:120]}"
            except Exception as e:
                results[f"{method} {path}"] = f"ERR: {e}"
    return results
