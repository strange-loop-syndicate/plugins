# Strange Loop Syndicate — Claude Plugins

Open plugin marketplace for Claude Code and Claude Cowork.

## Plugins

| Plugin | What it does |
|---|---|
| [`deep-research`](plugins/deep-research/) | World-class deep research with 500+ sources, ACH hypothesis testing, Admiralty Code source ratings, and structured evidence management. Spawns a research team or delegates to an autonomous background agent. |
| [`lead-ops`](plugins/lead-ops/) | Evidence-first, domain-agnostic lead research and outreach pipeline. Scope → build (discover/enrich/score/audit/export) → execute (outreach). Pluggable source modules, working surfaces, and outreach channels. Mandatory audit checkpoints; every claim ties to a fetched, verifiable URL. |

## Installation

### Claude Code

Add the marketplace once, then install plugins by name:

```
/plugin marketplace add strange-loop-syndicate/plugins
/plugin install deep-research
/plugin install lead-ops
```

After install, invoke each plugin's skills as `/deep-research:...` or `/lead-ops:plan`, `/lead-ops:build`, `/lead-ops:execute`.

### Claude Cowork

**Individual users** (Pro / Max / personal Team seat): open Claude Desktop → Cowork tab → **Customize** in the left sidebar → **Browse plugins** → install from the `strange-loop-syndicate/plugins` marketplace. Plugins install locally to your machine.

**Team / Enterprise owners**: add the marketplace org-wide via **Organization Settings → Plugins → Add plugin → GitHub** with source `strange-loop-syndicate/plugins`. Set the install policy per plugin (required / default / available / hidden).

After install, plugins surface as Skills in the `/` menu (or `+` button) inside any Cowork conversation.

See [`plugins/lead-ops/docs/USING-IN-CLAUDE-COWORK.md`](plugins/lead-ops/docs/USING-IN-CLAUDE-COWORK.md) for a detailed Cowork walkthrough.

## License

Per-plugin. Both plugins in this marketplace are MIT-licensed; see each plugin directory.

## Maintained by

[Oleg Ovsyannikov](https://github.com/olegovsyannikov) (`@oovsyannikov`).
