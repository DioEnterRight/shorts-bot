"""Channel branding (config.yaml `brand`) for every Short, whichever engine drew it (kit or toon2d):

  * "@outrichguy" in the top-right corner of every frame
  * a last-~3-seconds outro: an extra script scene where the main character faces the viewer and says
    "Follow Cons and Coins, and @outrichguy" (mouth moving), while a FOLLOW card shows the channel name and the handle

  add_outro(cfg, script)          -> script with the outro scene appended (before the voice is made)
  force_outro_beat(plan, script)  -> the kit shot plan with a fixed last beat: hero at the opening place, talking to camera
  apply(cfg, video, timeline, out)-> final video with the corner tag + the FOLLOW card (and >= outro_seconds of outro)
"""
import copy
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, ffprobe, log, run

FONT = ROOT / "toon2d" / "fonts" / "PermanentMarker-Regular.ttf"


def add_outro(cfg, script):
    b = cfg["brand"]
    o = b["outro"].get(script.get("language", "en")) or b["outro"]["en"]
    script = copy.deepcopy(script)
    if script["scenes"] and script["scenes"][-1].get("outro"):
        return script
    script["scenes"].append({"line": o["spoken"], "caption": o["caption"], "overlay": "", "emphasis": "",
                             "visual": "OUTRO: the main character from the opening faces the camera, smiles, waves and "
                                       "points up at the FOLLOW card; same place as the first shot.", "outro": True})
    return script


def force_outro_beat(plan, script):
    """The last beat of the kit plan = the outro: the opening place, the hero talking to camera (wave, then point)."""
    if not isinstance(plan, dict) or not plan.get("beats") or not script["scenes"][-1].get("outro"):
        return plan
    plan = copy.deepcopy(plan)
    first = plan["beats"][0]
    role = next((p.get("role") for p in first.get("people", []) if p.get("role")), "hero")
    beat = {"spot": first.get("spot"), "why": "outro: follow the channel",
            "people": [{"role": role, "at": "center", "look": "cam", "talk": True,
                        "acts": [["start", "wave", "grin"], [1.0, "point", "happy"]]}],
            "camera": [{"at": "start", "on": [role], "size": "MCU", "angle": 0, "height": 3}],
            "props": [], "sfx": [["start", "ding"]]}
    n = len(script["scenes"])
    beats = plan["beats"][: n - 1]
    plan["beats"] = beats + [beat]
    return plan


def _font(size):
    return ImageFont.truetype(str(FONT), size)


def _centered(d, y, text, size, fill, stroke=0, W=1080):
    f = _font(size)
    while d.textlength(text, font=f) > W - 120 and size > 30:
        size -= 4
        f = _font(size)
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(17, 17, 17))


def overlays(cfg, size, workdir):
    """Two full-frame transparent PNGs: the corner tag and the FOLLOW card."""
    b = cfg["brand"]
    W, H = size
    corner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(corner)
    f = _font(40)
    tw = d.textlength(b["corner_handle"], font=f)
    x1, y0 = W - 100, 70   # 100 px in from the edge: phones crop the sides of 9:16 a little
    d.rounded_rectangle((x1 - tw - 52, y0, x1, y0 + 66), radius=33, fill=(0, 0, 0, 130))
    d.text((x1 - tw - 26, y0 + 6), b["corner_handle"], font=f, fill=(255, 255, 255, 240))
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((90, 250, W - 90, 800), radius=36, fill=(244, 241, 234, 245), outline=(17, 17, 17), width=8)
    d.rounded_rectangle((W / 2 - 210, 300, W / 2 + 210, 420), radius=60, fill=(232, 49, 47), outline=(17, 17, 17), width=6)
    _centered(d, 312, "FOLLOW", 84, (255, 255, 255))
    _centered(d, 470, b["channel_name"].upper(), 110, (17, 17, 17))
    _centered(d, 640, "& " + b["corner_handle"], 84, (232, 49, 47))
    workdir.mkdir(parents=True, exist_ok=True)
    corner.save(workdir / "brand_corner.png")
    card.save(workdir / "brand_card.png")
    return workdir / "brand_corner.png", workdir / "brand_card.png"


def apply(cfg, video, timeline, out):
    """Burn in the corner tag on every frame and the FOLLOW card from the outro line on; hold the last frame so the
    outro lasts at least brand.outro_seconds."""
    info = ffprobe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"]["duration"])
    start = float(timeline[-1]["words"][0]["start"]) if timeline and timeline[-1].get("words") else max(0.0, dur - 3)
    hold = max(0.0, start + float(cfg["brand"]["outro_seconds"]) - dur)
    corner, card = overlays(cfg, (int(v["width"]), int(v["height"])), Path(out).parent)
    fc = (f"[0:v]tpad=stop_mode=clone:stop_duration={hold:.3f}[v0];"
          f"[2:v]format=rgba,fade=t=in:st={start:.3f}:d=0.25:alpha=1[c];"
          f"[v0][1:v]overlay=0:0:shortest=1[v1];"
          f"[v1][c]overlay=0:0:enable='gte(t,{start:.3f})':shortest=1[v];"
          f"[0:a]apad=pad_dur={hold:.3f}[a]")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-loop", "1", "-i", str(corner), "-loop", "1", "-i", str(card),
         "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur + hold:.3f}", "-movflags", "+faststart", str(out)])
    log(f"branding: corner tag + FOLLOW card from {start:.1f}s (held {hold:.1f}s extra)")
    (Path(out).parent / "brand.json").write_text(json.dumps({"outro_start": start, "held": hold}), encoding="utf-8")
    return Path(out)
