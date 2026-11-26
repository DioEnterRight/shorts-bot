"""Branding: the follow outro scene + fixed outro beat, and the corner tag / FOLLOW card burned into the final video."""
import json
import subprocess

from pipeline import branding, common
from tests.conftest import ROOT


def _script(code="en"):
    return json.loads((ROOT / "prompts" / f"sample_script_{code}.json").read_text(encoding="utf-8"))


def test_outro_scene_and_beat(cfg):
    for code in ("en", "hi"):
        s = branding.add_outro(cfg, _script(code))
        last = s["scenes"][-1]
        assert last["outro"] and "@outrichguy" in last["caption"] and "Cons" in last["caption"] and "out rich guy" in last["line"]
        assert branding.add_outro(cfg, s) == s   # idempotent
    plan = json.loads((ROOT / "prompts" / "sample_plan.json").read_text(encoding="utf-8"))
    s = branding.add_outro(cfg, _script("en"))
    p = branding.force_outro_beat(plan, s)
    assert len(p["beats"]) == len(s["scenes"])
    hero = p["beats"][-1]["people"][0]
    assert hero["look"] == "cam" and hero["talk"] is True and p["beats"][-1]["spot"] == plan["beats"][0]["spot"]


def test_apply_burns_in_tag_and_holds_outro(cfg, tmp_path):
    src = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:r=30:d=2", "-f", "lavfi",
                    "-i", "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
    timeline = [{"words": [{"word": "x", "start": 0.2, "end": 0.5}]}, {"words": [{"word": "Follow", "start": 1.0, "end": 1.4}]}]
    out = branding.apply(cfg, src, timeline, tmp_path / "out.mp4")
    dur = float(common.ffprobe(out)["format"]["duration"])
    assert dur >= 1.0 + cfg["brand"]["outro_seconds"] - 0.1
    frame = tmp_path / "f.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", str(out), "-frames:v", "1", str(frame)], check=True)
    from PIL import Image
    im = Image.open(frame).convert("RGB")
    assert im.getpixel((540, 360))[0] > 150          # the red FOLLOW button is on screen
    corner = im.crop((780, 80, 1040, 130))
    assert max(p[0] for p in corner.getdata()) > 200  # white handle text in the corner
