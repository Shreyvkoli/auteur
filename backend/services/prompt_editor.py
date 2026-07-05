"""
Prompt Editor — Natural Language → Edit State Patches.

User types:
  "0:15 pe zoom hatao aur caption yellow karo"

Flow:
  1. Fetch current edit_state
  2. Send to LLM with prompt + state context
  3. LLM returns structured PATCH JSON
  4. Apply patches to edit_state
  5. Mark dirty segments for re-render

This is the "Cursor-style" editing interface.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

from openai import AsyncOpenAI
from core.config import settings
from core.database import get_supabase
from services.edit_state import (
    get_edit_state, save_edit_state, _new_caption_id, _new_track_id,
    _mark_dirty, action_duplicate, action_speed_change, action_reverse,
    action_freeze_frame, action_crop, action_rotate, action_opacity,
)

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


PROMPT_EDIT_SYSTEM_PROMPT = """You are a friendly video editing assistant. You receive:
1. The current edit_state JSON (timeline, clips, captions, audio, effects, overlays, keyframes)
2. The timeline context summary
3. Video analysis data (scene changes, silences, energy, transcript, highlights, tone) — USE THIS
4. A user's natural language edit request

RESPONSE FORMAT: Always return valid JSON:
{
  "patches": [...],
  "message": "Your conversational reply to the user"
}

- If the user is just chatting, greeting, or asking a question: return "patches": [] and a friendly "message"
- If the user gives an editing command, return the patches AND a message describing what you did

Available patch types (only for edit commands):

1. {"type": "trim", "clip_id": "...", "start": <float>, "end": <float>}
   - Trim a clip to new start/end times in SOURCE time

2. {"type": "split", "clip_id": "...", "at": <float>}
   - Split a clip at a source timestamp

3. {"type": "delete", "clip_id": "..."}
   - Delete a clip from timeline

4. {"type": "move", "clip_id": "...", "new_position": <int>}
   - Reorder clip in timeline (0-based index)

5. {"type": "duplicate", "clip_id": "...", "count": <int>}
   - Duplicate a clip N times

6. {"type": "speed_change", "clip_id": "...", "speed": <float>}
   - Change clip speed (0.1 to 10.0)

7. {"type": "reverse", "clip_id": "..."}
   - Reverse clip playback

8. {"type": "freeze_frame", "clip_id": "...", "at": <float>, "duration": <float>}
   - Insert a freeze frame

9. {"type": "crop", "clip_id": "...", "x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
   - Crop clip (normalized 0-1)

10. {"type": "rotate", "clip_id": "...", "degrees": <float>}
    - Rotate clip

11. {"type": "opacity", "clip_id": "...", "opacity": <float>}
    - Set clip opacity (0-1)

12. {"type": "update_caption", "caption_id": "...", "text": "...", "style": "..."}
    - Edit a caption (only include changed fields)
    - If user specifies a timestamp but no caption_id, create a new caption:
      {"type": "add_caption", "start": <float>, "end": <float>, "text": "...", "style": "..."}

13. {"type": "delete_caption", "caption_id": "..."}
    - Remove a caption

14. {"type": "audio_edit", "track_id": "...", "volume": 0.5}
    - Change audio track volume or source

15. {"type": "add_music", "vibe": "lo-fi|trap|cinematic", "volume": 0.25}
    - Add background music track

16. {"type": "change_color_grade", "grade": "warm|cool|cinematic|vibrant|matte|none"}
    - Change color grade

17. {"type": "add_zoom", "timestamp": <float>, "scale": 1.3, "duration": 0.5}
    - Add a zoom effect at a timeline timestamp

18. {"type": "remove_zoom", "timestamp": <float>}
    - Remove zoom effect at a timeline timestamp

19. {"type": "add_transition", "clip_a_id": "...", "clip_b_id": "...", "transition_type": "fade|dissolve|wipe_left|wipe_right", "duration": <float>}
    - Add transition between two clips

20. {"type": "add_text_overlay", "text": "...", "start": <float>, "end": <float>, "x": 0.5, "y": 0.5, "animation": "none|fade_in|pop|typewriter"}
    - Add text overlay

21. {"type": "add_blur", "blur_type": "gaussian|motion|pixelate", "intensity": <float>, "start": <float>, "end": <float>}
    - Add blur effect

22. {"type": "add_shake", "intensity": <float>, "start": <float>, "end": <float>}
    - Add camera shake

23. {"type": "set_aspect_ratio", "ratio": "9:16|16:9|1:1|4:5"}
    - Change aspect ratio

IMPORTANT RULES:
- ALWAYS include a "message" field with your conversational reply — never omit it
- If the user is just chatting (greetings, questions, small talk), return "message" with your reply and "patches": []
- Timestamps in patches refer to TIMELINE time, not source time
- Be precise with timestamps — use the edit_state timeline to find correct times
- For natural language like "0:15 pe zoom hatao", convert "0:15" to 15.0 seconds
- Be warm, conversational, and helpful — this is a chat interface!
- To delete a text overlay use "delete_caption" with the overlay's id
"""


def _build_timeline_context(state: Dict[str, Any]) -> str:
    """Build a concise text summary of the edit state for the LLM."""
    parts = []
    parts.append(f"Mode: {state.get('mode', 'reels')}")
    parts.append(f"Total duration: {state['metadata']['total_duration']:.1f}s")

    tl = state.get("timeline", [])
    parts.append(f"Timeline: {len(tl)} segments")
    for seg in tl[:5]:
        speed_info = f" speed={seg.get('speed', 1.0)}" if seg.get("speed", 1.0) != 1.0 else ""
        rev_info = " REVERSED" if seg.get("reversed") else ""
        parts.append(f"  [{seg['id']}] clip={seg['clip_id']} src={seg['source_start']:.1f}-{seg['source_end']:.1f} → tl={seg['timeline_start']:.1f}-{seg['timeline_end']:.1f}{speed_info}{rev_info}")

    caps = state.get("captions", [])
    parts.append(f"Captions: {len(caps)} entries")
    for cap in caps[:3]:
        parts.append(f"  [{cap['id']}] \"{cap['text'][:40]}...\" @ {cap['start']:.1f}s-{cap['end']:.1f}s style={cap['style']}")

    audio = state.get("audio_tracks", [])
    parts.append(f"Audio tracks: {len(audio)}")
    for at in audio:
        parts.append(f"  [{at['id']}] {at['type']} '{at['name']}' vol={at['volume']} @ {at['start']:.1f}s")

    effects = state.get("effects", {})
    parts.append(f"Color grade: {effects.get('color_grade', 'none')}")
    transitions = [t for t in effects.get("transitions", []) if t.get("type") == "transition"]
    parts.append(f"Transitions: {len(transitions)}")
    for tr in transitions[:3]:
        parts.append(f"  {tr.get('transition')} between {tr.get('between', ['?','?'])}")

    overlays = state.get("overlays", [])
    text_overlays = [o for o in overlays if o.get("type") == "text"]
    if text_overlays:
        parts.append(f"Text overlays: {len(text_overlays)}")
        for tov in text_overlays[:3]:
            parts.append(f"  [{tov['id']}] \"{tov['text'][:30]}...\" @ {tov.get('start', 0):.1f}-{tov.get('end', 0):.1f}s anim={tov.get('animation', 'none')}")

    image_overlays = [o for o in overlays if o.get("type") in ("image", "sticker", "gif")]
    if image_overlays:
        parts.append(f"Image/sticker overlays: {len(image_overlays)}")

    keyframes = state.get("keyframes", [])
    if keyframes:
        kf_props = set(kf["property"] for kf in keyframes)
        parts.append(f"Keyframes: {len(keyframes)} total, properties: {', '.join(kf_props)}")

    metadata = state.get("metadata", {})
    if metadata.get("aspect_ratio") and metadata["aspect_ratio"] != "9:16":
        parts.append(f"Aspect ratio: {metadata['aspect_ratio']}")

    return "\n".join(parts)


async def process_prompt(
    job_id: str,
    user_id: str,
    prompt: str,
    video_analysis: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Process a natural language edit prompt.
    1. Fetch edit state
    2. Send to LLM with optional video analysis context + attachments
    3. Apply patches
    4. Return applied patches
    """
    state = get_edit_state(job_id, user_id)
    if not state:
        return {
            "job_id": job_id,
            "applied_patches": [],
            "message": "Edit state not found",
            "needs_render": False,
        }

    context = _build_timeline_context(state)
    state_json = json.dumps(state, indent=2, default=str)

    analysis_context = ""
    if video_analysis:
        stats = video_analysis.get("summary_stats", {})
        scenes = video_analysis.get("scenes", [])
        silences = video_analysis.get("silences", [])
        highlights = video_analysis.get("highlights", [])
        transcript = video_analysis.get("transcript", [])
        energy = video_analysis.get("energy_curve", [])

        analysis_context = f"""
Video Analysis Data (use this to make smarter edit decisions):
- Tone: {video_analysis.get('overall_tone', 'neutral')}
- Music present: {video_analysis.get('has_music', False)}
- Silence ratio: {video_analysis.get('silence_ratio', 0)}
- {len(scenes)} scene changes detected
- {len(silences)} silent segments
- {len(highlights)} highlight moments
- {len(transcript)} transcript segments
- Energy curve (0=calm, 1=intense): {energy[:10]}...

Top highlights (focus edits here):
{json.dumps(highlights[:5], indent=2)}

Silent segments (consider cutting these):
{json.dumps(silences[:5], indent=2)}"""

    attachments_context = ""
    if attachments and len(attachments) > 0:
        att_lines = "\n".join(
            f"- [{a.get('type', 'link')}] {a.get('label', '')}: {a.get('url', '')}"
            for a in attachments
        )
        attachments_context = f"""
User attached reference material (use these for context/inspiration):
{att_lines}"""

    user_message = f"""Current edit state:
```json
{state_json}
```

Timeline context:
{context}
{analysis_context}
{attachments_context}

User edit request: "{prompt}"

You MUST respond with a JSON object: {{"patches": [...], "message": "your reply"}}
The "message" field is REQUIRED — never omit it.
- If the user is just chatting: patches: [], message: your friendly reply
- If the user wants to edit: patches: [...], message: explain what you did"""

    client = _get_client()
    try:
        kwargs = dict()
        if not _is_local_llm():
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(
            model="llama3.2:3b",
            messages=[
                {"role": "system", "content": PROMPT_EDIT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1000,
            temperature=0.3,
            **kwargs,
        )

        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3].strip()
            content = content.strip()
        if not content:
            logger.error(f"Empty LLM response. Full response: {response}")
            return {
                "job_id": job_id,
                "applied_patches": [],
                "message": "The AI model returned an empty response. Try a simpler request.",
                "needs_render": False,
            }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = content[start:end+1]
        else:
            raw = content
        logger.info(f"LLM raw response (extracted): {raw[:300]}")
        try:
            patches_data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON parse error: {e}. Raw: {raw[:500]}")
            return {
                "job_id": job_id,
                "applied_patches": [],
                "message": raw[:200] or "The AI model returned an unexpected response.",
                "needs_render": False,
            }

        if isinstance(patches_data, list):
            patches = patches_data
            ai_message = ""
        else:
            patches = patches_data.get("patches", [])
            ai_message = (patches_data.get("message") or "").strip()

        applied = []
        needs_render = False

        for patch in patches:
            result = _apply_patch(state, patch)
            if result:
                applied.append(result)
                if result.get("needs_render", False):
                    needs_render = True

        if applied:
            save_edit_state(state)

        if not ai_message:
            if applied:
                ai_message = f"Applied {len(applied)} change(s)"
            else:
                ai_message = "Hey! How can I help you with your video today?"
        logger.info(f"Prompt editor: '{prompt[:50]}...' → {len(applied)} patches applied")

        return {
            "job_id": job_id,
            "applied_patches": applied,
            "message": ai_message,
            "needs_render": needs_render,
        }

    except Exception as e:
        logger.error(f"Prompt editor error: {e}")
        return {
            "job_id": job_id,
            "applied_patches": [],
            "message": f"Failed to process prompt: {str(e)[:100]}",
            "needs_render": False,
        }


def _apply_patch(state: Dict[str, Any], patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Apply a single patch operation to the edit state."""
    ptype = patch.get("type", "")

    if ptype == "trim":
        from services.edit_state import action_trim
        action_trim(state, patch["clip_id"], patch["start"], patch["end"])
        return {"type": "trim", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "split":
        from services.edit_state import action_split
        action_split(state, patch["clip_id"], patch["at"])
        return {"type": "split", "clip_id": patch["clip_id"], "at": patch["at"], "needs_render": True}

    elif ptype == "delete":
        from services.edit_state import action_delete
        action_delete(state, patch["clip_id"])
        return {"type": "delete", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "move":
        from services.edit_state import action_move
        action_move(state, patch["clip_id"], patch["new_position"])
        return {"type": "move", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "update_caption":
        from services.edit_state import action_update_caption
        action_update_caption(
            state,
            patch["caption_id"],
            text=patch.get("text"),
            style=patch.get("style"),
            start=patch.get("start"),
            end=patch.get("end"),
        )
        return {"type": "update_caption", "caption_id": patch["caption_id"], "needs_render": True}

    elif ptype == "add_caption":
        cap = {
            "id": _new_caption_id(),
            "text": patch.get("text", ""),
            "start": patch.get("start", 0),
            "end": patch.get("end", 0),
            "style": patch.get("style", "bold_white_center"),
        }
        state["captions"].append(cap)
        _mark_dirty(state, cap["start"], cap["end"])
        return {"type": "add_caption", "caption_id": cap["id"], "needs_render": True}

    elif ptype == "delete_caption":
        cid = patch["caption_id"]
        state["captions"] = [c for c in state["captions"] if c["id"] != cid]
        state["overlays"] = [o for o in state.get("overlays", []) if o["id"] != cid]
        return {"type": "delete_caption", "caption_id": cid, "needs_render": True}

    elif ptype == "audio_edit":
        from services.edit_state import action_audio_edit
        action_audio_edit(
            state,
            patch["track_id"],
            volume=patch.get("volume"),
            source_url=patch.get("source_url"),
            start=patch.get("start"),
        )
        return {"type": "audio_edit", "track_id": patch["track_id"], "needs_render": True}

    elif ptype == "add_music":
        duration = state["metadata"].get("total_duration", 0)
        if duration <= 0:
            try:
                from core.database import get_supabase
                supabase = get_supabase()
                video = supabase.table("videos").select("duration,fps,width,height").eq("id", state.get("video_id", "")).single().execute()
                if video.data:
                    duration = video.data.get("duration", 0) or 0
                    if duration > 0:
                        state["metadata"]["total_duration"] = duration
                        state["metadata"]["fps"] = video.data.get("fps", 30) or 30
                        state["metadata"]["width"] = video.data.get("width", 1080) or 1080
                        state["metadata"]["height"] = video.data.get("height", 1920) or 1920
            except Exception:
                pass
        track = {
            "id": _new_track_id(),
            "type": "music",
            "source_url": "",
            "start": 0,
            "duration": duration or 30,
            "volume": patch.get("volume", 0.25),
            "name": patch.get("vibe", "lo-fi"),
        }
        state["audio_tracks"].append(track)
        return {"type": "add_music", "track_id": track["id"], "needs_render": True}

    elif ptype == "change_color_grade":
        state["effects"]["color_grade"] = patch.get("grade", "warm")
        _mark_dirty(state, 0, state["metadata"]["total_duration"])
        return {"type": "change_color_grade", "grade": patch["grade"], "needs_render": True}

    elif ptype == "add_zoom":
        transitions = state["effects"].setdefault("transitions", [])
        transitions.append({
            "type": "zoom",
            "timestamp": patch["timestamp"],
            "scale": patch.get("scale", 1.3),
            "duration": patch.get("duration", 0.5),
        })
        _mark_dirty(state, patch["timestamp"], patch["timestamp"] + patch.get("duration", 0.5))
        return {"type": "add_zoom", "timestamp": patch["timestamp"], "needs_render": True}

    elif ptype == "remove_zoom":
        ts = patch.get("timestamp")
        transitions = state["effects"].get("transitions", [])
        state["effects"]["transitions"] = [
            t for t in transitions
            if not (t.get("type") == "zoom" and abs(t.get("timestamp", 0) - ts) < 1.0)
        ]
        return {"type": "remove_zoom", "timestamp": ts, "needs_render": True}

    elif ptype == "duplicate":
        action_duplicate(state, patch["clip_id"], patch.get("count", 1))
        return {"type": "duplicate", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "speed_change":
        action_speed_change(state, patch["clip_id"], patch["speed"])
        return {"type": "speed_change", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "reverse":
        action_reverse(state, patch["clip_id"])
        return {"type": "reverse", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "freeze_frame":
        action_freeze_frame(state, patch["clip_id"], patch["at"], patch.get("duration", 2.0))
        return {"type": "freeze_frame", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "crop":
        action_crop(state, patch["clip_id"], patch.get("x", 0), patch.get("y", 0), patch.get("width", 1), patch.get("height", 1))
        return {"type": "crop", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "rotate":
        action_rotate(state, patch["clip_id"], patch["degrees"])
        return {"type": "rotate", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "opacity":
        action_opacity(state, patch["clip_id"], patch["opacity"])
        return {"type": "opacity", "clip_id": patch["clip_id"], "needs_render": True}

    elif ptype == "add_transition":
        from services.transitions_engine import add_transition
        add_transition(state, patch["clip_a_id"], patch["clip_b_id"], patch.get("transition_type", "fade"), patch.get("duration", 0.5))
        return {"type": "add_transition", "needs_render": True}

    elif ptype == "add_text_overlay":
        from services.text_overlay_engine import add_text_overlay
        add_text_overlay(
            state, patch["text"], patch["start"], patch["end"],
            x=patch.get("x", 0.5), y=patch.get("y", 0.5),
            animation=patch.get("animation", "none"),
        )
        return {"type": "add_text_overlay", "needs_render": True}

    elif ptype == "add_blur":
        from services.effects_engine import add_blur_effect
        add_blur_effect(state, patch.get("blur_type", "gaussian"), patch.get("intensity", 5.0), patch.get("start", 0), patch.get("end", 0))
        return {"type": "add_blur", "needs_render": True}

    elif ptype == "add_shake":
        from services.effects_engine import add_shake_effect
        add_shake_effect(state, patch.get("intensity", 5.0), 10.0, patch.get("start", 0), patch.get("end", 0))
        return {"type": "add_shake", "needs_render": True}

    elif ptype == "set_aspect_ratio":
        from services.aspect_ratio_engine import set_aspect_ratio
        set_aspect_ratio(state, patch.get("ratio", "9:16"))
        return {"type": "set_aspect_ratio", "needs_render": True}

    elif ptype == "add_overlay":
        from services.overlay_engine import add_overlay
        add_overlay(
            state, patch.get("overlay_type", "image"), patch["source_url"],
            patch["start"], patch["end"],
            x=patch.get("x", 0.5), y=patch.get("y", 0.5),
            scale=patch.get("scale", 1.0), opacity=patch.get("opacity", 1.0),
        )
        return {"type": "add_overlay", "needs_render": True}

    elif ptype == "add_audio_track":
        from services.audio_engine import add_audio_track
        add_audio_track(
            state, patch["source_url"], patch.get("track_type", "music"),
            start=patch.get("start", 0), volume=patch.get("volume", 0.25),
            name=patch.get("name", ""),
        )
        return {"type": "add_audio_track", "needs_render": True}

    logger.warning(f"Unknown patch type: {ptype}")
    return None
