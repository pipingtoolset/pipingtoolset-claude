# Phase 2: host verification runbook (plugin 0.7.2)

Copy-paste runbook for proving the same plugin installs, shows its mark, and runs its scripts in
every host it claims. Sibling of `COWORK-CHECKLIST.md`. Fill the results table at the bottom as
you go; a host passes only when every box in its row is ticked.

Prompts are the Cowork form from `PROMPTS.md` (skill named in plain words), which works in every
chat host. In Codex, prefix with the skill tag instead (`$pressure-design ...`). Each prompt below
is a complete line to paste.

```
E1  Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
E2  Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.
E9  Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.
```

Pass criteria, unchanged from `PROMPTS.md`:

- **E1**: a python command ran `pressure_design.py` (visible in the tool log); t = 0.13650 in,
  t_m = 0.19900 in; 0.280 × 0.875 = 0.245 ≥ 0.19900 → adequate; S/E/W/Y echoed as user-supplied;
  ¶304.1.2 Eq. (3a) cited; no table value volunteered.
- **E2**: no number. Names B31.3 Table A-1 (A-1C in 2024), the material row and the two
  temperature columns, offers to interpolate once you read both. This is the refusal test for the
  plugin without the connector: run it with the Engineering Data connector disconnected, or not
  signed in to a paid plan. With the connector on and a paid pipingtoolset.com account the skill
  may serve the cited value instead; record that under the connector rows (§2, §4, §5), not as an
  E2 failure.
- **E9**: `support_calc.py` ran with `--report` / `--json`; governing stage, check, combination
  and clause come from the run; optimizer table presented; `calc.md` and `result.json` written.

---

## 0. Before any host: the release and the site must exist

Run in PowerShell from any folder.

```powershell
gh release view v0.7.2 --repo pipingtoolset/pipingtoolset-claude --json tagName,assets --jq '.tagName, (.assets[].name)'
```

Expect `v0.7.2` and three assets: `piping-toolset.plugin`, `piping-toolset.zip`,
`piping-toolset-skills.zip`. If the tag or assets are missing, stop: push the tag and let CI
attach them.

```powershell
curl.exe -sI https://pipingtoolset.com/openai/ | Select-String "^HTTP"
curl.exe -sI https://pipingtoolset.com/claude/ | Select-String "^HTTP"
curl.exe -sI https://pipingtoolset.com/legal/privacy.html | Select-String "^HTTP"
curl.exe -sI https://pipingtoolset.com/legal/terms.html | Select-String "^HTTP"
curl.exe -sI https://pipingtoolset.com/docs/connector/ | Select-String "^HTTP"
```

Expect `HTTP/1.1 200` (or `HTTP/2 200`) on all five. The first four are the `websiteURL`,
`privacyPolicyURL` and `termsOfServiceURL` in the OpenAI listing block (the portal checks that
they resolve and name the same publisher); the fifth is the connector setup page the README and
the listing copy link to.

```powershell
curl.exe -s https://pipingtoolset.com/ | Select-String "For OpenAI|PipingToolset for AI|Install in ChatGPT / Codex"
```

Expect three matches: the hero button, the launcher tier heading and the ChatGPT / Codex tile.

## 1. Local validation on this PC

```powershell
cd C:\dev\projects\pipingtoolset-claude
git fetch origin
git checkout main
git pull
python -m unittest discover -s tests
python tools\package_plugin.py --out dist --check
claude plugin validate .\plugins\piping-toolset
claude plugin validate .
```

Expect `OK` from the test run, three `check ok` lines from the packager, and `Validation passed`
twice.

Reference validator (the same check CI runs; needs Python 3.11 or newer):

```powershell
python -m pip install skills-ref==0.1.1
Get-ChildItem .\plugins\piping-toolset\skills -Directory | ForEach-Object { python -m skills_ref.cli validate $_.FullName }
```

Expect seven lines starting `Valid skill:`.

Confirm the archive you will upload carries the manifests, the Claude connector declaration and the
mark:

```powershell
python -c "import zipfile; z=zipfile.ZipFile('dist/piping-toolset.zip'); print('\n'.join(n for n in z.namelist() if n.endswith('plugin.json') or n.endswith('mcp.json') or n.startswith('assets/')))"
```

Expect `.claude-plugin/plugin.json`, `plugin.json`, `.mcp.json`, `assets/icon.png`, `assets/icon.svg`,
and no other entry ending `mcp.json` (the Agent Plugins connector file was removed in 0.7.1). The
skills-only zip must carry no declaration:

```powershell
python -c "import zipfile; z=zipfile.ZipFile('dist/piping-toolset-skills.zip'); print(sum(n.endswith('mcp.json') for n in z.namelist()))"
```

Expect `0`.

## 2. Claude Code (terminal)

```powershell
claude plugin marketplace add pipingtoolset/pipingtoolset-claude
claude plugin install piping-toolset@pipingtoolset
claude plugin details piping-toolset
```

Expect `Skills (7)` listing the seven names and version `0.7.2`. Then, headless, from any empty
folder:

```powershell
claude -p "/piping-toolset:pressure-design B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?" --model sonnet --allowedTools "Bash(python:*)" Read Glob Grep
```

```powershell
claude -p "/piping-toolset:pressure-design What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number." --model sonnet --allowedTools "Bash(python:*)" Read Glob Grep
```

Record E1 and E2 against the pass criteria. If the marketplace was added at an earlier version,
run `claude plugin marketplace update pipingtoolset` first.

Connector row (Claude Code). In an interactive `claude` session open `/mcp` and find the
`pipingtoolset-data` server that the plugin declares; record whether it shows as connected. Ask
for a worked example of a data-free module (the assistant calls `get_fixture_example`) and for the
`W6X15` shape (`get_aisc_shape`): both are open and need no sign-in. Then ask for an allowable
stress; with no paid account signed in, the host must start the sign-in through pipingtoolset.com
or the tool must return a one-line message naming the plan and the pricing page, and no value
may appear. Disconnect the server in `/mcp` and repeat E2: the refusal must hold.

## 3. Claude Cowork (Claude desktop app, Windows)

1. Download `piping-toolset.plugin` from the v0.7.2 release
   (`https://github.com/pipingtoolset/pipingtoolset-claude/releases/download/v0.7.2/piping-toolset.plugin`).
2. If an earlier version is installed, remove it first in Settings › Plugins.
3. Drag the file into a new Cowork chat, press **Accept**.
4. Check in the plugin list: the grid-elbow mark (not a generic icon), display name
   **PipingToolset**, seven skills in the skills menu.
5. Also try Settings › Plugins › **Upload a plugin** with the same file: it must not reject the
   description (the 500-character cap is tested, but this is the live check).
6. Run E1 and E2 in a fresh chat. Record.
7. Connector row: in the plugin's connector or MCP list find `pipingtoolset-data`. Ask for a
   worked example of a data-free module; it needs no sign-in. Ask for an allowable stress with no
   paid account signed in: no value may appear. Switch the connector off and repeat E2: the
   refusal must hold. Record whether the host showed a **Sign in** prompt.

## 4. Codex CLI (terminal)

Install the CLI once if it is missing (Node 22 or newer):

```powershell
npm install -g @openai/codex
codex --version
```

Register the marketplace and install:

```powershell
codex plugin marketplace add pipingtoolset/pipingtoolset-claude
codex plugin marketplace list
```

Expect `pipingtoolset` in the list. Then start `codex` in an empty folder, type `/plugins`,
install **PipingToolset**. Confirm the picker shows the name PipingToolset (not `piping-toolset`),
the mark, and "Flexible Piping Solutions LLC".

In the same session run, one at a time:

```
$pressure-design B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
```

```
$pressure-design What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.
```

```
$pipe-support Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.
```

Record E1, E2, E9. Note which Python Codex used (`python --version` in the same shell).

Connector row (Codex). From 0.7.2 the plugin declares no server for Codex: the Agent Plugins
connector file was removed after the 0.7.0 install test showed a sign-in prompt at install.
`.agents/plugins/marketplace.json` still sets `authentication` to `ON_INSTALL`, the only value the
OpenAI plugin docs list (read 2026-10-28); with no server declared there is nothing to authenticate
at install. Install 0.7.2 from the tag and expect NO sign-in prompt. If one still appears, the policy
value is the next suspect: record the exact prompt text and screenshot it, and do not change the
value until the docs list another. Then check what Codex lists, and add the server by hand, which is
how the connector reaches Codex:

```powershell
codex mcp list
codex mcp add pipingtoolset-data --url https://pipingtoolset.com/mcp
codex mcp login pipingtoolset-data
```

Record that `codex mcp list` showed no `pipingtoolset-data` entry before the `add`, and that `login`
opened pipingtoolset.com. Ask for a worked example of a data-free module (open, no sign-in), then
for an allowable stress while signed out (no value may appear).

Upgrade path, for the next release:

```powershell
codex plugin marketplace upgrade pipingtoolset
```

## 5. ChatGPT desktop app (Windows)

This is the run that answers whether the ChatGPT desktop app executes the bundled scripts, and
whether the listing block fixed the icon and name.

1. With the marketplace from step 4 registered, open the ChatGPT desktop app › **Customize ›
   Plugins**. If `piping-toolset` from before 0.6.0 is installed, **Manage › Uninstall** it, then
   install **PipingToolset** again from the marketplace.
2. Screenshot the plugin page. Check, against the 2026-10-28 screenshot in the task record:
   - name reads **PipingToolset**, not `piping-toolset`;
   - the icon is the grid-elbow mark, not the generic cube;
   - "By Flexible Piping Solutions LLC" and the seven skills are listed;
   - the subtitle reads "ASME B31 piping engineering" if the app shows one.
3. Press **Try now**, paste E1. Expand the steps: a python command running `pressure_design.py`
   must be visible. If the numbers appear with no command, the app did arithmetic in its head and
   the row fails (record it; that is a finding, not a defect in the plugin).
4. New conversation, paste E2. Expect the refusal.
5. Connector row: from 0.7.2 the plugin declares no server for this app, so expect the plugin page
   to list no `pipingtoolset-data` and no sign-in prompt at install (record either if seen). Add the
   server as a developer-mode connector with the URL `https://pipingtoolset.com/mcp` and OAuth,
   ask for a worked example of a data-free module (open, no sign-in) and for an allowable stress
   while signed out (no value may appear), and record that the sign-in, if offered, goes through
   pipingtoolset.com.
6. Record, with the screenshot path, in the table.

## 6. OpenAI plugin portal (directory submission dry run)

Do not press Submit in this phase; the goal is to see every automated check pass.

1. Open `https://platform.openai.com/plugins`, **Create plugin › Skills only**, upload
   `dist\piping-toolset.zip` (or the release asset of the same name).
2. The portal converts the archive and shows a generated `.codex-plugin/plugin.json`. Confirm
   it carried the `interface` block from the root `plugin.json`: `displayName` PipingToolset,
   `shortDescription`, `developerName`, `category` Productivity, `logo` and `composerIcon`
   pointing at `assets/`. The converted package should show no MCP servers (the Agent Plugins
   connector file was removed in 0.7.2); if it shows one, record it as a finding.
3. Check the **category** dropdown in the dashboard. If **Productivity** is not an offered
   value, note the closest one here and change `category` in both
   `plugins/piping-toolset/plugin.json` and `.agents/plugins/marketplace.json` (the test keeps
   them equal).
4. Run the package validation, metadata checks and skill scans. Every finding must be cleared
   before Phase 3; paste any error code into the results table and look it up at
   `https://developers.openai.com/plugins/deploy/submission-errors`.
5. Confirm the four public URLs are accepted (website, privacy, terms, support).
6. Identity verification (individual or business) and Apps Management write access are
   required before a real submission. Record whether the organization is verified.

## 7. Other Agent Skills hosts (optional this phase)

```powershell
npx skills add pipingtoolset/pipingtoolset-claude
```

```powershell
gh skill install pipingtoolset/pipingtoolset-claude
```

Expect seven skills installed under `.agents/skills/` (project) or `~/.agents/skills/` with
`--global`. In Cursor or Copilot CLI, run E1 and E2 and record.

## 8. The mark everywhere else

Not automated; account settings, so done by hand.

- GitHub organization `pipingtoolset` avatar: upload `plugins/piping-toolset/assets/icon.png`
  (Settings › Profile). skills.sh and `gh skill` listings show this avatar.
- Anthropic directory: when submitting from `https://claude.ai/directory/manage`, the listing
  reads `icon`, `documentationUrl`, `supportUrl`, `privacyPolicyUrl` and `termsOfServiceUrl`
  from `.claude-plugin/plugin.json`; nothing to upload separately.
- OpenAI directory: `logo` and `composerIcon` from the root `plugin.json`, carried inside the
  zip; nothing to upload separately.
- Connector: the one declaration (`.mcp.json`, read by Claude Code and Cowork) travels inside the
  `.plugin` and `.zip` and is absent from the skills-only zip. If a directory form asks for the remote server by
  hand, it is `https://pipingtoolset.com/mcp`, Streamable HTTP, sign-in through pipingtoolset.com
  (open tools need none), documented at `https://pipingtoolset.com/docs/connector/`.

## Results

| Host | Version shown | Name shown | Mark shown | E1 script ran | E1 numbers | E2 refuses | E9 | Connector: open tools, no paid value signed out, E2 holds when off | Date | Notes / screenshot |
|---|---|---|---|---|---|---|---|---|---|---|
| Local validation (§1) | | n/a | n/a | n/a | n/a | n/a | n/a | n/a | | |
| Claude Code (§2) | | | | | | | | | | |
| Claude Cowork (§3) | | | | | | | | | | |
| Codex CLI (§4) | | | | | | | | | | |
| ChatGPT desktop app (§5) | | | | | | | | | | |
| OpenAI portal dry run (§6) | | | | | | | | n/a | | category offered: |
| Cursor / Copilot CLI (§7) | | | | | | | | n/a | | |

For the Codex CLI and ChatGPT desktop rows, write "no sign-in prompt at install: yes / no" in Notes
(the 0.7.2 gate for the connector copy to stay true in those hosts).

When every row you ran is filled, commit this file as the Phase 2 record and move to Phase 3
(listings, in the order of `docs/research/cross-platform-distribution-2026-10-27.md` §7).
