import subprocess
import shutil
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from app.config import DIRS, SCENE_THRESHOLD, MIN_CLIP_DURATION


def _find_bin(name: str) -> str:
    # 1) imageio-ffmpeg 번들 바이너리 우선
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_path = str(Path(ffmpeg_path).parent / ("ffprobe" + (".exe" if ffmpeg_path.endswith(".exe") else "")))
        if name == "ffmpeg":
            return ffmpeg_path
        if name == "ffprobe" and Path(ffprobe_path).exists():
            return ffprobe_path
    except Exception:
        pass
    # 2) 시스템 PATH
    found = shutil.which(name)
    if found:
        return found
    return name


def _get_video_duration(video_path: str) -> float:
    import json
    result = subprocess.run([
        _find_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
        "-of", "json", video_path
    ], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        # ffprobe 없으면 ffmpeg로 대체
        result2 = subprocess.run([
            _find_bin("ffmpeg"), "-i", video_path
        ], capture_output=True, text=True)
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result2.stderr)
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mn * 60 + s
        return 30.0
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
