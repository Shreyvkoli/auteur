"""
Playback System — Playhead control, seek, frame stepping, playback state.

Provides server-side playback state for:
  - Current playhead position
  - Seek to time
  - Frame stepping (forward/backward)
  - Playback speed control
  - Loop regions
  - Marker system (in/out points)
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def get_playback_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Get the current playback state."""
    playback = state.setdefault("playback", {})
    return {
        "playhead": playback.get("playhead", 0.0),
        "playing": playback.get("playing", False),
        "speed": playback.get("speed", 1.0),
        "total_duration": state.get("metadata", {}).get("total_duration", 0.0),
        "fps": state.get("metadata", {}).get("fps", 30.0),
        "loop_start": playback.get("loop_start"),
        "loop_end": playback.get("loop_end"),
        "loop_enabled": playback.get("loop_enabled", False),
        "markers": playback.get("markers", []),
    }


def set_playhead(
    state: Dict[str, Any],
    time: float,
) -> Dict[str, Any]:
    """Set the playhead to a specific time."""
    playback = state.setdefault("playback", {})
    total = state.get("metadata", {}).get("total_duration", 0.0)
    playback["playhead"] = max(0.0, min(time, total))
    return state


def seek(
    state: Dict[str, Any],
    offset: float,
) -> Dict[str, Any]:
    """Seek relative to current playhead position."""
    playback = state.setdefault("playback", {})
    current = playback.get("playhead", 0.0)
    total = state.get("metadata", {}).get("total_duration", 0.0)
    playback["playhead"] = max(0.0, min(current + offset, total))
    return state


def step_forward(
    state: Dict[str, Any],
    frames: int = 1,
) -> Dict[str, Any]:
    """Step forward by N frames."""
    playback = state.setdefault("playback", {})
    fps = state.get("metadata", {}).get("fps", 30.0)
    current = playback.get("playhead", 0.0)
    total = state.get("metadata", {}).get("total_duration", 0.0)
    delta = frames / fps
    playback["playhead"] = max(0.0, min(current + delta, total))
    return state


def step_backward(
    state: Dict[str, Any],
    frames: int = 1,
) -> Dict[str, Any]:
    """Step backward by N frames."""
    playback = state.setdefault("playback", {})
    fps = state.get("metadata", {}).get("fps", 30.0)
    current = playback.get("playhead", 0.0)
    delta = frames / fps
    playback["playhead"] = max(0.0, current - delta)
    return state


def set_playback_speed(
    state: Dict[str, Any],
    speed: float,
) -> Dict[str, Any]:
    """Set playback speed (0.25x to 4x)."""
    playback = state.setdefault("playback", {})
    playback["speed"] = max(0.25, min(4.0, speed))
    return state


def toggle_play(state: Dict[str, Any]) -> Dict[str, Any]:
    """Toggle play/pause."""
    playback = state.setdefault("playback", {})
    playback["playing"] = not playback.get("playing", False)
    return state


def set_play(state: Dict[str, Any], playing: bool) -> Dict[str, Any]:
    """Set play state explicitly."""
    playback = state.setdefault("playback", {})
    playback["playing"] = playing
    return state


def set_loop_region(
    state: Dict[str, Any],
    start: Optional[float] = None,
    end: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Set loop region (in/out points)."""
    playback = state.setdefault("playback", {})
    total = state.get("metadata", {}).get("total_duration", 0.0)

    if start is not None:
        playback["loop_start"] = max(0.0, min(start, total))
    if end is not None:
        playback["loop_end"] = max(0.0, min(end, total))
    if enabled is not None:
        playback["loop_enabled"] = enabled

    if playback.get("loop_start") is not None and playback.get("loop_end") is not None:
        if playback["loop_start"] >= playback["loop_end"]:
            playback["loop_end"] = playback["loop_start"] + 0.1

    return state


def clear_loop_region(state: Dict[str, Any]) -> Dict[str, Any]:
    """Clear loop region."""
    playback = state.setdefault("playback", {})
    playback.pop("loop_start", None)
    playback.pop("loop_end", None)
    playback["loop_enabled"] = False
    return state


def add_marker(
    state: Dict[str, Any],
    time: float,
    label: str = "",
    color: str = "#FF0000",
) -> Dict[str, Any]:
    """Add a marker at a specific time."""
    playback = state.setdefault("playback", {})
    markers = playback.setdefault("markers", [])

    marker = {
        "time": time,
        "label": label,
        "color": color,
    }
    markers.append(marker)
    markers.sort(key=lambda m: m["time"])

    logger.info(f"Added marker at {time:.2f}s: {label}")
    return state


def remove_marker(
    state: Dict[str, Any],
    time: float,
    tolerance: float = 0.1,
) -> Dict[str, Any]:
    """Remove a marker near a specific time."""
    playback = state.get("playback", {})
    markers = playback.get("markers", [])
    playback["markers"] = [
        m for m in markers
        if abs(m["time"] - time) > tolerance
    ]
    return state


def clear_markers(state: Dict[str, Any]) -> Dict[str, Any]:
    """Remove all markers."""
    playback = state.setdefault("playback", {})
    playback["markers"] = []
    return state


def get_frame_at_time(
    state: Dict[str, Any],
    time: float,
) -> Dict[str, Any]:
    """Get info about what's at a specific time on the timeline."""
    timeline = state.get("timeline", [])
    overlays = state.get("overlays", [])
    captions = state.get("captions", [])
    text_overlays = [o for o in overlays if o.get("type") == "text"]

    active_segments = [
        seg for seg in timeline
        if seg["timeline_start"] <= time < seg["timeline_end"]
    ]

    active_captions = [
        cap for cap in captions
        if cap.get("start", 0) <= time < cap.get("end", 0)
    ]

    active_text = [
        o for o in text_overlays
        if o.get("start", 0) <= time < o.get("end", 0)
    ]

    active_overlays = [
        o for o in overlays
        if o.get("type") != "text"
        and o.get("start", 0) <= time < o.get("end", 0)
    ]

    return {
        "time": time,
        "segments": active_segments,
        "captions": active_captions,
        "text_overlays": active_text,
        "overlays": active_overlays,
        "frame_number": int(time * state.get("metadata", {}).get("fps", 30)),
    }
