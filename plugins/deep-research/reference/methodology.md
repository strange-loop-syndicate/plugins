# Research Methodology Reference

This document contains detailed analytical protocols used by the research-orchestrator
and its sub-agents. Load sections on-demand as needed during each phase.

---

## 1. MECE Decomposition Protocol (McKinsey)

**Purpose:** Decompose the research question into exhaustive, non-overlapping sub-questions
that collectively cover the entire problem space.

**When used:** Phase 1 (Scope), by the query-strategist agent.

### Steps

1. **State the core question** in one sentence. Remove ambiguity.

2. **Identify the decomposition axis.** Choose the dimension that best splits the question:
   - By stakeholder (who is affected?)
   - By time horizon (past / present / future)
   - By geography (regions, markets)
   - By component (technical layers, value chain stages)
   - By causal factor (supply-side / demand-side drivers)
   - By evaluation criterion (cost, performance, risk, adoption)

3. **Generate 8-12 sub-questions** along the chosen axis. Each sub-question must:
   - Be answerable independently
   - Not overlap with any other sub-question
   - Contribute to answering the parent question

4. **MECE validation check.** For each pair of sub-questions, ask:
   - "Could a source be relevant to both?" If yes, sharpen the boundary.
   - "Is there any aspect of the parent question not covered?" If yes, add a sub-question.

5. **Prioritize using 80/20.** Rank sub-questions by expected information value.
   The top 3-4 sub-questions should yield ~80% of the answer.

6. **Assign search weight.** Allocate more queries to high-priority sub-questions.

### Example Decomposition

**Parent question:** "What is the state of quantum computing in 2026?"

| # | Sub-question | Priority | Queries |
|---|-------------|----------|---------|
| 1 | What hardware milestones were achieved in 2025-2026? | High | 6 |
| 2 | Which error correction approaches are leading? | High | 5 |
| 3 | What practical applications have been demonstrated? | High | 5 |
| 4 | How do major players (Google, IBM, Microsoft, startups) compare? | High | 5 |
| 5 | What is the current funding and investment landscape? | Medium | 4 |
| 6 | What are the key remaining technical barriers? | Medium | 4 |
| 7 | How has the software/algorithm ecosystem evolved? | Medium | 3 |
| 8 | What policy and regulatory developments affect the field? | Low | 3 |
| 9 | What workforce and talent trends exist? | Low | 2 |
| 10 | What is the timeline consensus for quantum advantage? | Medium | 3 |

**Validation:** No sub-question overlaps. Together they cover hardware, software,
applications, players, economics, barriers, policy, talent, and timeline = exhaustive.

---

## 2. STORM Perspective Generation (Stanford)

**Purpose:** Generate diverse stakeholder perspectives to avoid blind spots and ensure
multi-angle coverage of the research question.

**When used:** Phase 1 (Scope), by the query-strategist agent.

**Source:** Stanford STORM paper (arXiv 2402.14207) — simulated conversations between
diverse perspectives produce more comprehensive and balanced research.

### Standard Perspectives (adapt to topic)

| Perspective | Role | Question Focus |
|------------|------|----------------|
| **Domain Expert** | Deep technical specialist | Mechanisms, methodologies, state of the art, technical feasibility |
| **Skeptical Analyst** | Critical evaluator | Weaknesses, limitations, failure modes, overhyped claims |
| **Industry Practitioner** | Working professional | Real-world adoption, implementation challenges, ROI |
| **Historian** | Contextualizer | How we got here, precedents, cyclical patterns, lessons from analogues |
| **Policy Analyst** | Regulatory/governance focus | Regulations, standards, ethical considerations, public interest |
| **Economic Analyst** | Market/financial focus | Market size, investment flows, cost structures, business models |
| **Futurist** | Forward-looking strategist | Trajectories, inflection points, second-order effects, scenarios |

### Generating Perspective-Specific Questions

For each perspective, generate 3-5 questions that person would ask:

**Domain Expert on quantum computing:**
- "What qubit modality has the best error rate trajectory?"
- "Is the threshold theorem being validated experimentally?"
- "Which fault-tolerant architectures are most promising?"

**Skeptical Analyst on quantum computing:**
- "Are quantum advantage claims reproducible by independent teams?"
- "What is the actual decoherence time vs what is needed for useful computation?"
- "How many claimed breakthroughs failed to replicate?"

**Industry Practitioner on quantum computing:**
- "Can any current quantum system solve a real business problem faster than classical?"
- "What does the development stack look like — is it production-ready?"
- "What is the total cost of operating a quantum system vs cloud classical?"

### Integration

Combine perspective questions with MECE sub-questions to generate the full query set.
Each MECE branch should be explored from at least 2-3 perspectives.

---

## 3. ACH Matrix Construction (Heuer, CIA)

**Purpose:** Systematically evaluate competing hypotheses against evidence to identify
the best-supported explanation. Prevents confirmation bias by forcing evaluation of
all hypotheses against all evidence.

**When used:** Phase 1 (hypothesis generation), Phase 5 (triangulation), Phase 7 (synthesis).

**Source:** Richards Heuer, "Psychology of Intelligence Analysis" (CIA, 1999).

### The 7 Steps

**Step 1: Identify hypotheses.**
Generate 3-5 competing hypotheses that could answer the research question. Include
at least one that challenges conventional wisdom. Each hypothesis must be:
- Falsifiable (evidence could prove it wrong)
- Distinct (not a variant of another hypothesis)
- Plausible (not a straw man)

**Step 2: List significant evidence and arguments.**
Compile all evidence items (claims extracted from sources). Include:
- Data points, statistics, experimental results
- Expert opinions and consensus positions
- Logical arguments and theoretical frameworks
- Absence of expected evidence (diagnostic in itself)

**Step 3: Prepare the matrix.**
Create a matrix with hypotheses as columns and evidence as rows:

| Evidence | H1: [Hypothesis 1] | H2: [Hypothesis 2] | H3: [Hypothesis 3] |
|----------|--------------------|--------------------|---------------------|
| E1: [Evidence item] | CC / C / N / I / II | ... | ... |
| E2: [Evidence item] | ... | ... | ... |

Rating scale:
- **CC** = Very Consistent (strongly supports)
- **C** = Consistent (supports)
- **N** = Neutral (neither supports nor contradicts)
- **I** = Inconsistent (contradicts)
- **II** = Very Inconsistent (strongly contradicts)

**Step 4: Work ACROSS the matrix, not down.**
This is the critical principle. For each evidence item (row), ask:
"How well does this evidence fit with EACH hypothesis?"

Do NOT evaluate all evidence for one hypothesis, then move to the next.
Working across forces comparative thinking and reveals diagnosticity.

**Step 5: Identify diagnosticity.**
Evidence that is consistent with ALL hypotheses is non-diagnostic — it tells
you nothing about which hypothesis is correct. Focus analysis on evidence that
differentiates: consistent with some hypotheses, inconsistent with others.

Diagnosticity score = number of different ratings across hypotheses.
- All same rating → diagnosticity = 0 (worthless for discrimination)
- Mix of C and I → diagnosticity = high (very useful)

**Step 6: Rank hypotheses by least inconsistent evidence.**
The winning hypothesis is NOT the one with the most supporting evidence.
It is the one with the LEAST inconsistent evidence. This is counterintuitive
but analytically rigorous — it prevents confirmation bias.

Count inconsistent (I) and very inconsistent (II) ratings for each hypothesis.
The hypothesis with the fewest is the best supported.

**Step 7: Sensitivity analysis.**
Ask: "If I removed or changed the most diagnostic evidence items, would the
ranking change?" If one or two pieces of evidence drive the entire conclusion,
flag them as linchpin evidence requiring extra verification.

### Output Format

```json
{
  "hypotheses": [
    {"id": "h_001", "text": "...", "inconsistent_count": 2, "rank": 1},
    {"id": "h_002", "text": "...", "inconsistent_count": 5, "rank": 2}
  ],
  "most_diagnostic_evidence": ["c_0012", "c_0034", "c_0056"],
  "linchpin_evidence": ["c_0012"],
  "non_diagnostic_evidence": ["c_0001", "c_0003", "c_0007"]
}
```

---

## 4. Multi-Wave Retrieval Protocol

**Purpose:** Systematic, iterative information gathering that maximizes source coverage
and minimizes blind spots through four progressive waves.

**When used:** Phase 3 (Retrieve), coordinated by the orchestrator with retrieval-agents.

### Wave 1: Broad Coverage

**Goal:** Cast a wide net across all MECE branches.

**Execution:**
- Generate 30-50 search queries covering all MECE sub-questions and perspectives
- Deploy 10-20 retrieval-agents in parallel (batch 5 at a time to manage memory)
- Each agent executes 5-10 WebSearch queries on its assigned sub-questions
- For each result: add to sources.json (URL, title, snippet, metadata)
- Deduplicate by normalized URL hash

**Query construction guidelines:**
- Mix broad and specific queries
- Include year filters for recency ("2025", "2026")
- Use domain-specific terminology where known
- Include negative queries ("X limitations", "X criticism", "X failure")
- Vary query structure: questions, keywords, phrases

**Target per mode:**
| Mode | Wave 1 Queries | Wave 1 Sources |
|------|---------------|----------------|
| Quick | 15-25 | 60-80 |
| Standard | 30-50 | 150-250 |
| Deep | 40-60 | 250-400 |
| UltraDeep | 50-70 | 300-500 |

### Wave 2: Terminology Refinement

**Goal:** Use discovered expert terminology to find sources missed in Wave 1.

**Execution:**
- Review Wave 1 results for domain-specific terms, jargon, acronyms
- Generate 10-20 refined queries using newly discovered terminology
- Target sub-questions with thin Wave 1 coverage
- Example: Wave 1 used "quantum error correction" → Wave 2 uses "surface code threshold",
  "topological qubits", "magic state distillation" (terms found in Wave 1 results)

### Wave 3: Citation Chain Following

**Goal:** Trace references from top-quality sources to discover authoritative material
not surfaced by web search.

**Execution:**
- Identify top 10-20 sources by Admiralty rating (A-B rated)
- Read their references, citations, and "related work" sections
- Search for cited papers, reports, and datasets by title
- Particularly valuable for academic sources that cite foundational work
- 5-10 targeted searches

### Wave 4: MECE Gap-Filling

**Goal:** Ensure every MECE branch has adequate coverage.

**Execution:**
- Compare source count per MECE sub-question against target
- Identify branches with < 5 sources (gaps)
- Generate 5-10 highly targeted queries for gap areas
- May use different search strategies: site-specific searches, alternative
  query formulations, non-English sources

### Quality Gates per Mode

| Mode | Min Total Sources | Min A-C Sources | Min Claims | Max Time |
|------|------------------|-----------------|------------|----------|
| Quick | 100 | 30 | 20 | 20 min |
| Standard | 300 | 100 | 50 | 60 min |
| Deep | 500 | 200 | 100 | 120 min |
| UltraDeep | 500-1000 | 300 | 150 | 240 min |

---

## 5. Admiralty Code Rating Guidelines (NATO)

**Purpose:** Standardized source evaluation framework used by NATO intelligence services.
Two independent dimensions: reliability of the source, credibility of the information.

**When used:** Phase 4 (Rate Sources), by the source-evaluator agent.

### Reliability Scale (A-F): "Can I trust this source?"

| Rating | Label | Description | Examples |
|--------|-------|-------------|----------|
| **A** | Completely Reliable | Established authority, track record of accuracy, institutional accountability, peer review | Nature, Science, NIST, WHO, IEEE, major government agencies |
| **B** | Usually Reliable | Generally accurate, professional editorial standards, occasional errors but self-correcting | Major newspapers (NYT, WSJ, FT), established industry analysts (Gartner, McKinsey), university press releases |
| **C** | Fairly Reliable | Mix of accurate and inaccurate, identifiable editorial process, some quality control | Trade publications, mid-tier news outlets, conference proceedings, well-maintained wikis |
| **D** | Not Usually Reliable | Frequent errors, weak editorial standards, inconsistent quality | Personal blogs, small news sites, self-published reports, forums |
| **E** | Unreliable | Known for inaccuracy, propaganda, or fabrication | Tabloids, known disinformation sources, SEO content farms |
| **F** | Reliability Cannot Be Judged | New or unknown source, insufficient track record | First-time publications, anonymous sources, paywalled content not accessible |

### Credibility Scale (1-6): "Can I trust this specific information?"

| Rating | Label | Description | Indicators |
|--------|-------|-------------|------------|
| **1** | Confirmed | Verified by independent sources, replicable data, official records | Multiple independent confirmations, government data, replicated experiments |
| **2** | Probably True | Consistent with known facts, logical, from credible source but not independently confirmed | Single authoritative source, consistent with base knowledge, well-reasoned |
| **3** | Possibly True | Plausible, some supporting evidence but not fully corroborated | Limited evidence, logical but unverified, early-stage findings |
| **4** | Doubtfully True | Questionable, inconsistent with some known facts, or from unreliable source with plausible claim | Contradicts some evidence, poorly sourced, speculative but not impossible |
| **5** | Improbable | Contradicts majority of evidence, implausible given known facts | Major contradictions, extraordinary claims without extraordinary evidence |
| **6** | Truth Cannot Be Judged | Insufficient information to assess, no basis for comparison | Novel domain, no prior data, ambiguous or incomplete information |

### Bias Flag Categories

Apply zero or more bias flags to each source:
- **VENDOR** — Source is writing about their own product/service/company
- **SPONSORED** — Content is sponsored, advertorial, or paid placement
- **IDEOLOGICAL** — Strong ideological or political framing shapes presentation
- **SELECTION** — Cherry-picks data that supports a predetermined conclusion
- **RECENCY** — Outdated information presented as current
- **GEOGRAPHIC** — Applies local context as if it were universal

### Rating Protocol

1. For each source, first assess reliability (A-F) based on the publisher/source identity
2. Then assess credibility (1-6) based on the specific content
3. Apply bias flags if applicable
4. Write 1-2 sentence rationale
5. Conservative default: when uncertain about source or content, rate **D3**
   (not usually reliable, possibly true)

### Batch Processing

When rating in batches of 20-50 sources:
- First pass: rate using URL, title, snippet, and world knowledge (fast, no page fetch)
- Second pass (optional): re-rate A-C sources after reading full page content
  (may upgrade or downgrade based on actual content quality)

---

## 6. Key Assumptions Check (CIA)

**Purpose:** Identify and stress-test the assumptions underpinning conclusions.
Assumptions are beliefs taken for granted — they are invisible until challenged.

**When used:** Phase 8 (Critique), by the critique-agent.

**Source:** CIA Structured Analytic Techniques.

### 4-Step Protocol

**Step 1: Surface assumptions.**
State the current leading conclusion. Then list every assumption (stated AND unstated)
that must be true for this conclusion to hold. Categories to check:
- Definitional: Are we defining key terms the same way sources do?
- Evidentiary: Are we assuming sources are independent? That reported data is accurate?
- Causal: Are we assuming X causes Y, when it might only correlate?
- Contextual: Are we assuming conditions will remain stable?
- Scope: Are we assuming findings generalize beyond the studied population?

Aim for 5-10 assumptions per conclusion.

**Step 2: Challenge each assumption.**
For each assumption, ask:
- "Why must this be true?"
- "What evidence supports it?"
- "What evidence would invalidate it?"
- "Has this assumption ever been wrong in analogous situations?"
- "What would change if this assumption is false?"

**Step 3: Rate assumption strength.**

| Rating | Meaning | Action |
|--------|---------|--------|
| **Strong** | Well-supported by evidence, unlikely to be wrong | Monitor |
| **Moderate** | Some support, but could be wrong under plausible conditions | Flag in report |
| **Weak** | Little support, or evidence is mixed | Investigate further, prominent flag |

**Step 4: Identify linchpin assumptions.**
A linchpin assumption is one that is both:
- **Weak or moderate** in strength
- **Critical** to the conclusion (if wrong, the conclusion falls apart)

Linchpin assumptions must be:
- Prominently flagged in the report's Key Assumptions section
- Targeted for additional evidence in Phase 9 (Refine)
- Accompanied by a "what if wrong" scenario

---

## 7. Devil's Advocacy Protocol

**Purpose:** Construct the strongest possible argument against the leading conclusion
to test its robustness. Not a weak "but maybe..." — a genuine attempt to defeat
the conclusion.

**When used:** Phase 8 (Critique), by the critique-agent.

### Steps

**Step 1: State the leading conclusion clearly.**
One sentence, unambiguous.

**Step 2: Steel-man the opposition.**
Construct the single strongest counter-argument. Rules:
- Use real evidence from the research (not hypothetical)
- Present it as compellingly as a true believer would
- Do not weaken it with qualifiers
- If no real counter-evidence exists, state that explicitly (the conclusion is robust)

**Step 3: Identify what evidence would change the conclusion.**
List 3-5 specific, concrete pieces of evidence that, if found, would force
a revision of the conclusion. Examples:
- "A replicated study showing no effect with n>500 would invalidate Finding 3"
- "Evidence that the 2025 market data was revised downward by >20% would change the outlook"

**Step 4: Assess the counter-argument's strength.**
Rate the devil's advocate case:
- **Strong**: Genuine risk that the conclusion is wrong. Add prominent caveat.
- **Moderate**: Plausible alternative, but weight of evidence favors the conclusion.
  Note in limitations.
- **Weak**: Counter-argument exists but evidence strongly against it. Brief mention.

**Step 5: Bias audit.**
Check the overall research for systematic biases:

| Bias | Check | Indicator |
|------|-------|-----------|
| **Confirmation** | Did we favor evidence supporting initial hypothesis? | Early sources disproportionately cited |
| **Availability** | Did prominent/recent sources dominate? | Source date clustering, same publications repeated |
| **Anchoring** | Did first sources shape all subsequent interpretation? | Conclusions mirror Wave 1 findings despite later contradictions |
| **Source homogeneity** | Are sources from the same type/region/perspective? | >70% from one source type or geographic region |
| **Survivorship** | Are we only seeing successes, not failures? | No failure cases, no negative results documented |

---

## 8. GRADE-Inspired Evidence Certainty

**Purpose:** Rate the overall certainty of each major conclusion using a framework
adapted from GRADE (Grading of Recommendations, Assessment, Development, Evaluation).
Originally medical; adapted here for general research.

**When used:** Phase 7 (Synthesize), by the orchestrator.

### Certainty Levels

| Level | Meaning |
|-------|---------|
| **High** | Very confident the true effect/state is close to our estimate. Further research unlikely to change the conclusion. |
| **Moderate** | Moderately confident. Further research likely to have an important impact and may change the conclusion. |
| **Low** | Limited confidence. Further research very likely to change the conclusion. |
| **Very Low** | Very little confidence. The conclusion is highly uncertain. |

### Downgrade Domains (each can reduce certainty by one level)

1. **Risk of Bias**: Are sources predominantly biased in one direction?
   Vendor-authored, sponsored, or ideologically driven sources lower certainty.

2. **Inconsistency**: Do sources disagree? If 60% of sources say X and 40% say Y,
   certainty is lower than if 95% agree.

3. **Indirectness**: Does the evidence directly address our question? Evidence about
   a related but different population, technology, or time period is indirect.

4. **Imprecision**: Are the data points precise? Wide ranges, small samples, and
   vague claims reduce certainty.

5. **Publication Bias**: Is there reason to believe negative or null findings are
   missing? If all sources are positive, suspect publication bias.

### Upgrade Domains (each can raise certainty by one level)

1. **Large Effect**: If the finding is dramatic and consistent (e.g., 10x improvement),
   it is less likely to be an artifact.

2. **Dose-Response**: If more of X leads to proportionally more of Y, the causal
   link is stronger.

3. **Confounding in Opposite Direction**: If plausible confounders would bias
   results AGAINST the finding, yet the finding persists, confidence increases.

### Application

Start at "High" certainty. Apply downgrade checks. Apply upgrade checks.
Document the final rating with rationale for each adjustment.

---

## 9. Cross-Checking Rules

**Purpose:** Ensure major claims are independently verified and contradictions are
resolved transparently.

**When used:** Phase 5 (Triangulate), by the evidence-analyst agent.

### Rule 1: 3+ Independent Sources Per Major Claim

Every claim that supports a report finding must have at least 3 independent sources.
"Independent" means:
- Not citing each other
- Not from the same organization
- Not derived from the same underlying dataset

If a claim has < 3 sources, it must be:
- Flagged as "uncorroborated" in claims.json
- Labeled in the report with reduced confidence
- Targeted for additional searching in Wave 4

### Rule 2: Source Independence Assessment

Before counting sources as independent, check:
- Do Source A and Source B cite the same original study? → They are not independent.
- Are Source A and Source B from the same company/organization? → Not independent.
- Did Source B copy from Source A? → Not independent.
- Is there a single "original source" that all others trace back to? → Only count once.

### Rule 3: Contradiction Resolution Protocol

When two sources make contradictory claims:

1. **Document the contradiction** in claims.json (contradicting_source_ids field)
2. **Assess source quality**: Higher Admiralty rating wins, all else being equal
3. **Check recency**: More recent data may supersede older data
4. **Check methodology**: Primary data > secondary analysis > opinion
5. **Check specificity**: Specific quantitative claim > vague qualitative claim
6. **If unresolvable**: Present both positions in the report, state which has
   stronger evidence, and flag in the Counterevidence Register

---

## 10. "So What?" Test (BCG)

**Purpose:** Filter findings to ensure every included item has clear implications
for the reader. Cut anything that is merely interesting but not actionable or insightful.

**When used:** Phase 7 (Synthesize), by the orchestrator.

### The Three Questions

For each finding, answer in sequence:

**What?** — State the finding as a fact.
"Quantum error rates improved 10x in 2025."

**So What?** — Explain why this matters.
"This brings practical quantum computing closer to the 2028 threshold theorem requirement."

**Now What?** — State the implication or action.
"Organizations should begin quantum-readiness assessments now rather than waiting for
proven practical advantage."

### Application Rules

- If you cannot answer "So What?" convincingly → **cut the finding** from the main
  report. It can go in an appendix.
- If you cannot answer "Now What?" → the finding is informational but not actionable.
  Include it only if it provides necessary context for other findings.
- Every finding that survives the test should have a clear "So What?" and ideally
  a "Now What?" embedded in its discussion paragraph.

---

## 11. Pyramid Principle (Minto)

**Purpose:** Structure the report so the reader gets the answer first, then
supporting arguments, then evidence. Readers who stop early still get the key message.

**When used:** Phase 10 (Package), by the orchestrator during report generation.

**Source:** Barbara Minto, "The Pyramid Principle" (McKinsey).

### Structure

```
Level 1: THE ANSWER (Executive Summary)
   Lead with the conclusion. One clear sentence.

Level 2: SUPPORTING ARGUMENTS (Findings)
   3-5 key arguments that support the answer.
   Each argument is a finding section.
   Arguments should be MECE (mutually exclusive, collectively exhaustive).

Level 3: EVIDENCE (Within each finding)
   Data, citations, analysis that support each argument.
   Organized logically: deductive (rule → case → result)
   or inductive (cases → pattern → rule).
```

### SCQA Framing (for Introduction)

| Element | Purpose | Example |
|---------|---------|---------|
| **Situation** | Establish shared context | "Quantum computing has received $50B+ in investment since 2020." |
| **Complication** | Introduce the tension/problem | "Despite this investment, no commercially viable quantum advantage has been demonstrated." |
| **Question** | State what the report answers | "When and how will quantum computing achieve practical advantage?" |
| **Answer** | Preview the conclusion | "Our analysis of 500+ sources suggests 2028-2030, driven primarily by error correction advances, with 3 critical assumptions that could delay it." |

### Practical Rules

1. **Lead with the answer.** The first paragraph of the Executive Summary should
   contain the conclusion. Do not build up to it.

2. **Each finding section starts with its conclusion.** The first sentence of each
   finding should state what was found. Supporting evidence follows.

3. **Group arguments MECE.** The findings should cover the question exhaustively
   without overlapping. This maps naturally to the MECE decomposition from Phase 1.

4. **Use deductive order for strong evidence.** Rule → Case → Result.
   "Error correction theory requires 10^-6 error rates [rule]. Google achieved
   10^-6.2 in Q3 2025 [case]. Therefore, the theoretical threshold is met [result]."

5. **Use inductive order for pattern discovery.** Case → Case → Case → Pattern.
   "IBM reported 15% cost reduction. Google reported 22%. Microsoft reported 18%.
   The industry trend is consistent double-digit cost improvement."
