# Reviewer test cases

All cases use a temporary sample Git repository and synthetic task text. They require no account, private network, credentials, or internal context.

## Positive cases

### 0. Automatic compaction detection

- Setup: Install the complete plugin, review and trust its hook definition, then start a fresh synthetic task.
- Event: Deliver a `SessionStart` lifecycle event with `source: compact`, followed by a later user turn in the same session.
- Expected behavior: Before substantive continuation, Codex receives `CONTEXT HANDOFF HEALTH CHECK` with one observed compaction. The later user turn receives the reminder again without incrementing the count.
- Expected result: The skill runs deterministic assessment, creates or refreshes a checkpoint, and audits only observed degradation signals. A second compact event reports two compactions and makes an authorized task handoff-ready.
- Privacy boundary: Local plugin state contains no prompt, response, transcript, path, or raw session identifier and is removed on `SessionEnd`.

### 1. Explicit handoff at a safe checkpoint

- Prompt: "Use Context Handoff to move this completed documentation task into a fresh verified thread."
- Expected behavior: The skill records the clean sample repository identity, creates and validates a bounded packet, creates a fresh thread when supported, and requires the destination sentinel.
- Expected result: The destination reports `HANDOFF VERIFIED` only after the path, HEAD, status, and selected check match, then continues the stated next action.
- Fixture: Any clean temporary Git repository with one passing test.

### 2. Standing authorization at high context pressure

- Prompt: "My standing preference authorizes fresh-thread handoffs. Assess 86,000 of 100,000 tokens and continue safely."
- Expected behavior: Assessment returns `handoff-ready`; the skill reaches a safe checkpoint and transfers without requesting duplicate authorization.
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
- Expected behavior: The skill retains the validated packet, captures only real surface-provided source thread/host IDs, waits for `HANDOFF VERIFIED`, confirms no active unsafe work, then calls the supported task/chat thread archival API.
- Expected result: The source is reported as archived (recoverable), not deleted; the successful handoff remains independently recorded.
- Fixture: A test surface exposing synthetic test thread IDs and a mock archival API.

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
- Expected fallback: Do not archive. Identify each missing prerequisite and provide a manual archive instruction when the real source identity and UI are available.
- Why not complete: Archival is a separately authorized, post-verification, recoverable action and identifiers must never be invented.
