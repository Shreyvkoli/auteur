"""
Partial Render System — Segment-level caching + re-render only dirty segments.

DO NOT re-render the full video on every small change.
Instead:
  1. Identify dirty segments from edit_state.dirty_segments
  2. Re-render only those segments
  3. Stitch with cached clean segments
  4. Return final output

Cache uses segment_cache table with content hashes for invalidation.
"""

import hashlib
import json
import logging
import os
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from core.database import get_supabase
from services.edit_state import get_edit_state, clear_dirty, get_dirty_ranges, save_edit_state
from services import ffmpeg_service, cloudinary_service

logger = logging.getLogger(__name__)


# ── Segment Hashing ─────────────────────────────────────────────────────────────

def _hash_segment(state: Dict[str, Any], clip_id: str, step_name: str) -> str:
    """Generate a content hash for cache invalidation."""
    clip = next((c for c in state.get("clips", []) if c["id"] == clip_id), {})
    seg = next((s for s in state.get("timeline", []) if s["clip_id"] == clip_id), {})

    content = {
        "clip_id": clip_id,
        "source_url": clip.get("source_url", ""),
        "source_start": seg.get("source_start", 0),
        "source_end": seg.get("source_end", 0),
        "speed": seg.get("speed", 1.0),
        "step": step_name,
        "state_version": state.get("version", 1),
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


def _check_cache(
    job_id: str,
    user_id: str,
    clip_id: str,
    step_name: str,
    expected_hash: str,
) -> Optional[str]:
    """Check if a rendered segment exists in cache and is still valid."""
    supabase = get_supabase()
    result = (
        supabase.table("segment_cache")
        .select("cloudinary_url")
        .eq("job_id", job_id)
        .eq("clip_id", clip_id)
        .eq("step_name", step_name)
        .eq("hash", expected_hash)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0].get("cloudinary_url")
    return None


def _save_to_cache(
    job_id: str,
    user_id: str,
    clip_id: str,
    step_name: str,
    clip_start: float,
    clip_end: float,
    cloudinary_url: str,
    public_id: str,
    content_hash: str,
) -> None:
    """Save a rendered segment to the cache."""
    supabase = get_supabase()
    supabase.table("segment_cache").insert({
        "id": str(uuid4()),
        "job_id": job_id,
        "user_id": user_id,
        "segment_key": f"{clip_id}_{step_name}",
        "clip_id": clip_id,
        "step_name": step_name,
        "start_time": clip_start,
        "end_time": clip_end,
        "cloudinary_url": cloudinary_url,
        "cloudinary_public_id": public_id,
        "hash": content_hash,
    }).execute()


# ── Render a Single Segment Step ───────────────────────────────────────────────

async def _render_segment_step(
    video_path: str,
    clip: Dict[str, Any],
    seg: Dict[str, Any],
    step_name: str,
    state: Dict[str, Any],
) -> str:
    """Render a single processing step for one timeline segment."""
    current_path = video_path

    if step_name == "cut":
        current_path = await ffmpeg_service.cut_and_concat(video_path, [
            {"start": seg["source_start"], "end": seg["source_end"]}
        ])

    elif step_name == "speed":
        speed = seg.get("speed", 1.0)
        if speed != 1.0:
            current_path = await ffmpeg_service.apply_speed(current_path, speed)

    elif step_name == "reverse":
        if seg.get("reversed", False):
            current_path = await ffmpeg_service.reverse_video(current_path)

    elif step_name == "freeze_frame":
        ff = seg.get("freeze_frame")
        if ff:
            current_path = await ffmpeg_service.freeze_frame(
                current_path, ff.get("at", 0), ff.get("duration", 2.0)
            )

    elif step_name == "crop":
        crop = seg.get("crop")
        if crop:
            current_path = await ffmpeg_service.apply_crop(
                current_path,
                crop.get("x", 0), crop.get("y", 0),
                crop.get("width", 1), crop.get("height", 1),
            )

    elif step_name == "rotate":
        rotation = seg.get("rotation", 0)
        if rotation != 0:
            current_path = await ffmpeg_service.apply_rotation(current_path, rotation)

    elif step_name == "opacity":
        opacity = seg.get("opacity", 1.0)
        if opacity < 1.0:
            current_path = await ffmpeg_service.apply_opacity(current_path, opacity)

    elif step_name == "zoom":
        zoom_moments = state["effects"].get("transitions", [])
        segment_zooms = [
            zm for zm in zoom_moments
            if seg["timeline_start"] <= zm.get("timestamp", 0) <= seg["timeline_end"]
            and zm.get("type") == "zoom"
        ]
        if segment_zooms:
            adjusted = []
            for zm in segment_zooms:
                adjusted.append({
                    "timestamp": zm["timestamp"] - seg["timeline_start"],
                    "scale": zm.get("scale", 1.3),
                    "duration": zm.get("duration", 0.5),
                })
            current_path = await ffmpeg_service.apply_zoom_moments(current_path, adjusted)

    elif step_name == "captions":
        segment_captions = [
            cap for cap in state.get("captions", [])
            if seg["timeline_start"] <= cap.get("start", 0) <= seg["timeline_end"]
        ]
        if segment_captions:
            for cap in segment_captions:
                cap["start"] = max(0, cap["start"] - seg["timeline_start"])
                cap["end"] = max(0, cap["end"] - seg["timeline_start"])
            current_path = await ffmpeg_service.burn_captions(current_path, segment_captions)

    elif step_name == "text_overlays":
        from services.text_overlay_engine import get_text_overlays_in_range, build_text_style_string
        text_overlays = get_text_overlays_in_range(state, seg["timeline_start"], seg["timeline_end"])
        if text_overlays:
            for tov in text_overlays:
                tov_copy = dict(tov)
                tov_copy["start"] = max(0, tov["start"] - seg["timeline_start"])
                tov_copy["end"] = max(0, tov["end"] - seg["timeline_start"])
            current_path = await ffmpeg_service.burn_text_overlays(current_path, text_overlays)

    elif step_name == "overlays":
        from services.overlay_engine import get_overlays_in_range
        overlays = get_overlays_in_range(state, seg["timeline_start"], seg["timeline_end"])
        if overlays:
            current_path = await ffmpeg_service.apply_overlays(current_path, overlays, seg["timeline_start"])

    elif step_name == "grade":
        grade = state["effects"].get("color_grade", "none")
        if grade and grade != "none":
            current_path = await ffmpeg_service.apply_color_grade(current_path, grade)

        effects = state.get("effects", {})
        if effects.get("brightness") is not None or effects.get("contrast") is not None or effects.get("saturation") is not None:
            from services.effects_engine import build_color_filter
            color_filter = build_color_filter(effects)
            if color_filter:
                current_path = await ffmpeg_service.apply_filter_string(current_path, color_filter)

    elif step_name == "blur_effects":
        effects = state.get("effects", {})
        blurs = effects.get("blur_effects", [])
        for blur in blurs:
            if seg["timeline_start"] <= blur.get("start", 0) <= seg["timeline_end"]:
                from services.effects_engine import build_blur_filter
                blur_filter = build_blur_filter(blur)
                current_path = await ffmpeg_service.apply_filter_string(current_path, blur_filter)

    elif step_name == "vignette":
        effects = state.get("effects", {})
        vignettes = effects.get("vignette_effects", [])
        for vig in vignettes:
            if seg["timeline_start"] <= vig.get("start", 0) <= seg["timeline_end"]:
                from services.effects_engine import build_vignette_filter
                vig_filter = build_vignette_filter(vig)
                current_path = await ffmpeg_service.apply_filter_string(current_path, vig_filter)

    elif step_name == "aspect_ratio":
        metadata = state.get("metadata", {})
        target_w = metadata.get("width", 1080)
        target_h = metadata.get("height", 1920)
        from services.aspect_ratio_engine import build_reframe_filter
        reframe_filter = build_reframe_filter(1080, 1920, target_w, target_h)
        current_path = await ffmpeg_service.apply_filter_string(current_path, reframe_filter)

    return current_path


# ── Partial Render Orchestrator ────────────────────────────────────────────────

async def render_edit_state(
    job_id: str,
    user_id: str,
    video_url: str,
) -> str:
    """
    Main render entry point.
    Reads the edit state, identifies dirty vs cached segments,
    re-renders only what's needed, stitches everything together.

    Returns the final Cloudinary URL.
    """
    state = get_edit_state(job_id, user_id)
    if not state:
        raise ValueError(f"Edit state not found for job {job_id}")

    supabase = get_supabase()
    tmp_files = []

    try:
        dirty_ranges = get_dirty_ranges(state)
        timeline = state.get("timeline", [])
        video_path = await _download_video(video_url)
        tmp_files.append(video_path)

        if not dirty_ranges:
            logger.info(f"No dirty segments for job {job_id}, checking cache...")
            # All clean — stitch from cache
            output_path = await _stitch_from_cache(job_id, user_id, state, video_path)
        else:
            logger.info(f"Rendering {len(dirty_ranges)} dirty range(s) for job {job_id}")
            output_path = await _render_dirty_and_stitch(
                job_id, user_id, state, video_path, dirty_ranges, tmp_files
            )

        # Upload final result
        output_path = await ffmpeg_service.export_reel(output_path)
        tmp_files.append(output_path)

        upload_result = cloudinary_service.upload_video_chunked(
            output_path,
            folder=f"auteur/outputs/{user_id}",
        )

        # Clear dirty markers
        clear_dirty(state)
        save_edit_state(state)

        logger.info(f"Partial render complete: {upload_result['secure_url']}")
        return upload_result["secure_url"]

    except Exception as e:
        logger.error(f"Partial render failed: {e}", exc_info=True)
        raise

    finally:
        for p in tmp_files:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


async def _download_video(url: str) -> str:
    """Download video from URL to temp path."""
    import httpx
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in resp.aiter_bytes(65536):
                    f.write(chunk)
    return path


async def _render_dirty_and_stitch(
    job_id: str,
    user_id: str,
    state: Dict[str, Any],
    video_path: str,
    dirty_ranges: List[Dict[str, float]],
    tmp_files: List[str],
) -> str:
    """
    For each dirty range, extract the relevant segments, re-render them,
    and stitch with clean (cached) segments.
    """
    timeline = state.get("timeline", [])

    # Determine which timeline segments overlap with dirty ranges
    dirty_segments = []
    clean_segments = []
    for seg in timeline:
        is_dirty = any(
            seg["timeline_start"] < r["end"] and seg["timeline_end"] > r["start"]
            for r in dirty_ranges
        )
        if is_dirty:
            dirty_segments.append(seg)
        else:
            clean_segments.append(seg)

    logger.info(f"Dirty: {len(dirty_segments)} segments, Clean: {len(clean_segments)} segments")

    # Render dirty segments in parallel for speed
    import asyncio

    async def _render_one_dirty(seg):
        clip = next((c for c in state.get("clips", []) if c["id"] == seg["clip_id"]), None)
        if not clip:
            return None

        segment_path = video_path
        local_tmps = []

        # Step 1: Cut
        cut_path = await ffmpeg_service.cut_and_concat(segment_path, [
            {"start": seg["source_start"], "end": seg["source_end"]}
        ])
        local_tmps.append(cut_path)
        segment_path = cut_path

        # Step 2: Zoom
        zoom_moments = state["effects"].get("transitions", [])
        segment_zooms = [
            zm for zm in zoom_moments
            if seg["timeline_start"] <= zm.get("timestamp", 0) <= seg["timeline_end"]
        ]
        if segment_zooms:
            adjusted = [{
                "timestamp": zm["timestamp"] - seg["timeline_start"],
                "scale": zm.get("scale", 1.3),
                "duration": zm.get("duration", 0.5),
            } for zm in segment_zooms]
            zoom_path = await ffmpeg_service.apply_zoom_moments(segment_path, adjusted)
            local_tmps.append(zoom_path)
            segment_path = zoom_path

        # Step 3: Captions
        segment_captions = [
            cap for cap in state.get("captions", [])
            if seg["timeline_start"] <= cap.get("start", 0) <= seg["timeline_end"]
        ]
        if segment_captions:
            for cap in segment_captions:
                cap["start"] = max(0, cap["start"] - seg["timeline_start"])
                cap["end"] = max(0, cap["end"] - seg["timeline_start"])
            cap_path = await ffmpeg_service.burn_captions(segment_path, segment_captions)
            local_tmps.append(cap_path)
            segment_path = cap_path

        # Step 4: Color grade
        grade = state["effects"].get("color_grade", "none")
        if grade and grade != "none":
            grade_path = await ffmpeg_service.apply_color_grade(segment_path, grade)
            local_tmps.append(grade_path)
            segment_path = grade_path

        # Upload to Cloudinary for caching
        upload_result = cloudinary_service.upload_video_chunked(
            segment_path,
            folder=f"auteur/segments/{user_id}",
        )

        # Save to cache
        content_hash = _hash_segment(state, seg["clip_id"], "full")
        _save_to_cache(
            job_id, user_id, seg["clip_id"], "full",
            seg["timeline_start"], seg["timeline_end"],
            upload_result["secure_url"], upload_result["public_id"],
            content_hash,
        )

        return {
            "seg": seg,
            "url": upload_result["secure_url"],
            "public_id": upload_result["public_id"],
            "_tmps": local_tmps,
        }

    # Run all dirty segments in parallel with concurrency limit
    max_concurrent = 3
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _limited_render(seg):
        async with semaphore:
            return await _render_one_dirty(seg)

    results = await asyncio.gather(*[_limited_render(seg) for seg in dirty_segments])

    rendered_dirty = []
    for r in results:
        if r:
            rendered_dirty.append({
                "seg": r["seg"],
                "url": r["url"],
                "public_id": r["public_id"],
            })
            tmp_files.extend(r.get("_tmps", []))

    # Get clean segment URLs from cache or render fresh
    clean_urls = []
    for seg in clean_segments:
        content_hash = _hash_segment(state, seg["clip_id"], "full")
        cached = _check_cache(job_id, user_id, seg["clip_id"], "full", content_hash)
        if cached:
            clean_urls.append({"seg": seg, "url": cached})
        else:
            # Cold cache — render clean segment
            clip = next((c for c in state.get("clips", []) if c["id"] == seg["clip_id"]), {})
            segment_path = video_path

            cut_path = await ffmpeg_service.cut_and_concat(segment_path, [
                {"start": seg["source_start"], "end": seg["source_end"]}
            ])
            tmp_files.append(cut_path)
            segment_path = cut_path

            grade = state["effects"].get("color_grade", "none")
            if grade and grade != "none":
                grade_path = await ffmpeg_service.apply_color_grade(segment_path, grade)
                tmp_files.append(grade_path)
                segment_path = grade_path

            upload_result = cloudinary_service.upload_video_chunked(
                segment_path,
                folder=f"auteur/segments/{user_id}",
            )
            clean_urls.append({"seg": seg, "url": upload_result["secure_url"]})

            _save_to_cache(
                job_id, user_id, seg["clip_id"], "full",
                seg["timeline_start"], seg["timeline_end"],
                upload_result["secure_url"], upload_result["public_id"],
                content_hash,
            )

    # Download all segments and stitch in order
    import httpx

    all_segments = []
    clean_idx = 0
    dirty_idx = 0
    for seg in timeline:
        if clean_idx < len(clean_segments) and seg["clip_id"] == clean_segments[clean_idx]["clip_id"]:
            all_segments.append(clean_urls[clean_idx])
            clean_idx += 1
        elif dirty_idx < len(dirty_segments) and seg["clip_id"] == dirty_segments[dirty_idx]["clip_id"]:
            all_segments.append(rendered_dirty[dirty_idx])
            dirty_idx += 1

    # Download all segment files
    segment_files = []
    for i, item in enumerate(all_segments):
        seg_path = os.path.join(tempfile.mkdtemp(), f"seg_{i}.mp4")
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("GET", item["url"]) as resp:
                resp.raise_for_status()
                with open(seg_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(65536):
                        f.write(chunk)
        segment_files.append(seg_path)
        tmp_files.append(seg_path)

    # Concat all segments
    list_file = os.path.join(tempfile.mkdtemp(), "concat.txt")
    with open(list_file, "w") as f:
        for sf in segment_files:
            f.write(f"file '{sf}'\n")
    tmp_files.append(list_file)

    output_path = os.path.join(tempfile.mkdtemp(), "stitched.mp4")
    import asyncio

    def _run_concat():
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Concat error: {result.stderr}")
        return output_path

    loop = asyncio.get_event_loop()
    output_path = await loop.run_in_executor(None, _run_concat)

    # Add background music and audio overlays
    if state.get("audio_tracks"):
        for track in state["audio_tracks"]:
            if track["type"] == "sound_effect" and track.get("name"):
                from services.edit_pipeline import _download_sound
                sound_path = await _download_sound(track["name"])
                if sound_path:
                    tmp_files.append(sound_path)
                    sound_path_with_overlay = await ffmpeg_service.add_audio_overlays(
                        output_path,
                        [{"timestamp": track["start"], "audio_path": sound_path, "volume": track["volume"]}],
                    )
                    if sound_path_with_overlay != output_path:
                        tmp_files.append(sound_path_with_overlay)
                        output_path = sound_path_with_overlay

        music_track = next((t for t in state["audio_tracks"] if t["type"] == "music"), None)
        if music_track and music_track.get("name"):
            from services.edit_pipeline import _download_music
            music_path = await _download_music(music_track["name"])
            if music_path:
                tmp_files.append(music_path)
                with_music = await ffmpeg_service.add_background_music(
                    output_path, music_path, music_track["volume"]
                )
                if with_music != output_path:
                    tmp_files.append(with_music)
                    output_path = with_music

    return output_path


async def _stitch_from_cache(
    job_id: str,
    user_id: str,
    state: Dict[str, Any],
    video_path: str,
) -> str:
    """When nothing is dirty, stitch entirely from cache."""
    timeline = state.get("timeline", [])
    segment_urls = []
    import httpx

    for seg in timeline:
        content_hash = _hash_segment(state, seg["clip_id"], "full")
        cached = _check_cache(job_id, user_id, seg["clip_id"], "full", content_hash)
        if cached:
            segment_urls.append({"seg": seg, "url": cached})
        else:
            # Fallback: render fresh
            clip = next((c for c in state.get("clips", []) if c["id"] == seg["clip_id"]), {})
            segment_path = video_path
            cut_path = await ffmpeg_service.cut_and_concat(segment_path, [
                {"start": seg["source_start"], "end": seg["source_end"]}
            ])
            grade = state["effects"].get("color_grade", "none")
            if grade and grade != "none":
                grade_path = await ffmpeg_service.apply_color_grade(cut_path, grade)
                segment_path = grade_path
            else:
                segment_path = cut_path
            upload_result = cloudinary_service.upload_video_chunked(
                segment_path, folder=f"auteur/segments/{user_id}"
            )
            segment_urls.append({"seg": seg, "url": upload_result["secure_url"]})

    tmp_files = []
    segment_files = []
    import httpx

    for i, item in enumerate(segment_urls):
        seg_path = os.path.join(tempfile.mkdtemp(), f"seg_{i}.mp4")
        url = item["url"]
        if url.startswith("/"):
            import shutil
            shutil.copy2(url, seg_path)
        elif "localhost" in url or "127.0.0.1" in url:
            local_path = url.split("/api/video/local/", 1)[-1] if "/api/video/local/" in url else None
            if local_path:
                from core.config import settings as _cfg
                dev_storage = _cfg.dev_storage_path
                full_path = os.path.join(dev_storage, local_path)
                output_path = os.path.join(dev_storage, "output", local_path)
                if os.path.exists(full_path):
                    import shutil
                    shutil.copy2(full_path, seg_path)
                elif os.path.exists(output_path):
                    import shutil
                    shutil.copy2(output_path, seg_path)
                else:
                    async with httpx.AsyncClient(timeout=300) as client:
                        async with client.stream("GET", url) as resp:
                            resp.raise_for_status()
                            with open(seg_path, "wb") as f:
                                async for chunk in resp.aiter_bytes(65536):
                                    f.write(chunk)
            else:
                async with httpx.AsyncClient(timeout=300) as client:
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with open(seg_path, "wb") as f:
                            async for chunk in resp.aiter_bytes(65536):
                                f.write(chunk)
        else:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(seg_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(65536):
                            f.write(chunk)
        segment_files.append(seg_path)
        tmp_files.append(seg_path)

    list_file = os.path.join(tempfile.mkdtemp(), "concat.txt")
    with open(list_file, "w") as f:
        for sf in segment_files:
            f.write(f"file '{sf}'\n")
    tmp_files.append(list_file)

    output_path = os.path.join(tempfile.mkdtemp(), "stitched.mp4")
    import asyncio, subprocess

    def _run():
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Concat error: {result.stderr}")

    await asyncio.get_event_loop().run_in_executor(None, _run)

    for p in tmp_files:
        try:
            if p and os.path.exists(p): os.remove(p)
        except Exception:
            pass

    return output_path
