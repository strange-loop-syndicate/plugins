# lead-ops v0.1.0 Build Spec

This is the working specification for plugin implementation. It assumes you have already read `session-genesis.md` in the same directory — that is the authoritative context for WHY each decision was made. This file says WHAT to build.

## Locked decisions

- **Plugin name:** `lead-ops`
- **Version:** 0.1.0
- **Author:** Oleg Ovsyannikov <oleg.ovsyannikov@gmail.com>
- **License:** MIT
- **Repository convention:** mirror deep-research plugin layout (skills/<name>/SKILL.md, agents/<name>.md, scripts/, templates/, reference/)
- **Config format:** YAML, single file at project root (`lead-ops.config.yaml`)
- **No `.claude/lead-ops.local.md`** for v1

### Skill flow defaults

| Skill | Default behavior |
|---|---|
| `plan` | After writing config, STOP and ask user to review. Do not auto-launch `build`. |
| `build` | STOP between major phases (discover → review → enrich → review → score → review → audit → review → export). Flag `--continuous` for end-to-end run. |
| `build` audit checkpoint interval | 20 items, overridable via `audit.checkpoint_interval` in config. |
| `execute` outreach state | Track in `leads.json` field `outreach_sent: [{channel, date, message_id, content_hash}]`. Skip leads with matching channel already sent unless `--regenerate`. |

### Agent model defaults

| Agent | Model |
|---|---|
| discoverer, extractor, relevance-filter, entity-resolver, metadata-enricher, external-cross-ref, outreach-writer | Sonnet |
| social-enricher | Sonnet (with browser tool access) |
| qa-auditor | Opus |

## Component inventory

### Skills (3)

```
skills/plan/SKILL.md
skills/build/SKILL.md
skills/execute/SKILL.md
```

Each skill is user-invoked (`/lead-ops:plan`, `/lead-ops:build`, `/lead-ops:execute`). Frontmatter must include `description`, `argument-hint`, `allowed-tools`. Instructions are written FOR Claude (not TO the user).

**`/lead-ops:plan` (skills/plan/SKILL.md)**

- Purpose: interactive scoping + market/domain research + pipeline planning. Writes `lead-ops.config.yaml` + `lead-ops-plan.md`.
- Inputs: optional argument is a one-liner project description (e.g., "oncology EA DOL outreach" or "early-stage fintech CTO prospecting"). If absent, start from a blank slate.
- Flow:
  1. Detect if `lead-ops.config.yaml` exists in cwd; if yes, ask whether to extend or replace.
  2. Run ICE-style clarifying conversation, one question at a time (genesis §2 Phase 0). Cover: domain, geography, time range, success criteria, stance filters, evidence threshold.
  3. If user needs market/domain familiarity, suggest `/deep-research` and pause until they return. Do NOT inline a research pass inside `plan`.
  4. Propose source modules (from `templates/sources/` library — see inventory below) with brief rationale per choice; let user confirm/add/remove.
  5. Propose lead schema (core fields always present + custom fields specific to this domain). Show as YAML preview.
  6. Propose scoring rules (priorities A-D + X override). Default rule set adapted from genesis §6.
  7. Pick working surface (Google Sheets / CSV / local JSON). For Sheets, ask for spreadsheet ID + tab; for CSV, file path.
  8. Pick outreach channels (LinkedIn note, cold email, Twitter DM). Ask for templates or use defaults from `templates/channels/`.
  9. Set audit defaults (checkpoint interval, require_user_approval).
  10. Write `lead-ops.config.yaml` and `lead-ops-plan.md`. Show file paths.
  11. STOP. Tell user: "Review config. Run `/lead-ops:build` when ready."

**`/lead-ops:build` (skills/build/SKILL.md)**

- Purpose: state-machine that runs discover → enrich → score → audit → export, resumable at any phase.
- Inputs:
  - `--from <phase>` to enter at a specific phase (discover|enrich|prioritize|audit|export). Default = next-due phase from state file `pipeline/state.json`.
  - `--source <id>` to scope discover to one source.
  - `--limit <N>` to bound runs for testing.
  - `--continuous` to skip user reviews between phases.
  - `--regenerate` to redo phases that produced output.
- Flow per phase (each is a section in the skill):
  1. **Discover**: For each configured source, spawn `discoverer` agent. Each writes candidates to `pipeline/discovered/<source-id>.json`. Dedup globally → `pipeline/candidates.json`. STOP for review.
  2. **Enrich**: Pipelined sub-phases, each its own agent spawn batch.
     - 2a. `extractor` reads candidates → fetches content (via Bash + scripts) → writes structured metadata + content-derived summary → `pipeline/enriched/<id>.json`. Persists raw content to `pipeline/evidence_store/`.
     - 2b. `relevance-filter` reads enriched → writes `keep/remove/reasons` JSON. Apply filter.
     - 2c. `entity-resolver` matches survivors against existing `leads.json`. Merges evidence into existing leads; creates new lead records for unmatched.
     - 2d. `metadata-enricher` fills stance/category/tier/domain_relation for every lead missing them.
     - 2e. `external-cross-ref` runs if `external_data` configured. Pulls email/phone/etc per match.
     - 2f. `social-enricher` runs if any social_channels configured (e.g., linkedin_url). MANDATORY audit checkpoints every N leads. Each lead gets multi-signal evaluation (name + institution + field + mutual connections). Wrong matches → `not_found`.
     STOP for review between each sub-phase by default.
  3. **Prioritize**: Call `scripts/priority_score.py` against `leads.json` with rules from config. No agent — pure rule application. STOP for review.
  4. **Audit**: Spawn `qa-auditor` (Opus). Read whole evidence store, spot-check N% of leads, report: broken URLs, duplicates, hallucinated IDs, redundant fields, wrong-profile sniff test results. Generate `pipeline/audit-report-<timestamp>.md`. STOP for review.
  5. **Export**: Call `scripts/surface_<type>.py` for working surface from config. Backup-first, RAW writes, targeted updates. STOP — return summary.

**`/lead-ops:execute` (skills/execute/SKILL.md)**

- Purpose: plan outreach strategy + draft messages + show status.
- Inputs:
  - `--status` to show pipeline state only (counts per priority bucket, last activity, channels used, send counts) and exit.
  - `--channel <id>` to target one configured channel.
  - `--priority <A|B|C|D>` to filter leads.
  - `--limit <N>` to bound batch size.
  - `--regenerate` to re-draft already-sent leads (default: skip).
- Flow:
  1. Read `lead-ops.config.yaml` + `leads.json`.
  2. If `--status`, report stats and exit.
  3. Plan strategy: discuss with user — sequencing across channels, batching, who-first. Brief conversation, write `exports/outreach/strategy-<date>.md`.
  4. Spawn `outreach-writer` agents (one per channel or one per batch — implementer's call). Each writes per-lead drafts honoring channel length/tone rules from `templates/channels/<channel>.yaml`.
  5. Output: `exports/outreach/<channel>/<date>-<batch>.md` with copy-paste-ready blocks (one lead per block, headed by lead name + key context for user).
  6. After user sends and tells `execute` so, update each lead's `outreach_sent` array.

### Agents (9)

```
agents/discoverer.md
agents/extractor.md
agents/relevance-filter.md
agents/entity-resolver.md
agents/metadata-enricher.md
agents/external-cross-ref.md
agents/social-enricher.md
agents/outreach-writer.md
agents/qa-auditor.md
```

Each agent file must have frontmatter:
```yaml
---
name: <agent-name>
description: When to use. Include 1-2 <example> blocks showing user-facing trigger + assistant decision.
tools: [list, of, allowed, tools]
model: sonnet|opus|haiku
color: <hex or named>
---
```

Body = system prompt. Each agent's responsibility is narrow and well-bounded.

Required contracts (apply to every agent):
- **No agent modifies `leads.json` directly.** They write to sidecar JSON files; `build` skill applies the merge.
- **No agent spawns other agents.** Skills orchestrate.
- **Audit checkpoint protocol** for any batched judgment work: stop every N (default 20), present sample, wait for approval, then continue.
- **Self-verification**: spot-check 5 random outputs before reporting done; report verification results.
- **Missing > wrong**: when uncertain, mark `not_found` / `unknown` rather than guess.

Per-agent specs (concise — full instructions in each agent file):

- **`discoverer`** — Takes `(source_module_id, source_config, scope_constraints)` from skill. Calls the configured source module (PubMed/web_search/web_scrape/clinicaltrials). Outputs candidate list with: title, url, source_type, source_specific_id, raw_metadata. NO content fetch (that's extractor's job).

- **`extractor`** — Takes candidate batch. For each: fetch full content (API where possible, WebFetch otherwise, `r.jina.ai/` for CAPTCHA pages). Persist raw to `pipeline/evidence_store/<type>/<id>.<ext>`. Extract structured fields per schema. Write **content-derived** summary (1-3 sentences capturing substance, NOT title paraphrase). Self-verifies: re-reads 5 random items, checks summary against source.

- **`relevance-filter`** — Takes enriched items + relevance criteria from config (plain English). Outputs `{keep: [], remove: [], reasons: {<id>: "..."}}`. Does NOT delete anything — skill applies.

- **`entity-resolver`** — Takes new items + existing `leads.json`. Performs layered matching (genesis §2 Phase 4: PMID overlap → full name+institution → surname+initial+institution → surname+specialty+location → fuzzy fallback → manual flag). Outputs `{merges: [{existing_id, evidence_to_add}], new_leads: [], manual_review: []}`.

- **`metadata-enricher`** — For each lead missing judgment fields (stance/category/tier/domain_relation/recency), reads its evidence and writes values. Plain LLM judgment, no keyword matching. Outputs `{<lead_id>: {field: value, ...}}`.

- **`external-cross-ref`** — Takes leads + user-provided external_data spec (file, match_on, fields_to_pull). Layered matching, writes `{<lead_id>: {field: value, source: external_data_id}}`. Does not overwrite existing values without flagging conflict.

- **`social-enricher`** — Takes lead batch + channel spec (e.g., LinkedIn config with logged-in cookie path). For each lead: search for "Name + Institution", evaluate top 3-5 results with multi-signal scoring, navigate to selected profile, extract fields. **Mandatory checkpoint every 20 leads.** "Missing > wrong." Outputs per-lead enrichment with `confidence` flag.

- **`outreach-writer`** — Takes lead batch + channel template + strategy notes. Per lead, drafts message respecting: char limit, tone rules, evidence-specific reference, no first-touch product pitch, no sender-company mention, sender first-name footer. Validates length before output. Outputs `{lead_id: {channel: id, draft: "...", char_count: N, evidence_used: [url], notes: "..."}}`.

- **`qa-auditor`** (Opus) — Reads whole `leads.json` + `pipeline/evidence_store/`. Spot-checks: broken URLs (sample N, fetch, verify status), hallucinated IDs (verify against API where applicable), duplicates (normalize-and-compare), redundant fields (evidence summary == domain_relation?), wrong-profile signals (institution mismatch between LinkedIn and primary evidence). Outputs structured `audit-report-<timestamp>.md` with severity-ranked findings.

### Scripts (5)

```
scripts/ncbi_fetch.py            # file-locked rate-limited NCBI E-utilities wrapper
scripts/sheet_upload.py          # bulk Google Sheets OAuth REST writer (backup-first, RAW)
scripts/priority_score.py        # config-driven priority scorer
scripts/name_normalize.py        # academic-suffix stripping, fuzzy matching
scripts/evidence_store.py        # persist raw content; lookup by URL/ID; verify by hash
```

Standalone CLIs (each with `python -m` invocation pattern), well-documented args, idempotent, no side effects beyond declared output paths. Use `requests`, `pyyaml`, stdlib only — no exotic deps.

- **`ncbi_fetch.py`** — three functions exposed via CLI subcommands: `elink-similar <pmid>`, `esummary <pmids...>`, `efetch <pmid>`. File lock at `/tmp/ncbi_rate.lock`, min interval 0.35s. Persists raw XML to `pipeline/evidence_store/pubmed/<pmid>.xml`. Genesis §6 pattern.

- **`sheet_upload.py`** — `python -m sheet_upload --config lead-ops.config.yaml --leads leads.json [--dry-run]`. Reads OAuth creds from `~/.google_workspace_mcp/credentials/<email>.json` (path configurable). Backs up current sheet to `exports/sheet_backup_<ts>.json` first. Writes with `valueInputOption=RAW`. Targeted updates only.

- **`priority_score.py`** — `python -m priority_score --config lead-ops.config.yaml --leads leads.json`. Parses scoring rules (string expressions like genesis §6 example). Updates `priority` field on each lead. Idempotent.

- **`name_normalize.py`** — utility library + CLI. Strips academic suffixes (MD, PhD, JD, MPH, MBA, MBE, PharmD, DO, FACNM, FASCO, BCPS, BCCCP, CIP, RN, BSN, RPh, Esq, DNP, PharmB, FNP and others). Lowercase. Strip middle initials. Library exposes `normalize(name)`, `match_layered(a, b, layer)`, `fuzzy_score(a, b)`.

- **`evidence_store.py`** — library + CLI. `store(url, content, type, id)` → persists to `pipeline/evidence_store/<type>/<id>.<ext>`. `retrieve(type, id)` → reads. `verify(url)` → fetches and compares hash. CLI: `python -m evidence_store verify --leads leads.json` to bulk-check.

### Templates (12)

#### Source modules (`templates/sources/`) — 4 files

Each is a Python module + YAML config snippet, both in one directory. Plus a `_template.py` showing the minimal contract a custom source must implement.

```
templates/sources/_template.py           # contract: discover(seeds, criteria) -> [Candidate]
templates/sources/pubmed/
  discover.py
  config_snippet.yaml
templates/sources/web_search/
  discover.py
  config_snippet.yaml
templates/sources/web_scrape/
  discover.py
  config_snippet.yaml
templates/sources/clinicaltrials_gov/
  discover.py
  config_snippet.yaml
```

Each `discover.py` exposes one entry: `discover(scope, params) -> list[dict]` where dict has `{title, url, source_id, source_type, raw_metadata}`. Use `scripts/ncbi_fetch.py` (for PubMed) or `requests` (others) — NOT WebFetch tool, since these run in agent context.

#### Working surfaces (`templates/surfaces/`) — 3 files

```
templates/surfaces/google_sheets/
  surface.py        # imports/uses scripts/sheet_upload.py
  config_snippet.yaml
templates/surfaces/csv/
  surface.py
  config_snippet.yaml
templates/surfaces/local_json/
  surface.py
  config_snippet.yaml
```

Contract: `setup(config)`, `upsert(config, leads)`, `read(config) -> leads`, `backup(config) -> path`.

#### Outreach channels (`templates/channels/`) — 3 files

```
templates/channels/linkedin_connection_note.yaml
templates/channels/cold_email.yaml
templates/channels/twitter_dm.yaml
```

Each YAML has: `id`, `max_chars`, `tone`, `template` (Jinja-style placeholders: `{name}`, `{evidence_ref}`, `{sender}`), `rules` (list of must/must-not strings), `example` (a few rendered samples).

#### Config examples (`templates/configs/`) — 2 files

```
templates/configs/lead-ops.config.skeleton.yaml    # minimal config to start a new project
templates/configs/lead-ops.config.example.yaml     # full oncology-DOL example from genesis
```

### Config schema (`lead-ops.config.yaml`)

Single root file. Sections:

```yaml
project:
  name: string
  description: string
  domain: string

scope:
  geography: [string]
  time_range: string             # e.g., "2010+"
  success_criteria: string
  custom: {}                     # free-form project-specific fields

sources:                          # list of enabled source modules
  - id: string                    # unique within project
    type: pubmed|web_search|web_scrape|clinicaltrials_gov|custom
    params: {}                    # source-specific (seeds, queries, filters)

schema:
  core_fields:                    # always present, list of field names with types
  custom_fields:
    - name: string
      type: enum|string|number|bool
      values: [string]            # required for enum
      description: string

relevance:
  keep_criteria: string           # plain English, passed to relevance-filter agent
  remove_criteria: string

scoring:
  priorities:                     # ordered, first match wins
    A: <expression>               # e.g., "stance == 'strong_advocate' and tier <= 1 and ev_count >= 2 and (reachable or quotable)"
    B: <expression>
    C: <expression>
    D: <expression>
  overrides:
    X: "do_not_approach or competitor"

working_surface:
  type: google_sheets|csv|local_json
  config: {}                     # surface-specific

external_data:                    # optional
  - name: string
    file: path
    match_on: [field_name]
    fields_to_pull: [field_name]

outreach:
  channels:
    - id: linkedin_connection_note|cold_email|twitter_dm|custom
      template_overrides: {}     # override defaults from templates/channels/

audit:
  checkpoint_interval: 20
  require_user_approval: true
  qa_sample_pct: 0.05
```

## Implementation guidance for teammates

- **Read genesis first.** Genesis doc is in `reference/session-genesis.md`. Lessons there are not negotiable.
- **Skill instructions are FOR Claude, not the user.** Use imperative form. No "you should consider..." — say "do X".
- **Skill body 1500-2000 words target.** Push detailed content to `reference/` files; skill file references them.
- **Agent descriptions are third-person + include 2+ `<example>` blocks** showing trigger user message → assistant decision to spawn agent.
- **No code snippets in skill bodies.** Describe what to do and why. Code goes in scripts/templates.
- **No emojis anywhere in plugin files.**
- **Use `${CLAUDE_PLUGIN_ROOT}` for any paths inside plugin files** (per plugin-dev convention).
- **Scripts must be runnable standalone** with `python -m <name>` — they go in plugin dir, not user project.
- **Templates are copy-and-customize.** They live in the plugin; user copies into their project.

## File path conventions

In skill instructions, reference plugin assets as:
- `${CLAUDE_PLUGIN_ROOT}/scripts/ncbi_fetch.py`
- `${CLAUDE_PLUGIN_ROOT}/templates/sources/pubmed/`
- `${CLAUDE_PLUGIN_ROOT}/agents/extractor.md`

Reference user project assets as:
- `./lead-ops.config.yaml`
- `./leads.json`
- `./pipeline/discovered/<id>.json`
- `./exports/outreach/<channel>/<date>-<batch>.md`

## Out of scope for v1

- Notion / Airtable working surfaces (v2)
- Twitter/Bluesky API channel (v2 — only manual DM template for v1)
- Hooks for any event
- MCP server
- Automated send (always user-mediated)
- CRM features (replies, status tracking beyond send-date)

## Acceptance criteria

- Plugin loads via `cc --plugin-dir <path>` without manifest errors.
- All 3 skills show in `/help` under `lead-ops:` namespace.
- All 9 agents discoverable when skill prompts mention them.
- All 5 scripts pass `python -m <name> --help` and have meaningful help text.
- All 12 templates valid YAML or Python (syntax check passes).
- Config skeleton + example both load via `yaml.safe_load()`.
- README quickstart is accurate (commands work as listed).
- Plugin-validator agent reports no critical errors.
- Each skill written in imperative form, addressed to Claude not user.
- Each agent has 2+ example blocks in description.
- No code snippets in any SKILL.md.
- No emojis in any file.
