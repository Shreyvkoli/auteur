"""
Vlog Engine — Story structure builder for 10-30 minute vlogs.
Creates intro/body/outro structure with pacing guidance.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

STRUCTURE_TEMPLATES = {
    "standard": [
        {"section": "hook", "label": "Hook", "pct": 5, "desc": "Strong opening hook (0-5%)"},
        {"section": "intro", "label": "Intro", "pct": 10, "desc": "What this vlog is about (5-15%)"},
        {"section": "body_1", "label": "Main Content 1", "pct": 25, "desc": "First main segment (15-40%)"},
        {"section": "body_2", "label": "Main Content 2", "pct": 25, "desc": "Second main segment (40-65%)"},
        {"section": "body_3", "label": "Main Content 3", "pct": 20, "desc": "Third main segment (65-85%)"},
        {"section": "outro", "label": "Outro", "pct": 15, "desc": "Wrap up + CTA (85-100%)"},
    ],
    "cinematic": [
        {"section": "cold_open", "label": "Cold Open", "pct": 3, "desc": "Cinematic cold open (0-3%)"},
        {"section": "title_card", "label": "Title Card", "pct": 2, "desc": "Title sequence (3-5%)"},
        {"section": "scene_1", "label": "Scene 1", "pct": 20, "desc": "First act (5-25%)"},
        {"section": "scene_2", "label": "Scene 2", "pct": 25, "desc": "Second act (25-50%)"},
        {"section": "climax", "label": "Climax", "pct": 20, "desc": "Peak moment (50-70%)"},
        {"section": "falling_action", "label": "Falling Action", "pct": 15, "desc": "Resolution (70-85%)"},
        {"section": "ending", "label": "Ending", "pct": 15, "desc": "Closing + credits (85-100%)"},
    ],
    "educational": [
        {"section": "hook", "label": "Hook Question", "pct": 5, "desc": "Problem statement (0-5%)"},
        {"section": "context", "label": "Context", "pct": 10, "desc": "Background info (5-15%)"},
        {"section": "point_1", "label": "Key Point 1", "pct": 20, "desc": "First teaching point (15-35%)"},
        {"section": "point_2", "label": "Key Point 2", "pct": 20, "desc": "Second teaching point (35-55%)"},
        {"section": "point_3", "label": "Key Point 3", "pct": 20, "desc": "Third teaching point (55-75%)"},
        {"section": "summary", "label": "Summary", "pct": 15, "desc": "Recap + key takeaways (75-90%)"},
        {"section": "cta", "label": "CTA", "pct": 10, "desc": "Call to action (90-100%)"},
    ],
    "vlog_casual": [
        {"section": "hook", "label": "Fun Hook", "pct": 5, "desc": "Casual attention grabber (0-5%)"},
        {"section": "setup", "label": "Today's Plan", "pct": 8, "desc": "What we're doing today (5-13%)"},
        {"section": "activity_1", "label": "Activity 1", "pct": 22, "desc": "First activity (13-35%)"},
        {"section": "activity_2", "label": "Activity 2", "pct": 22, "desc": "Second activity (35-57%)"},
        {"section": "activity_3", "label": "Activity 3", "pct": 20, "desc": "Third activity (57-77%)"},
        {"section": "reflection", "label": "Reflection", "pct": 13, "desc": "Thoughts + bloopers (77-90%)"},
        {"section": "outro", "label": "Outro", "pct": 10, "desc": "Bye + next time (90-100%)"},
    ],
}


def build_vlog_structure(
    state: Dict[str, Any],
    style: str = "standard",
    user_id: str = "",
) -> Dict[str, Any]:
    """Build a vlog story structure from the video content."""
    total_duration = state.get("metadata", {}).get("total_duration", 0)
    template = STRUCTURE_TEMPLATES.get(style, STRUCTURE_TEMPLATES["standard"])

    segments = state.get("timeline", [])
    if not segments and total_duration > 0:
        from services.edit_state import add_segment
        state = add_segment(state, 0, total_duration)

    structure = []
    timeline_segments = []

    cum_pct = 0.0
    for section in template:
        start_pct = cum_pct
        end_pct = cum_pct + section["pct"]
        start_time = total_duration * start_pct / 100
        end_time = total_duration * end_pct / 100

        structure.append({
            "section": section["section"],
            "label": section["label"],
            "start_pct": start_pct,
            "end_pct": end_pct,
            "start_time": round(start_time, 1),
            "end_time": round(end_time, 1),
            "duration": round(end_time - start_time, 1),
            "desc": section["desc"],
        })

        timeline_segments.append({
            "id": f"vlog_{section['section']}_{uuid4().hex[:8]}",
            "section": section["section"],
            "timeline_start": round(start_time, 1),
            "timeline_end": round(end_time, 1),
            "label": section["label"],
        })

        cum_pct += section["pct"]

    # Restructure the actual timeline to match story structure
    new_timeline = []
    for ts in timeline_segments:
        ts_clip = {
            "id": f"seg_{uuid4().hex[:12]}",
            "clip_id": f"clip_{uuid4().hex[:10]}",
            "source_start": ts["timeline_start"],
            "source_end": ts["timeline_end"],
            "timeline_start": ts["timeline_start"],
            "timeline_end": ts["timeline_end"],
            "speed": 1.0,
            "label": ts["label"],
            "section": ts["section"],
        }
        new_timeline.append(ts_clip)

    # Store structure in state
    state["vlog_structure"] = {
        "style": style,
        "sections": structure,
    }
    # Only replace timeline if it was previously empty
    if not state.get("timeline"):
        state["timeline"] = new_timeline

    logger.info(f"Vlog structure built for {style} mode, {total_duration:.0f}s duration")
    return {
        "structure": structure,
        "timeline_segments": timeline_segments,
        "state": state,
    }
