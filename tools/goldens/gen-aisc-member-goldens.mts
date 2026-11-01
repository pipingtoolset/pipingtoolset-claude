import { writeFileSync } from "node:fs";
import { findShape } from "../packages/code-data-service/src/index.ts";
import { sectionFromRow } from "../packages/calc-core/src/structural/aisc-section.ts";
import { aiscMemberDesign, simpleSpanDeflection, cantileverDeflection } from "../packages/calc-core/src/structural/aisc-member.ts";
import { cbFromMoments } from "../packages/calc-core/src/structural/aisc-strength.ts";

const A992 = { Fy: 50, Fu: 65 }, A36 = { Fy: 36, Fu: 58 }, HSS = { Fy: 46, Fu: 58 };
const del = "__del__";
function sec(label: string, over: Record<string, unknown> = {}): any {
  const row = findShape(label);
  if (!row) throw new Error("no shape " + label);
  const s: any = { ...sectionFromRow(row as any), ...over };
  for (const k of Object.keys(s)) if (s[k] === undefined || s[k] === del) delete s[k];
  return s;
}
type Case = { name: string; input: any };
const cases: Case[] = [];
const add = (name: string, section: any, material: any, method: "LRFD" | "ASD", rest: any) =>
  cases.push({ name, input: { section, material, method, ...rest } });

// ---- I-shapes
add("W12X40 LRFD braced compact", sec("W12X40"), A992, "LRFD", { Lx: 72, Ly: 72, Lb: 1, demand: { P: 100, Mx: 1500, Vx: 20 } });
add("W12X40 ASD braced compact", sec("W12X40"), A992, "ASD", { Lx: 72, Ly: 72, Lb: 1, demand: { P: 67, Mx: 1000, Vx: 14 } });
for (const lb of [24, 60, 100, 144, 240, 420, 600]) {
  add(`W12X40 LRFD Lb=${lb} in sweep`, sec("W12X40"), A992, "LRFD", { Lx: lb, Lb: lb, demand: { Mx: 800, Vx: 10 } });
  add(`W12X40 ASD Lb=${lb} in sweep`, sec("W12X40"), A992, "ASD", { Lx: lb, Lb: lb, demand: { Mx: 600, My: 20 } });
}
add("W12X40 Lb 144 Cb 1.67", sec("W12X40"), A992, "LRFD", { Lx: 144, Lb: 144, Cb: 1.67, demand: { Mx: 1200 } });
add("W12X40 Lb 480 Cb computed", sec("W12X40"), A992, "LRFD", { Lx: 480, Lb: 480, Cb: cbFromMoments(100, 80, 60, 90), demand: { Mx: 900 } });
add("W6X15 noncompact flange", sec("W6X15"), A992, "LRFD", { Lx: 96, Lb: 96, Kx: 2.1, Ky: 2.1, demand: { P: 12, Mx: 288, Vx: 2.5, deflection: 0.15 }, span: 96, deflectionLimit: 240 });
add("W8X10 noncompact flange + slender web", sec("W8X10"), A992, "LRFD", { Lx: 100, Lb: 100, demand: { P: 5, Mx: 120, My: 5, Vx: 3 } });
add("W14X90 noncompact", sec("W14X90"), A992, "ASD", { Lx: 150, Lb: 50, demand: { P: 300, Mx: 1200, Vy: 40 } });
add("W44X335 axial slender web", sec("W44X335"), HSS, "LRFD", { Lx: 400, Ly: 400, Lb: 400, demand: { P: 200, Mx: 3000, Vx: 100 } });
add("W10X12 axial slender", sec("W10X12"), HSS, "ASD", { Lx: 120, Lb: 120, demand: { P: 8, Mx: 150 } });
add("W16X26 biaxial", sec("W16X26"), A992, "LRFD", { Lx: 120, Ly: 60, Lb: 60, demand: { P: 40, Mx: 600, My: 60, Vx: 10, Vy: 5 } });
add("W21X44 heavy shear", sec("W21X44"), A992, "LRFD", { Lx: 200, Lb: 100, demand: { Mx: 2000, Vx: 120, Vy: 30 } });
add("W12X40 KL/r > 200", sec("W12X40"), A992, "LRFD", { Lx: 400, Ly: 400, Kx: 2.1, Ky: 2.1, demand: { P: 10 } });
add("W12X40 tension bolted An U", sec("W12X40"), A992, "LRFD", { Lx: 100, An: 9.5, U: 0.85, demand: { P: 400, axialTension: true } });
add("W12X40 tension ASD", sec("W12X40"), A992, "ASD", { Lx: 100, demand: { P: 250, axialTension: true, Mx: 400 } });
add("W12X40 tension L/r > 300", sec("W12X40"), A992, "LRFD", { Lx: 700, Ly: 700, demand: { P: 20, axialTension: true } });
add("W12X40 H1-1b small P", sec("W12X40"), A992, "LRFD", { Lx: 120, Lb: 120, demand: { P: 10, Mx: 900, Vx: 15 } });
add("W12X40 H1-1a large P fail", sec("W12X40"), A992, "LRFD", { Lx: 120, Lb: 120, demand: { P: 450, Mx: 900 } });
add("W12X40 all-zero demand", sec("W12X40"), A992, "LRFD", { Lx: 120, demand: {} });
add("W12X40 separate Lz Kz", sec("W12X40"), A992, "LRFD", { Lx: 120, Ly: 90, Lz: 60, Kz: 0.8, Lb: 30, demand: { P: 80, Mx: 300 } });
add("W12X40 E G override", sec("W12X40"), { Fy: 50, Fu: 65, E: 30000, G: 11500 }, "LRFD", { Lx: 300, Lb: 300, demand: { P: 50, Mx: 500 } });
add("W12X40 deflection pass L/360", sec("W12X40"), A992, "LRFD", { Lx: 240, Lb: 240, span: 240, deflectionLimit: 360, demand: { Mx: 500, deflection: 0.5 } });
add("W12X40 deflection fail default", sec("W12X40"), A992, "LRFD", { Lx: 240, Lb: 240, demand: { Mx: 500, deflection: 2.0 } });
add("W12X40 no rts fallback", sec("W12X40", { rts: del }), A992, "LRFD", { Lx: 240, Lb: 240, demand: { Mx: 500 } });
add("W12X40 zero Zx -> infinite ratio", sec("W12X40", { Zx: 0 }), A992, "LRFD", { Lx: 72, Lb: 1, demand: { Mx: 100 } });
add("S24X80 axial slender web", sec("S24X80"), HSS, "LRFD", { Lx: 300, demand: { P: 100, Mx: 2000, Vx: 60 } });
add("HP14X73 slender flange axial", sec("HP14X73"), HSS, "LRFD", { Lx: 150, demand: { P: 200, Mx: 600, My: 50 } });
add("M12X10.8 slender web", sec("M12X10.8"), A36, "ASD", { Lx: 100, demand: { P: 6, Mx: 100 } });
add("built-up I noncompact web", sec("W12X40", { builtUp: true, htw: 100 }), A992, "LRFD", { Lx: 180, Lb: 180, demand: { P: 100, Mx: 900, Vx: 20 } });
add("built-up I slender web", sec("W12X40", { builtUp: true, htw: 160 }), A992, "LRFD", { Lx: 180, Lb: 180, demand: { P: 60, Mx: 800, Vx: 20 } });
add("built-up I slender flange", sec("W12X40", { builtUp: true, bf2tf: 30, htw: 50 }), A992, "ASD", { Lx: 180, Lb: 180, demand: { P: 60, Mx: 500, My: 10 } });
add("built-up I noncompact flange", sec("W12X40", { builtUp: true, bf2tf: 14, htw: 60 }), A992, "LRFD", { Lx: 180, Lb: 90, demand: { P: 100, Mx: 900 } });
add("W12X40 htw noncompact web (F4)", sec("W12X40", { htw: 110 }), A992, "LRFD", { Lx: 120, Lb: 24, demand: { Mx: 1200, Vx: 20 } });
add("W12X40 htw slender web (F5)", sec("W12X40", { htw: 170 }), A992, "ASD", { Lx: 120, Lb: 24, demand: { P: 30, Mx: 900, Vx: 15 } });
add("C10X15.3 slender flange", sec("C10X15.3", { bf2tf: 30 }), A36, "LRFD", { Lx: 100, Lb: 40, demand: { Mx: 100, My: 10 } });
add("C10X15.3 noncompact flange minor F6-2", sec("C10X15.3", { bf2tf: 20 }), A36, "LRFD", { Lx: 100, Lb: 40, demand: { Mx: 100, My: 10 } });
add("W12X40 torsional buckling E4-2", sec("W12X40", { Cw: 1, J: 0.01 }), A992, "LRFD", { Lx: 100, Ly: 100, Lz: 100, demand: { P: 5 } });
// ---- channels
add("C10X15.3 major flexure + compress", sec("C10X15.3"), A36, "LRFD", { Lx: 72, Lb: 72, demand: { P: 20, Mx: 200, Vx: 10 } });
add("C12X30 minor + FTB", sec("C12X30"), A36, "ASD", { Lx: 120, Ly: 120, Lz: 120, demand: { P: 30, Mx: 100, My: 30, Vy: 8 } });
add("C10X15.3 elastic LTB", sec("C10X15.3"), A36, "ASD", { Lx: 300, Lb: 300, demand: { Mx: 100 } });
add("MC12X10.6 slender web", sec("MC12X10.6"), A36, "LRFD", { Lx: 150, demand: { P: 10, Mx: 80 } });
add("C15X50 tension", sec("C15X50"), A36, "LRFD", { Lx: 200, demand: { P: 300, axialTension: true } });
// ---- tees
add("WT6X20 compress + flexure", sec("WT6X20"), A992, "LRFD", { Lx: 60, Lb: 60, demand: { P: 30, Mx: 100, Vx: 5 } });
add("WT6X20 minor + tension", sec("WT6X20"), A992, "ASD", { Lx: 60, Lb: 120, demand: { P: 50, axialTension: true, My: 40, Vy: 5 } });
add("WT4X5 noncompact flange", sec("WT4X5"), A992, "LRFD", { Lx: 48, Lb: 48, demand: { P: 3, Mx: 20 } });
add("WT7X45 noncompact", sec("WT7X45"), A992, "LRFD", { Lx: 90, Lb: 90, demand: { P: 20, Mx: 150 } });
add("WT22X184 slender stem", sec("WT22X184"), A992, "LRFD", { Lx: 200, Lb: 200, demand: { P: 100, Mx: 800 } });
add("WT6X20 Lb tiny", sec("WT6X20"), A992, "LRFD", { Lx: 60, Lb: 0.001, demand: { Mx: 50 } });
// ---- tees, stem orientation (2026-10-26: F9 Mp = My, B < 0, F9.4 stem local buckling)
add("WT5X11 A36 stem in compression Lb 24", sec("WT5X11"), A36, "LRFD", { Lx: 24, Ly: 24, Lb: 24, Kx: 2.1, Ky: 2.1, stemInCompression: true, demand: { Mx: 40, Vx: 2 } });
add("WT5X11 A36 stem in tension explicit", sec("WT5X11"), A36, "LRFD", { Lx: 24, Lb: 24, stemInCompression: false, demand: { Mx: 40, Vx: 2 } });
add("WT5X11 A36 stem compression long Lb ASD", sec("WT5X11"), A36, "ASD", { Lx: 240, Lb: 240, stemInCompression: true, demand: { Mx: 20, P: 2 } });
add("WT6X20 A992 stem compression F9-18 branch", sec("WT6X20"), A992, "LRFD", { Lx: 60, Lb: 60, stemInCompression: true, demand: { P: 30, Mx: 100, Vx: 5 } });
add("WT6X20 thin stem F9-19 branch", sec("WT6X20", { tw: 0.12 }), A992, "LRFD", { Lx: 60, Lb: 60, stemInCompression: true, demand: { Mx: 60 } });
add("WT22X184 slender stem compression", sec("WT22X184"), A992, "LRFD", { Lx: 200, Lb: 200, stemInCompression: true, demand: { P: 100, Mx: 800 } });
add("WT4X5 noncompact flange, stem compression", sec("WT4X5"), A992, "LRFD", { Lx: 48, Lb: 48, stemInCompression: true, demand: { P: 3, Mx: 20 } });
add("WT4X5 noncompact flange, stem tension explicit ASD", sec("WT4X5"), A992, "ASD", { Lx: 48, Lb: 48, stemInCompression: false, demand: { P: 3, Mx: 20 } });
// ---- angles
add("L4X3X3/8 ASD", sec("L4X3X3/8"), A36, "ASD", { Lx: 48, Lb: 48, demand: { P: 3, Mx: 144, Vx: 0.5 } });
add("L4X3X3/8 tension default U", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, demand: { P: 30, axialTension: true } });
add("L4X3X3/8 tension U given", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, U: 0.8, An: 2.2, demand: { P: 30, axialTension: true } });
add("L6X6X1/2 slender leg compress", sec("L6X6X1/2"), A36, "LRFD", { Lx: 60, demand: { P: 20, Mx: 60, My: 20, Vx: 3 } });
add("L8X8X1/2 noncompact leg", sec("L8X8X1/2"), A36, "LRFD", { Lx: 100, demand: { P: 20, Mx: 300, My: 100 } });
add("L2X2X1/8 thin legs", sec("L2X2X1/8"), A36, "ASD", { Lx: 24, demand: { P: 1, Mx: 4 } });
add("L8X8X1 compact", sec("L8X8X1"), A36, "LRFD", { Lx: 150, demand: { P: 100, Mx: 400, Vx: 20, Vy: 20 } });
add("L6X6 slender leg flexure F10-7", sec("L6X6X1/2", { tw: 0.2, tf: 0.2 }), A36, "LRFD", { Lx: 60, demand: { P: 5, Mx: 30, My: 10 } });
// ---- HSS rect/square
add("HSS4X4X1/4 LRFD", sec("HSS4X4X1/4"), HSS, "LRFD", { Lx: 72, Lb: 72, demand: { P: 20, Mx: 200, Vx: 5 } });
add("HSS6X6X3/16 noncompact flange", sec("HSS6X6X3/16"), HSS, "LRFD", { Lx: 96, Lb: 96, demand: { P: 20, Mx: 150, My: 30, Vx: 4, Vy: 4 } });
add("HSS12X12X1/4 slender", sec("HSS12X12X1/4"), HSS, "LRFD", { Lx: 240, demand: { P: 80, Mx: 800, My: 100, Vx: 20 } });
add("HSS12X8X3/16 slender flange noncompact web", sec("HSS12X8X3/16"), HSS, "ASD", { Lx: 200, demand: { P: 30, Mx: 300, My: 80, Vx: 10, Vy: 10 } });
add("HSS12X4X3/16 noncompact web", sec("HSS12X4X3/16"), HSS, "LRFD", { Lx: 150, demand: { P: 15, Mx: 250, My: 20, Vx: 8, Vy: 3 } });
add("HSS10X6X3/16 noncompact", sec("HSS10X6X3/16"), HSS, "LRFD", { Lx: 150, demand: { P: 15, Mx: 150, My: 40 } });
add("HSS6X6X3/8 compact tension", sec("HSS6X6X3/8"), HSS, "LRFD", { Lx: 100, demand: { P: 120, axialTension: true, Mx: 100 } });
// ---- HSS round / pipe
add("PIPE4STD", sec("PIPE4STD"), HSS, "LRFD", { Lx: 72, Lb: 72, demand: { P: 20, Mx: 100, Vx: 3 } });
add("HSS6.625X0.280", sec("HSS6.625X0.280"), HSS, "ASD", { Lx: 144, demand: { P: 15, Mx: 150, My: 30, Vy: 3 } });
add("HSS12.75X0.250 noncompact wall", sec("HSS12.75X0.250"), HSS, "LRFD", { Lx: 240, demand: { P: 50, Mx: 800 } });
add("HSS12.75X0.188 E7-7", sec("HSS12.75X0.188"), HSS, "LRFD", { Lx: 240, demand: { P: 50, Mx: 500, Vx: 10 } });
add("round HSS slender flexure + E7-7", sec("HSS12.75X0.188", { tw: 0.06, htw: del, A: 2.3, Ix: 45, Sx: 7, Zx: 9, rx: 4.4, Iy: 45, Sy: 7, Zy: 9, ry: 4.4 }), HSS, "LRFD", { Lx: 200, demand: { P: 5, Mx: 60 } });
add("round HSS D/t beyond E7", sec("HSS12.75X0.188", { d: 20, tw: 0.06, htw: del, A: 3.7, Ix: 180, Sx: 18, Zx: 24, rx: 7, Iy: 180, Sy: 18, Zy: 24, ry: 7 }), HSS, "ASD", { Lx: 300, demand: { P: 4, Mx: 80 } });
add("PIPE4STD no J", sec("PIPE4STD", { J: del }), HSS, "LRFD", { Lx: 72, demand: { P: 20 } });

// ---- 2026-11-01 AISC 360-22 conformance
add("L4X3X3/8 ASD continuousLTR", sec("L4X3X3/8"), A36, "ASD", { Lx: 48, Lb: 48, continuousLTR: true, demand: { P: 3, Mx: 144, Vx: 0.5 } });
add("L4X3X3/8 LRFD F10.2 principal", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, Lb: 48, demand: { Mx: 60, My: 10 } });
add("L4X4X1/4 equal leg geometric", sec("L4X4X1/4"), A36, "LRFD", { Lx: 60, Lb: 60, demand: { Mx: 40 } });
add("L4X4X1/4 equal leg + axial", sec("L4X4X1/4"), A36, "LRFD", { Lx: 60, Lb: 60, Kx: 1, Ky: 1, demand: { P: 5, Mx: 20 } });
add("L4X4X1/4 equal leg Cb 2 capped", sec("L4X4X1/4"), A36, "LRFD", { Lx: 60, Lb: 60, Cb: 2, demand: { Mx: 40 } });
add("L8X8X1/2 long Lb F10-3", sec("L8X8X1/2"), A36, "LRFD", { Lx: 400, Lb: 400, demand: { Mx: 100 } });
add("L4X3X3/8 E5 planar long leg", sec("L4X3X3/8"), A36, "LRFD", { Lx: 72, angleE5: { conditionsMet: true, truss: "planar", connectedLeg: "long" }, demand: { P: 20 } });
add("L4X3X3/8 E5 planar short leg", sec("L4X3X3/8"), A36, "LRFD", { Lx: 72, angleE5: { conditionsMet: true, truss: "planar", connectedLeg: "short" }, demand: { P: 20 } });
add("L4X3X3/8 E5 space long leg", sec("L4X3X3/8"), A36, "ASD", { Lx: 120, angleE5: { conditionsMet: true, truss: "space", connectedLeg: "long" }, demand: { P: 8 } });
add("L4X3X3/8 E5 space short leg L", sec("L4X3X3/8"), A36, "LRFD", { Lx: 60, angleE5: { conditionsMet: true, truss: "space", connectedLeg: "short", L: 50 }, demand: { P: 10 } });
add("L4X4X1/4 E5 planar equal", sec("L4X4X1/4"), A36, "LRFD", { Lx: 100, Kx: 1, Ky: 1, angleE5: { conditionsMet: true, truss: "planar", connectedLeg: "short" }, demand: { P: 10 } });
add("L8X4X1/2 E5 ratio >= 1.7", sec("L8X4X1/2"), A36, "LRFD", { Lx: 96, angleE5: { conditionsMet: true, truss: "planar", connectedLeg: "long" }, demand: { P: 20 } });
add("L2X2X1/8 E5 KL/r > 200", sec("L2X2X1/8"), A36, "LRFD", { Lx: 120, angleE5: { conditionsMet: true, truss: "planar", connectedLeg: "long" }, demand: { P: 1 } });
add("L4X3X3/8 E5 not met", sec("L4X3X3/8"), A36, "LRFD", { Lx: 72, angleE5: { conditionsMet: false, truss: "planar", connectedLeg: "long" }, demand: { P: 20 } });
add("L6X6X5/16 E4-4 FTB", sec("L6X6X5/16"), A36, "LRFD", { Lx: 30, Kx: 1, Ky: 1, demand: { P: 30 } });
add("L4X3X3/8 tension 4 bolts", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, nBoltsPerLine: 4, demand: { P: 30, axialTension: true } });
add("L4X3X3/8 tension 3 bolts", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, nBoltsPerLine: 3, demand: { P: 30, axialTension: true } });
add("L4X3X3/8 tension 2 bolts + Case 2", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, nBoltsPerLine: 2, connectionEccentricity: 0.78, connectionLength: 6, demand: { P: 30, axialTension: true } });
add("L4X3X3/8 tension Case 2 short", sec("L4X3X3/8"), A36, "ASD", { Lx: 48, connectionEccentricity: 0.78, connectionLength: 1.2, demand: { P: 20, axialTension: true } });
add("L4X3X3/8 tension 2 bolts only", sec("L4X3X3/8"), A36, "LRFD", { Lx: 48, nBoltsPerLine: 2, demand: { P: 30, axialTension: true } });
add("C10X15.3 E4-3 channel Fex", sec("C10X15.3"), A36, "LRFD", { Lx: 120, Ly: 40, Lz: 120, Kx: 1, Ky: 1, demand: { P: 30 } });
add("WT6X15 E4-3 + flexure", sec("WT6X15"), A36, "LRFD", { Lx: 96, Kx: 2.1, Ky: 2.1, demand: { P: 8, Mx: 60 } });
add("WT6X15 no ro H ybar fallback", sec("WT6X15", { ro: del, H: del }), A36, "LRFD", { Lx: 96, Kx: 1, Ky: 1, demand: { P: 8 } });
add("WT6X15 no shear-centre data", sec("WT6X15", { ro: del, H: del, ybar: del }), A36, "LRFD", { Lx: 96, Kx: 1, Ky: 1, demand: { P: 8 } });
add("WT6X15 stem tension F9-6 band", sec("WT6X15"), A36, "LRFD", { Lx: 120, Lb: 120, stemInCompression: false, demand: { Mx: 60 } });
add("WT6X15 stem tension elastic F9-7", sec("WT6X15"), A36, "LRFD", { Lx: 600, Lb: 600, stemInCompression: false, demand: { Mx: 30 } });
add("WT6X15 minor G6 one flange", sec("WT6X15"), A36, "LRFD", { Lx: 60, demand: { My: 30, Vy: 10, Vx: 5 } });
add("HSS12X4X3/16 F7.4 LTB", sec("HSS12X4X3/16"), HSS, "LRFD", { Lx: 600, Lb: 600, demand: { Mx: 300 } });
add("HSS12X4X1/4 F7.4 very long Lb", sec("HSS12X4X1/4"), HSS, "LRFD", { Lx: 6000, Lb: 6000, demand: { Mx: 100 } });
add("HSS12X12X3/16 slender E7 row b", sec("HSS12X12X3/16"), HSS, "LRFD", { Lx: 120, Kx: 1, Ky: 1, demand: { P: 100 } });
add("W14X90 noncompact flange F3-1 kc", sec("W14X90"), A992, "LRFD", { Lx: 60, Lb: 60, demand: { Mx: 2000 } });
add("W12X40 slender flange F3-2 kc rolled", sec("W12X40", { bf2tf: 30 }), A992, "LRFD", { Lx: 60, Lb: 10, demand: { Mx: 500 } });
add("W12X40 F4 long Lb elastic", sec("W12X40", { htw: 110 }), A992, "LRFD", { Lx: 600, Lb: 600, demand: { Mx: 300 } });
add("W12X40 F4 slender flange", sec("W12X40", { htw: 110, bf2tf: 30 }), A992, "LRFD", { Lx: 60, Lb: 60, demand: { Mx: 300 } });
add("W12X40 F5 inelastic LTB", sec("W12X40", { htw: 170 }), A992, "LRFD", { Lx: 150, Lb: 150, demand: { Mx: 300 } });
add("W12X40 F5 elastic LTB + FLB", sec("W12X40", { htw: 170, bf2tf: 14 }), A992, "LRFD", { Lx: 600, Lb: 600, demand: { Mx: 300 } });
add("W12X40 F6-4 slender minor", sec("W12X40", { bf2tf: 30 }), A992, "LRFD", { Lx: 60, demand: { My: 50 } });
add("W12X40 G2-11 slender web shear", sec("W12X40", { htw: 200, builtUp: true }), A992, "LRFD", { Lx: 60, demand: { Vx: 50 } });
add("C10X15.3 G6 bf/tf", sec("C10X15.3", { bf2tf: 40 }), A36, "LRFD", { Lx: 60, demand: { Vy: 10 } });
add("W12X40 K given (no K warning)", sec("W12X40"), A992, "LRFD", { Lx: 120, Kx: 1.0, Ky: 1.0, demand: { P: 100 } });
add("W12X40 Kx only", sec("W12X40"), A992, "LRFD", { Lx: 120, Kx: 2.1, demand: { P: 100 } });
add("W12X40 Ky only", sec("W12X40"), A992, "LRFD", { Lx: 120, Ky: 2.1, demand: { P: 100 } });
add("L6X6X5/16 A992 E4-4 governs", sec("L6X6X5/16"), A992, "LRFD", { Lx: 30, Kx: 1, Ky: 1, demand: { P: 30 } });
add("L8X8X1/2 A992 E4-4 short", sec("L8X8X1/2"), A992, "ASD", { Lx: 20, Kx: 1, Ky: 1, demand: { P: 30 } });
add("WT6X15 stem compression Lb 600 F9-13", sec("WT6X15"), A36, "LRFD", { Lx: 600, Lb: 600, stemInCompression: true, demand: { Mx: 10 } });
add("WT6X15 stem tension Lb 3000 F9-7", sec("WT6X15"), A36, "LRFD", { Lx: 3000, Lb: 3000, stemInCompression: false, demand: { Mx: 5 } });
add("WT6X15 slender flange F9-15", sec("WT6X15", { bf2tf: 30 }), A36, "LRFD", { Lx: 60, Lb: 1, stemInCompression: false, demand: { Mx: 20 } });
add("W12X40 F4 noncompact flange F4-13", sec("W12X40", { htw: 110, bf2tf: 14 }), A992, "LRFD", { Lx: 60, Lb: 1, demand: { Mx: 300 } });
add("W12X40 F5 slender flange F5-7", sec("W12X40", { htw: 170, bf2tf: 30 }), A992, "LRFD", { Lx: 60, Lb: 1, demand: { Mx: 300 } });
const rep = (_k: string, v: unknown) =>
  typeof v === "number" && !Number.isFinite(v) ? String(v) : v;

const member: any[] = cases.map((c) => {
  try {
    return { name: c.name, input: c.input, output: aiscMemberDesign(c.input) };
  } catch (e) {
    return { name: c.name, input: c.input, error: (e as Error).message };
  }
});

const errIn = (name: string, over: any) => {
  const input = { section: sec("W12X40"), material: A992, method: "LRFD", Lx: 72, demand: {}, ...over };
  try { aiscMemberDesign(input); member.push({ name, input, error: "NO THROW" }); }
  catch (e) { member.push({ name, input, error: (e as Error).message }); }
};
errIn("A zero", { section: sec("W12X40", { A: 0 }) });
errIn("Ix negative", { section: sec("W12X40", { Ix: -1 }) });
errIn("Fy zero", { material: { Fy: 0, Fu: 65 } });
errIn("Lx zero", { Lx: 0 });
errIn("no buckling mode", { section: sec("W12X40", { rx: 0, ry: 0, J: del }) });

const cb = [[100, 80, 60, 90], [50, 50, 50, 50], [0, 0, 0, 0], [100, 25, 50, 75], [100, 0, 0, 0]].map((a) => ({
  args: a, output: cbFromMoments(a[0]!, a[1]!, a[2]!, a[3]!) }));
const ssd = [{ w: 0.1, L: 240, I: 300, E: 29000 }, { P: 5, L: 120, I: 100 }, { w: 0.05, P: 2, L: 180, I: 50.3 }]
  .map((a) => ({ args: a, output: simpleSpanDeflection(a) }));
const cld = [{ P: 2, L: 48, I: 29.1, E: 29000 }, { w: 0.02, L: 60, I: 10 }, { w: 0.01, P: 1.5, L: 36, I: 7.7, E: 29500 }]
  .map((a) => ({ args: a, output: cantileverDeflection(a) }));
const defErr: any[] = [];
for (const [fn, name] of [[simpleSpanDeflection, "simple"], [cantileverDeflection, "cantilever"]] as const) {
  try { (fn as any)({ L: 0, I: 1 }); defErr.push({ fn: name, args: { L: 0, I: 1 }, error: "NO THROW" }); }
  catch (e) { defErr.push({ fn: name, args: { L: 0, I: 1 }, error: (e as Error).message }); }
}
const rows = ["W12X40", "PIPE4STD", "HSS4X4X1/4", "L4X3X3/8", "WT6X20", "C10X15.3", "HSS12X8X3/16", "HSS6.625X0.280"]
  .map((l) => findShape(l)).filter(Boolean)
  .map((r) => ({ row: r, output: sectionFromRow(r as any) }));

writeFileSync(process.argv[2]!, JSON.stringify({ member, cb, simpleSpan: ssd, cantilever: cld, deflectionErrors: defErr, sectionFromRow: rows }, rep, 1));
console.log("member cases", member.length, "errors", member.filter((m: any) => m.error).length);
