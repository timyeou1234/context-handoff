#!/usr/bin/env python3
"""Assess context pressure and validate a loss-resistant Codex handoff packet."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = (
    "Goal",
    "Acceptance criteria",
    "Communication preferences",
    "Applicable constraints",
    "Workspace identity",
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
- Repository or artifact: [TODO: identity]
- Branch and HEAD, or equivalent identity: [TODO: identity]
- Working-state summary and hash when applicable: [TODO: state]

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
    if args.compactions < 0 or args.degradation_signals < 0:
        raise SystemExit("counts cannot be negative")

    ratio = None
    if args.used_tokens is not None:
        ratio = args.used_tokens / args.context_window

    checkpoint_reasons: list[str] = []
    handoff_reasons: list[str] = []
    if ratio is not None:
        if ratio >= 0.85:
            handoff_reasons.append(f"context usage is {ratio:.1%}")
        elif ratio >= 0.70:
            checkpoint_reasons.append(f"context usage is {ratio:.1%}")
    if args.compactions >= 2:
        handoff_reasons.append(f"{args.compactions} compactions observed")
    elif args.compactions == 1:
        checkpoint_reasons.append("1 compaction observed")
    if args.degradation_signals >= 2:
        handoff_reasons.append(
            f"{args.degradation_signals} context-degradation signals observed"
        )
    elif args.degradation_signals == 1:
        checkpoint_reasons.append("1 context-degradation signal observed")
    if args.requested:
        handoff_reasons.append("user explicitly requested a handoff")

    authorized = args.requested or args.standing_authorization
    if handoff_reasons:
        if args.unsafe:
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
    if not args.destination_verified:
        blockers.append("destination has not reported HANDOFF VERIFIED")
    if args.unsafe:
        blockers.extend(f"unsafe state: {reason}" for reason in args.unsafe)
    if not args.packet_available:
        blockers.append("validated recovery packet is unavailable")
    if not args.source_thread_id or not args.source_host_id:
        blockers.append("surface-provided source thread and host identifiers are required")
    if not (args.authorized or args.standing_preference):
        blockers.append("source archival is not authorized")
    if not args.api_available:
        blockers.append("thread archival API is unavailable; use manual archive fallback")

    emit(
        {
            "archive": not blockers,
            "blockers": blockers,
            "decision": "archive-ready" if not blockers else "archive-skipped",
            "source_host_id": args.source_host_id,
            "source_thread_id": args.source_thread_id,
        }
    )
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
    archive_parser.add_argument("--destination-verified", action="store_true")
    archive_parser.add_argument("--packet-available", action="store_true")
    archive_parser.add_argument("--source-thread-id")
    archive_parser.add_argument("--source-host-id")
    archive_parser.add_argument("--authorized", action="store_true")
    archive_parser.add_argument("--standing-preference", action="store_true")
    archive_parser.add_argument("--api-available", action="store_true")
    archive_parser.add_argument("--unsafe", action="append", default=[])
    archive_parser.set_defaults(run=archive_plan)

    return root


def main() -> int:
    args = parser().parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
