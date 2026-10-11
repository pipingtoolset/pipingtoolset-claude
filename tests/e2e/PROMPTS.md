# End-to-end example prompts

Run headless with the plugin loaded (from the repo root):

```
claude -p "<prompt>" --plugin-dir plugins/piping-toolset --model sonnet --allowedTools "Bash(python:*)" Read Glob Grep
```

Each prompt names the plugin skill explicitly, because other installed skills on the same topics
would otherwise compete. A pass needs every check in the
right-hand column.

| # | Skill | Prompt | Pass checks |
|---|---|---|---|
| E1 | pressure-design | `/piping-toolset:pressure-design B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?` | runs the script (not mental math); t = 0.13650, tm = 0.19900 (hand: 750·6.625/(2·(17900+750·0.4)) = 4968.75/36400); compares 0.280·0.875 = 0.245 ≥ 0.19900 → adequate; echoes S/E/W/Y as user-supplied; cites ¶304.1.2 Eq. (3a); does not volunteer any table value |
| E2 | pressure-design | `/piping-toolset:pressure-design What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.` | refuses to state a value; names B31.3 Table A-1 (A-1C in 2024), material row and temperature columns; offers to interpolate once the user reads the two values |
| E3 | stress-screening | `/piping-toolset:stress-screening B31.3-2022 line, 7,000 equivalent full cycles over life? Actually it's about 20,000 cycles. Ferrous material, SMTS below 75 ksi (from my spec), max metal temp 500 F, Sc = 12000 psi and Sh = 11000 psi from my copy. What is S_A and which f equation applies?` | uses the 2022+ form f = 20·N^-0.333 (not 6.0·N^-0.2); f ≈ 0.7392 for N = 20,000; applies the ferrous cap logic correctly; S_A = f·(1.25·Sc + 0.25·Sh) = f·17750 ≈ 13,122 psi; flags the liberal allowance as optional only where permitted |
| E4 | stress-screening | `/piping-toolset:stress-screening B31.3-2024 project. Which document gives the SIF for a welding tee and can I use Appendix D?` | B31J governs (App D deleted from B31.3-2020 on); does not give any SIF formula or value; warns about in-plane/out-of-plane transposition at tees |
| E5 | stress-screening | `/piping-toolset:stress-screening Quick exemption check, B31.3: 4 in. line, OD 4.5 in, total displacement to absorb 1.2 in, developed length 40 ft, straight-line distance between anchors 30 ft. S_A = 25000 psi and Ea = 1.5e7 psi from my copy.` | runs screen.flexibility-exemption; D·y/(L−U)² = 4.5·1.2/100 = 0.054; K1 = 30·25000/1.5e7 = 0.05 → ratio 1.08, exceeds, formal analysis required; lists the exemption's stated limitations |
| E6 | load-case-builder | `/piping-toolset:load-case-builder B31.1-2024 steam line, one operating state, CAESAR II 2019, springs designed by CAESAR, wind ±X ±Z, no seismic, with and without friction. Build the load case set.` | runs the generator; hanger cases are W (Rigid) and W+T1 (Ignore); states no ASD reduction under B31.1-2024; k-factor 1.15/1.20 with duration basis requested; extraction matrix present |
