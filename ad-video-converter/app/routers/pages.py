from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.services.job_store import get_job
from app.services.prompt_generator import generate_prompts_for_clips
from app.services.job_store import update_job

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/job/{job_id}/clips", response_class=HTMLResponse)
async def review_clips(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse("review_clips.html", {"request": request, "job": job})


@router.get("/job/{job_id}/prompts", response_class=HTMLResponse)
async def review_prompts(request: Request, job_id: str):
    import traceback
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # 프롬프트가 아직 없으면 생성
    clips = job.get("clips", [])
    if clips and "prompt" not in clips[0]:
        try:
            clips = generate_prompts_for_clips(clips, job["product_description"], job.get("mode", "product"))
            update_job(job_id, {"clips": clips, "status": "review_prompts"})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"프롬프트 생성 오류: {traceback.format_exc()}")

    return templates.TemplateResponse("review_prompts.html", {"request": request, "job": job})


@router.get("/job/{job_id}/result", response_class=HTMLResponse)
async def result(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") == "completed":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/job/{job_id}/download")
    return templates.TemplateResponse("result.html", {"request": request, "job": job})


@router.get("/job/{job_id}/download", response_class=HTMLResponse)
async def download(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    clips = job.get("clips", [])
    completed_count = sum(1 for c in clips if c.get("output_url"))
    failed_count = sum(1 for c in clips if c.get("output_status") == "failed")
    return templates.TemplateResponse("download.html", {
        "request": request,
        "job": job,
        "completed_count": completed_count,
        "failed_count": failed_count,
    })
