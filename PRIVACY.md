# Privacy Policy

Effective date: October 15, 2026

Context Handoff is a local plugin. It does not operate a hosted service, require an account, use an MCP server, transmit data to the developer, or collect analytics.

When the user enables and trusts the bundled lifecycle hooks, the plugin stores a minimal context-health record in Codex's local plugin data directory. The record contains a SHA-256 digest of the Codex session identifier, a schema version, the number of observed compactions, the last update time, notification severity and the count of user turns since the last notification. It does not store prompts, responses, transcript contents, repository contents, paths, credentials, or the original session identifier. The record is deleted when Codex delivers the session-end lifecycle event; an interrupted session may leave the small local record until plugin data is removed.

The plugin instructs Codex to create a temporary handoff packet from task context. That packet can contain repository paths, task requirements, evidence summaries, and other information the user asked Codex to preserve. It must exclude credentials, tokens, personal data, and unrelated conversation content. The packet is stored in the user's local temporary storage or another user-approved local location.

The packet remains available through destination verification and any authorized source-thread archival attempt. Cleanup occurs only with user authorization and when another adequate recovery record remains; otherwise the plugin discloses the retained path. Lifecycle hook execution, thread creation, navigation, and optional archival use Codex capabilities supplied by OpenAI and are governed by the user's OpenAI account and applicable OpenAI policies.

Questions or privacy requests may be opened through [GitHub support](https://github.com/timyeou1234/context-handoff/issues).

The optional usage command reads only explicitly supplied local rollout files and emits session identity, file path, aggregate token counters and integrity indicators. It does not output transcript text or send data to a service. Usage snapshots and handoff packets remain local until the user-authorized thread creation includes the bounded packet.

The optional evidence helper also examines the exact session’s tool-call/result records to correlate an observed Goal response, plus model settings and completion timestamps. It emits structured Goal state and usage metadata, never raw transcript text. It follows an archived rollout only by the same filename and rechecks session identity. Goal state can contain user-provided task details; review saved evidence before sharing it. Public benchmark summaries omit private task identifiers, transcript content and local filesystem paths.
