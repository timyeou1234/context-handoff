# Context Handoff for Codex

Current release: **0.3.7**.

OpenAI public directory status (2026-10-15): the published listing remains **0.3.4**. The 0.3.5 update was uploaded, but the portal blocked submission because the package contains lifecycle hooks and skills-only submissions are currently unavailable. Version 0.3.6 adds the supported `interface.supportURL` field to address a separate metadata finding. Hooks and acceptance criteria are preserved; GitHub releases and local marketplace updates do not imply public publication.

`context-handoff` is a Codex plugin and skill for moving an in-progress task into a genuinely fresh thread when context pressure threatens continuity. The complete plugin uses a local lifecycle hook to detect root-session compaction before the next model continuation, then the skill preserves the reply language, acceptance criteria, verified evidence, workspace identity, open risks, and the next action instead of copying the full conversation.

The skill aims to improve continuity without lowering the quality floor. General token or monetary savings are not guaranteed; the local paired E2E measurement below records one observed workflow improvement and its limits. A destination thread must verify a small workspace and artifact sentinel before it continues. Any mismatch stops with `HANDOFF REGRESSION`.

## What it does

- Uses proportional context thresholds instead of a fixed token count.
- Automatically records compaction through a plugin-bundled `SessionStart(source=compact)` hook.
- Emits health checks at the first/third compaction and every eight subsequent user turns, avoiding reminders on every message.
- Creates checkpoints at 85% usage, any compaction, or one observed degradation signal; reuses unchanged checkpoints.
- Prepares handoff at 95% usage plus degradation, three compactions plus degradation, two independent failures, or explicit request; applies a 60-minute chain cooldown.
- Defers transfer while mutations, tests, builds, uploads, or destructive actions are active.
- Preserves the reply language across the fresh-thread handshake without inventing locale or time-zone preferences.
- Validates required handoff sections, verification labels, size, and common secret patterns.
- Uses a fresh Codex thread rather than a full-history fork when thread tools and authorization are available.
- Preflights exact working-directory compatibility before creating a destination; another worktree or checkout is not treated as equivalent merely because it belongs to the same saved project.
- Treats workspace isolation as a routing boundary: it never loops on approval requests to read the source checkout or source-side recovery packet.
- Makes destinations discoverable without pinning: assigns a concise handoff title, verifies the exact local/cloud task-inventory identity, and successfully opens the task before source archival.
- Reports `HANDOFF VISIBILITY UNVERIFIED` and keeps the source recoverable when listing or opening fails. Local task visibility does not imply cloud mirroring or mobile Remote connectivity.
- Falls back to a validated, copyable packet when automatic thread creation is unavailable.
- Completes authorized source archival as a recoverable closure phase, but only after `HANDOFF VERIFIED`, with real surface-provided IDs and explicit or standing user authorization.
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

### Update an existing local installation

Update the configured marketplace source to the desired release, then reinstall the plugin from that marketplace so the cache contains the new version:

```bash
codex plugin add context-handoff@context-handoff-local
codex plugin list --marketplace context-handoff-local --json
```

Check that the installed version is `0.3.7`. A standalone skill installation is separate: update the full `skills/context-handoff/` directory, including both scripts and agent metadata. Do not copy only `SKILL.md`. Restart the desktop app if it still shows the previous local version; review any changed hook trust prompt in `/hooks`. Local installation and a GitHub release do not establish public Plugins Directory approval or publication.

## Use

Invoke it directly:

```text
Use $context-handoff to checkpoint this task and continue it in a fresh verified thread.
```

For automatic switching after detection, add standing authorization to the applicable global `AGENTS.md`. Detection never bypasses a safe checkpoint or destination validation.

Source task/chat archival requires per-transfer or standing authorization; an applicable standing preference must be executed without asking again. Codex surfaces may call the source a task or chat; the skill records whether its Goal is active, complete, blocked, absent, or unknown, then uses the supported thread-level archival capability and the real surface-provided identity. It never runs on a regression, unsafe state, missing recovery packet, missing identifiers, unsupported API, unavailable confirmation, or failed verification. On unsupported surfaces, the skill reports `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, warns that an unfinished Goal may auto-resume, identifies the source when available, and leaves archival as a manual user action. Archival is recoverable and is never described as deletion.

The deterministic preflight can be inspected with `scripts/context_handoff.py archive-plan`; it requires `--goal-status` and reports `archive-ready` only when verification, recovery, identifiers, authorization, safe state, API availability, and confirmation capability all pass. After the surface archival call, `archive-result` maps observed confirmation to `SOURCE_ARCHIVED_CONFIRMED`; failure or missing confirmation maps to `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`. The skill performs the actual archive through the surface's thread-management capability, not through this local script.

Fresh-thread creation also has a workspace-routing preflight. If the surface cannot place the destination in the exact source directory without elevated approval—for example, when the source is in a different Codex worktree—the plugin leaves the source checkpoint intact and returns `HANDOFF NEEDS COMPATIBLE WORKSPACE` with a complete copyable packet. The temporary packet path is recovery information for the source only; the destination receives the packet inline and must not request approval to open that file or the source worktree.

After creation, the plugin gives the destination a recognizable `Handoff: <goal>` title without pinning it. It reads the correct local/cloud task inventory, verifies the returned identity and title (including host for local tasks), opens that exact task, and records evidence before source archival. Missing listing/opening evidence produces `HANDOFF VISIBILITY UNVERIFIED` and preserves the source. The user receives the verified location and a supported link/task entry. This verifies availability at handoff time; it does not promise mirroring, access from an unchecked device, or availability after host disconnection. Cloud creation requires explicit user authorization and compatible workspace support.

```bash
python3 skills/context-handoff/scripts/context_handoff.py archive-plan \
  --destination-verified --destination-discoverable --destination-opened \
  --destination-thread-id destination-real-123 --destination-location local \
  --destination-host-id local --goal-continuity-verified --permissions-verified --packet-available \
  --source-thread-id <real-id> --source-host-id <real-id> \
  --goal-status active --authorized \
  --api-available --confirmation-available
```

## Local E2E measurement (2026-10-14)

One paired local test compared the frozen workflow before and after the coordination changes. Both accepted handoffs passed the same identity, contract, effective-permission, artifact write/read-back, Goal-state, visibility, unpinned-state, opening, recoverability, and independently confirmed source-archival gates. The regression suite also passed all 36 tests (30 existing and 6 added).

Both pairs used fresh source chats with the same task contract and source prompt except for the frozen implementation path. All four chats used GPT-6 Astra with high reasoning effort and the same permission settings. Initial source inputs were 35,636 and 35,631 tokens. Each handoff total includes its source through archival and its destination through the completed final response; cumulative samples are never added together.

| Observed metric | Before | After |
| --- | ---: | ---: |
| Total tokens | 1,614,078 | 1,219,432 |
| Cached input tokens | 1,471,488 | 1,115,904 |
| Uncached input tokens | 127,531 | 90,431 |
| Output tokens | 15,059 | 13,097 |
| Reasoning tokens (included in output) | 852 | 440 |
| Usage-advancing rounds | 29 | 23 |

The accepted handoff used **394,646 fewer tokens (24.45%)** in this pair. The changes support both tool-record formats, correlate Goal results with their calls, locate the exact rollout after archival, and guide bounded coordination, filtered evidence reads, and reports generated from one result object.

One-time costs are separate from the per-handoff comparison:

| Experimental work | Observed tokens |
| --- | ---: |
| Repairs, regression tests, initial setup and first dispatch | 1,118,661 |
| Failed preliminary packet-format trial | 359,067 |
| Parent observation, coordination and settlement | 4,373,520 |
| Both accepted handoffs | 2,833,510 |
| Entire observed experiment | 8,684,758 |

The preliminary failure remains in experiment costs but is excluded from the accepted baseline, so it does not inflate the reported reduction. Parent accounting ends at 2026-10-14 14:05:36.810 UTC and excludes later report generation, checks and replies; both accepted handoffs have completed-session accounting. The experiment has not demonstrated payback of its one-time costs.

This is one observed pair, not a guaranteed reduction or a comparison of handoff against continuing without handoff. Cache warmth, scheduling and model variability were not fully controlled; no monetary savings are inferred. Both native Goals were absent, so active-Goal restoration was not exercised. Only local task visibility was tested, with no cloud or other-device claim. The earlier long-history run included repairs and is not this comparison's control.

See the [sanitized measurement data](docs/benchmarks/2026-10-14-local-e2e.json) for counters, cutoffs, frozen skill hashes, acceptance coverage and limitations. A repeat should keep the same contract and gates, freeze both implementations, use fresh sources with matched model/settings, and account for both sessions, failures and experimental overhead separately.

## Compaction accounting repair and local rerun (2026-10-15)

Version 0.3.7 fixes both usage helpers. The previous native hook trace contained **141,422 tokens**, while legacy `event_msg.token_count` reported **123,139**: **18,283 compaction tokens were omitted**. Both commands now share a parser that prefers `token_usage_record.thread_token_usage`, keeps legacy and ledger counters separate, rejects mixed-basis intervals and counter resets, and preserves unknown optional fields. Legacy-only telemetry with compaction cannot establish complete cost.

All **40 regression tests** passed (the existing 36 plus four accounting regressions). A frozen local 0.3.7 installation passed the original contract, identity, effective-permission, Goal-null, visibility, opening, unpinned, recoverability, source-final-archive and independent archival-readback gates. Native compaction/hooks passed through a separate official local App Server trace; this is not a single desktop compact-to-handoff trace. SessionStart and UserPromptSubmit have successful runtime events; SessionEnd cleanup is evidenced by removal of the exact state file after process exit, without a retained completion event. Active Goal restoration and cloud/mobile visibility remain untested.

The previous controller's **7,858,997 tokens** came from **40 model requests**, averaging **195,863 input tokens** per request (maximum 224,489). Input totaled 7,834,528, including 7,751,424 cached tokens (**98.94%**); output was 24,469. Its tool batches included 13 waits, four documentation searches/fetches and 38 shell calls. A batched request does not establish the marginal cost of each nested tool. Repeated long-history input, including cached input, dominates the total.

The rerun reused the verified API/runtime path and preflight, retained required independent checks, and used deterministic ledger aggregation and report read-back. No implementation changed during measurement. Repair and release preparation are separate from test and handoff costs:

| Category | Previous 0.3.6 run | This 0.3.7 run |
| --- | ---: | ---: |
| One-time repair, regression, installation and documentation | 0 (defect left unfixed) | 1,204,310 |
| Test preparation and controller verification | 8,261,515 | 1,627,986 |
| Of which: controller | 7,858,997 | 1,243,244 |
| Handoff and archival, including completed destination | 1,785,655 | 1,389,487 |
| Entire observed run, including current repair | 10,047,170 | 4,221,783 |

Controller usage was **6,615,753 tokens lower (84.18%)**; including the current repair, the observed total was **5,825,387 tokens lower (57.98%)**. The new controller used 14 requests averaging 87,822 input tokens. These are observed differences, **not proven causal savings**: functional gates and GPT-6 Astra/high were retained, but the controller's starting history had been compacted, prompts were streamlined, and cache/scheduling differed. The old run's accounting defect is corrected from its raw ledger in this table.

Repair accounting ends at **2026-10-15T13:15:38.499Z**; test controller accounting ends at **2026-10-15T13:14:31.067Z**. Subsequent release operations and final user-facing reporting are excluded. Source and destination costs are disjoint from controller costs; cached input and reasoning are subsets, not additional tokens. See the [sanitized complete counters, phase boundaries and acceptance evidence](docs/benchmarks/2026-10-15-local-0.3.7.json).

## Release automation

The `Package and release plugin` GitHub Actions workflow runs the test suite, verifies that a `v*` tag matches `.codex-plugin/plugin.json`, creates a complete top-level `context-handoff/` ZIP plus SHA-256 file, uploads both as workflow artifacts, and creates a GitHub Release for tag-triggered runs. It can also be started manually to build submission artifacts without creating a release.

OpenAI Plugins Directory updates still require a new version in the OpenAI Platform submission portal. Policy attestations, review, and the post-approval Publish action are intentionally not automated.

## Contents

- `skills/context-handoff/SKILL.md` — workflow and safety contract.
- `skills/context-handoff/scripts/context_handoff.py` — deterministic assessment, packet template, and validator.
- `skills/context-handoff/scripts/handoff_evidence.py` — exact-session Goal evidence, archive-aware telemetry snapshots, and interval accounting.
- `skills/context-handoff/agents/openai.yaml` — Codex skill metadata.
- `hooks/hooks.json` and `hooks/context_health.py` — trusted local compaction detector and minimal per-session state.
- `.codex-plugin/plugin.json` — plugin manifest and listing metadata.
- `.agents/plugins/marketplace.json` — repo-local marketplace used for clean-install testing.
- `docs/SUBMISSION.md` and `docs/REVIEWER_TESTS.md` — portal copy, user-only steps, and reproducible reviewer cases.

## License

MIT. This is an independent community project and is not an official OpenAI product.

### Continuity and measurement

Packets require Goal objective, authorization evidence, remaining budget, runtime permission checks and chain accounting. Destination verification includes Goal read-back and effective permissions. A session approval is not copied by prompt text. Unsupported restoration leaves the source recoverable with a precise limitation.

`python3 skills/context-handoff/scripts/context_handoff.py usage <exact-rollout.jsonl> [...]` reports actual cumulative token counters; missing data stays null. Capture before/after snapshots for incremental transfer overhead. No savings percentage is reported without an equivalent accepted-work control; the command does not compute billing cost or infer retries/subagent usage.
