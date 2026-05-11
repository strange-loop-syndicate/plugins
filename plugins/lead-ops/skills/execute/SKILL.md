---
name: execute
description: >
  Plan outreach strategy, draft per-channel messages for prioritized leads, and report pipeline status.
  Triggers: "/lead-ops:execute", "draft outreach", "lead-ops status", "outreach plan", "write messages".
  Skips already-sent leads by default; --regenerate to redo.
  Do NOT use if leads.json is empty (run /lead-ops:build first).
argument-hint: "[--status] [--channel <id>] [--priority <A|B|C|D>] [--limit N] [--regenerate]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Task]
---

# Lead-Ops Execute

Plan an outreach campaign and produce per-lead, per-channel draft messages ready for the user to send. Every send is user-mediated; this skill produces drafts only and never auto-sends. Drafts honor channel-specific length, tone, and rule constraints, and reference specific evidence from each lead's record rather than generic outreach language.

## When to invoke

Match these signals: the user says "/lead-ops:execute", "draft outreach", "write messages", "plan an outreach campaign", "lead-ops status", or "show pipeline status". Before doing anything else, confirm both `./lead-ops.config.yaml` and `./leads.json` exist. If config is missing, route to `/lead-ops:plan`. If leads.json is missing or empty, route to `/lead-ops:build` and stop. Refuse to draft messages without a prioritized lead set.

## --status mode

If the invocation contains `--status`, do not draft anything. Read `./leads.json`, `./pipeline/state.json`, and any files under `./exports/outreach/`. Print a status table containing: total leads, counts per priority bucket (A, B, C, D, X), counts per stance and per category, the timestamp of the last completed phase from state.json, send counts per channel (extracted from each lead's `outreach_sent` array), and response counts if the user has tracked them. Include the last build run timestamp and the last export timestamp. Exit after the table; do not advance to strategy planning.

## Strategy planning

For non-status runs, open a brief strategy conversation with the user before drafting anything. Cover four topics with one question per turn:

- **Channel selection** — which configured channels to use for this campaign. Default to all channels in `lead-ops.config.yaml` unless the user narrows scope or passes `--channel <id>`.
- **Priority targeting** — which buckets to address. Default to A and B unless overridden by `--priority`. Confirm whether to skip leads already contacted on the selected channels.
- **Sequencing and batching** — how many messages per batch (default 25 per channel per batch), and the order across channels when multiple are active (e.g., LinkedIn note first, follow with cold email after one week).
- **Who first** — any specific leads to lead with (the user often has anchor names), and any leads to hold back.

Capture the conversation outcome to `./exports/outreach/strategy-<date>.md` as a short campaign brief: target buckets, channel sequencing, batch sizes, named priority leads, and any explicit holds. The strategy doc is a contract for the subsequent draft step and a record the user can reference later.

## Filter leads

Build the working set by reading `./leads.json` and applying these filters in order: priority bucket filter from strategy or `--priority`, channel filter from strategy or `--channel`, lead-count cap from `--limit`. Then skip any lead whose `outreach_sent` array already contains an entry matching the current channel, unless `--regenerate` is set. The `outreach_sent` schema is `[{channel, date, message_id, content_hash}]`; matching is on channel id alone for skip purposes, regardless of date.

Report the working set size before drafting: how many leads in scope, how many skipped due to prior sends, how many will be drafted per channel. Confirm with the user that the working set looks right, especially if the skip count is unexpectedly high.

## Draft messages

Spawn `outreach-writer` agents in batches, one batch per channel. Each batch handles up to the configured batch size (default 25). Pass each batch the lead records, the channel template from `${CLAUDE_PLUGIN_ROOT}/templates/channels/<channel>.yaml`, the strategy brief, and any `template_overrides` from the project config.

Each agent produces a copy-paste-ready output file at `./exports/outreach/<channel>/<date>-<batch>.md`. The file format is one block per lead, separated by horizontal rules, with each block headed by the lead's name and one line of relevant context (the `domain_relation` field is usually the right anchor), followed by the drafted message, followed by the character count. The output is optimized for the user to scan and copy individual messages quickly, not for machine consumption.

Pass the agent strict guidance on the per-channel rules from the YAML template: maximum character count, required tone (warm-professional, academic-formal, etc.), required content (specific evidence reference, sender first-name footer), forbidden content (no product pitch in first touch, no sender-company name, no boilerplate openings). The agent must reference a specific piece of the lead's evidence in every draft — paper title, conference talk, role, recent publication — not generic compliments.

## Validation

For each draft produced, validate that the character count does not exceed the channel `max_chars` from the channel YAML. Reject any draft that overshoots and have the agent regenerate. Run a sniff check on a sample of five drafts per batch: confirm each references a real piece of evidence that exists in the lead's record (not hallucinated), each includes the sender first-name footer, and none mentions the sender company or pitches a product. If any sample fails, regenerate the whole batch with reinforced guidance rather than patching individual drafts.

Validation is the place where small drift becomes large drift if missed. Reject quickly and regenerate; do not let the user discover format violations after they have already copy-pasted ten messages.

## Post-send tracking

After drafts are written, instruct the user how to record sends. The convention: when the user has actually sent a batch, they tell this skill which batch file they sent and the skill records the sends. If implementing the `--mark-sent <batch-file>` flag, parse the batch file for lead ids, then for each lead append a new entry to `./leads.json` under `outreach_sent`: `{channel: <id>, date: <iso8601>, message_id: <batch-file-basename>, content_hash: <sha256 of draft>}`. Write `./leads.json` atomically (temp file plus rename) and report the count of sends recorded.

If the user is using a tracking layer outside this plugin (CRM, sheet column), record sends there and pass the same metadata back so subsequent runs of this skill correctly skip already-contacted leads. The skill must trust the `outreach_sent` array on each lead as the canonical record; if the user has marked sends in the working surface but not back-synced to `./leads.json`, surface the divergence rather than silently drafting duplicates.

Recommend the user run `--status` immediately after sending a batch to confirm the recorded send counts match the channel-side tally. Drift between drafted, sent, and recorded numbers is the single most common source of accidental duplicate outreach, and the cost of a duplicate connection note to a senior contact is high.

## Reporting

After drafting completes, surface a final summary: total drafts produced, breakdown by channel, character-count distribution per channel, any leads that produced regeneration cycles, and the absolute paths to each batch file. Remind the user that nothing has been sent yet and that they need to copy from the batch files into the actual channel manually. Recommend they re-run with `--status` after sending so the priority and send counts stay in sync.

Include in the report any leads that were skipped due to prior sends on the selected channels — list them with their priority bucket so the user can spot-check whether the skip was correct or whether a re-engagement is intended (in which case the user re-runs with `--regenerate`). Skipped leads should not be invisible; they are part of the campaign's footprint.

## Channel rules

Each channel YAML at `${CLAUDE_PLUGIN_ROOT}/templates/channels/<id>.yaml` is the source of truth for that channel's drafting constraints. The outreach-writer agent reads the YAML for its assigned channel and enforces every rule: `max_chars`, `tone`, the `template` body with placeholder semantics, the must-include list (specific evidence reference, sender first name), and the must-not-include list (product pitch in first touch, sender company name, vague openings, exclamation marks unless the channel template allows). For LinkedIn connection notes the practical hard cap is 300 characters; staying under 280 leaves margin for safety. For cold email the body length is 500 to 800 characters of substance, with subject line drafted separately. For Twitter DM the limit is 1000 characters but anything over 400 reads as overlong; aim for 300 to 400.

The agent must never invent channel rules or guess at limits. If a channel YAML is missing, halt and surface the missing file to the user rather than producing drafts under unknown constraints.

## Do not auto-send

Every send is user-mediated. This skill produces drafts only. Do not call any send API, do not enqueue messages with any third-party scheduler, do not log "as sent" without explicit user confirmation. The genesis lessons are clear on this: the working surface (Sheets, CSV, or local JSON) is the CRM, and the human is the sender. The plugin's job is to produce excellent drafts and an organized record of what has been sent, not to automate channels that have terms-of-service constraints or relationship costs around bulk sending.

If the user asks for automated sending in a future session, route them to the build spec's "Out of scope for v1" note and explain that the plugin intentionally stops at draft generation. Suggest they wire a separate, channel-specific send tool against the produced batch files if they accept the operational and ethical risk; do not build that integration here.
