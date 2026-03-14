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

**DO NOT spawn any agents. DO NOT spawn the orchestrator. DO NOT start research.**

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

Also include your mode recommendation with reasoning:

```
Mode Selection (default: standard)
├─ "quick" / exploration / broad overview
│   → QUICK: 100+ sources, 10-20 min
├─ No qualifier / most requests
│   → STANDARD: 300+ sources, 30-60 min [DEFAULT]
├─ "deep" / critical decision / thorough
│   → DEEP: 500+ sources, 60-120 min
└─ "ultradeep" / comprehensive review / maximum rigor
    → ULTRADEEP: 500-1000+ sources, 120-240 min
```

**After sending questions, STOP and WAIT for the user to respond.**
Do not proceed to Step 3 until the user has answered.

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

CONTEXT FROM USER:
- Goal: [from clarification]
- Audience: [from clarification]
- Scope boundaries: [from clarification]
- Time range: [from clarification]
- Known context: [from clarification]

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

Topic name extraction: strip special characters, use CamelCase or underscores.
- "psilocybin research 2025" → Psilocybin_Research_20260314
- "compare React vs Vue" → React_vs_Vue_Research_20260314
- "AI safety trends" → AI_Safety_Trends_Research_20260314

## STEP 4: Present Plan and Get Approval

After the query-strategist completes, read `evidence/scope.json` and present
the research plan to the user in this format:

```markdown
## Research Plan: [Topic]

**Research Question:** [refined question]
**Mode:** [mode] ([source target] sources, [time estimate])

### Sub-Questions (MECE Decomposition)
1. [sq_01] [question] — priority: high
2. [sq_02] [question] — priority: high
...

### Competing Hypotheses
- H1: [hypothesis text]
- H2: [hypothesis text]
- H3: [hypothesis text]

### Stakeholder Perspectives
- [perspective 1]: [who, what they care about]
- [perspective 2]: [who, what they care about]
...

### Scope
- **Time range:** [range]
- **Geographic:** [scope]
- **Excluded:** [exclusions]

**Estimated time:** [time range for mode]
```

Then ask: **"Does this research plan look good? You can: approve as-is, adjust
sub-questions, modify hypotheses, change mode, or refine scope."**

**STOP and WAIT for user approval. Do not proceed to Step 5 until the user approves.**

If the user requests changes, update `evidence/scope.json` accordingly
(re-run query-strategist or edit directly for minor changes), present the
updated plan, and ask for approval again.

## STEP 5: Launch Research

**Only after the user explicitly approves the plan**, spawn the orchestrator:

```
Agent(
  subagent_type="deep-research:research-orchestrator",
  description="Deep research: [RESEARCH_QUESTION]",
  run_in_background=true,
  prompt="""
RESEARCH QUESTION: [refined question]

MODE: [approved mode]

OUTPUT FOLDER: ~/data/skills/deep-research/[TopicName]_Research_[YYYYMMDD]/

SCOPE: PRE-APPROVED
The scope has been approved by the user. evidence/scope.json already exists
in the output folder. Skip Phase 1 (SCOPE) and proceed directly to Phase 2 (PLAN).

USER CONTEXT:
- Goal: [from clarification]
- Audience: [from clarification]
- Special focus: [any user-specified focus areas]

INSTRUCTIONS:
1. Read methodology: [plugin_root]/reference/methodology.md
2. Read report template: [plugin_root]/templates/report_template.md
3. Read the pre-approved scope from evidence/scope.json.
4. Start from Phase 2 (PLAN) — scope is already approved.
5. Execute the remaining pipeline for the selected mode.
6. Store all evidence in the output folder.
7. Generate report in MD, HTML, and PDF formats.
8. Send Telegram notification when complete.

QUALITY GATES:
- Quick: 100+ sources, report 2000+ words
- Standard: 300+ sources, report 4000+ words
- Deep: 500+ sources, report 6000+ words
- UltraDeep: 500-1000+ sources, report 10000+ words
"""
)
```

## Output Contract

### Evidence Folder Structure

```
~/data/skills/deep-research/[TopicName]_Research_[YYYYMMDD]/
├── evidence/
│   ├── sources.json          # All sources with Admiralty ratings
│   ├── claims.json           # Claims linked to source IDs
│   ├── hypotheses.json       # ACH matrix
│   ├── scope.json            # MECE decomposition + perspectives
│   ├── search_log.json       # All queries executed
│   └── pages/                # Fetched pages as markdown (A-C rated only)
├── research_report_[YYYYMMDD]_[slug].md
├── research_report_[YYYYMMDD]_[slug].html
└── research_report_[YYYYMMDD]_[slug].pdf
```

### Required Report Sections

1. Executive Summary (50-250 words)
2. Introduction (question, scope, methodology, assumptions)
3. Main Findings (4-8+ findings, each with citations)
4. Competing Hypotheses Analysis (ACH ranking, diagnostic evidence)
5. Synthesis and Insights (patterns, novel insights, implications)
6. Limitations and Caveats
   - Counterevidence Register (contradictions found, resolution, impact)
   - Key Assumptions (linchpin flagging with strength ratings)
   - Known Gaps
7. Recommendations (immediate actions, next steps, further research)
8. Bibliography (every citation, no placeholders, no ranges)
9. Appendix: Methodology
   - Source Quality Summary (Admiralty distribution, source types, waves)
   - Claims-Evidence Table (claim | sources | confidence | status)

### Quality Standards

- Every factual claim cited with [N] in same sentence
- No vague attributions ("studies show", "experts believe")
- 3+ independent sources per major claim
- 80%+ prose (not bullets)
- No placeholder text
- No marketing language (superlatives without data)
- Facts clearly distinguished from synthesis
- Counterevidence documented, not hidden

### Writing Standards

- Narrative-driven flowing prose
- Precision: exact numbers, specific metrics
- Economy: no fluff, no unnecessary modifiers
- Directness: state findings without embellishment
- High signal-to-noise ratio

### Output Formats

1. **Markdown** — primary source, full report
2. **HTML** — McKinsey-style with metrics dashboard, citation tooltips
3. **PDF** — professional print format

## Error Handling

### Stop Rules

- 2 validation failures on same error → pause, report to user
- <5 sources after exhaustive search → report limitation, ask for direction
- User interrupts or changes scope → confirm new direction

### Graceful Degradation

- 5-50 sources found → note in limitations, proceed with extra verification
- Time constraint reached → package partial results, document gaps
- Critical critique issue → address before finalizing
- WebFetch failures → fallback chain: WebFetch → Jina Reader → Playwright → skip

### Progress Reporting

The orchestrator reports progress after each major phase:
- After each wave: source count, new terms discovered
- After rating: average credibility, high-reliability count
- After triangulation: claims extracted, corroborated count, contradictions
- After critique: key assumptions, linchpin risks
- After packaging: word count, validation status

## When to Use

**Use for:**
- Comprehensive analysis requiring 10+ sources
- Technology/approach/strategy comparisons
- State-of-the-art reviews
- Multi-perspective investigations
- Market and trend analysis
- Evidence-based decision support

**Do NOT use for:**
- Simple factual lookups (use WebSearch)
- Code debugging (use standard tools)
- Questions answerable with 1-2 searches
- Time-sensitive quick answers needing <5 min
