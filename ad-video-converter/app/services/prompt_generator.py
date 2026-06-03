import base64
from openai import OpenAI
from app.config import OPENAI_API_KEY


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def generate_prompt(thumb_path: str, product_description: str, mode: str = "product") -> str:
    """클립 대표 프레임 + 설명으로 Higgsfield용 프롬프트 생성"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    thumb_b64 = _encode_image(thumb_path)

    if mode == "service":
        system_msg = (
            "You are an expert at writing video-to-video prompts for Higgsfield AI. "
            "Your goal is to describe how to adapt a scene to promote a specific service, "
            "keeping the overall style, camera angle, lighting, and composition intact."
        )
        user_text = (
            f"This is a frame from a reference advertisement video. "
            f"I want to create a video promoting this service: {product_description}\n\n"
            "Write a concise Higgsfield video-to-video prompt that:\n"
            "1. Keeps the scene style, lighting, camera angle, and composition the same\n"
            "2. Naturally integrates the service into the scene (e.g. showing the app on a phone, UI elements, etc.)\n"
            "3. Makes the service feel like the natural focus of the scene\n\n"
            "Return only the prompt text, nothing else."
        )
    else:
        system_msg = (
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

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=300,
        messages=[
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{thumb_b64}"}},
                    {"type": "text", "text": user_text},
                ],
            },
        ],
    )
    return response.choices[0].message.content.strip()


def generate_prompts_for_clips(clips: list[dict], product_description: str, mode: str = "product") -> list[dict]:
    """모든 클립에 대해 프롬프트 생성"""
    for clip in clips:
        clip["prompt"] = generate_prompt(clip["thumb_path"], product_description, mode)
    return clips
