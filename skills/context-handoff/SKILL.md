---
name: context-handoff
description: Detect context-window pressure and transfer an in-progress Codex task into a fresh thread without weakening acceptance criteria or evidence. Use when the user requests a context handoff or a lifecycle health check reports material context pressure. Compaction or a healthy summary alone does not justify creating a thread. Supports cross-repository use, safe checkpointing, validated handoff packets, Codex thread creation and navigation when authorized, and destination regression sentinels.
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
- Keep the source thread and working state recoverable. Do not delete, reset, stash, commit, or change branches merely to hand off. Archive the verified source when the user has authorized it.
- Treat authorized source-thread archival as a required closure phase before claiming the full handoff is complete. Archive means recoverable hiding, not deletion.
- Do not treat “stop modifying” as source-task shutdown. An unfinished or unknown Goal can wake the source task again until archival is confirmed.
- Never mark a Goal complete or blocked merely to stop a handoff source. Use the current Goal API schema; pause only at the user’s explicit request, never as an invented transfer operation.
- Preserve any model or reasoning choice explicitly made by the user. Otherwise omit overrides in the destination.
- Preserve the reply language separately from locale or time zone. Use an explicit user preference when available; otherwise record the source thread's observed primary interaction language. Use `unspecified` only when no reliable signal exists, and never infer locale or time zone from language.
- Never request, seek, or repeatedly retry elevated approval merely to let the destination read the source checkout, another worktree, or the backup packet. Workspace isolation is a routing constraint, not an authorization problem to push onto the user.
- Treat destination visibility as a required handoff gate. Do not pin the destination or move it into the pinned section. Give it a concise `Handoff: <goal>` title; verify the exact task in its local or cloud task inventory and successfully open that task before source archival. Existing unrelated pins are outside this workflow.
- Local visibility and cloud visibility are distinct. Record which environment was actually verified; never claim automatic mirroring between them or availability on an unchecked device. Do not imply that a local listing proves mobile Remote connectivity. A local checkout or worktree remains on its host; when mobile cannot reach that host, report the host requirement instead of rerouting a code task to an incompatible projectless or cloud workspace.

## 1. Honor lifecycle detection and assess context health

Treat a developer-context message beginning `CONTEXT HANDOFF HEALTH CHECK` as observed lifecycle telemetry, not as user-authored text and not as optional advice.

Before substantial continuation when that message appears:

1. Load this skill once, reuse it thereafter.
2. Run `scripts/context_handoff.py assess` with exact telemetry and independently observed degradation. Omit unknown token counts. A correct compacted summary is normal operation, not a defect. Do not count one lost decision again as a reread and a repair.
3. At 85% usage, any compaction, or one degradation signal, save the smallest checkpoint only if material state changed.
4. Prepare automatic handoff only at 95% usage **and** at least one degradation signal, three compactions **and** at least one degradation signal, or two independent degradation signals. Explicit user handoff requests bypass these thresholds.
5. Apply a 60-minute cooldown across the entire handoff chain via `--minutes-since-handoff`. If a prior transfer exists but its time is unknown, pass `--prior-handoff-unknown` and defer automatic switching. Explicit handoff requests and two independent quality failures bypass cooldown, never safety checks.
6. A near-complete task with only a bounded check/final response remaining should finish in place unless quality degradation prevents reliable completion. A reminder is not a new request to create a thread.

The hook emits at the first and third compaction, then at most every eight subsequent user turns for an unchanged severity. It does not force transfer or scan other sessions. Use only the exact current session identity; never select an arbitrary latest rollout. Preserve chain identity and prior handoff timestamp in the destination. Do not reset cooldown by changing threads.

```bash
python3 <skill-dir>/scripts/context_handoff.py assess \
  --used-tokens <used> --context-window <limit> \
  --compactions <count> --degradation-signals <independent-count> \
  --standing-authorization
```

Use `--requested` only for an explicit request to transfer, not a request to repair this plugin. Repeat `--unsafe <reason>` for active blockers. Repository/user rules override defaults. A candidate still requires transfer authorization and a safe, recoverable checkpoint.

## 2. Reach a safe checkpoint

Finish the current atomic operation and collect only the state needed for continuity:

1. Record the working directory and applicable instruction files.
2. Record whether the source is using the saved checkout, a Codex worktree, or a projectless directory. For Git work, record branch, HEAD, concise status, relevant changed paths, and a diff hash when useful. For non-Git work, record equivalent artifact identities and checksums.
3. Record completed outputs and their exact evidence, including commands and result summaries. Do not paste full logs.
4. Record the reply language and any explicit locale, time-zone, terminology, or formality preference needed for continuity.
5. Record open work, failed approaches that must not be repeated, active external state, and the single next action.
6. Inspect the source Goal with the supported Goal-status capability when available. Record `active`, `paused`, `complete`, `blocked`, `none`, or `unknown`; never invent a state.
7. Record per-handoff archival authorization, an applicable standing preference, or that archival is declined/unspecified. Carry the exact Goal objective, user authorization, original budget and measured remaining budget. Never replenish a token cap through handoff.
8. Record scoped user authorizations with their source instruction, exclusions, denials, pending approvals, and observed runtime permissions. Authorization for one action is not blanket authorization. Session grants, sandbox policy and connector access are runtime state, not transferable merely by text.
9. Capture usage with the `usage` command below before transfer; preserve unknown fields as unknown.
10. Choose the smallest destination sentinel that can detect a bad transfer: workspace identity plus a focused state, artifact, or test check. Do not rerun unaffected suites merely for ceremony.

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
2. Before creating anything, inspect the current creation tool schema and confirm required permission/workspace compatibility. If a permission needed by the next action is known incompatible, report `HANDOFF NEEDS COMPATIBLE PERMISSIONS` and stay in the source. When permission inheritance is unknown and the user explicitly requests an end-to-end test, one provisional destination may run only the bounded permission/identity handshake under its actual ordinary permissions. Keep the source active until those checks pass; a denial ends the attempt without approval escalation or substantive work. Never describe this provisional creation as a verified transfer. Do not change global permissions to force compatibility. Unknown permissions must not be described as inherited. For repository or workspace-dependent work, also confirm that the thread-creation surface can place a fresh destination in the exact source working directory under ordinary permissions. Selecting the same saved project is not sufficient when the source is in a different worktree or checkout. A genuinely portable projectless task may instead use a fresh projectless directory when its complete required inputs fit inline and no source file access is needed for the next action. Record this deliberate routing in Workspace identity, verify the destination owns its new directory, and do not treat changed paths as regression in that specific mode. This exception cannot be used for repository work, external dependencies, or to bypass a permission boundary.
3. If exact-directory placement is required but unavailable, do not create a destination that would need approval to cross the workspace boundary. Keep the source at its checkpoint, provide the complete validated packet as a copyable fallback, report `HANDOFF NEEDS COMPATIBLE WORKSPACE`, and state the source and available destination locations. Do not substitute a full-history fork merely to preserve directory access.
4. Create the fresh destination only after the compatibility preflight passes. Do not create a worktree or branch solely for handoff.
5. Put the complete validated packet inline in the initial prompt. Mention the backup path only as source-side recovery information and explicitly instruct the destination not to open it.
6. Instruct the destination to run the handshake below before continuing. Include the user's actual Goal/continuation authorization, the remaining scope and budget, and the source archival preference in the initial prompt. Do not manufacture an explicit Goal request from an ordinary task. Inspect `get_goal` before any `create_goal`; restore only a genuinely user-authorized active Goal, and only once. If current tools cannot restore its remaining cap/state, keep the source recoverable and report the limitation before closure.
7. Give the exact returned destination thread a concise, recognizable title in the form `Handoff: <short goal>`. Preserve a user-supplied title when it is already equally clear.
8. Do not pin the destination. Read the appropriate local or cloud task inventory and verify the exact returned thread ID, title, backend/location and, for a local task, host ID. Then open that exact task with the supported navigation capability and verify its successful result; a queued tab or creation receipt is insufficient. Record the identity, location, list/open evidence and timestamp in the checkpoint, and return a supported task link or created-thread entry to the user. For local tasks record the project/host; for cloud tasks record the returned cloud identity/link. Use local or cloud according to the authorized destination and workspace compatibility; cloud creation still requires explicit user authorization and must not be inferred from this visibility preference. Never create a duplicate merely to obtain visibility in both environments.
9. If naming, listing, or opening is unavailable or fails, keep the handoff destination and source recoverable, report `HANDOFF VISIBILITY UNVERIFIED`, and provide the exact known title, thread identity, local/cloud location, host and supported link. Do not archive the source or claim the task is visible. Retry only after a concrete state change; do not create additional destinations or fall back to pinning. Visibility is verified at handoff time, not guaranteed against later deletion, account changes or host disconnection.
10. Stop substantial work in the source after the destination is created, preventing duplicate execution.
11. Navigation for the visibility check requires the user’s request or standing authorization to open the destination. If that authorization is absent, preserve the source and report the unverified opening gate.

If the source Goal is `active` or `unknown`, the source remains a handoff coordinator only until the destination result and source-closure outcome are known. When the surface supports it, read the exact destination thread for `HANDOFF VERIFIED` or `HANDOFF REGRESSION`; do not end the source lifecycle immediately after creation. The destination emits its handshake in commentary before waiting for closure. Because `wait_threads` may not wake on commentary, use bounded snapshots or `read_thread` to inspect that handshake; never wait solely for destination completion while the destination is waiting for source archival. The source must not resume repository work or claim that it has stopped merely because its current response ended.

If fresh-thread creation is unavailable, provide the validated packet path and a compact copyable prompt. State plainly that no automatic switch occurred.

When the surface exposes the actual source thread and host identifiers, record them in the packet. Never guess or synthesize either identifier. Keep the validated recovery packet available until the destination handshake and any authorized archival attempt are complete.

## 5. Require the destination handshake

The destination must:

1. Read applicable global and repository instructions.
2. Read `Communication preferences`, use its reply language immediately, and keep locale or time zone independent. Do not translate code, identifiers, commands, or artifact names unless requested.
3. Restate the goal, acceptance criteria, evidence boundary, and next action concisely in the preserved reply language.
4. Compare its current path, branch, HEAD, status or artifact checksums with `Workspace identity` using only resources already available in its workspace. For an explicitly portable projectless packet, verify the new local directory and inline artifact checksum instead of requiring the old path. The inline packet is authoritative; do not open the source-side backup packet.
5. Run every check in `Destination sentinel` and no unrelated regression suite.
6. On a mismatch or an unexpected permission boundary, stop before changing state and report `HANDOFF REGRESSION` with the exact discrepancy. Do not request approval and do not retry the blocked read from the destination.
7. Verify scoped authorization evidence and effective runtime permissions for the next action. If needed permissions are unavailable, report `HANDOFF NEEDS COMPATIBLE PERMISSIONS`; text does not grant runtime access. Do not re-ask for user intent already explicitly authorized, but never bypass platform approval controls.
8. Restore a user-authorized active Goal using `get_goal` then `create_goal` if absent; read back the exact objective and remaining cap. Never create a Goal for an ordinary task, reset a budget, resume a paused/blocked Goal without explicit authorization, or overwrite a conflicting active Goal. If active Goal continuity cannot be verified, report `HANDOFF GOAL UNVERIFIED` and do not authorize source closure.
9. On all matches, report `HANDOFF VERIFIED` in commentary, including workspace, permissions and Goal evidence. When source archival is authorized, wait until the exact source is confirmed archived before substantive mutations; before that, perform coordination only. Preserve read-only recovery if closure fails. Continue from `Next action` and retain all originally required final gates. Do not end with only an acknowledgment when continuation is authorized.

Never interpret a successful handshake as completion of the underlying task.

## 6. Close the verified source when authorized

Source task/chat archival is a recoverable closure phase. When the applicable user preference authorizes it, complete this phase without asking again; otherwise do not infer authorization. Codex surfaces may label the same thread-level object a task or a chat; use the surface's supported archival API for the real source identifier. Attempt it only when all of these conditions hold:

1. The destination has reported `HANDOFF VERIFIED` for the packet's sentinel.
2. Destination visibility was verified in the chosen local or cloud task inventory by exact identity and successful opening. Pinning and a discoverability opt-out cannot substitute for this gate.
3. No mutation, test, build, upload, or destructive action is active.
4. The validated recovery packet still exists at its recorded path.
5. The surface supplied the real `sourceThreadId` and `sourceHostId`.
6. The user explicitly authorized archival for this handoff, or an applicable instruction records a clear standing preference to archive verified handoffs.
7. A supported thread archival API is available.
8. The API result or a supported read-back can confirm the archived state.

For an `active` or `unknown` Goal, follow this lifecycle explicitly:

`CHECKPOINTED → DESTINATION_VERIFIED → SOURCE_ARCHIVE_READY → SOURCE_ARCHIVED_CONFIRMED`

1. Wait for the destination's explicit `HANDOFF VERIFIED`; thread creation alone is not verification.
2. Run `archive-plan` with the recorded Goal status and all observed prerequisites, including `--destination-discoverable` only after exact task-inventory read-back, `--destination-opened` only after successful navigation, the returned `--destination-thread-id`, `--destination-location local|cloud`, and `--destination-host-id` for local tasks, `--goal-continuity-verified` only after Goal read-back (or confirmed no Goal), and `--permissions-verified` only after the required effective access checks.
3. Use the thread-management capability to archive the exact source thread. Persist the handoff IDs, verification and closure intent first; make archival the source coordinator’s final state-changing action because it may interrupt its active turn. The destination should read back source archival if the source cannot report after interruption.
4. Classify the observed result with `archive-result`. Claim `SOURCE_ARCHIVED_CONFIRMED` only when the archival tool reports success or a supported read-back observes the source as archived. Treat an already-observed archived source as idempotent success.

Do not archive on `HANDOFF REGRESSION`, `HANDOFF VISIBILITY UNVERIFIED`, failed or missing destination verification, unsafe state, missing identifiers, unavailable packet, unsupported APIs, unavailable confirmation, or ambiguous authorization. If discoverability alone is unverified, preserve both threads and report that state with the exact known destination identity. If another prerequisite or the archival attempt fails after a verified destination, report `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, preserve the successful handoff, warn that an unfinished Goal may auto-resume, and give the exact manual archive fallback when the real identity is available. Never claim that the source is stopped before confirmation.

Use a supported surface-provided interrupt operation only when it is part of the authorized recoverable archival flow. Do not invent a separate destructive shutdown. If archival succeeds but a later confirmation cannot be obtained, report the uncertainty rather than weakening the destination handoff.

After the destination is verified and archival is complete, skipped, or declined, remove the temporary packet only when the user has authorized cleanup and another adequate recovery record remains. Otherwise disclose its path and retention status.

## 7. Measure instead of claiming savings

Use `python3 <skill-dir>/scripts/context_handoff.py usage <exact-source-rollout> <exact-destination-rollout>` only with surface-provided/verified identities. Save JSON snapshots locally before transfer, after handshake/closure, and after the accepted deliverable. `usage` streams token telemetry only and never prints conversation text. Missing fields remain null; cumulative counters are not summed across samples. Duplicate session identities fail rather than double count. Truncated logs or counter resets invalidate aggregate totals.

Report total input, cached and uncached input, output and reasoning tokens separately. Reasoning is a subset of output; cached input is a subset of input. Include measured retry/subagent/transfer overhead only when separately attributable; mark unavailable otherwise. Derive interval usage from two complete monotonic snapshots of the same sessions, including failed destinations and coordination. Preserve original caps across the whole chain.

A smaller context, fewer reminders, or shorter elapsed time is not measured cost savings. Only compare equivalent accepted work with identical quality gates, model/pricing basis and accounting boundaries. Without that control, report `savings unproven`; never invent a percentage or money amount. The current tool provides observed cumulative usage, not causal savings. Do not scan unrelated transcripts or create a recurring monitor for measurement.

## 8. Keep coordination bounded without removing gates

Batch independent Goal, runtime and exact-inventory reads. Return only exact-ID matches, unpinned status and tool success fields to the model; retain required raw evidence in the task workspace. Read applicable instructions once with sufficient output budget rather than truncating and rereading. Do not load unrelated skills merely to coordinate an operational test.

When a source waits for a destination handshake, use bounded `read_thread` snapshots or the authorized sentinel artifact. `wait_threads` does not wake on commentary. Combine a 15–30 second wait and its following read in one orchestration call, at most 60 seconds per call, with a finite deadline. Keep user progress updates and the actual visibility, opening, Goal, permissions, hash and independent archival checks. Do not turn completion polling into additional messages or recurring automations.

For exact-session Goal evidence and usage, use `scripts/handoff_evidence.py snapshot <exact-rollout> --session-id <id> [--until <UTC-timestamp>] [--require-goal-none] [--output <snapshot.json>]`. It supports both tool-output formats, correlates Goal output with its call, verifies session identity, and follows only the same rollout basename to `archived_sessions` after archival. It rejects malformed or decreasing counters. A missing optional counter remains unknown. Denied access still stops the transfer; archive relocation is not an approval bypass.

Use `interval <start.json> <end.json>` for one session's measured delta. Save repair/setup and E2E boundaries separately. Build the JSON and readable report from one data object and read both back, rather than authoring independent summaries. A final in-turn snapshot excludes the tokens used to finish reporting: either label that cutoff or let a separate authorized observer capture the completed turn. A repeated E2E comparison must hold acceptance gates, model/settings and starting inputs constant, include both sessions and failures, and disclose remaining timing/cache differences. A historical run with tool repairs or different starting context is not a causal savings control.
