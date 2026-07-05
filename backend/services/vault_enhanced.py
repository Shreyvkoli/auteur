"""
Vault Enhanced — Timestamped clips + auto suggestions + vault-aware editing.

Vault items (memes, sounds, music, presets) can now have:
  - Multiple timestamped clips within a single vault video
  - Auto-suggested placements based on transcript analysis
  - Smart matching between vault content and video segments
"""

import json
import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

from core.database import get_supabase
from services.ffmpeg_service import get_duration

logger = logging.getLogger(__name__)


# ── Timestamped Clips ───────────────────────────────────────────────────────────

def add_vault_clip(
    vault_item_id: str,
    user_id: str,
    start_time: float,
    end_time: float,
    label: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a timestamped clip marker to a vault item."""
    supabase = get_supabase()
    clip_id = str(uuid4())

    clip = {
        "id": clip_id,
        "vault_item_id": vault_item_id,
        "user_id": user_id,
        "start_time": start_time,
        "end_time": end_time,
        "label": label or "untitled",
        "tags": tags or [],
        "duration": end_time - start_time,
    }

    supabase.table("vault_clips").insert(clip).execute()
    logger.info(f"Vault clip added to {vault_item_id}: {start_time:.1f}-{end_time:.1f}s")
    return clip


def get_vault_clips(vault_item_id: str) -> List[Dict[str, Any]]:
    """Get all timestamped clips for a vault item."""
    supabase = get_supabase()
    result = (
        supabase.table("vault_clips")
        .select("*")
        .eq("vault_item_id", vault_item_id)
        .order("start_time")
        .execute()
    )
    return result.data or []


def get_all_user_clips(user_id: str, label: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all timestamped clips across all vault items for a user."""
    supabase = get_supabase()
    query = (
        supabase.table("vault_clips")
        .select("*, vault_items!inner(name, type)")
        .eq("vault_items.user_id", user_id)
    )
    if label:
        query = query.eq("label", label)
    result = query.order("created_at", desc=True).execute()
    return result.data or []


def delete_vault_clip(clip_id: str) -> bool:
    """Delete a timestamped clip marker."""
    supabase = get_supabase()
    supabase.table("vault_clips").delete().eq("id", clip_id).execute()
    return True


# ── Auto Suggestions ────────────────────────────────────────────────────────────

async def suggest_vault_placements(
    transcript: List[Dict[str, Any]],
    vault_items: List[Dict[str, Any]],
    version_type: str,
) -> List[Dict[str, Any]]:
    """
    Suggest where to place vault items in the timeline based on transcript content.
    Uses keyword matching + timing analysis.

    Returns: [{timestamp, item_id, type, reason}, ...]
    """
    suggestions = []

    if not vault_items or not transcript:
        return suggestions

    # Build text from transcript
    full_text = " ".join(w.get("word", "") for w in transcript).lower()
    words = [w for w in full_text.split() if len(w) > 2]

    # Categorize vault items
    memes = [v for v in vault_items if v.get("type") == "meme"]
    sounds = [v for v in vault_items if v.get("type") == "sound"]
    music = [v for v in vault_items if v.get("type") == "music"]

    # ── Sound effect triggers ──────────────────────────────────────────────
    trigger_words = {
        "bruh": ["bruh", "bro", "dude", "seriously"],
        "vine_boom": ["boom", "wow", "damn", "crazy"],
        "air_horn": ["let's go", "yess", "awesome", "killer"],
        "sad_violin": ["sad", "unfortunately", "sorry", "regret"],
        "bonk": ["no", "stop", "wrong", "bonk"],
    }

    for sound_word, triggers in trigger_words.items():
        for trigger in triggers:
            if trigger in full_text:
                # Find the best timestamp for this trigger
                for w in transcript:
                    if trigger in w.get("word", "").lower():
                        suggestions.append({
                            "timestamp": w.get("start", 0),
                            "item_id": None,
                            "type": "sound",
                            "sound": sound_word,
                            "reason": f'"{trigger}" detected',
                        })
                        break

    # ── Meme placement ─────────────────────────────────────────────────────
    if version_type in ("funny", "viral") and memes and len(memes) >= 2:
        # Place memes at natural pause points
        pause_moments = _find_pauses(transcript)
        for pm in pause_moments[:3]:
            suggestions.append({
                "timestamp": pm,
                "item_id": memes[0]["id"] if memes else None,
                "type": "meme",
                "reason": "Pause point — good for meme placement",
            })

    # ── Music selection ────────────────────────────────────────────────────
    if music:
        # Match music to video energy based on transcript sentiment
        from services.gpt_service import _get_client
        try:
            client = _get_client()
            sentiment_prompt = f"""Analyze this transcript for energy level (1-10, where 1=relaxed, 10=high energy):
'{full_text[:500]}'
Return only a number."""
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": sentiment_prompt}],
                max_tokens=10,
                temperature=0,
            )
            energy = int(response.choices[0].message.content.strip())
        except Exception:
            energy = 5

        if energy >= 7:
            suggestions.append({
                "timestamp": 0,
                "type": "music",
                "vibe": "trap",
                "reason": f"High energy content ({energy}/10)",
            })
        elif energy >= 4:
            suggestions.append({
                "timestamp": 0,
                "type": "music",
                "vibe": "lo-fi",
                "reason": f"Medium energy content ({energy}/10)",
            })

    logger.info(f"Generated {len(suggestions)} vault placement suggestions")
    return suggestions


# ── LLM-Powered Vault Relevance Ranking ───────────────────────────────────────

async def rank_vault_by_relevance(
    transcript: str,
    vault_items: List[Dict[str, Any]],
    version_type: str = "viral",
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Use LLM to rank vault items by relevance to the video content.
    Returns ranked list with relevance scores.
    """
    if not vault_items:
        return []

    vault_descriptions = []
    for item in vault_items[:20]:
        clips = item.get("clips", [])
        clip_desc = ""
        if clips:
            clip_desc = f" (clips: {', '.join(c.get('label', '') for c in clips[:3])})"
        vault_descriptions.append(
            f"- {item.get('name', 'unnamed')} [{item.get('type', 'unknown')}]{clip_desc}"
        )

    ranking_prompt = f"""Rank these vault items by relevance to the video transcript.
Version type: {version_type}

Transcript (first 1000 chars):
{transcript[:1000]}

Available vault items:
{chr(10).join(vault_descriptions)}

Return ONLY valid JSON:
{{
  "ranked": [
    {{"name": "<item name>", "relevance": <1-10>, "reason": "<why relevant>"}},
    ...
  ]
}}

Rules:
- relevance 10 = must use, perfectly matches content
- relevance 1 = completely unrelated
- Consider emotional tone, topic, pacing needs
- Return at most {top_k} items"""

    try:
        from services.gpt_service import generate_text
        result_text = await generate_text(ranking_prompt, max_tokens=1000, temperature=0.3)

        clean = result_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]

        ranked = json.loads(clean).get("ranked", [])

        # Merge relevance scores back into vault items
        ranked_map = {r["name"]: r for r in ranked if "name" in r}
        enriched = []
        for item in vault_items:
            name = item.get("name", "")
            ranking = ranked_map.get(name, {})
            item_copy = item.copy()
            item_copy["relevance_score"] = ranking.get("relevance", 5)
            item_copy["relevance_reason"] = ranking.get("reason", "")
            enriched.append(item_copy)

        # Sort by relevance descending
        enriched.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return enriched[:top_k]

    except Exception as e:
        logger.warning(f"LLM vault ranking failed: {e}, returning top {top_k} by default")
        return vault_items[:top_k]


async def suggest_vault_during_planning(
    transcript: str,
    vault_items: List[Dict[str, Any]],
    version_type: str,
) -> List[Dict[str, Any]]:
    """
    Called during edit planning to auto-suggest vault items.
    Combines keyword matching + LLM relevance scoring.
    """
    # First pass: keyword-based suggestions
    transcript_words = transcript.lower().split()

    keyword_suggestions = []
    for item in vault_items:
        name = item.get("name", "").lower()
        item_type = item.get("type", "")

        # Simple keyword matching
        name_words = name.split()
        match_count = sum(1 for w in name_words if w in transcript_words)
        if match_count > 0 or item_type in ("music", "sound"):
            keyword_suggestions.append(item)

    # If too few keyword matches, use LLM ranking
    if len(keyword_suggestions) < 3 and vault_items:
        ranked = await rank_vault_by_relevance(transcript, vault_items, version_type, top_k=5)
        return ranked

    return keyword_suggestions[:5]


def _find_pauses(transcript: List[Dict[str, Any]], min_gap: float = 1.0) -> List[float]:
    """Find moments where there are pauses in speech (good for meme placement)."""
    if not transcript or len(transcript) < 2:
        return []

    pauses = []
    for i in range(1, len(transcript)):
        gap = transcript[i].get("start", 0) - transcript[i - 1].get("end", 0)
        if gap >= min_gap:
            midpoint = (transcript[i - 1].get("end", 0) + transcript[i].get("start", 0)) / 2
            pauses.append(midpoint)

    return pauses


# ── Vault Usage Tracking ────────────────────────────────────────────────────────

def track_vault_usage(user_id: str, vault_item_id: str, job_id: str) -> None:
    """Track when a vault item is used in an edit (for analytics/creator memory)."""
    supabase = get_supabase()

    # Update creator memory vault_usage_freq
    memory = (
        supabase.table("creator_memories")
        .select("vault_usage_freq, edit_count")
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if memory.data:
        freq_map = {"low": 1, "medium": 2, "high": 3}
        current = freq_map.get(memory.data.get("vault_usage_freq", "low"), 1)
        new_freq_code = min(3, current + 0.3)
        rev_map = {1: "low", 2: "medium", 3: "high"}
        supabase.table("creator_memories").update({
            "vault_usage_freq": rev_map.get(round(new_freq_code), "low"),
        }).eq("user_id", user_id).execute()


# ── Auto-Tag Vault Items ────────────────────────────────────────────────────────

async def auto_tag_vault_item(vault_item_id: str, user_id: str) -> None:
    """
    Automatically analyze a vault item (video/audio) and create timestamped clips.
    Uses duration-based segmentation for now.
    """
    supabase = get_supabase()
    item = (
        supabase.table("vault_items")
        .select("*")
        .eq("id", vault_item_id)
        .single()
        .execute()
    )
    if not item.data:
        return

    r2_url = item.data.get("r2_url")
    if not r2_url:
        return

    # For now, create clips at thirds of the duration
    from services.r2 import generate_presigned_download_url
    url = generate_presigned_download_url(r2_url)
    if not url:
        return

    try:
        duration = await get_duration(url)
        if duration > 5:
            # Create 3 segments: intro, highlight, end
            thirds = duration / 3
            labels = ["intro", "highlight", "ending"]
            for i, label in enumerate(labels):
                ct = i * thirds
                add_vault_clip(
                    vault_item_id, user_id,
                    ct, min(ct + thirds, duration),
                    label=label,
                    tags=[label, item.data.get("type", "")],
                )
            logger.info(f"Auto-tagged {vault_item_id}: {len(labels)} clips from {duration:.0f}s")
    except Exception as e:
        logger.warning(f"Auto-tag failed for {vault_item_id}: {e}")
