# lead-ops

Evidence-first, domain-agnostic lead research and outreach pipeline for Claude Code.

## What it does

Walks you through a verifiable lead-discovery pipeline:

1. **`/lead-ops:plan`** — interactive scoping, source/schema/scoring design, writes `lead-ops.config.yaml`
2. **`/lead-ops:build`** — discover → fetch/extract → filter → resolve → enrich (meta + cross-ref + social) → score → audit → export. Resumable state machine.
3. **`/lead-ops:execute`** — plan outreach strategy, draft per-channel messages, track send status.

Every lead carries a verifiable fetched-URL evidence record. LLM agents handle judgment; Python scripts handle data ops. Mandatory audit checkpoints every N items prevent silent drift.

## Use cases

DOL/KOL identification (the original use case), B2B SaaS prospecting, journalist source-building, hiring pipelines, investor lists, real-estate prospects, political advocacy targets, academic collaboration scouting — anywhere you need to build a verified, prioritized contact database from public-web evidence.

## Architecture

- **3 skills** orchestrate the pipeline (`plan`, `build`, `execute`)
- **9 specialized agents** do per-item judgment work in isolation (discoverer, extractor, relevance-filter, entity-resolver, metadata-enricher, external-cross-ref, social-enricher, outreach-writer, qa-auditor)
- **5 utility scripts** handle data ops (NCBI rate-limited fetch, bulk sheet upload, priority scoring, name normalization, evidence-store helpers)
- **Pluggable templates** for source modules (PubMed, web search, web scrape, ClinicalTrials.gov), working surfaces (Google Sheets, CSV, local JSON), and outreach channels (LinkedIn note, cold email, Twitter DM)
- **Single project config** (`lead-ops.config.yaml`) defines scope, sources, schema, scoring rules, working surface, outreach channels, audit settings

## Quickstart

- **Using lead-ops in Claude Code** — see below
- **Using lead-ops in Claude Cowork** — see [`docs/USING-IN-CLAUDE-COWORK.md`](docs/USING-IN-CLAUDE-COWORK.md)

### Claude Code

**1. Install from the marketplace.**

```
/plugin marketplace add strange-loop-syndicate/plugins
/plugin install lead-ops
```

**2. Start a new project directory** — Claude will create configs and pipeline output here.

```
mkdir my-leads && cd my-leads
claude
```

**3. Scope the project.** Run `/lead-ops:plan` with a one-line description; Claude asks ICE-style clarifying questions one at a time (domain, geography, time range, success criteria, stance filters, evidence threshold), proposes source modules, schema, scoring rules, working surface, and outreach channels, and writes `lead-ops.config.yaml` + `lead-ops-plan.md`.

```
> /lead-ops:plan oncology KOLs who advocate for expanded access in the US, 2010+
```

Review the generated config before moving on. Edit `lead-ops.config.yaml` directly if you want to tweak sources, schema, scoring, or audit cadence.

**4. Build the database.** Run `/lead-ops:build`. The skill walks through discover → enrich → score → audit → export and stops between major phases so you can review intermediate output. At each judgment step (relevance filter, social enrichment, etc.) it spawns the relevant agent in batches of 20 and pauses for your audit.

```
> /lead-ops:build
```

Use `--from <phase>` to resume at a specific phase, `--source <id>` to scope discovery to one source, `--limit N` for a smoke run, `--continuous` to skip the between-phase reviews.

**5. Plan and draft outreach.** Run `/lead-ops:execute` to pick a channel + priority bucket and produce copy-paste-ready drafts that reference each lead's specific evidence and honor channel rules (LinkedIn 300-char cap, no first-touch product pitch, etc.).

```
> /lead-ops:execute --channel linkedin_connection_note --priority A
```

Drafts land in `exports/outreach/<channel>/<date>-<batch>.md`. Send them yourself (the plugin never auto-sends); then re-run with `--mark-sent` to record state.

**6. Check status anytime.**

```
> /lead-ops:execute --status
```

Prints counts per priority bucket, last build timestamps, send counts per channel.

### Tips

- **Each phase is resumable.** The skill writes `pipeline/state.json` after every phase. Re-running `build` picks up where you left off.
- **Treat audit checkpoints as a feature, not a delay.** They caught hundreds of wrong matches in the original session that produced this plugin.
- **`/deep-research` plays nicely.** When `plan` asks if you need to research the domain first, invoke `/deep-research` directly — return when ready and resume scoping.
- **Evidence is grep-able.** Every URL is also persisted under `pipeline/evidence_store/` so you can re-verify a claim without re-fetching.

## Project layout (created by `/lead-ops:plan`)

```
<your-project>/
├── lead-ops.config.yaml          # single source of truth for this project
├── lead-ops-plan.md              # human-readable strategy doc
├── leads.json                    # the master DB (versioned)
├── pipeline/
│   ├── discovered/               # raw per-source discovery output
│   ├── enriched/                 # fetched + summarized items
│   ├── evidence_store/           # raw scraped content (XML/HTML/MD)
│   └── intermediate/             # working files between phases
└── exports/
    ├── sheet_backup_*.json       # working-surface snapshots
    └── outreach/                 # generated message files per channel
```

## Design principles

- **Verifiable evidence only.** Every claim ties to a fetched, persisted source. No hallucinations.
- **Missing > wrong.** When uncertain, mark as not-found rather than guess.
- **LLM judgment over keyword matching.** Relevance, stance, category are agent calls.
- **Audit checkpoints.** Agents stop every 20 items, present sample, wait for approval.
- **Bulk-safe writes.** RAW value mode, backups before writes, semicolon-free URLs.
- **No ToS-violating automation.** Outreach drafting only; sending is user-mediated.

## Prerequisites

- Python 3.10+ with `requests`, `pyyaml`
- Optional: Google Workspace MCP (for Sheets export), `browser` skill (for social enrichment), `deep-research` plugin (referenced by `/lead-ops:plan` for market-scan steps)

## Status

v0.1.0 — initial release. v2 roadmap: Notion/Airtable working surfaces, Twitter/Bluesky API channels, more source modules.

## License

MIT
