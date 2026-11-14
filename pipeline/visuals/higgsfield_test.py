"""HIGGSFIELD TEST MODE — proves the Higgsfield clip pipeline works with NO account.

Set visuals.provider: higgsfield_test in config.yaml (or run with --provider higgsfield_test)
and the bot generates placeholder MOTION clips (moving colour + scene number), one per scene,
then runs them through the exact same path real Higgsfield clips use:
clips -> our voice -> captions -> music + SFX -> edit -> QC.

If this makes a good video, the real Higgsfield mode will too: switch provider to
higgsfield_clips and point the routine (tools/higgsfield_routine_prompt.md) at inbox/.
"""
from ..common import ROOT, log, run

FONT = ROOT / "assets" / "fonts" / "Anton-Regular.ttf"
W, H = 864, 1536
PALETTES = [("0b3158", "1fc8b8"), ("3a1d60", "c84678"), ("3a2a0a", "e68c28"),
            ("0f3220", "5ac878"), ("08263f", "5cc8ff")]


def generate(cfg, script, workdir):
    dur = 5
    out = []
    for i, sc in enumerate(script["scenes"]):
        a, b = PALETTES[i % len(PALETTES)]
        p = workdir / f"scene_{i:02d}.mp4"
        # slow gradient sweep (a source filter) + big scene number = visible motion to prove the clip path
        src = f"gradients=s={W}x{H}:c0=0x{a}:c1=0x{b}:d={dur}:r=30:speed=0.02"
        vf = (f"drawtext=text='SCENE {i + 1}':fontcolor=white@0.85:fontsize=120:"
              f"x=(w-text_w)/2:y=(h-text_h)/2:fontfile={FONT},format=yuv420p")
        log(f"Higgsfield-test clip {i + 1}/{len(script['scenes'])}")
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src,
             "-vf", vf, "-t", str(dur), "-pix_fmt", "yuv420p", str(p)])
        out.append(p)
    return out
