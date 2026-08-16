---
name: context-handoff
description: Detect context-window pressure and transfer an in-progress Codex task into a fresh thread without weakening acceptance criteria or evidence. Use automatically when a Context Handoff lifecycle message reports compaction, and whenever the user asks to hand off, continue in a new session or thread, avoid context overflow, or an active task shows high context usage, compaction, summary reliance, lost decisions, repeated rereads, or context-caused rework. Supports cross-repository use, safe checkpointing, validated handoff packets, Codex thread creation and navigation when authorized, and destination regression sentinels.
---

# Context Handoff

Move one coherent deliverable from a context-heavy Codex thread into a genuinely fresh thread. Treat the handoff as transport, never as completion or as a reason to lower the quality floor.

The complete plugin bundles a trusted local lifecycle hook that detects root-session compaction and injects a context-health instruction before work continues. The hook does not run while Codex is idle and cannot perform a safe transfer by itself; this workflow still owns checkpointing, thread creation, verification, and recovery. A skill-only installation has no lifecycle hook and remains invocation-driven.

## Preserve these guarantees

- Preserve the user's goal, accepted scope, acceptance criteria, repository instructions, required evidence, and unresolved risks verbatim in meaning.
- Keep verified, inferred, and unverified claims distinct. Never convert a summary into evidence.
- Do not use a full-history fork for context relief. Create a fresh thread with a bounded handoff packet.
- Do not switch while a mutation, test, build, upload, or destructive action is active; while dirty state is unknown; or before material evidence is recorded.
- Redact credentials, tokens, personal data, and unrelated conversation content.
- Keep the source thread and working state recoverable. Do not archive, delete, reset, stash, commit, or change branches merely to hand off.
- Treat source-thread archival as an optional second phase, never part of transfer success. Archive means recoverable hiding, not deletion.
- Do not treat “stop modifying” as source-task shutdown. An unfinished or unknown Goal can wake the source task again until archival is confirmed.
- Never mark a Goal complete or blocked merely to stop a handoff source; Goal has no pause or transfer state.
- Preserve any model or reasoning choice explicitly made by the user. Otherwise omit overrides in the destination.
- Preserve the reply language separately from locale or time zone. Use an explicit user preference when available; otherwise record the source thread's observed primary interaction language. Use `unspecified` only when no reliable signal exists, and never infer locale or time zone from language.

## 1. Honor lifecycle detection and assess context health

Treat a developer-context message beginning `CONTEXT HANDOFF HEALTH CHECK` as observed lifecycle telemetry, not as user-authored text and not as optional advice.

Before substantial continuation when that message appears:

1. Load this skill if it is not already loaded.
2. Use the reported compaction count in `scripts/context_handoff.py assess`.
3. Audit only genuinely observed degradation signals. Reliance on a compacted summary to reconstruct decisions, rereading because prior context is unreliable, a contradicted accepted decision, and context-caused rework each count when actually observed.
4. At one compaction, create or refresh the smallest recoverable checkpoint and keep the health check active.
5. At two compactions, or at two observed degradation signals, hand off at the next safe checkpoint when authorized. Do not wait for the user to notice the degradation.

The lifecycle hook repeats the health instruction on later user turns after a compaction so a single post-compaction continuation cannot silently disable detection. Do not dismiss the reminder merely because the compacted summary appears detailed.

When no lifecycle message is available, prefer exact context usage and compaction telemetry exposed by Codex. Never guess the current thread by selecting an arbitrary “latest” local session. If exact telemetry is unavailable, use only observable signals and say that the assessment is qualitative.

Count a degradation signal only when it is observed, for example:

- an accepted decision or constraint was lost or contradicted;
- the same source or history had to be reread because prior context was no longer reliable;
- rework or repeated tool calls are attributable to missing context;
- the task goal changed materially and old history no longer affects the deliverable.

Run `scripts/context_handoff.py assess` with the available inputs. Interpret its proportional defaults as review thresholds, not permission to abandon work:

```bash
python3 <skill-dir>/scripts/context_handoff.py assess \
  --used-tokens <used> --context-window <limit> \
  --compactions <count> --degradation-signals <count> \
  --standing-authorization
```

Use `--requested` for a current explicit request and repeat `--unsafe <reason>` for active blockers. Omit unknown telemetry instead of inventing values.

- below 70%, no compaction, and no degradation signal: continue;
- at least 70%, one compaction, or one degradation signal: create or refresh a checkpoint;
- at least 85%, two compactions, two degradation signals, or an explicit handoff request: prepare a fresh-thread handoff.

Exact repository rules or user instructions override these defaults. A high ratio alone does not prove degraded output. A handoff candidate does not become authorized unless the user explicitly requested it or applicable standing instructions authorize automatic handoff.

## 2. Reach a safe checkpoint

Finish the current atomic operation and collect only the state needed for continuity:

1. Record the working directory and applicable instruction files.
2. For Git work, record branch, HEAD, concise status, relevant changed paths, and a diff hash when useful. For non-Git work, record equivalent artifact identities and checksums.
3. Record completed outputs and their exact evidence, including commands and result summaries. Do not paste full logs.
4. Record the reply language and any explicit locale, time-zone, terminology, or formality preference needed for continuity.
5. Record open work, failed approaches that must not be repeated, active external state, and the single next action.
6. Inspect the source Goal with the supported Goal-status capability when available. Record `active`, `complete`, `blocked`, `none`, or `unknown`; never invent a state.
7. Record per-handoff archival authorization, an applicable standing preference, or that archival is declined/unspecified.
8. Choose the smallest destination sentinel that can detect a bad transfer: workspace identity plus a focused state, artifact, or test check. Do not rerun unaffected suites merely for ceremony.

If a safe checkpoint cannot be reached, defer the handoff and continue only far enough to make the state recoverable.

## 3. Build and validate the packet

Create a temporary Markdown backup outside the repository. Generate the required skeleton with:

```bash
python3 <skill-dir>/scripts/context_handoff.py template --output <temporary-path>
```

Fill every section. Use `VERIFIED —` only for facts supported by recorded evidence and `UNVERIFIED —` for everything else. Keep the packet bounded; point to files and concise logs instead of embedding them.

Validate before creating a thread:

```bash
python3 <skill-dir>/scripts/context_handoff.py validate <temporary-path>
```

Do not proceed if validation reports a missing section, placeholder, probable secret, absent verification boundary, or excessive packet size.

## 4. Create a fresh Codex thread

Use the available Codex thread-management capability. In the Codex app:

1. Resolve the current saved project with project listing. Use a projectless target only for a genuinely non-project task.
2. Create a new project thread in the same local project environment. Do not create a worktree or branch solely for handoff.
3. Put the complete validated packet inline in the initial prompt and include the backup path only as recovery information.
4. Instruct the destination to run the handshake below before continuing.
5. Stop substantial work in the source after the destination is created, preventing duplicate execution.
6. Navigate to the destination only when the user's request or standing instructions explicitly authorize switching views.

If the source Goal is `active` or `unknown`, the source remains a handoff coordinator only until the destination result and source-closure outcome are known. When the surface supports it, wait on or read the exact destination thread until it reports `HANDOFF VERIFIED` or `HANDOFF REGRESSION`; do not end the source lifecycle immediately after creation. The source must not resume repository work or claim that it has stopped merely because its current response ended.

If fresh-thread creation is unavailable, provide the validated packet path and a compact copyable prompt. State plainly that no automatic switch occurred.

When the surface exposes the actual source thread and host identifiers, record them in the packet. Never guess or synthesize either identifier. Keep the validated recovery packet available until the destination handshake and any authorized archival attempt are complete.

## 5. Require the destination handshake

The destination must:

1. Read applicable global and repository instructions.
2. Read `Communication preferences`, use its reply language immediately, and keep locale or time zone independent. Do not translate code, identifiers, commands, or artifact names unless requested.
3. Restate the goal, acceptance criteria, evidence boundary, and next action concisely in the preserved reply language.
4. Compare path, branch, HEAD, status or artifact checksums with `Workspace identity`.
5. Run every check in `Destination sentinel` and no unrelated regression suite.
6. On a mismatch, stop before changing state and report `HANDOFF REGRESSION` with the exact discrepancy.
7. On a match, report `HANDOFF VERIFIED`, continue from `Next action`, and retain all originally required final gates.

Never interpret a successful handshake as completion of the underlying task.

## 6. Optionally archive the verified source

Source task/chat archival is an optional, recoverable second phase. Codex surfaces may label the same thread-level object a task or a chat; use the surface's supported archival API for the real source identifier. Attempt it only when all of these conditions hold:

1. The destination has reported `HANDOFF VERIFIED` for the packet's sentinel.
2. No mutation, test, build, upload, or destructive action is active.
3. The validated recovery packet still exists at its recorded path.
4. The surface supplied the real `sourceThreadId` and `sourceHostId`.
5. The user explicitly authorized archival for this handoff, or an applicable instruction records a clear standing preference to archive verified handoffs.
6. A supported thread archival API is available.
7. The API result or a supported read-back can confirm the archived state.

For an `active` or `unknown` Goal, follow this lifecycle explicitly:

`CHECKPOINTED → DESTINATION_VERIFIED → SOURCE_ARCHIVE_READY → SOURCE_ARCHIVED_CONFIRMED`

1. Wait for the destination's explicit `HANDOFF VERIFIED`; thread creation alone is not verification.
2. Run `archive-plan` with the recorded Goal status and all observed prerequisites.
3. Use the thread-management capability to archive the exact source thread. Make this the source coordinator's final state-changing action because archival may interrupt its active turn.
4. Classify the observed result with `archive-result`. Claim `SOURCE_ARCHIVED_CONFIRMED` only when the archival tool reports success or a supported read-back observes the source as archived. Treat an already-observed archived source as idempotent success.

Do not archive on `HANDOFF REGRESSION`, failed or missing destination verification, unsafe state, missing identifiers, unavailable packet, unsupported APIs, unavailable confirmation, or ambiguous authorization. If any prerequisite or the archival attempt fails after a verified destination, report `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, preserve the successful handoff, warn that an unfinished Goal may auto-resume, and give the exact manual archive fallback when the real identity is available. Never claim that the source is stopped before confirmation.

Use a supported surface-provided interrupt operation only when it is part of the authorized recoverable archival flow. Do not invent a separate destructive shutdown. If archival succeeds but a later confirmation cannot be obtained, report the uncertainty rather than weakening the destination handoff.

After the destination is verified and archival is complete, skipped, or declined, remove the temporary packet only when the user has authorized cleanup and another adequate recovery record remains. Otherwise disclose its path and retention status.
