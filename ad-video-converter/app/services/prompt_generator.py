import base64
import anthropic
from pathlib import Path
from app.config import ANTHROPIC_API_KEY


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def generate_prompt(thumb_path: str, product_description: str) -> str:
    """클립 대표 프레임 + 제품 설명으로 Higgsfield용 프롬프트 생성"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    thumb_b64 = _encode_image(thumb_path)

    system = (
        "You are an expert at writing video-to-video prompts for Higgsfield AI. "
        "Your goal is to describe how to replace a product in a scene while keeping "
        "everything else identical: camera angle, lighting, background, hand positions, "
        "actions, and overall composition."
    )

    user_text = (
        f"This is a frame from an advertisement video. "
        f"I want to replace the product in this scene with: {product_description}\n\n"
        "Write a concise Higgsfield video-to-video prompt that:\n"
        "1. Keeps the scene, background, lighting, and camera angle exactly the same\n"
        "2. Replaces only the product with the described product\n"
        "3. Maintains natural hand/body positions and movements\n\n"
        "Return only the prompt text, nothing else."
    )

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=300,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": thumb_b64,
                    },
                },
                {"type": "text", "text": user_text},
            ],
        }],
    )

    return message.content[0].text.strip()


def generate_prompts_for_clips(clips: list[dict], product_description: str) -> list[dict]:
    """모든 클립에 대해 프롬프트 생성"""
    for clip in clips:
        clip["prompt"] = generate_prompt(clip["thumb_path"], product_description)
    return clips
