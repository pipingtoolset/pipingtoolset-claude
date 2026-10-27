"""Assemble the PipingToolset for Claude demo from the step recordings.

Run from anywhere:  python docs/demo/edit-tools/build_demo.py
Needs ffmpeg (Gyan build via winget) and the step*.mp4 files in docs/demo. Output lands in
docs/demo/PipingToolset_for_Claude_demo.mp4. The narration transcripts beside this script
(step5/7/8/9/11.txt) are what the caption timings were taken from.

Each segment is rendered to a uniform intermediate (1920x1080, 30 fps, yuv420p, AAC 48 kHz
stereo) with its captions burned in, then the intermediates are concatenated losslessly.
Voiced clips keep their audio (loudness-normalised); silent clips get a silent track so the
concat stays in sync. Text is passed through textfile= so no shell/filter escaping of the
caption bodies is needed.
"""
import os, subprocess, sys, pathlib, json

FF = r"C:\Users\matth\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
SRC = pathlib.Path(__file__).resolve().parent.parent          # docs/demo: the step recordings
OUT = SRC / "edit-work"                                        # intermediates (gitignored)
OUT.mkdir(exist_ok=True)
import shutil
for f in ("arial.ttf", "arialbd.ttf"):
    if not (OUT / f).exists():
        shutil.copy(pathlib.Path(r"C:/Windows/Fonts") / f, OUT / f)
SEG = OUT / "seg"; TXT = OUT / "txt"
SEG.mkdir(exist_ok=True); TXT.mkdir(exist_ok=True)
FONT = "arial.ttf"      # copied into OUT; ffmpeg runs with cwd=OUT so no drive-letter colon
FONTB = "arialbd.ttf"   # reaches the filter parser (ffmpeg 9 rejects the C\: escape form)

ENC = ["-c:v", "libx264", "-preset", "faster", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]
VF_BASE = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
AF_VOICE = "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11"

_n = [0]
def tf(text):
    _n[0] += 1
    p = TXT / f"c{_n[0]:03d}.txt"
    p.write_text(text, encoding="utf-8")
    return f"txt/{p.name}"

def cap(text, a, b, size=40, y=None, bold=False):
    """Lower-third caption, centred, boxed, visible between a and b seconds.
    y is derived from the line count so a two-line caption never clips the frame edge."""
    n = text.count(chr(10)) + 1
    if y is None:
        y = f"h-{150 + int((size + 10) * (n - 1))}"
    return (f"drawtext=expansion=none:fontfile={FONTB if bold else FONT}:textfile='{tf(text)}':fontsize={size}:fontcolor=white:"
            f"line_spacing=10:box=1:boxcolor=black@0.68:boxborderw=18:x=(w-text_w)/2:y={y}:"
            f"enable='between(t,{a},{b})'")

def tag(text, a, b):
    """Small top-right tag (e.g. 'sped up 4x')."""
    return (f"drawtext=expansion=none:fontfile={FONTB}:textfile='{tf(text)}':fontsize=30:fontcolor=white:box=1:"
            f"boxcolor=0xec3013@0.9:boxborderw=12:x=w-text_w-40:y=40:enable='between(t,{a},{b})'")

def run(args):
    if args[-1].endswith('.mp4') and 'seg' in args[-1] and pathlib.Path(args[-1]).exists() and pathlib.Path(args[-1]).stat().st_size > 100000:
        print('skip (exists)', pathlib.Path(args[-1]).name, flush=True); return
    print(" ".join(a if " " not in a else f'"{a}"' for a in args[:6]), "...", flush=True)
    subprocess.run(args, check=True, cwd=str(OUT))

segments = []

def clip(name, src, start=None, end=None, speed=1.0, voiced=False, caps=(), tags=()):
    out = SEG / f"{len(segments):02d}_{name}.mp4"
    vf = [VF_BASE]
    if start is not None or end is not None:
        s = start or 0
        vf.insert(0, f"trim=start={s}" + (f":end={end}" if end else "") + ",setpts=PTS-STARTPTS")
    if speed != 1.0:
        vf.append(f"setpts=PTS/{speed}")
    vf += list(caps) + list(tags)
    if voiced and speed == 1.0:
        af = []
        if start is not None or end is not None:
            s = start or 0
            af.append(f"atrim=start={s}" + (f":end={end}" if end else "") + ",asetpts=PTS-STARTPTS")
        af.append(AF_VOICE)
        args = [FF, "-y", "-v", "error", "-i", str(src), "-filter_complex",
                f"[0:v]{','.join(vf)}[v];[0:a]{','.join(af)}[a]", "-map", "[v]", "-map", "[a]", *ENC, str(out)]
    else:
        args = [FF, "-y", "-v", "error", "-i", str(src), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-filter_complex", f"[0:v]{','.join(vf)}[v]", "-map", "[v]", "-map", "1:a", "-shortest", *ENC, str(out)]
    run(args)
    segments.append(out)

def card(name, dur, lines, sub=None):
    """Ink-coloured title/end card with a red rule, matching the site brand.
    lines: (text, size, bold) tuples; each text may hold newlines, drawn one drawtext per line."""
    out = SEG / f"{len(segments):02d}_{name}.mp4"
    vf = ["drawbox=x=160:y=430:w=64:h=4:color=0xec3013:t=fill"]
    y = 300
    for i, (text, size, bold) in enumerate(lines):
        for ln in text.split(chr(10)):
            vf.append(f"drawtext=expansion=none:fontfile={FONTB if bold else FONT}:textfile='{tf(ln)}':fontsize={size}:"
                      f"fontcolor=white:x=160:y={y}")
            y += int(size * 1.45)
        y += 36 if i == 0 else 18
    if sub:
        vf.append(f"drawtext=expansion=none:fontfile={FONT}:textfile='{tf(sub)}':fontsize=26:fontcolor=0xa9a5a4:x=160:y=h-120")
    vf.append("fade=t=in:st=0:d=0.5,fade=t=out:st=%s:d=0.5" % (dur - 0.5))
    args = [FF, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x201e1d:s=1920x1080:r=30:d={dur}",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", f"[0:v]{','.join(vf)}[v]",
            "-map", "[v]", "-map", "1:a", "-t", str(dur), *ENC, str(out)]
    run(args)
    segments.append(out)

# ── the cut ───────────────────────────────────────────────────────────────────
card("title", 5, [
    ("PipingToolset for Claude", 86, True),
    ("Claude asks. A script computes. You read the table.", 44, False),
    ("B31.3 wall thickness, a refused table value and a pipe support check,\nevery number from a script", 32, False),
], sub="pipingtoolset.com/claude  ·  free  ·  open source  ·  Apache-2.0")

clip("step1", SRC / "step1.mp4", caps=[
    cap("PipingToolset for Claude: seven free skills for Claude Code and Claude Cowork", 0.5, 7.5),
    cap("From the people who build the free calculators at pipingtoolset.com", 7.5, 15),
])
clip("step1v", SRC / "Step1_voice.mp4", end=6, caps=[
    cap("Claude runs the interview. A Python script does the math.\nYou read the table from your own copy of the code.", 0.3, 6),
])
clip("step2", SRC / "step2.mp4", caps=[
    cap("Seven skills: pressure design, stress screening, load case builder,\npipe support, iso to PCF, nozzle load, bolted flange", 0.3, 8),
    cap("It never quotes a code table value. You read those from your licensed copy.", 8, 15),
    cap("Nothing you type is sent to us. The scripts run in your own Claude environment.", 15, 21.5),
])
clip("step3", SRC / "step3.mp4", caps=[
    cap("Install: download piping-toolset.plugin from pipingtoolset.com/claude", 0.5, 12),
    cap("One file, about 390 KB. No account, no API key, no telemetry.", 12, 28),
])
clip("step4", SRC / "step4_modified.mp4", caps=[
    cap("Claude desktop app  >  Settings  >  Plugins  >  Upload plugin\n(or drag the file into a Cowork chat and press Accept)", 0.5, 16),
    cap("PipingToolset is installed and ready to use", 20, 28),
])
clip("step5", SRC / "step5.mp4", voiced=True, caps=[
    cap("Skills menu: bolted-flange · iso-to-pcf · load-case-builder · nozzle-load\npipe-support · pressure-design · stress-screening", 4, 30),
])
clip("step6", SRC / "step6.mp4", caps=[
    cap("Point the chat at a working folder: C:\\demo\\PS-201. Output files land there.", 0.3, 6.2),
])
clip("step7", SRC / "step7.mp4", voiced=True, caps=[
    cap("Prompt 1: B31.3-2022, NPS 6 seamless, 750 psig at 600 F, c = 0.0625 in, 12.5 % mill tolerance,\nS = 17,900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. Does 0.280 in nominal work?", 1, 10, size=32),
    cap("Skill loaded: pressure-design. The skill writes a job file and runs pressure_design.py.", 18, 42),
    cap("t = 0.1365 in   ·   tm = t + c = 0.1990 in   ·   order 0.2274 in\n0.280 in nominal: 0.1825 in left for pressure, allowable 1,008 psig, PASS", 42.7, 73),
    cap("The sheet flags what a reviewer will: no material line behind S = 17,900 psi,\nW and Y table lines, the purchase spec behind the mill tolerance, the edition", 73.7, 86),
])
clip("step8", SRC / "step8.mp4", voiced=True, caps=[
    cap("Prompt 2: What is the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.", 0.5, 10, size=32),
    cap("No number. It names B31.3-2022 Table A-1 (Table A-1C in the 2024 edition),\nthe A106 Grade B seamless line and the 650 F column, and offers to interpolate.", 10.2, 28.5),
])
# step 9: narration runs to ~68 s while the skill works; the remaining wait is sped up, the answer is real time.
clip("step9a", SRC / "step9.mp4", end=68.5, voiced=True, caps=[
    cap("Prompt 3: PS-201, CSA type 1 t-post, W6X15 column and arm, two 6 in lines,\nCAESAR II restraint loads SUS / OPE / WIN / EQ, SDS 0.5, LRFD, 4 x 3/4 in adhesive anchors. Then optimize it.", 0.5, 12, size=30),
    cap("Load mapping: D = SUS,  T = OPE − SUS,  W = WIN,  Eh = EQ,  Ev = 0.2 · SDS · D", 17.8, 32),
    cap("ASCE 7-22 combinations · AISC 360-22 arm, column, welds, base plate · ACI 318-19 Ch. 17 anchors", 32.9, 45),
    cap("Governing: base metal at the arm-to-column weld, tension yielding (AISC J4-1)\nratio 0.888 under 1.4D + T  ·  all 23 LRFD combinations pass", 45.3, 68.5),
])
clip("step9b", SRC / "step9.mp4", start=68.5, end=83.5, speed=4.0, tags=[tag("sped up 4x", 0, 10)], caps=[
    cap("Optimizer re-run with every ratio capped at 0.85", 0, 3.75),
])
clip("step9c", SRC / "step9.mp4", start=83.5, voiced=True, caps=[
    cap("This run's pick: keep the W6X15 column, W8X10 arm, 7/8 in plate, 5/8 in anchors.\nEvery check at or under 0.834. A list of what to confirm before issue, then four files saved.", 0.5, 16.8),
])
clip("step10", SRC / "step10.mp4", caps=[
    cap("Saved to the working folder: PS-201_calc_as-drawn.md, PS-201_calc_optimized-0.85.md,\nPS-201_spec.json, PS-201_result.json", 0.5, 10),
    cap("The calc report is what you hand to your checker: design basis, loads, reactions,\nevery clause and every ratio, with the ASSUMED inputs called out", 10, 31),
])
clip("step11", SRC / "step11.mp4", voiced=True, caps=[
    cap("Open source, Apache-2.0  ·  verified against the pipingtoolset.com fixture cases", 8.9, 23),
    cap("Changelog = recall notice: an UNCONSERVATIVE-FIX release names the skill,\nthe affected inputs and the fix. Update when you see one.", 23, 50),
    cap("pipingtoolset.com/claude   ·   github.com/pipingtoolset/pipingtoolset-claude", 50.2, 66),
])
card("end", 9, [
    ("pipingtoolset.com/claude", 72, True),
    ("github.com/pipingtoolset/pipingtoolset-claude", 44, False),
    ("/plugin marketplace add pipingtoolset/pipingtoolset-claude\n/plugin install piping-toolset@pipingtoolset", 36, False),
], sub="Results are engineering aids. The engineer of record verifies them before issue.  ·  Flexible Piping Solutions LLC")

# ── concat ────────────────────────────────────────────────────────────────────
lst = OUT / "concat.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
final = SRC / "PipingToolset_for_Claude_demo.mp4"
run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)])
print("FINAL", final)
