# Privacy Policy

Effective date: August 14, 2026

Context Handoff is a local plugin. It does not operate a hosted service, require an account, use an MCP server, transmit data to the developer, or collect analytics.

When the user enables and trusts the bundled lifecycle hooks, the plugin stores a minimal context-health record in Codex's local plugin data directory. The record contains a SHA-256 digest of the Codex session identifier, a schema version, the number of observed compactions, and the last update time. It does not store prompts, responses, transcript contents, repository contents, paths, credentials, or the original session identifier. The record is deleted when Codex delivers the session-end lifecycle event; an interrupted session may leave the small local record until plugin data is removed.

The plugin instructs Codex to create a temporary handoff packet from task context. That packet can contain repository paths, task requirements, evidence summaries, and other information the user asked Codex to preserve. It must exclude credentials, tokens, personal data, and unrelated conversation content. The packet is stored in the user's local temporary storage or another user-approved local location.

The packet remains available through destination verification and any authorized source-thread archival attempt. Cleanup occurs only with user authorization and when another adequate recovery record remains; otherwise the plugin discloses the retained path. Lifecycle hook execution, thread creation, navigation, and optional archival use Codex capabilities supplied by OpenAI and are governed by the user's OpenAI account and applicable OpenAI policies.

Questions or privacy requests may be opened through [GitHub support](https://github.com/timyeou1234/context-handoff/issues).
