"""
Style Consistency Engine — Apply global style across all chunks/segments.

Problem: When processing vlog chunks independently, each chunk may get
a different style. This engine ensures the entire video maintains a
consistent look and feel based on the user's chosen style profile.
"""

import logging
from typing import Dict, Any, List, Optional

from services.creator_memory import get_style_profile_for_user

logger = logging.getLogger(__name__)


def enforce_global_style(
    edit_plan: Dict[str, Any],
    style_profile: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    mode: str = "reels",
) -> Dict[str, Any]:
    """
    Enforce style consistency on an edit plan.
    Priority: style_profile > creator_memory > defaults.
    """
    if not style_profile and user_id:
        style_profile = get_style_profile_for_user(user_id)

    plan = edit_plan.copy()

    if not style_profile:
        return plan

    # ── Caption style ──────────────────────────────────────────────────────
    preferred_caption_style = style_profile.get("caption_style")
    if isinstance(preferred_caption_style, str) and preferred_caption_style:
        # Map from style_profile format to caption style keys
        style_map = {
            "yellow": "bold_yellow_center",
            "white": "bold_white_center",
            "center": "bold_white_center",
            "top": "bold_white_top",
        }
        mapped = style_map.get(preferred_caption_style.lower(), preferred_caption_style)
        captions = plan.get("captions", [])
        for cap in captions:
            cap["style"] = mapped

    # ── Music ──────────────────────────────────────────────────────────────
    music_vibe = plan.get("music_vibe", "")
    preferred_music = style_profile.get("music_vibe")
    if preferred_music and (not music_vibe or music_vibe.lower() in ("no music", "")):
        plan["music_vibe"] = preferred_music

    # ── Color grade ────────────────────────────────────────────────────────
    color_grade = plan.get("color_grade", "none")
    preferred_grade = style_profile.get("color_grade")
    if preferred_grade and (not color_grade or color_grade == "none"):
        plan["color_grade"] = preferred_grade

    # ── Energy/pacing ──────────────────────────────────────────────────────
    preferred_pacing = style_profile.get("preferred_pacing", "medium")
    if preferred_pacing == "fast":
        plan = _apply_fast_pacing(plan)
    elif preferred_pacing == "slow":
        plan = _apply_slow_pacing(plan)

    # ── Hook pattern ───────────────────────────────────────────────────────
    hook_pattern = style_profile.get("hook_pattern", "")
    if hook_pattern and not plan.get("hook"):
        plan["hook"] = {"pattern": hook_pattern}

    # ── Blur background ────────────────────────────────────────────────────
    if style_profile.get("blur_background"):
        plan["blur_background"] = True

    # ── Meme frequency ────────────────────────────────────────────────────
    meme_freq = style_profile.get("meme_frequency", "none")
    if mode == "vlog" and meme_freq == "none":
        plan["meme_sounds"] = []
    elif meme_freq == "high":
        pass  # Keep AI-generated meme sounds

    return plan


def enforce_consistency_across_chunks(
    chunks: List[Dict[str, Any]],
    global_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Apply the same global style profile to all vlog chunks.
    This ensures: same caption style, same music, same color grade everywhere.
    """
    consistent = []
    for i, chunk in enumerate(chunks):
        plan = chunk.get("edit_plan", chunk)
        plan["color_grade"] = global_profile.get("color_grade", plan.get("color_grade", "warm"))
        plan["music_vibe"] = global_profile.get("music_vibe", plan.get("music_vibe", "lo-fi"))

        captions = plan.get("captions", [])
        preferred_style = global_profile.get("caption_style", "bold_white_center")
        style_map = {
            "yellow": "bold_yellow_center",
            "white": "bold_white_center",
            "center": "bold_white_center",
            "top": "bold_white_top",
        }
        mapped = style_map.get(preferred_style.lower(), preferred_style)
        for cap in captions:
            cap["style"] = mapped

        chunk["edit_plan"] = plan
        consistent.append(chunk)

    logger.info(f"Style consistency enforced across {len(chunks)} chunks")
    return consistent


def _apply_fast_pacing(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Adjust plan for fast pacing."""
    cuts = plan.get("cuts", [])
    if cuts and len(cuts) > 3:
        plan["total_duration"] = min(plan.get("total_duration", 60), 45)
    return plan


def _apply_slow_pacing(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Adjust plan for slow pacing."""
    plan["meme_sounds"] = []
    return plan
