# pipingtoolset.com drafts for the plugin launch (2026-10-27)

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

- [PipingToolset for Claude — B31 Piping Skills for Claude Code and Cowork](https://pipingtoolset.com/claude/): Five ASME B31.3 / B31.1 skills for Claude Code and Cowork. Claude runs the interview, a script does the math, no code table values are embedded, and nothing you enter reaches PipingToolset.
```

If the cross-platform plan goes ahead, retitle the section `## AI assistant plugin` and the page "PipingToolset for AI assistants", with Claude first.

## Build integration (pipecalcpro)

1. `scripts/seo/claude-content.mjs`: export `{ title, metaDescription, reviewed, body }` like `trust-content.mjs`. Body = everything inside `<main>` of `claude-page.html` after the breadcrumb and H1.
2. `scripts/seo/build-pages.mjs`: a `claudePage()` builder that writes `claude/index.html` with the shared chrome, pushes `{ title, metaDescription, path: "/claude/" }` into a new `CLAUDE_META` constant, and adds it to `sitemap.xml`, `llmsTxt()` (new section above) and `llmsFullTxt()`. Breadcrumb: Home › PipingToolset for Claude. JSON-LD: the `SoftwareApplication` block in the draft, plus `BreadcrumbList`.
3. OG image: `scripts/seo/og-images.mjs` needs a `claude` entry; the draft references `/brand/og/claude.png`.
4. Footer links: `apps/web/index.html` footer "Browse" nav gets `For Claude`, and the Trust column gets a `For AI assistants` group with `PipingToolset for Claude`, `Plugin source (GitHub)`, `llms.txt`. The e2e smoke test asserts every footer href resolves, so add the page in the same commit.
5. Generated-page footers: the `Browse` column template in `build-pages.mjs` gets the same `/claude/` link.
6. Netlify: `/claude/index.html` is served as a directory index like `/calculators/`; no redirect needed. `pretty_urls = false` and no SPA catch-all stay as they are.
7. Stamp: `reviewed: "2026-10-27"`; bump the version line (`0.4.0 · released 2026-10-26`) on each plugin release, or read it from the GitHub Releases API at build time.

## Homepage changes shown in the mock

1. Hero CTA row: a third button `For Claude` after `Pricing`, linking to `/claude/`.
2. Hero sub-paragraph: one sentence noting the engine now runs inside Claude Code and Cowork as a free plugin.
3. Launcher: a new tier `PipingToolset for Claude — free · open source · Apache-2.0` placed after the two free tiers and before Pro Tools, with three tiles (Install in Cowork, Install in Claude Code, What it does / will not do / where data goes) and a version pill. In `App.tsx` this is a hand-written block like Report Manager, with `<a href="/claude/">` tiles rather than hash-route buttons so crawlers follow it. Mirror the three titles in the pre-hydration `.shell-apps` catalog in `index.html`, since the build asserts tile titles appear there.
4. Footer: `For Claude` in the Browse nav; `For AI assistants` group in the Trust column; the disclaimer gains "The Claude plugin runs in your own Claude environment and sends nothing to Piping Toolset."

Placement rationale: after the free tiers keeps the SEO-bearing calculator catalog first and groups the plugin with the other free offerings; a dashed outline marks every addition in the mock.
