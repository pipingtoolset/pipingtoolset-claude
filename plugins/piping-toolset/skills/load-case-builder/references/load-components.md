# Load component notes

Relocated verbatim from the load-case-builder SKILL.md (Step 2).

**Uniform loads in g's** is a *global* flag (Kaux → Special Execution Parameters → "Uniform Load in Gs"). With it on, every U vector is read as an acceleration; with it off, every U vector is force per unit length. **You cannot mix the two in one model.** Three consequences:

- Seismic needs g's. Snow/ice is naturally lb/ft (depth × density × OD). Entering snow on `U2` in a g-based model needs an equivalent g that is only right for one pipe size — wrong everywhere else in a multi-size model.
- `U2` is the **only** vertical vector. If snow occupies it, nothing is left for the concurrent vertical seismic `E_v = 0.2·S_DS·W_p` that ASCE 7 Chapter 13 requires.
- Resolution: dedicate `U2` to `E_v`, carry snow as added weight or as a separate run, and say which you did.

**PSV thrust** is a real force pair: the thrust at the discharge elbow or tee and an equal, opposite force on the valve body. One `F` vector per independently firing valve — two valves that cannot fire together are not combined.
