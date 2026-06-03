import os
import fal_client
from app.config import FAL_API_KEY

os.environ["FAL_KEY"] = FAL_API_KEY


def upload_file(file_path: str) -> str:
    url = fal_client.upload_file(file_path)
    return url


def get_clip_duration(clip_path: str) -> str:
    import subprocess, json
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", clip_path
    ], capture_output=True, text=True)
    info = json.loads(result.stdout)
    secs = float(info["format"]["duration"])
    # Seedance 2.0 지원 범위: 4~15초, 최소 4초 보장
    return str(max(4, min(15, round(secs))))


def submit_video(clip_path: str, product_image_path: str, prompt: str) -> str:
    """클립 + 제품 이미지 + 프롬프트를 fal.ai에 제출하고 request_id 반환"""
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
            "resolution": "1080p",
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
