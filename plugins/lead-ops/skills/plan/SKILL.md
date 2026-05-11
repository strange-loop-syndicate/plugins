---
name: plan
description: >
  Walk the user through interactive scoping and pipeline design for a new lead-ops project, then write
  `./lead-ops.config.yaml` and `./lead-ops-plan.md`. Triggers: "set up lead-ops", "plan lead pipeline",
  "scope new lead project", "design lead research", "/lead-ops:plan", "lead-ops scope".
  Do NOT use for ongoing pipeline runs (use /lead-ops:build) or outreach (/lead-ops:execute).
argument-hint: "[optional one-liner project description]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Lead-Ops Plan

Run this skill to produce a complete project configuration for a new lead-ops pipeline. The output is two files in the user's project directory: `./lead-ops.config.yaml` (machine-readable, drives every subsequent skill) and `./lead-ops-plan.md` (human-readable strategy doc that records decisions and rationale). After writing both files, stop and instruct the user to review the config and invoke `/lead-ops:build` when ready. Do not auto-launch the build phase.

## When to invoke

Match these signals: the user says "set up lead-ops", "plan a lead pipeline", "scope a new lead project", "design lead research", or types `/lead-ops:plan`. Also match if the user describes a target audience they want to discover and reach ("I want to find X people who do Y") and lead-ops is the appropriate workflow.

Skip this skill and route elsewhere if `./lead-ops.config.yaml` already exists and the user wants to actually run discovery, enrichment, or scoring (route to `/lead-ops:build`) or draft outreach (route to `/lead-ops:execute`). If config exists and the user wants to extend or replace it, continue here.

## Inputs

The optional argument is a one-liner project description, for example "oncology EA DOL outreach" or "early-stage fintech CTO prospecting". Treat it as a seed for the first clarifying question, not as a finished scope. If no argument is given, start from a blank slate and let the user define the target audience in their first answer.

## Detect existing config

Before asking any scoping questions, read `./lead-ops.config.yaml` if present. If it exists, summarize the current project name, domain, source modules, and working surface in one or two sentences and ask the user whether to extend the existing config or replace it. Wait for the answer. On "extend", treat the existing config as the starting point and only ask about additions or changes. On "replace", archive the existing config to `./lead-ops.config.yaml.bak.<timestamp>` and start from scratch.

## Scoping conversation

Run an ICE-style clarifying conversation: one question at a time, wait for each answer, never batch. The goal is enough scope to make defensible source and schema choices, not exhaustive specification. Cover the following topics in this order, skipping any already answered:

- **Domain and audience** — who are the leads, in plain English. Probe for the role, the field, and the qualifying behavior or evidence ("co-authored a paper on X", "leads a team building Y", "speaks at Z events").
- **Geography** — primary region plus any included or excluded jurisdictions.
- **Time range** — recency cutoff for evidence ("2010+", "last 5 years", "all time"). Defaults to a 10-year horizon if the user has no preference.
- **Success criteria** — what makes the project successful in concrete terms (e.g., "100 A-tier leads with verified contact info" or "wide DB plus a curated shortlist with deep dossiers").
- **Stance filters** — does the project want advocates only, critics included, or stance-agnostic. If stance is relevant, capture the canonical labels (typically `strong_advocate`, `moderate_supporter`, `neutral`, `critic`).
- **Evidence threshold** — minimum corroboration to keep a lead: one source, two independent sources, or stricter.
- **Scale target** — rough lead count expected (50, 500, 5000). This calibrates source breadth, audit sample sizes, and review cadence.

Capture each answer verbatim where possible. Reflect back compact restatements before moving to the next question so the user can correct misunderstandings cheaply.

## Optional market scan

If the user signals unfamiliarity with the domain ("I don't know what good sources look like", "help me find the right journals") or asks for a landscape pass, suggest invoking `/deep-research` to produce a domain-familiarity brief, then pause this skill until the user returns with that output. Do not inline a research pass inside `plan` — keep the skill focused on scoping and design. When the user comes back, read the research output and use it to inform source module and scoring proposals.

## Source module selection

Propose a starting set of source modules from the available templates: `pubmed` (NCBI E-utilities for biomedical literature), `web_search` (broad search via WebSearch tool), `web_scrape` (targeted page extraction via WebFetch and `r.jina.ai/` for CAPTCHA-blocked pages), and `clinicaltrials_gov` (registered trial protocols). For each candidate module, read its config snippet at `${CLAUDE_PLUGIN_ROOT}/templates/sources/<id>/config_snippet.yaml` and use the schema there as the basis for the proposed entry.

Present each candidate as one line: module id, one-sentence rationale tied to the user's domain, and the parameters that need values (seed PMIDs, search queries, target URLs, registry filters). Ask the user to confirm the proposed set, drop modules that do not apply, and add custom modules if relevant. For custom sources, capture id, type, and free-form params; note in the plan doc that the user must implement the source in their project later. Default to no more than four source modules in v1 of a project to keep the discovery phase tractable.

## Schema design

Every lead carries a core set of fields plus project-specific custom fields. The core set is non-negotiable and always present: identity (`name`, `title`, `institution`, `location`), categorization (`category`, `stance`, `tier`, `priority`, `specialty`), context (`domain_relation` — a one-sentence synthesis of why this lead matters), evidence (an array of rich objects with `url`, `type`, `title`, `year`, `summary`, `person_role`), reachability (channel-specific URLs and connection signals), operational flags (`do_not_approach`, `competitor`, `notes`), and outreach hooks (`key_quote`, `recency`).

Propose custom fields that fit the user's domain. For oncology DOL work, that meant `ea_relation` and a domain-specific `category` enum. For B2B SaaS prospecting, custom fields might be `company_stage`, `tech_stack`, `decision_role`. Each custom field needs a name, type (enum, string, number, bool), and a one-line description; enums also need an explicit values list. Show the proposed schema as a YAML preview embedded in the conversation and ask the user to confirm, edit values, or add fields. Keep custom fields under ten in v1; surface schema bloat as a follow-up.

## Scoring rules

Propose A/B/C/D priority expressions plus an X override, adapted to the user's stance filter and evidence threshold. The default rule set is the one from the build spec: A = strongest stance, top tier, multiple pieces of evidence, and at least one reachability or quotability signal; B = strong stance with weaker tier or weaker reachability; C = moderate stance or single-evidence leads; D = weak or unverified evidence; X = do-not-approach or competitor flag overrides everything.

Express the rules as string expressions that the priority scorer at `${CLAUDE_PLUGIN_ROOT}/scripts/priority_score.py` can evaluate. Show the proposed YAML block in the conversation, explain each expression in one sentence of plain English, and let the user adjust thresholds or stance labels. Capture overrides explicitly; never let scoring expressions silently shadow them.

## Working surface

Pick exactly one working surface for v1 from the available templates: `google_sheets`, `csv`, or `local_json`. Read the config snippet at `${CLAUDE_PLUGIN_ROOT}/templates/surfaces/<type>/config_snippet.yaml` to know the required parameters. For Google Sheets, capture spreadsheet id, tab name, and the column ordering the user wants. For CSV, capture the file path and column ordering. For local JSON, capture the file path only.

Warn the user about the surface-specific footguns documented in genesis §4: Google Sheets needs `valueInputOption=RAW` writes and no semicolons after URLs; CSV breaks on embedded newlines in evidence summaries unless properly quoted; local JSON has no concurrent-write protection. Note these caveats in the plan doc so they are not rediscovered the hard way.

## Outreach channels

Propose one to three outreach channels from the available templates: `linkedin_connection_note`, `cold_email`, `twitter_dm`. Read the channel YAML at `${CLAUDE_PLUGIN_ROOT}/templates/channels/<id>.yaml` to know the defaults for max character count, tone, template body, and rules (must include, must not include). Ask the user whether the defaults work or whether they need template overrides. Capture overrides as a `template_overrides` map keyed by channel id. Do not write actual messages here — that is the execute skill's job.

## External data sources

Ask whether the user has any external data to cross-reference: contact databases in CSV, XLSX, or JSON; CRM exports; institutional rosters. For each external source, capture name, file path, match fields (the lead fields to match on, typically last name plus institution or first initial plus last name plus location), and the fields to pull (email, phone, city, specialty). Layered matching is handled by the `external-cross-ref` agent in the build phase; here only capture the spec. Flag if the file does not exist at the named path yet — let the user fix the path or proceed knowing the cross-ref step will be a no-op until the file appears.

## Social enrichment

Ask whether the project wants social-profile enrichment (LinkedIn, Twitter/X, GitHub, etc.). If yes, for each channel capture: `channel` id, `session_cookie_path` (path to a logged-in browser cookie jar the user provides; required because social platforms require auth), `fields` (list of fields to extract per matched profile, e.g. `linkedin_url`, `linkedin_about`, `mutual_connections`), and `min_signals_required` (default 2 — name match alone is insufficient; institution OR field match must also be present). Write these into the top-level `social_channels:` block of the config. If the user does not want social enrichment, leave `social_channels: []`; the build skill skips phase 2f entirely when empty. Warn the user that social enrichment is the highest-risk judgment step in the pipeline (wrong-profile selection is the canonical failure mode), that the agent will stop every `audit.checkpoint_interval` leads for review, and that "missing > wrong" is non-negotiable.

## Audit defaults

Set audit parameters with sensible defaults the user can override: `checkpoint_interval` (default 20 items between mandatory user review), `require_user_approval` (default `true` between major phases), `qa_sample_pct` (default 0.05 for the qa-auditor spot-check rate). Tell the user that the checkpoint interval is the single most important guardrail against bad judgment work compounding across the dataset; recommend keeping it at 20 unless the project is small (under 100 leads, where 10 is fine) or very large (over 1000 leads, where 30 is acceptable).

## Write outputs

Write `./lead-ops.config.yaml` with all sections captured during the conversation: `project`, `scope`, `sources`, `schema`, `relevance`, `scoring`, `working_surface`, `external_data`, `outreach`, and `audit`. Use the skeleton at `${CLAUDE_PLUGIN_ROOT}/templates/configs/lead-ops.config.skeleton.yaml` as the structural reference and the example at `${CLAUDE_PLUGIN_ROOT}/templates/configs/lead-ops.config.example.yaml` for field-level patterns. Validate that the resulting YAML loads cleanly before declaring the file written.

Write `./lead-ops-plan.md` as a human-readable companion: one section per decision area, capturing what the user picked and why, with explicit notes on tradeoffs the user accepted (e.g., "skipping LinkedIn enrichment in v1 to ship faster"). Include a short "next steps" block at the end pointing the user at `/lead-ops:build`.

## Stop and instruct

After both files are written, report the absolute paths to both files and stop. Tell the user to review the config, edit anything that looks wrong, and invoke `/lead-ops:build` when they are ready to start discovery. Do not invoke build automatically. Do not begin discovery in this session. The handoff from plan to build is intentional and gives the user a clear review point before any external traffic is generated.
