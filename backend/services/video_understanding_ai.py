"""
Video Understanding AI — Foundation layer for the entire AI system.
Extracts scene, face, speech, motion, audio, and highlight signals from raw video.
"""

import json
import logging
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from core.database import get_supabase
from core.config import settings

logger = logging.getLogger(__name__)


async def analyze_video(
    video_id: str,
    video_url: str,
    user_id: str,
    force_reprocess: bool = False,
) -> Dict[str, Any]:
    """Full video analysis pipeline. Returns structured analysis JSON."""
    supabase = get_supabase()

    # Check cache
    if not force_reprocess:
        cached = supabase.table("video_analysis").select("*").eq("video_id", video_id).single().execute()
        if cached.data:
            logger.info(f"Using cached analysis for {video_id}")
            return cached.data["analysis"]

    logger.info(f"Starting video analysis for {video_id}")

    local_path = _resolve_local_path(video_url, video_id)

    analysis: Dict[str, Any] = {
        "video_id": video_id,
        "analyzed_at": datetime.utcnow().isoformat(),
        "duration": 0,
        "scenes": [],
        "silences": [],
        "motion_segments": [],
        "audio_loudness": [],
        "transcript": [],
        "highlights": [],
        "energy_curve": [],
        "face_moments": [],
        "overall_tone": "neutral",
        "has_music": False,
        "silence_ratio": 0.0,
        "avg_sentence_speed": 0.0,
    }

    # 1. Basic metadata
    metadata = _get_metadata(local_path)
    analysis["duration"] = metadata.get("duration", 0)
    duration = analysis["duration"]
    if duration <= 0:
        logger.warning(f"Could not get duration for {local_path}, using defaults")
        duration = 60.0
        analysis["duration"] = duration

    # 2. Scene detection
    try:
        scenes = _detect_scenes(local_path)
        analysis["scenes"] = scenes
        logger.info(f"Detected {len(scenes)} scenes")
    except Exception as e:
        logger.warning(f"Scene detection failed: {e}")

    # 3. Silence detection
    try:
        silences = _detect_silences(local_path)
        analysis["silences"] = silences
        silence_total = sum(s["duration"] for s in silences)
        analysis["silence_ratio"] = round(silence_total / duration, 3) if duration > 0 else 0
    except Exception as e:
        logger.warning(f"Silence detection failed: {e}")

    # 4. Audio loudness / energy
    try:
        loudness = _get_audio_loudness(local_path, duration)
        analysis["audio_loudness"] = loudness
    except Exception as e:
        logger.warning(f"Loudness analysis failed: {e}")

    # 5. Motion analysis (via scene change frequency)
    scenes_for_motion = analysis["scenes"]
    if scenes_for_motion:
        motion = _compute_motion_curve(scenes_for_motion, duration)
        analysis["motion_segments"] = motion["segments"]
        analysis["energy_curve"] = motion["energy_curve"]

    # 6. Transcript (Whisper)
    try:
        from services.whisper_service import transcribe_audio
        transcript = await transcribe_audio(local_path)
        if transcript:
            analysis["transcript"] = transcript
            # Calculate avg sentence speed
            words = [w for seg in transcript for w in seg.get("words", [])]
            if words and duration > 0:
                analysis["avg_sentence_speed"] = round(len(words) / duration, 2)
    except Exception as e:
        logger.warning(f"Transcript failed: {e}")

    # 7. Detect music presence
    try:
        analysis["has_music"] = _detect_music(local_path)
    except Exception as e:
        logger.warning(f"Music detection failed: {e}")

    # 8. Overall tone from transcript keywords
    transcript_text = " ".join(s.get("text", "") for s in analysis["transcript"] if s.get("text"))
    if transcript_text:
        analysis["overall_tone"] = _classify_tone(transcript_text)

    # 9. Generate highlights by combining all signals
    analysis["highlights"] = _generate_highlights(
        scenes=analysis["scenes"],
        silences=analysis["silences"],
        transcript=analysis["transcript"],
        energy_curve=analysis["energy_curve"],
        duration=duration,
    )

    # 10. Face moments framework (ready for cloud ML)
    analysis["face_moments"] = _estimate_face_moments(analysis["highlights"], duration)

    # Cache
    try:
        supabase.table("video_analysis").upsert({
            "video_id": video_id,
            "user_id": user_id,
            "analysis": analysis,
            "duration": duration,
            "analyzed_at": analysis["analyzed_at"],
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to cache analysis: {e}")

    logger.info(f"Video analysis complete for {video_id}: {len(analysis['scenes'])} scenes, {len(analysis['highlights'])} highlights")
    return analysis


# ── FFprobe metadata ──────────────────────────────────────────────────────────────

def _resolve_local_path(video_url: str, video_id: str) -> str:
    """Convert URL to local filesystem path."""
    dev_api_url = settings.dev_api_url
    if video_url.startswith(f"{dev_api_url}/api/video/local/"):
        filename = video_url.split("/")[-1]
        dev_uploads = settings.dev_storage_path
        for base in [dev_uploads, "/tmp"]:
            p = os.path.join(base, filename)
            if os.path.exists(p):
                return p
            for ext in [".mp4", ".mov", ".webm", ".avi"]:
                p2 = os.path.join(base, filename.replace(".mp4", ext))
                if os.path.exists(p2):
                    return p2
        return os.path.join(dev_uploads, filename)
    return video_url


def _get_metadata(local_path: str) -> Dict[str, Any]:
    """Get basic video metadata via ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", local_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"duration": 0, "width": 0, "height": 0, "fps": 0}
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        width, height, fps = 0, 0, 0
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                width = int(s.get("width", 0))
                height = int(s.get("height", 0))
                fps_str = s.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    fps = float(num) / float(den) if float(den) > 0 else 0
                break
        return {"duration": duration, "width": width, "height": height, "fps": fps}
    except Exception as e:
        logger.warning(f"ffprobe error: {e}")
        return {"duration": 0, "width": 0, "height": 0, "fps": 0}


# ── Scene Detection ────────────────────────────────────────────────────────────────

def _detect_scenes(local_path: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
    """Detect scene changes using FFmpeg scene detection filter."""
    cmd = [
        "ffmpeg", "-i", local_path, "-filter:v",
        f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    scenes = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                parts = line.split()
                for p in parts:
                    if p.startswith("pts_time:"):
                        t = float(p.split(":")[1])
                        scenes.append({
                            "time": round(t, 2),
                            "type": "scene_change",
                            "confidence": 0.7,
                        })
            except (ValueError, IndexError):
                continue

    if not scenes:
        duration = _get_metadata(local_path).get("duration", 60)
        scenes = _fallback_scenes(duration)

    return scenes


def _fallback_scenes(duration: float, interval: float = 5.0) -> List[Dict[str, Any]]:
    """Fallback: divide video into equal segments."""
    scenes = []
    t = 0
    while t < duration:
        scenes.append({"time": round(t, 2), "type": "segment", "confidence": 0.3})
        t += interval
    return scenes


# ── Silence Detection ──────────────────────────────────────────────────────────────

def _detect_silences(local_path: str, silence_duration: float = 0.5, silence_threshold: float = -30) -> List[Dict[str, Any]]:
    """Detect silent segments using FFmpeg silencedetect."""
    cmd = [
        "ffmpeg", "-i", local_path, "-af",
        f"silencedetect=noise={silence_threshold}dB:d={silence_duration}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    silences = []
    current_start = None
    for line in result.stderr.split("\n"):
        if "silence_start:" in line:
            try:
                current_start = float(line.split("silence_start:")[1].strip())
            except (ValueError, IndexError):
                pass
        if "silence_end:" in line and current_start is not None:
            try:
                parts = line.split("silence_end:")
                end_str = parts[1].split("|")[0].strip()
                end = float(end_str)
                silences.append({
                    "start": round(current_start, 2),
                    "end": round(end, 2),
                    "duration": round(end - current_start, 2),
                })
                current_start = None
            except (ValueError, IndexError):
                pass
    return silences


# ── Audio Loudness ─────────────────────────────────────────────────────────────────

def _get_audio_loudness(local_path: str, duration: float, segments: int = 20) -> List[Dict[str, Any]]:
    """Get loudness levels across the video using ebur128 or volume stats."""
    seg_dur = max(1, duration / segments)
    loudness = []
    for i in range(segments):
        start = i * seg_dur
        cmd = [
            "ffmpeg", "-ss", str(start), "-t", str(seg_dur),
            "-i", local_path, "-af", "volumedetect",
            "-f", "null", "-",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            mean = -20
            peak = -10
            for line in result.stderr.split("\n"):
                if "mean_volume" in line:
                    try:
                        mean = float(line.split("mean_volume:")[1].strip().replace(" dB", ""))
                    except (ValueError, IndexError):
                        pass
                if "max_volume" in line:
                    try:
                        peak = float(line.split("max_volume:")[1].strip().replace(" dB", ""))
                    except (ValueError, IndexError):
                        pass
            loudness.append({
                "start": round(start, 1),
                "end": round(start + seg_dur, 1),
                "mean_db": round(mean, 1),
                "peak_db": round(peak, 1),
                "energy": round(abs(mean) / 40, 3),
            })
        except Exception:
            loudness.append({
                "start": round(start, 1),
                "end": round(start + seg_dur, 1),
                "mean_db": -20,
                "peak_db": -10,
                "energy": 0.5,
            })
    return loudness


# ── Motion Curve ───────────────────────────────────────────────────────────────────

def _compute_motion_curve(scenes: List[Dict[str, Any]], duration: float, bins: int = 30) -> Dict[str, Any]:
    """Compute motion/energy segments from scene change density."""
    bin_dur = max(1, duration / bins)
    bins_data = [{"start": i * bin_dur, "end": (i + 1) * bin_dur, "changes": 0} for i in range(bins)]
    for s in scenes:
        t = s["time"]
        idx = min(int(t / bin_dur), bins - 1)
        bins_data[idx]["changes"] += 1

    max_changes = max(b["changes"] for b in bins_data) or 1
    for b in bins_data:
        b["energy"] = round(b["changes"] / max_changes, 3)
        b["motion_type"] = "high" if b["energy"] > 0.6 else "medium" if b["energy"] > 0.3 else "low"

    return {"segments": bins_data, "energy_curve": [b["energy"] for b in bins_data]}


# ── Music Detection ────────────────────────────────────────────────────────────────

def _detect_music(local_path: str) -> bool:
    """Simple music detection: check if audio has rhythmic patterns."""
    cmd = [
        "ffmpeg", "-i", local_path, "-af", "astats=metadata=1:reset=1",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    # Simple heuristic: if silence ratio is very low, probably has music
    # This is a placeholder — real detection needs spectrogram analysis
    try:
        silences = _detect_silences(local_path, silence_duration=0.3, silence_threshold=-35)
        total_silence = sum(s["duration"] for s in silences)
        duration = _get_metadata(local_path).get("duration", 60)
        silence_ratio = total_silence / duration if duration > 0 else 0
        # Less silence typically means background music
        return silence_ratio < 0.15
    except Exception:
        return False


# ── Tone Classification ────────────────────────────────────────────────────────────

def _classify_tone(text: str) -> str:
    """Classify overall tone from transcript text."""
    text_lower = text.lower()
    funny_words = ["lol", "haha", "funny", "crazy", "wow", "omg", "hilarious"]
    serious_words = ["important", "serious", "critical", "must", "need", "problem", "issue"]
    emotional_words = ["amazing", "incredible", "beautiful", "love", "hate", "cry", "sad"]
    energetic_words = ["let's go", "yeah", "come on", "boom", "yes", "let's", "exciting"]

    scores = {"funny": 0, "serious": 0, "emotional": 0, "energetic": 0, "neutral": 1}
    for w in funny_words:
        if w in text_lower:
            scores["funny"] += 1
    for w in serious_words:
        if w in text_lower:
            scores["serious"] += 1
    for w in emotional_words:
        if w in text_lower:
            scores["emotional"] += 1
    for w in energetic_words:
        if w in text_lower:
            scores["energetic"] += 1
    return max(scores, key=scores.get)


# ── Highlight Generation ───────────────────────────────────────────────────────────

def _generate_highlights(
    scenes: List[Dict[str, Any]],
    silences: List[Dict[str, Any]],
    transcript: List[Dict[str, Any]],
    energy_curve: List[float],
    duration: float,
) -> List[Dict[str, Any]]:
    """Generate highlight candidates by combining all analysis signals."""
    highlights = []

    # 1. High energy scenes = potential highlights
    scene_times = [s["time"] for s in scenes]
    for i, t in enumerate(scene_times):
        end = scene_times[i + 1] if i + 1 < len(scene_times) else duration
        seg_dur = end - t
        if seg_dur < 1 or seg_dur > 30:
            continue
        # Energy score from nearby energy curve
        energy_idx = min(int(t / max(1, duration / len(energy_curve))), len(energy_curve) - 1) if energy_curve else 0
        energy = energy_curve[energy_idx] if energy_curve else 0.5
        if energy > 0.4:
            highlights.append({
                "start": round(t, 1),
                "end": round(end, 1),
                "duration": round(seg_dur, 1),
                "type": "energy_peak",
                "score": round(energy, 2),
                "reason": "High energy scene change",
            })

    # 2. Around silences = potential punchlines (quiet before loud)
    for s in silences:
        if s["duration"] > 0.3:
            punch_start = max(0, s["end"])
            punch_end = min(duration, s["end"] + 2)
            highlights.append({
                "start": round(punch_start, 1),
                "end": round(punch_end, 1),
                "duration": round(punch_end - punch_start, 1),
                "type": "punchline",
                "score": 0.6,
                "reason": "Post-silence moment",
            })

    # 3. Transcript-based highlights (keyword density)
    if transcript:
        for seg in transcript:
            text = seg.get("text", "")
            start = seg.get("start", 0)
            end = seg.get("end", start + 3)
            if len(text) > 20:
                highlights.append({
                    "start": round(start, 1),
                    "end": round(end, 1),
                    "duration": round(end - start, 1),
                    "type": "key_moment",
                    "score": 0.5,
                    "reason": f"Speech segment: {text[:40]}...",
                })

    # Deduplicate and prioritize by score
    highlights.sort(key=lambda h: -h["score"])
    seen_ranges = []
    deduped = []
    for h in highlights:
        overlap = False
        for sr in seen_ranges:
            if h["start"] < sr["end"] and h["end"] > sr["start"]:
                overlap = True
                break
        if not overlap:
            seen_ranges.append({"start": h["start"], "end": h["end"]})
            deduped.append(h)

    return deduped[:15]


# ── Face Moment Estimation ─────────────────────────────────────────────────────────

def _estimate_face_moments(highlights: List[Dict[str, Any]], duration: float) -> List[Dict[str, Any]]:
    """Estimate potential face/camera moments based on highlight clusters.
    When ML face detection is available, this gets replaced with real data."""
    # Distribute face moments near highlight areas
    moments = []
    for h in highlights:
        moments.append({
            "start": h["start"],
            "end": h["end"],
            "estimated_faces": 1,
            "primary_emotion": "neutral",
            "confidence": 0.3,
        })
    # Add some evenly spaced fallback moments
    if not moments and duration > 0:
        for i in range(0, min(int(duration), 5)):
            t = i * duration / 5
            moments.append({
                "start": round(t, 1),
                "end": round(t + 2, 1),
                "estimated_faces": 1,
                "primary_emotion": "neutral",
                "confidence": 0.2,
            })
    return moments


# ── Analysis Endpoint Helper ───────────────────────────────────────────────────────

def get_summary_stats(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Get human-readable summary from analysis data."""
    return {
        "duration": analysis.get("duration", 0),
        "scene_count": len(analysis.get("scenes", [])),
        "silence_count": len(analysis.get("silences", [])),
        "silence_ratio": analysis.get("silence_ratio", 0),
        "highlight_count": len(analysis.get("highlights", [])),
        "has_music": analysis.get("has_music", False),
        "overall_tone": analysis.get("overall_tone", "neutral"),
        "avg_cut_interval": round(analysis.get("duration", 0) / max(1, len(analysis.get("scenes", []))), 1) if analysis.get("scenes") else 0,
        "speech_speed": analysis.get("avg_sentence_speed", 0),
        "transcript_word_count": sum(len(s.get("text", "").split()) for s in analysis.get("transcript", [])),
    }
