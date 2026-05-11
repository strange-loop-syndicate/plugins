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

```
/lead-ops:plan        # interactive scoping → lead-ops.config.yaml
/lead-ops:build       # run pipeline (stops between major phases for review)
/lead-ops:execute     # draft outreach messages for prioritized leads
```

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
