import subprocess
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from app.config import DIRS, SCENE_THRESHOLD, MIN_CLIP_DURATION


def detect_scenes(video_path: str) -> list[dict]:
    """장면 전환 감지 후 타임스탬프 목록 반환"""
    video = open_video(video_path)
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=SCENE_THRESHOLD))
    manager.detect_scenes(video)

    scene_list = manager.get_scene_list()

    scenes = []
    for i, (start, end) in enumerate(scene_list):
        duration = end.get_seconds() - start.get_seconds()
        if duration < MIN_CLIP_DURATION:
            continue
        scenes.append({
            "index": i,
            "start": round(start.get_seconds(), 3),
            "end": round(end.get_seconds(), 3),
            "duration": round(duration, 3),
        })

    return scenes


def split_clips(video_path: str, scenes: list[dict], job_id: str) -> list[dict]:
    """장면 목록 기준으로 FFmpeg을 사용해 클립 분할"""
    clips_dir = DIRS["clips"] / job_id
    clips_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    for scene in scenes:
        clip_filename = f"clip_{scene['index']:03d}.mp4"
        clip_path = clips_dir / clip_filename

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(scene["start"]),
            "-to", str(scene["end"]),
            "-i", video_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            str(clip_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # 대표 프레임 추출 (중간 지점)
        mid_time = scene["start"] + scene["duration"] / 2
        thumb_path = clips_dir / f"thumb_{scene['index']:03d}.jpg"
        thumb_cmd = [
            "ffmpeg", "-y",
            "-ss", str(mid_time),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path)
        ]
        subprocess.run(thumb_cmd, check=True, capture_output=True)

        clips.append({
            **scene,
            "clip_path": str(clip_path),
            "thumb_path": str(thumb_path),
            "clip_filename": clip_filename,
            "thumb_filename": f"thumb_{scene['index']:03d}.jpg",
        })

    return clips
