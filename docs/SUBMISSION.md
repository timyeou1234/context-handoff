# Public Plugins Directory submission materials

These materials prepare a draft submission; they do not claim OpenAI review, approval, or publication.

## Listing

- Name: Context Handoff
- Category: Productivity
- Short description: Detect context pressure and continue in a verified fresh thread.
- Long description: Detect compaction with a trusted local lifecycle hook, keep context-health review active on later turns, and safely checkpoint a long-running Codex task. Preserve its goal, acceptance criteria, evidence, workspace identity, and open risks, then continue in a fresh thread only after a destination regression sentinel passes.
- Developer: Tim Yu
- Website: https://github.com/timyeou1234/context-handoff
- Support: https://github.com/timyeou1234/context-handoff/blob/main/SUPPORT.md
- Privacy: https://github.com/timyeou1234/context-handoff/blob/main/PRIVACY.md
- Terms: https://github.com/timyeou1234/context-handoff/blob/main/TERMS.md
- Logo: `assets/logo.png` (square high-resolution PNG; `assets/logo.svg` is the editable source)

## Starter prompts

1. Checkpoint this task and continue it in a fresh verified thread.
2. Prepare a safe handoff packet for this long-running Codex task.
3. Check context health and hand off only if a fresh thread is warranted.

## Release notes — 0.3.0

Adds trusted local lifecycle hooks that record root-session compaction and inject a mandatory context-health check before the next continuation and on later user turns. The hook stores only a hashed session key, compaction count, schema version, and update time in local plugin data, then deletes the record on session end. The existing bounded recovery packet, destination sentinel, safe fallback, and separately authorized post-verification source archival remain unchanged. No MCP server, hosted service, authentication, or reviewer credentials are used.

## USER-REQUIRED portal steps

- Confirm Apps Management write access in the submitting OpenAI organization.
- Complete and select the correct verified individual or business identity.
- Review legal text and publisher identity with qualified counsel if required.
- Confirm the website, support, privacy, and terms URLs resolve publicly from the final release ref.
- Choose only countries or regions where support and legal terms are ready.
- Upload the final skill bundle and production logo, enter listing details and prompts, and add the reviewer cases from `docs/REVIEWER_TESTS.md`.
- Review and complete policy attestations personally.
- Submit for review only when authorized.
- After approval, choose whether and when to publish. Approval and publication are not established by this repository.
