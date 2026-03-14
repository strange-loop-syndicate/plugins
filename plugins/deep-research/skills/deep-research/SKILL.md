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

First initialize the evidence store:
python3 {scripts_path}/evidence_store.py init {output_folder}

Then create evidence/scope.json with:
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

---

## CRITICAL: Phase Gate Verification Protocol

**YOU MUST FOLLOW THIS PROTOCOL. DO NOT SKIP IT.**

After EVERY phase that modifies the evidence store, you MUST:

1. Run `python3 {scripts_path}/evidence_store.py stats --folder {output_folder}`
2. Check the output against the **Phase Gate Minimums** table below
3. **DO NOT proceed to Phase N+1 until Phase N gate passes**
4. If a gate fails, diagnose the issue (re-read the JSON file directly if needed),
   then re-run or fix the failing phase before continuing

**Why this matters:** Agents sometimes REPORT success without actually executing
their bash commands. The only way to know work was done is to check the evidence
store yourself. Trust the data, not the agent's summary.

### Phase Gate Minimums

| Phase | Gate Check | quick | standard | deep | ultradeep |
|-------|-----------|-------|----------|------|-----------|
| After Phase 2 (Plan) | `searches_total` (planned queries) | >= 20 | >= 30 | >= 40 | >= 50 |
| After Phase 3 Wave 1 | `sources_total` | >= 50 | >= 100 | >= 150 | >= 200 |
| After Phase 3 all waves | `sources_total` | >= 100 | >= 250 | >= 400 | >= 500 |
| After Phase 4 (Rate) | `sources_rated` | >= 90% of total | >= 90% | >= 90% | >= 95% |
| After Phase 4.5 (Cache) | `sources_cached` | >= 10 | >= 30 | >= 50 | >= 80 |
| After Phase 5 (Triangulate) | `claims_total` | >= 20 | >= 40 | >= 60 | >= 80 |

### Spot-Check Protocol

After any agent completes a phase that writes to JSON files, perform a spot-check:

```bash
# Example: After source-evaluator completes, verify ratings exist
python3 -c "
import json
with open('{output_folder}/evidence/sources.json') as f:
    sources = json.load(f)
total = len(sources)
rated = sum(1 for s in sources.values() if isinstance(s, dict) and s.get('rating') is not None)
print(f'Total: {total}, Rated: {rated}, Unrated: {total - rated}')
# Show a sample rated source to verify structure
for sid, s in list(sources.items())[:1]:
    print(f'Sample {sid}: rating={s.get(\"rating\")}')
"
```

If the agent reported "281 sources rated" but the spot-check shows 0 rated, the
agent failed silently. Re-run the phase.

---

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
    ├── retrieval-agent ×5-10  — web searches (parallel OK, file locking protects evidence store)
    └── source-evaluator ×1    — Admiralty ratings (run SEQUENTIALLY, one instance only)
```

**Concurrency rules:**
- Retrieval agents CAN run in parallel (evidence_store.py uses file locking)
- Source evaluator MUST run as a single instance (reads/writes all sources)
- Evidence analyst MUST run after source evaluation AND page caching are verified complete
- Critique agent MUST run after synthesis is complete

### Phase 2: PLAN (Phase 1 was done in Steps 3-4)

```
SendMessage(to: "strategist", message: """
PHASE: 2 (Plan — Wave 1 Query Generation)
Generate 30-50 Wave 1 queries based on the approved scope.

For EACH query, run this exact command:
python3 {scripts_path}/evidence_store.py log-search {output_folder} --query "YOUR QUERY HERE" --results-count 0 --wave 1

For EACH hypothesis, run this exact command:
python3 {scripts_path}/evidence_store.py add-hypothesis {output_folder} --text "YOUR HYPOTHESIS HERE"

RESEARCH FOLDER: {output_folder}
SCRIPTS PATH: {scripts_path}
""")
```

**GATE CHECK after Phase 2:**
```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
# Verify: searches_total >= [mode minimum from table]
# Verify: hypotheses_total >= 3
```

If gate fails, ask strategist to generate more queries.
Report to user: "Phase 2 complete. {N} queries planned, {N} hypotheses registered."

### Phase 3: RETRIEVE (Multi-Wave)

Spawn retrieval agents independently (parallel, stateless).
The evidence store uses file locking, so parallel writes are safe.

**IMPORTANT:** Each retrieval agent prompt MUST include the EXACT bash commands
to use. Do NOT rely on the agent figuring out the CLI syntax.

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
  prompt="""
WAVE: 1
SUB-QUESTIONS: [list the specific sub-question IDs and text]
RESEARCH FOLDER: {output_folder}
SCRIPTS PATH: {scripts_path}

QUERIES TO EXECUTE (run each via WebSearch tool):
1. "query text here"
2. "query text here"
...

FOR EACH SEARCH RESULT, run this EXACT command (replace placeholders):
python3 {scripts_path}/evidence_store.py add-source {output_folder} \
  --url "URL_HERE" \
  --title "TITLE_HERE" \
  --snippet "SNIPPET_HERE (first 150 words of relevant content)" \
  --source-type "TYPE" \
  --wave 1 \
  --search-query "THE QUERY THAT FOUND THIS"

Source type must be one of: academic, industry, government, media, blog, other

After EACH search completes, log it:
python3 {scripts_path}/evidence_store.py log-search {output_folder} \
  --query "THE QUERY" \
  --results-count NUMBER_OF_RESULTS \
  --wave 1

Save your wave report to: {output_folder}/evidence/waves/wave1_[sub_question_slug].md
""")
```

**GATE CHECK after Wave 1 (run AFTER all retrieval agents finish):**
```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
# Verify: sources_total >= [mode minimum for Wave 1 from table]
```

Wait for ALL Wave 1 agents to complete (check their task status). Then run the
gate check. If sources_total is below the minimum, investigate: read agent
reports, check if agents actually ran the bash commands, re-run failing agents.

**Wave 2: Terminology Refinement** (skip in `quick`)
- Collect wave reports from `{output_folder}/evidence/waves/wave1_*.md`
- `SendMessage(to: "strategist")` with Wave 1 results + discovered terms
- Spawn 3-5 retrieval agents for refined queries (same prompt template as above, wave=2)

**GATE CHECK after Wave 2:** sources_total should be significantly higher than after Wave 1.

**Wave 3: Citation Chain Following** (skip in `quick`)
- `SendMessage(to: "strategist")` with top-source citations
- Spawn 2-3 retrieval agents (wave=3)

**Wave 4: MECE Gap Filling** (skip in `quick`)
- `SendMessage(to: "strategist")` with coverage stats
- Spawn 2-3 retrieval agents (wave=4)

**GATE CHECK after all waves:**
```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
# Verify: sources_total >= [mode minimum for all waves from table]
```

Report: "Retrieval complete. Total: {N} sources across {W} waves."

### Phase 4: RATE SOURCES

**Run as a SINGLE agent instance. Do NOT run multiple evaluators in parallel.**

```
Agent(
  subagent_type="deep-research:source-evaluator",
  description="Rate all sources using Admiralty Code",
  prompt="""
Rate ALL unrated sources in the evidence store.

RESEARCH FOLDER: {output_folder}
SCRIPTS PATH: {scripts_path}

STEP 1: Get the list of unrated sources:
python3 {scripts_path}/evidence_store.py get-unrated {output_folder}

STEP 2: For EACH unrated source, run this EXACT command:
python3 {scripts_path}/evidence_store.py update-rating {output_folder} \
  --source-id "SOURCE_ID" \
  --reliability "A|B|C|D|E|F" \
  --credibility SCORE_1_TO_6 \
  --bias-flags '["flag1", "flag2"]' \
  --rationale "1-2 sentence explanation"

Process in batches of 20-30 sources. After each batch, verify your work:
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}

You MUST actually execute each update-rating command. Do NOT skip the bash calls.
Do NOT try to write sources.json directly — always use the CLI.

STEP 3: After completing ALL sources, run final stats:
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
Report the rating distribution.
""")
```

**GATE CHECK after Phase 4 (MANDATORY — do not skip):**

```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
```

Verify:
- `sources_rated` >= 90% of `sources_total`
- `sources_unrated` < 10% of `sources_total`

**SPOT-CHECK** (always do this after source evaluation):
```bash
python3 -c "
import json
with open('{output_folder}/evidence/sources.json') as f:
    sources = json.load(f)
rated = sum(1 for s in sources.values() if isinstance(s, dict) and s.get('rating') is not None)
print(f'Verified: {rated}/{len(sources)} sources have rating field')
sample = next((s for s in sources.values() if s.get('rating')), None)
if sample:
    print(f'Sample rating: {sample[\"rating\"]}')
else:
    print('WARNING: No ratings found! Source evaluator did not execute commands.')
"
```

If the spot-check shows 0 ratings, the source-evaluator agent failed to execute
its bash commands. Re-run Phase 4 with explicit instructions to the agent to
execute EVERY `update-rating` command.

Report: "Sources rated: {N}/{total}. A-B: {N}, C: {N}, D-F: {N}."

### Phase 4.5: FETCH TOP SOURCES

Cache full page content for A-C rated sources. This phase uses two approaches:

**Approach 1 (Preferred): WebFetch tool — you do this yourself**

Get the list of A-C sources:
```bash
python3 {scripts_path}/evidence_store.py get-by-rating {output_folder} --min-reliability C
```

For each source URL, use the WebFetch tool to get the content, then save it:
```bash
# Save fetched content to the pages directory
cat > {output_folder}/evidence/pages/{source_id}.md << 'PAGEEOF'
[paste WebFetch content here]
PAGEEOF

# Update sources.json to mark as cached (uses file locking)
python3 -c "
import json, fcntl, os
path = '{output_folder}/evidence/sources.json'
lock_fd = open(path + '.lock', 'w')
fcntl.flock(lock_fd, fcntl.LOCK_EX)
with open(path) as f:
    sources = json.load(f)
sources['{source_id}']['page_cached'] = True
sources['{source_id}']['page_file'] = 'pages/{source_id}.md'
tmp = path + '.tmp'
with open(tmp, 'w') as f:
    json.dump(sources, f, indent=2, ensure_ascii=False)
    f.write('\n')
os.rename(tmp, path)
fcntl.flock(lock_fd, fcntl.LOCK_UN)
lock_fd.close()
"
```

**Approach 2 (Fallback): page_cache.py script**

For sources where WebFetch is unavailable or you want batch processing:
```bash
python3 {scripts_path}/page_cache.py fetch {output_folder} --source-id {id} --url "{url}"
```

Note: page_cache.py uses urllib which gets blocked by Cloudflare and many modern
sites. Prefer WebFetch for better success rates.

**Prioritization:** Cache A and B sources first, then C sources. Skip D-F sources.
If a fetch fails, log it and continue — do not block the pipeline.

**GATE CHECK after Phase 4.5:**
```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
# Verify: sources_cached >= [mode minimum from table]
```

Also verify pages are not empty:
```bash
find {output_folder}/evidence/pages/ -name "*.md" -size 0 -o -name "*.md" -size 1c | wc -l
# Should be 0 (no empty files)
```

Report: "Pages cached: {N}. Empty pages: {M} (re-fetch if > 0)."

### Phase 5: TRIANGULATE

**PREREQUISITE CHECK:** Before starting this phase, confirm:
1. `sources_rated` >= 90% of `sources_total` (from Phase 4 gate)
2. `sources_cached` >= [mode minimum] (from Phase 4.5 gate)
3. Pages directory has actual content (not empty files)

```
SendMessage(to: "analyst", message: """
PHASE: 5 (Triangulation)
Extract claims and build the ACH matrix.

RESEARCH FOLDER: {output_folder}
SCRIPTS PATH: {scripts_path}

STEP 1: Read hypotheses from evidence/scope.json
STEP 2: List and read all cached pages in evidence/pages/
STEP 3: For EACH page, extract 3-10 factual claims

For EACH claim, run this EXACT command:
python3 {scripts_path}/evidence_store.py add-claim {output_folder} \
  --text "CLAIM TEXT HERE" \
  --source-ids '["s_abc123", "s_def456"]' \
  --category "CATEGORY" \
  --confidence "high|moderate|low|very_low"

STEP 4: For EACH claim against EACH hypothesis, run:
python3 {scripts_path}/evidence_store.py update-assessment {output_folder} \
  --hypothesis-id "h_001" \
  --claim-id "c_0001" \
  --assessment "consistent|inconsistent|neutral"

STEP 5: Generate analysis artifacts:
- Write triangulation summary to: {output_folder}/evidence/triangulation.md
- Write ACH matrix to: {output_folder}/evidence/ach_matrix.md

STEP 6: Run final stats to verify:
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
""")
```

**GATE CHECK after Phase 5:**
```bash
python3 {scripts_path}/evidence_store.py stats --folder {output_folder}
# Verify: claims_total >= [mode minimum from table]
```

Also verify analysis artifacts exist:
```bash
ls -la {output_folder}/evidence/triangulation.md {output_folder}/evidence/ach_matrix.md
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
Save critique to: {output_folder}/evidence/CRITIQUE.md
""")
```

Report: "Linchpin assumptions: {N}. Actionable items: {N}."

### Phase 9: REFINE (skip in `quick`)

1. `SendMessage(to: "strategist")` for 5-10 targeted gap-filling queries
2. Spawn 2-3 retrieval agents (same detailed prompt template as Phase 3)
3. **GATE CHECK:** Run stats, verify sources_total increased
4. `SendMessage(to: "analyst")` to re-analyze with new evidence
5. **GATE CHECK:** Run stats, verify claims_total increased
6. Update synthesis if conclusions change

### Phase 10: PACKAGE

Write report progressively (section by section):
1. Read template from `[plugin_root]/templates/report_template.md`
2. Generate: Executive Summary, Methodology, Main Findings, Competing Hypotheses,
   Counterevidence Register, Claims-Evidence Table, Source Quality Summary,
   Key Assumptions, Limitations, References
3. Save as: `{output_folder}/research_report_[YYYYMMDD]_[slug].md`
4. Validate: `python3 {scripts_path}/validate_report.py {output_folder}/research_report_*.md`
5. Verify citations: `python3 {scripts_path}/verify_citations.py {output_folder}/research_report_*.md`
6. Generate HTML: `python3 {scripts_path}/verify_html.py {output_folder}/research_report_*.md`

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
Gate check: [PASS/FAIL] — {details}
---
```

## Output Contract

### Evidence Folder Structure

```
~/data/skills/deep-research/[TopicName]_Research_[YYYYMMDD]/
├── evidence/
│   ├── sources.json          # All sources with ratings
│   ├── claims.json           # Extracted claims
│   ├── hypotheses.json       # Hypotheses with ACH assessments
│   ├── scope.json            # Research scope and MECE decomposition
│   ├── search_log.json       # All search queries logged
│   ├── triangulation.md      # Triangulation summary
│   ├── ach_matrix.md         # ACH matrix visualization
│   ├── ANALYSIS.md           # Full analysis narrative
│   ├── CRITIQUE.md           # Critique agent output
│   ├── pages/                # Fetched A-C source pages (one .md per source)
│   └── waves/                # Wave reports from retrieval agents
│       ├── wave1_*.md
│       ├── wave2_*.md
│       └── wave3_*.md
├── research_report_[YYYYMMDD]_[slug].md
├── research_report_[YYYYMMDD]_[slug].html
└── research_report_[YYYYMMDD]_[slug].pdf
```

**Wave reports MUST go in `evidence/waves/`.** Do not scatter them in root or evidence/.

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

- Retrieval agent fails → log and continue, but track failure count
- Source evaluation fails → mark as F6, continue
- Page cache fails (403/Cloudflare) → try WebFetch fallback, then mark `page_cached: false`
- Validation fails → fix and re-validate
- Source count below target → note in report, don't fabricate
- Team member unresponsive → spawn fresh independent agent as fallback
- 2 validation failures on same error → pause, report to user
- **Gate check fails → DO NOT proceed. Diagnose, fix, re-run the phase.**
- **Agent reports success but spot-check fails → re-run with explicit bash commands**
