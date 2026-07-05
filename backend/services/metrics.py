"""
Internal Metrics Service — Track time to preview, render time, iterations, satisfaction.
Uses Redis for counters + Supabase for durability.
"""

import time
import json
import redis
from typing import Dict, Any, Optional
from core.database import get_supabase
from core.config import settings


def get_redis():
    return redis.from_url(settings.redis_url, decode_responses=True)


async def track_event(event_type: str, data: Dict[str, Any], user_id: Optional[str] = None,
                     project_id: Optional[str] = None):
    """Track an internal metric event."""
    event = {
        "event_type": event_type,
        "user_id": user_id,
        "project_id": project_id,
        "data": data,
        "timestamp": time.time(),
    }

    # Store in Supabase for durability
    try:
        db = get_supabase()
        db.table("metrics").insert({
            "event_type": event_type,
            "user_id": user_id,
            "project_id": project_id,
            "data": json.dumps(data),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }).execute()
    except Exception:
        pass

    # Increment Redis counter for real-time dashboard
    try:
        redis = get_redis()
        day_key = f"metrics:{event_type}:{time.strftime('%Y-%m-%d')}"
        redis.incr(day_key)
        redis.expire(day_key, 86400 * 30)  # 30 day TTL

        if user_id:
            user_key = f"metrics:{event_type}:user:{user_id}:{time.strftime('%Y-%m-%d')}"
            redis.incr(user_key)
            redis.expire(user_key, 86400 * 30)
    except Exception:
        pass


async def track_preview_time(project_id: str, preview_seconds: float, resolution: str = "480p"):
    """Track how long a preview took to render."""
    await track_event("preview_render", {
        "preview_seconds": round(preview_seconds, 2),
        "resolution": resolution,
    }, project_id=project_id)


async def track_full_render(project_id: str, render_seconds: float, file_size_bytes: int,
                            resolution: str = "1080p"):
    """Track full render performance."""
    await track_event("full_render", {
        "render_seconds": round(render_seconds, 2),
        "file_size_bytes": file_size_bytes,
        "resolution": resolution,
    }, project_id=project_id)


async def track_prompt_iteration(project_id: str, user_id: Optional[str], iteration_number: int,
                                 prompt_text: str, time_seconds: float):
    """Track a prompt edit iteration."""
    await track_event("prompt_iteration", {
        "iteration_number": iteration_number,
        "prompt_length": len(prompt_text),
        "time_seconds": round(time_seconds, 2),
    }, user_id=user_id, project_id=project_id)


async def track_edit_quality(project_id: str, quality_scores: Dict[str, float],
                             overall_score: float):
    """Track edit quality scores."""
    await track_event("edit_quality", {
        "quality_scores": quality_scores,
        "overall_score": overall_score,
    }, project_id=project_id)


async def track_vault_usage(project_id: str, vault_clips_used: int, total_suggestions: int,
                            relevance_scores: list):
    """Track vault suggestion quality."""
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
    await track_event("vault_usage", {
        "clips_used": vault_clips_used,
        "total_suggestions": total_suggestions,
        "avg_relevance": round(avg_relevance, 2),
    }, project_id=project_id)


async def get_daily_stats(date: Optional[str] = None) -> Dict[str, Any]:
    """Get aggregated stats for a day."""
    if not date:
        date = time.strftime("%Y-%m-%d")

    try:
        redis = get_redis()
        stats = {}
        event_types = ["preview_render", "full_render", "prompt_iteration", "edit_quality", "vault_usage"]

        for event_type in event_types:
            key = f"metrics:{event_type}:{date}"
            count = redis.get(key)
            stats[event_type] = int(count) if count else 0

        return {"date": date, "counts": stats}
    except Exception:
        return {"date": date, "counts": {}}


async def get_user_stats(user_id: str, days: int = 7) -> Dict[str, Any]:
    """Get user-specific stats over N days."""
    try:
        db = get_supabase()
        result = (
            db.table("metrics")
            .select("event_type, data, created_at")
            .eq("user_id", user_id)
            .gte("created_at", time.strftime("%Y-%m-%dT00:00:00Z",
                                              time.gmtime(time.time() - days * 86400)))
            .execute()
        )

        rows = result.data or []
        stats = {
            "total_projects": len(set(r.get("project_id") for r in rows if r.get("project_id"))),
            "total_preview_renders": 0,
            "total_full_renders": 0,
            "avg_preview_time": 0,
            "avg_render_time": 0,
            "total_iterations": 0,
        }

        preview_times = []
        render_times = []

        for row in rows:
            event_type = row.get("event_type")
            data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})

            if event_type == "preview_render":
                stats["total_preview_renders"] += 1
                if "preview_seconds" in data:
                    preview_times.append(data["preview_seconds"])
            elif event_type == "full_render":
                stats["total_full_renders"] += 1
                if "render_seconds" in data:
                    render_times.append(data["render_seconds"])
            elif event_type == "prompt_iteration":
                stats["total_iterations"] += 1

        if preview_times:
            stats["avg_preview_time"] = round(sum(preview_times) / len(preview_times), 2)
        if render_times:
            stats["avg_render_time"] = round(sum(render_times) / len(render_times), 2)

        return stats
    except Exception:
        return {}
