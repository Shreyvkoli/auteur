"""
Edit Quality Engine — Evaluate edit plans before rendering.

Scores:
  - hook_strength (1-10): Does the hook grab attention in first 3s?
  - pacing_score (1-10): Is the rhythm right for the mode?
  - engagement_score (1-10): Will viewer stay till end?

If overall_score < threshold → regenerate plan with feedback.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from core.database import get_supabase
from core.config import settings

logger = logging.getLogger(__name__)

QUALITY_THRESHOLD = settings.quality_threshold


def evaluate_edit_plan(
    edit_plan: Dict[str, Any],
    transcript: List[Dict[str, Any]],
    mode: str = "reels",
    version_type: str = "viral",
) -> Dict[str, Any]:
    """
    Rule-based evaluation of an edit plan's quality.
    Returns scores + details + pass/fail.
    """
    cuts = edit_plan.get("cuts", [])
    captions = edit_plan.get("captions", [])
    hook = edit_plan.get("hook", {})
    total_duration = edit_plan.get("total_duration", 0)
    zoom_moments = edit_plan.get("zoom_moments", [])
    meme_sounds = edit_plan.get("meme_sounds", [])

    # ── Hook Strength ──────────────────────────────────────────────────────
    hook_strength = 5
    hook_details = []

    if hook:
        hook_duration = hook.get("end", 0) - hook.get("start", 0)
        if hook_duration > 0:
            hook_strength = 7
            hook_details.append("Hook exists")
            if hook_duration <= 5:
                hook_strength += 1
                hook_details.append("Hook is short (<5s)")
            if hook_duration <= 3:
                hook_strength += 1
                hook_details.append("Hook is very short (<3s)")
    else:
        hook_details.append("No explicit hook")

    # Check if first cut starts near beginning for reels
    if mode == "reels" and cuts:
        first_cut = cuts[0]
        if first_cut.get("start", 0) > 15:
            hook_strength -= 1
            hook_details.append("Hook starts too late")

    hook_strength = max(1, min(10, hook_strength))

    # ── Pacing Score ───────────────────────────────────────────────────────
    pacing_score = 5
    pacing_details = []

    if mode == "reels":
        # Reels need fast pacing: 15-60s, frequent cuts
        if 15 <= total_duration <= 90:
            pacing_score += 1
            pacing_details.append(f"Good reel duration ({total_duration}s)")
        elif total_duration < 15:
            pacing_details.append("Very short reel")
        else:
            pacing_score -= 1
            pacing_details.append("Too long for reel")

        # Check cut frequency
        if cuts:
            avg_cut = total_duration / len(cuts) if len(cuts) > 0 else total_duration
            if avg_cut < 5:
                pacing_score += 2
                pacing_details.append(f"Fast cuts (avg {avg_cut:.1f}s)")
            elif avg_cut < 10:
                pacing_score += 1
                pacing_details.append(f"Medium pacing (avg {avg_cut:.1f}s)")
            else:
                pacing_score -= 1
                pacing_details.append(f"Slow cuts (avg {avg_cut:.1f}s)")

    elif mode == "vlog":
        # Vlogs need breathing room
        if total_duration > 60:
            pacing_score += 1
            pacing_details.append(f"Good vlog duration ({total_duration}s)")
        if cuts:
            avg_cut = total_duration / len(cuts) if len(cuts) > 0 else total_duration
            if 10 <= avg_cut <= 60:
                pacing_score += 1
                pacing_details.append(f"Good vlog pacing (avg {avg_cut:.1f}s)")

    # Check zoom variety
    if zoom_moments:
        pacing_score += 1
        pacing_details.append("Has zoom effects")

    pacing_score = max(1, min(10, pacing_score))

    # ── Engagement Score ───────────────────────────────────────────────────
    engagement_score = 5
    engagement_details = []

    # Caption coverage
    if captions:
        caption_coverage = len(captions) / max(1, total_duration / 3)
        if caption_coverage > 0.3:
            engagement_score += 1
            engagement_details.append("Good caption density")
        if len(captions) > 5:
            engagement_score += 1
            engagement_details.append("Many captions throughout")

    # Meme sounds for funny/viral
    if version_type in ("funny", "viral") and meme_sounds:
        engagement_score += 1
        engagement_details.append(f"Has {len(meme_sounds)} meme sound(s)")

    # Has color grade
    if edit_plan.get("color_grade") and edit_plan["color_grade"] != "none":
        engagement_score += 1
        engagement_details.append("Has color grading")

    # Has background music
    music = edit_plan.get("music_vibe", "")
    if music and music.lower() not in ("no music", "no_music", ""):
        engagement_score += 1
        engagement_details.append("Has background music")

    # Vault usage
    if edit_plan.get("vault_placements"):
        engagement_score += 1
        engagement_details.append("Uses vault assets")

    engagement_score = max(1, min(10, engagement_score))

    # ── Overall ────────────────────────────────────────────────────────────
    weights = {"hook": 0.35, "pacing": 0.35, "engagement": 0.30}
    overall = (
        hook_strength * weights["hook"]
        + pacing_score * weights["pacing"]
        + engagement_score * weights["engagement"]
    )
    passed = overall >= QUALITY_THRESHOLD

    evaluation_text = _generate_evaluation(
        hook_strength, pacing_score, engagement_score,
        hook_details, pacing_details, engagement_details,
        version_type, mode,
    )

    result = {
        "hook_strength": hook_strength,
        "pacing_score": pacing_score,
        "engagement_score": engagement_score,
        "overall_score": round(overall, 1),
        "passed": passed,
        "details": {
            "hook": hook_details,
            "pacing": pacing_details,
            "engagement": engagement_details,
            "weights": weights,
        },
        "evaluation": evaluation_text,
    }

    logger.info(
        f"Quality: hook={hook_strength}/10 pacing={pacing_score}/10 "
        f"engagement={engagement_score}/10 overall={overall:.1f} {'PASS' if passed else 'FAIL'}"
    )
    return result


def save_quality_score(job_id: str, user_id: str, scores: Dict[str, Any]) -> None:
    """Persist quality evaluation to DB."""
    supabase = get_supabase()
    supabase.table("edit_quality_scores").insert({
        "id": str(uuid4()),
        "job_id": job_id,
        "user_id": user_id,
        "hook_strength": scores["hook_strength"],
        "pacing_score": scores["pacing_score"],
        "engagement_score": scores["engagement_score"],
        "overall_score": scores["overall_score"],
        "passed": scores["passed"],
        "details": scores.get("details", {}),
    }).execute()


def build_regeneration_feedback(scores: Dict[str, Any]) -> str:
    """Build a feedback string for GPT to improve the edit plan."""
    feedback_parts = []
    if scores["hook_strength"] < 6:
        feedback_parts.append("Make the hook stronger — grab attention in the first 3 seconds with the most engaging moment.")
    if scores["pacing_score"] < 6:
        feedback_parts.append("Improve pacing — use faster cuts and keep total duration shorter for better retention.")
    if scores["engagement_score"] < 6:
        feedback_parts.append("Add more engagement elements: captions on every important line, background music, and color grading.")
    if not feedback_parts:
        feedback_parts.append("Slightly improve overall flow and viewer retention.")
    return " ".join(feedback_parts)


def _generate_evaluation(
    hook: int, pacing: int, engagement: int,
    hook_d: List[str], pacing_d: List[str], engagement_d: List[str],
    version_type: str, mode: str,
) -> str:
    """Generate a human-readable evaluation summary."""
    parts = [f"Edit quality evaluation for {version_type} {mode}:"]

    if hook >= 8:
        parts.append("✅ Strong hook — viewers will stay.")
    elif hook >= 6:
        parts.append("👍 Acceptable hook.")
    else:
        parts.append("⚠️ Weak hook — needs improvement.")

    if pacing >= 8:
        parts.append("✅ Excellent pacing.")
    elif pacing >= 6:
        parts.append("👍 Good pacing.")
    else:
        parts.append("⚠️ Pacing needs work.")

    if engagement >= 8:
        parts.append("✅ High engagement potential.")
    elif engagement >= 6:
        parts.append("👍 Reasonable engagement.")
    else:
        parts.append("⚠️ Low engagement — add more interactive elements.")

    return " ".join(parts)
