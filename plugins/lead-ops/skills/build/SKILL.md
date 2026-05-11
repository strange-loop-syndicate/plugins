---
name: build
description: >
  Run or resume the lead-ops data pipeline: discover, fetch/extract, filter, resolve, enrich, score, audit, export.
  Triggers: "/lead-ops:build", "run lead pipeline", "build lead database", "enrich leads", "score leads".
  Resumable state machine; stops between major phases by default for user review.
  Do NOT use if config does not exist (run /lead-ops:plan first) or for outreach (use /lead-ops:execute).
argument-hint: "[--from <phase>] [--source <id>] [--limit N] [--continuous] [--regenerate]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Task]
---

# Lead-Ops Build

Orchestrate the discover → enrich → score → audit → export pipeline. Each phase is resumable, and the skill stops between major phases by default so the user can review intermediate output. The skill owns coordination and merge logic; spawned agents own narrow transforms and write only to sidecar files. Never let two agents write the same file concurrently.

## When to invoke

Match these signals: the user says "/lead-ops:build", "run the lead pipeline", "build the lead database", "enrich leads", "score leads", or "resume the pipeline". Before doing anything else, confirm `./lead-ops.config.yaml` exists. If it does not, route the user to `/lead-ops:plan` and stop. Refuse to fabricate a default config.

## Read state

Open `./pipeline/state.json` if it exists; create the file with an empty state object otherwise. The state object tracks the last completed phase, the timestamp of each phase completion, the counts produced by each phase (candidates discovered, items enriched, leads scored, audit findings), and any partial-phase progress (e.g., source ids that completed inside the discover phase). Use the state to decide the default entry point: the next-due phase after the last completed phase.

## Argument parsing

Parse these flags from the invocation arguments:

- `--from <phase>` enters at a specific phase (`discover`, `enrich`, `prioritize`, `audit`, `export`). Override the state-derived default.
- `--source <id>` scopes discover to a single configured source. Other phases ignore this flag.
- `--limit N` bounds run size for testing (caps candidates per source in discover, items per batch in enrich, leads per audit sample).
- `--continuous` skips the user-review stops between phases. Use only when the user explicitly asks for an end-to-end run.
- `--regenerate` re-runs a phase that already produced output. Without this flag, phases with completed output skip to their gate check.

Surface the resolved plan to the user in one sentence before starting: which phase, which sources, which limits.

## Phase 1: Discover

For each enabled source in `./lead-ops.config.yaml`, spawn one `discoverer` agent. Discoverer instances can run in parallel because each writes to its own file at `./pipeline/discovered/<source-id>.json`. The skill passes each agent the source id, the source-specific params from config, and the scope constraints (geography, time range, success criteria). Discoverer fetches candidate records (title, url, source_type, source_specific_id, raw_metadata) and writes them out. It does not fetch full content — that is the extractor's job.

After every discoverer finishes, read all `./pipeline/discovered/*.json` files and produce `./pipeline/candidates.json`: a global deduplicated candidate list keyed by canonical id (url for web sources, PMID for PubMed, NCT id for clinicaltrials). Use stable id rules per source type; do not let one source overwrite another's records. Update `./pipeline/state.json` with the candidate count and per-source breakdown. Stop and report unless `--continuous`. Tell the user how many candidates each source produced, how many were deduplicated, and offer to proceed with `--from enrich`.

## Phase 2: Enrich

This phase has six sub-phases, each its own agent batch. Each sub-phase stops for user review by default. Sub-phases run sequentially because each depends on the previous one's output.

### 2a Extract

Spawn `extractor` agents in batches sized to the candidate count and any `--limit`. Each batch reads a slice of `./pipeline/candidates.json`, fetches full content for each candidate (API where possible, WebFetch otherwise, `r.jina.ai/` prefix for CAPTCHA-blocked pages), and persists raw content via `${CLAUDE_PLUGIN_ROOT}/scripts/evidence_store.py` to `./pipeline/evidence_store/<type>/<id>.<ext>`. Each batch writes structured metadata and a content-derived summary (one to three sentences capturing substance, not a paraphrase of the title) to `./pipeline/enriched/<batch-id>.json`. Extractor must self-verify before reporting done: re-read five random items, compare summary against source content, fix mismatches. Stop and report counts.

### 2b Filter

Spawn one `relevance-filter` agent over the enriched batch. Pass the `relevance.keep_criteria` and `relevance.remove_criteria` strings from config. Agent writes `./pipeline/filter-<timestamp>.json` with `{keep, remove, reasons}` arrays. The skill applies the filter to produce `./pipeline/enriched-filtered.json`; agent does not delete anything. Stop and report keep/remove counts with a sample of reasons.

### 2c Resolve

Spawn one `entity-resolver` agent against the filtered enriched set and the existing `./leads.json` (treat as empty if the file does not exist). The agent performs layered matching per genesis §2 Phase 4: PMID overlap → full name plus institution → surname plus first initial plus institution → surname plus specialty plus location → fuzzy fallback → manual flag. Agent writes `./pipeline/resolve-<timestamp>.json` with `{merges, new_leads, manual_review}`. The skill applies merges (append evidence to existing leads, dedup by url), inserts new leads, and surfaces the manual review list. Stop and report.

### 2d Meta enrich

Spawn one `metadata-enricher` agent over leads missing judgment fields (stance, category, tier, domain_relation, recency). Agent reads each lead's evidence and writes values to `./pipeline/meta-<timestamp>.json` keyed by lead id. The skill applies updates to `./leads.json`. Use plain LLM judgment; never keyword-match. Stop and report coverage.

### 2e External cross-ref

If `external_data` is configured, spawn one `external-cross-ref` agent per external file. Pass the file path, match fields, and fields-to-pull. Agent performs layered matching, writes `./pipeline/external-<source>-<timestamp>.json` with per-lead enrichments and source attribution. Skill applies updates, flagging any conflicts where existing values differ from external values rather than silently overwriting. Stop and report match rate per external source.

### 2f Social enrich

For each entry in the top-level `social_channels:` block of `./lead-ops.config.yaml`, spawn one `social-enricher` agent. Skip this sub-phase entirely if `social_channels` is empty or absent. Pass the agent the matching channel spec (`channel`, `session_cookie_path`, `fields`, `min_signals_required`) and the path to the active browser session cookie store. The agent searches "Name + Institution", evaluates the top three to five results with multi-signal scoring (name match, institution match, field relevance, mutual connections), navigates to the selected profile, and extracts fields. The agent runs mandatory audit checkpoints every `audit.checkpoint_interval` leads (default 20): it stops, presents the batch, and waits for skill-mediated user approval before continuing. The "missing > wrong" rule is non-negotiable — wrong matches must be flipped to `not_found`. Agent writes `./pipeline/social-<timestamp>.json`. Skill applies and stops for final review.

## Phase 3: Prioritize

Call `${CLAUDE_PLUGIN_ROOT}/scripts/priority_score.py` via Bash with the config and leads file: `python -m priority_score --config ./lead-ops.config.yaml --leads ./leads.json`. The script parses the scoring expressions from config and updates the `priority` field on every lead. No agent is needed; this is pure rule application and must be idempotent. After the script finishes, read the priority distribution from `./leads.json` and report counts per bucket. Stop unless `--continuous`.

## Phase 4: Audit

Spawn the `qa-auditor` agent (Opus model). Pass the path to `./leads.json` and `./pipeline/evidence_store/`. The agent spot-checks broken URLs (sample N from each rating tier, fetch, verify status), hallucinated identifiers (verify PMIDs and NCT ids against authoritative APIs), duplicates (normalize names and cross-compare), redundant fields (evidence summary == domain_relation), wrong-profile signals (institution mismatch between social profile and primary evidence), and any other issue surfaced in genesis §4. Agent writes `./pipeline/audit-report-<timestamp>.md` with severity-ranked findings and concrete remediation suggestions. Stop and walk the user through findings. Apply fixes the user approves; surface unresolved issues for follow-up.

## Phase 5: Export

Call the surface script matching the configured working surface type: `python ${CLAUDE_PLUGIN_ROOT}/templates/surfaces/<type>/surface.py upsert --config ./lead-ops.config.yaml --leads ./leads.json` for Sheets, CSV, or local JSON. For Google Sheets specifically, the surface script wraps `${CLAUDE_PLUGIN_ROOT}/scripts/sheet_upload.py` which backs up the current sheet to `./exports/sheet_backup_<ts>.json` before writing, uses `valueInputOption=RAW` for every write, and applies targeted cell updates rather than full sheet rewrites. After export, report counts written, counts updated, counts unchanged, backup path, and any cells flagged for manual attention.

## State updates

After each phase completes successfully, write a state update to `./pipeline/state.json`: the phase name, completion timestamp, output counts, and any partial-phase progress. State updates must be atomic — write to a temp file and rename, never edit in place. The state file is the source of truth for `--from` defaults and for the `/lead-ops:execute --status` skill; treat it as a contract.

## Failure modes to avoid

The pipeline is most vulnerable at the points where genesis §4 documented real failures. Do not let any of these recur silently:

- **Hallucinated PMIDs or other source identifiers** — never trust agent-generated ids. Verify every PMID against NCBI esummary via `${CLAUDE_PLUGIN_ROOT}/scripts/ncbi_fetch.py` and every URL against an actual fetch. The extractor and qa-auditor both enforce this.
- **Wrong-profile selection in social enrichment** — name match alone is insufficient. Social-enricher must use multi-signal scoring and obey the checkpoint protocol. "Missing > wrong" is the rule.
- **Sheet schema drift** — the export script writes RAW values, no semicolons after URLs, no autoparseable strings like `+27` unescaped. Backup first, write second.
- **Broken or outdated evidence URLs** — qa-auditor spot-checks fetch status. Failed URLs become candidates for removal, not silent retention.
- **Duplicate lead records** — entity-resolver applies aggressive name normalization via `${CLAUDE_PLUGIN_ROOT}/scripts/name_normalize.py`. Qa-auditor cross-scans for residual duplicates.
- **Non-target items polluting the database** — relevance-filter is LLM judgment, not keyword matching. Trust the agent but verify via the audit phase.

## Coordination rules

Never spawn parallel agents writing to the same output file. Each agent owns a sidecar file keyed by batch id or timestamp; the skill applies merges into `./leads.json` and `./pipeline/state.json`. Dismiss agents promptly after each phase completes — idle agents consume memory and contribute nothing. For long phases (extract over thousands of candidates, social enrich at full scale), spawn a background verifier agent that monitors progress and surfaces stalls; do not have the parent session poll synchronously. Update `./pipeline/state.json` only from the skill orchestrator, never from agents directly. If a phase fails mid-batch, leave the partial sidecar in place and resume on the next `--from <phase>` invocation rather than re-running from scratch.

When user-review stops surface intermediate output, summarize counts and show three to five representative samples per category — not the full dataset. The user needs enough signal to spot drift, not a wall of records. Reserve full dumps for explicit user requests.
