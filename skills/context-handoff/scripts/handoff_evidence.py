#!/usr/bin/env python3
"""Exact-session evidence and usage accounting. No transcript text is emitted."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


class UsageLedger:
    """Keep independent cumulative streams; the newer ledger includes compaction."""

    def __init__(self, session_id):
        self.session_id = session_id
        self.streams = {}

    def observe(self, event):
        q = event.get("payload", {})
        if not isinstance(q, dict):
            return
        if event.get("type") == "token_usage_record":
            basis = "token_usage_record.thread_token_usage"
            if not self.session_id or q.get("thread_id") != self.session_id:
                raise ValueError("usage ledger session identity mismatch")
            current = q.get("thread_token_usage")
            if not isinstance(current, dict):
                raise ValueError("missing cumulative usage ledger")
        elif event.get("type") == "event_msg" and q.get("type") == "token_count":
            basis = "event_msg.total_token_usage"
            info = q.get("info")
            current = info.get("total_token_usage") if isinstance(info, dict) else None
            if not isinstance(current, dict):
                return
        else:
            return
        values = {k: current.get(k) for k in FIELDS}
        if any(v is not None and (type(v) is not int or v < 0) for v in values.values()):
            raise ValueError("invalid token counter")
        previous = self.streams.get(basis, {})
        high = dict(previous.get("high", {}))
        if any(v is not None and v < high.get(k, 0) for k, v in values.items()):
            raise ValueError("non-monotonic token counters")
        high.update({k: v for k, v in values.items() if v is not None})
        inp, cache, output, reasoning, total = (values[k] for k in
            ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"))
        if inp is not None and cache is not None and cache > inp:
            raise ValueError("cached input exceeds input")
        if output is not None and reasoning is not None and reasoning > output:
            raise ValueError("reasoning exceeds output")
        if all(v is not None for v in (inp, output, total)) and inp + output != total:
            raise ValueError("inconsistent total")
        self.streams[basis] = {"usage": values, "high": high, "cutoff": event.get("timestamp"),
            "advances": previous.get("advances", 0) + (previous.get("usage") != values)}

    def result(self, compactions):
        basis = "token_usage_record.thread_token_usage"
        if basis not in self.streams:
            basis = "event_msg.total_token_usage"
            if compactions:
                raise ValueError("compaction accounting unavailable in legacy telemetry")
        if basis not in self.streams:
            raise ValueError("no usage telemetry")
        selected = self.streams[basis]
        values = dict(selected["usage"])
        legacy = self.streams.get("event_msg.total_token_usage", {}).get("usage", {})
        # Never silently report a stale ledger after a producer switches formats.
        if basis.startswith("token_usage_record") and any(
            legacy.get(k) is not None and values[k] is not None and legacy[k] > values[k]
            for k in FIELDS
        ):
            raise ValueError("legacy counters exceed cumulative ledger; incomplete telemetry")
        inp, cache = values["input_tokens"], values["cached_input_tokens"]
        values["uncached_input_tokens"] = inp - cache if inp is not None and cache is not None else None
        return values, selected["cutoff"], selected["advances"], basis


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
    ledger = UsageLedger(session_id)
    complete_at = None
    model = None
    effort = None
    pending = set()
    goal = None
    goal_at = None
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
            ledger.observe(event)
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
    latest, sample_at, advances, basis = ledger.result(compactions)
    return {"session_id": session_id, "rollout": str(path), "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "cutoff": sample_at, "accounting_basis": basis, "task_complete_at": complete_at, "completed_after_usage": bool(complete_at and sample_at and complete_at >= sample_at), "model": model, "effort": effort, "usage": latest, "usage_advances": advances, "tool_calls": calls, "compactions": compactions, "goal_evidence": goal, "goal_observed_at": goal_at}


def interval(start, end):
    if start["session_id"] != end["session_id"]:
        raise ValueError("interval session mismatch")
    if start.get("accounting_basis", "event_msg.total_token_usage") != end.get("accounting_basis", "event_msg.total_token_usage"):
        raise ValueError("interval accounting basis mismatch; recapture both snapshots")
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
