"""
Diff Engine — Compare old vs new edit state and generate human-readable diff.
Shows what changed after a prompt edit.
"""

import json
from typing import Dict, Any, List, Optional


def compute_edit_diff(old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two edit states and return a structured diff.
    Returns human-readable change descriptions.
    """
    changes = []
    old_segments = old_state.get("segments", [])
    new_segments = new_state.get("segments", [])

    old_ids = {s.get("id"): s for s in old_segments}
    new_ids = {s.get("id"): s for s in new_segments}

    # Find added segments
    added_ids = set(new_ids.keys()) - set(old_ids.keys())
    for sid in sorted(added_ids):
        seg = new_ids[sid]
        changes.append({
            "type": "segment_added",
            "segment_id": sid,
            "description": f"Added segment: \"{seg.get('text', '')[:80]}\"",
            "details": {
                "start_time": seg.get("start_time"),
                "end_time": seg.get("end_time"),
                "action": seg.get("action"),
            },
        })

    # Find removed segments
    removed_ids = set(old_ids.keys()) - set(new_ids.keys())
    for sid in sorted(removed_ids):
        seg = old_ids[sid]
        changes.append({
            "type": "segment_removed",
            "segment_id": sid,
            "description": f"Removed segment: \"{seg.get('text', '')[:80]}\"",
            "details": {
                "start_time": seg.get("start_time"),
                "end_time": seg.get("end_time"),
            },
        })

    # Find modified segments
    common_ids = set(old_ids.keys()) & set(new_ids.keys())
    for sid in sorted(common_ids):
        old_seg = old_ids[sid]
        new_seg = new_ids[sid]
        field_changes = []

        # Compare key fields
        for field in ["action", "speed", "caption", "caption_text", "transition", "effect",
                       "start_time", "end_time", "text", "broll_description", "music_cue"]:
            old_val = old_seg.get(field)
            new_val = new_seg.get(field)
            if old_val != new_val:
                field_changes.append({
                    "field": field,
                    "old": old_val,
                    "new": new_val,
                })

        if field_changes:
            changes.append({
                "type": "segment_modified",
                "segment_id": sid,
                "description": f"Modified segment {sid}: {', '.join(fc['field'] for fc in field_changes)}",
                "field_changes": field_changes,
            })

    # Compute summary
    summary = _generate_summary(changes, old_segments, new_segments)

    return {
        "changes": changes,
        "summary": summary,
        "total_changes": len(changes),
        "old_segment_count": len(old_segments),
        "new_segment_count": len(new_segments),
    }


def _generate_summary(changes: List[Dict], old_segments: List, new_segments: List) -> str:
    """Generate a human-readable summary of the diff."""
    if not changes:
        return "No changes made."

    added = [c for c in changes if c["type"] == "segment_added"]
    removed = [c for c in changes if c["type"] == "segment_removed"]
    modified = [c for c in changes if c["type"] == "segment_modified"]

    parts = []

    if added:
        parts.append(f"{len(added)} segment(s) added")
    if removed:
        parts.append(f"{len(removed)} segment(s) removed")
    if modified:
        # Highlight key changes
        speed_changes = sum(1 for m in modified for fc in m.get("field_changes", []) if fc["field"] == "speed")
        action_changes = sum(1 for m in modified for fc in m.get("field_changes", []) if fc["field"] == "action")
        caption_changes = sum(1 for m in modified for fc in m.get("field_changes", []) if fc["field"] in ("caption", "caption_text"))

        detail_parts = []
        if action_changes:
            detail_parts.append(f"{action_changes} action change(s)")
        if speed_changes:
            detail_parts.append(f"{speed_changes} speed adjustment(s)")
        if caption_changes:
            detail_parts.append(f"{caption_changes} caption update(s)")
        if detail_parts:
            parts.append(f"{len(modified)} segment(s) modified ({', '.join(detail_parts)})")
        else:
            parts.append(f"{len(modified)} segment(s) modified")

    return "; ".join(parts) + "."


def format_diff_for_display(diff_result: Dict[str, Any]) -> str:
    """Format diff result as readable text for API response."""
    lines = []
    lines.append(f"Edit Diff: {diff_result['total_changes']} change(s)")
    lines.append(f"Segments: {diff_result['old_segment_count']} → {diff_result['new_segment_count']}")
    lines.append("")

    for change in diff_result["changes"]:
        if change["type"] == "segment_added":
            lines.append(f"+ {change['description']}")
        elif change["type"] == "segment_removed":
            lines.append(f"- {change['description']}")
        elif change["type"] == "segment_modified":
            lines.append(f"~ {change['description']}")
            for fc in change.get("field_changes", []):
                lines.append(f"    {fc['field']}: {fc['old']} → {fc['new']}")

    return "\n".join(lines)


def get_diff_stats(diff_result: Dict[str, Any]) -> Dict[str, Any]:
    """Get summary statistics from diff."""
    changes = diff_result.get("changes", [])
    return {
        "total_changes": len(changes),
        "added": sum(1 for c in changes if c["type"] == "segment_added"),
        "removed": sum(1 for c in changes if c["type"] == "segment_removed"),
        "modified": sum(1 for c in changes if c["type"] == "segment_modified"),
        "fields_changed": list(set(
            fc["field"]
            for c in changes
            if c["type"] == "segment_modified"
            for fc in c.get("field_changes", [])
        )),
    }
