# Context Handoff for Codex

`context-handoff` is a Codex skill for moving an in-progress task into a genuinely fresh thread when context pressure threatens continuity. It preserves acceptance criteria, verified evidence, workspace identity, open risks, and the next action instead of copying the full conversation.

The skill is designed to reduce token cost without lowering the quality floor. A destination thread must verify a small workspace and artifact sentinel before it continues. Any mismatch stops with `HANDOFF REGRESSION`.

## What it does

- Uses proportional context thresholds instead of a fixed token count.
- Creates checkpoints at 70% usage, one compaction, or one observed degradation signal.
- Prepares a fresh-thread handoff at 85% usage, two compactions, two degradation signals, or an explicit request.
- Defers transfer while mutations, tests, builds, uploads, or destructive actions are active.
- Validates required handoff sections, verification labels, size, and common secret patterns.
- Uses a fresh Codex thread rather than a full-history fork when thread tools and authorization are available.
- Falls back to a validated, copyable packet when automatic thread creation is unavailable.
- Can optionally archive the source thread as a recoverable second phase, but only after `HANDOFF VERIFIED`, with real surface-provided IDs and explicit or standing user authorization.

It runs only during an active Codex turn; it is not a background context monitor.

## Install

Ask Codex to install the skill from:

```text
https://github.com/timyeou1234/context-handoff/tree/main/skills/context-handoff
```

Or use the bundled Codex installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo timyeou1234/context-handoff \
  --path skills/context-handoff
```

The skill becomes available on the next Codex turn.

To test the complete plugin from this checkout:

```bash
codex plugin marketplace add /absolute/path/to/context-handoff
codex plugin add context-handoff@context-handoff-local
```

Start a fresh Codex chat after installation so the new skill catalog is loaded. This local marketplace is for development and does not indicate acceptance in the public Plugins Directory.

## Use

Invoke it directly:

```text
Use $context-handoff to checkpoint this task and continue it in a fresh verified thread.
```

For automatic switching, add standing authorization to the applicable global `AGENTS.md`. The included skill still requires a safe checkpoint and destination validation before continuing.

Source task/chat archival is separately opt-in. Codex surfaces may call the source a task or chat; the skill uses the supported thread-level archival capability and the real surface-provided identity. It never runs on a regression, unsafe state, missing recovery packet, missing identifiers, unsupported API, or failed verification. On unsupported surfaces, the skill reports the source identity when available and leaves archival as a manual user action. Archival is recoverable and is never described as deletion.

The deterministic preflight can be inspected with `scripts/context_handoff.py archive-plan`; it reports `archive-ready` only when verification, recovery, identifiers, authorization, safe state, and API availability all pass. The skill performs the actual archive through the surface's thread-management capability, not through this local script.

## Contents

- `skills/context-handoff/SKILL.md` — workflow and safety contract.
- `skills/context-handoff/scripts/context_handoff.py` — deterministic assessment, packet template, and validator.
- `skills/context-handoff/agents/openai.yaml` — Codex skill metadata.
- `.codex-plugin/plugin.json` — skills-only plugin manifest and listing metadata.
- `.agents/plugins/marketplace.json` — repo-local marketplace used for clean-install testing.
- `docs/SUBMISSION.md` and `docs/REVIEWER_TESTS.md` — portal copy, user-only steps, and reproducible reviewer cases.

## License

MIT. This is an independent community project and is not an official OpenAI product.
