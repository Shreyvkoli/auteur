"""
Transitions Engine — Handle transitions between clips.

Supports: fade, dissolve, wipe_left, wipe_right, wipe_up, wipe_down,
          zoom_in, zoom_out, slide_left, slide_right, blur, glitch, spin
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


VALID_TRANSITIONS = {
    "fade", "dissolve", "wipe_left", "wipe_right", "wipe_up", "wipe_down",
    "zoom_in", "zoom_out", "slide_left", "slide_right", "blur", "glitch",
    "spin", "cross_fade", "luma_wipe", "radial_wipe",
}


def _new_transition_id() -> str:
    return f"tr_{uuid4().hex[:12]}"


def add_transition(
    state: Dict[str, Any],
    clip_a_id: str,
    clip_b_id: str,
    transition_type: str = "fade",
    duration: float = 0.5,
) -> Dict[str, Any]:
    """Add a transition between two adjacent clips."""
    if transition_type not in VALID_TRANSITIONS:
        raise ValueError(f"Invalid transition type: {transition_type}. Valid: {VALID_TRANSITIONS}")

    transitions = state["effects"].setdefault("transitions", [])

    for t in transitions:
        if t.get("between") == [clip_a_id, clip_b_id]:
            t["type"] = transition_type
            t["duration"] = duration
            logger.info(f"Updated transition between {clip_a_id} and {clip_b_id}")
            return state

    transition = {
        "id": _new_transition_id(),
        "type": "transition",
        "transition": transition_type,
        "duration": min(max(duration, 0.1), 5.0),
        "between": [clip_a_id, clip_b_id],
    }
    transitions.append(transition)

    _mark_transition_dirty(state, clip_a_id, clip_b_id, duration)
    logger.info(f"Added {transition_type} transition between {clip_a_id} and {clip_b_id}")
    return state


def remove_transition(
    state: Dict[str, Any],
    clip_a_id: str,
    clip_b_id: str,
) -> Dict[str, Any]:
    """Remove transition between two clips."""
    transitions = state["effects"].get("transitions", [])
    state["effects"]["transitions"] = [
        t for t in transitions
        if t.get("between") != [clip_a_id, clip_b_id]
    ]
    _mark_transition_dirty(state, clip_a_id, clip_b_id, 0)
    logger.info(f"Removed transition between {clip_a_id} and {clip_b_id}")
    return state


def update_transition(
    state: Dict[str, Any],
    transition_id: str,
    transition_type: Optional[str] = None,
    duration: Optional[float] = None,
) -> Dict[str, Any]:
    """Update a transition by ID."""
    transitions = state["effects"].get("transitions", [])
    for t in transitions:
        if t.get("id") == transition_id:
            if transition_type is not None:
                if transition_type not in VALID_TRANSITIONS:
                    raise ValueError(f"Invalid transition: {transition_type}")
                t["transition"] = transition_type
                t["type"] = "transition"
            if duration is not None:
                t["duration"] = min(max(duration, 0.1), 5.0)
            between = t.get("between", [])
            if len(between) == 2:
                _mark_transition_dirty(state, between[0], between[1], t.get("duration", 0.5))
            logger.info(f"Updated transition {transition_id}")
            return state
    logger.warning(f"Transition {transition_id} not found")
    return state


def get_transitions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all transitions in the state."""
    return [
        t for t in state["effects"].get("transitions", [])
        if t.get("type") == "transition"
    ]


def get_transition_for_clip(state: Dict[str, Any], clip_id: str) -> Optional[Dict[str, Any]]:
    """Get transition info for a specific clip (as clip_a or clip_b)."""
    for t in state["effects"].get("transitions", []):
        if t.get("type") == "transition":
            between = t.get("between", [])
            if clip_id in between:
                return t
    return None


def _mark_transition_dirty(
    state: Dict[str, Any],
    clip_a_id: str,
    clip_b_id: str,
    duration: float,
) -> None:
    """Mark the area around a transition as dirty."""
    from services.edit_state import _mark_dirty

    timeline = state.get("timeline", [])
    seg_a = next((s for s in timeline if s["clip_id"] == clip_a_id), None)
    seg_b = next((s for s in timeline if s["clip_id"] == clip_b_id), None)

    if seg_a and seg_b:
        start = max(0, seg_a["timeline_end"] - duration)
        end = seg_b["timeline_start"] + duration
        _mark_dirty(state, start, end)
    elif seg_a:
        _mark_dirty(state, seg_a["timeline_end"] - duration, seg_a["timeline_end"] + duration)
    elif seg_b:
        _mark_dirty(state, seg_b["timeline_start"] - duration, seg_b["timeline_start"] + duration)


def build_transition_filter(transition: Dict[str, Any], clip_duration: float) -> str:
    """Build FFmpeg filter string for a transition."""
    t_type = transition.get("transition", "fade")
    dur = transition.get("duration", 0.5)

    filters = {
        "fade": f"fade=t=in:st=0:d={dur},fade=t=out:st={clip_duration - dur}:d={dur}",
        "dissolve": f"xfade=transition=fade:duration={dur}:offset={clip_duration - dur}",
        "wipe_left": f"xfade=transition=wiperight:duration={dur}:offset={clip_duration - dur}",
        "wipe_right": f"xfade=transition=wipeleft:duration={dur}:offset={clip_duration - dur}",
        "wipe_up": f"xfade=transition=wipeup:duration={dur}:offset={clip_duration - dur}",
        "wipe_down": f"xfade=transition=wipedown:duration={dur}:offset={clip_duration - dur}",
        "zoom_in": f"xfade=transition=circlecrop:duration={dur}:offset={clip_duration - dur}",
        "slide_left": f"xfade=transition=slideleft:duration={dur}:offset={clip_duration - dur}",
        "slide_right": f"xfade=transition=slideright:duration={dur}:offset={clip_duration - dur}",
        "cross_fade": f"xfade=transition=fade:duration={dur}:offset={clip_duration - dur}",
        "luma_wipe": f"xfade=transition=lumawipe:duration={dur}:offset={clip_duration - dur}",
        "radial_wipe": f"xfade=transition=radial:duration={dur}:offset={clip_duration - dur}",
        "spin": f"xfade=transition=smoothleft:duration={dur}:offset={clip_duration - dur}",
    }

    return filters.get(t_type, filters["fade"])
