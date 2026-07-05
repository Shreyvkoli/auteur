"""
Reference Analyzer — Analyze reference videos for style/pacing/caption/clone profiles.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from core.database import get_supabase
from core.config import settings

logger = logging.getLogger(__name__)

# Default heuristics when no ref analysis available
DEFAULT_PACING_THRESHOLD_SEC = 60
DEFAULT_CUT_INTERVAL_SEC = 3.0
DEFAULT_STYLE_TAGS = ["fast-paced", "trending", "caption-heavy"]
DEFAULT_COLOR_TONE = "warm"
DEFAULT_CAPTION_STYLE = "dynamic"
DEFAULT_MUSIC_VIBE = "trending"


async def analyze_reference_video(
    reference_url: str,
    user_id: str,
    profile_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze a reference video URL and create a style profile."""
    profile_id = str(uuid4())
    profile_name = profile_name or f"ref_{datetime.utcnow().isoformat()[:10]}"

    # Try to extract metadata via ffprobe
    duration = 0
    try:
        import subprocess
        local_path = reference_url.replace(settings.dev_api_url, "").lstrip("/")
        if local_path and not local_path.startswith("http"):
            local_path = os.path.join(settings.dev_storage_path, os.path.basename(local_path))
        else:
            local_path = reference_url
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", local_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data.get("format", {}).get("duration", 0))
    except Exception as e:
        logger.warning(f"ffprobe failed for reference: {e}")

    detected_pacing = "medium" if duration < DEFAULT_PACING_THRESHOLD_SEC else "fast"
    estimated_cuts = max(1, int(duration / DEFAULT_CUT_INTERVAL_SEC))

    style_data = {
        "profile_id": profile_id,
        "name": profile_name,
        "reference_url": reference_url,
        "duration": duration,
        "detected_pacing": detected_pacing,
        "estimated_cuts": estimated_cuts,
        "color_tone": DEFAULT_COLOR_TONE,
        "caption_style": DEFAULT_CAPTION_STYLE,
        "music_vibe": DEFAULT_MUSIC_VIBE,
        "created_at": datetime.utcnow().isoformat(),
    }

    analysis = {
        "duration": duration,
        "estimated_clips": estimated_cuts,
        "avg_clip_duration": DEFAULT_CUT_INTERVAL_SEC if duration > 0 else 0,
        "style_tags": DEFAULT_STYLE_TAGS,
    }

    supabase = get_supabase()
    supabase.table("reference_profiles").insert(style_data.copy()).execute()
    logger.info(f"Reference profile {profile_id} created for {reference_url}")

    return {
        "profile_id": profile_id,
        "style_data": style_data,
        "analysis": analysis,
    }


async def apply_reference_style(
    state: Dict[str, Any],
    profile_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Apply a reference style profile to the current edit state."""
    supabase = get_supabase()
    result = supabase.table("reference_profiles").select("*").eq("profile_id", profile_id).single().execute()
    profile = result.data or {}

    applied_patches = []

    if profile.get("caption_style"):
        state["effects"]["color_grade"] = profile.get("color_tone", "warm")
        applied_patches.append("color_grade")

    if profile.get("music_vibe"):
        state["audio_tracks"] = state.get("audio_tracks", [])
        if not state["audio_tracks"]:
            state["audio_tracks"] = [{
                "id": f"track_{uuid4().hex[:12]}",
                "type": "music",
                "source_url": "",
                "start": 0,
                "duration": state.get("metadata", {}).get("total_duration", 0),
                "volume": 0.25,
                "name": profile["music_vibe"],
            }]
            applied_patches.append("music_vibe")

    logger.info(f"Reference profile {profile_id} applied to edit")
    return {
        "state": state,
        "applied_patches": applied_patches,
    }
