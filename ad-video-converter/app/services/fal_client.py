import os
import fal_client
from app.config import FAL_API_KEY

os.environ["FAL_KEY"] = FAL_API_KEY


def upload_file(file_path: str) -> str:
    """로컬 파일을 fal.ai에 업로드하고 URL 반환"""
    url = fal_client.upload_file(file_path)
    return url


def generate_video(clip_path: str, product_image_path: str, prompt: str) -> str:
    """클립 + 제품 이미지 + 프롬프트로 영상 생성 후 결과 URL 반환"""
    clip_url = upload_file(clip_path)
    image_url = upload_file(product_image_path)

    result = fal_client.subscribe(
        "bytedance/seedance-2.0/reference-to-video",
        arguments={
            "prompt": prompt,
            "video_urls": [clip_url],
            "image_urls": [image_url],
            "resolution": "720p",
            "aspect_ratio": "9:16",
        },
    )

    return result["video"]["url"]


def generate_videos_for_clips(clips: list[dict], product_image_path: str) -> list[dict]:
    """모든 클립에 대해 영상 생성"""
    for clip in clips:
        clip["output_url"] = generate_video(
            clip["clip_path"],
            product_image_path,
            clip["prompt"],
        )
    return clips
