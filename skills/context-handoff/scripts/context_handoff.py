#!/usr/bin/env python3
"""Assess context pressure and validate a loss-resistant Codex handoff packet."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from handoff_evidence import FIELDS, snapshot


REQUIRED_SECTIONS = (
    "Goal",
    "Acceptance criteria",
    "Communication preferences",
    "Applicable constraints",
    "Workspace identity",
    "Source lifecycle",
    "Goal continuity",
    "Authorization and permissions",
    "Handoff accounting",
    "Completed and verified",
    "Unverified and open",
    "Failures and discarded approaches",
    "Next action",
    "Destination sentinel",
    "Recovery",
)

SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.I)),
)

TEMPLATE = """# Codex Context Handoff

Created: [TODO: timestamp]
Source thread: [TODO: identifier or unavailable]
Source host: [TODO: identifier or unavailable]

## Goal

[TODO: one coherent deliverable]

## Acceptance criteria

- [TODO: observable criterion]

## Communication preferences

- Reply language: [TODO: explicit preference, observed primary interaction language, or unspecified]
- Locale or time zone: [TODO: explicit preference or unspecified; do not infer it from language]

## Applicable constraints

- [TODO: governing instruction or hard constraint]

## Workspace identity

- Path: [TODO: absolute path]
- Source workspace kind: [TODO: saved checkout, Codex worktree, or projectless directory]
- Destination compatibility: [TODO: exact source path must be selectable without elevated approval]
- Repository or artifact: [TODO: identity]
- Branch and HEAD, or equivalent identity: [TODO: identity]
- Working-state summary and hash when applicable: [TODO: state]

## Source lifecycle

- Goal status: [TODO: active, paused, complete, blocked, none, or unknown]
- Source archival authorization: [TODO: per-handoff, standing preference, declined, or unspecified]
- Source closure status: [TODO: pending destination verification]

## Goal continuity

- Objective: [TODO: exact source Goal objective, or none]
- Goal authorization: [TODO: user instruction authorizing the Goal and continuation, or none]
- Remaining budget: [TODO: original cap and measured remaining tokens, unbudgeted, or unknown; never reset]
- Resume policy: [TODO: restore active Goal only with authorization; preserve paused/blocked/completed state]

## Authorization and permissions

- Authorized scope and evidence: [TODO: exact user instruction, source turn reference, authorized actions and limits]
- Pending approvals and exclusions: [TODO: unresolved approvals, denials, or none]
- Runtime permissions: [TODO: observed sandbox, approval policy, filesystem roots, network and required connectors; unknown where unavailable]
- Destination permission check: [TODO: compare effective destination permissions for next action; text is not a grant]

## Handoff accounting

- Chain and prior transfer: [TODO: chain ID, exact previous handoff UTC timestamp or no prior transfer; do not reset in destination]
- Trigger evidence: [TODO: measured ratio and independently observed degradation, or explicit request]
- Usage evidence: [TODO: exact source rollout identity and pre-handoff cumulative snapshot, or unavailable]
- Comparable baseline: [TODO: equivalent accepted-work baseline identity or unavailable; no unsupported savings claim]

## Completed and verified

- VERIFIED — [TODO: artifact or fact]; evidence: [TODO: command, result, or source]

## Unverified and open

- UNVERIFIED — [TODO: remaining gap or risk]

## Failures and discarded approaches

- [TODO: failure to avoid, or state that none were observed]

## Next action

[TODO: one concrete action]

## Destination sentinel

- [TODO: smallest read-only identity check]
- [TODO: smallest materially relevant artifact or test check]

## Recovery

- Source remains intact: [TODO: recovery location]
- Backup packet: [TODO: absolute path]
"""


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def assess(args: argparse.Namespace) -> int:
    if (args.used_tokens is None) != (args.context_window is None):
        raise SystemExit("--used-tokens and --context-window must be supplied together")
    if args.context_window is not None and args.context_window <= 0:
        raise SystemExit("--context-window must be positive")
    if args.used_tokens is not None and args.used_tokens < 0:
        raise SystemExit("--used-tokens cannot be negative")
    if args.minutes_since_handoff is not None and (not math.isfinite(args.minutes_since_handoff) or args.minutes_since_handoff < 0):
        raise SystemExit("--minutes-since-handoff must be finite and nonnegative")
    if args.compactions < 0 or args.degradation_signals < 0:
        raise SystemExit("counts cannot be negative")

    ratio = None
    if args.used_tokens is not None:
        ratio = args.used_tokens / args.context_window

    checkpoint_reasons: list[str] = []
    handoff_reasons: list[str] = []
    if ratio is not None and ratio >= 0.85:
        checkpoint_reasons.append(f"context usage is {ratio:.1%}")
        if ratio >= 0.95 and args.degradation_signals >= 1:
            handoff_reasons.append(f"context usage is {ratio:.1%} with observed degradation")
    if args.compactions > 0:
        checkpoint_reasons.append(f"{args.compactions} compactions observed")
        if args.compactions >= 3 and args.degradation_signals >= 1:
            handoff_reasons.append(f"{args.compactions} compactions with observed degradation")
    if args.degradation_signals >= 2:
        handoff_reasons.append(
            f"{args.degradation_signals} context-degradation signals observed"
        )
    elif args.degradation_signals == 1:
        checkpoint_reasons.append("1 context-degradation signal observed")
    if args.requested:
        handoff_reasons.append("user explicitly requested a handoff")

    authorized = args.requested or args.standing_authorization
    cooldown = (not args.requested and args.degradation_signals < 2 and
                (args.prior_handoff_unknown or
                 (args.minutes_since_handoff is not None and args.minutes_since_handoff < 60)))
    if handoff_reasons:
        if args.unsafe or cooldown:
            decision = "handoff-deferred"
        elif authorized:
            decision = "handoff-ready"
        else:
            decision = "handoff-needs-authorization"
    elif checkpoint_reasons:
        decision = "checkpoint"
    else:
        decision = "continue"

    emit(
        {
            "authorized": authorized,
            "cooldown_active": cooldown,
            "context_ratio": round(ratio, 4) if ratio is not None else None,
            "decision": decision,
            "handoff_reasons": handoff_reasons,
            "checkpoint_reasons": checkpoint_reasons,
            "unsafe_reasons": args.unsafe,
        }
    )
    return 0


def sections_from(text: str) -> dict[str, str]:
    headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    sections: dict[str, str] = {}
    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections[match.group(1)] = text[start:end].strip()
    return sections


def validate(args: argparse.Namespace) -> int:
    path = Path(args.packet).expanduser()
    if not path.is_file():
        emit({"valid": False, "errors": [f"packet is not a file: {path}"]})
        return 1

    text = path.read_text(encoding="utf-8")
    sections = sections_from(text)
    errors: list[str] = []
    warnings: list[str] = []

    if args.max_chars <= 0:
        errors.append("--max-chars must be positive")
    if re.search(r"\[TODO(?:[^]]*)\]", text, re.I):
        errors.append("one or more TODO placeholders remain")

    for required in REQUIRED_SECTIONS:
        content = sections.get(required, "")
        if not content:
            errors.append(f"missing or empty section: {required}")
        elif re.search(r"\[(?:fill|todo|tbd)(?:[^]]*)\]", content, re.I):
            errors.append(f"placeholder remains in section: {required}")

    verified = sections.get("Completed and verified", "")
    if verified and "VERIFIED" not in verified:
        errors.append("Completed and verified must mark supported items as VERIFIED")
    open_items = sections.get("Unverified and open", "")
    if open_items and "UNVERIFIED" not in open_items:
        errors.append("Unverified and open must mark remaining items as UNVERIFIED")

    communication = sections.get("Communication preferences", "")
    for label in ("Reply language", "Locale or time zone"):
        if communication and not re.search(
            rf"(?mi)^\s*-\s*{re.escape(label)}\s*:\s*\S.+$", communication
        ):
            errors.append(f"Communication preferences must include {label}: <value>")

    workspace = sections.get("Workspace identity", "")
    for label in ("Path", "Source workspace kind", "Destination compatibility"):
        if workspace and not re.search(
            rf"(?mi)^\s*-\s*{re.escape(label)}\s*:\s*\S.+$", workspace
        ):
            errors.append(f"Workspace identity must include {label}: <value>")

    lifecycle = sections.get("Source lifecycle", "")
    for label in (
        "Goal status",
        "Source archival authorization",
        "Source closure status",
    ):
        if lifecycle and not re.search(
            rf"(?mi)^\s*-\s*{re.escape(label)}\s*:\s*\S.+$", lifecycle
        ):
            errors.append(f"Source lifecycle must include {label}: <value>")

    goal_match = re.search(
        r"(?mi)^\s*-\s*Goal status\s*:\s*(active|paused|complete|blocked|none|unknown)\s*$",
        lifecycle,
    )
    if lifecycle and not goal_match:
        errors.append(
            "Source lifecycle Goal status must be active, paused, complete, blocked, none, or unknown"
        )

    for section, labels in {
        "Goal continuity": ("Objective", "Goal authorization", "Remaining budget", "Resume policy"),
        "Authorization and permissions": ("Authorized scope and evidence", "Pending approvals and exclusions", "Runtime permissions", "Destination permission check"),
        "Handoff accounting": ("Chain and prior transfer", "Trigger evidence", "Usage evidence", "Comparable baseline"),
    }.items():
        for label in labels:
            if not re.search(rf"(?mi)^\s*-\s*{re.escape(label)}\s*:\s*\S.*$", sections.get(section, "")):
                errors.append(f"{section} must include {label}: <value>")

    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"probable secret detected: {label}")

    if len(text) > args.max_chars:
        errors.append(
            f"packet has {len(text)} characters; limit is {args.max_chars}. "
            "Replace embedded history or logs with concise evidence pointers."
        )
    if len(text) < 400:
        warnings.append("packet is unusually short; confirm that constraints and evidence are complete")

    payload: dict[str, object] = {
        "characters": len(text),
        "errors": errors,
        "packet": str(path.resolve()),
        "valid": not errors,
        "warnings": warnings,
    }
    emit(payload)
    return 0 if not errors else 1


def template(args: argparse.Namespace) -> int:
    if not args.output:
        print(TEMPLATE, end="")
        return 0

    path = Path(args.output).expanduser()
    if not path.parent.is_dir():
        raise SystemExit(f"output directory does not exist: {path.parent}")
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(TEMPLATE)
    except FileExistsError as exc:
        raise SystemExit(f"refusing to overwrite existing file: {path}") from exc
    emit({"created": str(path.resolve())})
    return 0


def archive_plan(args: argparse.Namespace) -> int:
    blockers: list[str] = []
    if args.destination_regression:
        blockers.append("destination reported HANDOFF REGRESSION")
    elif not args.destination_verified:
        blockers.append("destination has not reported HANDOFF VERIFIED")
    if not args.goal_continuity_verified:
        blockers.append("destination Goal continuity is unverified")
    if not args.permissions_verified:
        blockers.append("required destination permissions are unverified")
    visibility_blockers = []
    if not args.destination_discoverable:
        visibility_blockers.append("destination task-inventory visibility is unverified")
    if not args.destination_opened:
        visibility_blockers.append("destination has not been successfully opened")
    if not args.destination_thread_id or not args.destination_thread_id.strip():
        visibility_blockers.append("surface-provided destination thread identifier is required")
    if not args.destination_location:
        visibility_blockers.append("destination local/cloud location is unverified")
    if args.destination_location == "local" and not (args.destination_host_id and args.destination_host_id.strip()):
        visibility_blockers.append("local destination host identifier is required")
    blockers.extend(visibility_blockers)
    if args.unsafe:
        blockers.extend(f"unsafe state: {reason}" for reason in args.unsafe)
    if not args.packet_available:
        blockers.append("validated recovery packet is unavailable")
    if not args.source_thread_id or not args.source_host_id:
        blockers.append("surface-provided source thread and host identifiers are required")
    if not args.already_archived:
        if not (args.authorized or args.standing_preference):
            blockers.append("source archival is not authorized")
        if not args.api_available:
            blockers.append("thread archival API is unavailable; use manual archive fallback")
        if not args.confirmation_available:
            blockers.append("source archival cannot be confirmed on this surface")

    goal_auto_resume_risk = args.goal_status in {"active", "unknown"}
    archived_confirmed = args.already_archived and not blockers
    if archived_confirmed:
        decision = "archive-confirmed"
        lifecycle_state = "SOURCE_ARCHIVED_CONFIRMED"
    elif not blockers:
        decision = "archive-ready"
        lifecycle_state = "SOURCE_ARCHIVE_READY"
    elif (
        args.destination_verified
        and not args.destination_regression
        and visibility_blockers
    ):
        decision = "handoff-visibility-unverified"
        lifecycle_state = "HANDOFF VISIBILITY UNVERIFIED"
    elif args.destination_verified and not args.destination_regression and goal_auto_resume_risk:
        decision = "handoff-verified-source-still-active"
        lifecycle_state = "HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE"
    elif args.destination_verified and not args.destination_regression:
        decision = "archive-skipped"
        lifecycle_state = "DESTINATION_VERIFIED"
    else:
        decision = "archive-skipped"
        lifecycle_state = "CHECKPOINTED"

    emit(
        {
            "archive": not blockers and not archived_confirmed,
            "archived_confirmed": archived_confirmed,
            "blockers": blockers,
            "decision": decision,
            "goal_auto_resume_risk": goal_auto_resume_risk,
            "goal_status": args.goal_status,
            "lifecycle_state": lifecycle_state,
            "manual_fallback_required": bool(blockers and goal_auto_resume_risk),
            "destination_location": args.destination_location,
            "destination_thread_id": args.destination_thread_id,
            "destination_host_id": args.destination_host_id,
            "visibility_verified": not visibility_blockers,
            "source_host_id": args.source_host_id,
            "source_thread_id": args.source_thread_id,
        }
    )
    return 0


def archive_result(args: argparse.Namespace) -> int:
    if args.destination_regression:
        emit(
            {
                "archived_confirmed": False,
                "decision": "archive-prohibited",
                "failure": "destination reported HANDOFF REGRESSION",
                "goal_status": args.goal_status,
                "lifecycle_state": "CHECKPOINTED",
                "manual_fallback_required": False,
                "source_auto_resume_risk": args.goal_status in {"active", "unknown"},
            }
        )
        return 0

    if not args.destination_verified:
        emit(
            {
                "archived_confirmed": False,
                "decision": "archive-prohibited",
                "failure": "destination has not reported HANDOFF VERIFIED",
                "goal_status": args.goal_status,
                "lifecycle_state": "CHECKPOINTED",
                "manual_fallback_required": False,
                "source_auto_resume_risk": args.goal_status in {"active", "unknown"},
            }
        )
        return 0

    archived_confirmed = args.archive_confirmed
    source_auto_resume_risk = (
        not archived_confirmed and args.goal_status in {"active", "unknown"}
    )
    failure = None if archived_confirmed else (
        args.failure or "archived state was not confirmed"
    )
    emit(
        {
            "archived_confirmed": archived_confirmed,
            "decision": (
                "archive-confirmed"
                if archived_confirmed
                else "handoff-verified-source-still-active"
            ),
            "failure": failure,
            "goal_status": args.goal_status,
            "lifecycle_state": (
                "SOURCE_ARCHIVED_CONFIRMED"
                if archived_confirmed
                else "HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE"
            ),
            "manual_fallback_required": not archived_confirmed,
            "source_auto_resume_risk": source_auto_resume_risk,
        }
    )
    return 0


def usage(args: argparse.Namespace) -> int:
    """Read token telemetry only; never emit transcript content or infer cache misses."""
    fields = FIELDS
    rows = []
    seen = set()
    for name in args.rollouts:
        path = Path(name).expanduser().resolve()
        if path in seen:
            raise SystemExit("duplicate rollout would double-count usage")
        seen.add(path)
        session_id = None
        data = None
        error = None
        try:
            with path.open(encoding="utf-8") as stream:
                first = json.loads(stream.readline())
            if first.get("type") == "session_meta":
                session_id = first.get("payload", {}).get("id")
            if not session_id:
                raise ValueError("missing session identity")
            data = snapshot(path, session_id)
        except (ValueError, OSError) as exc:
            error = str(exc)
        rows.append({"rollout": str(path), "session_id": session_id,
                     "cumulative_usage": data["usage"] if data else None,
                     "accounting_basis": data["accounting_basis"] if data else None,
                     "compactions": data["compactions"] if data else None,
                     "counter_reset": bool(error and "non-monotonic" in error),
                     "malformed_lines": None if error else 0, "error": error})
    identities = [row["session_id"] for row in rows if row["session_id"]]
    if len(identities) != len(set(identities)):
        raise SystemExit("duplicate session identity would double-count usage")
    reliable = bool(rows) and all(row["cumulative_usage"] and not row["counter_reset"] and not row["error"] for row in rows)
    totals = {k: sum(row["cumulative_usage"][k] for row in rows) if reliable and all(row["cumulative_usage"][k] is not None for row in rows) else None for k in fields}
    inp, cached = totals["input_tokens"], totals["cached_input_tokens"]
    totals["uncached_input_tokens"] = inp - cached if inp is not None and cached is not None and inp >= cached else None
    emit({"measurement": "observed cumulative usage; not incremental handoff cost", "sessions": rows,
          "totals": totals, "savings_percent": None, "savings_status": "unproven: no equivalent accepted-work control",
          "retries": None, "subagent_share": None, "billing_cost": None})
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Assess Codex context pressure and validate handoff packets."
    )
    commands = root.add_subparsers(dest="command", required=True)

    assess_parser = commands.add_parser("assess", help="classify context pressure")
    assess_parser.add_argument("--used-tokens", type=int)
    assess_parser.add_argument("--context-window", type=int)
    assess_parser.add_argument("--compactions", type=int, default=0)
    assess_parser.add_argument("--degradation-signals", type=int, default=0)
    assess_parser.add_argument("--minutes-since-handoff", type=float)
    assess_parser.add_argument("--prior-handoff-unknown", action="store_true")
    assess_parser.add_argument("--requested", action="store_true")
    assess_parser.add_argument("--standing-authorization", action="store_true")
    assess_parser.add_argument(
        "--unsafe",
        action="append",
        default=[],
        metavar="REASON",
        help="reason the current point is unsafe for transfer; repeat as needed",
    )
    assess_parser.set_defaults(run=assess)

    template_parser = commands.add_parser("template", help="emit a packet skeleton")
    template_parser.add_argument("--output", help="create this new file; never overwrite")
    template_parser.set_defaults(run=template)

    validate_parser = commands.add_parser("validate", help="validate a completed packet")
    validate_parser.add_argument("packet")
    validate_parser.add_argument("--max-chars", type=int, default=12_000)
    validate_parser.set_defaults(run=validate)

    archive_parser = commands.add_parser(
        "archive-plan", help="check whether optional source archival is safe"
    )
    destination = archive_parser.add_mutually_exclusive_group()
    destination.add_argument("--destination-verified", action="store_true")
    destination.add_argument("--destination-regression", action="store_true")
    archive_parser.add_argument(
        "--destination-discoverable",
        action="store_true",
        help="exact destination identity was confirmed in its local/cloud task inventory; pinning or opting out is insufficient",
    )
    archive_parser.add_argument("--destination-opened", action="store_true")
    archive_parser.add_argument("--destination-thread-id")
    archive_parser.add_argument("--destination-location", choices=("local", "cloud"))
    archive_parser.add_argument("--destination-host-id")
    archive_parser.add_argument("--goal-continuity-verified", action="store_true")
    archive_parser.add_argument("--permissions-verified", action="store_true")
    archive_parser.add_argument("--packet-available", action="store_true")
    archive_parser.add_argument("--source-thread-id")
    archive_parser.add_argument("--source-host-id")
    archive_parser.add_argument(
        "--goal-status",
        choices=("active", "paused", "complete", "blocked", "none", "unknown"),
        required=True,
    )
    archive_parser.add_argument("--authorized", action="store_true")
    archive_parser.add_argument("--standing-preference", action="store_true")
    archive_parser.add_argument("--api-available", action="store_true")
    archive_parser.add_argument("--confirmation-available", action="store_true")
    archive_parser.add_argument("--already-archived", action="store_true")
    archive_parser.add_argument("--unsafe", action="append", default=[])
    archive_parser.set_defaults(run=archive_plan)

    result_parser = commands.add_parser(
        "archive-result", help="classify the observed source archival result"
    )
    result_destination = result_parser.add_mutually_exclusive_group()
    result_destination.add_argument("--destination-verified", action="store_true")
    result_destination.add_argument("--destination-regression", action="store_true")
    result_parser.add_argument(
        "--goal-status",
        choices=("active", "paused", "complete", "blocked", "none", "unknown"),
        required=True,
    )
    observed_result = result_parser.add_mutually_exclusive_group()
    observed_result.add_argument("--archive-confirmed", action="store_true")
    observed_result.add_argument("--failure")
    result_parser.set_defaults(run=archive_result)

    usage_parser = commands.add_parser("usage", help="read actual usage from exact named rollout files; no savings inference")
    usage_parser.add_argument("rollouts", nargs="+")
    usage_parser.set_defaults(run=usage)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
