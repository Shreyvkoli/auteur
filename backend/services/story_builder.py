"""
Story Builder — Vlog chunk pipeline + global story assembly.

For vlog mode (long-form), the video is split into 3-5 min chunks.
Each chunk is analyzed independently for:
  - importance score (1-10)
  - keep/remove segments
  - summary

Then a global story is built:
  - detect intro
  - detect highlights
  - detect ending
  - drop lowest-importance segments to hit target_duration
"""

import json
import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from openai import AsyncOpenAI
from core.config import settings
from core.database import get_supabase

logger = logging.getLogger(__name__)

_client: AsyncOpenAI = None


def _is_local_llm() -> bool:
    base = settings.openai_base_url or ""
    return "localhost" in base or "127.0.0.1" in base


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        _client = AsyncOpenAI(**kwargs)
    return _client


CHUNK_ANALYSIS_PROMPT = """You are a video story analyst. Given a transcript segment (a chunk of a larger video), analyze it:

Transcript chunk:
{transcript}

Chunk time range: {start:.1f}s to {end:.1f}s

Return ONLY valid JSON — no markdown, no explanation:
{{
  "importance": <int 1-10>,
  "keep_segments": [{{"start": <float>, "end": <float>, "reason": "<string>"}}],
  "remove_segments": [{{"start": <float>, "end": <float>, "reason": "<string>"}}],
  "summary": "<1-2 sentence summary>",
  "is_intro": <bool>,
  "is_highlight": <bool>,
  "is_ending": <bool>
}}

Rules:
- importance 10 = most important (key insight, emotional moment, punchline)
- importance 1 = filler (can be safely removed)
- keep_segments: the parts worth keeping within this chunk
- remove_segments: the parts that can be cut to save time
- A chunk can have multiple segments of each type
- When the user is rambling, mark those parts as remove
"""

STORY_ASSEMBLY_PROMPT = """You are a video story editor. Combine analyzed chunks into a coherent narrative.

Chunk analyses:
{chunks_json}

Target duration: {target_duration}s
Current total: {current_duration}s

Return ONLY valid JSON — no markdown, no explanation:
{{
  "intro": {{"from_chunk": <int>, "segments": [{{"start": <float>, "end": <float>}}]}},
  "body": [{{"from_chunk": <int>, "segments": [{{"start": <float>, "end": <float>}}], "narrative_role": "<string>"}}],
  "ending": {{"from_chunk": <int>, "segments": [{{"start": <float>, "end": <float>}}]}},
  "drop_segments": [{{"from_chunk": <int>, "start": <float>, "end": <float>, "reason": "<string>"}}],
  "final_duration": <float>,
  "story_flow": "<1-2 sentence describing the narrative flow>"
}}

Rules:
- If total exceeds target_duration, drop_lowest_importance segments first
- Maintain narrative continuity — don't create jarring jumps
- The story should have: hook → build → climax → resolution
"""


# ── Chunking ────────────────────────────────────────────────────────────────────

def chunk_video(duration: float, chunk_duration: float = 180) -> List[Dict[str, float]]:
    """Split a video timeline into chunks of specified duration (default 3 min)."""
    chunks = []
    start = 0.0
    while start < duration:
        end = min(start + chunk_duration, duration)
        chunks.append({"start": start, "end": end, "duration": end - start})
        start = end
    logger.info(f"Split {duration:.0f}s video into {len(chunks)} chunks")
    return chunks


def get_chunk_transcript(
    transcript: List[Dict[str, Any]],
    chunk_start: float,
    chunk_end: float,
) -> List[Dict[str, Any]]:
    """Filter transcript words that fall within a chunk's time range."""
    return [
        w for w in transcript
        if w.get("start", 0) >= chunk_start and w.get("end", 0) <= chunk_end
    ]


async def analyze_chunk(
    transcript_segment: List[Dict[str, Any]],
    start: float,
    end: float,
) -> Dict[str, Any]:
    """Analyze one chunk for importance and keep/remove segments."""
    client = _get_client()

    transcript_text = json.dumps(transcript_segment, ensure_ascii=False)
    prompt = CHUNK_ANALYSIS_PROMPT.format(
        transcript=transcript_text,
        start=start,
        end=end,
    )

    try:
        kwargs = dict()
        if not _is_local_llm():
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
            **kwargs,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        logger.info(f"Chunk [{start:.0f}-{end:.0f}s]: importance={result.get('importance')}, "
                     f"keep={len(result.get('keep_segments', []))}, "
                     f"remove={len(result.get('remove_segments', []))}")
        return result
    except Exception as e:
        logger.error(f"Chunk analysis error: {e}")
        return {
            "importance": 5,
            "keep_segments": [{"start": start, "end": end, "reason": "fallback"}],
            "remove_segments": [],
            "summary": "Analysis failed, keeping segment as-is.",
            "is_intro": False,
            "is_highlight": False,
            "is_ending": False,
        }


async def build_story(
    chunks: List[Dict[str, Any]],
    target_duration: float,
) -> Dict[str, Any]:
    """
    Given analyzed chunks, build a coherent story that fits within target_duration.
    Returns the assembled story with dropped segments identified.
    """
    client = _get_client()

    current_duration = sum(c.get("duration", c.get("end", 0) - c.get("start", 0)) for c in chunks)

    chunks_json = json.dumps(chunks, indent=2, default=str)
    prompt = STORY_ASSEMBLY_PROMPT.format(
        chunks_json=chunks_json,
        target_duration=target_duration,
        current_duration=current_duration,
    )

    try:
        kwargs = dict()
        if not _is_local_llm():
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3,
            **kwargs,
        )
        raw = response.choices[0].message.content.strip()
        story = json.loads(raw)
        logger.info(f"Story built: {story.get('final_duration', 0):.0f}s, "
                     f"dropped {len(story.get('drop_segments', []))} segments")
        return story
    except Exception as e:
        logger.error(f"Story building error: {e}")
        return _fallback_story(chunks, target_duration)


async def analyze_and_build_story(
    transcript: List[Dict[str, Any]],
    video_duration: float,
    mode: str,
    target_duration: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: chunk → analyze each chunk → build story.
    Returns story structure usable by the edit pipeline.
    Now includes: overlap chunks, story confidence, emotional moment prioritization.
    """
    if mode != "vlog":
        return {"chunks": [], "story": None, "mode": "reels"}

    chunk_size = 180  # 3 minutes
    if target_duration:
        chunk_size = max(60, target_duration / 5)

    overlap_seconds = 7.5  # 5-10s overlap for context continuity
    chunk_ranges = chunk_video_with_overlap(video_duration, chunk_size, overlap_seconds)
    logger.info(f"Analyzing {len(chunk_ranges)} vlog chunks (overlap={overlap_seconds}s)...")

    analyzed_chunks = []
    for i, cr in enumerate(chunk_ranges):
        chunk_transcript = get_chunk_transcript(transcript, cr["start"], cr["end"])
        analysis = await analyze_chunk(chunk_transcript, cr["start"], cr["end"])
        analyzed_chunks.append({
            "index": i,
            "start": cr["start"],
            "end": cr["end"],
            "duration": cr["duration"],
            "overlap_start": cr.get("overlap_start", cr["start"]),
            "importance": analysis.get("importance", 5),
            "summary": analysis.get("summary", ""),
            "keep_segments": analysis.get("keep_segments", [{"start": cr["start"], "end": cr["end"]}]),
            "remove_segments": analysis.get("remove_segments", []),
            "is_intro": analysis.get("is_intro", False),
            "is_highlight": analysis.get("is_highlight", False),
            "is_ending": analysis.get("is_ending", False),
        })

    # Prioritize emotional moments
    analyzed_chunks = _prioritize_emotional_moments(analyzed_chunks)

    # Build global story
    if target_duration:
        story = await build_story(analyzed_chunks, target_duration)
    else:
        story = _simple_assembly(analyzed_chunks)

    # Compute story confidence
    story_confidence = _compute_story_confidence(analyzed_chunks, story)

    # Enforce global narrative
    story = _enforce_narrative(story, analyzed_chunks)

    return {
        "chunks": analyzed_chunks,
        "story": story,
        "story_confidence": story_confidence,
        "mode": "vlog",
    }


def get_segments_from_story(
    story_result: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, float]]:
    """
    Convert story structure into a flat list of (start, end) segments for rendering.
    Drops segments identified as removable by the story builder.
    """
    story = story_result.get("story", {})
    if not story:
        return [{"start": c["start"], "end": c["end"]} for c in chunks]

    segments = []

    # Intro
    intro = story.get("intro", {})
    if intro:
        segments.extend(intro.get("segments", []))

    # Body
    for body_item in story.get("body", []):
        segments.extend(body_item.get("segments", []))

    # Ending
    ending = story.get("ending", {})
    if ending:
        segments.extend(ending.get("segments", []))

    # If no segments parsed, use keep_segments from chunks
    if not segments:
        for c in chunks:
            segments.extend(c.get("keep_segments", [{"start": c["start"], "end": c["end"]}]))

    logger.info(f"Story produced {len(segments)} segments for rendering")
    return segments


def _fallback_story(chunks: List[Dict[str, Any]], target_duration: float) -> Dict[str, Any]:
    """Fallback when GPT story building fails — drop lowest importance chunks."""
    sorted_chunks = sorted(chunks, key=lambda c: c.get("importance", 5))
    current_duration = sum(c["duration"] for c in chunks)
    drop_segments = []

    while current_duration > target_duration and sorted_chunks:
        chunk = sorted_chunks.pop(0)
        drop_segments.append({
            "from_chunk": chunk["index"],
            "start": chunk["start"],
            "end": chunk["end"],
            "reason": f"Low importance ({chunk.get('importance', 5)}/10)",
        })
        current_duration -= chunk["duration"]

    return {
        "drop_segments": drop_segments,
        "final_duration": current_duration,
    }


def _simple_assembly(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simple assembly — keep all keep_segments, no dropping."""
    segments = []
    for c in chunks:
        segments.extend(c.get("keep_segments", []))
    return {
        "body": [{"from_chunk": c["index"], "segments": c.get("keep_segments", [])} for c in chunks],
        "final_duration": sum(s["end"] - s["start"] for s in segments),
        "drop_segments": [],
    }


# ── Chunk Overlap ─────────────────────────────────────────────────────────────

def chunk_video_with_overlap(duration: float, chunk_duration: float = 180,
                              overlap: float = 7.5) -> List[Dict[str, float]]:
    """
    Split video into chunks with overlap for context continuity.
    Each chunk starts `overlap` seconds before the previous chunk ends.
    """
    chunks = []
    start = 0.0
    while start < duration:
        end = min(start + chunk_duration, duration)
        chunks.append({
            "start": start,
            "end": end,
            "duration": end - start,
            "overlap_start": max(start, start),
        })
        start = end - overlap  # Next chunk starts overlap seconds before this one ends
        if start >= duration - overlap:
            break
    logger.info(f"Split {duration:.0f}s video into {len(chunks)} overlapping chunks (overlap={overlap}s)")
    return chunks


# ── Emotional Moment Prioritization ───────────────────────────────────────────

def _prioritize_emotional_moments(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Boost importance of chunks that contain emotional moments.
    Emotional = high importance + has highlights or strong keep segments.
    """
    for chunk in chunks:
        if chunk.get("is_highlight"):
            chunk["importance"] = min(10, chunk.get("importance", 5) + 2)
        if chunk.get("is_intro"):
            chunk["importance"] = min(10, chunk.get("importance", 5) + 1)
        if chunk.get("is_ending"):
            chunk["importance"] = min(10, chunk.get("importance", 5) + 1)
    return chunks


# ── Story Confidence ──────────────────────────────────────────────────────────

def _compute_story_confidence(chunks: List[Dict[str, Any]], story: Dict[str, Any]) -> float:
    """
    Compute a confidence score (0-10) for how good the story is.
    Based on: intro presence, highlight count, importance distribution, narrative flow.
    """
    if not chunks:
        return 5.0

    has_intro = any(c.get("is_intro") for c in chunks)
    has_ending = any(c.get("is_ending") for c in chunks)
    highlight_count = sum(1 for c in chunks if c.get("is_highlight"))
    avg_importance = sum(c.get("importance", 5) for c in chunks) / len(chunks)

    score = 5.0
    if has_intro:
        score += 1.5
    if has_ending:
        score += 1.0
    if highlight_count >= 2:
        score += 1.5
    elif highlight_count >= 1:
        score += 0.5
    if avg_importance >= 7:
        score += 1.0
    elif avg_importance >= 5:
        score += 0.5

    # Penalize if too many low-importance chunks
    low_count = sum(1 for c in chunks if c.get("importance", 5) < 4)
    if low_count > len(chunks) * 0.5:
        score -= 2.0

    # Penalize if story dropped too many segments
    drop_segments = story.get("drop_segments", [])
    if len(drop_segments) > len(chunks) * 0.6:
        score -= 1.5

    return max(0, min(10, round(score, 1)))


# ── Narrative Enforcement ─────────────────────────────────────────────────────

def _enforce_narrative(story: Dict[str, Any], chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure the story has a valid narrative structure: hook → build → climax → resolution.
    If story is missing intro/ending, auto-fill from chunks.
    """
    if not story:
        return story

    # Ensure intro exists
    if not story.get("intro"):
        intro_chunks = [c for c in chunks if c.get("is_intro")]
        if intro_chunks:
            best_intro = max(intro_chunks, key=lambda c: c.get("importance", 5))
            story["intro"] = {
                "from_chunk": best_intro["index"],
                "segments": [{"start": best_intro["start"], "end": best_intro["end"]}],
            }

    # Ensure ending exists
    if not story.get("ending"):
        ending_chunks = [c for c in chunks if c.get("is_ending")]
        if ending_chunks:
            best_ending = max(ending_chunks, key=lambda c: c.get("importance", 5))
            story["ending"] = {
                "from_chunk": best_ending["index"],
                "segments": [{"start": best_ending["start"], "end": best_ending["end"]}],
            }

    # Ensure body has at least one segment
    if not story.get("body"):
        highlight_chunks = [c for c in chunks if c.get("is_highlight") and not c.get("is_intro") and not c.get("is_ending")]
        if highlight_chunks:
            story["body"] = [
                {"from_chunk": c["index"], "segments": c.get("keep_segments", [])}
                for c in highlight_chunks
            ]

    # Add story_flow if missing
    if not story.get("story_flow"):
        intro_label = "intro" if story.get("intro") else "none"
        body_count = len(story.get("body", []))
        ending_label = "ending" if story.get("ending") else "none"
        story["story_flow"] = f"Structure: {intro_label} → {body_count} body segments → {ending_label}"

    return story
