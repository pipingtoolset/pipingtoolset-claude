"""Assemble the silent, captioned PipingToolset for Claude demo from the step recordings.

Run from anywhere:  python docs/demo/edit-tools/build_claude_demo_silent.py
Needs ffmpeg (Gyan build via winget) and step1..step11 .mp4 in docs/demo (Step1_voice.mp4 and
the narrated audio are not used). Output: docs/demo/PipingToolset_for_Claude_demo_silent.mp4
and PipingToolset_for_Claude_demo_silent.srt beside it, for the YouTube subtitle track.

The 2026-10-27 cut (build_demo.py) was narrated; this one replaces it in the same format as the
ChatGPT / Codex demo: no voice, every step carries a burned-in caption that is also in the SRT.
Captures are 1918x1078 light-theme Cowork and browser windows, padded to 1920x1080 without
scaling; the long waits run at 8x with a tag; prompts, answers and report pages play in real time.
"""
import pathlib
import shutil
import subprocess

FF = r"C:\Users\matth\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
SRC = pathlib.Path(r"C:\dev\projects\pipingtoolset-claude\docs\demo")
OUT = SRC / "edit-work-claude-silent"
OUT.mkdir(exist_ok=True)
for f in ("arial.ttf", "arialbd.ttf"):
    if not (OUT / f).exists():
        shutil.copy(pathlib.Path(r"C:/Windows/Fonts") / f, OUT / f)
SEG = OUT / "seg"; TXT = OUT / "txt"
SEG.mkdir(exist_ok=True); TXT.mkdir(exist_ok=True)
FONT = "arial.ttf"
FONTB = "arialbd.ttf"

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]
VF_BASE = "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x201e1d,fps=30,format=yuv420p"

_n = [0]
def tf(text):
    _n[0] += 1
    p = TXT / f"c{_n[0]:03d}.txt"
    p.write_text(text, encoding="utf-8", newline="\n")   # LF only: CR renders as a blank line in drawtext
    return f"txt/{p.name}"

def cap(text, a, b, size=38, y=None, bold=False):
    n = text.count(chr(10)) + 1
    if y is None:
        y = f"h-{150 + int((size + 10) * (n - 1))}"
    return (f"drawtext=expansion=none:fontfile={FONTB if bold else FONT}:textfile='{tf(text)}':fontsize={size}:fontcolor=white:"
            f"line_spacing=10:box=1:boxcolor=black@0.72:boxborderw=18:x=(w-text_w)/2:y={y}:"
            f"enable='between(t,{a},{b})'", text, a, b)

def tag(text, a, b):
    return (f"drawtext=expansion=none:fontfile={FONTB}:textfile='{tf(text)}':fontsize=30:fontcolor=white:box=1:"
            f"boxcolor=0xec3013@0.9:boxborderw=12:x=w-text_w-40:y=40:enable='between(t,{a},{b})'")

def run(args):
    if args[-1].endswith('.mp4') and 'seg' in args[-1] and pathlib.Path(args[-1]).exists() and pathlib.Path(args[-1]).stat().st_size > 100000:
        print('skip (exists)', pathlib.Path(args[-1]).name, flush=True); return
    print(" ".join(a if " " not in a else f'"{a}"' for a in args[:6]), "...", flush=True)
    subprocess.run(args, check=True, cwd=str(OUT))

segments = []
timeline = 0.0
subs = []

def _collect(caps, dur):
    global timeline
    for _, text, a, b in caps:
        subs.append((timeline + a, timeline + min(b, dur), text))
    timeline += dur

def clip(name, src, start=None, end=None, speed=1.0, caps=(), tags=()):
    out = SEG / f"{len(segments):02d}_{name}.mp4"
    vf = [VF_BASE]
    if start is not None or end is not None:
        s = start or 0
        vf.insert(0, f"trim=start={s}" + (f":end={end}" if end else "") + ",setpts=PTS-STARTPTS")
    if speed != 1.0:
        vf.append(f"setpts=PTS/{speed}")
    vf += [c[0] for c in caps] + list(tags)
    args = [FF, "-y", "-v", "error", "-i", str(src), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-filter_complex", f"[0:v]{','.join(vf)}[v]", "-map", "[v]", "-map", "1:a", "-shortest", *ENC, str(out)]
    run(args)
    segments.append(out)
    dur = DUR[src.name] if end is None else end
    dur = (dur - (start or 0)) / speed
    _collect(caps, dur)

def card(name, dur, lines, sub=None):
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
    _collect((), dur)

# source durations (ffprobe, 2026-10-28), for the SRT clock when a clip runs to its end
DUR = {"step1.mp4": 15.3, "step2.mp4": 21.73, "step3.mp4": 28.1, "step4_modified.mp4": 28.4, "step5.mp4": 35.83,
       "step6.mp4": 6.3, "step7.mp4": 86.07, "step8.mp4": 28.6, "step9.mp4": 100.37, "step10.mp4": 31.27, "step11.mp4": 66.3}
S = lambda n: SRC / n
X8 = 8.0

# ── the cut ───────────────────────────────────────────────────────────────────
card("title", 5, [
    ("PipingToolset for Claude", 86, True),
    ("Claude asks. A script computes. You read the table.", 44, False),
    ("Install in Claude Cowork, a B31.3 wall thickness check, a refused table value,\nand a pipe support checked and optimized from CAESAR II loads, every number from a script", 30, False),
], sub="pipingtoolset.com/claude  ·  free  ·  open source  ·  Apache-2.0  ·  the same plugin ships for ChatGPT and Codex")

clip("step1", S("step1.mp4"), caps=[
    cap("pipingtoolset.com: the free calculators, and a launcher tier for the plugin that runs inside Claude", 0.5, 8),
    cap("Seven free skills for Claude Code and Claude Cowork, from a practicing piping engineer", 8, 15),
])
clip("step2", S("step2.mp4"), caps=[
    cap("pipingtoolset.com/claude: what a run looks like, the seven skills, the three rules", 0.3, 8),
    cap("It never quotes a code table value. You read those from your licensed copy.", 8, 14),
    cap("Where your data goes: the scripts make no network calls. The optional connector sends lookup keys only.", 14, 21.5),
])
clip("step3", S("step3.mp4"), end=26, caps=[
    cap("Install: press Download for Cowork (.plugin). One file from the GitHub release, about 400 KB.", 0.5, 12),
    cap("The plugin needs no account or API key, and has no telemetry.", 12, 24),
])
clip("step4", S("step4_modified.mp4"), caps=[
    cap("Claude desktop app  ›  Settings  ›  Plugins  ›  Add  ›  Upload plugin\n(or drag the file into a Cowork chat and press Accept)", 0.5, 16, size=34),
    cap("PipingToolset by Flexible Piping Solutions LLC, 7 skills: installed and ready to use", 20, 28, size=34),
])
clip("step5", S("step5.mp4"), end=18, caps=[
    cap("Plugins  ›  PipingToolset: bolted-flange, iso-to-pcf, load-case-builder, nozzle-load,\npipe-support, pressure-design, stress-screening. Hover a skill for what it does.", 1, 18, size=34),
])
clip("step6", S("step6.mp4"), caps=[
    cap("Point the chat at a working folder, C:\\demo\\PS-201. Output files land there.", 0.3, 6.2),
])

# step 7: prompt pasted at ~4 s, skill loads, two script runs, answer streams from ~44 s
clip("step7a", S("step7.mp4"), end=14, caps=[
    cap("Prompt 1: B31.3-2022, NPS 6 seamless, OD 6.625 in, 750 psig at 600 F, c = 0.0625 in, 12.5 % mill tolerance,\nS = 17,900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. Does 0.280 in nominal wall work?", 0.5, 14, size=30),
])
clip("step7b", S("step7.mp4"), start=14, end=44, speed=X8, tags=[tag("sped up 8x", 0, 3.75)], caps=[
    cap("Skill loaded: pressure-design. It lists the modules, writes a job file and runs pressure_design.py", 0.3, 3.75, size=34),
])
clip("step7c", S("step7.mp4"), start=44, end=86, caps=[
    cap("Ran 2 commands: wall thickness and MAWP checks. Yes, 0.280 in works.\nt = PD/[2(SEW + PY)] = 0.1365 in   ·   tm = t + c = 0.1990 in   ·   tOrder = tm/(1 − 0.125) = 0.2274 in", 3, 14, size=32),
    cap("0.280 in gives 0.1825 in for pressure after mill tolerance and corrosion: 1,008.4 psig allowable, 34 % above design.\nValidity by hand: t/D = 0.0206 under the D/6 limit, P/(SE) = 0.042 under 0.385, so Eq. (3a) applies.", 14, 27, size=30),
    cap("Gaps a reviewer will flag: no material listed behind S = 17,900 psi (the Table A-1 line), W = 1.0 and Y = 0.4\ntable lines, the mill tolerance from the purchase spec, and the edition. Each one is written on the calc sheet.", 27, 42, size=30),
])
clip("step8", S("step8.mp4"), end=24, caps=[
    cap("Prompt 2: What is the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.", 0.5, 7, size=32),
    cap("No number. It names B31.3-2022 Table A-1 (A-1C in the 2024 edition), the A106 Grade B seamless line\nand the 650 F column, and offers to interpolate once you have read both values.", 7.5, 24, size=32),
])

# step 9: prompt pasted ~2 s, 76 s of script runs, answer from ~82 s
clip("step9a", S("step9.mp4"), end=8, caps=[
    cap("Prompt 3: PS-201, CSA type 1 t-post, W6X15 column and arm, two 6 in lines, CAESAR II restraint loads\nSUS / OPE / WIN / EQ, SDS 0.5, LRFD, 4 x 3/4 in adhesive anchors, tau 800 psi from the ESR. Then optimize it.", 0.5, 8, size=30),
])
clip("step9b", S("step9.mp4"), start=8, end=85, speed=X8, tags=[tag("sped up 8x", 0, 9.6)], caps=[
    cap("Skill loaded: pipe-support. Reads the spec format and the CSA type 1 preset, builds the spec, runs support_calc.py", 0.3, 4.8, size=32),
    cap("Then the plate-geometry sensitivity, the optimizer at a 0.85 cap, the anchor bond check for the smaller bolts,\nand the deliverables staged for your folder", 4.8, 9.6, size=32),
])
clip("step9c", S("step9.mp4"), start=85, caps=[
    cap("PS-201 passes as drawn: all 23 LRFD combinations. Governing: arm-to-column weld base metal, 0.888 under 1.4D + T.\nLoad mapping stated: D = SUS, T = OPE − SUS, W = WIN, Eh = EQ, Ev = 0.2 · SDS · D", 0.5, 6, size=30),
    cap("Things to fix before issue: the preset anchor pattern does not fit the plate, the inputs it took from the preset,\nand column torsion is outside the engine. Then the optimizer pick: W8X10 arm, 7/8 in plate, 5/8 in anchors, 0.834", 6, 12, size=30),
    cap("Four files saved to the PS-201 folder: the as-drawn calc, the optimized calc, the spec and the result JSON", 12, 15.3, size=32),
])
clip("step10", S("step10.mp4"), start=4, end=26, caps=[
    cap("The working folder: PS-201_calc_as-drawn.md, PS-201_calc_optimized-0.85.md, PS-201_spec.json, PS-201_result.json", 0.3, 7, size=32),
    cap("The calc report: design basis and resistance factors, materials, assembly geometry, the ASCE 7-22 combinations,\nevery limit state with demand, capacity, ratio and clause, the compliance matrix and the review findings", 7, 22, size=30),
])
clip("step11", S("step11.mp4"), start=16, end=52, caps=[
    cap("Open source, Apache-2.0. Every script reproduces the pipingtoolset.com fixture cases; a red parity test blocks a release.", 0.5, 12, size=32),
    cap("The site's calculation changelog, and the plugin's: an UNCONSERVATIVE-FIX release names the skill,\nthe affected inputs and the fix. Update when you see one.", 12, 24, size=32),
    cap("pipingtoolset.com/claude   ·   github.com/pipingtoolset/pipingtoolset-claude   ·   the same plugin ships for ChatGPT and Codex", 24, 36, size=32),
])
card("end", 9, [
    ("pipingtoolset.com/claude", 72, True),
    ("github.com/pipingtoolset/pipingtoolset-claude", 44, False),
    ("/plugin marketplace add pipingtoolset/pipingtoolset-claude\n/plugin install piping-toolset@pipingtoolset", 36, False),
], sub="Results are engineering aids. The engineer of record verifies them before issue.  ·  Flexible Piping Solutions LLC")

# ── concat ────────────────────────────────────────────────────────────────────
lst = OUT / "concat.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
final = SRC / "PipingToolset_for_Claude_demo_silent.mp4"
run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)])

def _ts(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
srt = SRC / "PipingToolset_for_Claude_demo_silent.srt"
srt.write_text("".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(subs, 1)), encoding="utf-8", newline="\n")
print("FINAL", final, "duration %.1fs" % timeline, "captions", len(subs), "srt", srt)
