"""
Overlay System — Stickers, images, GIFs on top of video.

Supports:
  - Image overlays (PNG, JPG)
  - Sticker overlays
  - GIF overlays
  - Position (x, y) with pixel or percentage
  - Scale / size
  - Rotation
  - Opacity
  - Start/end time
  - Animation (fade, pop, bounce, slide)
  - Layer ordering
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

VALID_OVERLAY_TYPES = {"image", "sticker", "gif"}
VALID_OVERLAY_ANIMATIONS = {"none", "fade_in", "fade_out", "pop", "bounce", "slide_up", "slide_down"}


def _new_overlay_id() -> str:
    return f"ov_{uuid4().hex[:12]}"


def add_overlay(
    state: Dict[str, Any],
    overlay_type: str,
    source_url: str,
    start: float,
    end: float,
    x: float = 0.5,
    y: float = 0.5,
    scale: float = 1.0,
    rotation: float = 0.0,
    opacity: float = 1.0,
    animation: str = "none",
    animation_duration: float = 0.3,
    layer: int = 0,
    name: str = "",
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    """Add an overlay (image, sticker, gif) to the timeline."""
    if overlay_type not in VALID_OVERLAY_TYPES:
        raise ValueError(f"Invalid overlay type: {overlay_type}. Valid: {VALID_OVERLAY_TYPES}")

    overlay_id = _new_overlay_id()
    overlay = {
        "id": overlay_id,
        "type": overlay_type,
        "source_url": source_url,
        "start": start,
        "end": end,
        "x": max(0.0, min(1.0, x)),
        "y": max(0.0, min(1.0, y)),
        "scale": max(0.1, min(5.0, scale)),
        "rotation": max(-360.0, min(360.0, rotation)),
        "opacity": max(0.0, min(1.0, opacity)),
        "animation": animation if animation in VALID_OVERLAY_ANIMATIONS else "none",
        "animation_duration": max(0.1, min(2.0, animation_duration)),
        "layer": layer,
        "name": name,
        "width": width,
        "height": height,
        "keyframes": [],
    }

    overlays = state.setdefault("overlays", [])
    overlays.append(overlay)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)

    logger.info(f"Added {overlay_type} overlay at {start:.1f}-{end:.1f}s")
    return state


def update_overlay(
    state: Dict[str, Any],
    overlay_id: str,
    source_url: Optional[str] = None,
    start: Optional[float] = None,
    end: Optional[float] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    scale: Optional[float] = None,
    rotation: Optional[float] = None,
    opacity: Optional[float] = None,
    animation: Optional[str] = None,
    animation_duration: Optional[float] = None,
    layer: Optional[int] = None,
) -> Dict[str, Any]:
    """Update an existing overlay."""
    overlays = state.get("overlays", [])
    for ov in overlays:
        if ov["id"] == overlay_id:
            if source_url is not None:
                ov["source_url"] = source_url
            if start is not None:
                ov["start"] = start
            if end is not None:
                ov["end"] = end
            if x is not None:
                ov["x"] = max(0.0, min(1.0, x))
            if y is not None:
                ov["y"] = max(0.0, min(1.0, y))
            if scale is not None:
                ov["scale"] = max(0.1, min(5.0, scale))
            if rotation is not None:
                ov["rotation"] = max(-360.0, min(360.0, rotation))
            if opacity is not None:
                ov["opacity"] = max(0.0, min(1.0, opacity))
            if animation is not None:
                ov["animation"] = animation if animation in VALID_OVERLAY_ANIMATIONS else "none"
            if animation_duration is not None:
                ov["animation_duration"] = max(0.1, min(2.0, animation_duration))
            if layer is not None:
                ov["layer"] = layer

            from services.edit_state import _mark_dirty
            _mark_dirty(state, ov.get("start", 0), ov.get("end", 0))
            logger.info(f"Updated overlay {overlay_id}")
            return state

    logger.warning(f"Overlay {overlay_id} not found")
    return state


def delete_overlay(state: Dict[str, Any], overlay_id: str) -> Dict[str, Any]:
    """Delete an overlay."""
    overlays = state.get("overlays", [])
    for ov in overlays:
        if ov["id"] == overlay_id:
            from services.edit_state import _mark_dirty
            _mark_dirty(state, ov.get("start", 0), ov.get("end", 0))
            state["overlays"] = [o for o in overlays if o["id"] != overlay_id]
            logger.info(f"Deleted overlay {overlay_id}")
            return state
    return state


def get_overlays(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all overlays."""
    return state.get("overlays", [])


def get_overlays_in_range(
    state: Dict[str, Any], start: float, end: float
) -> List[Dict[str, Any]]:
    """Get overlays that overlap with a time range."""
    overlays = state.get("overlays", [])
    return [
        o for o in overlays
        if o.get("start", 0) < end
        and o.get("end", 0) > start
    ]


def get_overlay(state: Dict[str, Any], overlay_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific overlay."""
    return next((o for o in state.get("overlays", []) if o["id"] == overlay_id), None)


def reorder_overlay(state: Dict[str, Any], overlay_id: str, new_layer: int) -> Dict[str, Any]:
    """Change the layer order of an overlay."""
    overlays = state.get("overlays", [])
    for ov in overlays:
        if ov["id"] == overlay_id:
            ov["layer"] = max(0, new_layer)
            return state
    return state
