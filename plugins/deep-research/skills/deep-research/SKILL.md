---
name: deep-research
description: >
  Conduct world-class research with 100-1000+ sources, competing hypothesis analysis,
  structured evidence management, and rigorous verification. Triggers: "deep research",
  "comprehensive analysis", "research report", "compare X vs Y", "analyze trends",
  "state of the art", "research on", "investigate".
  Do NOT use for simple lookups, debugging, or questions answerable with 1-2 searches.
---

# Deep Research

## STEP 1: Validate This Is a Research Task

```
Is this a research task?
├─ Simple lookup / 1-2 searches → STOP. Use WebSearch directly.
├─ Debugging / code question → STOP. Use standard tools.
└─ Needs 10+ sources, synthesis, verification → Go to STEP 2.
```

## STEP 2: Clarify Research Task With User

**DO NOT spawn any agents. DO NOT start research.**

Your ONLY action in this step is to respond to the user with clarification questions.
No tool calls. Just a text response with questions.

Ask 3-5 of these questions (skip what's already obvious from the query):

1. **Goal**: "What decision or outcome will this research support?"
2. **Audience**: "Who is the intended audience? (technical, executive, general)"
3. **Scope boundaries**: "Any specific aspects to focus on or exclude?"
4. **Time range**: "What time period? (e.g., last 2 years, historical overview)"
5. **Geographic scope**: "Global or specific regions?"
6. **Known context**: "What do you already know? Any sources or leads to start from?"
7. **Depth vs breadth**: "Prefer comprehensive breadth or deep-dive on key areas?"
8. **Deliverable**: "Any specific format needs beyond the standard report?"

Also include your mode recommendation:

| Mode | Sources | Time | When |
|------|---------|------|------|
| quick | 100+ | 10-20 min | Exploration, broad overview |
| standard | 300+ | 30-60 min | Most requests (default) |
| deep | 500+ | 60-120 min | Critical decisions |
| ultradeep | 500-1000+ | 120-240 min | Maximum rigor |

**After sending questions, STOP and WAIT for the user to respond.**

## STEP 3: Generate Research Plan

Only after user answers your clarification questions.

Spawn the `deep-research:query-strategist` agent to produce the research scope:

```
Agent(
  subagent_type="deep-research:query-strategist",
  description="Generate research scope for: [TOPIC]",
  prompt="""
PHASE: 1 (Scope)
RESEARCH QUESTION: [refined question based on user's answers]
CONTEXT FROM USER: [goal, audience, scope, time range, known context]
OUTPUT FOLDER: ~/data/skills/deep-research/[TopicName]_Research_[YYYYMMDD]/
SCRIPTS PATH: [plugin_root]/scripts

Create the evidence/ directory and generate evidence/scope.json with:
- 8-12 MECE sub-questions
- 5-7 stakeholder perspectives
- 3-5 competing hypotheses
- Inclusion/exclusion criteria
"""
)
```

Topic name: strip special chars, use CamelCase (e.g., `Dub_Techno_Plugins_Research_20260314`).

## STEP 4: Present Plan and Get Approval

Read `evidence/scope.json` and present the research plan:

```markdown
## Research Plan: [Topic]

**Research Question:** [refined question]
**Mode:** [mode] ([source target] sources, [time estimate])

### Sub-Questions (MECE Decomposition)
1. [question] — priority: high/medium/low
...

### Competing Hypotheses
- H1: [text]
...

### Stakeholder Perspectives
- [type]: [who, what they care about]
...

### Scope
- **Time range / Geographic / Excluded:** [details]

**Estimated time:** [range]
```

Ask: **"Does this research plan look good? You can: approve as-is, adjust
sub-questions, modify hypotheses, change mode, or refine scope."**

**STOP and WAIT for user approval. Do not proceed until the user approves.**

## STEP 5: Run the Research Pipeline

**Only after user explicitly approves.** You orchestrate the pipeline directly
from the main session — no orchestrator agent. This gives the user full
visibility into every phase.

Set variables for the session:
- `output_folder` = `~/data/skills/deep-research/[TopicName]_Research_[YYYYMMDD]/`
- `scripts_path` = `[plugin_root]/scripts`
- `reference_path` = `[plugin_root]/reference`

Read the methodology reference: `{reference_path}/methodology.md`
Read the report template: `[plugin_root]/templates/report_template.md`

### Phase 0: Create Research Team

Create a team for agents that need back-and-forth communication across phases:

```
TeamCreate(
  team_name="research-team",
  members=[
    {name: "strategist", subagent_type: "deep-research:query-strategist"},
    {name: "analyst", subagent_type: "deep-research:evidence-analyst"},
    {name: "critic", subagent_type: "deep-research:critique-agent"}
  ]
)
```

Architecture:
```
You (main session — orchestrator)
│
├── TEAM: "research-team" (persistent, via SendMessage)
│   ├── strategist  — query generation, gap analysis
│   ├── analyst     — claim extraction, ACH matrix
│   └── critic      — assumptions check, bias audit
│
└── INDEPENDENT (via Agent tool, stateless, parallel)
    ├── retrieval-agent ×5-10  — web searches
    └── source-evaluator ×1    — Admiralty ratings
```

### Phase 2: PLAN (Phase 1 was done in Steps 3-4)

```
SendMessage(to: "strategist", message: """
PHASE: 2 (Plan — Wave 1 Query Generation)
Generate 30-50 Wave 1 queries based on the approved scope.
Log them: python3 {scripts_path}/evidence_store.py log-search --folder {output_folder} --query "..." --wave 1 --sub-question "sq_XX" --status planned
Save hypotheses: python3 {scripts_path}/evidence_store.py add-hypothesis --folder {output_folder} --text "..."
RESEARCH FOLDER: {output_folder}
SCRIPTS PATH: {scripts_path}
""")
```

Verify: queries cover all MECE branches, 10%+ contrarian.
Report to user: "Phase 2 complete. {N} queries planned."

### Phase 3: RETRIEVE (Multi-Wave)

Spawn retrieval agents independently (parallel, stateless):

**Wave 1: Broad Coverage**
- Read `evidence/search_log.json` for planned queries
- Distribute across 5-10 `deep-research:retrieval-agent` instances
- Each gets 5-10 queries for 1-2 sub-questions
- Check `free -h` before each batch of 5

```
Agent(
  subagent_type="deep-research:retrieval-agent",
  description="Retrieve: [sub-questions]",
  run_in_background=true,
  prompt="WAVE: 1\nQUERIES: [...]\nRESEARCH FOLDER: {output_folder}\nSCRIPTS PATH: {scripts_path}\nExecute queries via WebSearch, add to evidence store. Report: sources added, terminology, citations."
)
```

After Wave 1: report source count, discovered terms.

**Wave 2: Terminology Refinement** (skip in `quick`)
- `SendMessage(to: "strategist")` with Wave 1 results + discovered terms
- Spawn 3-5 retrieval agents for refined queries

**Wave 3: Citation Chain Following** (skip in `quick`)
- `SendMessage(to: "strategist")` with top-source citations
- Spawn 2-3 retrieval agents

**Wave 4: MECE Gap Filling** (skip in `quick`)
- `SendMessage(to: "strategist")` with coverage stats
- Spawn 2-3 retrieval agents

Report: "Retrieval complete. Total: {N} sources."

### Phase 4: RATE SOURCES

Spawn independent source evaluator:
```
Agent(
  subagent_type="deep-research:source-evaluator",
  description="Rate sources: Admiralty Code",
  prompt="Rate all unrated sources in evidence/sources.json.\nRESEARCH FOLDER: {output_folder}\nSCRIPTS PATH: {scripts_path}"
)
```

Report: "A-B: {N}, C: {N}, D-F: {N}."

### Phase 4.5: FETCH TOP SOURCES

Cache pages for A-C rated sources:
```bash
python3 {scripts_path}/evidence_store.py get-sources-by-rating --folder {output_folder} --min-reliability C
python3 {scripts_path}/page_cache.py fetch --folder {output_folder} --source-id {id} --url "{url}"
```

### Phase 5: TRIANGULATE

```
SendMessage(to: "analyst", message: """
Extract claims and build the ACH matrix.
- Cached pages: {output_folder}/evidence/pages/
- Hypotheses: {output_folder}/evidence/scope.json
- Sources: {output_folder}/evidence/sources.json
Output to: claims.json, hypotheses.json
RESEARCH FOLDER: {output_folder}
SCRIPTS PATH: {scripts_path}
""")
```

Report: "Claims: {N}. Corroborated (3+): {N}. Contradictions: {N}."

### Phase 6: OUTLINE REFINEMENT (do yourself)

Read scope.json, claims.json, hypotheses.json. Adapt report outline:
strong evidence → dedicated sections, weak → sub-sections with caveats,
unexpected findings → new sections, empty branches → noted as gaps.

### Phase 7: SYNTHESIZE (do yourself)

Apply: ACH Ranking, Pattern Recognition, "So What?" Filter, Pyramid Principle,
Novel Insights. This requires deep reasoning — don't delegate.

Report: "Leading conclusion: {text}. Key findings: {N}."

### Phase 8: CRITIQUE

```
SendMessage(to: "critic", message: """
Critique this synthesis.
SYNTHESIS: [your synthesis]
LEADING HYPOTHESIS: [text]
Evidence at: {output_folder}/evidence/
Perform: Key Assumptions Check, Devil's Advocacy, Bias Audit.
Output actionable items.
""")
```

Report: "Linchpin assumptions: {N}. Actionable items: {N}."

### Phase 9: REFINE (skip in `quick`)

1. `SendMessage(to: "strategist")` for 5-10 targeted gap-filling queries
2. Spawn 2-3 retrieval agents
3. `SendMessage(to: "analyst")` to re-analyze with new evidence
4. Update synthesis if conclusions change

### Phase 10: PACKAGE

Write report progressively (section by section):
1. Read template from `[plugin_root]/templates/report_template.md`
2. Generate: Executive Summary, Methodology, Main Findings, Competing Hypotheses,
   Counterevidence Register, Claims-Evidence Table, Source Quality Summary,
   Key Assumptions, Limitations, References
3. Validate: `python3 {scripts_path}/validate_report.py {output_folder}/research_report_*.md`
4. Verify citations: `python3 {scripts_path}/verify_citations.py {output_folder}/research_report_*.md`
5. Generate HTML: `python3 {scripts_path}/verify_html.py {output_folder}/research_report_*.md`

### Phase 11: VERIFY

```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
```

Report final metrics to user:
- Total sources, rated count, reliability distribution
- Pages cached, claims extracted, corroborated count
- Hypotheses tested, leading hypothesis
- Report word count, citation density, mode target met/not

### Quality Gates

| Mode | Sources | Waves | Report Length |
|------|---------|-------|--------------|
| quick | 100+ | 1-2 | 2000+ words |
| standard | 300+ | 3-4 | 4000+ words |
| deep | 500+ | 4 | 6000+ words |
| ultradeep | 500-1000+ | 4+ | 10000+ words |

## Progress Reporting

After EVERY phase, report progress to the user:
```
--- Phase {N}: {NAME} ---
{Summary + key metrics}
---
```

## Output Contract

### Evidence Folder Structure

```
~/data/skills/deep-research/[TopicName]_Research_[YYYYMMDD]/
├── evidence/
│   ├── sources.json, claims.json, hypotheses.json, scope.json, search_log.json
│   └── pages/                # Fetched A-C source pages
├── research_report_[YYYYMMDD]_[slug].md
├── research_report_[YYYYMMDD]_[slug].html
└── research_report_[YYYYMMDD]_[slug].pdf
```

### Report Quality Standards

- Every claim cited with [N] in same sentence. No vague attributions.
- 3+ independent sources per major claim
- 80%+ prose, no placeholder text, no marketing language
- Counterevidence documented, not hidden
- Narrative-driven, precise, economical, direct

### Output Formats

1. **Markdown** — primary source
2. **HTML** — McKinsey-style with metrics dashboard
3. **PDF** — professional print format

## Error Handling

- Retrieval agent fails → log and continue
- Source evaluation fails → mark as F6, continue
- Page cache fails → mark `page_cached: false`, continue
- Validation fails → fix and re-validate
- Source count below target → note in report, don't fabricate
- Team member unresponsive → spawn fresh independent agent as fallback
- 2 validation failures on same error → pause, report to user
