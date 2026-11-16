"""Remotion render path: Python builds a props JSON, the remotion/ project draws the video.

Python owns timing (scene frames, word times, sound cues); Remotion only draws. The props are
validated here before the render and again by the zod schema in remotion/src/bot/schema.ts.

  explainer style: each scene = its picture (from the visuals provider) with a camera move,
                   remocn transitions, overlay sticker / counter, impact bursts, word captions.
  blocky style:    each scene = a three.js toy world with original blocky characters acting
                   (no pictures needed, so no Cloudflare credits are spent).
"""
import json
import shutil
import subprocess
from pathlib import Path

from .audio import sfx_cues
from .common import ROOT, log
from .edit import HALF, plan

REMOTION = ROOT / "remotion"
COMPOSITION = "ShortsBot"
STYLES = {"explainer", "blocky"}
CAPTION_STYLES = {"word_pop", "karaoke", "highlight_box", "bounce_in", "active_pop", "outline", "stamp"}
CAMERAS = {"punch_in", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "shake"}
TRANSITIONS = {"cut", "whip", "zoom", "fade", "iris", "wave"}
SFX_FILES = {"hit": "hit", "pop": "pop", "tick": "tick", "whoosh": "whoosh", "boing": "pop", "riser": "whoosh"}
VIDEO_EXT = (".mp4", ".mov", ".webm")


def _caption_tokens(timeline):
    """@remotion/captions format. Tokens after the first carry a leading space (word separator)."""
    out = []
    for line in timeline:
        for w in line["words"]:
            out.append({"text": (" " if out else "") + w["word"], "startMs": round(w["start"] * 1000),
                        "endMs": round(w["end"] * 1000), "timestampMs": None, "confidence": None})
    return out


def _blocky(sc, i):
    if sc.get("sfx") == "hit" or sc.get("camera") == "shake":
        pose = "shock"
    elif sc.get("shot") == "wide":
        pose = "walk"
    elif sc.get("sfx") in ("pop", "boing"):
        pose = "jump"
    else:
        pose = ("talk", "wave", "think")[i % 3]
    return {"pose": pose, "pair": sc.get("shot") in ("wide", "character")}


def build_props(cfg, script, assets, timeline, total, lp, style, audio_name="mix.wav"):
    fps = int(cfg["video"]["fps"])
    n, h = plan(script, timeline, total, fps)
    rc = cfg["render"]
    scenes = []
    for i, (sc, asset) in enumerate(zip(script["scenes"], assets)):
        into = h[i]                       # transition into scene i is centred on the cut
        into_b = into                     # frames shown before the cut
        out_a = h[i + 1] if i + 1 < len(n) else 0
        trans = sc.get("transition", "cut") if into else "cut"
        media = None
        if asset is not None and style == "explainer":
            media = f"scene_{i:02d}{Path(asset).suffix.lower()}"
        scenes.append({
            "durationInFrames": n[i] + into_b + out_a,
            "transitionIn": trans,
            "transitionFrames": 2 * into if trans != "cut" else 0,
            "line": sc["line"],
            "media": media,
            "mediaIsVideo": bool(media and media.endswith(VIDEO_EXT)),
            "camera": sc.get("camera", "zoom_in"),
            "overlay": sc.get("overlay", ""),
            "shot": sc.get("shot", "closeup"),
            "emphasis": sc.get("emphasis", ""),
            "blocky": _blocky(sc, i),
        })
    # A transition of 2*h frames overlaps both scenes, so each scene is extended by h on that side
    # (done above) and the series still totals sum(n) frames: the audio stays in sync.
    words_per_chunk = int(cfg["captions"].get("words_per_chunk", 2))
    starts = [w["start"] for line in timeline for w in line["words"]][::words_per_chunk]
    cues = sfx_cues(cfg, script, timeline, starts)
    gain = 10 ** (cfg["audio"]["sfx_volume_db"] / 20)
    return {
        "fps": fps, "width": int(cfg["video"]["width"]), "height": int(cfg["video"]["height"]),
        "durationInFrames": sum(n),
        "language": script["language"],
        "style": style,
        "captionStyle": rc.get("caption_style", "word_pop"),
        "uppercase": bool(lp.get("caption_uppercase", False)),
        "accent": "#" + cfg["captions"].get("highlight", "FFE600"),
        "audio": audio_name,
        "scenes": scenes,
        "captions": _caption_tokens(timeline),
        "sfx": [{"name": SFX_FILES[name], "frame": round(at * fps), "volume": round(min(1.0, gain * g * 2), 3)}
                for name, at, g in cues if name in SFX_FILES and at < total],
    }


def validate_props(props, public_dir=None):
    """Fail fast before spending render minutes. Mirrors remotion/src/bot/schema.ts."""
    def need(ok, msg):
        if not ok:
            raise ValueError(f"Remotion props: {msg}")
    need(props["style"] in STYLES, f"style {props['style']!r}")
    need(props["captionStyle"] in CAPTION_STYLES, f"captionStyle {props['captionStyle']!r}")
    need(props["fps"] == 30 and props["width"] == 1080 and props["height"] == 1920, "must be 1080x1920 @30fps")
    need(props["scenes"], "no scenes")
    series = 0
    for i, s in enumerate(props["scenes"]):
        need(s["durationInFrames"] > 0, f"scene {i} has no frames")
        need(s["camera"] in CAMERAS, f"scene {i} camera {s['camera']!r}")
        need(s["transitionIn"] in TRANSITIONS, f"scene {i} transition {s['transitionIn']!r}")
        need(i > 0 or s["transitionFrames"] == 0, "first scene cannot have a transition")
        need(s["transitionFrames"] < s["durationInFrames"], f"scene {i} transition longer than scene")
        if i:
            need(s["transitionFrames"] <= props["scenes"][i - 1]["durationInFrames"], f"scene {i} transition too long")
        need(props["style"] == "blocky" or s["media"], f"scene {i} has no picture")
        if public_dir and s["media"]:
            need((Path(public_dir) / s["media"]).exists(), f"missing {s['media']}")
        series += s["durationInFrames"] - s["transitionFrames"]
    need(series == props["durationInFrames"], f"scene frames {series} != {props['durationInFrames']} (audio would drift)")
    last = -1
    for c in props["captions"]:
        need(c["endMs"] >= c["startMs"] >= 0, f"caption {c['text']!r} has bad times")
        need(c["startMs"] >= last, "captions out of order")
        last = c["startMs"]
    for q in props["sfx"]:
        need(0 <= q["frame"] < props["durationInFrames"], f"sfx {q['name']} outside the video")
    if public_dir:
        need((Path(public_dir) / props["audio"]).exists(), "missing audio file")


def stage_public(props, assets, mix_path, workdir):
    """Remotion reads files from one public folder: the run's media + the kit's sfx and fonts."""
    pub = workdir / "remotion_public"
    if pub.exists():
        shutil.rmtree(pub)
    shutil.copytree(REMOTION / "public", pub)
    shutil.copy(mix_path, pub / props["audio"])
    for s, asset in zip(props["scenes"], assets):
        if s["media"]:
            shutil.copy(asset, pub / s["media"])
    return pub


def _browser():
    for name in ("google-chrome", "chromium", "chromium-browser"):
        if p := shutil.which(name):
            return p
    return None   # Remotion downloads its own headless shell


def render(cfg, script, assets, timeline, total, lp, style, mix_path, workdir):
    props = build_props(cfg, script, assets, timeline, total, lp, style)
    pub = stage_public(props, assets, mix_path, workdir)
    validate_props(props, pub)
    props_path = workdir / "remotion_props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    raw = workdir / "remotion_raw.mp4"
    rc = cfg["render"]
    cmd = ["npx", "--no-install", "remotion", "render", "src/index.ts", COMPOSITION, str(raw),
           f"--props={props_path}", f"--public-dir={pub}", f"--concurrency={rc.get('concurrency', 2)}",
           "--log=error", "--codec=h264", "--crf=20", "--pixel-format=yuv420p", "--color-space=bt709"]
    if b := _browser():
        cmd.append(f"--browser-executable={b}")
    log(f"Remotion render: {props['durationInFrames']} frames, style={style}, captions={props['captionStyle']}")
    subprocess.run(cmd, cwd=REMOTION, check=True, timeout=int(rc.get("timeout_minutes", 25)) * 60)
    out = workdir / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-map", "0:v", "-map", "0:a",
                    "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)], check=True)
    raw.unlink()
    shutil.rmtree(pub)
    return out
