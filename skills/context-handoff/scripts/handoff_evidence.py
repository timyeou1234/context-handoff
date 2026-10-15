#!/usr/bin/env python3
"""Exact-session evidence and usage accounting. No transcript text is emitted."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def locate(path, session_id):
    path = Path(path).expanduser().resolve()
    if not path.exists():
        # Only the same basename in the known archive sibling; never latest-file search.
        parents = [p for p in path.parents if p.name == "sessions"]
        if not parents:
            raise ValueError("exact rollout is missing")
        path = parents[0].parent / "archived_sessions" / path.name
    with path.open(encoding="utf-8") as f:
        first = json.loads(f.readline())
    if first.get("type") != "session_meta" or first.get("payload", {}).get("id") != session_id:
        raise ValueError("session identity mismatch")
    return path


def objects(value):
    """Decode output text blocks, never search transcript substrings for a result."""
    if isinstance(value, dict):
        yield value
        for key in ("value", "result", "structuredContent"):
            if key in value:
                yield from objects(value[key])
        if value.get("type") in ("input_text", "text"):
            yield from objects(value.get("text", ""))
    elif isinstance(value, list):
        for item in value:
            yield from objects(item)
    elif isinstance(value, str):
        for line in value.splitlines():
            try:
                decoded = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(decoded, (dict, list)):
                yield from objects(decoded)


def snapshot(path, session_id, until=None):
    path = locate(path, session_id)
    latest = None
    highwater = {}
    sample_at = None
    complete_at = None
    model = None
    effort = None
    pending = set()
    goal = None
    goal_at = None
    advances = 0
    calls = 0
    compactions = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)  # Incomplete/malformed telemetry must fail closed.
            if not isinstance(event, dict):
                raise ValueError("invalid telemetry event")
            timestamp = event.get("timestamp")
            if until and timestamp and timestamp > until:
                continue
            q = event.get("payload", {})
            if not isinstance(q, dict):
                continue
            if event.get("type") == "session_meta" and q.get("id") != session_id:
                raise ValueError("conflicting session identity")
            if event.get("type") == "turn_context":
                model, effort = q.get("model"), q.get("effort")
            if event.get("type") == "compacted":
                compactions += 1
            kind = q.get("type")
            if event.get("type") == "response_item" and kind in ("function_call", "custom_tool_call"):
                calls += 1
                body = str(q.get("input", q.get("arguments", "")))
                if q.get("name") == "get_goal" or re.search(r"tools\.get_goal\s*\(", body):
                    pending.add(q.get("call_id"))
            if event.get("type") == "response_item" and kind in ("function_call_output", "custom_tool_call_output") and q.get("call_id") in pending:
                for obj in objects(q.get("output")):
                    if set(("goal", "remainingTokens", "completionBudgetReport")) <= obj.keys():
                        goal, goal_at = obj, timestamp
                pending.remove(q.get("call_id"))
            if event.get("type") != "event_msg":
                continue
            if kind == "task_complete":
                complete_at = timestamp
            if kind != "token_count" or not isinstance(q.get("info"), dict):
                continue
            current = q["info"].get("total_token_usage")
            if not isinstance(current, dict):
                continue
            values = {k: current.get(k) for k in FIELDS}
            if any(v is not None and (type(v) is not int or v < 0) for v in values.values()):
                raise ValueError("invalid token counter")
            if any(values[k] is not None and k in highwater and values[k] < highwater[k] for k in FIELDS):
                raise ValueError("non-monotonic token counters")
            highwater.update({k: v for k, v in values.items() if v is not None})
            if latest != values:
                advances += 1
            latest, sample_at = values, timestamp
    if latest is None:
        raise ValueError("no usage telemetry")
    inp, cache = latest["input_tokens"], latest["cached_input_tokens"]
    if inp is not None and cache is not None and cache > inp:
        raise ValueError("cached input exceeds input")
    if latest["output_tokens"] is not None and latest["reasoning_output_tokens"] is not None and latest["reasoning_output_tokens"] > latest["output_tokens"]:
        raise ValueError("reasoning exceeds output")
    if all(latest[k] is not None for k in ("input_tokens", "output_tokens", "total_tokens")) and latest["input_tokens"] + latest["output_tokens"] != latest["total_tokens"]:
        raise ValueError("inconsistent total")
    latest["uncached_input_tokens"] = inp - cache if inp is not None and cache is not None else None
    return {"session_id": session_id, "rollout": str(path), "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "cutoff": sample_at, "task_complete_at": complete_at, "completed_after_usage": bool(complete_at and sample_at and complete_at >= sample_at), "model": model, "effort": effort, "usage": latest, "usage_advances": advances, "tool_calls": calls, "compactions": compactions, "goal_evidence": goal, "goal_observed_at": goal_at}


def interval(start, end):
    if start["session_id"] != end["session_id"]:
        raise ValueError("interval session mismatch")
    if start["cutoff"] > end["cutoff"]:
        raise ValueError("reversed interval")
    values = {}
    for key in (*FIELDS, "uncached_input_tokens"):
        a, b = start["usage"].get(key), end["usage"].get(key)
        values[key] = b - a if a is not None and b is not None else None
        if values[key] is not None and values[key] < 0:
            raise ValueError("negative interval")
    return {"session_id": end["session_id"], "start": start["cutoff"], "end": end["cutoff"], "usage": values}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("snapshot")
    p.add_argument("rollout"); p.add_argument("--session-id", required=True)
    p.add_argument("--until"); p.add_argument("--output")
    p.add_argument("--require-goal-none", action="store_true")
    p = sub.add_parser("interval")
    p.add_argument("start"); p.add_argument("end"); p.add_argument("--output")
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            data = snapshot(args.rollout, args.session_id, args.until)
            if args.require_goal_none and (data["goal_evidence"] is None or data["goal_evidence"]["goal"] is not None):
                raise ValueError("actual get_goal null evidence missing")
        else:
            data = interval(json.loads(Path(args.start).read_text()), json.loads(Path(args.end).read_text()))
        rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
            if json.loads(Path(args.output).read_text()) != data:
                raise ValueError("snapshot read-back mismatch")
        print(rendered, end="")
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
