# Using `lead-ops` in Claude Cowork

Claude Cowork is Anthropic's desktop agent for knowledge work — it runs in the Claude Desktop app, alongside the Claude.ai web tab, and supports plugins on all paid plans (Pro, Max, Team, Enterprise). It uses the same agentic architecture as Claude Code, so `lead-ops` works the same end-to-end: the same three skills, the same nine agents, the same evidence-first guarantees. The differences are install flow, surface, and a few platform-specific caveats below.

## 1. Install the plugin

**As an individual user** (Pro, Max, personal Team seat):

1. Open Claude Desktop and switch to the **Cowork** tab.
2. Click **Customize** in the left sidebar.
3. Click **Browse plugins**.
4. Search for the marketplace `strange-loop-syndicate/plugins` (or add it via the marketplace add flow if not listed) and click **Install** on **lead-ops**.

Plugins you install yourself are saved locally to your machine.

**As a Team or Enterprise owner**, to make `lead-ops` available org-wide:

1. Open **Organization Settings → Plugins**.
2. Click **Add plugin** and choose **GitHub** as the source.
3. Enter `strange-loop-syndicate/plugins` in `owner/repo` format.
4. Pick the install policy: required, installed by default, available, or hidden. Restrict by group on Enterprise plans if needed.

Members cannot edit organization-managed plugins, which prevents conflicting changes to shared tooling.

## 2. Set up a project

Cowork doesn't have a per-project working directory the way Claude Code does — instead each Cowork conversation is a long-running task with its own context. For `lead-ops`, choose a stable folder on your machine that will hold the project artifacts (`lead-ops.config.yaml`, `leads.json`, `pipeline/`, `exports/`). Tell Cowork where it is at the start of the conversation:

> Use `~/work/my-leads/` as the project directory for this lead-ops session.

Cowork operates on local files via its filesystem tools, so the directory must be on the same machine as Claude Desktop.

## 3. Invoke skills

In Cowork, slash commands are surfaced as **Skills** in the `/` menu (or `+` button). After install, three lead-ops skills appear:

- **lead-ops: plan** — scoping and pipeline design
- **lead-ops: build** — data pipeline
- **lead-ops: execute** — outreach drafting and status

Type `/` or click `+`, pick the skill, and answer the clarifying questions in plain English. There is no separate command line; the conversation is the interface.

A typical session looks like this:

> **You:** `/lead-ops:plan`
>
> **Claude:** Walks through ICE-style scoping questions one at a time, proposes source modules and schema, writes `lead-ops.config.yaml` and `lead-ops-plan.md` into the project directory, and stops for your review.
>
> **You:** *(open `lead-ops-plan.md` in Cowork's file viewer, tweak `lead-ops.config.yaml` directly if needed)* "Looks good, let's build."
>
> **You:** `/lead-ops:build`
>
> **Claude:** Runs discover → enrich → score → audit → export with a mandatory review stop between each phase. At each judgment step you see a structured table of the latest batch and decide whether to approve, correct, or stop.
>
> **You:** `/lead-ops:execute --priority A --channel linkedin_connection_note`
>
> **Claude:** Drafts per-lead LinkedIn notes referencing specific evidence; writes them as a copy-paste-ready markdown file under `exports/outreach/`.

## 4. Customize for your workflow

Cowork has a dedicated **Customize** button (top right of the plugin page) that opens a Cowork task where Claude adjusts plugin behavior to match your specific workflow. Useful tweaks for `lead-ops`:

- Replace the default audit checkpoint cadence in `lead-ops.config.yaml` (e.g. 10 instead of 20 for small projects, 30 for large ones).
- Add an organization-specific outreach channel template under `${PROJECT}/lead-ops.config.yaml > outreach.channels[].template_overrides`.
- Wire in connectors you already have in Cowork (Google Drive, Gmail, Slack, etc.) via MCP for evidence pulls and outreach delivery prep.

## 5. Connectors and MCP

Cowork's strength on top of Claude Code is built-in connectors for knowledge-work tools. `lead-ops` plays well with:

- **Google Drive / Gmail** — drop an external contact CSV into Drive, reference its Drive URL as an `external_data` source; have Cowork pull it locally before `/lead-ops:build` runs the cross-reference phase.
- **Slack** — at outreach time, ask Cowork to post the strategy doc to a Slack channel for team review before you send any drafts.
- **Calendar** — ask Cowork to block a working session for the review pass between build phases (audit checkpoints take real time).

The plugin itself does not require any MCP server, but it benefits from the ones your org has already wired up.

## 6. Differences vs Claude Code

| | Cowork | Claude Code |
|---|---|---|
| Where it runs | Claude Desktop, Cowork tab | Terminal (CLI), VS Code, JetBrains, Claude.ai |
| Surface | Skills menu (`/` or `+`), conversation UI | Slash commands in the terminal prompt |
| Project state | A folder on your machine you tell Cowork to use | The current working directory the CLI is invoked in |
| Plugin install | Browse plugins UI, or org-managed via Settings | `/plugin marketplace add` + `/plugin install` |
| Customization | "Customize" button opens a Cowork task | Edit files / settings directly |
| Sub-agents | Same agentic architecture, surfaced as plugin agents in `/agents` | Same |

The pipeline behavior, agent contracts, audit checkpoints, evidence guarantees, and outputs are identical across both. The same `lead-ops.config.yaml` and `leads.json` produced in Cowork can be opened in Claude Code and vice versa.

## 7. Caveats specific to Cowork

- **Browser-driven enrichment** (LinkedIn, Twitter) requires a logged-in browser session via the `/browser` skill. In Cowork this currently means the social-enricher phase runs on the same machine that has Chrome + the user's session cookies. If your Cowork is on a different machine than your browser session, plan ahead — either run the social-enrichment phase on the machine that has the cookies (via Claude Code) and bring the enriched `leads.json` back, or set `social_channels: []` and skip the phase.
- **Long-running phases** — discovery against PubMed for hundreds of seeds, or social enrichment over 500+ leads, can run for many minutes. Cowork keeps the conversation alive while a task runs in the background; you'll get a notification when it pauses for the next audit checkpoint.
- **Organization plugins are read-only for members.** If your org pinned `lead-ops` and you want to modify the plugin itself (not just your project config), do it in a fork and have an admin update the org pin.

## 8. Recommended first session

Pick a small, well-bounded target audience for your first project so you can complete the full plan → build → execute loop in one sitting. Good starter cases:

- 30–50 conference speakers from a single 2-day event in your domain
- The 20 most-cited authors on a specific topic in PubMed over the last three years
- All Series-B SaaS founders in a single sub-vertical announced in the last 6 months

Run the loop end-to-end on this small set. You'll feel the audit cadence, see the evidence store fill up, hit (and correct) a few wrong-profile candidates during social enrichment, and produce 20–30 ready-to-send outreach drafts. Then scale up the source params for a real run.
