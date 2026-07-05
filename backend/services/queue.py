"""
Queue Service — Redis-backed job queue for edit pipeline.
Single job per edit request (one perfect edit per vibe).
"""

import redis
import json
import asyncio
import time
import os
import shutil
import tempfile
from typing import Dict, Any, Optional
from core.config import settings
from core.database import get_supabase
import logging

logger = logging.getLogger(__name__)

_redis_client = None
JOB_TIMEOUT_SECONDS = settings.job_timeout_seconds
DEAD_LETTER_QUEUE = "queue:dead_letters"


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def enqueue_edit_job(job_id: str, payload: Dict[str, Any]) -> bool:
    """Push a single edit job to the Redis queue."""
    try:
        r = _get_redis()
        job_data = json.dumps({"job_id": job_id, "payload": payload, "enqueued_at": time.time()})
        r.lpush("queue:edit_jobs", job_data)

        supabase = get_supabase()
        supabase.table("edit_jobs").update({"status": "queued"}).eq("id", job_id).execute()

        logger.info(f"Enqueued edit job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Enqueue error: {e}")
        return False


async def dequeue_edit_job() -> Optional[Dict[str, Any]]:
    """Pop a job from the queue (FIFO)."""
    try:
        r = _get_redis()
        job_data = r.rpop("queue:edit_jobs")
        if job_data:
            return json.loads(job_data)
        return None
    except Exception as e:
        logger.error(f"Dequeue error: {e}")
        return None


async def update_job_progress(
    job_id: str,
    progress: int,
    status: str,
    message: str = "",
    error: str = None,
):
    """Update job progress in Supabase and broadcast via Redis pub/sub."""
    try:
        supabase = get_supabase()
        update_data = {"progress": progress, "status": status}
        if error:
            update_data["error"] = error
        supabase.table("edit_jobs").update(update_data).eq("id", job_id).execute()

        r = _get_redis()
        r.publish(f"job:{job_id}:progress", json.dumps({
            "job_id":   job_id,
            "progress": progress,
            "status":   status,
            "message":  message,
            "error":    error,
        }))
    except Exception as e:
        logger.error(f"Progress update error: {e}")


async def cancel_job(job_id: str) -> bool:
    """Remove a queued job from Redis before it starts processing."""
    try:
        r = _get_redis()
        jobs = r.lrange("queue:edit_jobs", 0, -1)
        for job_data in jobs:
            job = json.loads(job_data)
            if job.get("job_id") == job_id:
                r.lrem("queue:edit_jobs", 1, job_data)
                logger.info(f"Cancelled job {job_id}")
                return True
        return False
    except Exception as e:
        logger.error(f"Cancel job error: {e}")
        return False


async def send_to_dead_letter(job_id: str, payload: Dict[str, Any], error: str):
    """Move a failed job to the dead letter queue."""
    try:
        r = _get_redis()
        dl_data = json.dumps({
            "job_id": job_id,
            "payload": payload,
            "error": error,
            "failed_at": time.time(),
        })
        r.lpush(DEAD_LETTER_QUEUE, dl_data)
        logger.info(f"Job {job_id} sent to dead letter queue: {error}")
    except Exception as e:
        logger.error(f"Dead letter error: {e}")


async def process_edit_job(job_id: str, payload: Dict[str, Any]):
    """Route job to correct pipeline based on is_refinement flag."""
    is_refinement = payload.get("is_refinement", False)
    try:
        if is_refinement:
            from services.edit_pipeline import run_refine_pipeline
            await asyncio.wait_for(
                run_refine_pipeline(job_id, payload),
                timeout=JOB_TIMEOUT_SECONDS,
            )
        else:
            from services.edit_pipeline import run_edit_pipeline
            await asyncio.wait_for(
                run_edit_pipeline(job_id, payload),
                timeout=JOB_TIMEOUT_SECONDS,
            )
    except asyncio.TimeoutError:
        logger.error(f"Job {job_id} timed out after {JOB_TIMEOUT_SECONDS}s")
        await update_job_progress(job_id, 0, "failed", error=f"Timed out after {JOB_TIMEOUT_SECONDS}s")
        await send_to_dead_letter(job_id, payload, f"Timeout")
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await update_job_progress(job_id, 0, "failed", error=str(e))
        await send_to_dead_letter(job_id, payload, str(e))


async def cleanup_temp_files():
    """Remove temporary files older than 1 hour from dev_uploads/."""
    try:
        temp_dir = os.path.join(os.path.dirname(__file__), "..", "dev_uploads")
        if not os.path.isdir(temp_dir):
            return
        now = time.time()
        for fname in os.listdir(temp_dir):
            fpath = os.path.join(temp_dir, fname)
            if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 3600:
                os.remove(fpath)
                logger.info(f"Cleaned up temp file: {fpath}")
    except Exception as e:
        logger.error(f"Temp cleanup error: {e}")


async def start_worker(shutdown_event: asyncio.Event = None):
    """
    Blocking worker loop — polls Redis queue and processes jobs one at a time.
    Run this as: python -m backend.worker  (see server.ts for full startup)
    """
    logger.info("Edit worker started. Waiting for jobs...")
    cleanup_counter = 0
    while True:
        if shutdown_event and shutdown_event.is_set():
            logger.info("Worker loop shutting down gracefully")
            break
        try:
            job = await dequeue_edit_job()
            if job:
                logger.info(f"Processing job: {job['job_id']}")
                await process_edit_job(job["job_id"], job["payload"])
            else:
                await asyncio.sleep(1)
            cleanup_counter += 1
            if cleanup_counter >= 60:
                await cleanup_temp_files()
                cleanup_counter = 0
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5)
