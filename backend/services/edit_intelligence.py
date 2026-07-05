"""
Edit Intelligence Layer — Multi-pass edit plan generation.
Pass 1: Generate edit plan from transcript + creator memory
Pass 2: Self-critique (LLM evaluates its own plan)
Pass 3: Improve (regenerate weak parts only)
Pass 4: Lock final plan
"""

import json
import time
from typing import Optional, Dict, Any, List
from services.gpt_service import generate_text
from services.creator_memory import get_or_create_memory
from services.edit_quality import evaluate_edit_plan
from core.database import get_supabase


async def generate_edit_plan(transcript: str, style: str = "funny", user_id: Optional[str] = None,
                             vault_context: str = "", project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Multi-pass edit plan generation with self-critique.
    Returns enhanced edit plan with story confidence score.
    """
    start_time = time.time()

    # Get creator memory context
    memory_context = ""
    if user_id:
        profile = get_or_create_memory(user_id)
        if profile:
            memory_context = (
                f"User's past editing style:\n"
                f"- Preferred pacing: {profile.get('preferred_pacing', 'medium')}\n"
                f"- Preferred captions: {profile.get('caption_style', 'moderate')}\n"
                f"- Preferred filters: {profile.get('color_grade', 'none')}\n"
                f"- Average retention: {profile.get('avg_cut_duration', 3.0)}\n"
            )

    vault_section = ""
    if vault_context:
        vault_section = f"\n\nVault media suggestions:\n{vault_context}"

    # PASS 1: Generate initial edit plan
    generation_prompt = f"""You are an expert video editor creating a detailed edit plan for a {style} video.

Transcript:
{transcript[:3000]}
{memory_context}{vault_section}

Create a detailed edit plan in JSON format:
{{
  "style": "{style}",
  "segments": [
    {{
      "id": 1,
      "text": "exact transcript text for this segment",
      "start_time": 0.0,
      "end_time": 5.0,
      "action": "keep",
      "speed": 1.0,
      "caption": true,
      "caption_text": "text for caption if needed",
      "transition": "cut",
      "effect": "none",
      "broll_description": "description if broll needed",
      "music_cue": "background music suggestion"
    }}
  ],
  "hooks": ["opening hook description"],
  "pacing_notes": "overall pacing strategy",
  "engagement_targets": ["moments to boost engagement"],
  "overall_score_estimate": 7.5
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no code blocks. Every segment must have a text field.

Rules for {style} style:
- Funny: Quick cuts, speed ramps on punchlines, zoom effects, meme captions
- Viral: Strong hook first 3s, trending sounds, text overlays, cliffhangers
- Professional: Smooth transitions, clean cuts, lower thirds, subtle effects

Focus on retention: keep the best moments, remove dead air, maintain energy.
Include b-roll suggestions for visual variety.
Add music cues for emotional beats."""

    plan_text = await generate_text(generation_prompt, max_tokens=3000, temperature=0.7)

    # Parse plan
    try:
        clean = plan_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        plan = json.loads(clean)
    except json.JSONDecodeError:
        plan = {
            "style": style,
            "segments": [
                {
                    "id": 1,
                    "text": transcript[:500],
                    "start_time": 0.0,
                    "end_time": min(len(transcript) * 0.1, 30.0),
                    "action": "keep",
                    "speed": 1.0,
                    "caption": True,
                    "caption_text": "",
                    "transition": "cut",
                    "effect": "none",
                }
            ],
            "hooks": [],
            "pacing_notes": "default pacing",
            "engagement_targets": [],
            "overall_score_estimate": 6.0,
        }

    # PASS 2: Self-critique
    critique_prompt = f"""You are a senior video editor reviewing an edit plan. Rate each segment 1-10 and list weaknesses.

Edit plan:
{json.dumps(plan, indent=2)[:2500]}

Transcript context:
{transcript[:1000]}

Provide a JSON critique:
{{
  "segment_scores": {{
    "1": 8,
    "2": 5
  }},
  "weaknesses": [
    "segment X has weak hook",
    "missing engagement moment"
  ],
  "strengths": [
    "good pacing",
    "strong visual variety"
  ],
  "overall_confidence": 6.5,
  "improvement_suggestions": [
    "add zoom effect at timestamp Y"
  ]
}}

Return ONLY valid JSON."""

    critique_text = await generate_text(critique_prompt, max_tokens=2000, temperature=0.5)

    try:
        clean = critique_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        critique = json.loads(clean)
    except json.JSONDecodeError:
        critique = {
            "segment_scores": {},
            "weaknesses": [],
            "strengths": [],
            "overall_confidence": 6.0,
            "improvement_suggestions": [],
        }

    # PASS 3: Improve weak segments
    weak_segments = []
    segment_scores = critique.get("segment_scores", {})
    for seg in plan.get("segments", []):
        seg_id = str(seg.get("id", ""))
        score = segment_scores.get(seg_id, 7)
        if score < 7:
            weak_segments.append(seg)

    if weak_segments:
        improvement_prompt = f"""Improve these weak segments in the edit plan:
{json.dumps(weak_segments, indent=2)[:1500]}

Context from critique:
- Weaknesses: {json.dumps(critique.get('weaknesses', []))}
- Suggestions: {json.dumps(critique.get('improvement_suggestions', []))}

Return improved segments as JSON array. Each segment must have the same structure but with:
- Better action/effect choices
- Improved timing
- Stronger engagement elements
- Keep the same id numbers

Return ONLY the improved segments array."""

        improved_text = await generate_text(improvement_prompt, max_tokens=2000, temperature=0.6)

        try:
            clean = improved_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            improved_segments = json.loads(clean)
            if isinstance(improved_segments, list):
                improved_map = {s["id"]: s for s in improved_segments if "id" in s}
                plan["segments"] = [
                    improved_map.get(seg["id"], seg)
                    for seg in plan.get("segments", [])
                ]
        except json.JSONDecodeError:
            pass  # Keep original segments if improvement fails

    # PASS 4: Lock and compute final scores
    cuts = plan.get("cuts", [])
    segments = plan.get("segments", [])
    total_cuts = len(cuts) if cuts else len(segments)
    total_duration = sum(
        (c.get("end", 0) - c.get("start", 0)) if "start" in c else (s.get("end_time", 0) - s.get("start_time", 0))
        for c in (cuts or []) for s in (segments or [])
    ) if cuts or segments else 0

    final_scores = {
        "hook_strength": min(10, max(1, 7 + (1 if plan.get("hook") else 0))),
        "pacing_score": min(10, max(1, int(8 - total_cuts / 10) if total_cuts > 0 else 5)),
        "engagement_score": min(10, max(1, 6 + len(plan.get("zoom_moments", [])))),
    }

    elapsed = time.time() - start_time

    result = {
        "plan": plan,
        "critique": critique,
        "quality_scores": final_scores,
        "story_confidence": critique.get("overall_confidence", 6.0),
        "passes_completed": 4,
        "elapsed_seconds": round(elapsed, 2),
        "segments_total": len(plan.get("segments", [])),
    }

    # Store intelligence metrics
    if project_id:
        try:
            db = get_supabase()
            db.table("edit_intelligence_metrics").insert({
                "project_id": project_id,
                "user_id": user_id,
                "passes_completed": 4,
                "story_confidence": result["story_confidence"],
                "quality_scores": json.dumps(final_scores),
                "elapsed_seconds": result["elapsed_seconds"],
            }).execute()
        except Exception:
            pass

    return result


async def self_critique_plan(plan: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    """Run self-critique on an existing plan. Returns critique dict."""
    critique_prompt = f"""Review this video edit plan critically. Be harsh — what would a viewer complain about?

Plan:
{json.dumps(plan, indent=2)[:2500]}

Transcript:
{transcript[:1000]}

Return JSON:
{{
  "segment_scores": {{"1": 8, "2": 5}},
  "weaknesses": ["list issues"],
  "strengths": ["list good parts"],
  "overall_confidence": 6.0,
  "improvement_suggestions": ["specific fixes"]
}}

Return ONLY valid JSON."""

    critique_text = await generate_text(critique_prompt, max_tokens=2000, temperature=0.5)

    try:
        clean = critique_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return json.loads(clean)
    except json.JSONDecodeError:
        return {
            "segment_scores": {},
            "weaknesses": [],
            "strengths": [],
            "overall_confidence": 6.0,
            "improvement_suggestions": [],
        }


async def improve_weak_segments(plan: Dict[str, Any], critique: Dict[str, Any]) -> Dict[str, Any]:
    """Regenerate only weak segments based on critique."""
    weak_segments = []
    segment_scores = critique.get("segment_scores", {})
    for seg in plan.get("segments", []):
        seg_id = str(seg.get("id", ""))
        score = segment_scores.get(seg_id, 7)
        if score < 7:
            weak_segments.append(seg)

    if not weak_segments:
        return plan

    improvement_prompt = f"""Improve these weak video segments:
{json.dumps(weak_segments, indent=2)[:1500]}

Weaknesses: {json.dumps(critique.get('weaknesses', []))}
Suggestions: {json.dumps(critique.get('improvement_suggestions', []))}

Return improved segments as JSON array with same structure. Only valid JSON."""

    improved_text = await generate_text(improvement_prompt, max_tokens=2000, temperature=0.6)

    try:
        clean = improved_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        improved_segments = json.loads(clean)
        if isinstance(improved_segments, list):
            improved_map = {s["id"]: s for s in improved_segments if "id" in s}
            plan["segments"] = [
                improved_map.get(seg["id"], seg)
                for seg in plan.get("segments", [])
            ]
    except json.JSONDecodeError:
        pass

    return plan
