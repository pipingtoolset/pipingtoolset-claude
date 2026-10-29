# Pipe-support golden generators

`tests/golden/pipe-support/*.json` are the parity goldens for the `pipe-support` skill: the
Python port in `plugins/piping-toolset/skills/pipe-support/scripts/pipe_support/` must reproduce
them digit for digit. They are produced by the real PiperSTR TypeScript engine in the private
`pipecalcpro` repository, not by hand, and this folder holds the scripts that produce them.

| Generator | Engine modules imported | Golden(s) |
|---|---|---|
| `gen-goldens.mts` | `structural/connection-weld.ts`, `baseplate-anchorage.ts`, `pier-soil.ts` | `weld.json`, `baseplate.json`, `pier.json` |
| `gen-assembly-goldens.mts` | `structural/support-assembly.ts`, `aisc-section.ts`, AISC shapes dataset | `assembly.json` |
| `gen-aisc-member-goldens.mts` | `structural/aisc-member.ts`, `aisc-strength.ts`, `aisc-section.ts` | `aisc-member.json` |

The generators import the engine by relative path (`../packages/...`), so they run from a
folder that is a direct child of a pipecalcpro checkout. `regen.py` does the copying, running
and cleanup:

```powershell
cd C:\dev\projects\pipingtoolset-claude
python tools\goldens\regen.py --src C:\dev\projects\pipecalcpro          # rewrite the goldens
python tools\goldens\regen.py --src C:\dev\projects\pipecalcpro --check  # exit 1 on drift
```

Requirements: Node.js (`npx`) on PATH and a pipecalcpro checkout with `node_modules`
installed (it provides `tsx`). The run takes a few seconds.

After a rewrite, run the parity tests and commit the goldens together with the port change
that motivated them:

```powershell
python -m unittest discover -s tests -p "test_pipe_support*.py"
```

`tests/golden/pipe-support/SOURCE.json` records the calc-core commit the committed goldens were
generated from and a SHA-256 of each file. A `--check` run says which goldens would change
against the engine at `--src`; it does not compare commits, so a pipecalcpro checkout that has
moved on without touching the structural engine still passes.

History: the generators were written in the pipecalcpro worktree for the 0.3.x pipe-support
work (PRs #5, #6, #7) and lived only in an untracked scratch folder until 2026-10-29, when a
review found that no tracked copy existed. They are committed here byte for byte; the
usage comments at the top of each file still describe running them from inside pipecalcpro,
which is exactly what `regen.py` arranges. On 2026-10-29 they reproduced all five committed
goldens byte-identically against calc-core at the PR #143 engine.
