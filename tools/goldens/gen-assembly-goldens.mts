// Golden generator for the pipe-support assembly port. Usage (from the main checkout):
//   cd /c/dev/projects/pipecalcpro && npx tsx <this file> <out.json>
import { writeFileSync } from "node:fs";
import { analyzeAssembly, CSA_PRESETS } from "../packages/calc-core/src/structural/support-assembly.ts";
import { sectionFromRow } from "../packages/calc-core/src/structural/aisc-section.ts";
import { findShape } from "../packages/code-data-service/src/datasets/aisc-shapes.ts";

const resolve = (l: string) => sectionFromRow(findShape(l)!);
const outFile = process.argv[2];
type C = Record<string, any>;
const A36 = { Fy: 36, Fu: 58 };
const A992 = { Fy: 50, Fu: 65 };
const A500B = { Fy: 46, Fu: 58 };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const P1 = clone(CSA_PRESETS["csa-type-1"]!) as C;
const P2 = clone(CSA_PRESETS["csa-type-2"]!) as C;
const pier = { pierLength: 16, pierWidth: 16, pierHeight: 24, fc: 4000, footingLength: 36, footingWidth: 36, footingThickness: 12, allowableBearing: 3, frictionCoefficient: 0.35 };
const bigPier = { ...pier, footingLength: 84, footingWidth: 84, footingThickness: 18 };
const cast = { ...P1.baseplate, anchorType: "cast-in", anchorEmbedment: 12, anchorEdgeDistance: 7.5, bondStrength: undefined, pierLength: 36, pierWidth: 36 };
const bigBp = { ...P1.baseplate, plateLength: 16, plateWidth: 16, plateThickness: 1.5, anchorSpacingLength: 12, anchorSpacingWidth: 12, pierLength: 36, pierWidth: 36, anchorEdgeDistance: 12, anchorEmbedment: 10 };

const t1 = (o: C = {}): C => ({ method: "LRFD", tag: "PS-101", material: A36, ...P1, pier: bigPier, arms: [{ shape: "W6X15", elevation: 96, projection: 24, pipes: [{ tag: "6-P-1201", offset: 8, vertical: 1.2, transverse: 0.2 }, { tag: "6-P-1202", offset: 18, vertical: 1.5, transverse: 0.25 }] }], ...o });
const t2 = (o: C = {}): C => ({ method: "LRFD", tag: "PS-202", material: A36, ...P2, arms: [
  { shape: "L4X3X3/8", elevation: 96, projection: 36, pipes: [{ offset: 24, vertical: 0.8, longitudinal: 0.2 }] },
  { shape: "L4X3X3/8", elevation: 66, projection: 36, pipes: [{ offset: 24, vertical: 0.6, longitudinal: 0.4 }] }], ...o });
const arm1 = (shape: string, p: C[], o: C = {}) => [{ shape, elevation: 96, projection: 24, pipes: p, ...o }];
const pipe = (offset: number, vertical: number, transverse?: number, longitudinal?: number, tag?: string) => ({ tag, offset, vertical, transverse, longitudinal });

const cases: C[] = [
  // --- CSA type 1 (t-post) baseline & variants
  t1({ pier }),
  t1(),
  t1({ method: "ASD", pier }),
  t1({ method: "ASD" }),
  t1({ pier: undefined }),
  t1({ baseplate: undefined, pier: undefined }),
  t1({ baseplate: undefined }),
  t1({ pier: bigPier }),
  t1({ pier: bigPier, arms: arm1("W6X15", [pipe(18, 15, 2)]) }),
  t1({ lateralLoad: 1.0 }),
  t1({ lateralLoad: -1.5, method: "ASD" }),
  t1({ columnSelfWeight: 0.3 }),
  t1({ columnK: 1.0 }),
  t1({ columnK: 2.1 }),
  t1({ columnK: 1.2, method: "ASD", pier: bigPier }),
  t1({ arms: arm1("L3X3X1/4", [pipe(48, 40)], { projection: 48 }) }),   // grossly overloaded arm
  t1({ arms: arm1("W6X15", [pipe(8, 1.2, undefined, 0.5)]) }),           // longitudinal only
  t1({ arms: arm1("W6X15", [pipe(8, 1.2, 1.0)]) }),                       // transverse only
  t1({ arms: [{ shape: "W6X15", elevation: 96, projection: 24, pipes: [pipe(8, 1.2, 0.3, 0.5), pipe(18, 1.5, -0.3, -0.5)] }] }), // magnitudes
  t1({ arms: arm1("W6X15", [pipe(-10, 2, 0.5, 0.5)]) }),                  // negative offset
  t1({ arms: arm1("W6X15", [pipe(40, 2, 0.5, 0.5)]) }),                   // offset beyond projection (clamped)
  t1({ arms: arm1("W6X15", [pipe(8, 3, 1, 1), pipe(14, 3, 1, 1), pipe(20, 3, 1, 1)], { weldSize: 0.3125, deflectionLimit: 360 }) }),
  t1({ arms: arm1("W6X15", [pipe(8, 0, 0, 0)]) }),                        // zero loads
  t1({ arms: arm1("W6X15", [pipe(8, 2, 0.4, 0.3)]), weldSize: 0.1875, weldFEXX: 60 }),
  t1({ arms: arm1("W6X15", [pipe(8, 2, 0.4, 0.3)]), material: { Fy: 50, Fu: 65, E: 29500 } }),
  t1({ arms: arm1("W6X15", [pipe(12, 1.5)]), baseplate: cast, pier: bigPier }),
  t1({ arms: arm1("W6X15", [pipe(12, 6, 3, 2)]), baseplate: bigBp, pier: { ...bigPier, pierLength: 36, pierWidth: 36 }, material: A992, columnShape: "W8X31" }),
  // --- member variety
  t1({ columnShape: "W8X18", material: A992, arms: arm1("W8X18", [pipe(12, 4, 1, 0.8), pipe(20, 4, 1, 0.8)]) }),
  t1({ columnShape: "HSS4X4X1/4", material: A500B, arms: arm1("HSS4X4X1/4", [pipe(10, 1.5, 0.3, 0.2)]) }),
  t1({ columnShape: "HSS6X4X1/4", material: A500B, arms: arm1("HSS6X4X1/4", [pipe(12, 3, 0.6, 0.4)]) }),
  t1({ columnShape: "HSS6X6X3/8", material: A500B, method: "ASD", arms: arm1("HSS3X3X1/4", [pipe(12, 1, 0.2, 0.1)]) }),
  t1({ columnShape: "PIPE4STD", arms: arm1("PIPE3STD", [pipe(12, 1, 0.2, 0.2)]), material: { Fy: 35, Fu: 60 } }),
  t1({ columnShape: "PIPE6STD", arms: arm1("PIPE4XS", [pipe(12, 2, 0.5, 0.3)]), material: { Fy: 35, Fu: 60 }, method: "ASD" }),
  t1({ columnShape: "C8X11.5", arms: arm1("C6X8.2", [pipe(14, 1.2, 0.3, 0.2)]) }),
  t1({ columnShape: "W6X15", arms: arm1("L4X4X1/4", [pipe(12, 1.0, 0.2, 0.1)]) }),
  t1({ columnShape: "W12X26", material: A992, arms: arm1("L6X4X3/8", [pipe(18, 2.5, 0.5, 0.4)]) }),
  t1({ columnShape: "S6X12.5", arms: arm1("C4X5.4", [pipe(14, 1.0, 0.2, 0.1)]) }),
  // --- CSA type 2 (multi-tier)
  t2(),
  t2({ method: "ASD" }),
  t2({ pier }),
  t2({ pier: bigPier }),
  t2({ pier: bigPier, baseplate: bigBp, columnShape: "W8X31", material: A992 }),
  t2({ arms: [
    { shape: "W6X15", elevation: 96, projection: 36, pipes: [pipe(12, 2, 0.6, 0.4, "8-P-1"), pipe(30, 2.5, 0.6, 0.4, "8-P-2")] },
    { shape: "W6X15", elevation: 72, projection: 36, pipes: [pipe(12, 1.5, 0.5, 0.3)] },
    { shape: "C6X8.2", elevation: 48, projection: 30, pipes: [pipe(20, 1, 0.2, 0.2)] }], pier: bigPier }),
  t2({ arms: [{ shape: "L4X3X3/8", elevation: 96, projection: 48, pipes: [pipe(48, 5, 2, 1)] }, { shape: "L4X3X3/8", elevation: 66, projection: 48, pipes: [pipe(48, 5, 2, 1)] }] }),
  // --- cantilever
  t1({ type: "cantilever" }),
  t1({ type: "cantilever", arms: arm1("W6X15", [pipe(18, 3, 0.6, 0.5)]), method: "ASD" }),
  t1({ type: "cantilever", columnShape: undefined, columnHeight: undefined, arms: arm1("HSS4X4X1/4", [pipe(14, 1, 0.2)]), material: A500B }),
  t1({ type: "cantilever", arms: arm1("W6X15", [pipe(18, 3, 0.6)]), lateralLoad: 0.5 }),
  // --- goalpost
  t1({ type: "goalpost", columnSpacing: 60 }),
  t1({ type: "goalpost" }),
  t1({ type: "goalpost", columnSpacing: 72, method: "ASD", arms: arm1("W8X18", [pipe(30, 4, 1, 1), pipe(40, 4, 1, 1)], { projection: 60 }), columnShape: "W8X18", material: A992, pier: bigPier }),
  // --- trapeze
  t1({ type: "trapeze", columnSpacing: 48, arms: arm1("C8X11.5", [pipe(12, 3, 0.5, 0.5), pipe(36, 3, 0.5, 0.5)], { projection: 48 }), columnShape: "HSS4X4X1/4", material: A500B }),
  t1({ type: "trapeze", arms: arm1("W6X15", [pipe(12, 1, 0.1)]), baseplate: undefined, pier: undefined }),
  t1({ type: "trapeze", columnSpacing: 60, method: "ASD", pier: bigPier, arms: arm1("W10X22", [pipe(20, 5, 1.5, 1)], { projection: 40 }), columnShape: "W10X22", material: A992 }),
  // --- uplift (negative vertical / negative self-weight)
  t1({ arms: arm1("W6X15", [pipe(8, -2, 0.3)]) }),
  t1({ arms: arm1("W6X15", [pipe(8, -3, 0.5, 0.2)]), pier: bigPier, method: "ASD" }),
  t1({ arms: arm1("W6X15", [pipe(8, 1)]), columnSelfWeight: -4, baseplate: cast }),
  t1({ type: "goalpost", columnSpacing: 60, arms: arm1("W6X15", [pipe(8, -4, 0.5)]) }),
  // --- PR #138: J4 per-line base metal (HSS/Pipe arms = full wall, open arms = t/2), J10.1 column-flange local bending
  t1({ arms: arm1("HSS4X4X1/4", [pipe(12, 2, 0.4, 0.3)]) }),                                         // HSS arm, loaded width 4 in >= 0.15 bf, near top x0.5
  t1({ arms: arm1("HSS4X4X1/4", [pipe(12, 2, 0.4, 0.3)], { elevation: 60 }), method: "ASD" }),       // not near top
  t1({ arms: arm1("HSS5X3X1/4", [pipe(14, 1.5, 0.3, 0.2)], { elevation: 90 }) }),                    // HSS-RECT, bf 3
  t1({ arms: arm1("PIPE3STD", [pipe(14, 1.5, 0.3, 0.2)]), material: { Fy: 35, Fu: 60 } }),           // Pipe arm: width = d
  t1({ arms: arm1("PIPE2STD", [pipe(10, 1.0, 0.2, 0.1)], { elevation: 70 }), material: { Fy: 35, Fu: 60 }, method: "ASD" }),
  t1({ arms: arm1("C6X8.2", [pipe(14, 1.2, 0.3, 0.2)], { elevation: 60 }) }),                        // channel arm, t/2
  t1({ arms: arm1("L4X3X3/8", [pipe(18, 1.5, 0.3, 0.2)], { elevation: 60 }) }),                      // angle arm
  t1({ arms: arm1("WT4X9", [pipe(12, 1.0, 0.2, 0.1)], { elevation: 50 }) }),                         // tee arm
  t1({ arms: arm1("W6X9", [pipe(12, 1.5, 0.3, 0.2)], { elevation: 60 }) }),                          // thin web: min(tw, tf of column)
  t1({ arms: arm1("W6X15", [pipe(12, 1.5, 0.3, 0.2)], { elevation: 94 }) }),                         // 2 in below top: near-top branch
  t1({ arms: arm1("W6X15", [pipe(12, 1.5, 0.3, 0.2)], { elevation: 84 }) }),                         // 12 in below top, > 10 tf = 2.6
  t1({ arms: arm1("W6X15", [pipe(12, 1.5, 0.3, 0.2)], { elevation: 90 }), columnShape: "W12X26", material: A992 }), // 10 tf = 3.8, 6 in below: not near
  t1({ arms: arm1("W6X15", [pipe(12, 1.5, 0.3, 0.2)], { elevation: 93 }), columnShape: "W12X26", material: A992 }), // 3 in < 3.8: near
  // J10.1 not required: loaded width < 0.15 bf
  t1({ columnShape: "W14X90", material: A992, arms: arm1("L3X3X1/4", [pipe(12, 1.5, 0.3, 0.2)]), baseplate: undefined, pier: undefined }),
  t1({ columnShape: "W14X90", material: A992, arms: arm1("L3X3X1/4", [pipe(12, 1.5, 0.3, 0.2)], { elevation: 60 }), baseplate: undefined, pier: undefined, method: "ASD" }),
  t1({ columnShape: "W14X90", material: A992, arms: arm1("W6X9", [pipe(12, 1.5, 0.3, 0.2)]), baseplate: bigBp, pier: { ...bigPier, pierLength: 36, pierWidth: 36 } }),
  t1({ columnShape: "W14X90", material: A992, arms: arm1("HSS2X2X1/4", [pipe(12, 1.0, 0.2, 0.1)]), baseplate: undefined, pier: undefined }),
  t1({ columnShape: "W14X90", material: A992, arms: arm1("PIPE2STD", [pipe(12, 1.0, 0.2, 0.1)]), baseplate: undefined, pier: undefined }),
  t1({ columnShape: "W14X90", material: A992, arms: [
    { shape: "L3X3X1/4", elevation: 96, projection: 24, pipes: [pipe(12, 1, 0.2, 0.1)] },
    { shape: "HSS4X4X1/4", elevation: 70, projection: 24, pipes: [pipe(12, 1, 0.2, 0.1)] },
    { shape: "C6X8.2", elevation: 40, projection: 24, pipes: [pipe(12, 1, 0.2, 0.1)] }], baseplate: undefined, pier: undefined }),
  // J10.1 / J4 failing, big loads and thin flanges
  t1({ arms: arm1("W6X15", [pipe(24, 8, 4, 2)]), baseplate: undefined, pier: undefined }),
  t1({ arms: arm1("W6X15", [pipe(24, 8, 4, 2)], { elevation: 50 }), baseplate: undefined, pier: undefined, method: "ASD" }),
  t1({ arms: arm1("HSS4X4X1/4", [pipe(24, 6, 6, 1)], { elevation: 50 }), baseplate: undefined, pier: undefined }),
  t1({ arms: arm1("W6X9", [pipe(24, 5, 8, 0)], { weldSize: 0.375, elevation: 50 }), baseplate: undefined, pier: undefined }),
  t1({ arms: arm1("W6X15", [pipe(20, 3, 12, 0)], { elevation: 50 }), baseplate: undefined, pier: undefined }),   // large axial tension on the flange face
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)], { weldSize: 0.1875 }), weldSize: 0.1875 }),
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)], { weldSize: 0.5 }), weldSize: 0.5 }),                       // oversize fillet
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)]), material: { Fy: 50, Fu: 65 }, columnShape: "W8X31" }),
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)]), weldFEXX: 60, weldSize: 0.3125 }),
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)]), columnShape: "C8X11.5", baseplate: undefined, pier: undefined }),     // channel column
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)]), columnShape: "HSS6X4X1/4", material: A500B, baseplate: undefined, pier: undefined }),   // HSS column: no J10.1
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)]), columnShape: "PIPE4STD", material: { Fy: 35, Fu: 60 }, baseplate: undefined, pier: undefined }), // Pipe column
  t1({ arms: arm1("W6X15", [pipe(12, 2, 0.4, 0.3)]), columnShape: "S6X12.5", baseplate: undefined, pier: undefined }),
  // column-to-base-plate weld base part = min(column thinnest element, plate)
  t1({ baseplate: { ...P1.baseplate, plateThickness: 0.125 }, pier: bigPier }),                       // plate thinner than column elements
  t1({ baseplate: { ...P1.baseplate, plateThickness: 0.1875 }, pier: bigPier, method: "ASD" }),
  t1({ baseplate: { ...P1.baseplate, plateThickness: 0.5 }, pier: bigPier }),
  t1({ baseplate: { ...P1.baseplate, plateThickness: 2 }, pier: bigPier }),
  t1({ columnShape: "HSS6X4X1/4", material: A500B, baseplate: { ...P1.baseplate, plateThickness: 0.125 }, pier: bigPier }),
  t1({ columnShape: "PIPE4STD", material: { Fy: 35, Fu: 60 }, baseplate: { ...P1.baseplate, plateThickness: 1.0 }, pier: bigPier }),
  t1({ columnShape: "W8X31", material: A992, baseplate: bigBp, pier: { ...bigPier, pierLength: 36, pierWidth: 36 } }),
  // arm weldSize per arm, mixed arms, cantilever / goalpost / trapeze with HSS and Pipe arms
  t2({ arms: [
    { shape: "HSS4X4X1/4", elevation: 96, projection: 36, weldSize: 0.1875, pipes: [pipe(24, 0.8, 0.2, 0.2)] },
    { shape: "PIPE3STD", elevation: 66, projection: 36, weldSize: 0.3125, pipes: [pipe(24, 0.6, 0.2, 0.4)] },
    { shape: "WT4X9", elevation: 40, projection: 30, pipes: [pipe(20, 0.5, 0.1, 0.1)] }], material: { Fy: 36, Fu: 58 } }),
  t1({ type: "cantilever", arms: arm1("PIPE3STD", [pipe(14, 1, 0.2, 0.2)]), material: { Fy: 35, Fu: 60 } }),
  t1({ type: "cantilever", arms: arm1("C6X8.2", [pipe(14, 1, 0.2, 0.2)]) }),
  t1({ type: "goalpost", columnSpacing: 60, arms: arm1("HSS4X4X1/4", [pipe(20, 4, 1, 1)], { elevation: 60 }), columnShape: "W8X18", material: A992 }),
  t1({ type: "trapeze", columnSpacing: 48, arms: arm1("PIPE3STD", [pipe(12, 2, 0.5, 0.5)], { projection: 48 }), columnShape: "HSS4X4X1/4", material: { Fy: 46, Fu: 58 } }),
  // --- 2026-10-26 P.E. rulings: WT stem orientation, header stage, psi_cp,N, J10.1 width note
  t1({ arms: arm1("WT5X11", [pipe(20, 1.5)]) }),                                                   // default stem down = compression
  t1({ arms: arm1("WT5X11", [pipe(20, 1.5)], { stemOrientation: "down" }) }),
  t1({ arms: arm1("WT5X11", [pipe(20, 1.5)], { stemOrientation: "up" }), method: "ASD" }),
  t1({ arms: arm1("WT4X9", [pipe(12, 1.0, 0.2, 0.1)], { elevation: 50, stemOrientation: "up" }) }),
  t1({ type: "goalpost", columnSpacing: 60, arms: arm1("W6X15", [pipe(20, 3), pipe(40, 1)]) }),   // header, unequal reactions
  t1({ type: "goalpost", columnSpacing: 60, arms: arm1("W6X15", [pipe(20, 2, 0.3, 0.4), pipe(40, 2, 0.3, 0.4)]) }), // symmetric, biaxial
  t1({ type: "goalpost", columnSpacing: 240, arms: arm1("W6X15", [pipe(120, 2)]), baseplate: undefined, pier: undefined }), // long span LTB
  t1({ type: "goalpost", columnSpacing: 24, arms: arm1("WT5X11", [pipe(12, 1)], { stemOrientation: "down" }) }),  // WT header: stem in tension
  t1({ type: "goalpost", columnSpacing: 24, arms: arm1("WT5X11", [pipe(12, 1)], { stemOrientation: "up" }), method: "ASD" }),
  t1({ type: "trapeze", columnSpacing: 48, arms: arm1("C8X11.5", [pipe(10, 3, 0.5, 0.5), pipe(40, 1, 0.5, 0.5)], { projection: 48, deflectionLimit: 360 }), columnShape: "HSS4X4X1/4", material: A500B }),
  t1({ type: "trapeze", columnSpacing: 60, arms: arm1("W6X15", [pipe(70, 2)]) }),                 // offset beyond span: clamped
  t1({ type: "goalpost", columnSpacing: 60, arms: arm1("W6X15", [pipe(30, 0)]) }),                // zero loads
  t1({ type: "goalpost", columnSpacing: 0 }),                                                      // zero spacing = not checked
  t1({ type: "multi-tier", columnSpacing: 60, arms: [
    { shape: "W6X15", elevation: 96, projection: 24, pipes: [pipe(12, 2, 0.6, 0.4)] },
    { shape: "WT5X11", elevation: 60, projection: 24, pipes: [pipe(12, 1.5)] }] }),                 // spacing ignored on a single column
  t1({ baseplate: { ...P1.baseplate, cracked: false }, pier: bigPier }),                           // uncracked, default cac
  t1({ baseplate: { ...P1.baseplate, cracked: false, cac: 10 }, pier: bigPier, method: "ASD" }),
  t1({ baseplate: { ...P1.baseplate, cracked: false, anchorType: "post-installed-mechanical", bondStrength: undefined }, pier: bigPier }),
  t1({ baseplate: { ...cast, cracked: false }, pier: bigPier }),                                   // cast-in: psi_cp,N stays 1
  t1({ weldSize: 0.375 }),                                                                         // J10.1 runs: tw + 2w = 0.98 > 0.15 bf
  t1({ weldSize: 0.375, arms: arm1("HSS4X4X1/4", [pipe(12, 2, 0.4, 0.3)]) }),                     // non-open width note
  // error ordering: the column is resolved BEFORE the arms
  t1({ columnShape: undefined, arms: arm1("ALSO-NOT", [pipe(12, 1, 0.2)]) }),
  t1({ type: "cantilever", columnShape: "NOT-A-SHAPE" }),                                           // cantilever never resolves the column
  t1({ columnShape: undefined, columnHeight: 0 }),                                                   // columnHeight error precedes
  // --- 2026-11-01: ACI CODE-318-25 anchorage, kds = 1.0 welds, F10.2 angle arms
  t1({ baseplate: { ...P1.baseplate, aciEdition: "318-19" }, pier: bigPier }),
  t1({ baseplate: { ...P1.baseplate, aciEdition: "318-19" }, pier: bigPier, method: "ASD" }),
  t1({ baseplate: { ...P1.baseplate, anchorCategory: 1 }, pier: bigPier }),
  t1({ baseplate: { ...P1.baseplate, anchorCategory: 2, anchorFya: 36, groutPad: true }, pier: bigPier }),
  t1({ baseplate: { ...P1.baseplate, anchorageRedundancy: "redundant", anchorCategory: 1 }, pier: bigPier }),
  t1({ arms: arm1("W6X15", [pipe(12, 8, 10)]), baseplate: { ...P1.baseplate }, pier: bigPier }),                       // 8 / 10 kip
  t1({ arms: arm1("W6X15", [pipe(12, 8, 10)]), baseplate: { ...P1.baseplate, anchorCategory: 1 }, pier: bigPier }),
  t1({ arms: arm1("W6X15", [pipe(12, 8, 10)]), baseplate: { ...P1.baseplate, aciEdition: "318-19" }, pier: bigPier }),
  t1({ baseplate: { ...P1.baseplate, applyCompressionField: true }, pier: bigPier }),
  t1({ baseplate: { ...P1.baseplate, bondStrengthUncracked: 1500, cracked: false }, pier: bigPier }),
  t1({ baseplate: { ...cast, aciEdition: "318-19" }, pier: { ...bigPier, aciEdition: "318-19" } }),
  t2({ arms: [{ shape: "L4X4X1/4", elevation: 96, projection: 36, pipes: [pipe(24, 0.8, 0.2, 0.2)] }, { shape: "L4X4X1/4", elevation: 66, projection: 36, pipes: [pipe(24, 0.6)] }] }),
  t2({ baseplate: { ...P2.baseplate, aciEdition: "318-19" } }),
  // --- errors
  t1({ arms: [] }),
  t1({ columnHeight: 0 }),
  t1({ columnShape: undefined }),
  t1({ type: "multi-tier", columnShape: undefined }),
  t1({ type: "cantilever", columnHeight: -5 }),
];

const out = cases.map((input) => {
  try {
    const r = analyzeAssembly(input as any, resolve);
    return { input, output: r.output, status: r.status, warnings: r.warnings };
  } catch (e) {
    return { input, error: (e as Error).message };
  }
});
const json = JSON.stringify({ module: "structural.support-assembly", cases: out },
  (_k, v) => (typeof v === "number" && !Number.isFinite(v) ? (Number.isNaN(v) ? "NaN" : v > 0 ? "Infinity" : "-Infinity") : v), 2);
writeFileSync(outFile, json + "\n");
console.log(out.length, "cases;", out.filter((c: any) => c.error).length, "errors");
for (const [i, c] of out.entries()) console.log(i, (c as any).error ?? `${(c as any).status} gov=${(c as any).output.governingRatio} ${(c as any).output.governingStage} | ${(c as any).output.summary.pass}/${(c as any).output.summary.fail}/${(c as any).output.summary.na}`);
