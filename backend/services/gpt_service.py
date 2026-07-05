"""
GPT Service — GPT-4o Vision for style analysis + edit plan generation + refinement.
In DEV_MODE, returns intelligent mock responses without calling OpenAI API.
"""

import json
import base64
import logging
from typing import List, Dict, Any, Optional
from core.config import settings

logger = logging.getLogger(__name__)

DEV_MODE = settings.dev_mode or not settings.openai_configured

_client = None


def _is_local_llm():
    """Detect if using a local LLM (Ollama, LM Studio, etc.) which lacks some OpenAI features."""
    base = settings.openai_base_url or ""
    return "localhost" in base or "127.0.0.1" in base

def _model():
    """Return the model name to use. Defaults to gpt-4o for OpenAI, or settings override for local."""
    return settings.openai_model


def _get_client():
    if DEV_MODE:
        return None
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        _client = AsyncOpenAI(**kwargs)
    return _client


async def generate_text(prompt: str, max_tokens: int = 1500, temperature: float = 0.7) -> str:
    """Simple text generation helper used by edit intelligence and other services."""
    if DEV_MODE:
        logger.info(f"[DEV] generate_text called (mock)")
        return "This is a dev mode mock response. The edit plan has been generated using intelligent fallback logic."
    client = _get_client()
    response = await client.chat.completions.create(
        model=_model(),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _encode_image(image_path: str) -> str:
    """Base64 encode an image for GPT-4o Vision."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── 1. Style Analysis from Frames ────────────────────────────────────────────

STYLE_ANALYSIS_PROMPT = """Analyse these frames from a short-form video (Instagram Reels/YouTube Shorts style).
Return ONLY valid JSON — no markdown, no explanation:
{
  "cut_speed_seconds": <float, avg seconds between cuts>,
  "caption_style": {
    "font": <string>,
    "color": <string, e.g. "yellow", "white">,
    "position": <"center" | "top" | "bottom">,
    "size": <"small" | "medium" | "large">,
    "animated": <boolean>
  },
  "energy_level": <int 1-10>,
  "hook_pattern": <string, e.g. "question hook", "shock value", "story tease">,
  "transition_type": <string, e.g. "hard cut", "zoom transition", "fade">,
  "music_vibe": <string, e.g. "lo-fi", "trap", "cinematic", "no music">,
  "blur_background": <boolean>,
  "meme_frequency": <"none" | "low" | "medium" | "high">,
  "color_grade": <"warm" | "cool" | "cinematic" | "vibrant" | "matte" | "none">
}"""


def _mock_style_analysis() -> Dict[str, Any]:
    return {
        "cut_speed_seconds": 2.5,
        "caption_style": {"font": "Impact", "color": "white", "position": "center", "size": "large", "animated": True},
        "energy_level": 8,
        "hook_pattern": "question hook",
        "transition_type": "hard cut",
        "music_vibe": "trap",
        "blur_background": False,
        "meme_frequency": "medium",
        "color_grade": "vibrant",
    }


def _mock_edit_plan(transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    last_end = transcript[-1]["end"] if transcript else 30.0
    mid = last_end / 2
    hook_start = 0.0
    hook_end = min(3.0, last_end)
    cuts = [
        {"start": hook_start, "end": hook_end},
        {"start": mid - 2, "end": mid + 3},
        {"start": last_end - 5, "end": last_end},
    ]
    captions = []
    for i, chunk in enumerate(transcript[:5]):
        if isinstance(chunk, dict) and "start" in chunk:
            captions.append({
                "start": chunk["start"],
                "end": chunk["end"],
                "text": chunk.get("word", "mock"),
                "style": "bold_white_center",
            })
    return {
        "hook": {"start": hook_start, "end": hook_end},
        "cuts": cuts,
        "captions": captions or [
            {"start": 0.0, "end": 3.0, "text": "Mock caption", "style": "bold_white_center"}
        ],
        "zoom_moments": [{"timestamp": hook_end, "scale": 1.3, "duration": 2.0}],
        "meme_sounds": [{"timestamp": hook_end, "sound": "vine_boom"}],
        "vault_placements": [],
        "music_vibe": "trap",
        "blur_background": False,
        "color_grade": "vibrant",
        "total_duration": int(last_end),
    }


def _mock_critique(cuts_count: int) -> Dict[str, Any]:
    import random
    scores = {str(i): random.randint(6, 9) for i in range(cuts_count)}
    avg = sum(scores.values()) / len(scores) if scores else 7.0
    return {
        "cut_scores": scores,
        "overall_score": round(avg, 1),
        "weaknesses": ["mock weakness for testing"],
        "strengths": ["mock strength for testing"],
        "suggestions": ["Add more dynamic cuts", "Improve hook timing"],
    }


async def analyze_style_from_frames(frame_paths: List[str]) -> Dict[str, Any]:
    """
    Send top 20 frames to GPT-4o Vision and extract style profile JSON.
    frame_paths: list of local image file paths.
    """
    if DEV_MODE:
        logger.info(f"[DEV] analyze_style_from_frames called with {len(frame_paths)} frames (mock)")
        return _mock_style_analysis()

    client = _get_client()

    # Build vision message content
    content = [{"type": "text", "text": STYLE_ANALYSIS_PROMPT}]

    for path in frame_paths[:20]:
        img_b64 = _encode_image(path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}",
                "detail": "low",  # Saves tokens
            },
        })

    logger.info(f"Analyzing style from {len(frame_paths)} frames via GPT-4o Vision")

    response = await client.chat.completions.create(
    model=_model(),
            messages=[{"role": "user", "content": content}],
            max_tokens=500,
            temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown if model wraps in ```json
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    style_json = json.loads(raw)
    logger.info(f"Style profile extracted: energy={style_json.get('energy_level')}, vibe={style_json.get('music_vibe')}")
    return style_json


# ── 2. Edit Plan Generation ───────────────────────────────────────────────────

VERSION_SYSTEM_PROMPTS = {
    "funny": """You are an expert short-form video editor specialising in COMEDY content.
Focus on: comedic timing, funny pauses, meme moments, unexpected cuts, reaction-worthy clips.
Hook should surprise or confuse in the first 3 seconds.
Use meme sounds frequently. Keep energy high and unpredictable.""",

    "viral": """You are an expert short-form video editor specialising in VIRAL content.
Focus on: strong hook in FIRST 3 SECONDS, high retention editing, trending transitions.
Open with the most shocking/interesting moment. Keep cuts fast. 
Every 5 seconds must give the viewer a reason to keep watching.
Caption every key statement.""",

    "serious": """You are an expert short-form video editor specialising in VALUE/EDUCATIONAL content.
Focus on: clear storytelling, professional pacing, value delivery.
Open with a clear promise of what viewer will learn/gain.
Use clean cuts, readable captions, no meme sounds.
Build to a satisfying conclusion.""",
}

EDIT_PLAN_PROMPT_TEMPLATE = """
Creator's video transcript (word-level timestamps):
{transcript}

Creator's prompt: "{prompt}"

Reference video style profile:
{style_profile}

Vault items available (creator's saved assets):
{vault_items}

Create an edit plan for a {version_type} version. 
Return ONLY valid JSON — no markdown, no explanation:
{{
  "hook": {{"start": <float>, "end": <float>}},
  "cuts": [
    {{"start": <float>, "end": <float>}}
  ],
  "captions": [
    {{
      "start": <float>,
      "end": <float>,
      "text": "<string>",
      "style": "<bold_yellow_center | bold_white_center | bold_white_top>"
    }}
  ],
  "zoom_moments": [
    {{"timestamp": <float>, "scale": <float 1.1-1.5>, "duration": <float>}}
  ],
  "meme_sounds": [
    {{"timestamp": <float>, "sound": "<bruh|vine_boom|air_horn|sad_violin|bonk>"}}
  ],
  "vault_placements": [
    {{"timestamp": <float>, "item_id": "<string>"}}
  ],
  "music_vibe": "<lo-fi|trap|cinematic|no music>",
  "blur_background": <boolean>,
  "color_grade": "<warm|cool|cinematic|vibrant|matte|none>",
  "total_duration": <int seconds>
}}

Rules:
- cuts must start from the hook
- total_duration should be 15-90 seconds
- captions for every important statement
- hook.start must be the most engaging moment in the transcript
"""


async def generate_edit_plan(
    transcript: List[Dict[str, Any]],
    prompt: str,
    style_profile: Optional[Dict[str, Any]],
    version_type: str,
    vault_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Generate a complete edit plan JSON using GPT-4o.
    Returns the edit plan dict.
    """
    if DEV_MODE:
        logger.info(f"[DEV] generate_edit_plan called for version='{version_type}' (mock)")
        return _mock_edit_plan(transcript)

    client = _get_client()

    system_prompt = VERSION_SYSTEM_PROMPTS.get(version_type, VERSION_SYSTEM_PROMPTS["viral"])

    user_prompt = EDIT_PLAN_PROMPT_TEMPLATE.format(
        transcript=json.dumps(transcript, ensure_ascii=False),
        prompt=prompt,
        style_profile=json.dumps(style_profile or {}, ensure_ascii=False),
        vault_items=json.dumps(vault_items or [], ensure_ascii=False),
        version_type=version_type,
    )

    logger.info(f"Generating edit plan for version='{version_type}'")

    response = await client.chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1500,
        temperature=0.7,
        **(dict() if _is_local_llm() else {"response_format": {"type": "json_object"}}),
    )

    raw = response.choices[0].message.content.strip()
    plan = json.loads(raw)
    logger.info(f"Edit plan generated: {len(plan.get('cuts', []))} cuts, {len(plan.get('captions', []))} captions")
    return plan


# ── 3. Refinement ────────────────────────────────────────────────────────────

REFINE_PROMPT_TEMPLATE = """
Original edit plan:
{original_plan}

Creator's refinement request: "{refinement}"

Return ONLY the CHANGED parts of the edit plan as valid JSON.
Only include keys that need to change — do not repeat unchanged parts.
Example response: {{"meme_sounds": [...], "captions": [...]}}
"""


async def refine_edit_plan(
    original_plan: Dict[str, Any],
    refinement_prompt: str,
) -> Dict[str, Any]:
    """
    Given an original edit plan + refinement prompt,
    return only the changed parts (partial plan).
    """
    if DEV_MODE:
        logger.info(f"[DEV] refine_edit_plan called: '{refinement_prompt[:50]}' (mock)")
        return {"meme_sounds": [{"timestamp": 5.0, "sound": "bonk"}]}



    client = _get_client()

    prompt = REFINE_PROMPT_TEMPLATE.format(
        original_plan=json.dumps(original_plan, ensure_ascii=False, indent=2),
        refinement=refinement_prompt,
    )

    logger.info(f"Refining edit plan: '{refinement_prompt[:80]}'")

    response = await client.chat.completions.create(
        model=_model(),
        messages=[
            {
                "role": "system",
                "content": "You are a video editing assistant. Return only the minimal JSON changes needed.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.5,
        **(dict() if _is_local_llm() else {"response_format": {"type": "json_object"}}),
    )

    raw = response.choices[0].message.content.strip()
    changes = json.loads(raw)
    logger.info(f"Refinement returned {len(changes)} changed keys")
    return changes


def merge_edit_plan(original: Dict[str, Any], changes: Dict[str, Any]) -> Dict[str, Any]:
    """Merge partial changes into original edit plan."""
    merged = original.copy()
    merged.update(changes)
    return merged


# ── Self-Critique Prompt ─────────────────────────────────────────────────────

SELF_CRITIQUE_PROMPT = """You are a harsh video editing critic. Review this edit plan and identify weaknesses.

Edit plan:
{edit_plan}

Transcript context:
{transcript_context}

Rate each cut 1-10 and list specific weaknesses. Be brutally honest.

Return ONLY valid JSON:
{{
  "cut_scores": {{"0": 8, "1": 5}},
  "overall_score": 6.5,
  "weaknesses": [
    "cut at 5.0s is too slow, viewer will drop",
    "missing visual variety in middle section"
  ],
  "strengths": [
    "strong hook opening",
    "good pacing in first 10 seconds"
  ],
  "suggestions": [
    "add zoom effect at 8.5s to boost engagement",
    "remove dead air at 12.0s"
  ]
}}"""


async def self_critique_edit_plan(
    edit_plan: Dict[str, Any],
    transcript_context: str = "",
) -> Dict[str, Any]:
    """
    Self-critique: LLM evaluates its own edit plan.
    Returns scores and improvement suggestions.
    """
    if DEV_MODE:
        logger.info(f"[DEV] self_critique_edit_plan called (mock)")
        cuts = edit_plan.get("cuts", [])
        return _mock_critique(len(cuts))

    client = _get_client()

    prompt = SELF_CRITIQUE_PROMPT.format(
        edit_plan=json.dumps(edit_plan, indent=2, ensure_ascii=False)[:3000],
        transcript_context=transcript_context[:1000],
    )

    try:
        response = await client.chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": "You are a video editing critic. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.4,
            **(dict() if _is_local_llm() else {"response_format": {"type": "json_object"}}),
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Self-critique failed: {e}")
        return {
            "cut_scores": {},
            "overall_score": 6.0,
            "weaknesses": [],
            "strengths": [],
            "suggestions": [],
        }


# ── Selective Regeneration Prompt ─────────────────────────────────────────────

SELECTIVE_REGEN_PROMPT = """Improve ONLY the weak parts of this edit plan. Keep all strong parts unchanged.

Original plan:
{original_plan}

Weak cuts (score < 7):
{weak_cuts}

Suggestions for improvement:
{suggestions}

Return ONLY the improved cuts as JSON. Same structure, better quality:
{{
  "improved_cuts": [
    {{"start": <float>, "end": <float>}}
  ],
  "improved_captions": [
    {{"start": <float>, "end": <float>, "text": "<string>", "style": "<string>"}}
  ],
  "improved_zoom_moments": [
    {{"timestamp": <float>, "scale": <float>, "duration": <float>}}
  ]
}}"""


async def selective_regen_edit_plan(
    edit_plan: Dict[str, Any],
    critique: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Selective regeneration: only regenerate weak parts based on critique.
    Returns improved plan.
    """
    if DEV_MODE:
        logger.info(f"[DEV] selective_regen_edit_plan called (mock, returning original)")
        return edit_plan

    client = _get_client()

    # Identify weak cuts
    cut_scores = critique.get("cut_scores", {})
    weak_cuts = []
    cuts = edit_plan.get("cuts", [])
    for i, cut in enumerate(cuts):
        score = cut_scores.get(str(i), 7)
        if score < 7:
            weak_cuts.append({"index": i, "score": score, **cut})

    suggestions = critique.get("suggestions", [])

    prompt = SELECTIVE_REGEN_PROMPT.format(
        original_plan=json.dumps(edit_plan, indent=2, ensure_ascii=False)[:2500],
        weak_cuts=json.dumps(weak_cuts, indent=2),
        suggestions=json.dumps(suggestions),
    )

    try:
        response = await client.chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": "You are a video editing assistant. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.6,
            **(dict() if _is_local_llm() else {"response_format": {"type": "json_object"}}),
        )
        raw = response.choices[0].message.content.strip()
        improvements = json.loads(raw)

        # Merge improvements into plan
        merged = edit_plan.copy()
        if "improved_cuts" in improvements:
            for i, cut in enumerate(improvements["improved_cuts"]):
                idx = weak_cuts[i]["index"] if i < len(weak_cuts) else len(merged.get("cuts", []))
                if idx < len(merged.get("cuts", [])):
                    merged["cuts"][idx] = cut
        if "improved_captions" in improvements:
            merged["captions"] = improvements["improved_captions"]
        if "improved_zoom_moments" in improvements:
            merged["zoom_moments"] = improvements["improved_zoom_moments"]

        return merged
    except Exception as e:
        logger.warning(f"Selective regen failed: {e}")
        return edit_plan
