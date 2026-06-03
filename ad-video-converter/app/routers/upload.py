import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.config import DIRS
from app.services.scene_detector import detect_scenes, split_clips
from app.services.job_store import create_job, update_job, get_job

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_files(
    reference_video: UploadFile = File(...),
    product_image: UploadFile = File(...),
    product_description: str = Form(...),
):
    job_id = str(uuid.uuid4())[:8]

    # 파일 저장
    ref_path = DIRS["reference"] / f"{job_id}_{reference_video.filename}"
    prod_path = DIRS["product"] / f"{job_id}_{product_image.filename}"

    for upload, path in [(reference_video, ref_path), (product_image, prod_path)]:
        with open(path, "wb") as f:
            shutil.copyfileobj(upload.file, f)

    create_job(job_id, {
        "job_id": job_id,
        "reference_video": str(ref_path),
        "product_image": str(prod_path),
        "product_description": product_description,
        "status": "detecting_scenes",
    })

    # 장면 감지 & 클립 분할
    try:
        scenes = detect_scenes(str(ref_path))
        if not scenes:
            raise HTTPException(status_code=400, detail="장면 전환을 감지할 수 없습니다.")

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
