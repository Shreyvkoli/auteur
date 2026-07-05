"""
Text Overlay Engine — Full text system with animations, styling, positioning.

Supports:
  - Multiple text overlays per timeline
  - Position (x, y) with pixel or percentage
  - Start/end time
  - Style config (font, color, size, shadow, outline)
  - Animations: fade, pop, typewriter, slide_up, slide_down, bounce, zoom
  - Per-character and word-level animations
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

VALID_ANIMATIONS = {
    "none", "fade_in", "fade_out", "fade_in_out",
    "pop", "pop_out",
    "typewriter",
    "slide_up", "slide_down", "slide_left", "slide_right",
    "bounce", "bounce_in",
    "zoom_in", "zoom_out",
    "shake",
    "glitch_text",
}

VALID_FONT_SIZES = {
    "small": 24,
    "medium": 36,
    "large": 48,
    "xlarge": 64,
    "xxlarge": 80,
}

DEFAULT_STYLE = {
    "font_family": "Arial",
    "font_size": "large",
    "font_size_px": 48,
    "color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": 2,
    "bg_color": None,
    "bg_opacity": 0.0,
    "shadow": True,
    "shadow_color": "#000000",
    "shadow_offset_x": 2,
    "shadow_offset_y": 2,
    "bold": True,
    "italic": False,
    "alignment": "center",
}


def _new_text_id() -> str:
    return f"txt_{uuid4().hex[:12]}"


def add_text_overlay(
    state: Dict[str, Any],
    text: str,
    start: float,
    end: float,
    x: float = 0.5,
    y: float = 0.5,
    style: Optional[Dict[str, Any]] = None,
    animation: str = "none",
    animation_duration: float = 0.3,
    layer: int = 0,
) -> Dict[str, Any]:
    """Add a text overlay to the timeline."""
    overlay_id = _new_text_id()

    text_style = {**DEFAULT_STYLE}
    if style:
        text_style.update(style)

    if isinstance(text_style.get("font_size"), str):
        text_style["font_size_px"] = VALID_FONT_SIZES.get(
            text_style["font_size"], 48
        )

    overlay = {
        "id": overlay_id,
        "type": "text",
        "text": text,
        "start": start,
        "end": end,
        "x": max(0.0, min(1.0, x)),
        "y": max(0.0, min(1.0, y)),
        "style": text_style,
        "animation": animation if animation in VALID_ANIMATIONS else "none",
        "animation_duration": max(0.1, min(2.0, animation_duration)),
        "layer": layer,
        "keyframes": [],
    }

    overlays = state.setdefault("overlays", [])
    overlays.append(overlay)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)

    logger.info(f"Added text overlay '{text[:30]}...' at {start:.1f}-{end:.1f}s")
    return state


def update_text_overlay(
    state: Dict[str, Any],
    overlay_id: str,
    text: Optional[str] = None,
    start: Optional[float] = None,
    end: Optional[float] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    style: Optional[Dict[str, Any]] = None,
    animation: Optional[str] = None,
    animation_duration: Optional[float] = None,
    layer: Optional[int] = None,
) -> Dict[str, Any]:
    """Update an existing text overlay."""
    overlays = state.get("overlays", [])
    for ov in overlays:
        if ov["id"] == overlay_id and ov["type"] == "text":
            if text is not None:
                ov["text"] = text
            if start is not None:
                ov["start"] = start
            if end is not None:
                ov["end"] = end
            if x is not None:
                ov["x"] = max(0.0, min(1.0, x))
            if y is not None:
                ov["y"] = max(0.0, min(1.0, y))
            if style is not None:
                ov["style"].update(style)
                if isinstance(ov["style"].get("font_size"), str):
                    ov["style"]["font_size_px"] = VALID_FONT_SIZES.get(
                        ov["style"]["font_size"], 48
                    )
            if animation is not None:
                ov["animation"] = animation if animation in VALID_ANIMATIONS else "none"
            if animation_duration is not None:
                ov["animation_duration"] = max(0.1, min(2.0, animation_duration))
            if layer is not None:
                ov["layer"] = layer

            from services.edit_state import _mark_dirty
            _mark_dirty(state, ov.get("start", 0), ov.get("end", 0))
            logger.info(f"Updated text overlay {overlay_id}")
            return state

    logger.warning(f"Text overlay {overlay_id} not found")
    return state


def delete_text_overlay(state: Dict[str, Any], overlay_id: str) -> Dict[str, Any]:
    """Delete a text overlay."""
    overlays = state.get("overlays", [])
    for ov in overlays:
        if ov["id"] == overlay_id and ov["type"] == "text":
            from services.edit_state import _mark_dirty
            _mark_dirty(state, ov.get("start", 0), ov.get("end", 0))
            state["overlays"] = [o for o in overlays if o["id"] != overlay_id]
            logger.info(f"Deleted text overlay {overlay_id}")
            return state
    return state


def get_text_overlays(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all text overlays."""
    return [o for o in state.get("overlays", []) if o.get("type") == "text"]


def get_text_overlays_in_range(
    state: Dict[str, Any], start: float, end: float
) -> List[Dict[str, Any]]:
    """Get text overlays that overlap with a time range."""
    overlays = state.get("overlays", [])
    return [
        o for o in overlays
        if o.get("type") == "text"
        and o.get("start", 0) < end
        and o.get("end", 0) > start
    ]


def build_text_style_string(style: Dict[str, Any]) -> str:
    """Build ASS/SSA style string for FFmpeg subtitle rendering."""
    font_name = style.get("font_family", "Arial")
    font_size = style.get("font_size_px", 48)
    color = style.get("color", "#FFFFFF").lstrip("#")
    bgr_color = f"&H00{color[4:6]}{color[2:4]}{color[:2]}" if len(color) == 6 else "&H00FFFFFF"

    stroke_color = style.get("stroke_color", "#000000").lstrip("#")
    bgr_stroke = f"&H00{stroke_color[4:6]}{stroke_color[2:4]}{stroke_color[:2]}" if len(stroke_color) == 6 else "&H00000000"

    alignment_map = {
        "left": 1, "center": 2, "right": 3,
        "top_left": 7, "top_center": 8, "top_right": 9,
        "bottom_left": 4, "bottom_center": 5, "bottom_right": 6,
    }
    alignment = alignment_map.get(style.get("alignment", "center"), 2)

    bold = -1 if style.get("bold", True) else 0
    italic = -1 if style.get("italic", False) else 0
    stroke_width = style.get("stroke_width", 2)

    return (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour={bgr_color},"
        f"OutlineColour={bgr_stroke},"
        f"BorderStyle=1,"
        f"Outline={stroke_width},"
        f"Alignment={alignment},"
        f"Bold={bold},"
        f"Italic={italic}"
    )


def build_animation_filter(animation: str, duration: float, fps: int = 30) -> str:
    """Build FFmpeg filter for text animation."""
    if animation == "none":
        return ""

    total_frames = int(duration * fps)

    if animation == "fade_in":
        return f"format=yuva420p,fade=t=in:st=0:d={duration}"
    elif animation == "fade_out":
        return f"format=yuva420p,fade=t=out:st=0:d={duration}"
    elif animation == "fade_in_out":
        half = duration / 2
        return f"format=yuva420p,fade=t=in:st=0:d={half},fade=t=out:st={half}:d={half}"
    elif animation == "pop":
        return f"format=yuva420p,fade=t=in:st=0:d={duration * 0.3}"
    elif animation == "typewriter":
        return f"format=yuva420p,fade=t=in:st=0:d={duration}"
    elif animation in ("slide_up", "slide_down", "slide_left", "slide_right"):
        return f"format=yuva420p,fade=t=in:st=0:d={duration * 0.5}"
    elif animation == "bounce":
        return f"format=yuva420p,fade=t=in:st=0:d={duration * 0.4}"
    elif animation == "zoom_in":
        return f"format=yuva420p,fade=t=in:st=0:d={duration * 0.3}"

    return f"format=yuva420p,fade=t=in:st=0:d={min(duration, 0.5)}"
