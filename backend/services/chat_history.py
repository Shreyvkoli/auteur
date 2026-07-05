"""
Chat History — file-based storage per job_id.
Falls back to local JSON when Supabase is not available.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

CHAT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chat_history")


def _ensure_dir():
    os.makedirs(CHAT_DIR, exist_ok=True)


def _path(job_id: str) -> str:
    return os.path.join(CHAT_DIR, f"{job_id}.json")


def get_chat_history(job_id: str) -> List[Dict[str, Any]]:
    _ensure_dir()
    p = _path(job_id)
    if not os.path.exists(p):
        return []
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read chat history for {job_id}: {e}")
        return []


def append_chat_message(job_id: str, role: str, text: str, patches_applied: bool = False) -> List[Dict[str, Any]]:
    history = get_chat_history(job_id)
    history.append({
        "role": role,
        "text": text,
        "patchesApplied": patches_applied,
        "timestamp": datetime.utcnow().isoformat(),
    })
    _ensure_dir()
    try:
        with open(_path(job_id), "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save chat history for {job_id}: {e}")
    return history
