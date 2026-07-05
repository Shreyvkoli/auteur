"""
Style Merger — Combine multiple reference video styles into one composite profile.
Each ref video contributes different aspects (pacing, captions, music, memes, color).
The composite style is used as the target for the edit plan.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from core.database import get_supabase

logger = logging.getLogger(__name__)

# Default style fallback — can be overridden via DB style_profiles
DEFAULT_STYLE: Dict[str, Any] = {
    "cut_speed_seconds": 3.0,
    "caption_style": {"font": "Arial", "color": "white", "position": "center", "size": "large", "animated": True},
    "energy_level": 6,
    "hook_pattern": "question hook",
    "transition_type": "hard cut",
    "music_vibe": "lo-fi",
    "blur_background": False,
    "meme_frequency": "medium",
    "color_grade": "warm",
}


def merge_style_profiles(profiles: List[Dict[str, Any]], weights: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Merge multiple style profiles into one composite.
    Each profile is a dict from GPT-4o Vision style analysis.
    
    Strategy: weight-based averaging for numeric fields,
    plurality for categorical fields.
    """
    if not profiles:
        return _default_style()
    
    if len(profiles) == 1:
        return profiles[0]
    
    n = len(profiles)
    if weights is None:
        weights = [1.0 / n] * n
    
    # Normalize weights
    total_w = sum(weights)
    weights = [w / total_w for w in weights]
    
    # Numeric fields: weighted average
    numeric_fields = [
        "cut_speed_seconds", "energy_level",
    ]
    merged = {}
    
    for field in numeric_fields:
        values = []
        for i, p in enumerate(profiles):
            val = p.get(field)
            if val is not None:
                values.append((val, weights[i]))
        if values:
            merged[field] = round(
                sum(v * w for v, w in values) / sum(w for _, w in values),
                1,
            )
        else:
            merged[field] = _default_style().get(field)
    
    # Categorical fields: take from highest-weighted profile that has it
    categorical_fields = [
        "hook_pattern", "transition_type", "music_vibe",
        "color_grade", "meme_frequency",
    ]
    for field in categorical_fields:
        for i in range(n):
            val = profiles[i].get(field)
            if val and val != "none":
                merged[field] = val
                break
        if field not in merged:
            merged[field] = _default_style().get(field)
    
    # Caption style: plurality vote
    caption_styles = {}
    for p in profiles:
        cs = p.get("caption_style", {})
        if isinstance(cs, dict):
            key = f"{cs.get('color','white')}_{cs.get('position','center')}_{cs.get('size','large')}_{cs.get('animated',False)}"
            caption_styles[key] = caption_styles.get(key, 0) + 1
        elif isinstance(cs, str):
            caption_styles[cs] = caption_styles.get(cs, 0) + 1
    
    if caption_styles:
        most_common = max(caption_styles, key=caption_styles.get)
        merged["caption_style"] = most_common
    else:
        merged["caption_style"] = _default_style().get("caption_style", "bold_white_center")
    
    # Blur background: true if majority has it
    blur_count = sum(1 for p in profiles if p.get("blur_background", False))
    merged["blur_background"] = blur_count > n / 2
    
    # Track which ref contributed what (for the summary screen)
    ref_contributions = []
    for i, p in enumerate(profiles):
        ref_contributions.append({
            "ref_index": i,
            "contributed": {
                "music_vibe": p.get("music_vibe"),
                "color_grade": p.get("color_grade"),
                "energy_level": p.get("energy_level"),
                "caption_style": p.get("caption_style"),
                "hook_pattern": p.get("hook_pattern"),
            }
        })
    
    merged["_ref_contributions"] = ref_contributions
    merged["_num_refs"] = n
    
    return merged


def store_composite_style(
    user_id: str,
    job_id: str,
    composite: Dict[str, Any],
    ref_video_ids: List[str],
) -> str:
    """Save the composite style profile to DB. Returns profile_id."""
    supabase = get_supabase()
    profile_id = str(uuid4())
    
    contributions = composite.pop("_ref_contributions", [])
    num_refs = composite.pop("_num_refs", len(ref_video_ids))
    
    supabase.table("style_profiles").insert({
        "id": profile_id,
        "user_id": user_id,
        "job_id": job_id,
        "source_url": f"composite:{','.join(ref_video_ids)}",
        "style_json": composite,
        "ref_video_ids": ref_video_ids,
        "ref_contributions": contributions,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()
    
    logger.info(f"Composite style {profile_id} saved for job {job_id} from {num_refs} refs")
    
    # Also update user's style_dna
    supabase.table("users").update({
        "style_dna": composite,
    }).eq("id", user_id).execute()
    
    return profile_id


def _default_style() -> Dict[str, Any]:
    return dict(DEFAULT_STYLE)


def _build_edit_events(
    cuts: List[Dict[str, Any]],
    captions: List[Dict[str, Any]],
    zoom_moments: List[Dict[str, Any]],
    meme_sounds: List[Dict[str, Any]],
    removed_silence_count: int,
    filler_count: int,
    original_duration: float,
) -> List[Dict[str, Any]]:
    """Build a timestamp-sorted list of per-timestamp edit events for the timeline."""
    events = []

    for c in cuts:
        events.append({
            "timestamp": c.get("timestamp", 0),
            "type": "cut",
            "subtype": c.get("subtype", "cut"),
            "description": c.get("description", f"Cut at {c.get('timestamp', 0):.1f}s"),
            "duration": c.get("duration", 1.0),
        })

    for cap in captions:
        events.append({
            "timestamp": cap.get("timestamp", 0),
            "type": "caption",
            "subtype": "added",
            "description": f"Caption: \"{cap.get('text', '')[:60]}\"",
            "content": cap.get("text", ""),
        })

    for z in zoom_moments:
        events.append({
            "timestamp": z.get("timestamp", 0),
            "type": "zoom",
            "subtype": "modified",
            "description": f"Zoom {z.get('scale', 1.2)}x",
            "scale": z.get("scale", 1.2),
        })

    for m in meme_sounds:
        events.append({
            "timestamp": m.get("timestamp", 0),
            "type": "meme_sound",
            "subtype": "added",
            "description": f"Meme: {m.get('sound', 'sound')}",
            "sound": m.get("sound", ""),
        })

    if removed_silence_count > 0:
        events.append({
            "timestamp": 0,
            "type": "silence_removed",
            "subtype": "removed",
            "description": f"Removed {removed_silence_count} silences (-{max(0, original_duration * 0.05):.0f}s)",
            "count": removed_silence_count,
        })

    if filler_count > 0:
        events.append({
            "timestamp": 0,
            "type": "filler_removed",
            "subtype": "removed",
            "description": f"Removed {filler_count} filler words (um/uh)",
            "count": filler_count,
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


def generate_changelog(
    original_duration: float,
    edited_duration: float,
    composite_style: Dict[str, Any],
    profiles: List[Dict[str, Any]],
    edit_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a detailed changelog/summary of what the AI did.
    This is what appears on the summary screen.
    """
    cuts = edit_plan.get("cuts", [])
    captions = edit_plan.get("captions", [])
    zoom_moments = edit_plan.get("zoom_moments", [])
    meme_sounds = edit_plan.get("meme_sounds", [])
    removed_silence_count = edit_plan.get("_removed_silence_count", 0)
    filler_count = edit_plan.get("_filler_count", 0)
    
    FILLER_ESTIMATE_RATIO = 0.05
    SILENCE_ESTIMATE_RATIO = 0.3
    total_removed = max(0, original_duration - edited_duration)
    avg_cut_duration = edited_duration / max(1, len(cuts)) if cuts else 0
    num_fillers_removed = filler_count or max(0, int(original_duration * FILLER_ESTIMATE_RATIO))
    num_silences_removed = removed_silence_count or max(0, int(len(cuts) * SILENCE_ESTIMATE_RATIO))
    
    # Determine which ref contributed what
    ref_contributions = composite_style.get("_ref_contributions", [])
    ref_breakdown = []
    for rc in ref_contributions:
        ref_breakdown.append({
            "ref_index": rc.get("ref_index", 0),
            "contributed": {
                "music_vibe": rc.get("contributed", {}).get("music_vibe", "—"),
                "color_grade": rc.get("contributed", {}).get("color_grade", "—"),
                "caption_style": rc.get("contributed", {}).get("caption_style", "—"),
                "hook_pattern": rc.get("contributed", {}).get("hook_pattern", "—"),
                "energy_level": rc.get("contributed", {}).get("energy_level", "—"),
            }
        })
    
    edit_events = _build_edit_events(
        cuts, captions, zoom_moments, meme_sounds,
        removed_silence_count, filler_count, original_duration,
    )
    
    changelog = {
        "original_duration": round(original_duration, 1),
        "edited_duration": round(edited_duration, 1),
        "total_removed": round(total_removed, 1),
        "cuts": {
            "total": len(cuts),
            "avg_cut_duration": round(avg_cut_duration, 1),
            "num_fillers_removed": num_fillers_removed,
            "num_silences_removed": num_silences_removed,
        },
        "captions": {
            "total": len(captions),
            "style": composite_style.get("caption_style", "bold_white_center"),
        },
        "zoom_moments": {
            "total": len(zoom_moments),
            "positions": [{"time": z.get("timestamp", 0), "scale": z.get("scale", 1.0)} for z in zoom_moments],
        },
        "meme_sounds": {
            "total": len(meme_sounds),
            "positions": [{"time": m.get("timestamp", 0), "sound": m.get("sound", "")} for m in meme_sounds],
        },
        "music_vibe": composite_style.get("music_vibe", "lo-fi"),
        "color_grade": composite_style.get("color_grade", "warm"),
        "style_match_score": composite_style.get("_style_match_score", 85),
        "ref_breakdown": ref_breakdown,
        "edit_events": edit_events,
    }
    
    return changelog
