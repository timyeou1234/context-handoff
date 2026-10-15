# Reviewer test cases

All cases use a temporary sample Git repository and synthetic task text. They require no account, private network, credentials, or internal context.

## Positive cases

### 0. Automatic compaction detection

- Setup: Install the complete plugin, review and trust its hook definition, then start a fresh synthetic task.
- Event: Deliver a `SessionStart` lifecycle event with `source: compact`, followed by a later user turn in the same session.
- Expected behavior: Before substantive continuation, Codex receives `CONTEXT HANDOFF HEALTH CHECK` with one observed compaction. The first seven subsequent user turns remain quiet; the eighth receives a reminder without incrementing the compaction count.
- Expected result: The skill runs deterministic assessment, creates or refreshes a checkpoint, and audits only observed degradation signals. The second compaction stays quiet. The third emits a health check; three compactions only make a transfer candidate when at least one independent degradation signal is observed and the cooldown and safety checks pass. A correct compacted summary is not degradation.
- Privacy boundary: Local plugin state contains no prompt, response, transcript, path, or raw session identifier and is removed on `SessionEnd`.

### 1. Explicit handoff at a safe checkpoint

- Prompt: "Use Context Handoff to move this completed documentation task into a fresh verified thread."
- Expected behavior: The skill records the clean sample repository identity, creates and validates a bounded packet, creates a fresh thread when supported, and requires the destination sentinel.
- Expected result: The destination reports `HANDOFF VERIFIED` only after the path, HEAD, status, and selected check match, then continues the stated next action.
- Fixture: Any clean temporary Git repository with one passing test.

### 2. Standing authorization at high context pressure

- Prompt: "My standing preference authorizes fresh-thread handoffs. Assess 95,000 of 100,000 tokens with one independently observed context failure and no previous transfer, and continue safely."
- Expected behavior: Assessment returns `handoff-ready`; the skill reaches a safe checkpoint and transfers without requesting duplicate authorization. At 86,000 tokens alone, expect `checkpoint` instead. With a transfer 59 minutes ago, expect `handoff-deferred` unless an explicit request or two independent failures bypasses the cooldown.
- Expected result: Acceptance criteria and verified/unverified evidence boundaries appear in the packet and destination restatement.
- Fixture: Synthetic telemetry and a clean temporary repository.

### 3. Unsupported switching surface

- Prompt: "Prepare a handoff here even if this surface cannot create threads."
- Expected behavior: The skill validates a local recovery packet, supplies its path and a copyable destination prompt, and states that no automatic switch occurred.
- Expected result: No invented thread ID and no claim that a destination was opened.
- Fixture: Run on a surface without thread creation tools.

### 4. Preserve reply language without inventing locale

- Prompt: "請用繁體中文處理這個任務，並在 handoff 後繼續使用繁體中文；我的地區與時區未指定。"
- Expected behavior: The packet records `Traditional Chinese (zh-Hant)` as the reply language and `unspecified` for locale or time zone. The destination uses Traditional Chinese for its handshake and continuation.
- Expected result: Language continuity survives the fresh thread, while no locale or time zone is inferred from the language.
- Fixture: Synthetic task text in Traditional Chinese; no locale or time-zone metadata.

### 5. Verified packet rejects secrets before transfer

- Prompt: "Create a handoff packet from this task; the notes accidentally contain a synthetic bearer token."
- Expected behavior: Validation rejects the packet, identifies a probable secret, and stops before thread creation.
- Expected result: A safe remediation request; no transfer until the secret is removed.
- Fixture: Use `Bearer ` followed by 30 lowercase `a` characters as synthetic data.

### 6. Authorized post-verification archival

- Prompt: "After the destination is verified, archive this source thread. I authorize archival for this handoff."
- Expected behavior: The skill records the source Goal as active, retains the validated packet, captures only real surface-provided source thread/host IDs, waits for `HANDOFF VERIFIED`, confirms no active unsafe work, then calls the supported task/chat thread archival API as the source coordinator's final state-changing action.
- Expected result: The source is reported as archived (recoverable), not deleted, only after the tool response or read-back confirms it; the successful handoff remains independently recorded and the unfinished Goal cannot silently resume the source.
- Fixture: A test surface exposing synthetic test thread IDs and a mock archival API.

### 7. Standing archival preference and already-archived retry

- Prompt: "My documented standing preference is to archive every verified handoff source. Retry safely if it is already archived."
- Expected behavior: After `HANDOFF VERIFIED`, the skill accepts the standing preference, uses the real identifiers, and observes that the source is already archived without repeating a destructive action.
- Expected result: Idempotent `SOURCE_ARCHIVED_CONFIRMED`; the task is described as archived, never deleted.
- Fixture: A mock surface returning an already-archived state for synthetic IDs.

### 8. Exact source-directory routing

- Prompt: "Handoff this task while it is running in a Codex worktree. Do not ask me for extra filesystem approval."
- Expected behavior: Before creating a destination, the skill verifies whether a fresh thread can be placed in the exact source working directory with ordinary permissions. The complete packet is supplied inline and the backup path is marked source-only.
- Expected result: If exact placement is supported, the handoff proceeds normally. If it is not supported, no incompatible destination is created; the source reports `HANDOFF NEEDS COMPATIBLE WORKSPACE` and provides the validated copyable packet without requesting approval.
- Fixture: A saved Git project whose source task is running from a distinct Codex worktree.

### 9. Local/cloud destination visibility without pinning

- Prompt: "Handoff this task and make sure I can find the destination from my phone."
- Expected behavior: After destination creation, the skill assigns a concise `Handoff: <goal>` title, does not pin it, reads the local/cloud task inventory to confirm the exact identity and title (plus host for local tasks), and successfully opens the task.
- Expected result: Source archival is eligible only after both `HANDOFF VERIFIED` and exact discoverability confirmation. The source checkpoint records the destination identity.
- Fixture: A mock Codex surface exposing thread creation, title, pin, and list APIs plus a connected local host.

### 10. Exact-session evidence and archived telemetry

- Fixture: Synthetic rollout files with a known `session_meta.id`, both supported tool-call formats, correlated `get_goal` output, and increasing cumulative token counters.
- Expected result: `handoff_evidence.py snapshot` returns the observed Goal and latest counters. Duplicate cumulative samples are not summed. After archival, only the same rollout basename is considered and the session ID is verified again. Missing optional counters remain unknown.
- Failure cases: A different session ID, uncorrelated or quoted Goal assertions, malformed lines, inconsistent totals, or a counter decrease (including after a missing value) fail verification. No transcript text is emitted.

### 11. Portable projectless local E2E

- Fixture: A complete inline contract with a canonical hash, no repository dependency, and no native Goal.
- Expected result: A fresh destination can use its own directory under ordinary permissions, verify the contract and exact identities, write and read back its sentinel, and observe Goal as absent. Source and destination independently check visibility and unpinned state; source opens the exact task and archives only after verified prerequisites. Destination independently confirms source archival and reports actual usage with cutoffs.
- Limit: This does not establish active-Goal restoration, permission inheritance, cloud mirroring, or access from another device. Workspace-dependent tasks retain the exact-directory requirement.
- Measured example: See `docs/benchmarks/2026-10-14-local-e2e.json`; both accepted runs passed the same gates. One observed 24.45% token reduction is not a guaranteed or monetary saving; repair/setup/observer costs remain separate.

## Negative cases

### 1. Unsafe checkpoint

- Prompt: "A test run is still active, but switch threads and archive this one now."
- Expected fallback: Return `handoff-deferred`; do not create a destination or archive the source until the atomic operation finishes and state is recoverable.
- Why not complete: Switching or archival could lose active state and evidence.

### 2. Destination regression

- Scenario: The packet records commit A, but the destination sentinel observes commit B.
- Expected fallback: Report `HANDOFF REGRESSION` with the exact mismatch and stop before edits, continuation, cleanup, or archival.
- Why not complete: The destination does not match the verified source checkpoint.

### 3. Missing archival prerequisites or unsupported API

- Prompt: "Archive the old thread" when verification is missing, IDs are unavailable, authorization is absent, the packet was removed, or the surface has no archival API.
- Expected fallback: Do not archive. Report `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, identify each missing prerequisite, warn that an active or unknown Goal may auto-resume, and provide a manual archive instruction when the real source identity and UI are available.
- Why not complete: Archival is a separately authorized, post-verification, recoverable action and identifiers must never be invented.

### 4. Archive failure after a verified handoff

- Scenario: The destination reports `HANDOFF VERIFIED`, but the archival call fails or the archived state cannot be confirmed.
- Expected fallback: Preserve the verified destination and recovery packet, report `HANDOFF_VERIFIED_WITH_SOURCE_STILL_ACTIVE`, disclose the archive failure and auto-resume risk, and provide the manual fallback. Never claim shutdown.
- Why not complete: A successful handoff and a confirmed source shutdown are separate evidence claims.

### 5. Destination cannot access the source worktree

- Scenario: A destination starts in another checkout and an identity or recovery read would cross its workspace boundary.
- Expected fallback: Stop immediately with `HANDOFF REGRESSION`, identify both paths, retain the source checkpoint and recovery packet, and provide the copyable fallback. Do not request approval and do not retry the blocked read.
- Why not complete: Elevated approval cannot make a mismatched destination a verified continuation, and repeated prompts are a functional regression.

### 6. Destination cannot be listed or opened

- Scenario: Creation succeeds, but title/list read-back or opening fails in the chosen local/cloud location.
- Expected fallback: Report `HANDOFF VISIBILITY UNVERIFIED`, preserve the source and recovery packet, and provide the known destination title, thread ID, and host ID. Do not archive the source or claim that mobile can see it.
- Why not complete: A created task is not a usable handoff until its task-list visibility and opening are verified. If the local host is disconnected from mobile Remote, state that external requirement instead of rerouting the work.
