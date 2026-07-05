"""
Video Route — upload, complete, list, delete.
Dev mode: saves locally and serves from backend.
Prod mode: uses Cloudinary for storage.
"""

from fastapi import APIRouter, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
import os
import json
import logging

from core.database import get_supabase
from core.security import get_current_user
from core.config import settings

router = APIRouter(prefix="/video", tags=["video"])
logger = logging.getLogger(__name__)

ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"}

# Dev mode: local storage
DEV_MODE = settings.dev_mode
DEV_STORAGE = settings.dev_storage_path
os.makedirs(DEV_STORAGE, exist_ok=True)


class VideoUploadInitRequest(BaseModel):
    filename: str
    content_type: str
    size: int


class VideoUploadInitResponse(BaseModel):
    video_id: str
    cloudinary_upload_url: str = ""
    cloud_name: str = ""
    api_key: str = ""
    timestamp: int = 0
    signature: str = ""
    folder: str = ""


class VideoResponse(BaseModel):
    id: str
    cloudinary_url: str
    duration: float
    status: str
    created_at: str


class YoutubeDownloadRequest(BaseModel):
    url: str


# ── Init upload ───────────────────────────────────────────────────────────────

@router.post("/upload/init", response_model=VideoUploadInitResponse)
async def init_upload(
    request: VideoUploadInitRequest,
    current_user: dict = Depends(get_current_user),
):
    if request.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid video format: {request.content_type}. Allowed: mp4, mov, avi, mkv, webm")

    if request.size > settings.max_video_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Video exceeds {settings.max_video_size_mb}MB limit")

    video_id = str(uuid4())
    folder = f"auteur/uploads/{current_user['id']}"

    if DEV_MODE:
        # Dev mode: just create record, upload happens via /upload/file
        supabase = get_supabase()
        supabase.table("videos").insert({
            "id": video_id,
            "user_id": current_user["id"],
            "cloudinary_url": None,
            "cloudinary_public_id": None,
            "duration": 0,
            "status": "uploading",
            "transcript": None,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        return VideoUploadInitResponse(
            video_id=video_id,
            folder=folder,
        )

    # Prod mode: Cloudinary signed upload
    from services.cloudinary_service import get_upload_signature
    sig_data = get_upload_signature(folder=folder)

    supabase = get_supabase()
    supabase.table("videos").insert({
        "id": video_id,
        "user_id": current_user["id"],
        "cloudinary_url": None,
        "cloudinary_public_id": None,
        "duration": 0,
        "status": "uploading",
        "transcript": None,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    return VideoUploadInitResponse(
        video_id=video_id,
        cloudinary_upload_url=f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/video/upload",
        cloud_name=settings.cloudinary_cloud_name,
        api_key=sig_data["api_key"],
        timestamp=sig_data["timestamp"],
        signature=sig_data["signature"],
        folder=folder,
    )


# ── Direct file upload (dev mode) ─────────────────────────────────────────────

@router.post("/upload/file")
async def upload_file_direct(
    video_id: str = Form(...),
    file: UploadFile = File(...),
    start_time: Optional[float] = Form(None),
    end_time: Optional[float] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """Direct file upload for dev mode — saves locally."""
    if not DEV_MODE:
        raise HTTPException(status_code=400, detail="Direct upload only available in dev mode")

    # Save file locally (temp path first if trimming)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    local_path = os.path.join(DEV_STORAGE, f"{video_id}{ext}")

    CHUNK_SIZE = 8 * 1024 * 1024
    with open(local_path, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            f.write(chunk)

    # Trim if start_time or end_time provided
    if start_time is not None or end_time is not None:
        trimmed_path = os.path.join(DEV_STORAGE, f"{video_id}_trimmed{ext}")
        try:
            from services.ffmpeg_service import _run
            ss = f"{start_time}" if start_time is not None else "0"
            to = f"{end_time}" if end_time is not None else ""
            cmd = ["ffmpeg", "-i", local_path, "-ss", ss]
            if to:
                cmd += ["-to", to]
            cmd += ["-c", "copy", "-y", trimmed_path]
            await _run(cmd)
            os.replace(trimmed_path, local_path)
        except Exception as e:
            logger.warning(f"Trim failed (saving full video): {e}")
            if os.path.exists(trimmed_path):
                os.remove(trimmed_path)

    # Build local URL
    local_url = f"{settings.dev_api_url}/api/video/local/{video_id}{ext}"

    # Get duration via ffprobe
    duration = 0.0
    try:
        from services.ffmpeg_service import get_duration
        duration = await get_duration(local_path)
    except Exception as e:
        logger.warning(f"Duration fetch failed: {e}")
        duration = 60.0  # fallback

    # Update DB
    supabase = get_supabase()
    supabase.table("videos").update({
        "cloudinary_url": local_url,
        "cloudinary_public_id": f"dev/{video_id}",
        "duration": duration,
        "status": "uploaded",
    }).eq("id", video_id).execute()

    return {"video_id": video_id, "duration": duration, "status": "uploaded", "url": local_url}


@router.get("/local/{filename}")
async def serve_local_file(filename: str):
    """Serve a locally stored video file (dev mode only)."""
    if not DEV_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    file_path = os.path.normpath(os.path.join(DEV_STORAGE, filename))
    if not file_path.startswith(os.path.normpath(DEV_STORAGE)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.exists(file_path):
        output_path = os.path.normpath(os.path.join(DEV_STORAGE, "output", filename))
        if output_path.startswith(os.path.normpath(DEV_STORAGE)) and os.path.exists(output_path):
            file_path = output_path
        else:
            raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4")


# ── Complete upload (prod mode) ───────────────────────────────────────────────

@router.post("/upload/complete")
async def complete_upload(
    video_id: str = Form(...),
    cloudinary_public_id: str = Form(...),
    cloudinary_url: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    if DEV_MODE:
        # Already handled by /upload/file
        return {"video_id": video_id, "duration": 0, "status": "uploaded"}

    supabase = get_supabase()
    video = supabase.table("videos").select("*").eq("id", video_id).eq("user_id", current_user["id"]).single().execute()
    if not video.data:
        raise HTTPException(status_code=404, detail="Video not found")

    duration = 0.0
    try:
        from services.ffmpeg_service import get_duration
        duration = await get_duration(cloudinary_url)
    except Exception as e:
        logger.warning(f"Duration fetch failed: {e}")

    supabase.table("videos").update({
        "cloudinary_public_id": cloudinary_public_id,
        "cloudinary_url": cloudinary_url,
        "duration": duration,
        "status": "uploaded",
    }).eq("id", video_id).execute()

    return {"video_id": video_id, "duration": duration, "status": "uploaded"}


# ── YouTube import ────────────────────────────────────────────────────────────

# ── Ref Video Upload ────────────────────────────────────────────────────────────

@router.post("/upload-ref")
async def upload_ref_video(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a reference video for style analysis. Saved as 'ref' type video."""
    if not file.content_type or file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid format: {file.content_type}")

    ref_id = str(uuid4())
    ext = os.path.splitext(file.filename or "ref.mp4")[1] or ".mp4"
    local_path = os.path.join(DEV_STORAGE, f"ref_{ref_id}{ext}")

    CHUNK_SIZE = 8 * 1024 * 1024
    with open(local_path, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            f.write(chunk)

    duration = 0.0
    try:
        from services.ffmpeg_service import get_duration
        duration = await get_duration(local_path)
    except Exception:
        duration = 30.0

    supabase = get_supabase()
    supabase.table("videos").insert({
        "id": ref_id,
        "user_id": current_user["id"],
        "cloudinary_url": f"{settings.dev_api_url}/api/video/local/ref_{ref_id}{ext}",
        "cloudinary_public_id": f"dev/ref_{ref_id}",
        "duration": duration,
        "status": "ref_uploaded",
        "filename": file.filename,
        "transcript": None,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    return {
        "ref_id": ref_id,
        "filename": file.filename,
        "duration": duration,
        "status": "ref_uploaded",
    }


@router.post("/youtube")
async def import_youtube(
    request: YoutubeDownloadRequest,
    current_user: dict = Depends(get_current_user),
):
    if DEV_MODE:
        video_id = str(uuid4())
        supabase = get_supabase()
        supabase.table("videos").insert({
            "id": video_id,
            "user_id": current_user["id"],
            "cloudinary_url": None,
            "cloudinary_public_id": None,
            "duration": 0,
            "status": "uploading",
            "transcript": None,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
        return {"video_id": video_id, "duration": 0, "status": "uploading",
                "message": "Dev mode: use direct file upload instead"}

    from services.yt_dlp_service import download_ref_video, cleanup_ref_video
    from services.cloudinary_service import upload_video_chunked

    video_id = str(uuid4())
    supabase = get_supabase()
    supabase.table("videos").insert({
        "id": video_id,
        "user_id": current_user["id"],
        "cloudinary_url": None,
        "cloudinary_public_id": None,
        "duration": 0,
        "status": "downloading",
        "transcript": None,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    try:
        ref = await download_ref_video(request.url)
        result = upload_video_chunked(ref["video_path"], folder=f"auteur/uploads/{current_user['id']}")
        supabase.table("videos").update({
            "cloudinary_url": result["secure_url"],
            "cloudinary_public_id": result["public_id"],
            "duration": ref["duration"],
            "status": "uploaded",
        }).eq("id", video_id).execute()
        cleanup_ref_video(ref["output_dir"])
        return {"video_id": video_id, "duration": ref["duration"], "status": "uploaded"}
    except Exception as e:
        supabase.table("videos").update({"status": "failed"}).eq("id", video_id).execute()
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)[:300]}")


# ── List & Get ────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[VideoResponse])
async def list_videos(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    videos = supabase.table("videos").select("*").eq("user_id", current_user["id"]).execute()
    return [
        VideoResponse(
            id=v["id"],
            cloudinary_url=v.get("cloudinary_url") or "",
            duration=v.get("duration", 0),
            status=v["status"],
            created_at=v.get("created_at", ""),
        )
        for v in (videos.data or [])
    ]


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    video = supabase.table("videos").select("*").eq("id", video_id).eq("user_id", current_user["id"]).single().execute()
    if not video.data:
        raise HTTPException(status_code=404, detail="Video not found")
    v = video.data
    return VideoResponse(
        id=v["id"],
        cloudinary_url=v.get("cloudinary_url") or "",
        duration=v.get("duration", 0),
        status=v["status"],
        created_at=v.get("created_at", ""),
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{video_id}")
async def delete_video(video_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    video = supabase.table("videos").select("*").eq("id", video_id).eq("user_id", current_user["id"]).single().execute()
    if not video.data:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete local file in dev mode
    if DEV_MODE:
        local_path = os.path.join(DEV_STORAGE, f"{video_id}.mp4")
        if os.path.exists(local_path):
            os.remove(local_path)
    else:
        public_id = video.data.get("cloudinary_public_id")
        if public_id:
            from services.cloudinary_service import delete_asset
            delete_asset(public_id, resource_type="video")

    supabase.table("videos").delete().eq("id", video_id).execute()

    # Cleanup thumbnails
    thumb_dir = os.path.join(DEV_STORAGE, "thumbs", video_id)
    if os.path.exists(thumb_dir):
        import shutil
        shutil.rmtree(thumb_dir)

    return {"message": "Video deleted"}


# ── Generate thumbnails for timeline ──────────────────────────────────────

THUMB_INTERVAL = settings.thumb_interval
THUMB_WIDTH = settings.thumb_width
THUMB_HEIGHT = settings.thumb_height


@router.get("/{video_id}/thumbnails")
async def get_video_thumbnails(video_id: str):
    """Generate and return timeline thumbnail strip for a video."""
    thumb_dir = os.path.join(DEV_STORAGE, "thumbs", video_id)
    os.makedirs(thumb_dir, exist_ok=True)

    # Check if thumbnails already exist
    existing = sorted([
        f for f in os.listdir(thumb_dir) if f.endswith(".jpg")
    ])
    if existing:
        return {
            "thumbnails": [
                f"{settings.dev_api_url}/api/video/thumb/{video_id}/{f}"
                for f in existing
            ],
            "interval": THUMB_INTERVAL,
            "count": len(existing),
        }

    # Find video file
    video_path = None
    for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        p = os.path.join(DEV_STORAGE, f"{video_id}{ext}")
        if os.path.exists(p):
            video_path = p
            break
    if not video_path:
        raise HTTPException(status_code=404, detail="Video file not found")

    # Get duration
    dur = 0.0
    try:
        from services.ffmpeg_service import get_duration
        dur = await get_duration(video_path)
    except Exception:
        dur = 60.0

    import subprocess
    count = max(1, min(int(dur / THUMB_INTERVAL), 100))
    output_pattern = os.path.join(thumb_dir, "thumb_%04d.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"fps=1/{THUMB_INTERVAL},scale={THUMB_WIDTH}:{THUMB_HEIGHT}",
        "-q:v", "5",
        output_pattern,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {str(e)[:200]}")

    generated = sorted([
        f for f in os.listdir(thumb_dir) if f.endswith(".jpg")
    ])
    return {
        "thumbnails": [
            f"{settings.dev_api_url}/api/video/thumb/{video_id}/{f}"
            for f in generated
        ],
        "interval": THUMB_INTERVAL,
        "count": len(generated),
    }


@router.get("/thumb/{video_id}/{filename}")
async def serve_thumbnail(video_id: str, filename: str):
    """Serve a generated thumbnail image."""
    thumb_path = os.path.normpath(os.path.join(DEV_STORAGE, "thumbs", video_id, filename))
    if not thumb_path.startswith(os.path.normpath(os.path.join(DEV_STORAGE, "thumbs"))):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")
