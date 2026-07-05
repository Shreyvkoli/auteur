"""
yt-dlp Service — download YouTube/social videos for reference style analysis.
Downloads temporarily, extracted frames are used, then video deleted.

Requires: yt-dlp installed → pip install yt-dlp
"""

import asyncio
import os
import tempfile
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def download_ref_video(url: str, max_duration_sec: int = 300) -> Dict[str, Any]:
    """
    Download a reference video from YouTube/Instagram/TikTok for style analysis.
    Returns: {video_path: str, duration: float, title: str}
    
    Video is downloaded to a temp directory — caller must delete after use.
    max_duration_sec: Skip videos longer than this (default 5 min).
    """
    output_dir = tempfile.mkdtemp()
    output_template = os.path.join(output_dir, "ref_%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=720]+bestaudio/best[height<=720]",  # Max 720p for speed
        "--merge-output-format", "mp4",
        "--output", output_template,
        "--no-playlist",
        "--max-filesize", "500m",
        "--match-filter", f"duration <= {max_duration_sec}",
        "--print", "after_move:filepath",  # Print final path after download
        url,
    ]

    logger.info(f"Downloading ref video: {url}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError("yt-dlp download timed out after 180s")

    if proc.returncode != 0:
        err = stderr.decode()
        raise RuntimeError(f"yt-dlp failed: {err[:500]}")

    # Get the downloaded file path
    output_lines = stdout.decode().strip().split("\n")
    video_path = None
    for line in output_lines:
        line = line.strip()
        if line and os.path.isfile(line):
            video_path = line
            break

    if not video_path:
        # Fallback: find first mp4 in output dir
        for f in os.listdir(output_dir):
            if f.endswith(".mp4"):
                video_path = os.path.join(output_dir, f)
                break

    if not video_path:
        raise FileNotFoundError(f"yt-dlp download succeeded but file not found in {output_dir}")

    # Get duration via ffprobe
    duration = 0.0
    try:
        from services.ffmpeg_service import get_duration
        duration = await get_duration(video_path)
    except Exception as e:
        logger.warning(f"Could not get duration: {e}")

    logger.info(f"Downloaded ref video → {video_path} ({duration:.1f}s)")
    return {
        "video_path": video_path,
        "duration": duration,
        "output_dir": output_dir,
    }


def cleanup_ref_video(output_dir: str) -> None:
    """Delete temp directory after frame extraction is done."""
    import shutil
    try:
        shutil.rmtree(output_dir, ignore_errors=True)
        logger.info(f"Cleaned up ref video dir: {output_dir}")
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
