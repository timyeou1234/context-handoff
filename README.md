# Context Handoff for Codex

`context-handoff` is a Codex plugin and skill for moving an in-progress task into a genuinely fresh thread when context pressure threatens continuity. The complete plugin uses a local lifecycle hook to detect root-session compaction before the next model continuation, then the skill preserves the reply language, acceptance criteria, verified evidence, workspace identity, open risks, and the next action instead of copying the full conversation.

The skill is designed to reduce token cost without lowering the quality floor. A destination thread must verify a small workspace and artifact sentinel before it continues. Any mismatch stops with `HANDOFF REGRESSION`.

## What it does

- Uses proportional context thresholds instead of a fixed token count.
- Automatically records compaction through a plugin-bundled `SessionStart(source=compact)` hook.
- Repeats the context-health instruction on later user turns after compaction, so detailed summaries do not silently disable assessment.
- Creates checkpoints at 70% usage, one compaction, or one observed degradation signal.
- Prepares a fresh-thread handoff at 85% usage, two compactions, two degradation signals, or an explicit request.
- Defers transfer while mutations, tests, builds, uploads, or destructive actions are active.
- Preserves the reply language across the fresh-thread handshake without inventing locale or time-zone preferences.
- Validates required handoff sections, verification labels, size, and common secret patterns.
- Uses a fresh Codex thread rather than a full-history fork when thread tools and authorization are available.
- Falls back to a validated, copyable packet when automatic thread creation is unavailable.
- Can optionally archive the source thread as a recoverable second phase, but only after `HANDOFF VERIFIED`, with real surface-provided IDs and explicit or standing user authorization.
- Records the source Goal state and confirms source archival, preventing an unfinished Goal from silently auto-resuming after a verified handoff.

The hook and skill run only during the Codex lifecycle; they do not run while Codex is idle. The hook detects and injects the health check, while the skill performs the safe checkpoint and verified transfer.

## Install

For automatic compaction detection, install the complete plugin. From this repository checkout:

```bash
codex plugin marketplace add /absolute/path/to/context-handoff
codex plugin add context-handoff@context-handoff-local
```

Start a fresh Codex chat, open `/hooks`, and trust the Context Handoff hook definition. Codex intentionally skips new or changed non-managed hooks until the user reviews and trusts their exact hash.

The skill can also be installed without lifecycle hooks from:

```text
https://github.com/timyeou1234/context-handoff/tree/main/skills/context-handoff
```

Or use the bundled Codex installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo timyeou1234/context-handoff \
  --path skills/context-handoff
```

The skill-only installation becomes available on the next Codex turn but cannot automatically observe compaction. The local marketplace is for development and does not indicate acceptance in the public Plugins Directory.

## Use

Invoke it directly:

```text
Use $context-handoff to checkpoint this task and continue it in a fresh verified thread.
```

For automatic switching after detection, add standing authorization to the applicable global `AGENTS.md`. Detection never bypasses a safe checkpoint or destination validation.

Source task/chat archival is separately opt-in. Codex surfaces may call the source a task or chat; the skill records whether its Goal is active, complete, blocked, absent, or unknown, then uses the supported thread-level archival capability and the real surface-provided identity. It never runs on a regression, unsafe state, missing recovery packet, missing identifiers, unsupported API, unavailable confirmation, or failed verification. On unsupported surfaces, the skill reports `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, warns that an unfinished Goal may auto-resume, identifies the source when available, and leaves archival as a manual user action. Archival is recoverable and is never described as deletion.

The deterministic preflight can be inspected with `scripts/context_handoff.py archive-plan`; it requires `--goal-status` and reports `archive-ready` only when verification, recovery, identifiers, authorization, safe state, API availability, and confirmation capability all pass. After the surface archival call, `archive-result` maps observed confirmation to `SOURCE_ARCHIVED_CONFIRMED`; failure or missing confirmation maps to `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`. The skill performs the actual archive through the surface's thread-management capability, not through this local script.

```bash
python3 skills/context-handoff/scripts/context_handoff.py archive-plan \
  --destination-verified --packet-available \
  --source-thread-id <real-id> --source-host-id <real-id> \
  --goal-status active --authorized \
  --api-available --confirmation-available
```

## Release automation

The `Package and release plugin` GitHub Actions workflow runs the test suite, verifies that a `v*` tag matches `.codex-plugin/plugin.json`, creates a complete top-level `context-handoff/` ZIP plus SHA-256 file, uploads both as workflow artifacts, and creates a GitHub Release for tag-triggered runs. It can also be started manually to build submission artifacts without creating a release.

OpenAI Plugins Directory updates still require a new version in the OpenAI Platform submission portal. Policy attestations, review, and the post-approval Publish action are intentionally not automated.

## Contents

- `skills/context-handoff/SKILL.md` — workflow and safety contract.
- `skills/context-handoff/scripts/context_handoff.py` — deterministic assessment, packet template, and validator.
- `skills/context-handoff/agents/openai.yaml` — Codex skill metadata.
- `hooks/hooks.json` and `hooks/context_health.py` — trusted local compaction detector and minimal per-session state.
- `.codex-plugin/plugin.json` — plugin manifest and listing metadata.
- `.agents/plugins/marketplace.json` — repo-local marketplace used for clean-install testing.
- `docs/SUBMISSION.md` and `docs/REVIEWER_TESTS.md` — portal copy, user-only steps, and reproducible reviewer cases.

## License

MIT. This is an independent community project and is not an official OpenAI product.
