"""
Aspect Ratio Control — Multi-format output with auto-reframe.

Supports:
  - 9:16 (Reels, TikTok, Shorts)
  - 16:9 (YouTube, Landscape)
  - 1:1 (Instagram Square)
  - 4:5 (Instagram Feed)
  - 2.35:1 (Cinematic)
  - 9:20 (Ultra Tall)
  - Custom aspect ratios
  - Auto reframe (smart crop to keep subject centered)
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

ASPECT_RATIOS = {
    "9:16": {"width": 1080, "height": 1920, "label": "Reels / TikTok / Shorts"},
    "16:9": {"width": 1920, "height": 1080, "label": "YouTube / Landscape"},
    "1:1": {"width": 1080, "height": 1080, "label": "Instagram Square"},
    "4:5": {"width": 1080, "height": 1350, "label": "Instagram Feed"},
    "2.35:1": {"width": 1920, "height": 816, "label": "Cinematic"},
    "9:20": {"width": 810, "height": 1800, "label": "Ultra Tall"},
    "3:4": {"width": 1080, "height": 1440, "label": "Portrait"},
    "21:9": {"width": 1920, "height": 822, "label": "Ultra Wide"},
}


def set_aspect_ratio(
    state: Dict[str, Any],
    aspect_ratio: str = "9:16",
    auto_reframe: bool = False,
    custom_width: Optional[int] = None,
    custom_height: Optional[int] = None,
) -> Dict[str, Any]:
    """Set the output aspect ratio."""
    metadata = state.setdefault("metadata", {})

    if aspect_ratio == "custom":
        width = custom_width or 1080
        height = custom_height or 1920
    elif aspect_ratio in ASPECT_RATIOS:
        dims = ASPECT_RATIOS[aspect_ratio]
        width = dims["width"]
        height = dims["height"]
    else:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}. Valid: {list(ASPECT_RATIOS.keys())}")

    metadata["aspect_ratio"] = aspect_ratio
    metadata["width"] = width
    metadata["height"] = height
    metadata["auto_reframe"] = auto_reframe

    effects = state.setdefault("effects", {})
    effects["aspect_ratio"] = aspect_ratio
    effects["auto_reframe"] = auto_reframe

    from services.edit_state import mark_all_dirty
    mark_all_dirty(state)

    logger.info(f"Set aspect ratio: {aspect_ratio} ({width}x{height})")
    return state


def get_aspect_ratio(state: Dict[str, Any]) -> Dict[str, Any]:
    """Get current aspect ratio settings."""
    metadata = state.get("metadata", {})
    return {
        "aspect_ratio": metadata.get("aspect_ratio", "9:16"),
        "width": metadata.get("width", 1080),
        "height": metadata.get("height", 1920),
        "auto_reframe": metadata.get("auto_reframe", False),
    }


def get_available_aspect_ratios() -> Dict[str, Dict[str, Any]]:
    """Get all available aspect ratios."""
    return ASPECT_RATIOS


def calculate_crop_params(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> Dict[str, float]:
    """Calculate crop parameters to fit source into target aspect ratio."""
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height

    if source_ratio > target_ratio:
        new_width = int(source_height * target_ratio)
        new_height = source_height
    else:
        new_width = source_width
        new_height = int(source_width / target_ratio)

    x = int((source_width - new_width) * focus_x)
    y = int((source_height - new_height) * focus_y)

    x = max(0, min(x, source_width - new_width))
    y = max(0, min(y, source_height - new_height))

    return {
        "x": x,
        "y": y,
        "width": new_width,
        "height": new_height,
    }


def build_reframe_filter(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> str:
    """Build FFmpeg filter for aspect ratio conversion."""
    crop = calculate_crop_params(
        source_width, source_height,
        target_width, target_height,
        focus_x, focus_y,
    )

    return (
        f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']},"
        f"scale={target_width}:{target_height}:flags=lanczos"
    )


def auto_reframe_segment(
    state: Dict[str, Any],
    clip_id: str,
    target_ratio: str = "9:16",
) -> Dict[str, Any]:
    """Mark a clip for auto-reframe (subject tracking)."""
    metadata = state.get("metadata", {})
    target_dims = ASPECT_RATIOS.get(target_ratio, ASPECT_RATIOS["9:16"])

    effects = state.setdefault("effects", {})
    reframe = effects.setdefault("reframe", {})
    reframe[clip_id] = {
        "target_ratio": target_ratio,
        "target_width": target_dims["width"],
        "target_height": target_dims["height"],
        "auto": True,
    }

    from services.edit_state import _mark_dirty
    seg = next((s for s in state.get("timeline", []) if s["clip_id"] == clip_id), None)
    if seg:
        _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])

    logger.info(f"Auto-reframe set for {clip_id} → {target_ratio}")
    return state
