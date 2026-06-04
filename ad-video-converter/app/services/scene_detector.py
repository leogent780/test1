import subprocess
import shutil
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from app.config import DIRS, SCENE_THRESHOLD, MIN_CLIP_DURATION


def _find_bin(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    # Nix store fallback
    for candidate in [f"/usr/bin/{name}", f"/usr/local/bin/{name}", f"/nix/var/nix/profiles/default/bin/{name}"]:
        if Path(candidate).exists():
            return candidate
    return name


def _get_video_duration(video_path: str) -> float:
    import subprocess, json
    result = subprocess.run([
        _find_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
        "-of", "json", video_path
    ], capture_output=True, text=True)
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def detect_scenes(video_path: str) -> list[dict]:
    """장면 전환 감지 후 타임스탬프 목록 반환. 감지 안 되면 전체를 1개 클립으로 반환."""
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

    # 장면 전환이 없으면 영상 전체를 1개 클립으로 처리
    if not scenes:
        total = _get_video_duration(video_path)
        scenes = [{"index": 0, "start": 0.0, "end": round(total, 3), "duration": round(total, 3)}]

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
            _find_bin("ffmpeg"), "-y",
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
            _find_bin("ffmpeg"), "-y",
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
