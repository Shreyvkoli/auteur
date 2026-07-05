"""
Effects Engine — Color grading, LUT presets, blur, shake, glow, and more.

Supports:
  - Color grading (brightness, contrast, saturation, hue, temperature)
  - LUT presets
  - Blur (gaussian, motion, radial)
  - Camera shake
  - Glow / bloom
  - Vignette
  - Grain / noise
  - Speed ramp
  - Reverse
  - Freeze frame
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

VALID_COLOR_GRADES = {
    "none", "warm", "cool", "cinematic", "vibrant", "matte",
    "vintage", "noir", "sunset", "ocean", "forest", "neon",
    "pastel", "dramatic", "bleach_bypass", "cross_process",
}

VALID_BLUR_TYPES = {"gaussian", "motion", "radial", "pixelate", "depth_of_field"}


def _new_effect_id() -> str:
    return f"fx_{uuid4().hex[:12]}"


def set_color_grading(
    state: Dict[str, Any],
    grade: str = "none",
    brightness: Optional[float] = None,
    contrast: Optional[float] = None,
    saturation: Optional[float] = None,
    hue: Optional[float] = None,
    temperature: Optional[float] = None,
    shadows: Optional[float] = None,
    highlights: Optional[float] = None,
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> Dict[str, Any]:
    """Set color grading on the entire timeline or a specific range."""
    if grade not in VALID_COLOR_GRADES:
        raise ValueError(f"Invalid color grade: {grade}. Valid: {VALID_COLOR_GRADES}")

    effects = state.setdefault("effects", {})

    if start is not None and end is not None:
        graded_ranges = effects.setdefault("graded_ranges", [])
        graded_range = {
            "id": _new_effect_id(),
            "grade": grade,
            "brightness": brightness,
            "contrast": contrast,
            "saturation": saturation,
            "hue": hue,
            "temperature": temperature,
            "shadows": shadows,
            "highlights": highlights,
            "start": start,
            "end": end,
        }
        graded_ranges.append(graded_range)
        from services.edit_state import _mark_dirty
        _mark_dirty(state, start, end)
    else:
        effects["color_grade"] = grade
        if brightness is not None:
            effects["brightness"] = max(-1.0, min(1.0, brightness))
        if contrast is not None:
            effects["contrast"] = max(0.0, min(3.0, contrast))
        if saturation is not None:
            effects["saturation"] = max(0.0, min(3.0, saturation))
        if hue is not None:
            effects["hue"] = max(-180.0, min(180.0, hue))
        if temperature is not None:
            effects["temperature"] = max(-1.0, min(1.0, temperature))
        if shadows is not None:
            effects["shadows"] = max(-1.0, min(1.0, shadows))
        if highlights is not None:
            effects["highlights"] = max(-1.0, min(1.0, highlights))
        from services.edit_state import _mark_dirty, mark_all_dirty
        mark_all_dirty(state)

    logger.info(f"Set color grading: {grade}")
    return state


def add_blur_effect(
    state: Dict[str, Any],
    blur_type: str = "gaussian",
    intensity: float = 5.0,
    start: float = 0.0,
    end: float = 0.0,
    region: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Add a blur effect to a time range."""
    if blur_type not in VALID_BLUR_TYPES:
        raise ValueError(f"Invalid blur type: {blur_type}")

    effects = state.setdefault("effects", {})
    blurs = effects.setdefault("blur_effects", [])

    blur = {
        "id": _new_effect_id(),
        "type": "blur",
        "blur_type": blur_type,
        "intensity": max(0.1, min(50.0, intensity)),
        "start": start,
        "end": end,
        "region": region,
    }
    blurs.append(blur)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)
    logger.info(f"Added {blur_type} blur at {start:.1f}-{end:.1f}s")
    return state


def add_shake_effect(
    state: Dict[str, Any],
    intensity: float = 5.0,
    frequency: float = 10.0,
    start: float = 0.0,
    end: float = 0.0,
) -> Dict[str, Any]:
    """Add camera shake effect."""
    effects = state.setdefault("effects", {})
    shakes = effects.setdefault("shake_effects", [])

    shake = {
        "id": _new_effect_id(),
        "type": "shake",
        "intensity": max(0.5, min(30.0, intensity)),
        "frequency": max(1.0, min(60.0, frequency)),
        "start": start,
        "end": end,
    }
    shakes.append(shake)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)
    logger.info(f"Added shake effect at {start:.1f}-{end:.1f}s")
    return state


def add_glow_effect(
    state: Dict[str, Any],
    intensity: float = 0.5,
    radius: float = 10.0,
    start: float = 0.0,
    end: float = 0.0,
) -> Dict[str, Any]:
    """Add glow/bloom effect."""
    effects = state.setdefault("effects", {})
    glows = effects.setdefault("glow_effects", [])

    glow = {
        "id": _new_effect_id(),
        "type": "glow",
        "intensity": max(0.0, min(2.0, intensity)),
        "radius": max(1.0, min(50.0, radius)),
        "start": start,
        "end": end,
    }
    glows.append(glow)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)
    logger.info(f"Added glow effect at {start:.1f}-{end:.1f}s")
    return state


def add_vignette(
    state: Dict[str, Any],
    intensity: float = 0.5,
    start: float = 0.0,
    end: float = 0.0,
) -> Dict[str, Any]:
    """Add vignette effect."""
    effects = state.setdefault("effects", {})
    vignettes = effects.setdefault("vignette_effects", [])

    vignette = {
        "id": _new_effect_id(),
        "type": "vignette",
        "intensity": max(0.0, min(1.0, intensity)),
        "start": start,
        "end": end,
    }
    vignettes.append(vignette)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)
    logger.info(f"Added vignette at {start:.1f}-{end:.1f}s")
    return state


def add_grain(
    state: Dict[str, Any],
    intensity: float = 0.3,
    start: float = 0.0,
    end: float = 0.0,
) -> Dict[str, Any]:
    """Add film grain effect."""
    effects = state.setdefault("effects", {})
    grains = effects.setdefault("grain_effects", [])

    grain = {
        "id": _new_effect_id(),
        "type": "grain",
        "intensity": max(0.0, min(1.0, intensity)),
        "start": start,
        "end": end,
    }
    grains.append(grain)

    from services.edit_state import _mark_dirty
    _mark_dirty(state, start, end)
    return state


def remove_effect(
    state: Dict[str, Any],
    effect_id: str,
) -> Dict[str, Any]:
    """Remove an effect by ID from any effects list."""
    effects = state.get("effects", {})
    for key in ("blur_effects", "shake_effects", "glow_effects", "vignette_effects", "grain_effects"):
        items = effects.get(key, [])
        for item in items:
            if item.get("id") == effect_id:
                from services.edit_state import _mark_dirty
                _mark_dirty(state, item.get("start", 0), item.get("end", 0))
                effects[key] = [i for i in items if i["id"] != effect_id]
                logger.info(f"Removed effect {effect_id}")
                return state

    logger.warning(f"Effect {effect_id} not found")
    return state


def get_all_effects(state: Dict[str, Any]) -> Dict[str, Any]:
    """Get all effects in the state."""
    effects = state.get("effects", {})
    return {
        "color_grade": effects.get("color_grade", "none"),
        "brightness": effects.get("brightness"),
        "contrast": effects.get("contrast"),
        "saturation": effects.get("saturation"),
        "blur_effects": effects.get("blur_effects", []),
        "shake_effects": effects.get("shake_effects", []),
        "glow_effects": effects.get("glow_effects", []),
        "vignette_effects": effects.get("vignette_effects", []),
        "grain_effects": effects.get("grain_effects", []),
    }


def build_color_filter(effects: Dict[str, Any]) -> str:
    """Build FFmpeg filter string for color grading."""
    parts = []

    brightness = effects.get("brightness")
    if brightness is not None:
        parts.append(f"eq=brightness={brightness}")

    contrast = effects.get("contrast")
    if contrast is not None:
        parts.append(f"eq=contrast={contrast}")

    saturation = effects.get("saturation")
    if saturation is not None:
        parts.append(f"eq=saturation={saturation}")

    hue = effects.get("hue")
    if hue is not None:
        parts.append(f"hue=h={hue}")

    temperature = effects.get("temperature")
    if temperature is not None:
        if temperature > 0:
            parts.append(f"curves=r='0/0 0.5/{0.5 + temperature * 0.2} 1/1'")
        elif temperature < 0:
            abs_t = abs(temperature)
            parts.append(f"curves=b='0/0 0.5/{0.5 + abs_t * 0.2} 1/1'")

    return ",".join(parts) if parts else None


def build_blur_filter(blur: Dict[str, Any], video_width: int = 1080, video_height: int = 1920) -> str:
    """Build FFmpeg filter string for blur effect."""
    blur_type = blur.get("blur_type", "gaussian")
    intensity = blur.get("intensity", 5.0)

    if blur_type == "gaussian":
        return f"boxblur={intensity}:{intensity}"
    elif blur_type == "motion":
        return f"boxblur={intensity * 2}:{intensity}"
    elif blur_type == "radial":
        return f"gblur=sigma={intensity}"
    elif blur_type == "pixelate":
        pixel_size = max(2, int(intensity * 3))
        return f"scale=1:{pixel_size},scale={video_width}:{video_height}:flags=neighbor"
    elif blur_type == "depth_of_field":
        return f"gblur=sigma={intensity * 0.5}"

    return f"boxblur={intensity}:{intensity}"


def build_shake_filter(shake: Dict[str, Any]) -> str:
    """Build FFmpeg filter string for camera shake."""
    intensity = shake.get("intensity", 5.0)
    return f"crop=in_w-2*{intensity}:in_h-2*{intensity}:{intensity}+rand(0,{intensity}):{intensity}+rand(0,{intensity})"


def build_glow_filter(glow: Dict[str, Any]) -> str:
    """Build FFmpeg filter string for glow effect."""
    intensity = glow.get("intensity", 0.5)
    radius = glow.get("radius", 10.0)
    return f"gblur=sigma={radius},curves=all='0/0 0.5/{0.5 + intensity * 0.3} 1/1'"


def build_vignette_filter(vignette: Dict[str, Any]) -> str:
    """Build FFmpeg filter string for vignette."""
    intensity = vignette.get("intensity", 0.5)
    angle = 0.5 - intensity * 0.3
    return f"vignette=PI/{max(0.1, angle)}"


def build_grain_filter(grain: Dict[str, Any]) -> str:
    """Build FFmpeg filter string for film grain."""
    intensity = grain.get("intensity", 0.3)
    return f"noise=alls={intensity * 100}:allf=t"
