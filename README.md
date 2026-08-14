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

## Use

Invoke it directly:

```text
Use $context-handoff to checkpoint this task and continue it in a fresh verified thread.
```

For automatic switching, add standing authorization to the applicable global `AGENTS.md`. The included skill still requires a safe checkpoint and destination validation before continuing.

## Contents

- `skills/context-handoff/SKILL.md` — workflow and safety contract.
- `skills/context-handoff/scripts/context_handoff.py` — deterministic assessment, packet template, and validator.
- `skills/context-handoff/agents/openai.yaml` — Codex skill metadata.

## License

MIT. This is an independent community project and is not an official OpenAI product.
