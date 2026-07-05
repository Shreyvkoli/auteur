"""
Preview Render Service — 480p fast preview rendering.
Generates low-res preview in <5s for instant feedback.
"""

import asyncio
import os
import uuid
import subprocess
import tempfile
from typing import Dict, Any, Optional


async def render_preview(edit_state: Dict[str, Any], video_path: str) -> Dict[str, Any]:
    """
    Render a 480p ultrafast preview of the edit state.
    Returns preview path and metadata.
    """
    preview_id = str(uuid.uuid4())[:8]
    preview_dir = tempfile.mkdtemp()
    preview_path = os.path.join(preview_dir, f"preview_{preview_id}.mp4")

    segments = edit_state.get("timeline", [])
    if not segments:
        return {"error": "No segments to preview", "preview_path": None}

    # Build FFmpeg filter chain for fast preview
    filter_parts = []
    input_args = ["-i", video_path]

    # Ultrafast encoding settings for preview
    encode_args = [
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-vf", "scale=854:480",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        "-y",
    ]

    # Build complex filter for segments (trim + concat)
    if len(segments) == 1:
        seg = segments[0]
        start = seg.get("source_start", seg.get("start_time", 0))
        end = seg.get("source_end", seg.get("end_time", 0))
        speed = seg.get("speed", 1.0)

        filter_complex = []
        if speed != 1.0:
            filter_complex.append(f"[0:v]setpts={1/speed}*PTS[v]")
            filter_complex.append(f"[0:a]atempo={speed}[a]")
            encode_args = [
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-vf", "scale=854:480",
                "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart", "-y",
            ]
        else:
            filter_complex = []

        cmd = ["ffmpeg"] + input_args + [
            "-ss", str(start), "-to", str(end),
        ]
        if filter_complex:
            cmd += ["-filter_complex", ";".join(filter_complex), "-map", "[v]", "-map", "[a]"]
        cmd += encode_args + [preview_path]
    else:
        # Multi-segment: build concat filter
        filter_complex_parts = []
        concat_inputs = ""

        for i, seg in enumerate(segments):
            start = seg.get("source_start", seg.get("start_time", 0))
            end = seg.get("source_end", seg.get("end_time", 0))
            speed = seg.get("speed", 1.0)

            filter_complex_parts.append(
                f"[0:v]trim=start={start}:end={end},setpts={1/speed}*PTS[v{i}]"
            )
            filter_complex_parts.append(
                f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,atempo={speed}[a{i}]"
            )
            concat_inputs += f"[v{i}][a{i}]"

        n = len(segments)
        filter_complex_parts.append(
            f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"
        )

        cmd = ["ffmpeg"] + input_args + [
            "-filter_complex", ";".join(filter_complex_parts),
            "-map", "[outv]", "-map", "[outa]",
        ] + encode_args + [preview_path]

    # Run FFmpeg
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return {
            "error": f"FFmpeg failed: {stderr.decode()[:500]}",
            "preview_path": None,
        }

    # Get file size
    file_size = os.path.getsize(preview_path) if os.path.exists(preview_path) else 0

    return {
        "preview_path": preview_path,
        "preview_id": preview_id,
        "resolution": "480p",
        "preset": "ultrafast",
        "file_size_bytes": file_size,
        "segments_count": len(segments),
    }


async def render_segment_preview(video_path: str, segment: Dict[str, Any]) -> Dict[str, Any]:
    """Render preview for a single segment."""
    preview_id = str(uuid.uuid4())[:8]
    preview_dir = tempfile.mkdtemp()
    preview_path = os.path.join(preview_dir, f"seg_preview_{preview_id}.mp4")

    start = segment.get("source_start", segment.get("start_time", 0))
    end = segment.get("source_end", segment.get("end_time", 0))
    speed = segment.get("speed", 1.0)

    cmd = [
        "ffmpeg", "-i", video_path,
        "-ss", str(start), "-to", str(end),
    ]

    if speed != 1.0:
        cmd += [
            "-filter_complex",
            f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo={speed}[a]",
            "-map", "[v]", "-map", "[a]",
        ]

    cmd += [
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-vf", "scale=854:480",
        "-c:a", "aac", "-b:a", "64k",
        "-movflags", "+faststart",
        "-y", preview_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return {"error": f"FFmpeg failed: {stderr.decode()[:500]}", "preview_path": None}

    file_size = os.path.getsize(preview_path) if os.path.exists(preview_path) else 0

    return {
        "preview_path": preview_path,
        "preview_id": preview_id,
        "file_size_bytes": file_size,
    }


async def cleanup_preview(preview_path: str):
    """Delete a preview file after use."""
    try:
        if preview_path and os.path.exists(preview_path):
            os.remove(preview_path)
            parent = os.path.dirname(preview_path)
            if parent and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
    except Exception:
        pass
