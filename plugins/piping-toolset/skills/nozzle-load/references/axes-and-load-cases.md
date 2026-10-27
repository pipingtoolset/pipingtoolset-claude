# Axes, sign conventions and load cases

Relocated detail for Step 0 items 2 and 3 and Steps 2 and 3 of `SKILL.md`. A load set judged in the wrong axes, at the wrong point or from the wrong load case passes silently, so this file is the part of the interview a reviewer checks first.

## 1. Axis mapping interview

The piping model reports restraint or nozzle loads in the **global** axes (or in the local axes of a node). Every allowable in the standards is stated in the **equipment's own** axes. Before any run, get these answers and write the mapping into section 2 of the calc sheet:

1. Which global direction is vertical (Y-up or Z-up in the model), and which is the plant north.
2. For each nozzle, the nozzle axis (the direction the nozzle points out of the equipment) in global terms, and the two transverse axes.
3. For the equipment's own frame, the reference axes: the shaft for a compressor, turbine or horizontal pump (x parallel to the shaft in API 617, 611 and 612; Figure E.1, I.1 and D.1 are image content: verify on the printed page), vertical, and horizontal at right angles to the shaft. For a pump, the axes of the Annex F figures (Figures 23 to 27). For an exchanger, the axes of API 660 Figure 4 or API 661 Figure 6. For a heater, API 560 Figure 1 or 2. For a vessel, the axes of the PVP2011-57100 paper: x the nozzle centreline directed out, y the vessel centreline up, z = x cross y.
4. The sign convention of the piping software's report: whether the printed load is the load **on the nozzle** (from the pipe) or the load **on the pipe** (from the nozzle); the two have opposite signs. Equipment allowables are for the load from the piping on the equipment.
5. Whether the loads are at the nozzle face, at the pipe node, or already resolved to the standard's resolution point.

Write the mapping as a short table (equipment axis, global direction, sign) and carry it to the calc sheet. The tool works in the axes it is given: it cannot detect a transposed Fy and Fz.

**Checks a reviewer applies.** A pump suction nozzle top-mounted and an end-suction nozzle have different axis maps; do not copy one pump's map to another. For compressors the shaft axis is the first axis. For moments, apply the right-hand rule to the stated axes. Mixed unit systems (ft-lbf for moments against in-lbf from the software) are a common 12x error: the tool takes moments in ft-lbf in USC, and for API 610 Annex F the SI option takes N·m.

## 2. Resolution to a common point

| Equipment | Resolution point | Source |
|---|---|---|
| Centrifugal pump | Intersection of the shaft centreline and the casing transverse centreline (pump centre C) | API 610 Annex F; PIP RECE002 4.1.2.3 |
| Compressor | Fixed end; if none, the largest nozzle | PIP RECE002 4.1.2.2; API 617 E.5 for the combined resultant |
| Steam turbine | Exhaust flange (exhaust connection centreline) | PIP RECE002 4.1.2.1; API 611 I.5, API 612 D.5 |
| Exchanger, heater, vessel, tank | The nozzle itself: the allowables are per nozzle (a sum for API 661 headers, in one common system) | API 660, 661, 560 |

Moments transfer as `M' = M + r x F`. For pump Annex F the tool does the transfer (Eq. F.5.1.1 to F.5.1.3) from the nozzle coordinates relative to C, with 12 converting inches to feet in USC and 1000 converting mm to m in SI. For all other uses, resolve the loads yourself first and state the point in the calc sheet; the sum module and the SM-23 module take what they are given.

## 3. Which load case meets which allowable

The table says what to compare in each condition; confirm the datasheet where it is silent. "Total" means the piping loads at the nozzle with weight, pressure thrust and thermal expansion together, as the piping program reports them for the case.

| Family | Case compared with the allowable | Notes |
|---|---|---|
| Pump, API 610 | Total operating loads, each operating state (the hot case with thermal), and the cold or installed state for alignment | Table 5 and Annex F values are for the loads imposed by the connected piping; hydrotest through the pump is not compared unless the vendor requires it |
| Compressor and turbine | Total operating loads for each state; **thermal included**; cold case for alignment | The vendor sheet may restrict start-up, upset or trip conditions; record what the vendor says |
| Exchanger, heater | Total loads in the **corroded condition** | API 660 7.6.9, API 661 7.1.10.1, API 560 9.2 say corroded condition; heaters also have movement limits |
| Air-cooled header | Header sum in the same case as the individual nozzles, all nozzles of the header | API 661 7.1.10.2 and 7.1.10.3 |
| Tank, Annex P | The loads from the piping flexibility analysis with the shell movement of P.2.5 applied (the manufacturer's growth and rotation) | The piping load is a result of the interaction; the purchaser gives the loads, the manufacturer judges (P.2.8) |
| Vessel, PVP2011-57100 | **Total operating loads**, forces and moments together | The paper's basis; do not split into sustained and thermal and compare each |

Rules that apply to every family:

- **Thermal is included.** The expansion-only range loads are never the whole operating load on equipment.
- **Hydrotest is excluded** unless the standard or the datasheet says to compare it (a test that fills the line with water through the equipment may require the vendor's agreement).
- **Occasional loads** (wind, seismic, relief valve thrust, slug): none of these methods gives an occasional increase; the vendor or owner states whether an event may exceed the table, and the answer goes in the calc sheet. Do not apply a 1.33 type factor on the engineer's authority.
- **Corroded condition** where the standard says so. The loads come from the corroded model; a new-condition run is not the required basis.
- **Friction.** State whether the loads include support friction. Compare both the friction and the no-friction runs when the case set provides both; the governing one is stated.
- **Cold spring** is not permitted where PIP RECE002 is invoked (4.3.1.9); it never reduces the nozzle load credited in the calc.
- **Installed conditions.** Loads when the pipe is connected at the nozzle in the cold state matter for alignment; state them if the vendor requires them.

## 4. What to write in the calc sheet

- The axis table and the global-to-nozzle map (section 2 of the sheet).
- Every load case run, with the source of each load set and its file or run identifier.
- The resolution point and the arms used.
- Units, and the conversions made.
- The cases deliberately not compared, with the reason.
