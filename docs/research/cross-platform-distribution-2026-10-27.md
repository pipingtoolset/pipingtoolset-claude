# PipingToolset beyond Claude: cross-platform distribution report

Prepared 2026-10-27 by Kai (orchestrator) from three parallel research agents (OpenAI surfaces; other agent hosts and the Agent Skills standard; directories and competition), with the key claims re-verified against the source pages and the plugin's own files. Anything marked UNVERIFIED was not confirmed against a primary source.

## 1. Executive summary

1. **A universal PipingToolset plugin is feasible today, and it is almost the package you already ship.** The five skills are folders of `SKILL.md` + `references/` + standard-library Python, which is the Agent Skills open standard (agentskills.io). OpenAI Codex, ChatGPT, GitHub Copilot, Cursor, Gemini CLI / Antigravity, Windsurf, Cline, Roo, Kilo, Kiro (ex Amazon Q), JetBrains Junie, Goose, OpenCode, Factory Droid, Zed, Warp, Devin, Manus, Perplexity Computer and Mistral Vibe all read that format. Verified against each host's own docs (section 4).
2. **The five SKILL.md files already pass the spec.** Checked today: frontmatter is `name` and `description` only, every `name` matches its folder, descriptions are 371 to 401 characters (limit 1,024), bodies are 104 to 237 lines (recommendation 500), and every script is referenced by a skill-relative path. No `${CLAUDE_PLUGIN_ROOT}` or Claude-only tool names appear in any skill. Porting effort for the skill content is zero.
3. **What changes is packaging and distribution, not content.** Add a root `plugin.json` (the Agent Plugins 1.0 shape that OpenAI, Cursor, Copilot and Vercel back), an `.agents/plugins/marketplace.json` for Codex, keep `.claude-plugin/` for Claude, and publish `.zip` builds for the hosts that take uploads (ChatGPT, Manus, Perplexity).
4. **MCP is the wrong primary vehicle.** Wrapping the scripts as an MCP server would reach a few tool-only hosts but loses the interview, the refusal rules and the progressive disclosure that make the pack defensible in review. Ship it later, if at all, as a fallback.
5. **One blocker precedes everything: the GitHub repository is private.** Verified today with `gh repo view` (visibility PRIVATE) and an anonymous fetch (HTTP 404). Every directory, every installer (`npx skills add`, `gh skill install`) and the download links on the draft /claude/ page need a public repository.
6. **The mcpmarket.com "piping-stress-analysis" listing is not a real competitor.** It is an auto-scraped page for a prose-only stub inside an unrelated agent-orchestration monorepo (a5c-ai/babysitter) that embeds unsourced SIF values and span tables. It does hold the keyword on that site, which is a reason to list there.

## 2. Is a universal plugin feasible? Yes, in three layers

| Layer | Standard | Who reads it | What you do |
|---|---|---|---|
| Skill content | Agent Skills (`SKILL.md`, `scripts/`, `references/`) | Every host in section 4 | Nothing. Already compliant. |
| Package | Agent Plugins 1.0: root `plugin.json`, `skills/`, optional `mcp.json` (agent-plugins.org; TSC: Amazon, Cursor, Microsoft, OpenAI, Vercel) | OpenAI (Codex + ChatGPT Plugin Directory), Cursor marketplace, Copilot CLI plugins | Add one `plugin.json` at the plugin root with `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`. Keep `.claude-plugin/plugin.json` beside it. |
| Catalog | `.agents/plugins/marketplace.json` (OpenAI) and `.claude-plugin/marketplace.json` (Anthropic). OpenAI's desktop app also reads the Claude one as a "legacy-compatible marketplace" (verified on developers.openai.com/codex/plugins/build). | Codex desktop/CLI, Claude Code, Cowork | Add the OpenAI catalog file pointing at the same `plugins/piping-toolset` folder. |

Three host-specific facts limit "universal":

- **Script execution is local.** Codex CLI, Claude Code, Cursor, Copilot CLI and the other terminal agents run `scripts/*.py` with the user's Python. Cowork provides Python in its sandbox. ChatGPT web, Manus and Perplexity Computer accept skill uploads, but whether they execute bundled Python is UNVERIFIED for all three. The ChatGPT desktop app and Codex cloud are documented as running skills; test one upload before promising it.
- **Hosts ignore unknown frontmatter.** Keep the universal copy to `name`, `description` and the optional `license`, `compatibility`, `metadata`. Do not add Claude-only fields.
- **Each host has its own install path.** The universal convention is `.agents/skills/` (project) and `~/.agents/skills/` (user); Copilot, Cursor, Windsurf, Cline, Kilo, Goose, OpenCode and Warp also read `.claude/skills/`. Installers handle this (section 5).

## 3. OpenAI specifically (Codex and ChatGPT)

Verified today on learn.chatgpt.com/docs/build-skills and developers.openai.com/codex/plugins/build.

| Claude Code plugin feature | OpenAI equivalent | Effort |
|---|---|---|
| `SKILL.md` folders | Same standard. Discovered in `.agents/skills` (walks up to repo root), `$HOME/.agents/skills`, `/etc/codex/skills`. OpenAI's page links agentskills.io. | None |
| `references/`, `scripts/` | Same. OpenAI: "prefer instructions over scripts unless you need deterministic behavior", which is exactly this pack's case. | None |
| `/piping-toolset:pressure-design` | `$pressure-design` or `/skills` in Codex CLI and IDE; `@` in ChatGPT; implicit invocation by description everywhere | Rewrite the "how to invoke" paragraph in README |
| `.claude-plugin/plugin.json` | Root `plugin.json` (portable) or `.codex-plugin/plugin.json` (compatibility fallback) | Add one file |
| `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json`; the Claude file is also read as legacy-compatible | Add one file |
| `/plugin marketplace add owner/repo` | `codex plugin marketplace add owner/repo`, install from the ChatGPT desktop app's Plugins view | Document |
| Cowork drag-and-drop `.plugin` | ChatGPT Plugin Directory: skills-only ZIP upload, automated metadata and skill checks, policy attestations, emailed review result; organization verification required; review time UNVERIFIED | Package a ZIP and submit |

Surfaces, as documented: standalone skills work in the ChatGPT desktop app, Codex CLI and the IDE extension; skills bundled in plugins also work in ChatGPT Chat and Work on web, desktop and mobile. OpenAI's plugin page does not mention the IDE extension for plugins; the research agent's source for "IDE extension does not support plugins" was learn.chatgpt.com/docs/plugins (not re-fetched, treat as likely).

Do not build a Custom GPT. OpenAI announced the retirement of custom GPTs on 2026-09-11 (Enterprise GPTs stop running 2026-12-11 per a secondary source; OpenAI's FAQ returned 403). GPT instructions migrate into plugin skills; Actions do not. The Apps SDK (MCP-based, now folded into plugins) is a hosted-server design that contradicts the no-network promise; skip it.

MCP in OpenAI products: Codex supports stdio and streamable HTTP servers; ChatGPT web supports remote MCP only, through plugins or developer mode. Not needed for this pack.

## 4. Host support matrix (condensed)

Y = documented in the host's own docs. Full per-host paths and links are in the research agent's matrix; the essentials:

| Host | SKILL.md | Reads `.agents/skills` | Also reads `.claude/skills` | Runs bundled scripts | Note |
|---|---|---|---|---|---|
| OpenAI Codex / ChatGPT desktop | Y | Y | not documented | Y (CLI, desktop) | Plugin Directory for ChatGPT web |
| GitHub Copilot (CLI, VS Code, cloud agent) | Y | Y | Y | Y (CLI docs) | Also `.github/skills` |
| Cursor | Y | Y | Y | Y | Marketplace needs public repo, manual review |
| Gemini CLI / Google Antigravity | Y | Y | no | Y (Antigravity docs) | Gemini CLI replaced by Antigravity CLI 2026-06-18 for free users |
| Windsurf (now Devin Desktop) | Y | Y | if enabled | allowed | |
| Cline | Y | not listed | Y | Y | |
| Roo Code | Y | Y | no | allowed | |
| Kilo Code | Y | Y | if enabled | Y (trusted) | |
| Kiro (Amazon Q successor) | Y | no (`.kiro/skills`) | no | Y | Q Developer IDE plugins end of support 2027-04-30 (secondary source) |
| JetBrains Junie | Y | Y (trusted) | no | Y | |
| Goose (Block) | Y | Y | Y | files accessible | |
| OpenCode | Y | Y | Y | not stated | |
| Factory Droid | Y | Y | no | Y | |
| Zed | Y | Y | no | allowed | |
| Warp | Y | Y | Y | Y | |
| Devin CLI | Y | Y | no | not stated | |
| Manus | Y (zip upload) | n/a | n/a | UNVERIFIED | |
| Perplexity Computer | Y (zip upload, 10 MB) | n/a | n/a | UNVERIFIED | |
| Mistral Vibe | Y | Y | no | not stated | |

Every host above also supports MCP servers (stdio and remote) except where the agent could not verify (Kilo, Manus, Perplexity, Antigravity).

## 5. Installers that make one repo reach every host

- **`npx skills add pipingtoolset/pipingtoolset-claude`** (Vercel, launched 2026-01-20, Node 22.20+). Detects skills in the repo root, `skills/`, agent folders and `.claude-plugin/plugin.json` or `marketplace.json`, and installs into about 70 agents' paths. No submission step: skills.sh's leaderboard is built from the installer's anonymous telemetry, so the listing appears once people install.
- **`gh skill install pipingtoolset/pipingtoolset-claude`** (GitHub CLI 2.90+, public preview since 2026-04-16). Targets Copilot, Claude Code, Cursor, Codex, Gemini CLI and Antigravity. `gh skill publish` validates against the agentskills.io spec and cuts a release.
- Both need the repo public. Add the `agent-skills` topic on GitHub (secondary source for the topic convention).

## 6. MCP as a universal vehicle: gain versus loss

Gain: one Python artifact (FastMCP over stdio, the existing scripts imported as typed tools), works in hosts that have MCP but no skills, typed JSON schemas instead of "write JSON, run script", remote HTTP for cloud hosts.

Lose: the interview layer (what to ask first, when to mark ASSUMED), the refusal rule (no table values) which would have to live in tool descriptions the model weighs less, progressive disclosure (`references/` become resources that hosts may never surface; only VS Code, Cursor, Gemini CLI, Windsurf, Kiro, Devin CLI, Zed and Roo document prompts or resources at all), setup friction (editing JSON/TOML config plus Python and `uv`), a larger security surface than a folder of text, and MCP spec churn (current revision 2026-07-28).

Recommendation: skills first. If an MCP server is built later, duplicate each SKILL.md body into the server's instructions and expose one prompt per skill; publish it to the Official MCP Registry under `io.github.pipingtoolset/...` so GitHub's registry and PulseMCP (submissions currently paused) pick it up.

## 7. Where to list, in order

| Priority | Directory | Accepts | Route | Cost | Why |
|---|---|---|---|---|---|
| 1 | Anthropic plugin directory (claude.ai/directory/manage, claude-plugins-official) | Plugin bundles, skills folders | Developer portal, public GitHub repo, automated validation + security scan, reviewer hold | None found | Highest trust; covers Cowork, claude.ai and Claude Code. Pre-checks: LICENSE present (Apache-2.0 ok), README ≥ 40 words (ok), no non-image binary over 256 KiB, `name` not matching a known brand (check CAESAR II / AutoPIPE in display text), at least three example prompts (PROMPTS.md has ten) |
| 2 | OpenAI Plugin Directory (ChatGPT + Codex) | Skills-only ZIP | Upload, automated checks, attestations, emailed review | None stated | The second-largest audience of engineers using an assistant; one review per update |
| 3 | skills.sh (Vercel) | Skills | None; add the install command to the README | Free | Zero effort once public; reaches Claude Code, Cursor and Codex users |
| 4 | mcpmarket.com | Agent Skills and MCP servers | mcpmarket.com/submit with the GitHub URL | $29 one-time (24 h, "Official" badge) or free queue (4 to 6 weeks) | Displaces the a5c-ai stub on the piping keyword; terms include an indemnity clause (§12), read before paying |
| 5 | Cursor marketplace | Plugins (skills, MCP, rules) | cursor.com/marketplace/publish; public repo with root `plugin.json`; manual review including publisher legitimacy | Free | Large paying developer base; use the LLC identity |
| 6 | Low-effort batch: ClawHub (`clawhub skill publish`), mcp.so (/submit), agentskill.sh (/submit, process UNVERIFIED) | Skills | Repo URL or one command | Free | Volume listings; ClawHub has the largest skills base |
| Hold | awesome-claude-skills, awesome-agent-skills (VoltAgent requires real community usage), GitHub MCP registry, Glama, PulseMCP, Cline marketplace | Lists / MCP only | PR or MCP publish | Free | Either need usage first or need an MCP server |

Not researched: Composio's platform, Product Hunt launches, LobeHub's submission route.

## 8. The mcpmarket.com piping-stress-analysis listing

- Publisher shown as a5c-ai, unclaimed ("Claim this listing"), linking to github.com/a5c-ai/babysitter (MIT, about 1.9k stars, an agent-orchestration monorepo).
- The listing wraps one file: `library/specializations/domains/science/mechanical-engineering/skills/piping-stress/SKILL.md`, about 6.8 KB of prose. No scripts, no references, no tests. CAESAR II, AutoPIPE and STAAD appear as metadata tags only.
- It is one of about 28 near-identical stubs produced by bulk commits ("annotate remaining ~2800 library files"). A sibling pressure-vessel stub is also listed.
- Content: B31.3 stress equations, thermal expansion coefficients, "common SIF values", a B31.1 support-span table and a P_eq flange formula, all without an edition stamp or provenance, and no refusal path. That is the opposite of this pack's rules 1 and 2.
- Star counts on the listing (1,328) are a stale snapshot of the monorepo, not the skill.
- Verdict: an aggregator artifact, not a competitor in quality, but the current holder of the "piping stress" keyword on that site and on agentskill.sh. A code-faithful listing with the "no embedded code values" statement in its first line is the counter.

Other competition found: a handful of one-star hobby repos (a B31.3 wall-thickness web app, an ASME VIII/API 650 Python engine, a CCPP calc MCP server) and nothing for CAESAR II load cases, isometric-to-PCF or pipe support checks. Treat as search-limited, but the niche looks open.

## 9. Recommended plan

Phase 0, before anything public (this week):
1. Decide the repository visibility question. Public is required for every route above; the roadmap's "squash history before first public push" item is the gating task.
2. Pull the stale main checkout (`C:\dev\projects\pipingtoolset-claude` is on an old `main` at 0.1.0 with three skills; the worktrees are current).

Phase 1, packaging (one day of work, no skill content changes):
1. Add root `plugins/piping-toolset/plugin.json` in the Agent Plugins shape; keep `.claude-plugin/plugin.json`.
2. Add `.agents/plugins/marketplace.json` for Codex.
3. Extend `tools/package_plugin.py` to also emit `piping-toolset-skills.zip` (skills only) for ChatGPT, Manus and Perplexity uploads.
4. Add `compatibility: Requires Python 3.9+` to each SKILL.md frontmatter (spec-legal, host-neutral).
5. README: an "Other assistants" section with `npx skills add`, `gh skill install`, `codex plugin marketplace add`, and the install-path table.
6. CI: run `skills-ref validate` on each skill folder.

Phase 2, verification (half a day each):
1. Codex CLI: run E1, E2, E9 from PROMPTS.md. Pass criteria unchanged.
2. ChatGPT desktop app: upload the ZIP, run E1 and E2; this answers the script-execution question for ChatGPT.
3. Cursor and Copilot CLI: run E1 and E2.
4. Record results in a `tests/e2e/HOSTS.md` sibling of the Cowork checklist.

Phase 3, listings in the order of section 7. Each listing's text leads with the three rules and the "nothing you enter reaches PipingToolset" line; the /claude/ page becomes the canonical landing page for every host, so consider retitling it "PipingToolset for AI assistants" with a Claude section first.

Phase 4, optional: MCP server as a fallback, published to the Official MCP Registry.

## 10. What was not verified

- Script execution in ChatGPT web, Manus and Perplexity Computer.
- OpenAI Plugin Directory review time and plan eligibility for ChatGPT skills.
- Whether Codex reads `.claude-plugin/plugin.json` (the marketplace file is documented; the plugin manifest is not).
- Cursor's handling of the `plugins/piping-toolset/.claude-plugin/` layout without a root `plugin.json`.
- Anthropic directory plan-tier requirement (third-party guides only).
- The Agent Skills spec publication date; Agent Plugins 1.0 date (2026-08-06 per secondary sources).
- Whether any other piping skill exists on mcpmarket.com (its skills search ignores the query).

## Sources (primary, re-fetched today marked *)

- agentskills.io/specification *
- learn.chatgpt.com/docs/build-skills *
- developers.openai.com/codex/plugins/build *
- learn.chatgpt.com/docs/plugins; learn.chatgpt.com/docs/extend/mcp; developers.openai.com/apps-sdk/deploy/submission; github.com/openai/plugins; github.com/openai/codex/pull/28789
- agent-plugins.org; github.com/vercel-labs/skills; skills.sh/docs/cli; github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli
- Host docs: docs.github.com (Copilot agent skills, CLI add-skills, CLI plugins), cursor.com/docs/context/skills and /docs/plugins, geminicli.com/docs/cli/skills, antigravity.google/docs/skills, docs.devin.ai (desktop skills, CLI skills), docs.cline.bot/customization/skills, roocodeinc.github.io (skills), kilo.ai/docs/customize/skills, kiro.dev/docs/skills and /docs/cli/migrating-from-q, junie.jetbrains.com/docs/agent-skills.html, goose-docs.ai (using-skills), opencode.ai/docs/skills, docs.factory.com/cli/configuration/skills, zed.dev/docs/ai/skills, docs.warp.dev (skills), manus.im/docs/features/skills, perplexity.ai help center 13914413, docs.mistral.ai/vibe/code/cli/skills
- modelcontextprotocol.io/specification/2026-07-28 (transports, prompts, resources); modelcontextprotocol.io/registry/quickstart
- Directories: claude.com/docs/plugins/submit and pre-submission-checklist; support.claude.com article 13145358; github.com/anthropics/claude-plugins-official; mcpmarket.com (/submit, /sell, /terms, /tools/skills/piping-stress-analysis); raw.githubusercontent.com/a5c-ai/babysitter/main/library/specializations/domains/science/mechanical-engineering/skills/piping-stress/SKILL.md; cursor.com/marketplace/publish; smithery.ai/docs; glama.ai; pulsemcp.com/submit; github.com/cline/mcp-marketplace; github.com/openclaw/clawhub; mcp.so/submit; agentskill.sh; github.com/ComposioHQ/awesome-claude-skills; github.com/VoltAgent/awesome-agent-skills
- Repository visibility: `gh repo view pipingtoolset/pipingtoolset-claude` (PRIVATE, latest release v0.4.0 2026-10-27T02:30Z) *
