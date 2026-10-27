# Reading the isos, and choosing SKEYs

## Getting geometry out of a PDF iso set

Isogen-plotted PDFs usually carry a real text layer. When they do, the fastest reliable route
is positioned text extraction plus targeted image zooms, not OCR.

**Quick check first.** `pdftotext -layout -f N -l N iso.pdf -` (poppler) prints sheet N with
the drawing layout kept. If it prints nothing, the sheet has no text layer (see the rendering
fallback below). `pdftotext -layout` is also a usable alternative to the positioned routes.

**Positioned words with pdfplumber.** pdfplumber, pypdf and poppler are expected in the Cowork
sandbox and are common in Python setups, so this route usually needs no install:

```python
import pdfplumber
with pdfplumber.open(path) as pdf:
    words = pdf.pages[i].extract_words()        # dicts with x0, top, x1, bottom, text
```

Group words into lines by `round(top)` (a small tolerance, a point or two) and sort by
`(top, x0)`. That gives every callout, coordinate, dimension and BOM row with its position on
the sheet, which is enough to tie a dimension to the run it annotates.

**Optional faster route, when pymupdf is already installed.** Do not try to install it if pip
or the network is unavailable; use the pdfplumber route above instead.

```python
import pymupdf                                  # optional: only when already installed
doc = pymupdf.open(path)
words = doc[i].get_text("words")                # (x0, y0, x1, y1, word, block, line, word_no)
```

Group words by `(block, line)` and sort by `(y, x)`. That gives every callout, coordinate,
dimension and BOM row with its position on the sheet, which is enough to tie a dimension to
the run it annotates.

Some sheets will have **no** text layer (vector-only plots). Detect that (a page that returns
no words) and fall back to rendering. With no install at all, use poppler's `pdftoppm`; if
pymupdf is already installed, `get_pixmap` does the same job:

```bash
pdftoppm -r 300 -f N -l N -png iso.pdf sheet     # poppler, no install; page N only
pdftoppm -r 200 -f N -l N -png iso.pdf sheet     # whole sheet, for orientation
```

```python
pix = doc[i].get_pixmap(dpi=200)                # whole sheet, for orientation
pix = doc[i].get_pixmap(dpi=450, clip=rect)     # congested area, for reading
```

Read the whole sheet first to establish the topology and the run direction, then zoom only
where callouts overlap. A 300 × 200 pt clip at 400–600 dpi is legible. Whole-sheet renders
above about 250 dpi mostly waste tokens.

Use the text layer **and** the image. The text layer has no arrows, so a number with no visible
arrowheads cannot be tied to a run.

**The BOM block is the highest-value region on every sheet.** It gives exact component
descriptions, sizes and counts, and it is the independent check on your extraction.

## What to capture per sheet

- Continuation coordinates at both ends (`CONT. ON <line> E… N… EL…`). These are the hard
  anchors between sheets and become `check` items.
- Every stated elevation along the run, with its station. These become profile anchors.
- Every dimension chain, including the small ones (`7.3/16`, `8.1/8`): branch stub heights
  and fitting offsets. Note whether each dimension is to a face, a centreline or a weld. The
  walk is centreline-to-centreline, with face-to-face lengths on fittings.
- Bend angles where called out (`89.8°`, `44.2°`). Trimmed elbows are common, and the angle is
  rarely exactly 90.
- Reducer offsets (`4" OFFSET`) and flat side up or down.
- Support tags, type, and any orientation or "offline" note.
- The title block: line number, spec, size, insulation, design conditions, datum and north
  arrow.

## The `X.n/d` dimension convention

On an iso, `13.7/8` means 13 **and** 7/8 in, never 13.7-something. `2635'0.7/16` is 2635 ft
0 7/16 in. The builder's parser (`pcf_lib.ftin`) applies this rule and rejects plain decimals.
Transcribe dimensions exactly as printed and let the parser read them.

## SKEYs

The SKEY decides how CAESAR II classifies a component, including its SIF treatment. The
importer's SKEY map (`caesar-import.md`) is the contract.

**Harvest SKEYs from the user's own Isogen PCFs rather than recalling them.** Ask for one
known-good PCF from their CAD system and list its SKEYs:

```python
import re, collections
print(collections.Counter(re.findall(r"^\s+SKEY\s+(\S+)", open(p).read(), re.M)))
```

Pass that list to `validate_pcf.py --skeys` so anything outside it is flagged.

Common Isogen SKEYs the builder uses as defaults. **Confirm each against the user's own
output before relying on it:**

| SKEY | Component |
|---|---|
| `FLWN` | Weld-neck flange |
| `FLSW` | Socket-weld flange |
| `FLBL` | Blind flange |
| `BEBW` | Butt-weld elbow / bend (written as a `BEND` record) |
| `ELBW` | Butt-weld elbow (`ELBOW` record; not import-proven) |
| `TEBW` | Butt-weld tee |
| `WTBW` | Weldolet |
| `RECC` | Eccentric reducer |
| `SKSW` | Sockolet |
| `CPBW` | Butt-weld cap |
| `FPPL` | Nipple / plain pipe |
| `WS` | Field weld |
| `PB5D` | Mitred bend |
| `VBSW` / `VBFL` | Ball valve, socket-weld / flanged |
| `VVFL` / `AVBW` | Valve flanged / angle valve (import-proven) |
| `FLSO` | Slip-on flange (import-proven) |
| `FPFA` | Fixed pipe (`PIPE-FIXED`, import-proven) |
| `ANCH` `SKID` `GUID` `SPRG` | Support: anchor, resting, guide, spring (import-proven) |

The rows marked import-proven appear in PCFs that import cleanly into CAESAR II. The rest were
seen in one site's Isogen output. Treat `BELW`, `OLBW`/`OLTH` and `VABW`/`VAFL` as unconfirmed
until you find them in the user's own PCFs.

### Why tee and olet SKEYs matter most

The importer's `PCF_SIF_MAP.TXT` turns the SKEY into a CAESAR II SIF type. In the default map on
the build it was checked against: `TEBW` → 3 (welding tee), `TERF` → 2 (unreinforced fabricated
tee), `WTBW` → 5 (weldolet), `SKSW` → 5 (sockolet), `SWBW` → 4 (sweepolet). A B16.9 reducing tee
must therefore carry `TEBW`, not `TERF`, or it imports with an unreinforced-tee SIF. Read the map
on the user's machine. Sites edit it.

If a component type has no confirmed SKEY, use the nearest confirmed one in the same family.
Keep the true identity in `desc` and list the substitution in the handover note.

## Third-party PCFs that import badly

Run `validate_pcf.py` on them first. The usual causes, in order:

1. **Floating starts.** Components were rounded independently, so ends miss each other by
   fractions of a millimetre.
2. **Y-up versus Z-up.** The whole model lies on its side. Rebuild with the right `axes`
   instead of rotating in CAESAR II.
3. **Zero-length elements** from fittings that make up, written as a 0 mm pipe.
4. **Record types the importer does not accept** (`caesar-import.md`).

Fix them by rebuilding from the drawing with this skill, not by patching coordinates.
