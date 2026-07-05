"""
Whisper Service — transcription with word-level timestamps.
Uses OpenAI Whisper API (cloud, accurate, fast).
In DEV_MODE, returns mock transcript without calling API.
"""

import os
import logging
from typing import List, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)

DEV_MODE = settings.dev_mode or not settings.openai_configured


def _mock_transcript() -> List[Dict[str, Any]]:
    return [
        {"word": "mock", "start": 0.0, "end": 0.5},
        {"word": "transcript", "start": 0.5, "end": 1.2},
        {"word": "for", "start": 1.2, "end": 1.5},
        {"word": "testing", "start": 1.5, "end": 2.0},
        {"word": "purposes", "start": 2.0, "end": 2.5},
    ]

_client = None


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


async def transcribe(audio_path: str, language: str = "hi") -> List[Dict[str, Any]]:
    """
    Transcribe audio using OpenAI Whisper API.
    Returns word-level timestamps:
      [{word: str, start: float, end: float}, ...]

    language: "hi" for Hindi/Hinglish, "en" for English.
    Whisper auto-detects if None.
    """
    if DEV_MODE:
        logger.info(f"[DEV] transcribe called: {audio_path} (mock)")
        return _mock_transcript()

    client = _get_client()

    logger.info(f"Transcribing {audio_path} (lang={language})")

    with open(audio_path, "rb") as audio_file:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )

    # Parse word-level timestamps
    words = []
    if hasattr(response, "words") and response.words:
        for w in response.words:
            words.append({
                "word": w.word.strip(),
                "start": round(w.start, 3),
                "end": round(w.end, 3),
            })
    else:
        # Fallback: segment-level if word-level not available
        if hasattr(response, "segments") and response.segments:
            for seg in response.segments:
                words.append({
                    "word": seg.text.strip(),
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                })

    logger.info(f"Transcribed {len(words)} words from {audio_path}")
    return words


async def transcribe_to_text(audio_path: str, language: str = "hi") -> str:
    """Simple transcription — just returns the full text string."""
    if DEV_MODE:
        logger.info(f"[DEV] transcribe_to_text called (mock)")
        words = _mock_transcript()
        return " ".join(w["word"] for w in words)
    
    client = _get_client()

    with open(audio_path, "rb") as audio_file:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="text",
        )

    return response
