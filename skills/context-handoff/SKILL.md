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
- Never request, seek, or repeatedly retry elevated approval merely to let the destination read the source checkout, another worktree, or the backup packet. Workspace isolation is a routing constraint, not an authorization problem to push onto the user.
- Treat destination discoverability as part of a usable handoff. When the surface supports titles, sidebar pinning, and thread listing, give the destination a concise `Handoff: <goal>` title, pin the exact returned thread, and verify that exact thread and host in the pinned list before the source can be archived.
- Do not imply that pinning can replace mobile Remote connectivity. A local checkout or worktree remains on its host; when mobile cannot reach that host, report the host requirement instead of rerouting a code task to an incompatible projectless or cloud workspace.

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
2. Record whether the source is using the saved checkout, a Codex worktree, or a projectless directory. For Git work, record branch, HEAD, concise status, relevant changed paths, and a diff hash when useful. For non-Git work, record equivalent artifact identities and checksums.
3. Record completed outputs and their exact evidence, including commands and result summaries. Do not paste full logs.
4. Record the reply language and any explicit locale, time-zone, terminology, or formality preference needed for continuity.
5. Record open work, failed approaches that must not be repeated, active external state, and the single next action.
6. Inspect the source Goal with the supported Goal-status capability when available. Record `active`, `complete`, `blocked`, `none`, or `unknown`; never invent a state.
7. Record per-handoff archival authorization, an applicable standing preference, or that archival is declined/unspecified.
8. Choose the smallest destination sentinel that can detect a bad transfer: workspace identity plus a focused state, artifact, or test check. Do not rerun unaffected suites merely for ceremony.

If a safe checkpoint cannot be reached, defer the handoff and continue only far enough to make the state recoverable.

## 3. Build and validate the packet

Create a temporary Markdown backup outside the repository. This file is source-side recovery state; the destination must receive the complete packet inline and must not need to read the backup path. Generate the required skeleton with:

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

1. Resolve the current saved project with project listing and identify the source execution context. Use a projectless target only for a genuinely non-project task.
2. Before creating anything, confirm that the thread-creation surface can place a fresh destination in the exact source working directory under ordinary permissions. Selecting the same saved project is not sufficient when the source is in a different worktree or checkout.
3. If exact-directory placement is unavailable, do not create a destination that would need approval to cross the workspace boundary. Keep the source at its checkpoint, provide the complete validated packet as a copyable fallback, report `HANDOFF NEEDS COMPATIBLE WORKSPACE`, and state the source and available destination locations. Do not substitute a full-history fork merely to preserve directory access.
4. Create the fresh destination only after the compatibility preflight passes. Do not create a worktree or branch solely for handoff.
5. Put the complete validated packet inline in the initial prompt. Mention the backup path only as source-side recovery information and explicitly instruct the destination not to open it.
6. Instruct the destination to run the handshake below before continuing.
7. Give the exact returned destination thread a concise, recognizable title in the form `Handoff: <short goal>`. Preserve a user-supplied title when it is already equally clear.
8. When supported, pin that exact destination thread to the sidebar, then read the thread inventory and verify the same thread ID, host ID, and title in the pinned list. Record those three values in the source checkpoint. Do not infer success from the mutation call alone.
9. If naming, pinning, or read-back is unavailable or fails, keep the handoff destination and source recoverable, report `HANDOFF MOBILE VISIBILITY UNVERIFIED`, and provide the exact destination title, thread ID, and host ID that are actually known. Do not archive the source or claim mobile visibility.
10. Stop substantial work in the source after the destination is created, preventing duplicate execution.
11. Navigate to the destination only when the user's request or standing instructions explicitly authorize switching views.

If the source Goal is `active` or `unknown`, the source remains a handoff coordinator only until the destination result and source-closure outcome are known. When the surface supports it, wait on or read the exact destination thread until it reports `HANDOFF VERIFIED` or `HANDOFF REGRESSION`; do not end the source lifecycle immediately after creation. The source must not resume repository work or claim that it has stopped merely because its current response ended.

If fresh-thread creation is unavailable, provide the validated packet path and a compact copyable prompt. State plainly that no automatic switch occurred.

When the surface exposes the actual source thread and host identifiers, record them in the packet. Never guess or synthesize either identifier. Keep the validated recovery packet available until the destination handshake and any authorized archival attempt are complete.

## 5. Require the destination handshake

The destination must:

1. Read applicable global and repository instructions.
2. Read `Communication preferences`, use its reply language immediately, and keep locale or time zone independent. Do not translate code, identifiers, commands, or artifact names unless requested.
3. Restate the goal, acceptance criteria, evidence boundary, and next action concisely in the preserved reply language.
4. Compare its current path, branch, HEAD, status or artifact checksums with `Workspace identity` using only resources already available in its workspace. The inline packet is authoritative; do not open the source-side backup packet.
5. Run every check in `Destination sentinel` and no unrelated regression suite.
6. On a mismatch or an unexpected permission boundary, stop before changing state and report `HANDOFF REGRESSION` with the exact discrepancy. Do not request approval and do not retry the blocked read from the destination.
7. On a match, report `HANDOFF VERIFIED`, continue from `Next action`, and retain all originally required final gates.

Never interpret a successful handshake as completion of the underlying task.

## 6. Optionally archive the verified source

Source task/chat archival is an optional, recoverable second phase. Codex surfaces may label the same thread-level object a task or a chat; use the surface's supported archival API for the real source identifier. Attempt it only when all of these conditions hold:

1. The destination has reported `HANDOFF VERIFIED` for the packet's sentinel.
2. Destination discoverability was verified by exact thread and host identity, or the user explicitly declined mobile/sidebar discoverability for this handoff.
3. No mutation, test, build, upload, or destructive action is active.
4. The validated recovery packet still exists at its recorded path.
5. The surface supplied the real `sourceThreadId` and `sourceHostId`.
6. The user explicitly authorized archival for this handoff, or an applicable instruction records a clear standing preference to archive verified handoffs.
7. A supported thread archival API is available.
8. The API result or a supported read-back can confirm the archived state.

For an `active` or `unknown` Goal, follow this lifecycle explicitly:

`CHECKPOINTED → DESTINATION_VERIFIED → SOURCE_ARCHIVE_READY → SOURCE_ARCHIVED_CONFIRMED`

1. Wait for the destination's explicit `HANDOFF VERIFIED`; thread creation alone is not verification.
2. Run `archive-plan` with the recorded Goal status and all observed prerequisites, including `--destination-discoverable` only after exact sidebar read-back or an explicit discoverability opt-out.
3. Use the thread-management capability to archive the exact source thread. Make this the source coordinator's final state-changing action because archival may interrupt its active turn.
4. Classify the observed result with `archive-result`. Claim `SOURCE_ARCHIVED_CONFIRMED` only when the archival tool reports success or a supported read-back observes the source as archived. Treat an already-observed archived source as idempotent success.

Do not archive on `HANDOFF REGRESSION`, `HANDOFF MOBILE VISIBILITY UNVERIFIED`, failed or missing destination verification, unsafe state, missing identifiers, unavailable packet, unsupported APIs, unavailable confirmation, or ambiguous authorization. If discoverability alone is unverified, preserve both threads and report that state with the exact known destination identity. If another prerequisite or the archival attempt fails after a verified destination, report `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, preserve the successful handoff, warn that an unfinished Goal may auto-resume, and give the exact manual archive fallback when the real identity is available. Never claim that the source is stopped before confirmation.

Use a supported surface-provided interrupt operation only when it is part of the authorized recoverable archival flow. Do not invent a separate destructive shutdown. If archival succeeds but a later confirmation cannot be obtained, report the uncertainty rather than weakening the destination handoff.

After the destination is verified and archival is complete, skipped, or declined, remove the temporary packet only when the user has authorized cleanup and another adequate recovery record remains. Otherwise disclose its path and retention status.
