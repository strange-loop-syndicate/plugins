# Lead-Ops Plugin — Session Genesis Document

This document captures the complete context and learnings from the T-0130 Right2Hope DOL discovery session that motivated the creation of the `lead-ops` plugin. It is the authoritative reference for plugin design decisions and should be preserved verbatim.

**Created:** 2026-04-11
**Original project:** T-0130 — Right2Hope (Cromospharma) — find Doctor/Opinion Leader candidates for Expanded Access / Compassionate Use outreach in oncology
**Final scale:** 818 leads with rich evidence objects, multi-source data, LinkedIn enrichment, prioritization, and outreach-ready notes

---

## 1. The Original Problem

Right2Hope (R2H) is a platform helping cancer patients access experimental treatments via FDA Expanded Access (EA) / Compassionate Use (CU) / Managed Access Programs (MAP) pathways. To reach the right oncology professionals, R2H needs a comprehensive, verified database of every doctor, bioethicist, FDA official, pharma EA program manager, patient advocate, and clinical researcher who has publicly engaged with EA/CU.

**Original input:** 88-person shortlist of LinkedIn search URLs that the user had partially curated, plus a 33K-row oncologist contact database in xlsx format.

**Original output goal:** A prioritized, evidence-backed lead database where every person has:
- Verifiable URL-based evidence (no hallucinations)
- Stance classification (advocate / critic / neutral)
- Tier and accessibility rating
- Contact information
- LinkedIn connection degree and mutual connections
- A specific reason to reach out

**Final outcome:** 818 leads in a Google Sheet, sorted by priority (A=74, B=163, C=566, D=3, X=12), backed by a JSON evidence store with 1387 rich evidence records and a persistent `evidence_store/` filesystem mirror of every fetched page.

---

## 2. The Pipeline We Built (must be generalizable)

This is the abstraction the plugin must enable. The DOL domain was the use case; the pipeline pattern is what matters.

### Phase 0: Scoping & Brainstorming

Before any data is collected, the user and assistant negotiate scope through clarifying questions. Real examples from this session:

- **Geography:** US only? Global? → "US primary, include affiliations elsewhere"
- **Time horizon:** Recent only? All time? → "2010+" (post-modern-EA-era)
- **Stance filter:** Only advocates? Include critics? → "Include critics, flag them as X-priority"
- **Sources:** What counts as evidence? → "PubMed primary, also conference programs, news articles, company pages"
- **Outreach goal:** Just contact list? Or full dossiers? → "Wide DB + curated shortlist with deep dossiers for top tier"

The plugin needs a `brainstorm` or `scope` skill that asks ICE-style (Impact/Confidence/Ease) clarifying questions one at a time, never batching, and converges on a scope document.

### Phase 1: Discovery (multi-source)

For DOL/EA the channels were:
- **PubMed similar articles** via NCBI E-utilities `elink` API (37 seeds → 4300 candidates → 222 filtered)
- **ClinicalTrials.gov** EA protocols (`studyType=exp` filter)
- **Conference speaker pages** (Operationalise EAP Summit, EAP World Congress, Operationalize EAP)
- **Pharma EA/MAP company pages** (Novartis, Pfizer, Roche, etc.)
- **News/policy article search** (STAT, Health Affairs, AJMC, ASCO Post, Pink Sheet)

The plugin must support ARBITRARY source plugins per use case. A real-estate lead pipeline would discover from MLS, Zillow, Reddit r/realestate, local FB groups, agent associations. A B2B SaaS pipeline would discover from product reviews, GitHub stars, conference attendee lists, podcasts. The plugin design must allow USER-DEFINED source modules.

**Pattern:** Each source has a `discover(seeds | query) → list[candidate]` function. Candidates are deduplicated globally. Title/text relevance filters can be applied per source.

### Phase 2: Fetch & Extract (content-aware)

For each discovered item:
1. Fetch full content (with API where possible, WebFetch for HTML, `r.jina.ai/` prefix for CAPTCHA-blocked pages)
2. Persist raw content to `evidence_store/{type}/{id}.{ext}` for re-verification
3. Extract structured metadata (authors, dates, institutions)
4. Generate a **content-derived summary** (1-3 sentences) capturing the substance — NOT a paraphrase of title

For DOL/EA the metadata was: PMID, title, authors with affiliations, journal, year, DOI, abstract. Summary captured what the article *argued* about EA/CU.

For other domains the metadata fields differ but the pattern is identical: structured fields + free-form summary. The plugin should let users define a metadata schema per source type.

**Critical lesson:** Summaries must be derived from the actual content, not the title. Previous-session agents wrote summaries from titles, producing useless results. We solved this by:
- Saving raw content to disk (`evidence_store/`)
- Having the summarizer agent re-read content from disk before writing
- Including a self-verification step: re-read 5 random items, compare summary against source, fix mismatches

### Phase 3: Relevance Filtering

Discovery is broad. Most discovered items will be irrelevant. We had 854 new leads from PubMed co-author chains; 210 were not actually oncology-EA-related (they came from COVID convalescent plasma EAPs, ALS EAPs, SMA nusinersen EAPs, etc.).

**Solution:** A dedicated `relevance-filter` agent that reads each lead's evidence and decides KEEP or REMOVE based on user-defined criteria. Output goes to a `keep/remove/reasons` JSON. Then a script applies the filter to the master DB.

The plugin must let users define relevance criteria in plain English. Example from this session:

> KEEP if cancer/oncology evidence, OR general EA/CU policy work (applies to oncology too)
> REMOVE if all evidence is non-cancer disease-specific (COVID plasma, SMA, MS, etc.)
> REMOVE if co-authored a generic PhRMA survey with no EA involvement

### Phase 4: Entity Resolution & Merge

PubMed gives co-author lists. Some co-authors are already in the DB; others are new. We need to match:

**Layered matching (in order):**
1. PMID overlap (new person co-authored a paper already linked to existing lead)
2. Full name + institution exact match
3. Surname + first initial + institution (handles "Arthur L." vs "Arthur")
4. Surname + specialty + location (catches institution changes — e.g. Subbiah moved Sarah Cannon → Stanford)
5. Fuzzy fallback → flag for manual review

Name normalization strips academic suffixes (MD, PhD, JD, MPH, MBA, MBE, PharmD, DO, FACNM, FASCO, BCPS, BCCCP, CIP, RN, BSN, RPh, Esq, DNP, PharmB, FNP), middle initials, and lowercases.

After matching, evidence is merged (deduplicated by URL/PMID). New people get fresh lead records.

### Phase 5: Metadata Enrichment

The discovery phase gives basic fields (name, institution from affiliation, evidence). To make leads actionable, we need:
- **Specialty** (e.g., "Medical Oncology", "Bioethics / Medical Ethics", "Patient Access / EA Operations")
- **Stance** (strong_advocate / moderate_supporter / neutral_academic / critic)
- **Category** (practicing_oncologist / bioethics_policy / fda_government / biopharma_ea_leader / patient_advocacy / clinical_trial_pi / irb_infrastructure / pharmacist_coordinator / ea_service_company)
- **Tier** (1 = first/last author 2+ papers OR program director OR FDA official; 2 = co-author + speaker; 3 = single weak evidence)
- **ea_relation** (one-sentence synthesis: "Co-author of 2022 JAMA study on oncologist EA experiences; interviewed 25 physicians at 4 academic centers")
- **Recency** (most recent year from evidence)

These are LLM-judgment fields, filled by a dedicated `metadata-enricher` agent that reads each lead's evidence and writes them. **Do not use keyword matching** — agents make better calls.

### Phase 6: Cross-Reference Enrichment

If the user has external data sources (the 33K oncologist DB in our case), cross-reference by name. Layered matching as above. Pull email, phone, location, specialty.

The plugin should support arbitrary CSV/XLSX/JSON external data sources defined in user config.

### Phase 7: LinkedIn (or other social) Enrichment

Logged-in browser session, scrape per-lead. For DOL/EA we used Chrome + CDP via the `browser` skill, with the user's session cookies. Per lead:

1. Search LinkedIn for "Name + Institution" (strip suffixes, middle initials)
2. **Evaluate top 3-5 search results** — name match alone is insufficient
3. Score using MULTIPLE signals:
   - Name match (required)
   - Institution/company match (strong)
   - Field relevance (medical/pharma/bioethics for our domain)
   - Mutual connections > 0
4. Navigate to the selected profile, scroll, extract:
   - Headline, location, About text
   - Followers count, connections count
   - Connection degree (1st/2nd/3rd+)
   - Mutual connections (names + count)
   - Current position

**The hard lesson:** Earlier agents grabbed wrong profiles because they matched on name alone. Examples of failures:
- "Arthur Caplan music producer at NYU Clive Davis" instead of the bioethicist at NYU Grossman
- "Barbara Redman Chief Development at Metro Atlanta Chamber" instead of the bioethics professor
- "Andrzej Górski Converting Market Consultant" instead of the immunology professor

**Fix:** Mandatory checkpoint protocol — agent stops every 10-20 leads, presents what it found, waits for user audit. Bad matches get flipped to `not_found` rather than kept.

**Rule:** A missing profile is 100x better than a wrong profile.

### Phase 8: Prioritization

Score each lead with a transparent formula. Ours:

- **A** = strong_advocate + tier 1 + evidence_count ≥ 2 + (reachable [1st/2nd] OR quotable [has key_quote])
- **B** = strong_advocate + tier 2 + evidence ≥ 1, OR moderate_supporter + tier 1 + reachable
- **C** = moderate_supporter + evidence ≥ 1, OR tier 3 with verified evidence
- **D** = weak/unverified evidence
- **X** = do_not_approach OR competitor (override regardless of strength)

Priority must be re-scored after every enrichment phase. Tier 1 → 2 changes from new evidence. Reachability changes from LinkedIn data. Stance can change from new evidence.

### Phase 9: Output to Working Surface

The working surface is where the user actually USES the data. For us: Google Sheets.

**Key requirements for sheet output:**
- Column structure user-configurable
- Evidence URLs in single cell, newline-separated, NO semicolons (semicolons break Google Sheets auto-linking)
- Use `value_input_option=RAW` for all writes (prevents "+27" from being parsed as a formula)
- Truncate long fields (evidence summaries can be 5000+ chars; truncate to 400-500)
- Always create a backup tab/file BEFORE writing
- Targeted updates (only changed cells), not full rewrites
- Append new rows at end, don't reorder existing
- Bulk via OAuth REST API for >50 rows (MCP tool calls are too expensive per-call)

The plugin should abstract the working surface — Google Sheets is one option, Notion DB is another, Airtable, plain CSV, Linear, etc.

### Phase 10: Outreach Campaign

Once leads are prioritized, write personalized outreach. For DOL/EA we generated LinkedIn connection notes.

**Pattern that worked:**
- ~280 characters (LinkedIn Premium limit is 300)
- Reference SPECIFIC evidence from the lead's work
- State purpose in general terms (don't pitch a product in first message)
- Don't name the company in the note (it's visible from the sender's profile)
- Mix of warm, humble, professional tone

Example:
> Dr. Tsimberidou — your MD Anderson Compassionate Use Committee work and investigational cancer therapeutics experience stand out. I'm working on improving EA navigation for cancer patients and would love to learn from your approach. Would love to connect. — Vlad

The plugin should support arbitrary outreach channels: LinkedIn DM, email, Twitter, Slack, etc. — each with its own length limit and tone.

### Phase 11: Execution

Sending the messages. We did not automate this step (would require LinkedIn ToS-violating bots). The plugin should support:
- Manual mode: produce a markdown file the user can copy-paste from
- Semi-automated: queue messages, user reviews and clicks send
- API mode (where ethical/allowed): use a provider API (e.g., Gmail send, Twitter DM API)

---

## 3. Agent Orchestration — Lessons Learned

This session ran into many orchestration problems. The plugin's agent layer must encode these lessons:

### Decision: Team vs Single Agent

- **TeamCreate (multi-agent, addressable)** for any work needing iteration, audits, or coordination. Default.
- **Single fire-and-forget Agent** only for genuinely trivial tasks (<5 tool calls, zero ambiguity).
- **Never** spawn parallel background subagents writing to the same file.

### Audit Checkpoint Protocol (CRITICAL)

When an agent does judgment work (LinkedIn profile selection, relevance filtering, summary writing), it MUST:
1. Process N items (10 or 20)
2. Save progress to disk
3. Report findings in a structured table to the orchestrator (user)
4. **STOP and WAIT for approval**
5. Apply any corrections the orchestrator makes
6. Continue with next batch

We caught hundreds of wrong matches this way. Without this protocol, agents drift into wrong patterns and the user discovers the problem only after hundreds of bad records.

### Verification Requirements

Every agent must self-verify before reporting completion:
- Spot-check 5 random outputs against source data
- Report verification results in completion message
- Flag uncertain cases as "not_found" rather than guessing

### Agent Idle Loop Failure Mode

Background agents sometimes go idle and stop processing messages. Symptoms:
- `idleReason: "available"` repeating with no work done
- Agent not responding to `shutdown_request`
- Agent not responding to wake-up `SendMessage`

Workaround: user manually interrupts the agent (one of the few user actions that breaks the loop). Plugin should warn about this and provide guidance for force-cleanup.

### Rate-Limited Shared Resources

When multiple agents need to hit the same rate-limited API (NCBI E-utilities, OpenAI, etc.), use a file-based lock:

```python
LOCK_FILE = "/tmp/ncbi_rate.lock"
TS_FILE = "/tmp/ncbi_rate_ts"
MIN_INTERVAL = 0.35  # 3 req/sec

def _wait_for_slot():
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # check last timestamp, sleep if needed, write new timestamp
```

All agents call a shared wrapper script instead of curl directly.

### Bulk Write Pattern (Google Sheets)

MCP tool calls inline JSON. For large batches (>50 rows), token cost is prohibitive. Solution: spawn an agent that uses OAuth credentials directly to call the underlying REST API. Credentials at `~/.google_workspace_mcp/credentials/{email}.json`.

---

## 4. Failure Modes Encountered (the plugin must prevent these)

### Hallucinated Data
- Agent-generated PMIDs that didn't exist or pointed to wrong papers
- Wrong-author attributions
- **Fix:** Verify via authoritative API (NCBI esummary/efetch) before using; never trust agent-generated identifiers

### Wrong Profile Selection
- Name match alone selected unrelated people
- **Fix:** Multi-signal matching with mandatory institutional/field check; checkpoint protocol; "missing > wrong"

### Sheet Schema Drift
- Column order between versions changed (Name vs Priority swapped position)
- Semicolons after URLs broke auto-linking
- "+27 mutual" parsed as a formula
- **Fix:** RAW value mode, explicit column mapping in config, no separators that conflict with sheet syntax

### Broken/Outdated Evidence URLs
- PMIDs that 404
- DOIs paywalled
- Conference URLs pointing to list page instead of individual speaker page
- **Fix:** Verify every URL by fetching; remove broken ones; persist raw content so re-verification is possible without re-fetching

### Duplicate Lead Records
- "Richard Bedlack" and "Richard S Bedlack" as separate entries
- "David J Greenblatt" and "David J. Greenblatt" (punctuation difference)
- **Fix:** Aggressive name normalization; periodic duplicate scan; merge UI in working surface

### Evidence Summary == EA Relation (redundancy)
- Both fields containing essentially the same paraphrase
- **Fix:** Evidence summary derived from article content; EA Relation synthesizes person's role across all evidence

### Non-Oncology Co-Authors Polluting the DB
- PubMed similar articles to EA papers can be about COVID, SMA, MS, etc. EAPs — co-authors of those are NOT oncology DOLs
- **Fix:** LLM-judgment relevance filter, not keyword-based

### Vague Targets
- "Calabria med onc" (a region with thousands of medical oncologists)
- First-initial-only names ("A Chou", "P M Anderson")
- **Fix:** Target schema validation — require enough disambiguating info before searching; otherwise mark unsearchable

---

## 5. Data Model

The lead record schema that emerged:

```json
{
  "name": "Alison Bateman-House, PhD, MPH",
  "title": "Associate Professor, Medical Ethics",
  "institution": "NYU Grossman School of Medicine",
  "location": "New York, NY",
  "specialty": "Bioethics",
  "stance": "strong_advocate",
  "tier": 1,
  "category": "bioethics_policy",
  "key_quote": "I don't think Right to Try will ever be a mainstream path.",
  "recency": "2024+",
  "linkedin_url": "https://www.linkedin.com/in/alison-bateman-house/",
  "linkedin_connection": "2nd",
  "mutual_connections": "Brandon Kashfian, Spencer Guthrie +22",
  "linkedin_about": "Academic with a demonstrated history of...",
  "linkedin_followers": "1,790",
  "linkedin_connections": "500+",
  "db_email": null,
  "db_phone": null,
  "do_not_approach": false,
  "competitor": false,
  "notes": "Co-leads NYU CUPA. Central node connecting academia, FDA, pharma on EA policy.",
  "priority": "A",
  "ea_relation": "Co-chair of NYU CUPA and CompAC (J&J); co-author of multiple EA policy studies; Reagan-Udall Innovation Award 2019",
  "evidence": [
    {
      "url": "https://pubmed.ncbi.nlm.nih.gov/29714573/",
      "type": "pubmed",
      "pmid": "29714573",
      "title": "A Pilot Experiment in Responding to Individual Patient Requests for Compassionate Use",
      "authors": ["Arthur L Caplan", "Alison Bateman-House", ...],
      "journal": "Ther Innov Regul Sci",
      "year": 2019,
      "summary": "Describes the CompAC pilot: 180 CU requests for daratumumab reviewed by independent ethics committee at NYU. 163 approved. Argues third-party model reduces bias in CU decisions.",
      "summary_source": "abstract",
      "person_role": "co-author"
    }
  ]
}
```

**Generalization:** The DOMAIN-SPECIFIC fields are `ea_relation` (which the plugin should call something like `topic_relation` or `domain_relation`) and the category enum. Everything else generalizes.

The plugin's lead schema should be configurable per project, with these core fields always present:
- Identity: name, title, institution, location
- Categorization: category, stance, tier, priority, specialty
- Context: domain_relation (one-sentence summary of why this lead matters)
- Evidence: array of rich objects with url, type, title, year, summary, person_role
- Reachability: contact channels (linkedin_url, email, phone, etc.) and connection signals
- Operational: do_not_approach, competitor flags, notes
- Outreach: key_quote, recency

Domain-specific extension fields (`evidence[].pmid`, `evidence[].journal`, etc.) live alongside but are project-scoped.

---

## 6. The Working Files We Built

These are reusable artifacts that the plugin should productize:

### `ncbi_fetch.py` (~150 lines)
Shared NCBI E-utilities wrapper. File-based rate limiter. Three functions: `elink_similar(pmid)`, `esummary_batch(pmids)`, `efetch_article(pmid)`. Persists raw XML to evidence store. Used by all agents. Reusable for any NCBI-using project.

**Plugin generalization:** The plugin should ship a library of `source-fetch` modules for common APIs: NCBI, OpenAlex, CrossRef, ClinicalTrials.gov, OpenCorporates, NPI Registry, etc.

### `phase1_discover.py` (~120 lines)
Seed-based discovery: take known PMIDs, follow elink chain, filter by title keywords, output ranked candidates.

**Plugin generalization:** A `discover` skill that takes (seeds, filter_criteria) and runs a configurable similarity chain. Different sources have different "similarity" semantics (PubMed similar articles, citation chains, author co-occurrence, conference co-attendance, etc.).

### `phase2_fetch_pubmed.py` (~80 lines)
For each discovered PMID, fetch full metadata via efetch. Resume support. Progress saving.

### `phase3_merge.py` (~280 lines)
Person matching, evidence merge, new lead creation, deduplication, priority re-scoring, sort.

### Browser-based LinkedIn scraper (no single file — was orchestrated by an agent)
Logged-in session via cookie injection. Search → evaluate top 3-5 results → navigate → scroll → extract. Human-like random pauses (5-15s between actions, 10-25s between leads). Checkpoint protocol every 10-20 leads.

### `phase3_merge.py` priority scorer
Lines ~155-180 in phase3_merge.py. The exact formula:

```python
def score_priority(lead):
    ev_count = len(lead.get("evidence", []))
    stance = lead.get("stance", "")
    tier = lead.get("tier", 3)
    reachable = lead.get("linkedin_connection") in ["1st", "2nd"]
    quotable = bool(lead.get("key_quote", "").strip())
    if lead.get("do_not_approach") or lead.get("competitor"): return "X"
    if stance == "strong_advocate" and tier <= 1 and ev_count >= 2 and (reachable or quotable): return "A"
    if stance == "strong_advocate" and tier <= 2 and ev_count >= 1:
        return "A" if tier == 1 else "B"
    if stance == "moderate_supporter" and tier <= 1 and reachable: return "B"
    if stance == "strong_advocate" and ev_count >= 1: return "B"
    if stance == "moderate_supporter" and ev_count >= 1: return "C"
    if tier <= 3 and ev_count >= 1: return "C"
    return "D"
```

The plugin should expose this as a user-configurable rule set, not hardcoded.

---

## 7. The Agents We Spawned (and what they did)

Reverse-engineering the agents we used into reusable plugin agents:

### `query-strategist` (deep-research)
Decomposed the EA/DOL research question. Generated multi-wave search queries. Triggered at start of research and between retrieval waves.

### `retrieval-agent` (deep-research, spawned 10-20 in parallel)
Each took one sub-question, executed multiple web searches, added sources to evidence store, extracted key passages.

### `source-evaluator` (deep-research)
Rated batches of sources using NATO Admiralty Code (A-F reliability × 1-6 credibility).

### `evidence-analyst` (deep-research)
Extracted factual claims, built ACH matrix, triangulated across sources.

### `critique-agent` (deep-research)
Devil's advocacy, key assumptions check, bias audit.

### `research-agent` (deep-research)
Autonomous full-pipeline researcher when delegation needed.

### `verifier-N` (this session, custom)
URL verification at scale. Three of them ran in parallel, each took a batch of 44 URLs, fetched each, verified author/topic match against claimed evidence.

### `metadata-enricher` (this session, custom)
For every lead with empty stance/category/ea_relation, read evidence and inferred values. 100% coverage in one pass.

### `specialty-filler` (this session, custom)
Same pattern but for specialty field. Used LinkedIn headlines + about + evidence summaries.

### `relevance-filter` (this session, custom)
Read each new lead, classified KEEP/REMOVE, output JSON with reasons.

### `linkedin-scraper-vN` (this session, multiple iterations)
We needed 4 iterations to get matching logic right. Final version (v4) used multi-signal evaluation (name + institution + field + mutual connections), per-batch checkpoint protocol with user audit, "missing > wrong" rule.

### `sheet-uploader` (this session, custom)
Bulk upload to Google Sheets via OAuth REST API (faster than MCP for large batches).

**Plugin generalization:** These map to a set of reusable plugin agents:

- `lead-scoper`: clarifying questions + scope definition
- `source-planner`: choose discovery sources and queries
- `discoverer`: run discovery against configured sources
- `extractor`: fetch + summarize each candidate
- `relevance-filter`: keep/remove judgment
- `entity-resolver`: matching + merging
- `metadata-enricher`: fill judgment fields
- `external-cross-ref`: match against user-provided data sources
- `social-enricher`: LinkedIn / Twitter / GitHub profile lookup with audit checkpoints
- `prioritizer`: apply scoring rules
- `outreach-writer`: generate channel-appropriate messages
- `working-surface-writer`: push to sheets/Notion/Airtable/CSV
- `qa-auditor`: spot-check verifier

---

## 8. The Skills the Plugin Should Have

(User-invocable slash commands; details to be designed in subsequent plugin-dev phases.)

- `/lead-ops:scope` — interactive scoping conversation
- `/lead-ops:plan-discovery` — design discovery pipeline for the scope
- `/lead-ops:run-discovery` — execute discovery
- `/lead-ops:enrich` — run enrichment pipeline (metadata, cross-ref, social)
- `/lead-ops:audit` — spot-check current DB for hallucinations, broken URLs, duplicates
- `/lead-ops:prioritize` — re-score using configured rules
- `/lead-ops:plan-outreach` — design outreach strategy
- `/lead-ops:draft-messages` — generate per-lead messages
- `/lead-ops:export` — push to working surface (Sheets, Notion, etc.)
- `/lead-ops:status` — show pipeline state and stats

---

## 9. Config & Project Layout

The plugin should encourage a per-project layout like:

```
project-name/
├── lead-ops.config.yaml      # scope, sources, schema, scoring rules
├── leads.json                # the master DB
├── pipeline/
│   ├── discovered/           # raw discovery output per source
│   ├── enriched/             # fetched + summarized items
│   ├── evidence_store/       # raw scraped content (XML, HTML, MD)
│   └── intermediate/         # working files between phases
└── exports/
    ├── sheet_backup_*.json   # snapshots of working surface
    └── outreach/             # generated message files
```

The `lead-ops.config.yaml` defines (rough sketch):

```yaml
scope:
  domain: "oncology EA/CU professionals"
  geography: ["US primary", "global supplemental"]
  time_range: "2010+"
  
sources:
  - id: pubmed
    type: pubmed_similar_articles
    seeds: ["<file>:./seeds/pmids.txt"]
    title_filter_keywords: ["expanded access", "compassionate use", ...]
    date_min: 2010
  - id: conferences
    type: web_scrape
    pages:
      - url: https://operationalize-eap.com/
        speaker_link_pattern: "/speaker/{slug}/"
  - id: news
    type: web_search
    queries: ["expanded access oncology site:statnews.com 2020..2026", ...]

schema:
  custom_fields:
    - name: ea_relation
      type: string
      description: "One sentence on the person's connection to EA/CU"
    - name: category
      type: enum
      values: [practicing_oncologist, bioethics_policy, fda_government, ...]
    - name: stance
      type: enum
      values: [strong_advocate, moderate_supporter, neutral_academic, critic]

scoring:
  priorities:
    A: "stance == 'strong_advocate' AND tier <= 1 AND evidence_count >= 2 AND (linkedin_connection in ['1st','2nd'] OR key_quote)"
    B: "stance == 'strong_advocate' AND tier <= 2 AND evidence_count >= 1"
    # ...
  
working_surface:
  type: google_sheet
  spreadsheet_id: "1JtDLKby7..."
  tab: "Database"
  columns: [...]
  
external_data:
  - name: oncologist_db
    file: "~/data/oncologists.xlsx"
    match_on: [last_name, first_initial, institution]
    fields_to_pull: [email, phone, city, state, specialty]
```

---

## 10. Outreach Note Patterns (for the outreach-writer agent)

Real examples we generated, with character counts:

| Channel | Limit | Pattern |
|---------|-------|---------|
| LinkedIn connection note (Premium) | 300 chars | Address + specific evidence reference + intent (general) + ask |
| LinkedIn DM (after connection) | longer | Can add light pitch + scheduling |
| Cold email | 500-800 chars body | Specific evidence + intent + call-to-action + sender footer |
| Twitter DM | 1000 chars | Lighter, refer to a recent tweet/paper |

**Template for connection notes:**

```
Hi [Name] — [specific evidence reference, 1 sentence]. I'm working on [general purpose statement, no product name]. Would love to connect and learn from your [field-specific noun]. — [Sender first name]
```

**Rules:**
- Don't pitch product in first touch
- Don't name the sender's company (visible from profile)
- Reference SPECIFIC piece of work (paper title, speech, role)
- Match tone to the recipient (academic = "Dr." + formal, advocacy = warmer)
- Always under platform character limit
- Always include sender first name to humanize

---

## 11. Things This Plugin Should NOT Try To Do

To keep scope manageable:

- **Don't automate message sending** through ToS-violating channels (LinkedIn scraping/messaging bots). Generate drafts, hand off to user.
- **Don't try to be a CRM.** The working surface (Sheets/Notion/Airtable) is the CRM. Plugin produces records and updates; doesn't track interactions, replies, status.
- **Don't generate fictional evidence.** Every claim must come from a fetched, persistent source.
- **Don't enrich without consent.** Cross-referencing personal databases (emails/phones) is fine if user provides them; plugin shouldn't scrape unauthorized data.
- **Don't bypass rate limits.** Honor robots.txt, API ToS, platform usage policies.

---

## 12. Memory of Specific Real People (anonymize before publishing)

Some leads identified in this session (kept here as test cases for plugin validation; sanitize before publishing the plugin publicly):

**A-tier 1st-degree connection:** Bob Stevens, MPS Society CEO, UK
**B-tier 1st-degree:** Debra Ainge (Clinigen), Josh Bilenker (Treeline Bio, ex-Loxo CEO), Paolo Ascierto (Istituto Nazionale Tumori Napoli)
**Top mutual-connection leads:** Arthur Caplan (NYU, 315 mutuals), Adam Jones (Amicus, 167), Sean Khozin (143)

Removed during relevance filtering: ~210 non-oncology co-authors (COVID convalescent plasma EAP authors, ALS EA participants, SMA nusinersen co-authors, MS ocrelizumab CU participants, etc.)

Worst mismatches caught during LinkedIn audit:
- "Arthur Caplan, Music Producer at NYU Clive Davis" (target: bioethicist at NYU Grossman)
- "Barbara K Redman, Chief Development Officer at Metro Atlanta Chamber" (target: bioethics professor)
- "Andrzej Górski, Converting Market Consultant" (target: immunology professor in Warsaw)
- "Annalisa Capuano" → grabbed "Rasha Tawfik" (completely different person)
- "Gil Cunha de Santis, writer and producer" (target: hematologist at USP São Paulo)

These should be in the plugin's test suite as known traps.

---

## 13. The Pipeline as a State Machine

For documentation purposes, here's the full pipeline as states:

```
[SCOPE]
  ↓ user clarifying conversation
[PLAN]
  ↓ design sources, schema, scoring rules
[DISCOVER]
  ↓ run all configured sources, collect candidates
[FETCH]
  ↓ for each candidate, fetch full content + save raw
[EXTRACT]
  ↓ generate structured metadata + content-derived summaries
[FILTER]
  ↓ relevance judgment, remove out-of-scope
[RESOLVE]
  ↓ entity match new vs existing, merge evidence
[ENRICH-META]
  ↓ LLM judgment for stance/category/tier/etc
[ENRICH-CROSSREF]
  ↓ pull from user-provided external DBs
[ENRICH-SOCIAL]
  ↓ LinkedIn/Twitter/etc lookup with audit checkpoints
[SCORE]
  ↓ apply prioritization rules
[EXPORT]
  ↓ push to working surface with backup
[OUTREACH-PLAN]
  ↓ design strategy: channels, sequencing, segments
[OUTREACH-DRAFT]
  ↓ generate per-lead messages
[OUTREACH-SEND]
  ↓ user-mediated (manual/semi-auto/automated)
[MONITOR]
  ↓ track replies / status in working surface
[ITERATE]
  ↓ refine sources, scoring, messages based on results
```

The plugin's main `/lead-ops:run` should be able to enter at any state and progress forward, with appropriate resume support.

---

## 14. Critical Quotes from the User (these guided the design)

- "I'd suggest to do same for clinicaltrials.gov" — implied: every source is pluggable
- "Use teammate but instruct better and validate results... also I want you to spin up additional teammate to re-check and verify others agents findings, find gaps and flaws as I just did. I think it's necessary step as agents are really sloppy" — implied: orchestration with verification is mandatory
- "Final database MUST contain evidence of EA relation + URL (mandatory!!! I want results to be VERIFIABLE before we could use them). Evidence without URL = no evidence." — implied: nothing in DB without a fetched, verifiable source
- "DISMISS AGENTS!!! They still doing something!" — implied: must support cleanup of stuck agents
- "Pls don't include code snippets [in the plan], instead describe what to do and why" — implied: plans should be conceptual not implementation-specific
- "we should evaluate few search results instead of simply going with first" — implied: judgment > pattern matching at every step
- "I'd suggest to do intermediate checks every 20 profiles" — codified: checkpoint protocol
- "It should ask you approval to continue" — codified: stop-and-wait at checkpoints
- "I want you to do a systematic gaps verification iteration (including co-authors extraction)" — codified: co-author chasing as discovery method
- "we decided not to mention product in first communication + should not mention Cromos" — implied: outreach is generic in first touch

---

## 15. What "Generalize" Means For This Plugin

The session was about ONE use case (oncology EA DOLs). The plugin must generalize to:

**Use cases (sample):**
- B2B SaaS leads (CTOs at Series-A startups, decision-makers in fintech, etc.)
- Real estate (homeowners in specific ZIP codes who might sell, agents in growth markets)
- Investment (LPs interested in climate tech, founders in specific verticals)
- Journalism (sources on a beat, expert commentators, eyewitnesses)
- Academia (collaboration prospects, citation network influencers, conference invitees)
- Hiring (passive candidates with specific skills, in specific locations)
- Sales (decision-makers at companies matching ICP)
- Political (voters in swing districts, donors above threshold, volunteers)
- Cause-based (advocates on specific issues, journalists covering the issue, legislators)

**Source modules (sample):**
- PubMed/OpenAlex (academic)
- LinkedIn search (social)
- Twitter/Bluesky (social)
- ClinicalTrials.gov (clinical research)
- SEC filings / Edgar (financial)
- GitHub (developers)
- ArXiv (preprints)
- Conference programs (events)
- Company websites (employees, leadership)
- News search (mentions in articles)
- Reddit/HN/Discord (communities)
- Public records (real estate, business filings)
- NPI Registry (healthcare providers)
- USPTO (patent inventors)
- Crunchbase / Pitchbook (investors)

**Communication channels (sample):**
- LinkedIn (connection request, DM, InMail)
- Email (cold, warm intro, follow-up)
- Twitter / Bluesky (DM, public reply)
- SMS
- Mail (physical)
- In-person at events

The plugin's architecture must accommodate ALL of these via plugin-of-plugin source modules. Initial release can ship with 2-3 source modules and let users add more.

---

## 16. Suggested Plugin v1 Scope

Don't try to ship everything. v1:

**Core skills:**
- `/lead-ops:scope` (interactive scoping)
- `/lead-ops:plan` (design pipeline)
- `/lead-ops:run` (execute pipeline)
- `/lead-ops:audit` (QA pass)
- `/lead-ops:outreach` (draft messages)

**Core agents:**
- `lead-scoper`, `source-planner`, `discoverer` (one generic + one PubMed reference impl), `extractor`, `relevance-filter`, `entity-resolver`, `metadata-enricher`, `prioritizer`, `outreach-writer`

**Reference source modules (ship as templates):**
- PubMed (NCBI E-utilities)
- Web search (via WebSearch tool)
- Web scrape (via WebFetch + jina.ai prefix)

**Reference working surface adapters (ship as templates):**
- Google Sheets (via google-workspace MCP)
- Local JSON (no external dependency)
- CSV file

**Reference outreach channels (ship as templates):**
- LinkedIn connection note generator (string output, user pastes)
- Cold email draft generator
- CSV of messages for bulk-paste

v2 can add: Notion, Airtable, Twitter/Bluesky API, more source modules.

---

## 17. Files in This Session That Inspired The Plugin

For traceability:

- `/Users/claude/data/tasks/now/T-0130-r2h-find-dol-candidates.md` — task tracker with session log
- `/Users/claude/data/tasks/outputs/T-0130-linkedin-dol-list/master_leads_db.json` — final 818-lead DB
- `/Users/claude/data/tasks/outputs/T-0130-linkedin-dol-list/v3_pipeline/` — all pipeline scripts and intermediate files
- `/Users/claude/data/tasks/outputs/T-0130-linkedin-dol-list/2026-04-09-evidence-enrichment-v3-design.md` — design spec for v3 pipeline (good model for plugin spec format)
- `/Users/claude/data/tasks/outputs/T-0130-linkedin-dol-list/2026-04-09-evidence-enrichment-v3-plan.md` — implementation plan (good model for plugin task plans)
- `/Users/claude/.claude/plugins/marketplaces/strange-loop-syndicate/plugins/deep-research/` — reference plugin structure to follow

---

## END OF GENESIS DOCUMENT

The plugin development will proceed in subsequent phases using this document as the single source of truth for what we built and why. Compact the conversation as needed; this document preserves the essential context.
