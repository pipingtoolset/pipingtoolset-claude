# Spring hangers - full detail

Relocated verbatim from `SKILL.md` (Step 8). The body keeps the limits and the reporting rule in summary.

## Step 8 — Spring hangers

```
cold load   = hot load + rate·travel
variability = |rate·travel| / hot load
```

- **Variable springs: variability ≤ 25 %** (MSS SP-58 §7.7.1.2, Eq. 1). **Constant supports: deviation ≤ 6 %** (§7.7.1.3). B31.3-2022 and 2024 reference the 2018 edition of SP-58, so say so if you use a provision that exists only in a later edition.
- In the tool, `supports.spring-variability` takes `limit` in **percent** (25), but `supports.max-spring-rate` takes `variabilityLimit` as a **fraction** (0.25). Do not mix them.
- Report hot load, cold load, travel, rate and variability for **every** spring, and check springs in the installed case as well as the operating case. A spring that tops or bottoms out in the cold case is a finding.
- A tighter limit on a variable spring is a project-specification choice, not an SP-58 figure for that device.
- The attachment of the support (trunnion, lug, clip) needs its own local-stress check; the stress calc ends at the restraint load.
