from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID
from enum import Enum


class UserBase(BaseModel):
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    plan: Optional[str] = None


class User(UserBase):
    id: str
    plan: str = "free"
    videos_used_this_month: int = 0
    style_dna: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VideoBase(BaseModel):
    filename: str
    r2_url: str
    duration: float
    size: int


class VideoCreate(VideoBase):
    user_id: str


class Video(VideoBase):
    id: str
    user_id: str
    transcript: Optional[str] = None
    status: str = "uploaded"
    created_at: datetime

    class Config:
        from_attributes = True


class VideoUploadRequest(BaseModel):
    filename: str
    content_type: str
    size: int


class VideoUploadResponse(BaseModel):
    video_id: str
    upload_url: str
    fields: Dict[str, str]


class YoutubeDownloadRequest(BaseModel):
    url: HttpUrl


class EditJobBase(BaseModel):
    video_id: str
    prompt: str
    ref_url: Optional[str] = None


class EditJobCreate(EditJobBase):
    user_id: str


class EditJob(EditJobBase):
    id: str
    user_id: str
    style_profile: Optional[Dict[str, Any]] = None
    edit_plan: Optional[Dict[str, Any]] = None
    status: str = "pending"
    progress: int = 0
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EditPlan(BaseModel):
    hook: Dict[str, Any]
    cuts: List[Dict[str, float]]
    captions: List[Dict[str, Any]]
    zoom_moments: List[Dict[str, Any]]
    music_vibe: str
    meme_moments: List[Dict[str, Any]]
    total_duration_target: int


class StyleProfile(BaseModel):
    avg_cut_duration_seconds: float
    caption_style: Dict[str, Any]
    energy_level: int
    hook_pattern: str
    transition_type: str
    music_vibe: str


class OutputVideoBase(BaseModel):
    job_id: str
    version_type: Literal["funny", "viral", "serious"]
    r2_url: str


class OutputVideo(OutputVideoBase):
    id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class IterationBase(BaseModel):
    job_id: str
    refinement_prompt: str
    updated_edit_plan: Dict[str, Any]
    output_url: str


class IterationCreate(IterationBase):
    user_id: str


class Iteration(IterationBase):
    id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class VaultItemBase(BaseModel):
    type: Literal["meme", "sound", "music", "preset"]
    name: str
    r2_url: str


class VaultItemCreate(VaultItemBase):
    user_id: str


class VaultItem(VaultItemBase):
    id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class PlanBase(BaseModel):
    name: str
    price_inr: int
    price_usd: int
    video_limit: int
    vault_limit: int
    features: List[str]


class Plan(PlanBase):
    id: str

    class Config:
        from_attributes = True


class PaymentBase(BaseModel):
    user_id: str
    plan_id: str
    amount: int
    currency: str
    provider: Literal["razorpay", "stripe"]
    status: str


class Payment(PaymentBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    error: Optional[str] = None
    output_videos: List[Dict[str, str]] = []


class RefineRequest(BaseModel):
    job_id: str
    version_type: Literal["funny", "viral", "serious"]
    refinement_prompt: str


class QuickVibe(str, Enum):
    FUNNY = "funny"
    VIRAL = "viral"
    CINEMATIC = "cinematic"
    PODCAST = "podcast"
    MEME_LORD = "meme_lord"
    MY_STYLE = "my_style"


# ══════════════════════════════════════════════════════════════════════════
# EDIT STATE LAYER — Source of Truth
# ══════════════════════════════════════════════════════════════════════════

class TimelineSegment(BaseModel):
    id: str
    clip_id: str
    source_start: float
    source_end: float
    timeline_start: float
    timeline_end: float
    speed: float = 1.0
    reversed: bool = False
    opacity: float = 1.0
    rotation: float = 0.0
    volume: float = 1.0
    freeze_frame: Optional[Dict[str, Any]] = None
    crop: Optional[Dict[str, float]] = None


class ClipMetadata(BaseModel):
    id: str
    video_id: str
    source_url: str
    duration: float
    fps: float = 30.0
    width: int = 1080
    height: int = 1920


class CaptionEntry(BaseModel):
    id: str
    text: str
    start: float
    end: float
    style: str = "bold_white_center"


class AudioTrack(BaseModel):
    id: str
    type: Literal["music", "sound_effect", "voiceover", "narration", "ambient"]
    source_url: str
    start: float
    duration: float
    volume: float = 0.25
    name: str = ""
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = False
    detached: bool = False


class EditEffects(BaseModel):
    color_grade: str = "none"
    transitions: List[Dict[str, Any]] = []
    blur_background: bool = False
    brightness: Optional[float] = None
    contrast: Optional[float] = None
    saturation: Optional[float] = None
    blur_effects: List[Dict[str, Any]] = []
    shake_effects: List[Dict[str, Any]] = []
    glow_effects: List[Dict[str, Any]] = []
    vignette_effects: List[Dict[str, Any]] = []
    grain_effects: List[Dict[str, Any]] = []


class EditMetadata(BaseModel):
    total_duration: float = 0
    fps: float = 30.0
    width: int = 1080
    height: int = 1920
    mode: str = "reels"
    aspect_ratio: str = "9:16"
    auto_reframe: bool = False


class EditState(BaseModel):
    id: str = ""
    job_id: str = ""
    user_id: str = ""
    video_id: str = ""
    mode: str = "reels"
    timeline: List[TimelineSegment] = []
    clips: List[ClipMetadata] = []
    captions: List[CaptionEntry] = []
    audio_tracks: List[AudioTrack] = []
    effects: EditEffects = EditEffects()
    metadata: EditMetadata = EditMetadata()
    dirty_segments: List[Dict[str, float]] = []
    version: int = 1
    version_history: List[Dict[str, Any]] = []
    undo_stack: List[Dict[str, Any]] = []
    redo_stack: List[Dict[str, Any]] = []
    keyframes: List[Dict[str, Any]] = []
    overlays: List[Dict[str, Any]] = []
    playback: Dict[str, Any] = {}
    audio_ducking: Optional[Dict[str, Any]] = None


# ── Manual Editor Actions ────────────────────────────────────────────────

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


class EditStateAction(BaseModel):
    pass  # Union type handled manually


# ── Quality Engine ────────────────────────────────────────────────────────

class QualityScoreResponse(BaseModel):
    job_id: str
    hook_strength: int
    pacing_score: int
    engagement_score: int
    overall_score: float
    passed: bool
    details: Dict[str, Any] = {}
    evaluation: str = ""


# ── Prompt Editor ─────────────────────────────────────────────────────────

class PromptEditRequest(BaseModel):
    job_id: str
    prompt: str


class PromptEditResponse(BaseModel):
    job_id: str
    applied_patches: List[Dict[str, Any]]
    message: str
    needs_render: bool = True


# ── Reels / Vlog ──────────────────────────────────────────────────────────

class VlogChunk(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    importance: int = 5
    summary: str = ""
    keep_segments: List[Dict[str, float]] = []
    remove_segments: List[Dict[str, float]] = []


class ChunkAnalysisResult(BaseModel):
    chunks: List[VlogChunk]
    story_intro: Optional[Dict[str, float]] = None
    story_highlights: List[Dict[str, float]] = []
    story_ending: Optional[Dict[str, float]] = None
    global_duration: float = 0


# ── Creator Memory ────────────────────────────────────────────────────────

class CreatorMemory(BaseModel):
    preferred_pacing: str = "medium"
    caption_style: str = "bold_white_center"
    music_vibe: str = "lo-fi"
    color_grade: str = "warm"
    energy_level: int = 5
    avg_cut_duration: float = 3.0
    hook_pattern: str = "question hook"
    vault_usage_freq: str = "low"
    style_json: Dict[str, Any] = {}
    edit_count: int = 0


# ── Vault Enhanced ────────────────────────────────────────────────────────

class VaultClipSuggestion(BaseModel):
    vault_item_id: str
    clip_id: str
    start_time: float
    end_time: float
    label: str
    tags: List[str] = []


# ── Edit Intelligence Layer ──────────────────────────────────────────────

class EditIntelligenceResult(BaseModel):
    plan: Dict[str, Any]
    critique: Dict[str, Any] = {}
    quality_scores: Dict[str, float] = {}
    story_confidence: float = 6.0
    passes_completed: int = 4
    elapsed_seconds: float = 0
    segments_total: int = 0


# ── Diff Engine ──────────────────────────────────────────────────────────

class EditDiffResult(BaseModel):
    changes: List[Dict[str, Any]]
    summary: str
    total_changes: int
    old_segment_count: int
    new_segment_count: int


# ── Preview Render ───────────────────────────────────────────────────────

class PreviewRenderResult(BaseModel):
    preview_path: Optional[str] = None
    preview_id: str = ""
    resolution: str = "480p"
    preset: str = "ultrafast"
    file_size_bytes: int = 0
    segments_count: int = 0


# ── Metrics ──────────────────────────────────────────────────────────────

class MetricsEvent(BaseModel):
    event_type: str
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    data: Dict[str, Any] = {}


# ── Undo/Redo ────────────────────────────────────────────────────────────

class UndoRedoResult(BaseModel):
    state: Dict[str, Any]
    undo_remaining: int
    redo_remaining: int
    message: str


# ── Version History ──────────────────────────────────────────────────────

class VersionSnapshot(BaseModel):
    index: int
    label: str
    saved_at: str


class VersionHistoryResult(BaseModel):
    versions: List[VersionSnapshot]
    current_version: int