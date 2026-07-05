"""
Creator Memory — Per-user style preferences that persist across edits.

This is the "moat" — over time, the system learns each creator's
preferred pacing, caption style, music taste, color grading, etc.
And automatically applies them to future edits.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4

from core.database import get_supabase

logger = logging.getLogger(__name__)

DEFAULT_MEMORY = {
    "preferred_pacing": "medium",
    "caption_style": "bold_white_center",
    "music_vibe": "lo-fi",
    "color_grade": "warm",
    "energy_level": 5,
    "avg_cut_duration": 3.0,
    "hook_pattern": "question hook",
    "vault_usage_freq": "low",
    "style_json": {},
    "edit_count": 0,
}


def get_creator_memory(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the creator memory for a user."""
    supabase = get_supabase()
    result = (
        supabase.table("creator_memories")
        .select("*")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        return None
    return result.data


def get_or_create_memory(user_id: str) -> Dict[str, Any]:
    """Get existing memory or create default."""
    memory = get_creator_memory(user_id)
    if memory:
        return memory

    supabase = get_supabase()
    default = {
        "id": str(uuid4()),
        "user_id": user_id,
        **DEFAULT_MEMORY,
        "last_used": datetime.utcnow().isoformat(),
    }
    supabase.table("creator_memories").insert(default.copy()).execute()
    logger.info(f"Creator memory created for user {user_id}")
    return default


def update_memory_from_edit(user_id: str, edit_plan: Dict[str, Any]) -> None:
    """Update creator memory based on edit plan choices."""
    memory = get_or_create_memory(user_id)
    supabase = get_supabase()

    changes = {}
    edit_count = memory.get("edit_count", 0) + 1

    # Weighted moving average for preferences
    alpha = min(0.3, 1.0 / max(1, edit_count))

    # Music vibe — use most recent
    music = edit_plan.get("music_vibe", "")
    if music and music.lower() not in ("no music", "no_music", ""):
        changes["music_vibe"] = music

    # Color grade
    grade = edit_plan.get("color_grade", "")
    if grade and grade != "none":
        changes["color_grade"] = grade

    # Caption style
    captions = edit_plan.get("captions", [])
    if captions:
        style_counts = {}
        for cap in captions:
            s = cap.get("style", "bold_white_center")
            style_counts[s] = style_counts.get(s, 0) + 1
        if style_counts:
            changes["caption_style"] = max(style_counts, key=style_counts.get)

    # Pacing inference from cut frequency
    cuts = edit_plan.get("cuts", [])
    total_duration = edit_plan.get("total_duration", 0)
    if cuts and total_duration > 0:
        avg_cut = total_duration / len(cuts)
        changes["avg_cut_duration"] = avg_cut
        if avg_cut < 3:
            changes["preferred_pacing"] = "fast"
            changes["energy_level"] = min(10, int(memory.get("energy_level", 5) + 2))
        elif avg_cut < 8:
            changes["preferred_pacing"] = "medium"
        else:
            changes["preferred_pacing"] = "slow"
            changes["energy_level"] = max(1, int(memory.get("energy_level", 5) - 1))

    changes["edit_count"] = edit_count
    changes["last_used"] = datetime.utcnow().isoformat()

    supabase.table("creator_memories").update(changes).eq("user_id", user_id).execute()
    logger.info(f"Creator memory updated for user {user_id} (edit #{edit_count})")


def apply_memory_to_plan(memory: Dict[str, Any], edit_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply creator memory preferences as defaults for missing fields in an edit plan.
    Does NOT override explicit user choices.
    """
    plan = edit_plan.copy()

    if not plan.get("music_vibe") or plan["music_vibe"] in ("no music", "no_music", ""):
        plan["music_vibe"] = memory.get("music_vibe", "lo-fi")

    if not plan.get("color_grade") or plan["color_grade"] == "none":
        plan["color_grade"] = memory.get("color_grade", "warm")

    captions = plan.get("captions", [])
    if captions:
        preferred_style = memory.get("caption_style", "bold_white_center")
        for cap in captions:
            if not cap.get("style") or cap["style"] == "bold_white_center":
                cap["style"] = preferred_style

    return plan


def get_style_profile_for_user(user_id: str) -> Dict[str, Any]:
    """Build a style profile from creator memory for passing to GPT."""
    memory = get_or_create_memory(user_id)
    return {
        "preferred_pacing": memory.get("preferred_pacing", "medium"),
        "caption_style": memory.get("caption_style", "bold_white_center"),
        "music_vibe": memory.get("music_vibe", "lo-fi"),
        "color_grade": memory.get("color_grade", "warm"),
        "energy_level": memory.get("energy_level", 5),
        "avg_cut_duration": memory.get("avg_cut_duration", 3.0),
        "hook_pattern": memory.get("hook_pattern", "question hook"),
        "pacing_curve": memory.get("pacing_curve", []),
        "caption_density_pattern": memory.get("caption_density_pattern", []),
        "editing_frequency": memory.get("editing_frequency", []),
    }


# ── Time-Series Pattern Storage ───────────────────────────────────────────────

def store_pacing_curve(user_id: str, video_duration: float, cuts: List[Dict[str, Any]]) -> None:
    """
    Store pacing curve: how fast/slow the edit was at different time points.
    Pacing = inverse of avg cut duration in each 30s window.
    """
    memory = get_or_create_memory(user_id)
    supabase = get_supabase()

    if not cuts or video_duration <= 0:
        return

    window_size = 30.0
    num_windows = max(1, int(video_duration / window_size))
    pacing_curve = []

    for w in range(num_windows):
        w_start = w * window_size
        w_end = min((w + 1) * window_size, video_duration)
        cuts_in_window = [
            c for c in cuts
            if c.get("start", 0) < w_end and c.get("end", 0) > w_start
        ]
        if cuts_in_window:
            avg_cut_dur = sum(
                c.get("end", 0) - c.get("start", 0) for c in cuts_in_window
            ) / len(cuts_in_window)
            pace = min(10, max(1, int(10 - avg_cut_dur)))  # Faster cuts = higher pace
        else:
            pace = 5
        pacing_curve.append({
            "window": w,
            "start": w_start,
            "end": w_end,
            "pace": pace,
        })

    existing = memory.get("pacing_curve", [])
    existing.append(pacing_curve)
    if len(existing) > 10:
        existing = existing[-10:]

    supabase.table("creator_memories").update({
        "pacing_curve": json.dumps(existing),
    }).eq("user_id", user_id).execute()


def store_caption_density(user_id: str, video_duration: float, captions: List[Dict[str, Any]]) -> None:
    """
    Store caption density pattern: how many captions per 30s window.
    """
    memory = get_or_create_memory(user_id)
    supabase = get_supabase()

    if not captions or video_duration <= 0:
        return

    window_size = 30.0
    num_windows = max(1, int(video_duration / window_size))
    density = []

    for w in range(num_windows):
        w_start = w * window_size
        w_end = min((w + 1) * window_size, video_duration)
        caps_in_window = sum(
            1 for c in captions
            if c.get("start", 0) < w_end and c.get("end", 0) > w_start
        )
        density.append({
            "window": w,
            "start": w_start,
            "end": w_end,
            "count": caps_in_window,
        })

    existing = memory.get("caption_density_pattern", [])
    existing.append(density)
    if len(existing) > 10:
        existing = existing[-10:]

    supabase.table("creator_memories").update({
        "caption_density_pattern": json.dumps(existing),
    }).eq("user_id", user_id).execute()


def store_editing_frequency(user_id: str, video_duration: float, edits_per_minute: float) -> None:
    """
    Store editing frequency: how many edits (cuts, effects, captions) per minute.
    """
    memory = get_or_create_memory(user_id)
    supabase = get_supabase()

    existing = memory.get("editing_frequency", [])
    existing.append({
        "edits_per_minute": round(edits_per_minute, 1),
        "video_duration": round(video_duration, 1),
        "timestamp": datetime.utcnow().isoformat(),
    })
    if len(existing) > 20:
        existing = existing[-20:]

    supabase.table("creator_memories").update({
        "editing_frequency": json.dumps(existing),
    }).eq("user_id", user_id).execute()


def get_pacing_average(user_id: str) -> float:
    """Get the user's average preferred pacing from historical data."""
    memory = get_creator_memory(user_id)
    if not memory:
        return 5.0

    pacing_curves = memory.get("pacing_curve", [])
    if not pacing_curves:
        return 5.0

    all_paces = []
    for curve in pacing_curves:
        if isinstance(curve, list):
            for point in curve:
                if isinstance(point, dict) and "pace" in point:
                    all_paces.append(point["pace"])

    return sum(all_paces) / len(all_paces) if all_paces else 5.0
