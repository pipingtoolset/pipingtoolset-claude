// Golden generator for the pipe-support Python port. Usage (from the main checkout):
//   cd /c/dev/projects/pipecalcpro && npx tsx <this file> <outDir>
import { writeFileSync, mkdirSync } from "node:fs";
import { filletWeld } from "../packages/calc-core/src/structural/connection-weld.ts";
import { basePlateAnchorage } from "../packages/calc-core/src/structural/baseplate-anchorage.ts";
import { pierSoil } from "../packages/calc-core/src/structural/pier-soil.ts";

const outDir = process.argv[2];
mkdirSync(outDir, { recursive: true });

type Case = Record<string, unknown>;

function run(fn: (i: any) => any, inputs: Case[]) {
  return inputs.map((input) => {
    try {
      const r = fn(input);
      return { input, output: r.output, status: r.status, warnings: r.warnings };
    } catch (e) {
      return { input, error: (e as Error).message };
    }
  });
}
function dump(name: string, module: string, cases: unknown[]) {
  const json = JSON.stringify(
    { module, cases },
    (_k, v) => (typeof v === "number" && !Number.isFinite(v) ? (Number.isNaN(v) ? "NaN" : v > 0 ? "Infinity" : "-Infinity") : v),
    2,
  );
  writeFileSync(`${outDir}/${name}.json`, json + "\n");
  console.log(name, cases.length);
}

// ---------------------------------------------------------------- weld
const W = { method: "LRFD", size: 0.25, FEXX: 70, pattern: "single", depth: 10 };
const weld: Case[] = [
  { ...W, Vparallel: 10 },
  { ...W, Vtransverse: 10 },
  { ...W, Vtransverse: 10, Vparallel: 10 },
  { ...W, Vtransverse: 3, Vparallel: 8, Pnormal: 2 },
  { ...W, Pnormal: 15 },
  { ...W },                                   // zero load
  { ...W, M: 40, Vtransverse: 2 },            // single with moment -> eccentric warning
  { ...W, method: "ASD", Vtransverse: 10 },
  { ...W, method: "ASD", Vparallel: 10 },
  { ...W, depth: 0.75, Vtransverse: 2 },         // L/w < 4 warning
  { ...W, depth: 0.75, length: 0.75, Vtransverse: 2 }, // length override suppresses the warning
  { ...W, length: 6, M: 12, Vtransverse: 3 },
  { ...W, pattern: "two-parallel", depth: 6, Vtransverse: 3, M: 40 },
  { ...W, pattern: "two-parallel", depth: 6, Vparallel: 8, M: 20, Pnormal: 4 },
  { ...W, pattern: "two-parallel", method: "ASD", depth: 5.99, size: 0.3125, Vtransverse: 2.7, M: 36.6, basePartThickness: 0.23 },
  { ...W, pattern: "two-parallel", depth: 8, length: 12, Vtransverse: 5 },
  { ...W, pattern: "all-round", depth: 5.99, width: 5.99, Vtransverse: 1.5, M: 96, basePartThickness: 0.75, baseFy: 36, baseFu: 58 },
  { ...W, pattern: "all-round", depth: 8, width: 6, Vtransverse: 4, Vparallel: 2, M: 100, Pnormal: 10 },
  { ...W, pattern: "all-round", depth: 8, width: 6, method: "ASD", Vtransverse: 4, M: 100 },
  { ...W, pattern: "all-round", depth: 8, width: 6, length: 20, Vtransverse: 4, M: 60 },
  { ...W, pattern: "all-round", depth: 4, width: 4, size: 0.5, Vtransverse: 60, M: 400 },   // overloaded
  // minimum / maximum size flags (Table J2.4, J2.2b)
  { ...W, size: 0.125, basePartThickness: 0.25, Vparallel: 2 },
  { ...W, size: 0.125, basePartThickness: 0.4, Vparallel: 2 },     // below min 3/16
  { ...W, size: 0.1875, basePartThickness: 0.6, Vparallel: 2 },    // below min 1/4
  { ...W, size: 0.25, basePartThickness: 1.0, Vparallel: 2 },      // below min 5/16
  { ...W, size: 0.3125, basePartThickness: 0.5, Vparallel: 2 },
  { ...W, size: 0.375, basePartThickness: 0.375, Vparallel: 2 },   // above max t - 1/16
  { ...W, size: 0.25, basePartThickness: 0.1875, Vparallel: 1 },   // t < 1/4: max = t, w > t
  { ...W, size: 0.125, basePartThickness: 0.1875, Vparallel: 1 },
  { ...W, size: 0.3125, basePartThickness: 0.23, Vparallel: 1 },
  { ...W, size: 0.25, basePartThickness: 0, Vparallel: 2 },        // falsy t -> no limits
  // base-metal rupture (J4-4)
  { ...W, size: 0.5, basePartThickness: 0.25, baseFu: 58, Vparallel: 10 },     // base governs
  { ...W, size: 0.25, basePartThickness: 0.75, baseFu: 58, Vparallel: 10 },    // weld governs
  { ...W, size: 0.5, basePartThickness: 0.25, baseFu: 58, method: "ASD", Vparallel: 10 },
  { ...W, size: 0.25, baseFu: 58, Vparallel: 10 },                 // baseFu without t -> null
  { ...W, FEXX: 60, Vtransverse: 5 },
  { ...W, FEXX: 80, size: 0.375, Vtransverse: 5, Vparallel: 5 },
  // J4 base metal split by direction (connection-weld.ts, PR #138)
  { ...W, size: 0.25, basePartThickness: 0.75, baseFu: 58, Vparallel: 10 },                       // shear only, weld governs, baseFy absent
  { ...W, size: 0.25, basePartThickness: 0.75, baseFu: 58, baseFy: 36, Vparallel: 10 },           // baseFy present -> yield row
  { ...W, size: 0.25, basePartThickness: 0.75, baseFu: 58, baseFy: 36, Pnormal: 15 },             // normal tension only
  { ...W, size: 0.25, basePartThickness: 0.75, baseFu: 58, baseFy: 36, M: 40, Vtransverse: 2 },   // moment -> normal via M/Sw
  { ...W, size: 0.25, basePartThickness: 0.75, baseFu: 58, baseFy: 36, M: 40, Vtransverse: 2, method: "ASD" },
  { ...W, size: 0.5, basePartThickness: 0.25, baseFu: 58, baseFy: 36, Pnormal: 12, Vparallel: 4 }, // base metal governs (warning), may fail
  { ...W, size: 0.5, basePartThickness: 0.25, baseFu: 58, baseFy: 36, Pnormal: 6, Vparallel: 2, method: "ASD" },
  { ...W, size: 0.5, basePartThickness: 0.25, baseFu: 58, Vparallel: 3 },                          // baseMetalRatio governing but <= 1
  { ...W, size: 0.5, basePartThickness: 0.25, baseFu: 58, baseFy: 36, Pnormal: 2 },                // yield vs rupture, passes
  { ...W, size: 0.25, basePartThickness: 0.75, baseMetalThickness: 0.1, baseFu: 58, baseFy: 36, Vparallel: 6 },   // thin per-line base metal fails, weld passes
  { ...W, size: 0.25, basePartThickness: 0.75, baseMetalThickness: 0.1, baseFu: 58, baseFy: 36, Pnormal: 4, method: "ASD" },
  { ...W, size: 0.25, baseMetalThickness: 0.125, baseFu: 58, baseFy: 36, Vparallel: 3 },           // baseMetalThickness without basePartThickness
  { ...W, size: 0.25, baseMetalThickness: 0.125, baseFu: 58, Vparallel: 3 },
  { ...W, size: 0.25, baseMetalThickness: 0.125, Vparallel: 3 },                                   // no baseFu -> null rows, thickness reported
  { ...W, size: 0.25, basePartThickness: 0.75, baseMetalThickness: 0, baseFu: 58, Vparallel: 3 },   // 0 -> falsy -> no J4
  { ...W, size: 0.25, basePartThickness: 0.375, baseFu: 58, baseFy: 36 },                          // zero load, base ratio 0
  { ...W, size: 0.25, basePartThickness: 0.375, baseFu: 58, baseFy: 36, baseForces: { normal: 0, shear: 0 } },
  { ...W, pattern: "two-parallel", depth: 6, size: 0.25, basePartThickness: 0.23, baseMetalThickness: 0.115, baseFu: 58, baseFy: 36,
    Vtransverse: 3, Vparallel: 2, M: 40, baseForces: { normal: 1.5, shear: 3.6 } },
  { ...W, pattern: "two-parallel", depth: 6, size: 0.25, basePartThickness: 0.23, baseMetalThickness: 0.115, baseFu: 58, baseFy: 36,
    Vparallel: 2.5, M: 40, baseForces: { normal: 8, shear: 1 } },                                  // baseForces normal differs from Pnormal
  { ...W, pattern: "two-parallel", depth: 6, size: 0.25, basePartThickness: 0.23, baseFu: 58, baseFy: 36,
    Vtransverse: 3, Vparallel: 2, M: 20, baseForces: { normal: -6, shear: -2 }, method: "ASD" },   // negative forces -> abs
  { ...W, pattern: "all-round", depth: 8, width: 6, size: 0.3125, basePartThickness: 0.23, baseFu: 58, baseFy: 36, Vtransverse: 4, M: 100 },
  { ...W, pattern: "all-round", depth: 8, width: 6, length: 20, size: 0.3125, basePartThickness: 0.25, baseFu: 58, baseFy: 36, Vtransverse: 4, M: 60, Pnormal: 3 },
  { ...W, pattern: "two-parallel", depth: 8, length: 12, size: 0.25, basePartThickness: 0.3, baseFu: 65, baseFy: 50, Vtransverse: 5, M: 30 },
  { ...W, FEXX: 60, size: 0.1875, basePartThickness: 0.2, baseFu: 58, baseFy: 36, Pnormal: 5 },
  // alongEdge: the J2.2b maximum applies only to a fillet along an edge (default true)
  { ...W, size: 0.375, basePartThickness: 0.375, Vparallel: 2 },                                   // warns (default)
  { ...W, size: 0.375, basePartThickness: 0.375, Vparallel: 2, alongEdge: true },                  // warns
  { ...W, size: 0.375, basePartThickness: 0.375, Vparallel: 2, alongEdge: false },                 // no max warning, maxSize still reported
  { ...W, size: 0.25, basePartThickness: 0.1875, Vparallel: 1, alongEdge: false },
  { ...W, size: 0.125, basePartThickness: 0.4, Vparallel: 2, alongEdge: false },                   // min-size warning still emitted
  { ...W, size: 0.375, basePartThickness: 0.375, baseMetalThickness: 0.1875, baseFu: 58, baseFy: 36, Vparallel: 4, alongEdge: false },
  // errors
  { ...W, size: 0 },
  { ...W, FEXX: 0 },
  { ...W, depth: 0 },
  { ...W, pattern: "all-round" },
  { ...W, length: 0 },
];

// ---------------------------------------------------------------- base plate
const BP = {
  columnDepth: 5.99, columnWidth: 5.99, plateLength: 12, plateWidth: 12, plateThickness: 0.75, plateFy: 36,
  fc: 4000, pierLength: 16, pierWidth: 16, anchorType: "post-installed-adhesive", anchorCount: 4,
  anchorDiameter: 0.75, anchorEmbedment: 4.25, anchorFuta: 58, anchorSpacingLength: 9, anchorSpacingWidth: 9,
  anchorEdgeDistance: 3.5, method: "LRFD", P: 2.7, M: 75, V: 0.85,
};
const CI = { ...BP, anchorType: "cast-in", pierLength: 24, pierWidth: 24, anchorEmbedment: 12, anchorEdgeDistance: 7.5, P: 20, M: 120, V: 4, method: "ASD" };
const bp = (o: Case, base: Case = BP): Case => ({ ...base, ...o });
const baseplate: Case[] = [
  bp({}),
  bp({ bondStrength: 1000 }),
  bp({ bondStrength: 0 }),
  bp({ bondStrength: 1000, method: "ASD" }),
  bp({ P: 60, M: 0, V: 0 }),
  bp({ P: 40, M: 20, V: 0 }),                  // e inside kern: trapezoid
  bp({ P: 40, M: 20, V: 3 }),
  { ...CI },
  bp({}, { ...CI, method: "LRFD" }),
  bp({ V: 0 }, CI),
  bp({ P: 0, M: 0, uplift: 8, V: 0 }),         // pure uplift
  bp({ P: 5, uplift: 3, M: 20, V: 0 }),        // net compression + uplift
  bp({ P: 5, uplift: 12, M: 20, V: 1 }),       // net tension + moment
  bp({ P: 0, uplift: 6, M: 0, V: 2 }, { ...CI, method: "LRFD" }),
  bp({ P: 10, uplift: 4, M: 30, V: 1 }, CI),
  bp({ anchorType: "post-installed-mechanical", anchorEmbedment: 5, P: 3, M: 60, V: 1.5 }),
  bp({ anchorType: "post-installed-mechanical", anchorEmbedment: 5, cracked: false, P: 3, M: 60, V: 1.5 }),
  bp({ anchorType: "post-installed-mechanical", anchorEmbedment: 5, cracked: false, method: "ASD", P: 3, M: 60, V: 1.5 }),
  bp({ anchorEdgeDistance: 1.5, anchorEmbedment: 6 }, CI),                   // blowout (ca1 < 0.4 hef)
  bp({ anchorEdgeDistance: 1.5, anchorEmbedment: 6, cracked: false }, CI),
  bp({ cracked: false }, CI),
  bp({ cracked: false }),                                           // psi_cp,N: Table 17.9.5 default cac = 2 hef (2026-10-26)
  bp({ cracked: false, cac: 7 }),
  bp({ cracked: false, cac: 3 }),                                   // ca,min >= cac -> 1.0
  bp({ cracked: false, cac: 0 }),                                   // 0 = not supplied
  bp({ cracked: false, cac: 7, method: "ASD" }),
  bp({ anchorType: "post-installed-mechanical", anchorEmbedment: 5, cracked: false, cac: 12, P: 3, M: 60, V: 1.5 }),
  bp({ pierLength: 16, pierWidth: 16, anchorEdgeDistance: 3.5, anchorEmbedment: 8 }, CI), // 17.6.2.1.2 reduced hef
  bp({ pierLength: 48, pierWidth: 48, anchorEdgeDistance: 19.5, anchorEmbedment: 6 }),
  bp({ pierLength: 48, pierWidth: 48, anchorEdgeDistance: 19.5, anchorEmbedment: 10 }),
  bp({ pierLength: 48, pierWidth: 48, anchorEdgeDistance: 19.5, anchorType: "post-installed-mechanical", anchorEmbedment: 8 }),
  bp({ anchorEdgeDistance: 2 }),               // edge-distance governed breakout (psi_ed,N)
  bp({ anchorEdgeDistance: 2, pierLength: 20, pierWidth: 20 }),
  bp({ anchorEdgeDistance: 2, pierLength: 20, pierWidth: 20, anchorType: "post-installed-mechanical" }),
  bp({ anchorEdgeDistance: 1, pierLength: 14, pierWidth: 14, V: 2, anchorType: "cast-in", anchorEmbedment: 8 }),
  bp({ anchorStressArea: 0.3 }),
  bp({ anchorStressArea: 0.3, anchorType: "cast-in" }, CI),
  bp({ anchorDiameter: 0.8 }),                  // not in UNC table: 8-UN fallback
  bp({ anchorDiameter: 1, anchorStressArea: undefined }),
  bp({ anchorDiameter: 1.25, anchorEmbedment: 6 }),
  bp({ ductile: false }),
  bp({ lambda: 0.75 }),
  bp({ lambda: 0.75 }, CI),
  bp({ anchorCount: 2 }),
  bp({ anchorCount: 6 }),
  bp({ anchorCount: 5, V: 3 }),
  bp({ pierLength: 60, pierWidth: 60 }),         // bearing ratio capped at 2
  bp({ plateThickness: 0.25 }),                  // thin plate fails
  bp({ plateThickness: 0.5, M: 150, P: 4 }),
  bp({ P: 300, M: 750, V: 0 }),                  // no real root
  bp({ P: 300, M: 750, V: 0, anchorSpacingLength: 0 }),
  bp({ P: 500, M: 0, V: 0 }),                    // over capacity, X > 1
  bp({ P: 420, M: 0, V: 0 }),
  bp({ P: 0, M: 0, V: 0 }),                      // all n/a
  bp({ P: 0, M: 50, V: 0 }),                     // P = 0 -> infinite eccentricity
  bp({ M: -75 }),                                // sign of M
  bp({ V: 8 }),                                  // shear fails
  bp({ V: 2, M: 15, P: 3 }),
  bp({ V: 0 }),
  bp({ columnDepth: 8, columnWidth: 6.5, plateLength: 14, plateWidth: 10, pierLength: 24, pierWidth: 20, anchorSpacingLength: 11, anchorSpacingWidth: 7, anchorEdgeDistance: 6.5, P: 30, M: 90, V: 2 }),
  bp({ anchorEmbedment: 2, anchorType: "post-installed-mechanical", V: 1 }),     // kcp = 1
  bp({ anchorEmbedment: 2, anchorType: "cast-in", pierLength: 24, pierWidth: 24, anchorEdgeDistance: 7.5, V: 1 }),
  bp({ fc: 3000, plateFy: 50 }),
  bp({ fc: 6000, method: "ASD", plateFy: 50 }),
  bp({ anchorSpacingLength: 6, anchorSpacingWidth: 6, anchorEdgeDistance: 5 }),
  // errors
  bp({ plateLength: 0 }),
  bp({ plateThickness: 0 }),
  bp({ fc: 0 }),
  bp({ anchorCount: 0 }),
  bp({ anchorEmbedment: 0 }),
];

// ---------------------------------------------------------------- pier
const PR = {
  method: "ASD", pierLength: 16, pierWidth: 16, pierHeight: 24, fc: 4000, footingLength: 48, footingWidth: 48,
  footingThickness: 12, allowableBearing: 3, frictionCoefficient: 0.35, plateLength: 12, plateWidth: 12,
  P: 15, M: 96, V: 0,
};
const pr = (o: Case, base: Case = PR): Case => ({ ...base, ...o });
const pier: Case[] = [
  { ...PR },
  pr({ method: "LRFD" }),
  pr({ footingLength: 36, footingWidth: 36, P: 2.7, M: 75, V: 0.85 }),                // partial bearing
  pr({ footingLength: 36, footingWidth: 36, P: 2.7, M: 75, V: 0.85, method: "LRFD" }),
  pr({ footingLength: 24, footingWidth: 24, P: 2, M: 400, V: 0 }),                    // resultant off the footing
  pr({ P: 0, uplift: 20, M: 10 }),                                                    // net uplift
  pr({ P: 0, uplift: 2.9333333333333336, M: 0 }),                                     // near-zero vertical
  { method: "ASD", pierLength: 16, pierWidth: 16, pierHeight: 24, fc: 4000, allowableBearing: 3, restraint: "anchored", plateLength: 12, plateWidth: 12, P: 2.7, M: 75, V: 0.85 },
  pr({ restraint: "anchored", P: 10, M: 400, V: 5 }),
  pr({ restraint: "anchored", footingThickness: 0, P: 10, M: 200, V: 5, method: "LRFD" }),
  pr({ restraint: "gravity", V: 3, frictionCoefficient: 0.35 }),
  pr({ V: 3, frictionCoefficient: 0, cohesion: 0 }),                                  // sliding not evaluable
  pr({ V: 3, frictionCoefficient: 0, cohesion: 0.2 }),                                // cohesion only
  pr({ V: 3, frictionCoefficient: 0.3, cohesion: 0.1 }),
  pr({ V: 12, frictionCoefficient: 0.25 }),                                           // sliding fails
  pr({ V: 3, slidingFS: 2, overturningFS: 2 }),
  pr({ V: 3, slidingFS: 1.25, overturningFS: 1.1 }),
  pr({ embedment: 24, soilUnitWeight: 110, footingLength: 60, footingWidth: 60 }),
  pr({ embedment: 24, soilUnitWeight: 110, footingLength: 60, footingWidth: 60, V: 4, M: 200 }),
  pr({ embedment: 24 }),                                                              // cover without unit weight
  pr({ footingThickness: 0, footingLength: undefined, footingWidth: undefined, P: 6, M: 30 }),  // pier on soil
  pr({ footingThickness: 0, footingLength: undefined, footingWidth: undefined, P: 6, M: 30, method: "LRFD" }),
  pr({ plateLength: undefined, plateWidth: undefined }),                              // punching skipped
  pr({ plateLength: 0, plateWidth: 12 }),
  pr({ footingThickness: 5, P: 80, M: 0 }),                                            // thin footing, punching
  pr({ footingThickness: 3, P: 60, M: 0 }),                                            // dEff floor of 1
  pr({ footingThickness: 18, P: 120, M: 0, footingLength: 60, footingWidth: 60 }),
  pr({ footingThickness: 18, P: 120, M: 0, footingLength: 60, footingWidth: 60, method: "LRFD" }),
  pr({ plateLength: 20, plateWidth: 8, P: 40, M: 0 }),                                // rectangular plate, beta > 1
  pr({ plateLength: 8, plateWidth: 20, P: 40, M: 0, method: "LRFD" }),
  pr({ P: 400, M: 0 }),                                                                // pier bearing / soil fail
  pr({ P: 2000, M: 0, allowableBearing: 100 }),
  pr({ P: 0, M: 0, V: 0 }),                                                            // self weight only
  pr({ P: 0, M: 0, V: 0, footingThickness: 0, footingLength: undefined, footingWidth: undefined }),
  pr({ M: -96, V: 1 }),
  pr({ pierHeight: 60, M: 0, V: 6, footingLength: 30, footingWidth: 30 }),            // tall pier, small footing
  pr({ footingLength: 12, footingWidth: 12 }),                                         // footing smaller than pier
  pr({ footingLength: 72, footingWidth: 40, M: 300, P: 25 }),
  pr({ allowableBearing: 0.5 }),
  // errors
  pr({ pierLength: 0 }),
  pr({ pierHeight: 0 }),
  pr({ fc: 0 }),
  pr({ allowableBearing: 0 }),
];

dump("weld", "structural.fillet-weld", run(filletWeld, weld));
dump("baseplate", "structural.baseplate-anchorage", run(basePlateAnchorage, baseplate));
dump("pier", "structural.pier-soil", run(pierSoil, pier));
