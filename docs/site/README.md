# pipingtoolset.com drafts for the plugin launch (2026-10-27)

**2026-10-28, 0.7.0 (optional Engineering Data connector):** `claude-page.html` is rewritten and
`openai-page.html` is new; both are generated from one set of fragments so the two pages agree. They
replace the 0.4.0 and 0.6.0 copy. What changed in the copy:

- "Nothing you enter reaches PipingToolset" is gone. The true statement is that the skills and their
  scripts make no network calls, carry no telemetry and need no account, and that the optional
  connector, if enabled, sends only lookup keys (standard, material or table row, temperature,
  size).
- A new section describes the connector: what it serves with no account and with a signed-in paid
  account (Pro, Pro Plus, Ultimate) at the site's tier, what stays pointer-only, the lookup envelope,
  sign-in, and how to add or remove it per host. Tier and source statements say "currently".
- "What it will not do" now says the plugin's own files hold no tabulated value, and that a looked-up
  value is still the user's to verify. The line saying a subscription changes nothing and that
  installing unlocks nothing is replaced by "the plugin is free and works without the connector".
- Seven skills everywhere, version 0.7.0, no "same engine" or "licensed piping engineer" wording
  (board rules of 2026-10-28), and the OpenAI page no longer says a directory listing is pending
  (OpenAI does not take skill-only plugins; the install routes are the marketplace and Agent Skills).

**Production is in pipecalcpro, not here:** port the two bodies into
`scripts/seo/claude-content.mjs` and `scripts/seo/openai-content.mjs` (bump `PLUGIN.version` to
0.7.0 and `reviewed` to 2026-10-28, update `metaDescription` and `summary`, and the llms.txt line).
The `SKILLS` array there already has seven rows; only the nozzle-load row's second cell changed
here ("every table row is cited, from your copy or from a connector lookup").

**2026-10-28, 0.6.0:** the site gained a sibling page, `https://pipingtoolset.com/openai/`
(`scripts/seo/openai-content.mjs` + `openaiPage()` in `build-pages.mjs`, OG image `openai`, an
`## AI assistant plugin` section in llms.txt), a fourth hero button **For OpenAI**, and the
launcher tier retitled **PipingToolset for AI** with tiles *Install in Claude Cowork / Code* and
*Install in ChatGPT / Codex*. The `/openai/` URL is the `websiteURL` in the plugin's OpenAI
listing block, so it must resolve before the directory submission. The drafts below predate it.

Two drafts for the pipecalcpro site (`C:\dev\projects\pipecalcpro`). **Wired into the site on 2026-10-27** (pipecalcpro PR 145): `scripts/seo/claude-content.mjs` + `claudePage()` in `build-pages.mjs` produce `/claude/`; the homepage launcher tier, hero CTA, footer group and llms.txt section are in. These drafts are the design record; the live copy says seven skills and v0.5.0 where the drafts still say five and v0.4.0.

| File | What it is | Where it lands in pipecalcpro |
|---|---|---|
| `claude-page.html` | Full draft of `https://pipingtoolset.com/claude/` in the trust-page chrome, previewable as is | Body becomes `scripts/seo/claude-content.mjs`; `build-pages.mjs` writes `apps/web/public/claude/index.html` |
| `homepage-draft.html` | Homepage mock with the new "PipingToolset for Claude" launcher category, hero button and footer links (additions outlined) | `apps/web/index.html` (static shell + footer) and `apps/web/src/App.tsx` (launcher tier) |

## Repository visibility

Public since 2026-10-27 (`gh repo view --json visibility` → PUBLIC; anonymous fetch of the repo, the latest release and the raw marketplace.json all return 200). Every download and install link on the live page resolves.

## llms.txt entry

`build-pages.mjs` generates `llms.txt` from page metadata, so the line is produced, not pasted. Add a section between `## Tools` and `## Guides`:

```
## Claude plugin

- [PipingToolset for Claude — B31 Piping Skills for Claude Code and Cowork](https://pipingtoolset.com/claude/): Seven ASME B31.3 / B31.1 skills for Claude Code and Cowork. Claude runs the interview, a script does the math, no code table values are embedded in the plugin, and an optional connector serves cited table values to signed-in paid accounts.
```

If the cross-platform plan goes ahead, retitle the section `## AI assistant plugin` and the page "PipingToolset for AI assistants", with Claude first.

## Build integration (pipecalcpro)

1. `scripts/seo/claude-content.mjs`: export `{ title, metaDescription, reviewed, body }` like `trust-content.mjs`. Body = everything inside `<main>` of `claude-page.html` after the breadcrumb and H1.
2. `scripts/seo/build-pages.mjs`: a `claudePage()` builder that writes `claude/index.html` with the shared chrome, pushes `{ title, metaDescription, path: "/claude/" }` into a new `CLAUDE_META` constant, and adds it to `sitemap.xml`, `llmsTxt()` (new section above) and `llmsFullTxt()`. Breadcrumb: Home › PipingToolset for Claude. JSON-LD: the `SoftwareApplication` block in the draft, plus `BreadcrumbList`.
3. OG image: `scripts/seo/og-images.mjs` needs a `claude` entry; the draft references `/brand/og/claude.png`.
4. Footer links: `apps/web/index.html` footer "Browse" nav gets `For Claude`, and the Trust column gets a `For AI assistants` group with `PipingToolset for Claude`, `Plugin source (GitHub)`, `llms.txt`. The e2e smoke test asserts every footer href resolves, so add the page in the same commit.
5. Generated-page footers: the `Browse` column template in `build-pages.mjs` gets the same `/claude/` link.
6. Netlify: `/claude/index.html` is served as a directory index like `/calculators/`; no redirect needed. `pretty_urls = false` and no SPA catch-all stay as they are.
7. Stamp: `reviewed: "2026-10-27"`; bump the version line (`0.7.0 · released 2026-10-28`) on each plugin release, or read it from the GitHub Releases API at build time.

## Homepage changes shown in the mock

1. Hero CTA row: a third button `For Claude` after `Pricing`, linking to `/claude/`.
2. Hero sub-paragraph: one sentence noting the engine now runs inside Claude Code and Cowork as a free plugin.
3. Launcher: a new tier `PipingToolset for Claude — free · open source · Apache-2.0` placed after the two free tiers and before Pro Tools, with three tiles (Install in Cowork, Install in Claude Code, What it does / will not do / where data goes) and a version pill. In `App.tsx` this is a hand-written block like Report Manager, with `<a href="/claude/">` tiles rather than hash-route buttons so crawlers follow it. Mirror the three titles in the pre-hydration `.shell-apps` catalog in `index.html`, since the build asserts tile titles appear there.
4. Footer: `For Claude` in the Browse nav; `For AI assistants` group in the Trust column; the disclaimer gains "The AI plugin's scripts run in your own assistant environment and make no network calls; its optional connector sends lookup keys only."

Placement rationale: after the free tiers keeps the SEO-bearing calculator catalog first and groups the plugin with the other free offerings; a dashed outline marks every addition in the mock.
