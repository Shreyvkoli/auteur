"""
Keyframe System — Animate any property over time.

Supports keyframes for:
  - zoom (scale)
  - position (x, y)
  - opacity
  - rotation
  - blur amount
  - brightness / contrast / saturation
  - volume
  - crop region

Keyframes use cubic interpolation between points for smooth animation.
"""

import logging
import bisect
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

SUPPORTED_PROPERTIES = {
    "zoom", "x", "y", "opacity", "rotation",
    "blur", "brightness", "contrast", "saturation",
    "volume", "crop_x", "crop_y", "crop_w", "crop_h",
}

INTERPOLATION_TYPES = {"linear", "ease_in", "ease_out", "ease_in_out", "cubic", "step"}


def _new_keyframe_id() -> str:
    return f"kf_{uuid4().hex[:12]}"


def add_keyframe(
    state: Dict[str, Any],
    clip_id: str,
    property: str,
    time: float,
    value: float,
    interpolation: str = "ease_in_out",
    easing_power: float = 2.0,
) -> Dict[str, Any]:
    """Add a keyframe to a clip property."""
    if property not in SUPPORTED_PROPERTIES:
        raise ValueError(f"Unsupported property: {property}. Supported: {SUPPORTED_PROPERTIES}")

    if interpolation not in INTERPOLATION_TYPES:
        raise ValueError(f"Invalid interpolation: {interpolation}. Valid: {INTERPOLATION_TYPES}")

    keyframes = state.setdefault("keyframes", [])

    for kf in keyframes:
        if kf["clip_id"] == clip_id and kf["property"] == property and abs(kf["time"] - time) < 0.01:
            kf["value"] = value
            kf["interpolation"] = interpolation
            kf["easing_power"] = easing_power
            logger.info(f"Updated keyframe for {property} at {time:.2f}s on {clip_id}")
            return state

    keyframe = {
        "id": _new_keyframe_id(),
        "clip_id": clip_id,
        "property": property,
        "time": time,
        "value": value,
        "interpolation": interpolation,
        "easing_power": easing_power,
    }
    keyframes.append(keyframe)
    keyframes.sort(key=lambda kf: (kf["clip_id"], kf["property"], kf["time"]))

    from services.edit_state import _mark_dirty
    seg = next((s for s in state.get("timeline", []) if s["clip_id"] == clip_id), None)
    if seg:
        _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])

    logger.info(f"Added keyframe: {property}={value} at {time:.2f}s on {clip_id}")
    return state


def remove_keyframe(
    state: Dict[str, Any],
    keyframe_id: str,
) -> Dict[str, Any]:
    """Remove a keyframe by ID."""
    keyframes = state.get("keyframes", [])
    kf = next((k for k in keyframes if k["id"] == keyframe_id), None)
    if not kf:
        logger.warning(f"Keyframe {keyframe_id} not found")
        return state

    state["keyframes"] = [k for k in keyframes if k["id"] != keyframe_id]

    from services.edit_state import _mark_dirty
    seg = next((s for s in state.get("timeline", []) if s["clip_id"] == kf["clip_id"]), None)
    if seg:
        _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])

    logger.info(f"Removed keyframe {keyframe_id}")
    return state


def update_keyframe(
    state: Dict[str, Any],
    keyframe_id: str,
    time: Optional[float] = None,
    value: Optional[float] = None,
    interpolation: Optional[str] = None,
    easing_power: Optional[float] = None,
) -> Dict[str, Any]:
    """Update a keyframe."""
    keyframes = state.get("keyframes", [])
    for kf in keyframes:
        if kf["id"] == keyframe_id:
            if time is not None:
                kf["time"] = time
            if value is not None:
                kf["value"] = value
            if interpolation is not None:
                kf["interpolation"] = interpolation
            if easing_power is not None:
                kf["easing_power"] = easing_power
            keyframes.sort(key=lambda k: (k["clip_id"], k["property"], k["time"]))
            logger.info(f"Updated keyframe {keyframe_id}")
            return state

    logger.warning(f"Keyframe {keyframe_id} not found")
    return state


def get_keyframes_for_clip(
    state: Dict[str, Any],
    clip_id: str,
    property: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get keyframes for a specific clip, optionally filtered by property."""
    keyframes = state.get("keyframes", [])
    result = [kf for kf in keyframes if kf["clip_id"] == clip_id]
    if property:
        result = [kf for kf in result if kf["property"] == property]
    return sorted(result, key=lambda kf: kf["time"])


def get_keyframes_for_property(
    state: Dict[str, Any],
    property: str,
) -> List[Dict[str, Any]]:
    """Get all keyframes for a property across all clips."""
    keyframes = state.get("keyframes", [])
    return sorted(
        [kf for kf in keyframes if kf["property"] == property],
        key=lambda kf: (kf["clip_id"], kf["time"]),
    )


def interpolate_keyframes(
    keyframes: List[Dict[str, Any]],
    time: float,
) -> float:
    """Interpolate value at a given time from a list of keyframes."""
    if not keyframes:
        return 0.0

    if len(keyframes) == 1:
        return keyframes[0]["value"]

    times = [kf["time"] for kf in keyframes]

    if time <= times[0]:
        return keyframes[0]["value"]
    if time >= times[-1]:
        return keyframes[-1]["value"]

    idx = bisect.bisect_right(times, time) - 1
    idx = max(0, min(idx, len(keyframes) - 2))

    kf_a = keyframes[idx]
    kf_b = keyframes[idx + 1]

    t_range = kf_b["time"] - kf_a["time"]
    if t_range <= 0:
        return kf_a["value"]

    t = (time - kf_a["time"]) / t_range
    interp = kf_a.get("interpolation", "ease_in_out")
    power = kf_a.get("easing_power", 2.0)

    t_eased = _apply_easing(t, interp, power)

    return kf_a["value"] + (kf_b["value"] - kf_a["value"]) * t_eased


def _apply_easing(t: float, interp: str, power: float = 2.0) -> float:
    """Apply easing function to normalized time t (0-1)."""
    if interp == "linear":
        return t
    elif interp == "ease_in":
        return t ** power
    elif interp == "ease_out":
        return 1 - (1 - t) ** power
    elif interp == "ease_in_out":
        if t < 0.5:
            return 0.5 * (2 * t) ** power
        else:
            return 1 - 0.5 * (2 * (1 - t)) ** power
    elif interp == "cubic":
        return t * t * (3 - 2 * t)
    elif interp == "step":
        return 0.0 if t < 0.5 else 1.0

    return t


def build_keyframe_property_map(
    state: Dict[str, Any],
    clip_id: str,
    fps: float = 30.0,
    duration: float = 0.0,
) -> Dict[str, List[Dict[str, float]]]:
    """
    Build a per-frame property map for a clip from its keyframes.
    Returns: {property: [{frame: int, value: float}, ...]}
    """
    result = {}
    keyframes = state.get("keyframes", [])

    clip_kfs = [kf for kf in keyframes if kf["clip_id"] == clip_id]
    properties = set(kf["property"] for kf in clip_kfs)

    total_frames = int(duration * fps) if duration > 0 else 0

    for prop in properties:
        prop_kfs = sorted(
            [kf for kf in clip_kfs if kf["property"] == prop],
            key=lambda kf: kf["time"],
        )
        frames = []
        if total_frames > 0:
            for frame_num in range(total_frames):
                t = frame_num / fps
                val = interpolate_keyframes(prop_kfs, t)
                frames.append({"frame": frame_num, "value": round(val, 4)})
        result[prop] = frames

    return result


def batch_add_keyframes(
    state: Dict[str, Any],
    clip_id: str,
    property: str,
    values: List[Dict[str, float]],
) -> Dict[str, Any]:
    """Add multiple keyframes at once. values: [{time, value}, ...]"""
    for v in values:
        add_keyframe(
            state, clip_id, property,
            time=v["time"],
            value=v["value"],
            interpolation=v.get("interpolation", "ease_in_out"),
            easing_power=v.get("easing_power", 2.0),
        )
    return state
