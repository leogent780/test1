import os
import fal_client

# FAL_KEY 또는 FAL_API_KEY 둘 다 지원
if not os.environ.get("FAL_KEY"):
    fal_key = os.environ.get("FAL_API_KEY", "")
    if fal_key:
        os.environ["FAL_KEY"] = fal_key


def upload_file(file_path: str) -> str:
    url = fal_client.upload_file(file_path)
    return url


def get_clip_duration_secs(clip_path: str) -> float:
    import subprocess, json, re
    from app.services.scene_detector import _find_bin
    secs = None
    try:
        result = subprocess.run([
            _find_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
            "-of", "json", clip_path
        ], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            secs = float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        pass
    if secs is None:
        try:
            result2 = subprocess.run([_find_bin("ffmpeg"), "-i", clip_path], capture_output=True, text=True)
            m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result2.stderr)
            if m:
                h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                secs = h * 3600 + mn * 60 + s
        except Exception:
            pass
    return secs if secs is not None else 5.0


def get_clip_duration(clip_path: str) -> str:
    secs = get_clip_duration_secs(clip_path)
    return str(max(4, min(15, round(secs))))


def _ensure_min_duration(clip_path: str, min_secs: float = 4.0) -> str:
    """클립이 min_secs보다 짧으면 슬로우모션으로 늘려서 임시 파일 반환. 충분하면 원본 반환."""
    import subprocess, tempfile
    from pathlib import Path
    from app.services.scene_detector import _find_bin

    secs = get_clip_duration_secs(clip_path)
    if secs >= min_secs:
        return clip_path

    factor = min(min_secs / max(secs, 0.1), 10.0)
    pts_factor = factor

    suffix = Path(clip_path).suffix
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()

    # atempo는 0.5~2.0 범위만 지원하므로 factor > 2이면 체인
    rem = 1.0 / factor
    atempo_chain = []
    while rem < 0.5:
        atempo_chain.append("atempo=0.5")
        rem /= 0.5
    atempo_chain.append(f"atempo={rem:.4f}")
    af = ",".join(atempo_chain)

    cmd = [
        _find_bin("ffmpeg"), "-y", "-i", clip_path,
        "-vf", f"setpts={pts_factor:.4f}*PTS",
        "-af", af,
        "-c:v", "libx264", "-c:a", "aac",
        tmp.name
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        return clip_path
    return tmp.name


def submit_video(clip_path: str, product_image_path: str, prompt: str) -> str:
    """클립 + 제품 이미지 + 프롬프트를 fal.ai에 제출하고 request_id 반환"""
    clip_path = _ensure_min_duration(clip_path)
    clip_url = upload_file(clip_path)
    image_url = upload_file(product_image_path)
    duration = get_clip_duration(clip_path)

    full_prompt = f"Use @Video1 as the reference video. Use @Image1 as the replacement product. {prompt}"

    handler = fal_client.submit(
        "bytedance/seedance-2.0/reference-to-video",
        arguments={
            "prompt": full_prompt,
            "video_urls": [clip_url],
            "image_urls": [image_url],
            "resolution": "480p",
            "aspect_ratio": "9:16",
            "duration": duration,
        },
    )

    return handler.request_id


def check_status(request_id: str) -> dict:
    """request_id로 생성 상태 확인"""
    status = fal_client.status(
        "bytedance/seedance-2.0/reference-to-video",
        request_id,
        with_logs=False,
    )
    return {"status": type(status).__name__, "request_id": request_id}


def get_result(request_id: str) -> str:
    """완료된 request_id에서 결과 영상 URL 반환"""
    result = fal_client.result(
        "bytedance/seedance-2.0/reference-to-video",
        request_id,
    )
    return result["video"]["url"]


def submit_all_clips(clips: list[dict], product_image_path: str) -> list[dict]:
    """모든 클립을 fal.ai에 제출하고 request_id 저장"""
    for clip in clips:
        request_id = submit_video(
            clip["clip_path"],
            product_image_path,
            clip["prompt"],
        )
        clip["request_id"] = request_id
        clip["output_status"] = "queued"
    return clips
