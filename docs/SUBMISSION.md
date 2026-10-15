# Public Plugins Directory submission materials

These materials prepare a draft submission; they do not claim OpenAI review, approval, or publication.

## Listing

- Name: Context Handoff
- Category: Productivity
- Short description: Continue work in fresh threads
- Long description: Detect context pressure with throttled local lifecycle checks, then safely continue work in a fresh verified thread. Preserve language, Goal state, scoped authorization, runtime permission checks and evidence. Verify destination visibility and opening without pinning before authorized source archival. Record exact-session token usage without assuming savings.
- Developer: Tim Yu
- Website: https://github.com/timyeou1234/context-handoff
- Support: https://github.com/timyeou1234/context-handoff/blob/main/SUPPORT.md (enter in the portal; the supported plugin manifest schema has no support URL field)
- Privacy: https://github.com/timyeou1234/context-handoff/blob/main/PRIVACY.md
- Terms: https://github.com/timyeou1234/context-handoff/blob/main/TERMS.md
- Directory logo: `assets/logo.png` (512 × 512 PNG; current portal minimum is 256 × 256)
- Composer icon: `assets/icon.png` (256 × 256 PNG; current portal minimum is 48 × 48)
- Editable logo source: `assets/logo.svg`

## Starter prompts

1. Checkpoint this task and continue it in a fresh verified thread.
2. Prepare a safe handoff packet for this long-running Codex task.
3. Check context health and hand off only if a fresh thread is warranted.

## Release notes — 0.3.5

Reduces repeated handoff coordination while preserving verification and recoverability. Health checks are throttled to the first and third compaction, then every eight user turns; handoff requires the documented degradation thresholds and a 60-minute chain cooldown unless explicitly requested or two independent quality failures occur. Packets carry Goal, authorization, permission and budget continuity; destination visibility, successful opening and authorized source archival remain required.

Adds exact-session evidence snapshots, correlated Goal tool results, archive-aware rollout lookup, monotonic token validation and separate interval accounting. Required identity, permission, visibility and archival checks are unchanged. The portable projectless route is limited to complete inline inputs and does not relax exact-workspace requirements for repository work.

A single local paired E2E measurement observed 1,614,078 versus 1,219,432 tokens (24.45% fewer for the accepted handoff); this is not a guaranteed reduction or a monetary claim. One-time repair, failed setup and observer costs are reported separately. Both Goals were absent, so active-Goal restoration and cross-device access were not exercised. All 36 regression tests passed. See the README and sanitized benchmark data for evidence and limits.

No MCP server, hosted service, authentication or reviewer credentials are required. This release is available through the repository/local marketplace; public directory approval or publication is a separate portal action.

## USER-REQUIRED portal steps

GitHub Actions can build the versioned ZIP and checksum and can publish the matching GitHub Release. The OpenAI Platform submission remains a separate reviewed workflow; this repository has no submission credential or supported public submission API.

- Confirm Apps Management write access in the submitting OpenAI organization.
- Complete and select the correct verified individual or business identity.
- Review legal text and publisher identity with qualified counsel if required.
- Confirm the website, support, privacy, and terms URLs resolve publicly from the final release ref.
- Choose only countries or regions where support and legal terms are ready.
- Upload the final skill bundle and production logo, enter listing details and prompts, and add the reviewer cases from `docs/REVIEWER_TESTS.md`.
- Review and complete policy attestations personally.
- Submit for review only when authorized.
- After approval, choose whether and when to publish. Approval and publication are not established by this repository.
