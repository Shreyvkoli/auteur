import json
import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from core.database import get_supabase
from core.security import get_current_user
from core.config import settings
from services.queue import enqueue_edit_job
import redis
import logging

DEV_MODE = settings.dev_mode

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


class JobListResponse(BaseModel):
    id: str
    video_id: str
    prompt: str
    status: str
    progress: int
    created_at: str
    output_videos: List[dict] = []


@router.get("/", response_model=List[JobListResponse])
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase()
    query = supabase.table("edit_jobs").select("*").eq("user_id", current_user["id"])
    
    if status:
        query = query.eq("status", status)
    
    jobs = query.order("created_at", desc=True).limit(limit).execute()
    
    result = []
    for job in (jobs.data or []):
        output_videos = []
        if job.get("status") == "completed" and not DEV_MODE:
            outputs = supabase.table("output_videos").select("*").eq("job_id", job["id"]).execute()
            for o in (outputs.data or []):
                output_videos.append({
                    "version_type": o.get("version_type", ""),
                    "url": o.get("cloudinary_url", ""),
                    "id": o.get("id", ""),
                })
        
        result.append(JobListResponse(
            id=job.get("id", ""),
            video_id=job.get("video_id", ""),
            prompt=job.get("prompt", ""),
            status=job.get("status", "unknown"),
            progress=job.get("progress", 0),
            created_at=job.get("created_at", ""),
            output_videos=output_videos,
        ))
    
    return result


@router.get("/{job_id}")
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    job = supabase.table("edit_jobs").select("*").eq("id", job_id).eq("user_id", current_user["id"]).single().execute()
    
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    j = job.data
    
    output_videos = []
    if j.get("status") == "completed" and not DEV_MODE:
        outputs = supabase.table("output_videos").select("*").eq("job_id", job_id).execute()
        for o in (outputs.data or []):
            output_videos.append({
                "version_type": o.get("version_type", ""),
                "url": o.get("cloudinary_url", ""),
                "id": o.get("id", ""),
            })
    
    return {
        **j,
        "output_videos": output_videos,
    }


@router.delete("/{job_id}")
async def cancel_job(job_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    job = supabase.table("edit_jobs").select("*").eq("id", job_id).eq("user_id", current_user["id"]).single().execute()
    
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.data["status"] in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed job")
    
    supabase.table("edit_jobs").update({"status": "cancelled", "error": "Cancelled by user"}).eq("id", job_id).execute()
    
    from services.queue import cancel_job as cancel_queue_job
    await cancel_queue_job(job_id)
    
    return {"message": "Job cancelled"}


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    job = supabase.table("edit_jobs").select("*").eq("id", job_id).eq("user_id", current_user["id"]).single().execute()
    
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.data["status"] not in ["failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Can only retry failed or cancelled jobs")
    
    new_job_id = job.data["id"]
    supabase.table("edit_jobs").update({
        "status": "queued",
        "progress": 0,
        "error": None
    }).eq("id", new_job_id).execute()
    
    ref_video_ids = job.data.get("ref_video_ids") or []

    await enqueue_edit_job(new_job_id, {
        "video_id":        job.data["video_id"],
        "user_id":         current_user["id"],
        "prompt":          job.data["prompt"],
        "version_type":    job.data.get("version_type", "viral"),
        "ref_video_ids":   ref_video_ids,
        "vault_items":     job.data.get("vault_items", []),
        "mode":            job.data.get("mode", "reels"),
        "target_duration": job.data.get("target_duration"),
        "style_profile":   job.data.get("ref_style_profile"),
        "edit_plan":       job.data.get("edit_plan"),
    })
    
    return {"job_id": new_job_id, "status": "queued"}


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str, current_user: dict = Depends(get_current_user)):
    """Server-Sent Events endpoint for real-time job progress."""
    supabase = get_supabase()
    job = supabase.table("edit_jobs").select("*").eq("id", job_id).eq("user_id", current_user["id"]).single().execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        r = redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        pubsub.subscribe(f"job:{job_id}:progress")
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = message["data"]
                    yield f"data: {data}\n\n"
                    parsed = json.loads(data)
                    if parsed.get("status") in ("completed", "failed"):
                        break
                else:
                    job = supabase.table("edit_jobs").select("status").eq("id", job_id).single().execute()
                    if job.data and job.data.get("status") in ("completed", "failed"):
                        yield f"data: {json.dumps({'status': job.data['status'], 'progress': 100})}\n\n"
                        break
                await asyncio.sleep(0.5)
        finally:
            pubsub.unsubscribe()
            r.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")