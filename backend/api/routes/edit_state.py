"""
Edit State Route — CapCut-level Manual Editor.

PATCH  /edit-state/{job_id}          — Apply batch edit operations
GET    /edit-state/{job_id}          — Fetch current edit state
POST   /edit-state/{job_id}/render   — Trigger re-render of dirty segments
POST   /edit-state/{job_id}/prompt   — Natural language edit (Cursor-style)

New CapCut-level endpoints:
POST   /edit-state/{job_id}/transitions       — Add/update/remove transitions
GET    /edit-state/{job_id}/transitions       — List all transitions
POST   /edit-state/{job_id}/text-overlays     — Add text overlay
PATCH  /edit-state/{job_id}/text-overlays/{id} — Update text overlay
DELETE /edit-state/{job_id}/text-overlays/{id} — Delete text overlay
GET    /edit-state/{job_id}/text-overlays     — List text overlays

POST   /edit-state/{job_id}/overlays          — Add image/sticker/gif overlay
PATCH  /edit-state/{job_id}/overlays/{id}     — Update overlay
DELETE /edit-state/{job_id}/overlays/{id}     — Delete overlay
GET    /edit-state/{job_id}/overlays          — List overlays

POST   /edit-state/{job_id}/keyframes         — Add keyframe
DELETE /edit-state/{job_id}/keyframes/{id}    — Delete keyframe
GET    /edit-state/{job_id}/keyframes         — List keyframes

POST   /edit-state/{job_id}/audio             — Add audio track
PATCH  /edit-state/{job_id}/audio/{id}        — Update audio track
DELETE /edit-state/{job_id}/audio/{id}        — Delete audio track
POST   /edit-state/{job_id}/audio/detach      — Detach audio from clip

POST   /edit-state/{job_id}/effects           — Add effect (blur/shake/glow/etc)
DELETE /edit-state/{job_id}/effects/{id}      — Remove effect
PATCH  /edit-state/{job_id}/effects/color     — Set color grading

PATCH  /edit-state/{job_id}/aspect-ratio      — Set aspect ratio
GET    /edit-state/{job_id}/aspect-ratio      — Get aspect ratio

POST   /edit-state/{job_id}/playback/seek     — Set playhead
POST   /edit-state/{job_id}/playback/step     — Step forward/backward
POST   /edit-state/{job_id}/playback/speed    — Set playback speed
GET    /edit-state/{job_id}/playback          — Get playback state
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal, Union
from uuid import uuid4

from core.database import get_supabase
from core.security import get_current_user
from services.edit_state import (
    create_edit_state, get_edit_state, save_edit_state,
    action_trim, action_split, action_delete, action_move, action_move_clip,
    action_replace_asset, action_update_caption, action_audio_edit,
    action_duplicate, action_speed_change, action_reverse,
    action_freeze_frame, action_crop, action_rotate, action_opacity,
    get_dirty_ranges, clear_dirty, mark_all_dirty,
    push_undo, undo, redo, get_undo_stack_size, get_redo_stack_size,
    save_version, restore_version, get_version_history,
)
from services.partial_render import render_edit_state
from services.prompt_editor import process_prompt
from services.diff_engine import compute_edit_diff, format_diff_for_display, get_diff_stats
from services.preview_render import render_preview, cleanup_preview
from services.metrics import track_preview_time, track_prompt_iteration
from models.schemas import EditState

router = APIRouter(prefix="/edit-state", tags=["edit-state"])


# ── Manual Edit Actions ─────────────────────────────────────────────────────────

class TrimAction(BaseModel):
    action: Literal["trim"]
    clip_id: str
    start: float
    end: float


class SplitAction(BaseModel):
    action: Literal["split"]
    clip_id: str
    at: float


class DeleteAction(BaseModel):
    action: Literal["delete"]
    clip_id: str


class MoveAction(BaseModel):
    action: Literal["move"]
    clip_id: str
    new_position: int


class MoveClipAction(BaseModel):
    action: Literal["move_clip"]
    clip_id: str
    new_start: float


class ReplaceAssetAction(BaseModel):
    action: Literal["replace_asset"]
    clip_id: str
    source_url: str


class UpdateCaptionAction(BaseModel):
    action: Literal["update_caption"]
    caption_id: str
    text: Optional[str] = None
    style: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None


class AudioEditAction(BaseModel):
    action: Literal["audio_edit"]
    track_id: str
    volume: Optional[float] = None
    source_url: Optional[str] = None
    start: Optional[float] = None


class DuplicateAction(BaseModel):
    action: Literal["duplicate"]
    clip_id: str
    count: int = 1


class SpeedChangeAction(BaseModel):
    action: Literal["speed_change"]
    clip_id: str
    speed: float


class ReverseAction(BaseModel):
    action: Literal["reverse"]
    clip_id: str


class FreezeFrameAction(BaseModel):
    action: Literal["freeze_frame"]
    clip_id: str
    at: float
    duration: float = 2.0


class CropAction(BaseModel):
    action: Literal["crop"]
    clip_id: str
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0


class RotateAction(BaseModel):
    action: Literal["rotate"]
    clip_id: str
    degrees: float


class OpacityAction(BaseModel):
    action: Literal["opacity"]
    clip_id: str
    opacity: float


class AddTransitionAction(BaseModel):
    action: Literal["add_transition"]
    clip_a_id: str
    clip_b_id: str
    transition_type: str = "fade"
    duration: float = 0.5


class RemoveTransitionAction(BaseModel):
    action: Literal["remove_transition"]
    clip_a_id: str
    clip_b_id: str


class SaveVersionAction(BaseModel):
    action: Literal["save_version"]
    label: Optional[str] = None


class RestoreVersionAction(BaseModel):
    action: Literal["restore_version"]
    version_index: int


class SetModeAction(BaseModel):
    action: Literal["set_mode"]
    mode: str = "reels"


class AddBlurAction(BaseModel):
    action: Literal["add_blur"]
    blur_type: str = "gaussian"
    intensity: float = 5.0
    start: float = 0.0
    end: float = 0.0


class AddShakeAction(BaseModel):
    action: Literal["add_shake"]
    intensity: float = 5.0
    frequency: float = 10.0
    start: float = 0.0
    end: float = 0.0


class AddGlowAction(BaseModel):
    action: Literal["add_glow"]
    intensity: float = 0.5
    radius: float = 10.0
    start: float = 0.0
    end: float = 0.0


class AddVignetteAction(BaseModel):
    action: Literal["add_vignette"]
    intensity: float = 0.5
    start: float = 0.0
    end: float = 0.0


class ChangeColorGradeAction(BaseModel):
    action: Literal["change_color_grade"]
    grade: str = "none"
    brightness: Optional[float] = None
    contrast: Optional[float] = None
    saturation: Optional[float] = None


class AddTextOverlayAction(BaseModel):
    action: Literal["add_text_overlay"]
    text: str = "Text"
    start: float = 0.0
    end: float = 3.0
    x: float = 0.5
    y: float = 0.5
    animation: str = "none"
    layer: int = 0


class UpdateTextOverlayAction(BaseModel):
    action: Literal["update_text_overlay"]
    overlay_id: str
    text: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    style: Optional[str] = None
    animation: Optional[str] = None


class AddMusicAction(BaseModel):
    action: Literal["add_music"]
    vibe: str = "lo-fi"
    volume: float = 0.25


class AudioDetachAction(BaseModel):
    action: Literal["audio_detach"]
    clip_id: str


class AddKeyframeAction(BaseModel):
    action: Literal["add_keyframe"]
    clip_id: str
    property: str = "zoom"
    time: float = 0.0
    value: float = 1.0
    interpolation: str = "ease_in_out"
    easing_power: float = 2.0


class RemoveKeyframeAction(BaseModel):
    action: Literal["remove_keyframe"]
    keyframe_id: str


class RemoveEffectAction(BaseModel):
    action: Literal["remove_effect"]
    effect_id: str


class SetAspectRatioAction(BaseModel):
    action: Literal["set_aspect_ratio"]
    ratio: str = "9:16"
    auto_reframe: bool = False


class BatchEditRequest(BaseModel):
    actions: List[
        Union[
            TrimAction, SplitAction, DeleteAction, MoveAction, MoveClipAction,
            ReplaceAssetAction, UpdateCaptionAction, AudioEditAction,
            DuplicateAction, SpeedChangeAction, ReverseAction,
            FreezeFrameAction, CropAction, RotateAction, OpacityAction,
            AddTransitionAction, RemoveTransitionAction,
            SaveVersionAction, RestoreVersionAction,
            SetModeAction, AddBlurAction, AddShakeAction, AddGlowAction,
            AddVignetteAction, ChangeColorGradeAction, AddTextOverlayAction,
            UpdateTextOverlayAction,
            AddMusicAction, AudioDetachAction, AddKeyframeAction,
            RemoveKeyframeAction, RemoveEffectAction, SetAspectRatioAction,
        ]
    ]


class EditStateResponse(BaseModel):
    state: Dict[str, Any]
    dirty_ranges: List[Dict[str, float]]


class CreateEditStateRequest(BaseModel):
    video_id: str
    mode: str = "reels"


class CreateEditStateResponse(BaseModel):
    job_id: str
    state: Dict[str, Any]
    dirty_ranges: List[Dict[str, float]]


class RenderResponse(BaseModel):
    job_id: str
    output_url: str
    message: str


# ── POST: Create new edit state ────────────────────────────────────────────────

@router.post("", response_model=CreateEditStateResponse)
async def create_state(
    request: CreateEditStateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new edit state for a video."""
    job_id = str(uuid4())
    state = create_edit_state(job_id, current_user["id"], request.video_id, request.mode)
    return CreateEditStateResponse(
        job_id=job_id,
        state=state,
        dirty_ranges=get_dirty_ranges(state),
    )


# ── GET: Fetch edit state ──────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=EditStateResponse)
async def get_state(job_id: str, current_user: dict = Depends(get_current_user)):
    """Fetch the current edit state for a job."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")
    return EditStateResponse(
        state=state,
        dirty_ranges=get_dirty_ranges(state),
    )


# ── PATCH: Apply edit operations ──────────────────────────────────────────────

@router.patch("/{job_id}", response_model=EditStateResponse)
async def patch_edit_state(
    job_id: str,
    request: BatchEditRequest,
    current_user: dict = Depends(get_current_user),
):
    """Apply one or more edit operations to the timeline."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    applied = []
    for action_data in request.actions:
        action = action_data.action
        try:
            if action == "trim":
                action_trim(state, action_data.clip_id, action_data.start, action_data.end)
                applied.append(f"trim:{action_data.clip_id}")

            elif action == "split":
                action_split(state, action_data.clip_id, action_data.at)
                applied.append(f"split:{action_data.clip_id}@{action_data.at}")

            elif action == "delete":
                action_delete(state, action_data.clip_id)
                applied.append(f"delete:{action_data.clip_id}")

            elif action == "move":
                action_move(state, action_data.clip_id, action_data.new_position)
                applied.append(f"move:{action_data.clip_id}→{action_data.new_position}")

            elif action == "move_clip":
                action_move_clip(state, action_data.clip_id, action_data.new_start)
                applied.append(f"move_clip:{action_data.clip_id}→{action_data.new_start}s")

            elif action == "replace_asset":
                action_replace_asset(state, action_data.clip_id, action_data.source_url)
                applied.append(f"replace:{action_data.clip_id}")

            elif action == "update_caption":
                action_update_caption(
                    state, action_data.caption_id,
                    text=action_data.text,
                    style=action_data.style,
                    start=action_data.start,
                    end=action_data.end,
                )
                applied.append(f"caption:{action_data.caption_id}")

            elif action == "audio_edit":
                action_audio_edit(
                    state, action_data.track_id,
                    volume=action_data.volume,
                    source_url=action_data.source_url,
                    start=action_data.start,
                )
                applied.append(f"audio:{action_data.track_id}")

            elif action == "duplicate":
                action_duplicate(state, action_data.clip_id, action_data.count)
                applied.append(f"duplicate:{action_data.clip_id}×{action_data.count}")

            elif action == "speed_change":
                action_speed_change(state, action_data.clip_id, action_data.speed)
                applied.append(f"speed:{action_data.clip_id}→{action_data.speed}x")

            elif action == "reverse":
                action_reverse(state, action_data.clip_id)
                applied.append(f"reverse:{action_data.clip_id}")

            elif action == "freeze_frame":
                action_freeze_frame(state, action_data.clip_id, action_data.at, action_data.duration)
                applied.append(f"freeze:{action_data.clip_id}@{action_data.at}")

            elif action == "crop":
                action_crop(state, action_data.clip_id, action_data.x, action_data.y, action_data.width, action_data.height)
                applied.append(f"crop:{action_data.clip_id}")

            elif action == "rotate":
                action_rotate(state, action_data.clip_id, action_data.degrees)
                applied.append(f"rotate:{action_data.clip_id}→{action_data.degrees}°")

            elif action == "opacity":
                action_opacity(state, action_data.clip_id, action_data.opacity)
                applied.append(f"opacity:{action_data.clip_id}→{action_data.opacity}")

            elif action == "add_transition":
                from services.transitions_engine import add_transition as add_tr
                add_tr(state, action_data.clip_a_id, action_data.clip_b_id, action_data.transition_type, action_data.duration)
                applied.append(f"add_transition:{action_data.clip_a_id}↔{action_data.clip_b_id}")

            elif action == "remove_transition":
                from services.transitions_engine import remove_transition as rm_tr
                rm_tr(state, action_data.clip_a_id, action_data.clip_b_id)
                applied.append(f"remove_transition:{action_data.clip_a_id}↔{action_data.clip_b_id}")

            elif action == "save_version":
                state = save_version(state, action_data.label)
                applied.append(f"save_version")

            elif action == "restore_version":
                state = restore_version(state, action_data.version_index)
                applied.append(f"restore_version:v{action_data.version_index}")

            elif action == "set_mode":
                state["mode"] = getattr(action_data, "mode", "reels")
                applied.append(f"mode:{state['mode']}")

            elif action == "add_blur":
                from services.effects_engine import add_blur_effect
                state = add_blur_effect(state, getattr(action_data, "blur_type", "gaussian"), getattr(action_data, "intensity", 5), getattr(action_data, "start", 0), getattr(action_data, "end", 0))
                applied.append("add_blur")

            elif action == "add_shake":
                from services.effects_engine import add_shake_effect
                state = add_shake_effect(state, getattr(action_data, "intensity", 5), getattr(action_data, "frequency", 10), getattr(action_data, "start", 0), getattr(action_data, "end", 0))
                applied.append("add_shake")

            elif action == "add_glow":
                from services.effects_engine import add_glow_effect
                state = add_glow_effect(state, getattr(action_data, "intensity", 0.5), getattr(action_data, "radius", 10), getattr(action_data, "start", 0), getattr(action_data, "end", 0))
                applied.append("add_glow")

            elif action == "add_vignette":
                from services.effects_engine import add_vignette
                state = add_vignette(state, getattr(action_data, "intensity", 0.5), getattr(action_data, "start", 0), getattr(action_data, "end", 0))
                applied.append("add_vignette")

            elif action == "change_color_grade":
                from services.effects_engine import set_color_grading
                state = set_color_grading(state, getattr(action_data, "grade", "none"), brightness=getattr(action_data, "brightness", None), contrast=getattr(action_data, "contrast", None), saturation=getattr(action_data, "saturation", None))
                applied.append(f"color_grade:{getattr(action_data, 'grade', 'none')}")

            elif action == "add_text_overlay":
                from services.text_overlay_engine import add_text_overlay
                state = add_text_overlay(state, getattr(action_data, "text", "Text"), getattr(action_data, "start", 0), getattr(action_data, "end", 3), x=getattr(action_data, "x", 0.5), y=getattr(action_data, "y", 0.5), animation=getattr(action_data, "animation", "none"), layer=getattr(action_data, "layer", 0))
                applied.append("add_text_overlay")

            elif action == "update_text_overlay":
                from services.text_overlay_engine import update_text_overlay
                state = update_text_overlay(
                    state, getattr(action_data, "overlay_id", ""),
                    text=getattr(action_data, "text", None),
                    start=getattr(action_data, "start", None),
                    end=getattr(action_data, "end", None),
                    x=getattr(action_data, "x", None),
                    y=getattr(action_data, "y", None),
                    style=getattr(action_data, "style", None),
                    animation=getattr(action_data, "animation", None),
                )
                applied.append("update_text_overlay")

            elif action == "add_music":
                from services.audio_engine import add_audio_track
                vibe = getattr(action_data, "vibe", "lo-fi")
                vol = getattr(action_data, "volume", 0.25)
                state = add_audio_track(state, f"generated:{vibe}", "music", start=0, duration=0, volume=vol, name=f"AI {vibe.title()} Music", loop=True)
                applied.append(f"add_music:{vibe}")

            elif action == "audio_detach":
                from services.audio_engine import detach_audio
                state = detach_audio(state, getattr(action_data, "clip_id", ""))
                applied.append(f"audio_detach:{getattr(action_data, 'clip_id', '')}")

            elif action == "add_keyframe":
                from services.keyframe_engine import add_keyframe
                state = add_keyframe(state, getattr(action_data, "clip_id", ""), getattr(action_data, "property", "zoom"), getattr(action_data, "time", 0), getattr(action_data, "value", 1.0), interpolation=getattr(action_data, "interpolation", "ease_in_out"), easing_power=getattr(action_data, "easing_power", 2.0))
                applied.append(f"add_keyframe:{getattr(action_data, 'property', '')}")

            elif action == "remove_keyframe":
                from services.keyframe_engine import remove_keyframe
                state = remove_keyframe(state, getattr(action_data, "keyframe_id", ""))
                applied.append(f"remove_keyframe:{getattr(action_data, 'keyframe_id', '')}")

            elif action == "remove_effect":
                from services.effects_engine import remove_effect
                state = remove_effect(state, getattr(action_data, "effect_id", ""))
                applied.append(f"remove_effect:{getattr(action_data, 'effect_id', '')}")

            elif action == "set_aspect_ratio":
                from services.aspect_ratio_engine import set_aspect_ratio
                state = set_aspect_ratio(state, getattr(action_data, "ratio", "9:16"), getattr(action_data, "auto_reframe", False))
                applied.append(f"aspect_ratio:{getattr(action_data, 'ratio', '9:16')}")

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Action '{action}' failed: {str(e)}")

    save_edit_state(state)

    return EditStateResponse(
        state=state,
        dirty_ranges=get_dirty_ranges(state),
    )


# ── POST: Trigger render ──────────────────────────────────────────────────────

@router.post("/{job_id}/render", response_model=RenderResponse)
async def render_dirty(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-render only the dirty segments of the edit state and stitch with cached ones."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    dirty = get_dirty_ranges(state)
    if not dirty:
        return RenderResponse(
            job_id=job_id,
            output_url="",
            message="No dirty segments to render. Everything is up to date.",
        )

    try:
        supabase = get_supabase()
        job = supabase.table("edit_jobs").select("video_id").eq("id", job_id).single().execute()
        if not job.data:
            raise HTTPException(status_code=404, detail="Job not found")

        video = supabase.table("videos").select("cloudinary_url").eq("id", job.data["video_id"]).single().execute()
        if not video.data or not video.data.get("cloudinary_url"):
            raise HTTPException(status_code=400, detail="Video source not found")

        output_url = await render_edit_state(
            job_id=job_id,
            user_id=current_user["id"],
            video_url=video.data["cloudinary_url"],
        )

        return RenderResponse(
            job_id=job_id,
            output_url=output_url,
            message=f"Re-rendered {len(dirty)} dirty range(s). Total duration: {state['metadata']['total_duration']:.1f}s",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render failed: {str(e)[:200]}")


# ── POST: Prompt-based editing ────────────────────────────────────────────────

class PromptEditRequest(BaseModel):
    prompt: str
    attachments: Optional[List[Dict[str, Any]]] = None


class PromptEditResponse(BaseModel):
    job_id: str
    applied_patches: List[Dict[str, Any]]
    message: str
    needs_render: bool = True


@router.post("/{job_id}/prompt", response_model=PromptEditResponse)
async def prompt_edit(
    job_id: str,
    request: PromptEditRequest,
    current_user: dict = Depends(get_current_user),
):
    """Natural language editing — uses GPT-4o to process edit commands."""
    import time as _time
    start = _time.time()

    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    old_state_snapshot = {k: v for k, v in state.items() if k not in ("undo_stack", "redo_stack", "version_history")}

    # Fetch video analysis if available
    video_analysis = None
    try:
        from services.video_understanding_ai import analyze_video
        supabase = get_supabase()
        video_id = state.get("video_id", "")
        if video_id:
            video_data = supabase.table("video_analysis").select("analysis").eq("video_id", video_id).single().execute()
            if video_data.data:
                video_analysis = video_data.data["analysis"]
    except Exception:
        pass

    result = await process_prompt(job_id, current_user["id"], request.prompt, video_analysis=video_analysis, attachments=request.attachments)

    new_state = get_edit_state(job_id, current_user["id"])
    diff = compute_edit_diff(old_state_snapshot, new_state) if new_state else {}

    elapsed = _time.time() - start
    await track_prompt_iteration(
        project_id=job_id,
        user_id=current_user["id"],
        iteration_number=new_state.get("version", 1),
        prompt_text=request.prompt,
        time_seconds=elapsed,
    )

    return PromptEditResponse(
        job_id=job_id,
        applied_patches=result["applied_patches"],
        message=result["message"],
        needs_render=result.get("needs_render", True),
    )


# ── POST/GET: Undo/Redo ──────────────────────────────────────────────────────

class UndoRedoResponse(BaseModel):
    state: Dict[str, Any]
    undo_remaining: int
    redo_remaining: int
    message: str


@router.post("/{job_id}/undo", response_model=UndoRedoResponse)
async def undo_edit(job_id: str, current_user: dict = Depends(get_current_user)):
    """Undo the last edit operation."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    state = undo(state)
    save_edit_state(state)

    return UndoRedoResponse(
        state=state,
        undo_remaining=get_undo_stack_size(state),
        redo_remaining=get_redo_stack_size(state),
        message="Undo successful",
    )


@router.post("/{job_id}/redo", response_model=UndoRedoResponse)
async def redo_edit(job_id: str, current_user: dict = Depends(get_current_user)):
    """Redo the last undone edit operation."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    state = redo(state)
    save_edit_state(state)

    return UndoRedoResponse(
        state=state,
        undo_remaining=get_undo_stack_size(state),
        redo_remaining=get_redo_stack_size(state),
        message="Redo successful",
    )


class UndoRedoInfo(BaseModel):
    undo_count: int
    redo_count: int


@router.get("/{job_id}/undo-info", response_model=UndoRedoInfo)
async def get_undo_info(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get undo/redo stack sizes."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")
    return UndoRedoInfo(
        undo_count=get_undo_stack_size(state),
        redo_count=get_redo_stack_size(state),
    )


# ── POST/GET: Version History ─────────────────────────────────────────────────

class SaveVersionRequest(BaseModel):
    label: Optional[str] = None


class VersionHistoryResponse(BaseModel):
    versions: List[Dict[str, Any]]
    current_version: int


@router.post("/{job_id}/versions", response_model=VersionHistoryResponse)
async def save_version_snapshot(
    job_id: str,
    request: SaveVersionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Save current state as a named version."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    state = save_version(state, label=request.label)
    save_edit_state(state)

    return VersionHistoryResponse(
        versions=get_version_history(state),
        current_version=state.get("version", 1),
    )


@router.get("/{job_id}/versions", response_model=VersionHistoryResponse)
async def list_versions(job_id: str, current_user: dict = Depends(get_current_user)):
    """List all saved versions."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")
    return VersionHistoryResponse(
        versions=get_version_history(state),
        current_version=state.get("version", 1),
    )


@router.post("/{job_id}/versions/{version_index}/restore", response_model=EditStateResponse)
async def restore_version_snapshot(
    job_id: str,
    version_index: int,
    current_user: dict = Depends(get_current_user),
):
    """Restore state from a specific version."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    state = restore_version(state, version_index)
    save_edit_state(state)

    return EditStateResponse(
        state=state,
        dirty_ranges=get_dirty_ranges(state),
    )


# ── POST: Render preview ──────────────────────────────────────────────────────

class PreviewResponse(BaseModel):
    preview_path: str
    duration_seconds: float
    message: str


@router.post("/{job_id}/preview-render", response_model=PreviewResponse)
async def render_preview_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Render a 480p ultrafast preview for instant feedback."""
    import time as _time
    start = _time.time()

    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    supabase = get_supabase()
    job = supabase.table("edit_jobs").select("video_id").eq("id", job_id).single().execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")

    video = supabase.table("videos").select("cloudinary_url").eq("id", job.data["video_id"]).single().execute()
    if not video.data or not video.data.get("cloudinary_url"):
        raise HTTPException(status_code=400, detail="Video source not found")

    try:
        from services.preview_render import render_preview as _render_preview
        result = await _render_preview(state, video.data["cloudinary_url"])

        elapsed = _time.time() - start
        await track_preview_time(job_id, elapsed)

        return PreviewResponse(
            preview_path=result.get("preview_path", ""),
            duration_seconds=round(elapsed, 2),
            message=f"Preview rendered in {elapsed:.1f}s ({result.get('resolution', '480p')})",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview render failed: {str(e)[:200]}")


# ── GET: Edit diff ────────────────────────────────────────────────────────────

class EditDiffResponse(BaseModel):
    changes: List[Dict[str, Any]]
    summary: str
    total_changes: int
    old_segment_count: int
    new_segment_count: int
    stats: Dict[str, Any]


@router.get("/{job_id}/diff", response_model=EditDiffResponse)
async def get_edit_diff(
    job_id: str,
    before_version: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get the diff between the current state and a previous version."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    history = state.get("version_history", [])

    if before_version is not None and 0 <= before_version < len(history):
        old_state = history[before_version]
    elif history:
        old_state = history[-1]
    else:
        return EditDiffResponse(
            changes=[], summary="No previous version to compare against.",
            total_changes=0, old_segment_count=0, new_segment_count=0, stats={},
        )

    diff = compute_edit_diff(old_state, state)

    return EditDiffResponse(
        changes=diff["changes"], summary=diff["summary"],
        total_changes=diff["total_changes"],
        old_segment_count=diff["old_segment_count"],
        new_segment_count=diff["new_segment_count"],
        stats=get_diff_stats(diff),
    )


# ── GET: Preview URL ──────────────────────────────────────────────────────────

@router.get("/{job_id}/preview")
async def get_preview(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get the latest rendered output URL for a job."""
    supabase = get_supabase()
    output = (
        supabase.table("output_videos")
        .select("*")
        .eq("job_id", job_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not output.data:
        raise HTTPException(status_code=404, detail="No output video found")
    return {
        "job_id": job_id,
        "output_url": output.data[0]["cloudinary_url"],
        "version_type": output.data[0]["version_type"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NEW CAPCUT-LEVEL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


# ── Transitions ────────────────────────────────────────────────────────────────

class TransitionRequest(BaseModel):
    clip_a_id: str
    clip_b_id: str
    transition_type: str = "fade"
    duration: float = 0.5


class TransitionUpdateRequest(BaseModel):
    transition_id: str
    transition_type: Optional[str] = None
    duration: Optional[float] = None


@router.post("/{job_id}/transitions")
async def add_transition_endpoint(
    job_id: str,
    request: TransitionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a transition between two clips."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    try:
        from services.transitions_engine import add_transition
        state = add_transition(
            state, request.clip_a_id, request.clip_b_id,
            request.transition_type, request.duration,
        )
        save_edit_state(state)
        return {"state": state, "dirty_ranges": get_dirty_ranges(state)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{job_id}/transitions")
async def update_transition_endpoint(
    job_id: str,
    request: TransitionUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing transition."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.transitions_engine import update_transition
    state = update_transition(state, request.transition_id, request.transition_type, request.duration)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.delete("/{job_id}/transitions/{clip_a_id}/{clip_b_id}")
async def remove_transition_endpoint(
    job_id: str,
    clip_a_id: str,
    clip_b_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a transition between two clips."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.transitions_engine import remove_transition
    state = remove_transition(state, clip_a_id, clip_b_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.get("/{job_id}/transitions")
async def list_transitions(job_id: str, current_user: dict = Depends(get_current_user)):
    """List all transitions."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.transitions_engine import get_transitions
    return {"transitions": get_transitions(state)}


# ── Text Overlays ──────────────────────────────────────────────────────────────

class TextOverlayRequest(BaseModel):
    text: str
    start: float
    end: float
    x: float = 0.5
    y: float = 0.5
    style: Optional[Dict[str, Any]] = None
    animation: str = "none"
    animation_duration: float = 0.3
    layer: int = 0


class TextOverlayUpdateRequest(BaseModel):
    text: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    style: Optional[Dict[str, Any]] = None
    animation: Optional[str] = None
    animation_duration: Optional[float] = None
    layer: Optional[int] = None


@router.post("/{job_id}/text-overlays")
async def add_text_overlay_endpoint(
    job_id: str,
    request: TextOverlayRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a text overlay with styling and animation."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.text_overlay_engine import add_text_overlay
    state = add_text_overlay(
        state, request.text, request.start, request.end,
        x=request.x, y=request.y, style=request.style,
        animation=request.animation, animation_duration=request.animation_duration,
        layer=request.layer,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.patch("/{job_id}/text-overlays/{overlay_id}")
async def update_text_overlay_endpoint(
    job_id: str,
    overlay_id: str,
    request: TextOverlayUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a text overlay."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.text_overlay_engine import update_text_overlay
    state = update_text_overlay(
        state, overlay_id,
        text=request.text, start=request.start, end=request.end,
        x=request.x, y=request.y, style=request.style,
        animation=request.animation, animation_duration=request.animation_duration,
        layer=request.layer,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.delete("/{job_id}/text-overlays/{overlay_id}")
async def delete_text_overlay_endpoint(
    job_id: str,
    overlay_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a text overlay."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.text_overlay_engine import delete_text_overlay
    state = delete_text_overlay(state, overlay_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.get("/{job_id}/text-overlays")
async def list_text_overlays(job_id: str, current_user: dict = Depends(get_current_user)):
    """List all text overlays."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.text_overlay_engine import get_text_overlays
    return {"text_overlays": get_text_overlays(state)}


# ── Image/Sticker/GIF Overlays ────────────────────────────────────────────────

class OverlayRequest(BaseModel):
    overlay_type: Literal["image", "sticker", "gif"]
    source_url: str
    start: float
    end: float
    x: float = 0.5
    y: float = 0.5
    scale: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    animation: str = "none"
    animation_duration: float = 0.3
    layer: int = 0
    name: str = ""
    width: Optional[int] = None
    height: Optional[int] = None


class OverlayUpdateRequest(BaseModel):
    source_url: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    scale: Optional[float] = None
    rotation: Optional[float] = None
    opacity: Optional[float] = None
    animation: Optional[str] = None
    animation_duration: Optional[float] = None
    layer: Optional[int] = None


@router.post("/{job_id}/overlays")
async def add_overlay_endpoint(
    job_id: str,
    request: OverlayRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add an image/sticker/gif overlay."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.overlay_engine import add_overlay
    state = add_overlay(
        state, request.overlay_type, request.source_url,
        request.start, request.end,
        x=request.x, y=request.y, scale=request.scale,
        rotation=request.rotation, opacity=request.opacity,
        animation=request.animation, animation_duration=request.animation_duration,
        layer=request.layer, name=request.name,
        width=request.width, height=request.height,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.patch("/{job_id}/overlays/{overlay_id}")
async def update_overlay_endpoint(
    job_id: str,
    overlay_id: str,
    request: OverlayUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update an overlay."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.overlay_engine import update_overlay
    state = update_overlay(
        state, overlay_id,
        source_url=request.source_url, start=request.start, end=request.end,
        x=request.x, y=request.y, scale=request.scale,
        rotation=request.rotation, opacity=request.opacity,
        animation=request.animation, animation_duration=request.animation_duration,
        layer=request.layer,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.delete("/{job_id}/overlays/{overlay_id}")
async def delete_overlay_endpoint(
    job_id: str,
    overlay_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an overlay."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.overlay_engine import delete_overlay
    state = delete_overlay(state, overlay_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.get("/{job_id}/overlays")
async def list_overlays(job_id: str, current_user: dict = Depends(get_current_user)):
    """List all overlays."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.overlay_engine import get_overlays
    return {"overlays": get_overlays(state)}


# ── Keyframes ──────────────────────────────────────────────────────────────────

class KeyframeRequest(BaseModel):
    clip_id: str
    property: str
    time: float
    value: float
    interpolation: str = "ease_in_out"
    easing_power: float = 2.0


class KeyframeUpdateRequest(BaseModel):
    time: Optional[float] = None
    value: Optional[float] = None
    interpolation: Optional[str] = None
    easing_power: Optional[float] = None


class BatchKeyframeRequest(BaseModel):
    clip_id: str
    property: str
    values: List[Dict[str, float]]


@router.post("/{job_id}/keyframes")
async def add_keyframe_endpoint(
    job_id: str,
    request: KeyframeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a keyframe to animate a property over time."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.keyframe_engine import add_keyframe
    try:
        state = add_keyframe(
            state, request.clip_id, request.property,
            request.time, request.value,
            interpolation=request.interpolation,
            easing_power=request.easing_power,
        )
        save_edit_state(state)
        return {"state": state, "dirty_ranges": get_dirty_ranges(state)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/keyframes/batch")
async def batch_add_keyframes_endpoint(
    job_id: str,
    request: BatchKeyframeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add multiple keyframes at once."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.keyframe_engine import batch_add_keyframes
    state = batch_add_keyframes(state, request.clip_id, request.property, request.values)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.patch("/{job_id}/keyframes/{keyframe_id}")
async def update_keyframe_endpoint(
    job_id: str,
    keyframe_id: str,
    request: KeyframeUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a keyframe."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.keyframe_engine import update_keyframe
    state = update_keyframe(
        state, keyframe_id,
        time=request.time, value=request.value,
        interpolation=request.interpolation,
        easing_power=request.easing_power,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.delete("/{job_id}/keyframes/{keyframe_id}")
async def delete_keyframe_endpoint(
    job_id: str,
    keyframe_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a keyframe."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.keyframe_engine import remove_keyframe
    state = remove_keyframe(state, keyframe_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.get("/{job_id}/keyframes")
async def list_keyframes(
    job_id: str,
    clip_id: Optional[str] = None,
    property: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List keyframes, optionally filtered by clip_id and/or property."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.keyframe_engine import get_keyframes_for_clip, get_keyframes_for_property
    if clip_id:
        return {"keyframes": get_keyframes_for_clip(state, clip_id, property)}
    elif property:
        return {"keyframes": get_keyframes_for_property(state, property)}
    return {"keyframes": state.get("keyframes", [])}


# ── Audio Tracks ───────────────────────────────────────────────────────────────

class AddAudioTrackRequest(BaseModel):
    source_url: str
    track_type: str = "music"
    start: float = 0.0
    duration: float = 0.0
    volume: float = 0.25
    name: str = ""
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = False
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None


class UpdateAudioTrackRequest(BaseModel):
    volume: Optional[float] = None
    source_url: Optional[str] = None
    start: Optional[float] = None
    fade_in: Optional[float] = None
    fade_out: Optional[float] = None
    loop: Optional[bool] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    name: Optional[str] = None


class DetachAudioRequest(BaseModel):
    clip_id: str


class AudioDuckingRequest(BaseModel):
    music_track_id: str
    voice_track_ids: List[str]
    duck_volume: float = 0.1
    attack: float = 0.3
    release: float = 0.5


@router.post("/{job_id}/audio")
async def add_audio_track_endpoint(
    job_id: str,
    request: AddAudioTrackRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add an audio track (music, SFX, voiceover, etc)."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.audio_engine import add_audio_track
    state = add_audio_track(
        state, request.source_url, request.track_type,
        start=request.start, duration=request.duration,
        volume=request.volume, name=request.name,
        fade_in=request.fade_in, fade_out=request.fade_out,
        loop=request.loop, trim_start=request.trim_start,
        trim_end=request.trim_end,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.patch("/{job_id}/audio/{track_id}")
async def update_audio_track_endpoint(
    job_id: str,
    track_id: str,
    request: UpdateAudioTrackRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update an audio track."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.audio_engine import update_audio_track
    state = update_audio_track(
        state, track_id,
        volume=request.volume, source_url=request.source_url,
        start=request.start, fade_in=request.fade_in,
        fade_out=request.fade_out, loop=request.loop,
        trim_start=request.trim_start, trim_end=request.trim_end,
        name=request.name,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.delete("/{job_id}/audio/{track_id}")
async def delete_audio_track_endpoint(
    job_id: str,
    track_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an audio track."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.audio_engine import delete_audio_track
    state = delete_audio_track(state, track_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.post("/{job_id}/audio/detach")
async def detach_audio_endpoint(
    job_id: str,
    request: DetachAudioRequest,
    current_user: dict = Depends(get_current_user),
):
    """Detach audio from a video clip into a separate track."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.audio_engine import detach_audio
    state = detach_audio(state, request.clip_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.post("/{job_id}/audio/ducking")
async def set_audio_ducking_endpoint(
    job_id: str,
    request: AudioDuckingRequest,
    current_user: dict = Depends(get_current_user),
):
    """Configure audio ducking (lower music when voice speaks)."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.audio_engine import set_audio_ducking
    state = set_audio_ducking(
        state, request.music_track_id, request.voice_track_ids,
        duck_volume=request.duck_volume, attack=request.attack,
        release=request.release,
    )
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.get("/{job_id}/audio")
async def list_audio_tracks(job_id: str, current_user: dict = Depends(get_current_user)):
    """List all audio tracks."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.audio_engine import get_audio_tracks
    return {"audio_tracks": get_audio_tracks(state)}


# ── Effects ────────────────────────────────────────────────────────────────────

class BlurEffectRequest(BaseModel):
    blur_type: str = "gaussian"
    intensity: float = 5.0
    start: float = 0.0
    end: float = 0.0


class ShakeEffectRequest(BaseModel):
    intensity: float = 5.0
    frequency: float = 10.0
    start: float = 0.0
    end: float = 0.0


class GlowEffectRequest(BaseModel):
    intensity: float = 0.5
    radius: float = 10.0
    start: float = 0.0
    end: float = 0.0


class VignetteRequest(BaseModel):
    intensity: float = 0.5
    start: float = 0.0
    end: float = 0.0


class ColorGradeRequest(BaseModel):
    grade: str = "none"
    brightness: Optional[float] = None
    contrast: Optional[float] = None
    saturation: Optional[float] = None
    hue: Optional[float] = None
    temperature: Optional[float] = None
    start: Optional[float] = None
    end: Optional[float] = None


@router.post("/{job_id}/effects/blur")
async def add_blur_effect_endpoint(
    job_id: str,
    request: BlurEffectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a blur effect."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import add_blur_effect
    state = add_blur_effect(state, request.blur_type, request.intensity, request.start, request.end)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.post("/{job_id}/effects/shake")
async def add_shake_effect_endpoint(
    job_id: str,
    request: ShakeEffectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a camera shake effect."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import add_shake_effect
    state = add_shake_effect(state, request.intensity, request.frequency, request.start, request.end)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.post("/{job_id}/effects/glow")
async def add_glow_effect_endpoint(
    job_id: str,
    request: GlowEffectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a glow/bloom effect."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import add_glow_effect
    state = add_glow_effect(state, request.intensity, request.radius, request.start, request.end)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.post("/{job_id}/effects/vignette")
async def add_vignette_endpoint(
    job_id: str,
    request: VignetteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a vignette effect."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import add_vignette
    state = add_vignette(state, request.intensity, request.start, request.end)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.delete("/{job_id}/effects/{effect_id}")
async def remove_effect_endpoint(
    job_id: str,
    effect_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove an effect by ID."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import remove_effect
    state = remove_effect(state, effect_id)
    save_edit_state(state)
    return {"state": state, "dirty_ranges": get_dirty_ranges(state)}


@router.patch("/{job_id}/effects/color")
async def set_color_grading_endpoint(
    job_id: str,
    request: ColorGradeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set color grading on the timeline or a specific range."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import set_color_grading
    try:
        state = set_color_grading(
            state, request.grade,
            brightness=request.brightness, contrast=request.contrast,
            saturation=request.saturation, hue=request.hue,
            temperature=request.temperature,
            start=request.start, end=request.end,
        )
        save_edit_state(state)
        return {"state": state, "dirty_ranges": get_dirty_ranges(state)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/effects")
async def list_effects(job_id: str, current_user: dict = Depends(get_current_user)):
    """List all effects."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.effects_engine import get_all_effects
    return {"effects": get_all_effects(state)}


# ── Aspect Ratio ───────────────────────────────────────────────────────────────

class AspectRatioRequest(BaseModel):
    aspect_ratio: str = "9:16"
    auto_reframe: bool = False
    custom_width: Optional[int] = None
    custom_height: Optional[int] = None


@router.patch("/{job_id}/aspect-ratio")
async def set_aspect_ratio_endpoint(
    job_id: str,
    request: AspectRatioRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set the output aspect ratio."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.aspect_ratio_engine import set_aspect_ratio
    try:
        state = set_aspect_ratio(
            state, request.aspect_ratio, request.auto_reframe,
            custom_width=request.custom_width, custom_height=request.custom_height,
        )
        save_edit_state(state)
        return {"state": state, "dirty_ranges": get_dirty_ranges(state)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/aspect-ratio")
async def get_aspect_ratio_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get current aspect ratio settings."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.aspect_ratio_engine import get_aspect_ratio, get_available_aspect_ratios
    return {
        "current": get_aspect_ratio(state),
        "available": get_available_aspect_ratios(),
    }


# ── Playback ──────────────────────────────────────────────────────────────────

class SeekRequest(BaseModel):
    time: float


class StepRequest(BaseModel):
    frames: int = 1


class PlaybackSpeedRequest(BaseModel):
    speed: float = 1.0


class LoopRequest(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    enabled: Optional[bool] = None


@router.get("/{job_id}/playback")
async def get_playback_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get current playback state."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.playback_engine import get_playback_state
    return {"playback": get_playback_state(state)}


@router.post("/{job_id}/playback/seek")
async def seek_endpoint(
    job_id: str,
    request: SeekRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set the playhead to a specific time."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.playback_engine import set_playhead
    state = set_playhead(state, request.time)
    save_edit_state(state)
    return {"playback": get_playback_state(state)}


@router.post("/{job_id}/playback/step")
async def step_endpoint(
    job_id: str,
    request: StepRequest,
    current_user: dict = Depends(get_current_user),
):
    """Step forward or backward by N frames."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.playback_engine import step_forward, step_backward
    if request.frames >= 0:
        state = step_forward(state, request.frames)
    else:
        state = step_backward(state, abs(request.frames))
    save_edit_state(state)
    return {"playback": get_playback_state(state)}


@router.post("/{job_id}/playback/speed")
async def set_playback_speed_endpoint(
    job_id: str,
    request: PlaybackSpeedRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set playback speed."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.playback_engine import set_playback_speed
    state = set_playback_speed(state, request.speed)
    save_edit_state(state)
    return {"playback": get_playback_state(state)}


@router.post("/{job_id}/playback/loop")
async def set_loop_endpoint(
    job_id: str,
    request: LoopRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set loop region."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.playback_engine import set_loop_region
    state = set_loop_region(state, request.start, request.end, request.enabled)
    save_edit_state(state)
    return {"playback": get_playback_state(state)}


@router.get("/{job_id}/playback/frame")
async def get_frame_info_endpoint(
    job_id: str,
    time: float = 0.0,
    current_user: dict = Depends(get_current_user),
):
    """Get info about what's at a specific time on the timeline."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.playback_engine import get_frame_at_time
    return {"frame": get_frame_at_time(state, time)}


# ═══════════════════════════════════════════════════════════════════════════════
# NEW FEATURES
# ═══════════════════════════════════════════════════════════════════════════════


# ── Export: Full render + download ────────────────────────────────────────────

class ExportResponse(BaseModel):
    job_id: str
    output_url: str
    download_url: str
    message: str


@router.post("/{job_id}/export", response_model=ExportResponse)
async def export_video(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Full render + return download URL for final export."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from core.config import settings as cfg
    DEV_MODE = cfg.dev_mode
    supabase = get_supabase()

    # Get video source URL
    video_id = state.get("video_id")
    video_url = None
    if DEV_MODE:
        ext = ".mp4"
        video_url = f"{cfg.dev_api_url}/api/video/local/{video_id}{ext}"
    else:
        video_data = supabase.table("videos").select("cloudinary_url").eq("id", video_id).single().execute()
        if video_data.data:
            video_url = video_data.data["cloudinary_url"]

    if not video_url:
        raise HTTPException(status_code=400, detail="Video source not found")

    # Mark all as dirty and render
    from services.edit_state import mark_all_dirty
    state = mark_all_dirty(state)
    save_edit_state(state)

    from services.partial_render import render_edit_state
    output_url = await render_edit_state(
        job_id=job_id,
        user_id=current_user["id"],
        video_url=video_url,
    )

    download_url = output_url
    if DEV_MODE and output_url:
        download_url = output_url.replace(cfg.dev_api_url, "")

    return ExportResponse(
        job_id=job_id,
        output_url=output_url,
        download_url=download_url,
        message=f"Export complete. Total duration: {state['metadata']['total_duration']:.1f}s",
    )


# ── Video Analysis: AI understands the video ───────────────────────────────────

class AnalyzeVideoResponse(BaseModel):
    video_id: str
    analysis: Dict[str, Any]
    summary: Dict[str, Any]


@router.post("/{job_id}/analyze", response_model=AnalyzeVideoResponse)
async def analyze_video_endpoint(
    job_id: str,
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Trigger full video analysis (scene, silence, motion, audio, transcript, highlights)."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    video_id = state.get("video_id")
    if not video_id:
        raise HTTPException(status_code=400, detail="No video_id in edit state")

    from services.video_understanding_ai import analyze_video, get_summary_stats
    from core.config import settings

    supabase = get_supabase()
    DEV_MODE = settings.dev_mode
    video_url = None
    if DEV_MODE:
        video_url = f"{settings.dev_api_url}/api/video/local/{video_id}.mp4"
    else:
        video_data = supabase.table("videos").select("cloudinary_url").eq("id", video_id).single().execute()
        if video_data.data:
            video_url = video_data.data["cloudinary_url"]

    if not video_url:
        raise HTTPException(status_code=400, detail="Video source not found")

    analysis = await analyze_video(video_id, video_url, current_user["id"], force_reprocess=force)
    summary = get_summary_stats(analysis)

    return AnalyzeVideoResponse(
        video_id=video_id,
        analysis=analysis,
        summary=summary,
    )

class AutoEditResponse(BaseModel):
    job_id: str
    message: str
    applied_patches: List[str]


@router.post("/{job_id}/auto-edit", response_model=AutoEditResponse)
async def auto_edit(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """One-click AI auto-edit — analyzes video, generates edit plan, applies it."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.prompt_editor import process_prompt
    from services.ffmpeg_service import get_duration

    # Get video duration from metadata
    duration = state.get("metadata", {}).get("total_duration", 0)

    # Auto-detect mode based on duration
    mode = "reels" if duration < 120 else "vlog"

    # Generate smart auto-edit prompt
    auto_prompt = (
        f"Auto edit this {mode} video ({duration:.0f}s). "
        f"Smart cut silences, add dynamic captions throughout, "
        f"apply cinematic color grade, add smooth transitions between scenes. "
        f"Optimize pacing — remove dead space. "
        f"If reels mode: add zoom effects on key moments, keep tight pacing. "
        f"If vlog mode: structure with clear intro/body/outro pacing."
    )

    # Fetch video analysis
    video_analysis = None
    try:
        from services.video_understanding_ai import analyze_video
        video_id = state.get("video_id", "")
        if video_id:
            cached = supabase.table("video_analysis").select("analysis").eq("video_id", video_id).single().execute()
            if cached.data:
                video_analysis = cached.data["analysis"]
    except Exception:
        pass

    result = await process_prompt(job_id, current_user["id"], auto_prompt, video_analysis=video_analysis)
    state = get_edit_state(job_id, current_user["id"])

    # Auto-render after edit
    from services.edit_state import mark_all_dirty
    state = mark_all_dirty(state)
    save_edit_state(state)

    return AutoEditResponse(
        job_id=job_id,
        message=f"Auto edit complete for {mode} mode ({duration:.0f}s). {len(result['applied_patches'])} changes made.",
        applied_patches=result["applied_patches"],
    )


# ── Reference System: Analyze reference video ─────────────────────────────────

class ReferenceAnalysisRequest(BaseModel):
    reference_url: str
    style_profile_name: Optional[str] = None


class ReferenceAnalysisResponse(BaseModel):
    profile_id: str
    style_data: Dict[str, Any]
    analysis: Dict[str, Any]


@router.post("/{job_id}/reference", response_model=ReferenceAnalysisResponse)
async def analyze_reference(
    job_id: str,
    request: ReferenceAnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    """Analyze a reference video and create a style profile."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.reference_analyzer import analyze_reference_video
    result = await analyze_reference_video(
        reference_url=request.reference_url,
        user_id=current_user["id"],
        profile_name=request.style_profile_name,
    )

    # Store profile_id in edit state
    state["reference_profile"] = result["profile_id"]
    save_edit_state(state)

    return ReferenceAnalysisResponse(
        profile_id=result["profile_id"],
        style_data=result["style_data"],
        analysis=result["analysis"],
    )


# ── Apply Reference Style to current edit ─────────────────────────────────────

class ApplyReferenceResponse(BaseModel):
    job_id: str
    message: str
    applied_patches: List[str]


@router.post("/{job_id}/reference/apply", response_model=ApplyReferenceResponse)
async def apply_reference_style(
    job_id: str,
    profile_id: str = "",
    current_user: dict = Depends(get_current_user),
):
    """Apply a saved reference style profile to the current edit."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    pid = profile_id or state.get("reference_profile")
    if not pid:
        raise HTTPException(status_code=400, detail="No reference profile found")

    from services.reference_analyzer import apply_reference_style
    result = await apply_reference_style(state, pid, current_user["id"])

    state = result["state"]
    from services.edit_state import mark_all_dirty
    state = mark_all_dirty(state)
    save_edit_state(state)

    return ApplyReferenceResponse(
        job_id=job_id,
        message=f"Reference style applied. {len(result['applied_patches'])} changes made.",
        applied_patches=result["applied_patches"],
    )


# ── Vault: Store/retrieve media assets ────────────────────────────────────────

class VaultItem(BaseModel):
    id: str = ""
    type: Literal["meme", "sound", "video", "image"]
    name: str
    url: str
    tags: List[str] = []
    source: str = "user"


class VaultItemResponse(BaseModel):
    items: List[VaultItem]
    total: int


class VaultAddRequest(BaseModel):
    type: Literal["meme", "sound", "video", "image"]
    name: str
    url: str
    tags: List[str] = []


@router.post("/vault", response_model=VaultItem)
async def add_vault_item(
    request: VaultAddRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add an item to the user's vault."""
    from uuid import uuid4
    supabase = get_supabase()
    item = {
        "id": str(uuid4()),
        "user_id": current_user["id"],
        "type": request.type,
        "name": request.name,
        "url": request.url,
        "tags": request.tags,
        "source": "user",
    }
    supabase.table("vault_items").insert(item).execute()
    return VaultItem(**item)


@router.get("/vault", response_model=VaultItemResponse)
async def list_vault_items(
    type: Optional[str] = None,
    tag: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List vault items with optional type/tag filter."""
    supabase = get_supabase()
    q = supabase.table("vault_items").select("*").eq("user_id", current_user["id"])
    if type:
        q = q.eq("type", type)
    if tag:
        all_items = q.execute().data or []
        items = [i for i in all_items if tag in i.get("tags", [])]
    else:
        items = q.order("created_at", desc=True).limit(100).execute().data or []
    return VaultItemResponse(items=[VaultItem(**i) for i in items], total=len(items))


@router.delete("/vault/{item_id}")
async def delete_vault_item(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a vault item."""
    supabase = get_supabase()
    supabase.table("vault_items").delete().eq("id", item_id).eq("user_id", current_user["id"]).execute()
    return {"message": "Item deleted"}


@router.post("/vault/suggest")
async def suggest_vault_items(
    query: str = "",
    current_user: dict = Depends(get_current_user),
):
    """AI-suggest vault items based on edit context."""
    supabase = get_supabase()
    result = supabase.table("vault_items").select("*").eq("user_id", current_user["id"]).limit(50).execute()
    items = result.data or []

    scored = []
    q = query.lower()
    for item in items:
        score = 0
        if q in item.get("name", "").lower(): score += 3
        if any(q in t.lower() for t in item.get("tags", [])): score += 2
        if item.get("type") in q: score += 1
        scored.append((score, item))

    scored.sort(key=lambda x: -x[0])
    suggested = [item for _, item in scored if _ > 0][:10]

    return {"suggestions": suggested}


# ── Creator Memory: Save/Load style memory ────────────────────────────────────

class CreatorMemoryResponse(BaseModel):
    profile: Dict[str, Any]
    memories: List[Dict[str, Any]]


class MemoryEntry(BaseModel):
    key: str
    value: Any
    context: str = ""


@router.get("/{job_id}/memory", response_model=CreatorMemoryResponse)
async def get_creator_memory(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the creator's memory profile for this job."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.creator_memory import get_memory_profile
    profile, memories = get_memory_profile(current_user["id"], job_id)
    return CreatorMemoryResponse(profile=profile, memories=memories)


@router.post("/{job_id}/memory")
async def save_creator_memory(
    job_id: str,
    request: MemoryEntry,
    current_user: dict = Depends(get_current_user),
):
    """Save a memory entry (e.g., caption style, pacing preference)."""
    from services.creator_memory import save_memory
    save_memory(current_user["id"], job_id, request.key, request.value, request.context)
    return {"message": f"Memory saved: {request.key}"}


@router.post("/{job_id}/memory/auto-save")
async def auto_save_memory(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Auto-extract and save style preferences from current edit state."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.creator_memory import auto_learn_from_state
    saved = auto_learn_from_state(current_user["id"], job_id, state)
    return {"message": f"Learned {len(saved)} patterns from this edit", "saved": saved}


# ── Reel Highlight Detection ──────────────────────────────────────────────────

class HighlightRequest(BaseModel):
    max_clips: int = 10
    min_duration: float = 2.0
    max_duration: float = 15.0


class HighlightResponse(BaseModel):
    highlights: List[Dict[str, Any]]
    total_duration: float


@router.post("/{job_id}/highlights", response_model=HighlightResponse)
async def detect_highlights(
    job_id: str,
    request: HighlightRequest,
    current_user: dict = Depends(get_current_user),
):
    """Auto-detect highlight clips from the video for reel creation."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.highlight_engine import detect_highlights
    highlights = detect_highlights(
        state=state,
        max_clips=request.max_clips,
        min_duration=request.min_duration,
        max_duration=request.max_duration,
    )

    total_duration = sum(h["end"] - h["start"] for h in highlights)
    return HighlightResponse(highlights=highlights, total_duration=total_duration)


# ── Vlog Story Builder ────────────────────────────────────────────────────────

class VlogStructureRequest(BaseModel):
    style: str = "standard"  # standard, cinematic, educational, vlog_casual


class VlogStructureResponse(BaseModel):
    structure: List[Dict[str, Any]]
    timeline_segments: List[Dict[str, Any]]


@router.post("/{job_id}/vlog-structure", response_model=VlogStructureResponse)
async def build_vlog_structure(
    job_id: str,
    request: VlogStructureRequest,
    current_user: dict = Depends(get_current_user),
):
    """Build a vlog story structure from the video content."""
    state = get_edit_state(job_id, current_user["id"])
    if not state:
        raise HTTPException(status_code=404, detail="Edit state not found")

    from services.vlog_engine import build_vlog_structure
    result = build_vlog_structure(state, request.style, current_user["id"])

    state = result["state"]
    from services.edit_state import mark_all_dirty
    state = mark_all_dirty(state)
    save_edit_state(state)

    return VlogStructureResponse(
        structure=result["structure"],
        timeline_segments=result["timeline_segments"],
    )


# ── Chat History ──────────────────────────────────────────────────────────────


class ChatMessageRequest(BaseModel):
    role: str
    text: str
    patches_applied: bool = False


class ChatHistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]


@router.get("/{job_id}/chat", response_model=ChatHistoryResponse)
async def get_chat(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    from services.chat_history import get_chat_history
    messages = get_chat_history(job_id)
    return ChatHistoryResponse(messages=messages)


@router.post("/{job_id}/chat", response_model=ChatHistoryResponse)
async def post_chat(
    job_id: str,
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    from services.chat_history import append_chat_message
    messages = append_chat_message(job_id, request.role, request.text, request.patches_applied)
    return ChatHistoryResponse(messages=messages)
