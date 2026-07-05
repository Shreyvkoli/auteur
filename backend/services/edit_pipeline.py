"""
Edit Pipeline — Main Worker (Flows 4 → 5 → 6 → 7)
Updated with ref video analysis integration, style merging, and changelog.
"""

import asyncio
import json
import os
import tempfile
import logging
import httpx
from typing import Dict, Any, Optional, List

from core.database import get_supabase
from core.config import settings
from services import ffmpeg_service, whisper_service, gpt_service, cloudinary_service
from services.edit_state import edit_plan_to_state, get_edit_state, save_edit_state, push_undo
from services.edit_quality import evaluate_edit_plan, save_quality_score, build_regeneration_feedback
from services.creator_memory import (
    get_or_create_memory, update_memory_from_edit,
    apply_memory_to_plan, get_style_profile_for_user,
    store_pacing_curve, store_caption_density, store_editing_frequency,
)
from services.style_consistency import enforce_global_style
from services.partial_render import render_edit_state
from services.edit_intelligence import generate_edit_plan as generate_intelligent_edit_plan
from services.vault_enhanced import suggest_vault_during_planning, rank_vault_by_relevance
from services.style_merger import merge_style_profiles, store_composite_style, generate_changelog
from services.metrics import track_edit_quality, track_vault_usage

logger = logging.getLogger(__name__)

_ASSETS_BASE_URL = settings.assets_base_url

MEME_SOUND_URLS: Dict[str, str] = {
    "bruh":       f"{_ASSETS_BASE_URL}/sounds/bruh.mp3",
    "vine_boom":  f"{_ASSETS_BASE_URL}/sounds/vine_boom.mp3",
    "air_horn":   f"{_ASSETS_BASE_URL}/sounds/air_horn.mp3",
    "sad_violin": f"{_ASSETS_BASE_URL}/sounds/sad_violin.mp3",
    "bonk":       f"{_ASSETS_BASE_URL}/sounds/bonk.mp3",
}

MUSIC_TRACK_URLS: Dict[str, str] = {
    "lo-fi":       f"{_ASSETS_BASE_URL}/music/lofi_bg.mp3",
    "trap":        f"{_ASSETS_BASE_URL}/music/trap_bg.mp3",
    "cinematic":   f"{_ASSETS_BASE_URL}/music/cinematic_bg.mp3",
    "no music":    "",
    "no_music":    "",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _download_file(url: str, suffix: str = ".mp4") -> str:
    """Download a file from URL to a temp path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in resp.aiter_bytes(65536):
                    f.write(chunk)
    return path


async def _download_sound(sound_name: str) -> Optional[str]:
    """Download a meme sound to temp file. Returns path or None."""
    url = MEME_SOUND_URLS.get(sound_name)
    if not url:
        return None
    try:
        return await _download_file(url, suffix=".mp3")
    except Exception as e:
        logger.warning(f"Could not download sound '{sound_name}': {e}")
        return None


def _cleanup(*paths: str) -> None:
    """Remove temp files quietly."""
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


async def _update_progress(job_id: str, progress: int, status: str, message: str = "") -> None:
    """Update job progress in Supabase."""
    try:
        supabase = get_supabase()
        supabase.table("edit_jobs").update({
            "progress": progress,
            "status": status,
        }).eq("id", job_id).execute()
        logger.info(f"[Job {job_id[:8]}] {status} — {progress}% {message}")
    except Exception as e:
        logger.error(f"Progress update error: {e}")


# ── Ref Video Analysis ─────────────────────────────────────────────────────────

async def _analyze_ref_videos(
    ref_video_ids: List[str],
    user_id: str,
    job_id: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Analyze all reference videos. Returns (profiles, composite_style).
    Each ref is downloaded, frames extracted, and style analyzed via GPT.
    """
    supabase = get_supabase()
    profiles = []
    ref_sources = []

    for idx, ref_id in enumerate(ref_video_ids):
        await _update_progress(
            job_id, 5, "analyzing_style",
            f"Analysing ref video {idx + 1}/{len(ref_video_ids)}..."
        )

        # Get ref video record
        ref = supabase.table("videos").select("*").eq("id", ref_id).eq("user_id", user_id).single().execute()
        if not ref.data:
            logger.warning(f"Ref video {ref_id} not found, skipping")
            continue

        ref_url = ref.data.get("cloudinary_url", "")
        if not ref_url:
            logger.warning(f"Ref video {ref_id} has no URL, skipping")
            continue

        frame_paths = []
        video_path = None
        output_dir = None

        try:
            # Check if it's a YouTube URL or local file
            if ref_url.startswith("http") and "youtube" in ref_url:
                from services.yt_dlp_service import download_ref_video, cleanup_ref_video
                dl = await download_ref_video(ref_url)
                video_path = dl["video_path"]
                output_dir = dl["output_dir"]
            else:
                # Local file or direct URL
                video_path = await _download_file(ref_url, suffix=".mp4")

            # Extract frames
            frame_paths = await ffmpeg_service.extract_frames(video_path, interval_sec=3, max_frames=20)

            if frame_paths:
                # Analyze via GPT
                style_json = await gpt_service.analyze_style_from_frames(frame_paths)
                style_json["_ref_video_id"] = ref_id
                style_json["_ref_filename"] = ref.data.get("filename", f"ref_{idx}")
                style_json["_ref_duration"] = ref.data.get("duration", 0)
                profiles.append(style_json)
                ref_sources.append({
                    "ref_id": ref_id,
                    "filename": ref.data.get("filename", f"ref_{idx}"),
                    "contributed": {
                        "music_vibe": style_json.get("music_vibe"),
                        "color_grade": style_json.get("color_grade"),
                        "energy_level": style_json.get("energy_level"),
                        "caption_style": style_json.get("caption_style"),
                        "hook_pattern": style_json.get("hook_pattern"),
                    }
                })
                logger.info(f"Ref {ref_id} analysed: energy={style_json.get('energy_level')}, vibe={style_json.get('music_vibe')}")
            else:
                logger.warning(f"No frames extracted from ref {ref_id}")

        except Exception as e:
            logger.error(f"Ref analysis failed for {ref_id}: {e}")
        finally:
            for fp in frame_paths:
                try:
                    os.remove(fp)
                except Exception:
                    pass
            if output_dir:
                from services.yt_dlp_service import cleanup_ref_video
                cleanup_ref_video(output_dir)
            if video_path and video_path != ref_url and output_dir is None:
                try:
                    os.remove(video_path)
                except Exception:
                    pass

    # Merge all profiles
    composite = merge_style_profiles(profiles) if profiles else get_style_profile_for_user(user_id)

    # Store ref contributions for summary
    composite["_ref_sources"] = ref_sources
    composite["_num_refs"] = len(ref_sources)

    # Save composite style
    if profiles:
        store_composite_style(user_id, job_id, composite, ref_video_ids)
        logger.info(f"Composite style saved for job {job_id} from {len(profiles)} refs")

    return profiles, composite


# ── Main Pipeline ─────────────────────────────────────────────────────────────

async def run_edit_pipeline(job_id: str, payload: Dict[str, Any]) -> None:
    """
    Full edit pipeline for one job.
    payload: {video_id, user_id, prompt, version_type, ref_video_ids, style_profile, vault_items, mode}
    """
    supabase = get_supabase()
    tmp_files = []

    try:
        await _update_progress(job_id, 2, "transcribing", "Queued — starting your edit...")

        # ── Fetch video record ──────────────────────────────────────────────
        video_id  = payload["video_id"]
        prompt    = payload.get("prompt", "")
        version   = payload.get("version_type", "viral")
        vault_items = payload.get("vault_items") or []
        style_profile = payload.get("style_profile")
        mode = payload.get("mode", "reels")
        ref_video_ids = payload.get("ref_video_ids") or []

        video_row = supabase.table("videos").select("*").eq("id", video_id).single().execute()
        if not video_row.data:
            raise ValueError(f"Video {video_id} not found")

        cloudinary_url_val = video_row.data.get("cloudinary_url")
        video_duration = video_row.data.get("duration", 0)

        if not cloudinary_url_val:
            raise ValueError("Video has no URL")

        # ── Load creator memory ────────────────────────────────────────────
        user_id = payload["user_id"]
        memory = get_or_create_memory(user_id)
        creator_style = get_style_profile_for_user(user_id)

        # ── Step 1: Analyze Ref Videos (if any) ─────────────────────────────
        composite_style = None
        ref_profiles = []
        ref_sources = []

        if ref_video_ids:
            await _update_progress(job_id, 3, "analyzing_style", f"Analysing {len(ref_video_ids)} reference videos...")
            ref_profiles, composite_style = await _analyze_ref_videos(ref_video_ids, user_id, job_id)
            ref_sources = composite_style.get("_ref_sources", [])
        else:
            composite_style = style_profile or creator_style

        # Merge provided style_profile with composite/creator style
        if style_profile and not ref_video_ids:
            style_profile = style_profile
        else:
            style_profile = composite_style or creator_style

        # ── Step 2: Download video locally ─────────────────────────────────
        await _update_progress(job_id, 6, "transcribing", "Downloading your video...")
        video_path = await _download_file(cloudinary_url_val, suffix=".mp4")
        tmp_files.append(video_path)

        # ── Step 3: Transcribe ─────────────────────────────────────────────
        await _update_progress(job_id, 10, "transcribing", "Extracting audio...")
        transcript = []

        try:
            audio_path = await ffmpeg_service.extract_audio(video_path)
            tmp_files.append(audio_path)

            await _update_progress(job_id, 20, "transcribing", "AI is listening to your video...")
            transcript = await whisper_service.transcribe(audio_path)
        except ValueError as e:
            if "no audio track" in str(e).lower():
                logger.info(f"Video has no audio track, creating placeholder transcript")
                transcript = [{"word": "[no audio]", "start": 0.0, "end": video_duration}]
            else:
                raise

        # Save transcript to DB
        supabase.table("videos").update({
            "transcript": transcript,
        }).eq("id", video_id).execute()

        await _update_progress(job_id, 25, "generating_plan", "Transcript ready!")

        # ── Step 4: Generate Edit Plan ─────────────────────────────────────
        await _update_progress(job_id, 28, "generating_plan", "Building your edit plan...")

        # Build style context string from ref analysis
        ref_context = ""
        if ref_sources:
            ref_lines = []
            for i, rs in enumerate(ref_sources):
                ref_lines.append(f"Ref {i + 1} ({rs['filename']}): {json.dumps(rs['contributed'])}")
            ref_context = "\n".join(ref_lines)
            ref_context = f"\n\nReference video style analysis:\n{ref_context}"

        # Vault intelligence
        vault_context = ""
        if vault_items:
            suggested_vault = await suggest_vault_during_planning(
                transcript=json.dumps(transcript, ensure_ascii=False),
                vault_items=vault_items,
                version_type=version,
            )
            if suggested_vault:
                vault_names = [v.get("name", "") for v in suggested_vault[:5]]
                vault_context = f"\n\nSuggested vault items: {', '.join(vault_names)}"

        # Use Intelligence Layer (multi-pass: generate → self-critique → improve → lock)
        intelligence_result = await generate_intelligent_edit_plan(
            transcript=json.dumps(transcript, ensure_ascii=False),
            style=version,
            user_id=user_id,
            vault_context=vault_context + ref_context,
            project_id=job_id,
        )

        edit_plan = intelligence_result.get("plan", {})
        story_confidence = intelligence_result.get("story_confidence", 6.0)

        # ── Step 5: Quality Check + Auto-Regeneration ──────────────────────
        quality = evaluate_edit_plan(edit_plan, transcript, mode, version)
        save_quality_score(job_id, user_id, quality)
        await track_edit_quality(job_id, quality.get("scores", {}), quality.get("overall_score", 0))

        max_attempts = settings.max_regeneration_attempts
        attempt = 0
        while not quality["passed"] and attempt < max_attempts:
            attempt += 1
            feedback = build_regeneration_feedback(quality)
            logger.info(f"[Job {job_id[:8]}] Quality FAILED ({quality['overall_score']:.1f}), regenerating (attempt {attempt})...")

            await _update_progress(job_id, 30, "generating_plan", f"Improving edit plan (attempt {attempt})...")

            intelligence_result = await generate_intelligent_edit_plan(
                transcript=json.dumps(transcript, ensure_ascii=False),
                style=version,
                user_id=user_id,
                vault_context=vault_context + ref_context + f"\n\nFeedback: {feedback}",
                project_id=job_id,
            )
            edit_plan = intelligence_result.get("plan", {})
            quality = evaluate_edit_plan(edit_plan, transcript, mode, version)
            save_quality_score(job_id, user_id, quality)

        if quality["passed"]:
            logger.info(f"[Job {job_id[:8]}] Quality PASSED ({quality['overall_score']:.1f}) after {attempt} regen(s)")
        else:
            logger.warning(f"[Job {job_id[:8]}] Quality BELOW threshold ({quality['overall_score']:.1f}), proceeding anyway")

        # ── Step 6: Apply Style Consistency ────────────────────────────────
        edit_plan = enforce_global_style(edit_plan, style_profile, user_id, mode)

        # Save edit plan to job
        supabase.table("edit_jobs").update({
            "edit_plan": edit_plan,
        }).eq("id", job_id).execute()

        # ── Step 7: Create Edit State ──────────────────────────────────────
        await _update_progress(job_id, 35, "rendering", "Building edit timeline...")
        edit_state = edit_plan_to_state(
            edit_plan=edit_plan,
            job_id=job_id,
            user_id=user_id,
            video_id=video_id,
            source_url=cloudinary_url_val,
            video_duration=video_duration,
            mode=mode,
        )

        save_edit_state(edit_state)

        # ── Step 8: Update Creator Memory ──────────────────────────────────
        update_memory_from_edit(user_id, edit_plan)

        try:
            cuts = edit_plan.get("cuts", [])
            captions = edit_plan.get("captions", [])
            total_edits = len(cuts) + len(captions) + len(edit_plan.get("zoom_moments", []))
            edits_per_minute = (total_edits / max(1, video_duration)) * 60

            store_pacing_curve(user_id, video_duration, cuts)
            store_caption_density(user_id, video_duration, captions)
            store_editing_frequency(user_id, video_duration, edits_per_minute)
        except Exception as e:
            logger.warning(f"Creator memory time-series update failed: {e}")

        if vault_items:
            vault_used = [v for v in vault_items if v.get("relevance_score", 0) >= 7]
            await track_vault_usage(
                job_id,
                vault_clips_used=len(vault_used),
                total_suggestions=len(vault_items),
                relevance_scores=[v.get("relevance_score", 5) for v in vault_items],
            )

        # ── Step 9: Render ─────────────────────────────────────────────────
        await _update_progress(job_id, 50, "rendering", "Starting render...")

        output_url = await render_edit_state(
            job_id=job_id,
            user_id=user_id,
            video_url=cloudinary_url_val,
        )

        # ── Step 10: Save output ───────────────────────────────────────────
        from uuid import uuid4 as _uuid4
        output_id = str(_uuid4())
        supabase.table("output_videos").insert({
            "id":            output_id,
            "job_id":        job_id,
            "version_type":  version,
            "cloudinary_url":       output_url,
            "cloudinary_public_id": "",
            "edit_plan":     edit_plan,
        }).execute()

        # ── Step 11: Generate Changelog ────────────────────────────────────
        edited_duration = edit_plan.get("total_duration", video_duration)
        changelog = generate_changelog(
            original_duration=video_duration,
            edited_duration=edited_duration,
            composite_style=composite_style or style_profile or {},
            profiles=ref_profiles,
            edit_plan=edit_plan,
        )

        supabase.table("edit_jobs").update({
            "changelog": changelog,
        }).eq("id", job_id).execute()

        # Calculate style match score
        if ref_profiles:
            base_score = 60
            per_ref_bonus = min(len(ref_profiles) * 10, 30)
            quality_bonus = int(quality.get("overall_score", 6) * 5)
            style_match = min(100, base_score + per_ref_bonus + quality_bonus)
            changelog["style_match_score"] = style_match

        await _update_progress(job_id, 100, "completed", "Your edit is ready!")
        logger.info(f"[Job {job_id[:8]}] DONE → {output_url}")

    except Exception as e:
        logger.error(f"[Job {job_id[:8]}] FAILED: {e}", exc_info=True)
        supabase = get_supabase()
        supabase.table("edit_jobs").update({
            "status": "failed",
            "progress": 0,
            "error": str(e),
        }).eq("id", job_id).execute()

    finally:
        _cleanup(*tmp_files)


# ── Refinement Pipeline ───────────────────────────────────────────────────────

async def run_refine_pipeline(job_id: str, payload: Dict[str, Any]) -> None:
    """
    Partial re-render pipeline for vibe iteration.
    Now uses Edit State + Prompt Editor + Partial Render.
    """
    supabase = get_supabase()
    tmp_files = []

    try:
        await _update_progress(job_id, 10, "generating_plan", "Applying refinement...")

        original_plan     = payload["original_edit_plan"]
        refinement_prompt = payload["refinement_prompt"]
        version           = payload.get("version_type", "viral")
        video_id          = payload["video_id"]
        user_id           = payload["user_id"]
        original_job_id   = payload.get("original_job_id", job_id)

        # Try using prompt editor on existing edit state first
        edit_state = get_edit_state(original_job_id, user_id)
        if edit_state:
            logger.info(f"Using prompt editor for refinement on job {original_job_id}")
            from services.prompt_editor import process_prompt as process_edit_prompt
            result = await process_edit_prompt(original_job_id, user_id, refinement_prompt)

            updated_state = get_edit_state(original_job_id, user_id)
            if updated_state and result.get("needs_render"):
                await _update_progress(job_id, 40, "rendering", "Re-rendering with changes...")
                video_row = supabase.table("videos").select("cloudinary_url").eq("id", video_id).single().execute()

                video_path = await _download_file(video_row.data["cloudinary_url"], suffix=".mp4")
                tmp_files.append(video_path)

                output_url = await render_edit_state(
                    job_id=original_job_id,
                    user_id=user_id,
                    video_url=video_row.data["cloudinary_url"],
                )

                from uuid import uuid4 as _uuid4
                supabase.table("iterations").insert({
                    "id": str(_uuid4()),
                    "job_id": original_job_id,
                    "version": version,
                    "refinement_prompt": refinement_prompt,
                    "updated_plan": updated_state,
                    "output_url": output_url,
                }).execute()

                supabase.table("output_videos").insert({
                    "id": str(_uuid4()),
                    "job_id": job_id,
                    "version_type": version,
                    "cloudinary_url": output_url,
                    "cloudinary_public_id": "",
                    "edit_plan": updated_state,
                }).execute()

                # Regenerate changelog
                original_job = supabase.table("edit_jobs").select("*").eq("id", original_job_id).single().execute()
                original_duration = 0
                if original_job.data:
                    video_rec = supabase.table("videos").select("duration").eq("id", video_id).single().execute()
                    if video_rec.data:
                        original_duration = video_rec.data.get("duration", 0)

                new_changelog = generate_changelog(
                    original_duration=original_duration,
                    edited_duration=updated_state.get("metadata", {}).get("total_duration", 0),
                    composite_style={},
                    profiles=[],
                    edit_plan=updated_state,
                )
                supabase.table("edit_jobs").update({
                    "changelog": new_changelog,
                }).eq("id", original_job_id).execute()

                await _update_progress(job_id, 100, "completed", "Refined edit ready!")
                return

        # Fallback: old refinement path
        await _update_progress(job_id, 15, "generating_plan", "Generating refinement changes...")
        changes = await gpt_service.refine_edit_plan(original_plan, refinement_prompt)
        updated_plan = gpt_service.merge_edit_plan(original_plan, changes)

        from uuid import uuid4 as _uuid4
        supabase.table("iterations").insert({
            "id":               str(_uuid4()),
            "job_id":           original_job_id,
            "version":          version,
            "refinement_prompt": refinement_prompt,
            "updated_plan":     updated_plan,
            "output_url":       "",
        }).execute()

        await _update_progress(job_id, 40, "rendering", "Re-rendering with changes...")

        video_row = supabase.table("videos").select("cloudinary_url").eq("id", video_id).single().execute()
        if not video_row.data:
            raise ValueError("Original video not found")

        video_path = await _download_file(video_row.data["cloudinary_url"], suffix=".mp4")
        tmp_files.append(video_path)

        changed_keys = set(changes.keys())
        current_video = video_path

        cuts = updated_plan.get("cuts", [])
        if cuts:
            current_video = await ffmpeg_service.cut_and_concat(video_path, cuts)
            tmp_files.append(current_video)

        if "zoom_moments" in changed_keys and updated_plan.get("zoom_moments"):
            zoomed = await ffmpeg_service.apply_zoom_moments(current_video, updated_plan["zoom_moments"])
            tmp_files.append(zoomed)
            current_video = zoomed

        if "captions" in changed_keys and updated_plan.get("captions"):
            captioned = await ffmpeg_service.burn_captions(current_video, updated_plan["captions"])
            tmp_files.append(captioned)
            current_video = captioned

        if "meme_sounds" in changed_keys and updated_plan.get("meme_sounds"):
            overlays = []
            for ms in updated_plan["meme_sounds"]:
                sp = await _download_sound(ms.get("sound", ""))
                if sp:
                    tmp_files.append(sp)
                    overlays.append({"timestamp": ms["timestamp"], "audio_path": sp, "volume": 0.8})
            if overlays:
                with_sounds = await ffmpeg_service.add_audio_overlays(current_video, overlays)
                tmp_files.append(with_sounds)
                current_video = with_sounds

        if "color_grade" in changed_keys:
            graded = await ffmpeg_service.apply_color_grade(current_video, updated_plan.get("color_grade", "warm"))
            tmp_files.append(graded)
            current_video = graded

        final_path = await ffmpeg_service.export_reel(current_video)
        tmp_files.append(final_path)

        await _update_progress(job_id, 85, "finalizing", "Uploading refined edit...")

        upload_result = cloudinary_service.upload_video_chunked(
            final_path,
            folder=f"auteur/outputs/{user_id}",
        )
        output_url = upload_result["secure_url"]

        supabase.table("iterations").update({
            "output_url": output_url,
        }).eq("job_id", original_job_id).order("created_at", desc=True).limit(1).execute()

        supabase.table("output_videos").insert({
            "id":            str(_uuid4()),
            "job_id":        job_id,
            "version_type":  version,
            "cloudinary_url":       output_url,
            "cloudinary_public_id": upload_result["public_id"],
            "edit_plan":     updated_plan,
        }).execute()

        # Regenerate changelog
        new_changelog = generate_changelog(
            original_duration=updated_plan.get("total_duration", 0),
            edited_duration=updated_plan.get("total_duration", 0),
            composite_style={},
            profiles=[],
            edit_plan=updated_plan,
        )
        supabase.table("edit_jobs").update({
            "changelog": new_changelog,
        }).eq("id", original_job_id).execute()

        await _update_progress(job_id, 100, "completed", "Refined edit ready!")

    except Exception as e:
        logger.error(f"[Refine {job_id[:8]}] FAILED: {e}", exc_info=True)
        supabase = get_supabase()
        supabase.table("edit_jobs").update({
            "status": "failed",
            "error": str(e),
        }).eq("id", job_id).execute()

    finally:
        _cleanup(*tmp_files)
