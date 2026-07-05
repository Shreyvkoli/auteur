"""
Edit State Service — The Source of Truth for every edit.

Edit state is a persistent JSON document that stores:
  - timeline (ordered segments)
  - clips (source video references)
  - captions (text overlays with timestamps)
  - audio_tracks (music, sound effects, voiceovers)
  - effects (color grade, transitions)
  - metadata (duration, dimensions)

All manual edits and prompt edits modify THIS document.
The render layer reads THIS document to produce output.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from uuid import uuid4
from datetime import datetime

from core.database import get_supabase

logger = logging.getLogger(__name__)


# ── CRUD ───────────────────────────────────────────────────────────────────────

def create_edit_state(
    job_id: str,
    user_id: str,
    video_id: str,
    mode: str = "reels",
) -> Dict[str, Any]:
    """Create a new edit state for a job. Returns the state dict."""
    supabase = get_supabase()
    state_id = str(uuid4())

    # Fetch actual video duration from DB
    video_duration = 0
    video_fps = 30
    video_width = 1080
    video_height = 1920
    try:
        video = supabase.table("videos").select("*").eq("id", video_id).single().execute()
        if video.data:
            video_duration = video.data.get("duration", 0) or 0
            video_fps = video.data.get("fps", 30) or 30
            video_width = video.data.get("width", 1080) or 1080
            video_height = video.data.get("height", 1920) or 1920
    except Exception:
        pass

    clip_id = video_id
    segment_id = str(uuid4())
    dur = max(video_duration, 1)

    default_state = {
        "id": state_id,
        "job_id": job_id,
        "user_id": user_id,
        "video_id": video_id,
        "mode": mode,
        "timeline": [
            {
                "id": segment_id,
                "clip_id": clip_id,
                "source_start": 0.0,
                "source_end": dur,
                "timeline_start": 0.0,
                "timeline_end": dur,
                "speed": 1.0,
                "reversed": False,
                "opacity": 1.0,
                "rotation": 0.0,
                "volume": 1.0,
                "freeze_frame": None,
                "crop": None,
            },
        ],
        "clips": [
            {
                "id": clip_id,
                "video_id": video_id,
                "source_url": "",
                "duration": dur,
                "fps": video_fps,
                "width": video_width,
                "height": video_height,
            },
        ],
        "captions": [],
        "audio_tracks": [],
        "effects": {
            "color_grade": "none",
            "transitions": [],
            "blur_background": False,
            "blur_effects": [],
            "shake_effects": [],
            "glow_effects": [],
            "vignette_effects": [],
            "grain_effects": [],
        },
        "metadata": {
            "total_duration": dur,
            "fps": video_fps,
            "width": video_width,
            "height": video_height,
            "mode": mode,
            "aspect_ratio": "9:16",
            "auto_reframe": False,
        },
        "dirty_segments": [],
        "version": 1,
        "version_history": [],
        "undo_stack": [],
        "redo_stack": [],
        "keyframes": [],
        "overlays": [],
        "playback": {
            "playhead": 0.0,
            "playing": False,
            "speed": 1.0,
            "loop_start": None,
            "loop_end": None,
            "loop_enabled": False,
            "markers": [],
        },
        "audio_ducking": None,
    }

    supabase.table("edit_states").insert(default_state.copy()).execute()
    logger.info(f"Edit state created for job {job_id}")
    return default_state


def get_edit_state(job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the current edit state for a job."""
    supabase = get_supabase()
    result = (
        supabase.table("edit_states")
        .select("*")
        .eq("job_id", job_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        return None
    return _deserialize(result.data)


def get_edit_state_by_id(state_id: str) -> Optional[Dict[str, Any]]:
    """Fetch edit state by its primary key."""
    supabase = get_supabase()
    result = (
        supabase.table("edit_states")
        .select("*")
        .eq("id", state_id)
        .single()
        .execute()
    )
    if not result.data:
        return None
    return _deserialize(result.data)


def save_edit_state(state: Dict[str, Any]) -> bool:
    """Persist the full edit state to DB. Increments version."""
    supabase = get_supabase()
    state["version"] = state.get("version", 0) + 1
    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        supabase.table("edit_states").update(state).eq("id", state["id"]).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save edit state: {e}")
        return False


# ── Timeline Operations ─────────────────────────────────────────────────────────

def _new_clip_id() -> str:
    return f"clip_{uuid4().hex[:12]}"


def _new_caption_id() -> str:
    return f"cap_{uuid4().hex[:12]}"


def _new_track_id() -> str:
    return f"track_{uuid4().hex[:12]}"


def state_add_clip(state: Dict[str, Any], source_url: str, duration: float) -> Dict[str, Any]:
    """Add a source clip reference to the state."""
    clip_id = _new_clip_id()
    clip = {
        "id": clip_id,
        "video_id": state["video_id"],
        "source_url": source_url,
        "duration": duration,
        "fps": 30,
        "width": 1080,
        "height": 1920,
    }
    state["clips"].append(clip)

    # Also add a timeline segment for the full clip
    seg_id = f"seg_{clip_id}"
    seg = {
        "id": seg_id,
        "clip_id": clip_id,
        "source_start": 0,
        "source_end": duration,
        "timeline_start": state["metadata"]["total_duration"],
        "timeline_end": state["metadata"]["total_duration"] + duration,
        "speed": 1.0,
    }
    state["timeline"].append(seg)
    state["metadata"]["total_duration"] += duration
    _mark_dirty(state, 0, duration)
    return state


def action_trim(state: Dict[str, Any], clip_id: str, start: float, end: float) -> Dict[str, Any]:
    """Trim a timeline segment to new start/end times."""
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            old_start = seg["source_start"]
            old_end = seg["source_end"]
            seg["source_start"] = start
            seg["source_end"] = end
            duration_change = (old_end - old_start) - (end - start)
            seg["timeline_end"] = seg["timeline_start"] + (end - start)
            _shift_subsequent(state, seg["timeline_start"] + (end - start), duration_change)
            _rebuild_timeline_positions(state)
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            logger.info(f"Trimmed {clip_id}: {old_start}-{old_end} -> {start}-{end}")
            return state
    logger.warning(f"Clip {clip_id} not found for trim")
    return state


def action_split(state: Dict[str, Any], clip_id: str, at: float) -> Dict[str, Any]:
    """Split a timeline segment at a given timestamp."""
    for i, seg in enumerate(state["timeline"]):
        if seg["clip_id"] == clip_id:
            if at <= seg["source_start"] or at >= seg["source_end"]:
                logger.warning(f"Cannot split {clip_id} at {at}: outside bounds")
                return state

            new_clip_id = _new_clip_id()
            new_seg = {
                "id": f"seg_{new_clip_id}",
                "clip_id": new_clip_id,
                "source_start": at,
                "source_end": seg["source_end"],
                "timeline_start": at,
                "timeline_end": seg["timeline_end"],
                "speed": 1.0,
            }

            # Copy source clip ref
            original_clip = next((c for c in state["clips"] if c["id"] == clip_id), None)
            if original_clip:
                new_clip = original_clip.copy()
                new_clip["id"] = new_clip_id
                state["clips"].append(new_clip)

            seg["source_end"] = at
            seg["timeline_end"] = at

            state["timeline"].insert(i + 1, new_seg)
            _rebuild_timeline_positions(state)
            _mark_dirty(state, seg["timeline_start"], new_seg["timeline_end"])
            logger.info(f"Split {clip_id} at {at}")
            return state
    return state


def action_delete(state: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    """Remove a timeline segment."""
    for i, seg in enumerate(state["timeline"]):
        if seg["clip_id"] == clip_id:
            duration = seg["timeline_end"] - seg["timeline_start"]
            state["timeline"].pop(i)
            _rebuild_timeline_positions(state)
            state["metadata"]["total_duration"] -= duration
            logger.info(f"Deleted {clip_id}")
            return state
    return state


def action_move(state: Dict[str, Any], clip_id: str, new_position: int) -> Dict[str, Any]:
    """Reorder a timeline segment to a new position."""
    seg = None
    for i, s in enumerate(state["timeline"]):
        if s["clip_id"] == clip_id:
            seg = state["timeline"].pop(i)
            break
    if not seg:
        return state
    new_position = max(0, min(new_position, len(state["timeline"])))
    state["timeline"].insert(new_position, seg)
    _rebuild_timeline_positions(state)
    _mark_dirty(state, 0, state["metadata"]["total_duration"])
    return state


def action_replace_asset(state: Dict[str, Any], clip_id: str, source_url: str) -> Dict[str, Any]:
    """Replace the source asset for a clip."""
    for clip in state["clips"]:
        if clip["id"] == clip_id:
            clip["source_url"] = source_url
            logger.info(f"Replaced asset for {clip_id}")
            return state
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            for clip in state["clips"]:
                if clip["id"] == clip_id:
                    clip["source_url"] = source_url
                    break
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            return state
    return state


def action_duplicate(state: Dict[str, Any], clip_id: str, count: int = 1) -> Dict[str, Any]:
    """Duplicate a timeline segment N times (appends after original)."""
    seg = None
    for s in state["timeline"]:
        if s["clip_id"] == clip_id:
            seg = s
            break
    if not seg:
        logger.warning(f"Clip {clip_id} not found for duplicate")
        return state

    original_clip = next((c for c in state["clips"] if c["id"] == clip_id), None)
    insert_idx = next(
        (i for i, s in enumerate(state["timeline"]) if s["clip_id"] == clip_id),
        len(state["timeline"]) - 1,
    ) + 1

    for _ in range(max(1, min(count, 10))):
        new_clip_id = _new_clip_id()
        new_seg_id = f"seg_{new_clip_id}"

        if original_clip:
            new_clip = original_clip.copy()
            new_clip["id"] = new_clip_id
            state["clips"].append(new_clip)

        duration = seg["source_end"] - seg["source_start"]
        new_seg = {
            "id": new_seg_id,
            "clip_id": new_clip_id,
            "source_start": seg["source_start"],
            "source_end": seg["source_end"],
            "timeline_start": 0,
            "timeline_end": 0,
            "speed": seg.get("speed", 1.0),
            "reversed": seg.get("reversed", False),
            "opacity": seg.get("opacity", 1.0),
            "rotation": seg.get("rotation", 0.0),
            "volume": seg.get("volume", 1.0),
        }
        state["timeline"].insert(insert_idx, new_seg)
        insert_idx += 1

    _rebuild_timeline_positions(state)
    _mark_dirty(state, seg["timeline_start"], state["metadata"]["total_duration"])
    logger.info(f"Duplicated {clip_id} x{count}")
    return state


def action_speed_change(state: Dict[str, Any], clip_id: str, speed: float) -> Dict[str, Any]:
    """Change the playback speed of a clip."""
    speed = max(0.1, min(10.0, speed))
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            seg["speed"] = speed
            _rebuild_timeline_positions(state)
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            logger.info(f"Speed changed {clip_id} → {speed}x")
            return state
    logger.warning(f"Clip {clip_id} not found for speed change")
    return state


def action_reverse(state: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    """Reverse a clip's playback direction."""
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            seg["reversed"] = not seg.get("reversed", False)
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            logger.info(f"Reversed {clip_id}: now={seg['reversed']}")
            return state
    logger.warning(f"Clip {clip_id} not found for reverse")
    return state


def action_freeze_frame(
    state: Dict[str, Any], clip_id: str, at: float, duration: float = 2.0
) -> Dict[str, Any]:
    """Insert a freeze frame at a specific time within a clip."""
    for i, seg in enumerate(state["timeline"]):
        if seg["clip_id"] == clip_id:
            if at < seg["source_start"] or at > seg["source_end"]:
                logger.warning(f"Freeze frame time {at} outside clip bounds")
                return state

            new_clip_id = _new_clip_id()
            original_clip = next((c for c in state["clips"] if c["id"] == clip_id), None)
            if original_clip:
                new_clip = original_clip.copy()
                new_clip["id"] = new_clip_id
                state["clips"].append(new_clip)

            freeze_seg = {
                "id": f"seg_{new_clip_id}",
                "clip_id": new_clip_id,
                "source_start": at,
                "source_end": at + 0.001,
                "timeline_start": 0,
                "timeline_end": 0,
                "speed": 1.0,
                "reversed": False,
                "opacity": 1.0,
                "rotation": 0.0,
                "volume": 1.0,
                "freeze_frame": {
                    "at": at,
                    "duration": duration,
                },
            }

            split_point = at
            original_end = seg["source_end"]
            seg["source_end"] = split_point
            state["timeline"].insert(i + 1, freeze_seg)
            remainder_seg = {
                "id": f"seg_{_new_clip_id()}",
                "clip_id": clip_id,
                "source_start": split_point,
                "source_end": original_end,
                "timeline_start": 0,
                "timeline_end": 0,
                "speed": seg.get("speed", 1.0),
                "reversed": seg.get("reversed", False),
                "opacity": seg.get("opacity", 1.0),
                "rotation": seg.get("rotation", 0.0),
                "volume": seg.get("volume", 1.0),
            }
            state["timeline"].insert(i + 2, remainder_seg)

            _rebuild_timeline_positions(state)
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"] + duration)
            logger.info(f"Freeze frame inserted at {at}s for {duration}s")
            return state
    return state


def action_crop(
    state: Dict[str, Any],
    clip_id: str,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 1.0,
    height: float = 1.0,
) -> Dict[str, Any]:
    """Crop a clip to a specific region (0-1 normalized coordinates)."""
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            seg["crop"] = {
                "x": max(0.0, min(1.0, x)),
                "y": max(0.0, min(1.0, y)),
                "width": max(0.05, min(1.0, width)),
                "height": max(0.05, min(1.0, height)),
            }
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            logger.info(f"Cropped {clip_id}")
            return state
    logger.warning(f"Clip {clip_id} not found for crop")
    return state


def action_rotate(state: Dict[str, Any], clip_id: str, degrees: float) -> Dict[str, Any]:
    """Rotate a clip by specified degrees."""
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            seg["rotation"] = degrees % 360
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            logger.info(f"Rotated {clip_id} → {degrees}°")
            return state
    logger.warning(f"Clip {clip_id} not found for rotate")
    return state


def action_opacity(state: Dict[str, Any], clip_id: str, opacity: float) -> Dict[str, Any]:
    """Set the opacity of a clip (0.0 to 1.0)."""
    for seg in state["timeline"]:
        if seg["clip_id"] == clip_id:
            seg["opacity"] = max(0.0, min(1.0, opacity))
            _mark_dirty(state, seg["timeline_start"], seg["timeline_end"])
            logger.info(f"Opacity {clip_id} → {opacity}")
            return state
    logger.warning(f"Clip {clip_id} not found for opacity")
    return state


def action_move_clip(state: Dict[str, Any], clip_id: str, new_start: float) -> Dict[str, Any]:
    """Move a clip to a new position on the timeline by absolute time."""
    seg = None
    for i, s in enumerate(state["timeline"]):
        if s["clip_id"] == clip_id:
            seg = state["timeline"].pop(i)
            break
    if not seg:
        return state

    duration = seg["source_end"] - seg["source_start"]
    seg["timeline_start"] = new_start
    seg["timeline_end"] = new_start + duration

    insert_idx = 0
    for i, s in enumerate(state["timeline"]):
        if s["timeline_start"] < new_start:
            insert_idx = i + 1

    state["timeline"].insert(insert_idx, seg)
    _rebuild_timeline_positions(state)
    _mark_dirty(state, 0, state["metadata"]["total_duration"])
    return state


# ── Caption Operations ──────────────────────────────────────────────────────────

def action_update_caption(
    state: Dict[str, Any],
    caption_id: str,
    text: Optional[str] = None,
    style: Optional[str] = None,
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> Dict[str, Any]:
    """Modify a caption entry."""
    for cap in state["captions"]:
        if cap["id"] == caption_id:
            if text is not None:
                cap["text"] = text
            if style is not None:
                cap["style"] = style
            if start is not None:
                cap["start"] = start
            if end is not None:
                cap["end"] = end
            _mark_dirty(state, cap.get("start", 0), cap.get("end", 0))
            logger.info(f"Updated caption {caption_id}")
            return state
    logger.warning(f"Caption {caption_id} not found")
    return state


def action_audio_edit(
    state: Dict[str, Any],
    track_id: str,
    volume: Optional[float] = None,
    source_url: Optional[str] = None,
    start: Optional[float] = None,
) -> Dict[str, Any]:
    """Modify an audio track."""
    for track in state["audio_tracks"]:
        if track["id"] == track_id:
            if volume is not None:
                track["volume"] = volume
            if source_url is not None:
                track["source_url"] = source_url
            if start is not None:
                track["start"] = start
            logger.info(f"Updated audio track {track_id}")
            return state
    logger.warning(f"Audio track {track_id} not found")
    return state


# ── Dirty Tracking ──────────────────────────────────────────────────────────────

def _mark_dirty(state: Dict[str, Any], start: float, end: float) -> None:
    """Mark a time range as needing re-render."""
    state["dirty_segments"].append({"start": start, "end": end})


def mark_all_dirty(state: Dict[str, Any]) -> None:
    """Mark entire timeline as dirty (full re-render)."""
    state["dirty_segments"] = [{"start": 0, "end": state["metadata"]["total_duration"]}]


def clear_dirty(state: Dict[str, Any]) -> None:
    """Clear dirty segments after render."""
    state["dirty_segments"] = []


def get_dirty_ranges(state: Dict[str, Any]) -> List[Dict[str, float]]:
    """Get merged dirty ranges for efficient partial render."""
    if not state.get("dirty_segments"):
        return []

    ranges = sorted(state["dirty_segments"], key=lambda r: r["start"])
    merged = [ranges[0]]
    for r in ranges[1:]:
        if r["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        else:
            merged.append(r)
    return merged


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _rebuild_timeline_positions(state: Dict[str, Any]) -> None:
    """Recalculate timeline_start/timeline_end for all segments."""
    cursor = 0.0
    for seg in state["timeline"]:
        source_duration = seg["source_end"] - seg["source_start"]
        speed = seg.get("speed", 1.0)
        if speed <= 0:
            speed = 1.0
        ff = seg.get("freeze_frame")
        if ff:
            duration = ff.get("duration", 2.0)
        else:
            duration = source_duration / speed
        seg["timeline_start"] = cursor
        seg["timeline_end"] = cursor + duration
        cursor += duration
    state["metadata"]["total_duration"] = cursor


def _shift_subsequent(state: Dict[str, Any], after: float, by: float) -> None:
    """Shift all timeline segments after `after` by `by` seconds."""
    for seg in state["timeline"]:
        if seg["timeline_start"] >= after:
            seg["timeline_start"] += by
            seg["timeline_end"] += by
    state["metadata"]["total_duration"] += by


def _deserialize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DB row to mutable dict, handling JSONB fields."""
    for field in ("timeline", "clips", "captions", "audio_tracks", "dirty_segments",
                  "keyframes", "overlays"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    for field in ("effects", "metadata", "playback"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    for field in ("version_history", "undo_stack", "redo_stack"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    if isinstance(data.get("audio_ducking"), str):
        data["audio_ducking"] = json.loads(data["audio_ducking"])
    return data


# ── Undo/Redo System ──────────────────────────────────────────────────────────

MAX_HISTORY = 50


def _snapshot_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Create a deep copy snapshot of the current state for undo history."""
    import copy
    snapshot = copy.deepcopy(state)
    snapshot.pop("version_history", None)
    snapshot.pop("undo_stack", None)
    snapshot.pop("redo_stack", None)
    return snapshot


def push_undo(state: Dict[str, Any]) -> Dict[str, Any]:
    """Save current state to undo stack before making a change."""
    snapshot = _snapshot_state(state)
    undo_stack = state.get("undo_stack", [])
    undo_stack.append(snapshot)
    if len(undo_stack) > MAX_HISTORY:
        undo_stack = undo_stack[-MAX_HISTORY:]
    state["undo_stack"] = undo_stack
    state["redo_stack"] = []
    return state


def undo(state: Dict[str, Any]) -> Dict[str, Any]:
    """Undo the last change. Returns the state after undo."""
    undo_stack = state.get("undo_stack", [])
    redo_stack = state.get("redo_stack", [])

    if not undo_stack:
        logger.warning("Nothing to undo")
        return state

    current_snapshot = _snapshot_state(state)
    redo_stack.append(current_snapshot)

    previous = undo_stack.pop()
    state.update(previous)
    state["undo_stack"] = undo_stack
    state["redo_stack"] = redo_stack
    state["version"] = state.get("version", 0) + 1
    logger.info(f"Undo: restored to version {state['version']}")
    return state


def redo(state: Dict[str, Any]) -> Dict[str, Any]:
    """Redo the last undone change. Returns the state after redo."""
    undo_stack = state.get("undo_stack", [])
    redo_stack = state.get("redo_stack", [])

    if not redo_stack:
        logger.warning("Nothing to redo")
        return state

    current_snapshot = _snapshot_state(state)
    undo_stack.append(current_snapshot)

    next_state = redo_stack.pop()
    state.update(next_state)
    state["undo_stack"] = undo_stack
    state["redo_stack"] = redo_stack
    state["version"] = state.get("version", 0) + 1
    logger.info(f"Redo: restored to version {state['version']}")
    return state


def get_undo_stack_size(state: Dict[str, Any]) -> int:
    return len(state.get("undo_stack", []))


def get_redo_stack_size(state: Dict[str, Any]) -> int:
    return len(state.get("redo_stack", []))


# ── Version History ───────────────────────────────────────────────────────────

def save_version(state: Dict[str, Any], label: Optional[str] = None) -> Dict[str, Any]:
    """Save current state as a named version in version_history."""
    snapshot = _snapshot_state(state)
    snapshot["version_label"] = label or f"v{state.get('version', 1)}"
    snapshot["saved_at"] = datetime.utcnow().isoformat()

    history = state.get("version_history", [])
    history.append(snapshot)
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    state["version_history"] = history
    logger.info(f"Version saved: {snapshot['version_label']}")
    return state


def restore_version(state: Dict[str, Any], version_index: int) -> Dict[str, Any]:
    """Restore state from a specific version in history."""
    history = state.get("version_history", [])
    if version_index < 0 or version_index >= len(history):
        logger.warning(f"Invalid version index {version_index}")
        return state

    push_undo(state)
    snapshot = history[version_index]
    state.update(snapshot)
    state["version"] = state.get("version", 0) + 1
    logger.info(f"Restored to version {snapshot.get('version_label', version_index)}")
    return state


def get_version_history(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get summary of version history (without full state data)."""
    history = state.get("version_history", [])
    return [
        {
            "index": i,
            "label": v.get("version_label", f"v{i}"),
            "saved_at": v.get("saved_at", ""),
        }
        for i, v in enumerate(history)
    ]


# ── Edit Plan → Edit State ─────────────────────────────────────────────────────

def edit_plan_to_state(
    edit_plan: Dict[str, Any],
    job_id: str,
    user_id: str,
    video_id: str,
    source_url: str,
    video_duration: float,
    mode: str = "reels",
) -> Dict[str, Any]:
    """
    Convert a GPT-generated edit plan into a full Edit State.
    This is the critical bridge: AI Planning Layer → Edit State Layer.
    """
    state = create_edit_state(job_id, user_id, video_id, mode)

    # Add source clip
    clip_id = _new_clip_id()
    state["clips"].append({
        "id": clip_id,
        "video_id": video_id,
        "source_url": source_url,
        "duration": video_duration,
        "fps": 30,
        "width": 1080,
        "height": 1920,
    })

    # Build timeline segments from cuts
    cuts = edit_plan.get("cuts", [])
    if not cuts:
        cuts = [{"start": 0, "end": video_duration}]

    cursor = 0.0
    for cut in cuts:
        seg_id = f"seg_{uuid4().hex[:12]}"
        duration = cut["end"] - cut["start"]
        seg = {
            "id": seg_id,
            "clip_id": clip_id,
            "source_start": cut["start"],
            "source_end": cut["end"],
            "timeline_start": cursor,
            "timeline_end": cursor + duration,
            "speed": 1.0,
        }
        state["timeline"].append(seg)
        cursor += duration

    state["metadata"]["total_duration"] = cursor

    # Captions
    for cap in edit_plan.get("captions", []):
        state["captions"].append({
            "id": _new_caption_id(),
            "text": cap.get("text", ""),
            "start": cap.get("start", 0),
            "end": cap.get("end", 0),
            "style": cap.get("style", "bold_white_center"),
        })

    # Zoom moments → effects transitions
    for zm in edit_plan.get("zoom_moments", []):
        state["effects"]["transitions"].append({
            "type": "zoom",
            "timestamp": zm.get("timestamp", 0),
            "scale": zm.get("scale", 1.3),
            "duration": zm.get("duration", 0.5),
        })

    # Music
    music_vibe = edit_plan.get("music_vibe", "")
    if music_vibe and music_vibe.lower() not in ("no music", "no_music", ""):
        state["audio_tracks"].append({
            "id": _new_track_id(),
            "type": "music",
            "source_url": "",
            "start": 0,
            "duration": cursor,
            "volume": 0.25,
            "name": music_vibe,
        })

    # Meme sounds
    for ms in edit_plan.get("meme_sounds", []):
        state["audio_tracks"].append({
            "id": _new_track_id(),
            "type": "sound_effect",
            "source_url": "",
            "start": ms.get("timestamp", 0),
            "duration": 1.5,
            "volume": 0.8,
            "name": ms.get("sound", ""),
        })

    # Color grade
    color_grade = edit_plan.get("color_grade", "none")
    if color_grade and color_grade != "none":
        state["effects"]["color_grade"] = color_grade

    save_edit_state(state)
    logger.info(f"Edit plan → state for job {job_id}: {len(state['timeline'])} segments, {len(state['captions'])} captions")
    return state
