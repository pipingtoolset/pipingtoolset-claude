"""Assemble the PipingToolset for ChatGPT and Codex demo from the Codex recordings.

Run from anywhere:  python docs/demo/edit-tools/build_codex_demo.py
Needs ffmpeg (Gyan build via winget) and these silent screen recordings in docs/demo:
PipingToolset_Codex_install_intro.mp4, _e1.mp4, _e2.mp4, _e9.mp4, _e9_part2.mp4.
Output: docs/demo/PipingToolset_for_ChatGPT_Codex_demo.mp4 and, beside it, the same captions
as PipingToolset_for_ChatGPT_Codex_demo.srt for the YouTube subtitle track.

No narration was recorded, so every caption is burned in as a lower third and also written to
the SRT. The recordings are 1916x1078 / 1918x1028 window captures; each is padded to 1920x1080
without scaling, so no pixel is resampled. Waiting stretches run at 8x with a tag; every prompt,
answer and report page plays in real time. Audio is a silent AAC track so the concat stays in sync.
"""
import pathlib
import shutil
import subprocess

FF = r"C:\Users\matth\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
SRC = pathlib.Path(r"C:\dev\projects\pipingtoolset-claude\docs\demo")   # the recordings (gitignored)
OUT = SRC / "edit-work-codex"                                           # intermediates (gitignored)
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
# Pad only: the captures are smaller than or equal to 1920x1080, so nothing is resampled.
VF_BASE = "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0c1f22,fps=30,format=yuv420p"

_n = [0]
def tf(text):
    _n[0] += 1
    p = TXT / f"c{_n[0]:03d}.txt"
    # newline="\n": on Windows the default translation writes CR LF, and drawtext renders the
    # CR as an empty line, which doubles the gap inside every two-line caption.
    p.write_text(text, encoding="utf-8", newline="\n")
    return f"txt/{p.name}"

def cap(text, a, b, size=38, y=None, bold=False):
    """Lower-third caption, centred, boxed, visible between a and b seconds of the clip."""
    n = text.count(chr(10)) + 1
    if y is None:
        y = f"h-{150 + int((size + 10) * (n - 1))}"
    return (f"drawtext=expansion=none:fontfile={FONTB if bold else FONT}:textfile='{tf(text)}':fontsize={size}:fontcolor=white:"
            f"line_spacing=10:box=1:boxcolor=black@0.72:boxborderw=18:x=(w-text_w)/2:y={y}:"
            f"enable='between(t,{a},{b})'", text, a, b)

def tag(text, a, b):
    """Small top-right tag (e.g. 'sped up 8x')."""
    return (f"drawtext=expansion=none:fontfile={FONTB}:textfile='{tf(text)}':fontsize=30:fontcolor=white:box=1:"
            f"boxcolor=0xec3013@0.9:boxborderw=12:x=w-text_w-40:y=40:enable='between(t,{a},{b})'")

def run(args):
    if args[-1].endswith('.mp4') and 'seg' in args[-1] and pathlib.Path(args[-1]).exists() and pathlib.Path(args[-1]).stat().st_size > 100000:
        print('skip (exists)', pathlib.Path(args[-1]).name, flush=True); return
    print(" ".join(a if " " not in a else f'"{a}"' for a in args[:6]), "...", flush=True)
    subprocess.run(args, check=True, cwd=str(OUT))

segments = []      # intermediate files in order
timeline = 0.0     # running output time, for the SRT
subs = []          # (start, end, text) in output time

def _collect(caps, dur):
    global timeline
    for _, text, a, b in caps:
        subs.append((timeline + a, timeline + min(b, dur), text))
    timeline += dur

def clip(name, src, start, end, speed=1.0, caps=(), tags=()):
    out = SEG / f"{len(segments):02d}_{name}.mp4"
    vf = [f"trim=start={start}:end={end},setpts=PTS-STARTPTS", VF_BASE]
    if speed != 1.0:
        vf.append(f"setpts=PTS/{speed}")
    vf += [c[0] for c in caps] + list(tags)
    args = [FF, "-y", "-v", "error", "-i", str(src), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-filter_complex", f"[0:v]{','.join(vf)}[v]", "-map", "[v]", "-map", "1:a", "-shortest", *ENC, str(out)]
    run(args)
    segments.append(out)
    _collect(caps, (end - start) / speed)

def card(name, dur, lines, sub=None):
    """Ink-coloured title/end card with a red rule, matching the site brand."""
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

INTRO = SRC / "PipingToolset_Codex_install_intro.mp4"
E1 = SRC / "PipingToolset_Codex_e1.mp4"
E2 = SRC / "PipingToolset_Codex_e2.mp4"
E9 = SRC / "PipingToolset_Codex_e9.mp4"
E9B = SRC / "PipingToolset_Codex_e9_part2.mp4"
X8 = 8.0

# ── the cut ───────────────────────────────────────────────────────────────────
card("title", 5, [
    ("PipingToolset for ChatGPT and Codex", 80, True),
    ("The assistant asks. A script computes. You read the table.", 44, False),
    ("Install from the marketplace, a B31.3 wall thickness check, a refused table value,\nand a pipe support checked and optimized from CAESAR II loads, every number from a script", 30, False),
], sub="pipingtoolset.com/openai  ·  free  ·  open source  ·  Apache-2.0  ·  the same plugin that ships for Claude")

# Install, from the ChatGPT desktop app on Windows
clip("intro_home", INTRO, 0, 7, caps=[
    cap("ChatGPT desktop app on Windows. One plugin, two assistants: the same seven skills that ship for Claude", 0.3, 7),
])
clip("intro_add", INTRO, 8, 13, caps=[
    cap("Plugins  ›  Add  ›  Add a marketplace", 0.3, 5),
])
clip("intro_page", INTRO, 22, 30, caps=[
    cap("pipingtoolset.com/openai: the install route, and what runs where, side by side with Claude", 0.3, 8),
])
clip("intro_dialog", INTRO, 36, 50, caps=[
    cap("Source: github.com/pipingtoolset/pipingtoolset-claude, ref main. Add marketplace.", 0.3, 6),
    cap("Marketplace added. PipingToolset appears under Personal; open it and press Install plugin", 6, 10.5),
    cap("Installed. The listing carries the PipingToolset mark, the publisher and three starter prompts", 10.5, 14),
])
clip("intro_settings", INTRO, 50, 62, caps=[
    cap("Settings  ›  Plugin settings  ›  PipingToolset: seven skills, each with the description the skill declares", 0.3, 7),
    cap("No account, no API key, no telemetry. Nothing you type reaches PipingToolset.", 7, 12),
])

# E1: wall thickness, every number from pressure_design.py
clip("e1_prompt", E1, 34, 42, caps=[
    cap("Prompt 1 ($piping-toolset:pressure-design): B31.3-2022, NPS 6 seamless, OD 6.625 in, 750 psig at 600 F,\nc = 0.0625 in, 12.5 % mill tolerance, S = 17,900 psi from my copy, E = W = 1.0, Y = 0.4. Does 0.280 in nominal work?", 0.3, 8, size=30),
])
clip("e1_work", E1, 42, 161, speed=X8, tags=[tag("sped up 8x", 0, 15)], caps=[
    cap("The skill loads pressure-design, writes job.json and runs pressure_design.py with your inputs", 0.3, 7),
    cap("Two minutes of checking: the script run, a second python pass over the thin-wall limits, the clause lookup", 7, 14.8),
])
clip("e1_result", E1, 161, 180, caps=[
    cap("t = 0.13650 in   ·   tm = t + c = 0.19900 in   ·   order 0.22743 in with 12.5 % under-tolerance\n0.280 in nominal: allowable 1,008 psi against 750 psig, no warnings; t < D/6 and P/(SE) = 0.0419, below 0.385", 0.3, 10, size=32),
    cap("Basis and review items: S, E, W, Y echoed as user-supplied; the material grade and the Table A-1 line\nwere not given, so they are flagged ASSUMED or unverified before issue", 10, 19, size=32),
])

# E2: the refusal
clip("e2", E2, 0, 22, caps=[
    cap("Prompt 2: What is the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.", 0.3, 9, size=32),
    cap("No number. It names B31.3 Appendix A, Table A-1 (through 2022) or A-1C (2024), the A106 Grade B row\nand 650 F. You read the value from your licensed copy; the plugin embeds no table.", 13, 22, size=32),
])

# E9: pipe support check and optimization
clip("e9_pick", E9, 12, 16, caps=[
    cap("Type /piping to filter the picker to the seven PipingToolset skills", 0.3, 4),
])
clip("e9_prompt", E9, 16, 24, caps=[
    cap("Prompt 3 ($piping-toolset:pipe-support): PS-201, CSA type 1 t-post, W6X15 column and arm, two 6 in lines,\nCAESAR II restraint loads SUS / OPE / WIN / EQ, SDS 0.5, LRFD, 4 x 3/4 in adhesive anchors, tau 800 psi. Then optimize it.", 0.3, 8, size=30),
])
clip("e9_work1", E9, 24, 110, speed=X8, tags=[tag("sped up 8x", 0, 11)], caps=[
    cap("Reads the pipe-support skill, the spec format and the code basis, then maps the loads", 0.3, 5),
    cap("D = SUS,   T = OPE − SUS,   W = WIN,   Eh = EQ,   Ev = 0.2 · SDS · D   ·   LRFD, T = 1.0, SDS = 0.5", 5, 10.7),
])
clip("e9_question", E9, 110, 131, caps=[
    cap("The skill asks for what it is missing: steel grade, weld, plate and anchor layout, concrete, the ESR data.\nReply: proceed. Missing inputs are screened with the CSA Type 1 defaults and marked ASSUMED", 0.3, 12, size=32),
    cap("support_calc.py runs 23 ASCE 7-22 LRFD combinations: a nominal pass,\ngoverned by the arm-to-column weld base metal at UR 0.888", 13, 21, size=32),
])
clip("e9_work2", E9, 131, 201, speed=X8, tags=[tag("sped up 8x", 0, 9)], caps=[
    cap("The reviewer pass: anchor layout, bond strength, edge distances, what the ESR must confirm", 0.3, 8.6),
])
clip("e9b_work", E9B, 0, 64, speed=X8, tags=[tag("sped up 8x", 0, 8)], caps=[
    cap("Optimizer re-run with every ratio capped at 0.85; the spec files are written with the assumptions in them", 0.3, 7.9),
])
clip("e9b_assumed", E9B, 64, 72, caps=[
    cap("Every assumed input is written into the spec as ASSUMED: steel, welds, plate, anchors, cracked concrete, offsets", 0.3, 8, size=32),
])
clip("e9b_report", E9B, 84, 97, caps=[
    cap("The calc report: PS-201, T-post, AISC 360-22 / ACI 318-19 / ASCE 7-22, LRFD\nENGINE PASS (screening only), governing Arm 1 to column weld UR 0.888; reviewer HOLD until the findings are resolved", 0.3, 13, size=30),
])
clip("e9b_limits", E9B, 97, 109, caps=[
    cap("The ASCE 7-22 combinations with their factors, then the reactions at the base plate", 0.3, 3.5, size=32),
    cap("Limit-state results enveloped over every combination, with demand, capacity, ratio and clause:\nArm 1 W6X15 max UR 0.153, arm-to-column weld 0.888, base plate 0.583, anchorage 0.586", 3.5, 7.2, size=32),
    cap("Compliance matrix by code area: AISC members, welds, base plate, ACI anchorage and pier all pass;\nAWS D1.1 prequalified joints left for the engineer to confirm", 7.2, 12, size=32),
])
clip("e9b_findings", E9B, 109, 118, caps=[
    cap("Reviewer findings: two critical (arm-to-column load path incomplete, column torsion not checked)\nand the majors: ESR qualification, seismic overstrength, the J10.1 weld detail, the material basis", 0.3, 3.8, size=32),
    cap("Optimized alternatives, ranked by weight, field work and standard sizes, every one passing at or under 0.85", 3.8, 9, size=32),
])
clip("e9b_optim", E9B, 118, 128, caps=[
    cap("#1: a W8X10 arm on a PIPE5 STD column, 3/16 in fillet, 1 in plate, 5/8 in anchors, 170 lb of steel, UR 0.764", 0.3, 10, size=32),
])
clip("e9b_files", E9B, 132, 148, caps=[
    cap("The chat summary: the governing ratios, what was assumed, what must be confirmed before issue", 0.3, 9.5),
    cap("Four files in the working folder: the calc report, the reviewed and raw result JSON, the input spec", 9.5, 16),
])

card("end", 9, [
    ("pipingtoolset.com/openai", 72, True),
    ("github.com/pipingtoolset/pipingtoolset-claude", 44, False),
    ("codex plugin marketplace add pipingtoolset/pipingtoolset-claude\nthen install PipingToolset from the Plugins view", 36, False),
], sub="Results are engineering aids. The engineer of record verifies them before issue.  ·  Flexible Piping Solutions LLC")

# ── concat ────────────────────────────────────────────────────────────────────
lst = OUT / "concat.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
final = SRC / "PipingToolset_for_ChatGPT_Codex_demo.mp4"
run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)])

def _ts(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
srt = SRC / "PipingToolset_for_ChatGPT_Codex_demo.srt"
srt.write_text("".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(subs, 1)), encoding="utf-8", newline="\n")
print("FINAL", final, "duration %.1fs" % timeline, "captions", len(subs), "srt", srt)
