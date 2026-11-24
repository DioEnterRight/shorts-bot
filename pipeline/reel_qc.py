"""Reel director QC (.claude/skills/reel-director/quality-control): look at real pixels, score, fix only weak scenes.

1. preview_review(): one rendered still per scene -> numbered contact sheet -> a free vision model judges every scene against its
   narration line (reel-director/quality-control/visual-review.md). Weak scenes get a targeted rewrite in cartoon3d.free_storyboard().
2. inspect_final(): checks the finished MP4 with ffprobe/ffmpeg and real frame samples (export, black/frozen frames, loudness and
   clipping, silences, caption pixels, A/V sync), adds shot metrics from the compiled data and the vision scores, and writes a
   weighted 100-point report (quality_report.md/json). Categories nothing could inspect are marked "not inspected", never guessed.
"""
import base64
import io
import json
import math
import re
import subprocess

from . import freellm

# category: (weight, label) - reel-director/quality-control/scoring.md
WEIGHTS = {
    "story": (15, "Storytelling and creativity"),
    "camera": (15, "Cinematic camera direction"),
    "visual": (15, "Visual storytelling and composition"),
    "assets": (10, "3D models and environments"),
    "animation": (10, "Animation and motion"),
    "voice": (10, "Voice quality"),
    "captions": (10, "Captions"),
    "editing": (10, "Editing and transitions"),
    "technical": (5, "Technical export quality"),
}
WEAK = 6   # scenes scored below this (or not showing their line) are rewritten


# ---------------------------------------------------------------- preview (before the long render)
def scene_frames(data):
    """One representative frame per scene: 70 % into the scene's first shot (after most cue reveals)."""
    out = {}
    for s in data["shots"]:
        if s["scene"] not in out:
            out[s["scene"]] = s["a"] + int((s["b"] - s["a"]) * 0.7)
    return [out[i] for i in sorted(out)]


def contact_sheet(paths, cols=None):
    """Numbered grid of stills -> JPEG bytes (max ~1100 px wide so vision models read it cheaply)."""
    from PIL import Image, ImageDraw, ImageFont
    n = len(paths); cols = cols or (3 if n <= 6 else 4)
    w, h = 270, 480
    rows = math.ceil(n / cols)
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB").resize((w, h))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 58, 46], fill="black"); d.text((8, 4), str(i + 1), fill="white", font=font)
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    buf = io.BytesIO(); sheet.save(buf, "JPEG", quality=82); return buf.getvalue()


def _clamp(v, lo=0.0, hi=10.0):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return None


def parse_review(raw, n):
    """Model reply -> {"scenes": [n entries], "storytelling".."continuity", "summary"}; missing scenes are marked unscored."""
    by_n = {}
    for s in raw.get("scenes") or []:
        if isinstance(s, dict) and str(s.get("n", "")).isdigit() and 1 <= int(s["n"]) <= n:
            by_n[int(s["n"])] = s
    scenes = []
    for i in range(1, n + 1):
        s = by_n.get(i, {})
        sc = _clamp(s.get("score"))
        scenes.append({"n": i, "score": sc, "shows_line": bool(s.get("shows_line")) if sc is not None else None,
                       "issue": str(s.get("issue") or "")[:200], "fix": str(s.get("fix") or "")[:300]})
    out = {"scenes": scenes, "summary": str(raw.get("summary") or "")[:300]}
    for k in ("storytelling", "composition", "assets", "camera", "continuity"):
        out[k] = _clamp(raw.get(k))
    return out


def weak_scenes(review, limit=4):
    weak = [s for s in review["scenes"] if s["score"] is not None and (s["score"] < WEAK or s["shows_line"] is False)]
    return sorted(weak, key=lambda s: s["score"])[:limit]


def review_mean(review, only=None):
    vals = [s["score"] for s in review["scenes"] if s["score"] is not None and (only is None or s["n"] in only)]
    return sum(vals) / len(vals) if vals else None


def preview_review(cfg, budget, sheet_jpeg, script, director_text):
    """-> parsed review. Raises RuntimeError when no vision model answers (the caller then skips visual QC and says so)."""
    lines = "\n".join(f"{i + 1}. \"{sc['line']}\"" for i, sc in enumerate(script["scenes"]))
    content = [{"type": "text", "text": f"{director_text}\n\nShort: \"{script['title']}\"\nNarration per scene:\n{lines}"},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(sheet_jpeg).decode()}}]
    reply = freellm.chat(cfg, [{"role": "user", "content": content}], budget)
    review = parse_review(freellm.extract_json(reply), len(script["scenes"]))
    if review_mean(review) is None:
        raise RuntimeError("visual review came back without scene scores")
    return review


# ---------------------------------------------------------------- final inspection (after the render)
def _ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,duration,sample_rate,channels",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout).get("streams", [])


def _ff_log(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats"] + args, capture_output=True, text=True).stderr


def _black(path):
    out = _ff_log(["-i", str(path), "-vf", "blackdetect=d=0.25:pix_th=0.06", "-an", "-f", "null", "-"])
    return [float(m) for m in re.findall(r"black_duration:([\d.]+)", out)]


def _frozen(path):
    out = _ff_log(["-i", str(path), "-vf", "freezedetect=n=0.0008:d=1.6", "-an", "-f", "null", "-"])
    return [float(m) for m in re.findall(r"freeze_duration: ([\d.]+)", out)]


def _loudness(path):
    out = _ff_log(["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    tp = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", out)
    return (float(i[-1]) if i else None, float(tp[-1]) if tp and tp[-1] != "-inf" else None)


def _silences(path, start, end):
    out = _ff_log(["-i", str(path), "-af", "silencedetect=n=-40dB:d=1.2", "-f", "null", "-"])
    s = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    return [t for t in s if start + 0.5 < t < end - 1.5]


def _caption_hits(path, times, w=1080, h=1920):
    """Grab frames at word times and look for the lime current-word colour in the caption band (bottom 30 %)."""
    from PIL import Image
    hits = 0
    for t in times:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        if not r.stdout:
            continue
        im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        import numpy as np
        band = np.asarray(im.crop((0, int(im.height * 0.62), im.width, int(im.height * 0.95))).resize((270, 160))).astype(int)
        r_, g, b = band[..., 0], band[..., 1], band[..., 2]
        lime = int(((g > 200) & (r_ > 140) & (r_ < 225) & (b < 130)).sum())
        hits += lime > 25
    return hits


def shot_metrics(data):
    shots = data["shots"]
    lens = [(s["b"] - s["a"] + 1) / data["fps"] for s in shots]
    pairs = [(s.get("kind"), s.get("move")) for s in shots]
    repeats = sum(1 for i in range(1, len(pairs)) if pairs[i] == pairs[i - 1])
    anims = sum(1 for sc in data["scenes"] for p in sc["props"] if p.get("anim"))
    reacts = len({(s["scene"], c.get("who")) for s in shots for c in s["cast"] if c.get("react")})
    story_objects = sum(1 for sc in data["scenes"] for p in sc["props"] if p.get("prefab"))
    return {"shots": len(shots), "max_shot_s": round(max(lens), 2), "min_shot_s": round(min(lens), 2),
            "shot_types": len({p[0] for p in pairs}), "moves": len({p[1] for p in pairs}), "repeats": repeats,
            "holds": sum(1 for p in pairs if p[1] == "hold"), "anims": anims, "reactions": reacts,
            "story_objects": story_objects, "scenes": len(data["scenes"])}


def _avg(*vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def inspect_final(mp4, data, words, review=None, captions=True):
    """-> report dict {score, verdict, critical, categories, checks, metrics}."""
    crit, notes = [], []
    st = _ffprobe(mp4)
    v = next((s for s in st if s["codec_type"] == "video"), None)
    a = next((s for s in st if s["codec_type"] == "audio"), None)
    tech = 10.0
    if not v:
        crit.append("no video stream")
    else:
        num, _, den = v.get("r_frame_rate", "0/1").partition("/")
        fps = float(num) / max(1.0, float(den or 1))
        if (v.get("width"), v.get("height")) != (1080, 1920):
            crit.append(f"resolution {v.get('width')}x{v.get('height')} (need 1080x1920)")
        if abs(fps - 30) > 0.01:
            crit.append(f"frame rate {fps:.2f} (need 30)")
        if v.get("pix_fmt") != "yuv420p" or v.get("codec_name") != "h264":
            tech -= 4; notes.append(f"video {v.get('codec_name')}/{v.get('pix_fmt')}")
    if not a:
        crit.append("no audio stream")
    vdur, adur = float((v or {}).get("duration") or 0), float((a or {}).get("duration") or 0)
    if v and a and abs(vdur - adur) > 0.2:
        crit.append(f"audio and video lengths differ by {abs(vdur - adur):.2f} s")
    elif v and a and abs(vdur - adur) > 0.08:
        tech -= 2; notes.append(f"A/V length differs by {abs(vdur - adur):.2f} s")
    black = _black(mp4)
    if sum(black) >= 0.5:
        crit.append(f"black frames for {sum(black):.1f} s")
    elif black:
        tech -= 3; notes.append(f"short black flash ({sum(black):.2f} s)")
    frozen = _frozen(mp4)
    if any(f >= 2.5 for f in frozen):
        crit.append(f"frozen picture for {max(frozen):.1f} s")
    # voice / mix
    I, tp = _loudness(mp4) if a else (None, None)
    voice = 10.0
    if I is None or I < -40:
        voice = 0.0
        crit.append("audio is silent" if I is not None else "loudness could not be measured")
    else:
        if not -16.5 <= I <= -11.5:
            voice -= 3; notes.append(f"loudness {I:.1f} LUFS (target -14)")
        if tp is not None and tp > -0.5:
            voice -= 3; notes.append(f"peak {tp:.1f} dBFS (clipping risk)")
    flat = [w for line in words for w in line]
    speech_start = float(flat[0]["start"]) if flat else 0.0
    speech_end = float(flat[-1]["end"]) if flat else vdur
    gaps = _silences(mp4, speech_start, speech_end) if a else []
    if gaps:
        voice -= 2 * min(2, len(gaps)); notes.append(f"{len(gaps)} silence(s) over 1.2 s inside the narration")
    # captions: real pixels at word times
    caps = None
    if captions and flat:
        times = [(float(w["start"]) + float(w["end"])) / 2 for w in flat[:: max(1, len(flat) // 6)]][:6]
        hits = _caption_hits(mp4, times)
        caps = 10.0 * hits / max(1, len(times))
        if hits == 0:
            crit.append("no captions visible at word times")
        elif hits < len(times):
            notes.append(f"captions seen at {hits}/{len(times)} word times")
        if any(float(flat[i]["start"]) < float(flat[i - 1]["start"]) for i in range(1, len(flat))):
            caps -= 3; notes.append("word timings out of order")
    # shots from the compiled data
    m = shot_metrics(data)
    cam_code = 10.0
    cam_code -= 2.5 * m["repeats"]
    cam_code -= max(0, 4 - m["shot_types"]) * 1.2 + max(0, 4 - m["moves"]) * 1.0
    cam_code -= max(0, m["holds"] - m["shots"] // 3) * 0.8
    edit = 10.0
    if m["max_shot_s"] > 4.0:
        edit -= 3; notes.append(f"a shot runs {m['max_shot_s']} s")
    if m["min_shot_s"] < 0.6:
        edit -= 2; notes.append(f"a shot is only {m['min_shot_s']} s")
    edit -= 2.5 * m["repeats"]
    anim = 10.0 - max(0, 3 - m["anims"] - m["reactions"]) * 1.5 - (3 if any(f >= 1.6 for f in frozen) else 0)
    assets_code = min(10.0, 6 + m["story_objects"] / max(1, m["scenes"]) * 2)
    R = review or {}
    scenes = [s for s in R.get("scenes", []) if s.get("score") is not None]
    visual = None
    if scenes:
        shown = sum(1 for s in scenes if s["shows_line"]) / len(scenes)
        visual = _avg(sum(s["score"] for s in scenes) / len(scenes), R.get("composition")) * (0.7 + 0.3 * shown)
    cats = {
        "story": R.get("storytelling"),
        # variety alone can't prove a shot is cinematic: without the vision review camera tops out at 8
        "camera": _avg(cam_code, cam_code, cam_code, R.get("camera"), R.get("camera")) if R.get("camera") is not None else min(8.0, cam_code),
        "visual": visual,
        "assets": _avg(assets_code, R.get("assets"), R.get("continuity")) if R.get("assets") is not None else None,
        "animation": max(0.0, anim),
        "voice": max(0.0, voice),
        "captions": None if caps is None else max(0.0, caps),
        "editing": max(0.0, edit),
        "technical": max(0.0, tech),
    }
    used = {k: v_ for k, v_ in cats.items() if v_ is not None}
    wsum = sum(WEIGHTS[k][0] for k in used)
    score = round(sum(WEIGHTS[k][0] * used[k] / 10 for k in used) * 100 / wsum) if wsum else 0
    if crit:
        verdict = "REJECTED (critical defect)"
    elif score >= 90:
        verdict = "Production ready"
    elif score >= 80:
        verdict = "Minor improvements"
    elif score >= 70:
        verdict = "Requires revision"
    else:
        verdict = "Rework required"
    if not crit and cats["visual"] is None:
        verdict += " on technical checks only (pictures not reviewed)"
    return {"score": score, "verdict": verdict, "partial": wsum < 100, "critical": crit, "notes": notes,
            "categories": {k: (None if v_ is None else round(v_, 1)) for k, v_ in cats.items()}, "metrics": m,
            "loudness_lufs": I, "true_peak_db": tp, "duration": round(vdur, 2), "review": R}


def report_markdown(rep, title=""):
    rows = "\n".join(f"| {WEIGHTS[k][1]} | {WEIGHTS[k][0]} | " + ("not inspected" if v is None else f"{v:.1f}/10") + " |"
                     for k, v in rep["categories"].items())
    sc = rep.get("review", {}).get("scenes") or []
    scene_rows = "\n".join(f"| {s['n']} | {'-' if s['score'] is None else s['score']:g} | {'yes' if s['shows_line'] else 'no' if s['shows_line'] is False else '-'} | {s['issue'] or ''} |"
                           for s in sc) if sc else ""
    m = rep["metrics"]
    out = f"""## Reel QC: {title}

**Score {rep['score']}/100 - {rep['verdict']}**{' (partial: some categories could not be inspected, the score uses the rest)' if rep['partial'] else ''}

| Category | Weight | Result |
|---|---:|---|
{rows}

Critical defects: {', '.join(rep['critical']) or 'none'}
Notes: {'; '.join(rep['notes']) or 'none'}
Shots: {m['shots']} ({m['shot_types']} shot types, {m['moves']} camera moves, {m['repeats']} repeats), longest {m['max_shot_s']} s;
animated objects {m['anims']}, reaction beats {m['reactions']}, story objects {m['story_objects']} in {m['scenes']} scenes.
Loudness {rep['loudness_lufs']} LUFS, peak {rep['true_peak_db']} dBFS, length {rep['duration']} s.
"""
    if scene_rows:
        out += f"\nVisual review per scene (free vision model, on preview stills):\n\n| Scene | Score | Shows the line | Issue |\n|---:|---:|---|---|\n{scene_rows}\n"
        if rep["review"].get("summary"):
            out += f"\n{rep['review']['summary']}\n"
    return out
