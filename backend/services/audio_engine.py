"""
Audio Engine — Multi-track audio with volume, fades, detach, ducking.

Supports:
  - Multiple audio tracks (music, sound_effect, voiceover, narration)
  - Volume control per track
  - Fade in/out per track
  - Audio detach from video
  - Audio ducking (lower music when voice speaks)
  - Trim audio to time range
  - Loop audio
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

VALID_TRACK_TYPES = {"music", "sound_effect", "voiceover", "narration", "ambient"}


def _new_audio_id() -> str:
    return f"aud_{uuid4().hex[:12]}"


def add_audio_track(
    state: Dict[str, Any],
    source_url: str,
    track_type: str = "music",
    start: float = 0.0,
    duration: float = 0.0,
    volume: float = 0.25,
    name: str = "",
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    loop: bool = False,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Add an audio track to the state."""
    track_id = _new_audio_id()
    track = {
        "id": track_id,
        "type": track_type if track_type in VALID_TRACK_TYPES else "music",
        "source_url": source_url,
        "start": start,
        "duration": duration or state["metadata"]["total_duration"],
        "volume": max(0.0, min(1.0, volume)),
        "name": name,
        "fade_in": max(0.0, min(10.0, fade_in)),
        "fade_out": max(0.0, min(10.0, fade_out)),
        "loop": loop,
        "trim_start": trim_start,
        "trim_end": trim_end,
        "detached": False,
    }

    state["audio_tracks"].append(track)
    logger.info(f"Added audio track: {track_type} '{name}' at {start:.1f}s")
    return state


def update_audio_track(
    state: Dict[str, Any],
    track_id: str,
    volume: Optional[float] = None,
    source_url: Optional[str] = None,
    start: Optional[float] = None,
    fade_in: Optional[float] = None,
    fade_out: Optional[float] = None,
    loop: Optional[bool] = None,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an audio track."""
    for track in state["audio_tracks"]:
        if track["id"] == track_id:
            if volume is not None:
                track["volume"] = max(0.0, min(1.0, volume))
            if source_url is not None:
                track["source_url"] = source_url
            if start is not None:
                track["start"] = start
            if fade_in is not None:
                track["fade_in"] = max(0.0, min(10.0, fade_in))
            if fade_out is not None:
                track["fade_out"] = max(0.0, min(10.0, fade_out))
            if loop is not None:
                track["loop"] = loop
            if trim_start is not None:
                track["trim_start"] = trim_start
            if trim_end is not None:
                track["trim_end"] = trim_end
            if name is not None:
                track["name"] = name
            logger.info(f"Updated audio track {track_id}")
            return state

    logger.warning(f"Audio track {track_id} not found")
    return state


def delete_audio_track(state: Dict[str, Any], track_id: str) -> Dict[str, Any]:
    """Delete an audio track."""
    before = len(state["audio_tracks"])
    state["audio_tracks"] = [t for t in state["audio_tracks"] if t["id"] != track_id]
    if len(state["audio_tracks"]) < before:
        logger.info(f"Deleted audio track {track_id}")
    return state


def detach_audio(state: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    """Detach audio from a video clip into a separate audio track."""
    clip = next((c for c in state["clips"] if c["id"] == clip_id), None)
    if not clip:
        logger.warning(f"Clip {clip_id} not found for audio detach")
        return state

    seg = next((s for s in state["timeline"] if s["clip_id"] == clip_id), None)
    if not seg:
        return state

    track_id = _new_audio_id()
    track = {
        "id": track_id,
        "type": "voiceover",
        "source_url": clip["source_url"],
        "start": seg["timeline_start"],
        "duration": seg["timeline_end"] - seg["timeline_start"],
        "volume": 1.0,
        "name": f"detached_{clip_id}",
        "fade_in": 0.0,
        "fade_out": 0.0,
        "loop": False,
        "trim_start": seg["source_start"],
        "trim_end": seg["source_end"],
        "detached": True,
        "source_clip_id": clip_id,
    }

    state["audio_tracks"].append(track)
    logger.info(f"Detached audio from clip {clip_id}")
    return state


def set_audio_ducking(
    state: Dict[str, Any],
    music_track_id: str,
    voice_track_ids: List[str],
    duck_volume: float = 0.1,
    attack: float = 0.3,
    release: float = 0.5,
) -> Dict[str, Any]:
    """Configure audio ducking — lower music when voice is present."""
    ducking = state.setdefault("audio_ducking", {
        "enabled": True,
        "music_track_id": music_track_id,
        "voice_track_ids": voice_track_ids,
        "duck_volume": duck_volume,
        "attack_time": attack,
        "release_time": release,
    })
    ducking["music_track_id"] = music_track_id
    ducking["voice_track_ids"] = voice_track_ids
    ducking["duck_volume"] = max(0.0, min(1.0, duck_volume))
    ducking["attack_time"] = max(0.05, min(2.0, attack))
    ducking["release_time"] = max(0.05, min(2.0, release))
    logger.info(f"Configured audio ducking for music {music_track_id}")
    return state


def get_audio_tracks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all audio tracks."""
    return state.get("audio_tracks", [])


def get_audio_track(state: Dict[str, Any], track_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific audio track."""
    return next((t for t in state["audio_tracks"] if t["id"] == track_id), None)


def build_audio_filter(track: Dict[str, Any]) -> str:
    """Build FFmpeg filter string for an audio track."""
    filters = []

    vol = track.get("volume", 1.0)
    if vol != 1.0:
        filters.append(f"volume={vol}")

    fade_in = track.get("fade_in", 0)
    if fade_in > 0:
        filters.append(f"afade=t=in:d={fade_in}")

    fade_out = track.get("fade_out", 0)
    if fade_out > 0:
        duration = track.get("duration", 10)
        filters.append(f"afade=t=out:st={duration - fade_out}:d={fade_out}")

    return ",".join(filters) if filters else "anull"
