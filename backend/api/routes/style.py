"""
Style Route — Reference video style analysis via GPT-4o Vision.

Flow:
  POST /style/analyze-ref
    1. yt-dlp se ref video download (temp)
    2. FFmpeg se frames extract (har 3 sec, max 20)
    3. GPT-4o Vision se style JSON extract
    4. Supabase style_profiles table mein save
    5. Temp video delete
    6. Style badges return
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from uuid import uuid4
from core.database import get_supabase
from core.security import get_current_user
from services import yt_dlp_service, ffmpeg_service, gpt_service
import logging
import asyncio

router = APIRouter(prefix="/style", tags=["style"])
logger = logging.getLogger(__name__)


class AnalyzeRefRequest(BaseModel):
    url: str  # YouTube / Instagram / TikTok URL


class StyleBadge(BaseModel):
    icon: str
    label: str
    value: str


class AnalyzeRefResponse(BaseModel):
    profile_id: str
    style_json: Dict[str, Any]
    badges: List[StyleBadge]


class StyleDNAResponse(BaseModel):
    avg_cut_duration_seconds: float
    caption_style: Dict[str, Any]
    energy_level: int
    hook_pattern: str
    transition_type: str
    music_vibe: str


def _build_badges(style: Dict[str, Any]) -> List[StyleBadge]:
    """Convert style JSON into human-readable badges for frontend."""
    badges = []

    energy = style.get("energy_level", 5)
    if energy >= 8:
        badges.append(StyleBadge(icon="⚡", label="Energy", value="High Energy"))
    elif energy >= 5:
        badges.append(StyleBadge(icon="🔥", label="Energy", value="Mid Energy"))
    else:
        badges.append(StyleBadge(icon="😌", label="Energy", value="Chill Vibe"))

    cut_speed = style.get("cut_speed_seconds", 3)
    if cut_speed <= 2:
        badges.append(StyleBadge(icon="✂️", label="Cuts", value="Fast Cuts"))
    elif cut_speed <= 4:
        badges.append(StyleBadge(icon="✂️", label="Cuts", value="Medium Cuts"))
    else:
        badges.append(StyleBadge(icon="✂️", label="Cuts", value="Slow Cuts"))

    music = style.get("music_vibe", "")
    if music and music.lower() != "no music":
        icons = {"lo-fi": "🎵", "trap": "🔊", "cinematic": "🎼"}
        badges.append(StyleBadge(icon=icons.get(music.lower(), "🎵"), label="Music", value=music.title()))

    meme_freq = style.get("meme_frequency", "none")
    if meme_freq in ("medium", "high"):
        badges.append(StyleBadge(icon="😂", label="Memes", value="Meme Heavy"))

    hook = style.get("hook_pattern", "")
    if hook:
        badges.append(StyleBadge(icon="🪝", label="Hook", value=hook.title()))

    color = style.get("color_grade", "")
    if color and color != "none":
        grade_icons = {"warm": "🌅", "cool": "❄️", "cinematic": "🎬", "vibrant": "🌈"}
        badges.append(StyleBadge(icon=grade_icons.get(color, "🎨"), label="Grade", value=color.title()))

    return badges


@router.post("/analyze-ref", response_model=AnalyzeRefResponse)
async def analyze_reference_video(
    request: AnalyzeRefRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Download a YouTube reference video, extract frames,
    analyse editing style with GPT-4o Vision, return style profile + badges.
    """
    supabase = get_supabase()
    frame_paths = []
    output_dir = None

    try:
        # 1. Download ref video temporarily
        logger.info(f"Downloading ref video: {request.url}")
        try:
            ref = await yt_dlp_service.download_ref_video(request.url)
            video_path = ref["video_path"]
            output_dir = ref["output_dir"]
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not download reference video: {str(e)[:200]}"
            )

        # 2. Extract frames every 3 seconds (max 20)
        logger.info("Extracting frames for style analysis...")
        try:
            frame_paths = await ffmpeg_service.extract_frames(video_path, interval_sec=3, max_frames=20)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Frame extraction failed: {str(e)[:200]}"
            )

        if not frame_paths:
            raise HTTPException(status_code=400, detail="No frames could be extracted from the video")

        # 3. GPT-4o Vision style analysis
        logger.info(f"Analysing {len(frame_paths)} frames with GPT-4o Vision...")
        try:
            style_json = await gpt_service.analyze_style_from_frames(frame_paths)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Style analysis failed: {str(e)[:200]}"
            )

        # 4. Save to style_profiles table
        profile_id = str(uuid4())
        supabase.table("style_profiles").insert({
            "id":         profile_id,
            "user_id":    current_user["id"],
            "source_url": request.url,
            "style_json": style_json,
        }).execute()

        logger.info(f"Style profile saved: {profile_id}")

        # 5. Build badges
        badges = _build_badges(style_json)

        return AnalyzeRefResponse(
            profile_id=profile_id,
            style_json=style_json,
            badges=badges,
        )

    finally:
        # Always clean up temp files
        import os
        for fp in frame_paths:
            try:
                os.remove(fp)
            except Exception:
                pass
        if output_dir:
            yt_dlp_service.cleanup_ref_video(output_dir)


@router.get("/profiles")
async def get_style_profiles(current_user: dict = Depends(get_current_user)):
    """Get all style profiles saved by this user."""
    supabase = get_supabase()
    profiles = supabase.table("style_profiles").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return profiles.data


@router.get("/dna", response_model=Optional[StyleDNAResponse])
async def get_style_dna(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    user = supabase.table("users").select("style_dna").eq("id", current_user["id"]).single().execute()
    if not user.data or not user.data.get("style_dna"):
        return None
    return StyleDNAResponse(**user.data["style_dna"])


@router.get("/profile")
async def get_style_profile(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    user = supabase.table("users").select("style_dna, plan").eq("id", current_user["id"]).single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "style_dna": user.data.get("style_dna"),
        "plan": user.data.get("plan"),
        "has_style": bool(user.data.get("style_dna")),
    }