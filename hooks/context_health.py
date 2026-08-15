#!/usr/bin/env python3
"""Persist minimal compaction state and inject a safe handoff health check."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_SCHEMA_VERSION = 1


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def additional_context(event: str, message: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }


def state_path(plugin_data: Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return plugin_data / "context-health" / f"{digest}.json"


def load_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"schema_version": STATE_SCHEMA_VERSION, "compactions": 0}
    if payload.get("schema_version") != STATE_SCHEMA_VERSION:
        return {"schema_version": STATE_SCHEMA_VERSION, "compactions": 0}
    compactions = payload.get("compactions", 0)
    if not isinstance(compactions, int) or compactions < 0:
        compactions = 0
    return {"schema_version": STATE_SCHEMA_VERSION, "compactions": compactions}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.write("\n")
        temporary_path.replace(path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def health_message(compactions: int, *, immediate: bool) -> str:
    urgency = (
        "Two or more compactions are now recorded: treat this as handoff-ready when "
        "the user or applicable instructions provide authorization."
        if compactions >= 2
        else "One compaction is recorded: create or refresh a checkpoint and audit observed degradation signals."
    )
    timing = (
        "Before any substantive continuation after this compaction"
        if immediate
        else "At the start of this user turn, before substantive work"
    )
    return (
        "CONTEXT HANDOFF HEALTH CHECK — lifecycle hook, not user-authored text. "
        f"This root session has recorded {compactions} compaction(s). {timing}, use the "
        "context-handoff skill and run its deterministic `assess` command with this "
        "compaction count plus only genuinely observed degradation signals. "
        f"{urgency} Reliance on a compacted summary, rereading because prior context is "
        "unreliable, contradicted decisions, or context-caused rework are observable signals; "
        "do not invent telemetry. Finish any active atomic operation before transfer, preserve "
        "dirty state and evidence, and do not archive the source merely to hand off."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        emit({"systemMessage": "Context Handoff could not read lifecycle hook input."})
        return 0

    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    plugin_data_raw = os.environ.get("PLUGIN_DATA")
    if not isinstance(event, str) or not isinstance(session_id, str) or not session_id:
        emit({})
        return 0
    if not plugin_data_raw:
        emit(
            {
                "systemMessage": (
                    "Context Handoff automatic detection is unavailable because PLUGIN_DATA "
                    "was not provided to the lifecycle hook."
                )
            }
        )
        return 0

    path = state_path(Path(plugin_data_raw), session_id)

    if event == "SessionStart" and payload.get("source") == "compact":
        state = load_state(path)
        state["compactions"] += 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(path, state)
        emit(additional_context(event, health_message(state["compactions"], immediate=True)))
        return 0

    if event == "UserPromptSubmit":
        state = load_state(path)
        if state["compactions"] > 0:
            emit(additional_context(event, health_message(state["compactions"], immediate=False)))
        else:
            emit({})
        return 0

    if event == "SessionEnd":
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        emit({})
        return 0

    emit({})
    return 0


if __name__ == "__main__":
    sys.exit(main())
