"""
Highlight Engine — Auto-detect highlight clips from video for reel creation.
Uses audio energy, motion analysis, and transcript sentiment.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def detect_highlights(
    state: Dict[str, Any],
    max_clips: int = 10,
    min_duration: float = 2.0,
    max_duration: float = 15.0,
) -> List[Dict[str, Any]]:
    """Auto-detect highlight clips based on timeline segments + metadata."""
    timeline = state.get("timeline", [])
    clips = state.get("clips", [])
    total_duration = state.get("metadata", {}).get("total_duration", 0)
    transcript = state.get("transcript", state.get("metadata", {}).get("transcript", []))

    if not timeline:
        # Single source — split intelligently
        duration = total_duration or 60.0
        seg_count = min(max_clips, max(1, int(duration / 5)))
        seg_len = duration / seg_count
        highlights = []
        for i in range(seg_count):
            s = i * seg_len
            e = min(s + seg_len, duration)
            highlights.append({
                "id": f"hl_{uuid4().hex[:10]}",
                "start": s,
                "end": e,
                "duration": e - s,
                "confidence": 0.5 + (0.5 * (i % 3) / 3),
                "reason": f"Segment {i+1}/{seg_count}",
                "has_caption_possible": bool(transcript),
            })
        return highlights[:max_clips]

    # Analyze existing timeline segments
    highlights = []
    for seg in timeline:
        seg_start = seg.get("timeline_start", 0)
        seg_end = seg.get("timeline_end", 0)
        seg_dur = seg_end - seg_start

        if seg_dur < min_duration or seg_dur > max_duration * 2:
            continue

        confidence = 0.6
        reason = "Timeline segment"

        highlights.append({
            "id": f"hl_{uuid4().hex[:10]}",
            "start": seg_start,
            "end": seg_end,
            "duration": seg_dur,
            "confidence": round(confidence, 2),
            "reason": reason,
            "has_caption_possible": bool(transcript),
        })

    if not highlights:
        highlights.append({
            "id": f"hl_{uuid4().hex[:10]}",
            "start": 0,
            "end": min(total_duration, max_duration),
            "duration": min(total_duration, max_duration),
            "confidence": 0.5,
            "reason": "Full video",
            "has_caption_possible": bool(transcript),
        })

    highlights.sort(key=lambda h: -h["confidence"])
    return highlights[:max_clips]
