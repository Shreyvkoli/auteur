"""
FFmpeg Service — all video processing operations.
Cuts, zoom, captions, audio overlay, color grade, final export.

Requires: ffmpeg + ffprobe installed on system.
  macOS:  brew install ffmpeg
  Ubuntu: apt install ffmpeg
"""

import asyncio
import json
import os
import subprocess
import tempfile
import logging
from typing import List, Dict, Any, Optional, Tuple

from core.config import settings

logger = logging.getLogger(__name__)

FFMPEG_THREADS = int(os.getenv("FFMPEG_THREADS", "1"))
_ffmpeg_semaphore = asyncio.Semaphore(settings.max_ffmpeg_processes)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run(cmd: List[str], timeout: int = 300) -> Tuple[str, str]:
    """Run ffmpeg command asynchronously."""
    logger.debug(f"FFmpeg cmd: {' '.join(cmd)}")
    async with _ffmpeg_semaphore:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "FFMPEG_THREADS": str(FFMPEG_THREADS)},
        )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError(f"FFmpeg timed out after {timeout}s")
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{stderr.decode()}")
    return stdout.decode(), stderr.decode()


def _tmp(suffix: str) -> str:
    """Create a temp file path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


# ── 1. Duration ───────────────────────────────────────────────────────────────

async def get_duration(video_path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path,
    ]
    stdout, _ = await _run(cmd, timeout=30)
    data = json.loads(stdout)
    return float(data["format"].get("duration", 0))


# ── 2. Compression ────────────────────────────────────────────────────────────

async def compress_video(input_path: str, output_path: str, target_mb: int = 80) -> str:
    """
    Compress video to approximately target_mb size.
    Uses CRF-based encoding (quality-based, not exact size).
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vcodec", "libx264",
        "-crf", "28",          # Higher = smaller file, lower quality
        "-preset", "fast",
        "-acodec", "aac",
        "-b:a", "128k",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=600)
    logger.info(f"Compressed video → {output_path}")
    return output_path


# ── 3. Audio Extraction ───────────────────────────────────────────────────────

async def extract_audio(video_path: str) -> str:
    """
    Extract audio from video as mono MP3 at 16kHz (optimal for Whisper).
    Returns path to the audio file.
    Raises ValueError if video has no audio stream.
    """
    output_path = _tmp(".mp3")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                   # No video
        "-acodec", "libmp3lame",
        "-ar", "16000",          # 16kHz — Whisper optimal
        "-ac", "1",              # Mono
        "-q:a", "4",
        output_path,
    ]
    try:
        await _run(cmd, timeout=120)
    except RuntimeError as e:
        if "does not contain any stream" in str(e) or "Output file does not contain" in str(e):
            raise ValueError("Video has no audio track — cannot transcribe")
        raise
    logger.info(f"Audio extracted → {output_path}")
    return output_path


# ── 4. Frame Extraction ───────────────────────────────────────────────────────

async def extract_frames(video_path: str, interval_sec: int = 3, max_frames: int = 20) -> List[str]:
    """
    Extract frames every `interval_sec` seconds from a video.
    Returns list of image file paths.
    Used for GPT-4o Vision style analysis.
    """
    output_dir = tempfile.mkdtemp()
    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"fps=1/{interval_sec},scale=640:-1",  # 640px wide, every N sec
        "-q:v", "3",
        output_pattern,
    ]
    await _run(cmd, timeout=120)

    frames = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.endswith(".jpg")
    ])

    # Cap at max_frames (evenly spaced if too many)
    if len(frames) > max_frames:
        step = len(frames) // max_frames
        frames = frames[::step][:max_frames]

    logger.info(f"Extracted {len(frames)} frames from {video_path}")
    return frames


# ── 5. Cut & Concat ───────────────────────────────────────────────────────────

async def cut_and_concat(video_path: str, segments: List[Dict[str, float]]) -> str:
    """
    Cut video into segments and concatenate them.
    segments: [{start: float, end: float}, ...]
    Returns path to concatenated output video.
    """
    if not segments:
        raise ValueError("No segments provided")

    segment_files = []
    for i, seg in enumerate(segments):
        out = _tmp(f"_seg{i}.mp4")
        duration = seg["end"] - seg["start"]
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(seg["start"]),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-threads", str(FFMPEG_THREADS),
            out,
        ]
        await _run(cmd, timeout=120)
        segment_files.append(out)

    # Write concat list
    list_file = _tmp(".txt")
    with open(list_file, "w") as f:
        for sf in segment_files:
            f.write(f"file '{sf}'\n")

    output_path = _tmp("_concat.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path,
    ]
    await _run(cmd, timeout=300)

    # Cleanup segments and list
    for sf in segment_files:
        try:
            os.remove(sf)
        except Exception:
            pass
    try:
        os.remove(list_file)
    except Exception:
        pass

    logger.info(f"Cut and concat complete → {output_path}")
    return output_path


# ── 6. Zoom Effects ───────────────────────────────────────────────────────────

async def apply_zoom_moments(video_path: str, zoom_moments: List[Dict[str, Any]]) -> str:
    """
    Apply punch zoom effects at specified timestamps.
    zoom_moments: [{timestamp: float, scale: float, duration: float}, ...]
    """
    if not zoom_moments:
        return video_path

    output_path = _tmp("_zoom.mp4")

    # Build zoompan filter for each moment
    # Simple approach: scale + crop at each timestamp
    filters = []
    for zm in zoom_moments:
        t = zm["timestamp"]
        scale = zm.get("scale", 1.3)
        dur = zm.get("duration", 0.5)
        # Zoom in between t and t+dur
        filters.append(
            f"zoompan=z='if(between(t,{t},{t+dur}),{scale},1)'"
            f":d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s=1080x1920"
        )

    # Apply first zoom filter (stacking complex, use simple scale approach)
    # For production, each zoom_moment gets its own filter segment
    vf = ",".join(filters) if filters else "scale=1080:1920"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Zoom applied → {output_path}")
    return output_path


# ── 7. Captions ───────────────────────────────────────────────────────────────

CAPTION_STYLES = {
    "bold_yellow_center": {
        "FontName": "Arial",
        "PrimaryColour": "&H0000FFFF",  # Yellow in BGR hex
        "BorderStyle": "1",
        "Outline": "2",
        "Alignment": "2",  # Center-bottom
        "FontSize": "52",
    },
    "bold_white_center": {
        "FontName": "Arial",
        "PrimaryColour": "&H00FFFFFF",
        "BorderStyle": "1",
        "Outline": "2",
        "Alignment": "2",
        "FontSize": "52",
    },
    "bold_white_top": {
        "FontName": "Arial",
        "PrimaryColour": "&H00FFFFFF",
        "BorderStyle": "1",
        "Outline": "2",
        "Alignment": "8",  # Center-top
        "FontSize": "48",
    },
}


def _build_srt(captions: List[Dict[str, Any]]) -> str:
    """Build SRT subtitle file content from captions list."""
    def fmt_time(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, cap in enumerate(captions, 1):
        lines.append(str(i))
        lines.append(f"{fmt_time(cap['start'])} --> {fmt_time(cap['end'])}")
        lines.append(cap["text"])
        lines.append("")
    return "\n".join(lines)


async def burn_captions(video_path: str, captions: List[Dict[str, Any]]) -> str:
    """
    Burn captions into video using FFmpeg subtitles filter.
    captions: [{start, end, text, style}, ...]
    """
    if not captions:
        return video_path

    # Write SRT file
    srt_path = _tmp(".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(_build_srt(captions))

    output_path = _tmp("_captioned.mp4")

    # Get style from first caption (simplification — one style per video)
    style_key = captions[0].get("style", "bold_white_center")
    style = CAPTION_STYLES.get(style_key, CAPTION_STYLES["bold_white_center"])

    # Build force_style string
    force_style = ",".join(f"{k}={v}" for k, v in style.items())

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={srt_path}:force_style='{force_style}'",
        "-c:v", "libx264",
        "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)

    try:
        os.remove(srt_path)
    except Exception:
        pass

    logger.info(f"Captions burned → {output_path}")
    return output_path


# ── 8. Audio Overlay (Meme Sounds) ───────────────────────────────────────────

async def add_audio_overlays(
    video_path: str,
    overlays: List[Dict[str, Any]],  # [{timestamp, audio_path, volume}]
) -> str:
    """
    Mix multiple audio clips into the video at specified timestamps.
    overlays: [{timestamp: float, audio_path: str, volume: float (0-1)}]
    """
    if not overlays:
        return video_path

    output_path = _tmp("_sounds.mp4")

    # Build complex filter for each overlay
    inputs = ["-i", video_path]
    for ov in overlays:
        inputs += ["-i", ov["audio_path"]]

    # amix filter — mix original audio with each overlay
    n = len(overlays)
    filter_parts = []

    # Delay each overlay audio to its timestamp
    for i, ov in enumerate(overlays, 1):
        delay_ms = int(ov["timestamp"] * 1000)
        vol = ov.get("volume", 0.8)
        filter_parts.append(
            f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={vol}[ov{i}]"
        )

    # Mix all together
    mix_inputs = "[0:a]" + "".join(f"[ov{i}]" for i in range(1, n + 1))
    filter_parts.append(f"{mix_inputs}amix=inputs={n + 1}:duration=first[aout]")

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Audio overlays added → {output_path}")
    return output_path


# ── 9. Background Music ───────────────────────────────────────────────────────

async def add_background_music(
    video_path: str,
    music_path: str,
    music_volume: float = 0.25,
) -> str:
    """
    Add background music to video, mixed under the voice.
    music_volume: 0.0-1.0 (default 0.25 = 25%)
    """
    output_path = _tmp("_music.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex",
        f"[1:a]volume={music_volume}[bg];[0:a][bg]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Background music added → {output_path}")
    return output_path


# ── 10. Color Grading ─────────────────────────────────────────────────────────

COLOR_GRADES = {
    "warm": "curves=r='0/0 0.5/0.6 1/1':g='0/0 0.5/0.5 1/0.9':b='0/0 0.5/0.4 1/0.8'",
    "cool": "curves=r='0/0 0.5/0.4 1/0.9':g='0/0 0.5/0.5 1/0.9':b='0/0 0.5/0.6 1/1'",
    "cinematic": "curves=r='0/0.05 0.5/0.5 1/0.95':g='0/0.02 0.5/0.48 1/0.92':b='0/0.05 0.5/0.55 1/1'",
    "vibrant": "eq=saturation=1.4:contrast=1.1:brightness=0.02",
    "matte": "curves=r='0/0.05 1/0.95':g='0/0.05 1/0.95':b='0/0.05 1/0.95'",
    "none": None,
}


async def apply_color_grade(video_path: str, grade: str = "warm") -> str:
    """Apply a color grade preset to the video."""
    filter_str = COLOR_GRADES.get(grade)
    if not filter_str:
        return video_path  # No grade needed

    output_path = _tmp("_graded.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", filter_str,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Color grade '{grade}' applied → {output_path}")
    return output_path


# ── 11. Final Export ──────────────────────────────────────────────────────────

async def export_reel(video_path: str) -> str:
    """
    Final export: scale to 1080x1920 (portrait/reels), H.264, mobile-optimized.
    """
    output_path = _tmp("_reel.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        ),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",  # Web-optimized
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=600)
    logger.info(f"Final reel exported → {output_path}")
    return output_path


# ── 12. Preview Render (480p Ultrafast) ──────────────────────────────────────

async def render_preview(video_path: str, output_path: Optional[str] = None,
                          start: float = 0, end: Optional[float] = None,
                          speed: float = 1.0) -> str:
    """
    Render a 480p ultrafast preview for instant feedback.
    Uses ultrafast preset + lower CRF for maximum speed.
    """
    if not output_path:
        output_path = _tmp("_preview.mp4")

    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", video_path]
    if end:
        cmd += ["-to", str(end)]

    if speed != 1.0:
        cmd += [
            "-filter_complex",
            f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo={speed}[a]",
            "-map", "[v]", "-map", "[a]",
        ]

    cmd += [
        "-vf", "scale=854:480",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]

    await _run(cmd, timeout=60)
    logger.info(f"Preview rendered → {output_path}")
    return output_path


async def render_preview_multi_segment(
    video_path: str,
    segments: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """
    Render a multi-segment preview. Each segment can have its own speed.
    Uses concat filter for fast preview generation.
    """
    if not output_path:
        output_path = _tmp("_preview_multi.mp4")

    if len(segments) == 1:
        seg = segments[0]
        return await render_preview(
            video_path, output_path,
            start=seg.get("start_time", 0),
            end=seg.get("end_time", 0),
            speed=seg.get("speed", 1.0),
        )

    # Build complex filter for multiple segments
    filter_parts = []
    concat_inputs = ""

    for i, seg in enumerate(segments):
        start = seg.get("start_time", 0)
        end = seg.get("end_time", 0)
        speed = seg.get("speed", 1.0)

        filter_parts.append(
            f"[0:v]trim=start={start}:end={end},setpts={1/speed}*PTS[v{i}]"
        )
        filter_parts.append(
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,atempo={speed}[a{i}]"
        )
        concat_inputs += f"[v{i}][a{i}]"

    n = len(segments)
    filter_parts.append(
        f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outv]", "-map", "[outa]",
        "-vf", "scale=854:480",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]

    await _run(cmd, timeout=120)
    logger.info(f"Multi-segment preview rendered → {output_path}")
    return output_path


# ── 13. Speed Change ─────────────────────────────────────────────────────────

async def apply_speed(video_path: str, speed: float) -> str:
    """Change playback speed of a video."""
    output_path = _tmp("_speed.mp4")
    speed = max(0.1, min(10.0, speed))

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-filter_complex",
        f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo={min(2.0, speed)}[a]" if speed <= 2.0
        else f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo=2.0,atempo={speed/2.0}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Speed {speed}x applied → {output_path}")
    return output_path


# ── 14. Reverse ───────────────────────────────────────────────────────────────

async def reverse_video(video_path: str) -> str:
    """Reverse a video clip."""
    output_path = _tmp("_reversed.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", "reverse",
        "-af", "areverse",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Video reversed → {output_path}")
    return output_path


# ── 15. Freeze Frame ──────────────────────────────────────────────────────────

async def freeze_frame(video_path: str, at: float, duration: float = 2.0) -> str:
    """Insert a freeze frame at a specific time."""
    output_path = _tmp("_freeze.mp4")

    before_path = _tmp("_freeze_before.mp4")
    after_path = _tmp("_freeze_after.mp4")
    freeze_path = _tmp("_freeze_img.jpg")

    await _run([
        "ffmpeg", "-y", "-i", video_path,
        "-t", str(at), "-c:v", "libx264", "-c:a", "aac", before_path,
    ], timeout=120)

    await _run([
        "ffmpeg", "-y", "-ss", str(at), "-i", video_path,
        "-frames:v", "1", freeze_path,
    ], timeout=30)

    await _run([
        "ffmpeg", "-y", "-ss", str(at), "-i", video_path,
        "-c:v", "libx264", "-c:a", "aac", after_path,
    ], timeout=120)

    freeze_video = _tmp("_freeze_loop.mp4")
    await _run([
        "ffmpeg", "-y", "-loop", "1", "-i", freeze_path,
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", "30", freeze_video,
    ], timeout=60)

    list_file = _tmp(".txt")
    with open(list_file, "w") as f:
        f.write(f"file '{before_path}'\n")
        f.write(f"file '{freeze_video}'\n")
        f.write(f"file '{after_path}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output_path,
    ]
    await _run(cmd, timeout=300)

    for p in [before_path, after_path, freeze_path, freeze_video, list_file]:
        try:
            os.remove(p)
        except Exception:
            pass

    logger.info(f"Freeze frame inserted → {output_path}")
    return output_path


# ── 16. Crop ──────────────────────────────────────────────────────────────────

async def apply_crop(
    video_path: str,
    x: float, y: float,
    width: float, height: float,
) -> str:
    """Apply crop to video (normalized 0-1 coordinates)."""
    output_path = _tmp("_cropped.mp4")

    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path,
    ]
    stdout, _ = await _run(probe_cmd, timeout=30)
    streams = json.loads(stdout)
    vw, vh = 1080, 1920
    for s in streams.get("streams", []):
        if s.get("codec_type") == "video":
            vw = int(s.get("width", 1080))
            vh = int(s.get("height", 1920))
            break

    crop_w = int(vw * width)
    crop_h = int(vh * height)
    crop_x = int(vw * x)
    crop_y = int(vh * y)

    crop_x = max(0, min(crop_x, vw - crop_w))
    crop_y = max(0, min(crop_y, vh - crop_h))

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        "-c:v", "libx264", "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Crop applied → {output_path}")
    return output_path


# ── 17. Rotate ────────────────────────────────────────────────────────────────

async def apply_rotation(video_path: str, degrees: float) -> str:
    """Rotate video by degrees."""
    output_path = _tmp("_rotated.mp4")
    degrees = degrees % 360

    if degrees == 90:
        vf = "transpose=1"
    elif degrees == 180:
        vf = "transpose=1,transpose=1"
    elif degrees == 270:
        vf = "transpose=2"
    else:
        vf = f"rotate={degrees}*PI/180:fillcolor=black"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Rotation {degrees}° applied → {output_path}")
    return output_path


# ── 18. Opacity ───────────────────────────────────────────────────────────────

async def apply_opacity(video_path: str, opacity: float) -> str:
    """Set video opacity (requires black background overlay)."""
    output_path = _tmp("_opacity.mp4")
    opacity = max(0.0, min(1.0, opacity))

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"color=black:s=1080x1920[bg];[bg][0:v]overlay=format=auto:alpha={opacity}",
        "-c:v", "libx264", "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Opacity {opacity} applied → {output_path}")
    return output_path


# ── 19. Apply Arbitrary Filter String ─────────────────────────────────────────

async def apply_filter_string(video_path: str, filter_str: str) -> str:
    """Apply an arbitrary FFmpeg filter string."""
    if not filter_str:
        return video_path

    output_path = _tmp("_filtered.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Filter applied → {output_path}")
    return output_path


# ── 20. Burn Text Overlays ───────────────────────────────────────────────────

async def burn_text_overlays(video_path: str, text_overlays: List[Dict[str, Any]]) -> str:
    """Burn text overlays into video using drawtext filter."""
    if not text_overlays:
        return video_path

    output_path = _tmp("_text_overlays.mp4")
    filters = []

    for tov in text_overlays:
        text = tov.get("text", "").replace("'", "\\'").replace(":", "\\:")
        start = tov.get("start", 0)
        end = tov.get("end", 0)
        x = tov.get("x", 0.5)
        y = tov.get("y", 0.5)
        style = tov.get("style", {})
        font_size = style.get("font_size_px", 48)
        color = style.get("color", "#FFFFFF").lstrip("#")
        ffmpeg_color = f"0x{color}"

        x_expr = f"({x})*(w-tw)"
        y_expr = f"({y})*(h-th)"

        filters.append(
            f"drawtext=text='{text}'"
            f":fontsize={font_size}"
            f":fontcolor={ffmpeg_color}"
            f":x={x_expr}"
            f":y={y_expr}"
            f":enable='between(t,{start},{end})'"
        )

    if not filters:
        return video_path

    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-c:a", "copy",
        "-threads", str(FFMPEG_THREADS),
        output_path,
    ]
    await _run(cmd, timeout=300)
    logger.info(f"Text overlays burned → {output_path}")
    return output_path


# ── 21. Apply Image Overlays ──────────────────────────────────────────────────

async def apply_overlays(
    video_path: str,
    overlays: List[Dict[str, Any]],
    timeline_start: float = 0,
) -> str:
    """Apply image/sticker overlays on top of video."""
    if not overlays:
        return video_path

    output_path = _tmp("_overlays.mp4")
    current = video_path
    tmp_files = []

    for ov in overlays:
        overlay_path = _tmp("_overlay_img.png")
        source_url = ov.get("source_url", "")

        if source_url.startswith("http"):
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(source_url)
                with open(overlay_path, "wb") as f:
                    f.write(resp.content)
        elif os.path.exists(source_url):
            import shutil
            shutil.copy2(source_url, overlay_path)
        else:
            continue

        x = ov.get("x", 0.5)
        y = ov.get("y", 0.5)
        scale = ov.get("scale", 1.0)

        out = _tmp("_overlay_out.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", current,
            "-i", overlay_path,
            "-filter_complex",
            f"[1:v]scale=iw*{scale}:ih*{scale}[ov];"
            f"[0:v][ov]overlay=({x})*({1080}-overlay_w):({y})*({1920}-overlay_h)",
            "-c:v", "libx264", "-c:a", "copy",
            "-threads", str(FFMPEG_THREADS),
            out,
        ]
        try:
            await _run(cmd, timeout=120)
            tmp_files.append(out)
            current = out
        except Exception as e:
            logger.warning(f"Overlay apply failed: {e}")

        try:
            os.remove(overlay_path)
        except Exception:
            pass

    if current != video_path:
        return current
    return video_path
