from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime
from core.database import get_supabase
from core.security import get_current_user
from core.config import settings
from services.queue import enqueue_edit_job
import logging

DEV_MODE = settings.dev_mode

router = APIRouter(prefix="/edit", tags=["edit"])
logger = logging.getLogger(__name__)


class EditRequest(BaseModel):
    video_id: str
    prompt: str = ""
    version_type: str = "viral"          # "funny" | "viral" | "serious" — user picks ONE
    ref_video_ids: Optional[List[str]] = None  # array of ref video IDs for style analysis
    ref_url: Optional[str] = None        # single ref URL (legacy)
    style_profile: Optional[Dict[str, Any]] = None   # from /style/analyze-ref
    vault_items: Optional[List[Dict[str, Any]]] = None
    mode: str = "reels"                  # "reels" | "vlog"
    target_duration: Optional[float] = None  # vlog mode: desired final duration


class EditResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    error: Optional[str] = None
    output_video: Optional[Dict[str, str]] = None    # single output, not list
    changelog: Optional[Dict[str, Any]] = None


class RefineRequest(BaseModel):
    job_id: str
    version_type: str
    refinement_prompt: str
    mode: str = "reels"


@router.post("/", response_model=EditResponse)
async def create_edit_job(
    request: EditRequest,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase()

    # ── Validate video belongs to user ────────────────────────────────────────
    video = supabase.table("videos").select("*").eq("id", request.video_id).eq("user_id", current_user["id"]).single().execute()
    if not video.data:
        raise HTTPException(status_code=404, detail="Video not found")

    if not DEV_MODE and video.data["status"] not in ("uploaded", "processed"):
        raise HTTPException(status_code=400, detail="Video not ready for editing")

    # ── Plan limit check (skip in dev mode) ──────────────────────────────────
    if not DEV_MODE:
        user = supabase.table("users").select("plan, videos_used_this_month").eq("id", current_user["id"]).single().execute()
        if not user.data:
            raise HTTPException(status_code=404, detail="User not found")

        plan = user.data.get("plan", "free")
        videos_used = user.data.get("videos_used_this_month", 0)
        plan_limits = {"free": 3, "creator": -1, "pro": -1}
        limit = plan_limits.get(plan, 3)

        if limit != -1 and videos_used >= limit:
            raise HTTPException(
                status_code=403,
                detail=f"Monthly limit reached ({limit} videos). Upgrade to continue."
            )

    # ── Create job ────────────────────────────────────────────────────────────
    job_id = str(uuid4())
    now = datetime.utcnow().isoformat()

    ref_video_ids = request.ref_video_ids or []
    if not ref_video_ids and request.ref_url:
        ref_video_ids = [request.ref_url]

    supabase.table("edit_jobs").insert({
        "id":             job_id,
        "user_id":        current_user["id"],
        "video_id":       request.video_id,
        "prompt":         request.prompt,
        "version_type":   request.version_type,
        "ref_video_ids":  ref_video_ids,
        "ref_style_profile": request.style_profile,
        "status":         "queued",
        "progress":       0,
        "error":          None,
        "created_at":     now,
        "updated_at":     now,
    }).execute()

    # ── Enqueue single job ────────────────────────────────────────────────────
    await enqueue_edit_job(job_id, {
        "video_id":        request.video_id,
        "user_id":         current_user["id"],
        "prompt":          request.prompt,
        "version_type":    request.version_type,
        "style_profile":   request.style_profile,
        "ref_video_ids":   ref_video_ids,
        "vault_items":     request.vault_items or [],
        "mode":            request.mode,
        "target_duration": request.target_duration,
    })

    return EditResponse(
        job_id=job_id,
        status="queued",
        message="Edit job queued. Your reel will be ready in ~60 seconds."
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    job = supabase.table("edit_jobs").select("*").eq("id", job_id).eq("user_id", current_user["id"]).single().execute()

    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")

    j = job.data
    output_video = None

    if j["status"] == "completed":
        output = supabase.table("output_videos").select("*").eq("job_id", job_id).order("created_at", desc=True).limit(1).execute()
        if output.data:
            o = output.data[0]
            output_video = {
                "version_type":  o["version_type"],
                "url":           o["cloudinary_url"],
                "id":            o["id"],
            }

    return JobStatusResponse(
        job_id=j["id"],
        status=j["status"],
        progress=j["progress"],
        message=j.get("error") or _status_message(j["status"]),
        error=j.get("error"),
        output_video=output_video,
        changelog=j.get("changelog"),
    )


def _status_message(status: str) -> str:
    return {
        "queued":          "Waiting in queue...",
        "transcribing":    "AI is listening to your video...",
        "analyzing_style": "Analysing reference style...",
        "generating_plan": "Building your perfect edit plan...",
        "rendering":       "Cutting and rendering your reel...",
        "finalizing":      "Finalising your video...",
        "completed":       "Your edit is ready! 🎬",
        "failed":          "Something went wrong. Please try again.",
    }.get(status, f"Processing...")


@router.post("/refine", response_model=EditResponse)
async def refine_edit(
    request: RefineRequest,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase()

    # Validate original job
    job = supabase.table("edit_jobs").select("*").eq("id", request.job_id).eq("user_id", current_user["id"]).single().execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.data["status"] != "completed":
        raise HTTPException(status_code=400, detail="Can only refine completed jobs")

    # Get latest output to retrieve edit_plan
    output = supabase.table("output_videos").select("*").eq("job_id", request.job_id).order("created_at", desc=True).limit(1).execute()
    if not output.data:
        raise HTTPException(status_code=404, detail="Output video not found")

    original_edit_plan = output.data[0].get("edit_plan", {})

    # Create refinement job
    new_job_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    ref_video_ids = job.data.get("ref_video_ids") or []
    if not ref_video_ids:
        ref_url = job.data.get("ref_url") or ""
        ref_video_ids = [ref_url] if ref_url else []

    supabase.table("edit_jobs").insert({
        "id":             new_job_id,
        "user_id":        current_user["id"],
        "video_id":       job.data["video_id"],
        "prompt":         f"REFINE: {request.refinement_prompt}",
        "version_type":   request.version_type,
        "ref_video_ids":  ref_video_ids,
        "ref_style_profile": job.data.get("ref_style_profile"),
        "status":         "queued",
        "progress":       0,
        "error":          None,
        "created_at":     now,
        "updated_at":     now,
    }).execute()

    await enqueue_edit_job(new_job_id, {
        "video_id":            job.data["video_id"],
        "user_id":             current_user["id"],
        "prompt":              request.refinement_prompt,
        "version_type":        request.version_type,
        "ref_video_ids":       ref_video_ids,
        "vault_items":         job.data.get("vault_items", []),
        "mode":                request.mode,
        "target_duration":     job.data.get("target_duration"),
        "refinement_prompt":   request.refinement_prompt,
        "original_edit_plan":  original_edit_plan,
        "original_job_id":     request.job_id,
        "is_refinement":       True,
    })

    return EditResponse(
        job_id=new_job_id,
        status="queued",
        message="Refinement queued. Re-rendering only the changed parts..."
    )


@router.get("/history")
async def get_edit_history(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    jobs = supabase.table("edit_jobs").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).limit(50).execute()
    return jobs.data