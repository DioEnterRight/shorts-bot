"""Editor: turns pictures/clips + mix + captions into the final 1080x1920 MP4.

Frames are drawn in Python with sub-pixel camera moves (smooth, no jitter), joined with
transitions, then piped into ffmpeg which burns captions, adds audio and encodes.

Timing never drifts: every scene owns exactly the frames between its narration cut points.
A transition borrows `h` extra frames from both neighbours (the outgoing picture keeps
moving a little longer, the incoming one starts a little earlier) and blends them around
the cut, so the total frame count — and audio sync — is unchanged.
"""
import math
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import ROOT, log, run
from .languages import DEVANAGARI

W, H = 1080, 1920
HALF = {"cut": 0, "fade": 5, "whip": 4, "zoom": 5}   # frames on EACH side of the cut
FONTS = ROOT / "assets" / "fonts"
OVERLAY_Y = 330


def _ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _prep_still(path):
    """Upscale once so per-frame crops stay sharp."""
    img = Image.open(path).convert("RGB")
    scale = max(2160 / img.width, 3840 / img.height, 1.0)
    if scale > 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    return img


def _camera(motion, p, sec, rng_seed):
    """Return (zoom, dx, dy) for progress p in [0,1]; dx/dy in -1..1 of free room."""
    if motion == "punch_in":
        z = 1.0 + 0.16 * _ease(sec / 0.22) + 0.07 * p
        return z, 0, 0
    if motion == "zoom_in":
        return 1.04 + 0.16 * _ease(p), 0, 0
    if motion == "zoom_out":
        return 1.22 - 0.17 * _ease(p), 0, 0
    if motion == "pan_left":
        return 1.2, 0.8 - 1.6 * _ease(p), 0
    if motion == "pan_right":
        return 1.2, -0.8 + 1.6 * _ease(p), 0
    if motion == "pan_up":
        return 1.2, 0, 0.8 - 1.6 * _ease(p)
    if motion == "pan_down":
        return 1.2, 0, -0.8 + 1.6 * _ease(p)
    if motion == "shake":
        decay = math.exp(-sec * 7)
        rng = random.Random(rng_seed + int(sec * 60))
        return 1.12 + 0.05 * p, (rng.random() - 0.5) * 0.6 * decay, (rng.random() - 0.5) * 0.6 * decay
    return 1.1, 0, 0


def _still_frames(img, n, motion, fps, seed, flash_at):
    base_w = min(img.width, img.height * W / H)
    base_h = base_w * H / W
    cx0, cy0 = img.width / 2, img.height / 2
    for f in range(n):
        p = f / max(n - 1, 1)
        z, dx, dy = _camera(motion, p, f / fps, seed)
        bw, bh = base_w / z, base_h / z
        cx = cx0 + dx * (img.width - bw) / 2
        cy = cy0 + dy * (img.height - bh) / 2
        frame = img.resize((W, H), Image.BILINEAR, box=(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))
        if flash_at is not None and 0 <= f - flash_at < 3:
            frame = Image.blend(frame, Image.new("RGB", (W, H), (255, 255, 255)), 0.55 - (f - flash_at) * 0.18)
        yield np.asarray(frame)


def _clip_frames(path, n, fps):
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},tpad=stop_mode=clone:stop_duration=60",
         "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    size = W * H * 3
    got, last = 0, None
    while got < n:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        last = np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 3)
        got += 1
        yield last
    proc.wait()
    if last is None:
        raise RuntimeError(f"Could not read video clip {path}")
    while got < n:  # safety: hold last frame
        got += 1
        yield last


# ---------------- overlays ----------------
def overlay_label(text, lp_code):
    """A rounded label (RGBA) for cutaway/diagram callouts."""
    font_file = "NotoSansDevanagari-Bold.ttf" if DEVANAGARI.search(text) else "NotoSans-Bold.ttf"
    font = ImageFont.truetype(str(FONTS / font_file), 64)
    tw = font.getlength(text)
    pad_x, pad_y, h = 42, 22, 64 + 44
    img = Image.new("RGBA", (int(tw + 2 * pad_x), h + 2 * pad_y), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, pad_y // 2, img.width - 1, img.height - 1 - pad_y // 2), radius=40,
                        fill=(255, 230, 0, 235), outline=(20, 20, 20, 255), width=6)
    d.text((img.width / 2, img.height / 2), text, font=font, fill=(20, 20, 20, 255), anchor="mm")
    return img


def _apply_overlay(frame, label, k):
    """Pop the label in over 6 frames."""
    if label is None or k < 0:
        return frame
    t = _ease(min(1.0, (k + 1) / 6))
    s = 0.6 + 0.4 * t + 0.08 * math.sin(math.pi * t)
    lab = label.resize((max(1, int(label.width * s)), max(1, int(label.height * s))), Image.BILINEAR)
    if t < 1:
        alpha = lab.getchannel("A").point(lambda v: int(v * t))
        lab.putalpha(alpha)
    img = Image.fromarray(frame)
    img.paste(lab, (W // 2 - lab.width // 2, OVERLAY_Y - lab.height // 2), lab)
    return np.asarray(img)


# ---------------- transitions ----------------
def _zoomed(frame, z):
    if abs(z - 1) < 1e-3:
        return frame
    img = Image.fromarray(frame)
    if z > 1:
        bw, bh = W / z, H / z
        return np.asarray(img.resize((W, H), Image.BILINEAR, box=((W - bw) / 2, (H - bh) / 2, (W + bw) / 2, (H + bh) / 2)))
    small = img.resize((int(W * z), int(H * z)), Image.BILINEAR)
    out = Image.new("RGB", (W, H))
    out.paste(small, ((W - small.width) // 2, (H - small.height) // 2))
    return np.asarray(out)


def blend(kind, a, b, alpha):
    """One transition frame between outgoing a and incoming b, alpha 0 -> 1."""
    e = _ease(alpha)
    if kind == "fade":
        return (a.astype(np.float32) * (1 - e) + b.astype(np.float32) * e).astype(np.uint8)
    if kind == "zoom":
        za = _zoomed(a, 1 + 0.8 * e).astype(np.float32)
        zb = _zoomed(b, 1.35 - 0.35 * e).astype(np.float32)
        return (za * (1 - e) + zb * e).astype(np.uint8)
    if kind == "whip":
        sx = int(e * W)
        comp = np.empty_like(a)
        comp[:, :W - sx] = a[:, sx:]
        comp[:, W - sx:] = b[:, :sx]
        k = int(48 * math.sin(math.pi * alpha))
        if k > 2:
            acc = np.zeros(comp.shape, np.float32)
            taps = range(-k, k + 1, max(1, k // 3))
            for t in taps:
                acc += np.roll(comp, t, axis=1)
            comp = (acc / len(taps)).astype(np.uint8)
        return comp
    return b


# ---------------- render ----------------
def plan(script, timeline, total, fps):
    """Frame ranges + transition sizes for every scene."""
    cuts = [0.0] + [max(0.0, t["start"] - 0.06) for t in timeline[1:]] + [total]
    at = [round(c * fps) for c in cuts]
    n = [at[i + 1] - at[i] for i in range(len(script["scenes"]))]
    h = [0] * (len(n) + 1)   # h[i] = half transition INTO scene i
    for i in range(1, len(n)):
        want = HALF.get(script["scenes"][i].get("transition", "cut"), 0)
        h[i] = max(0, min(want, n[i - 1] // 3, n[i] // 3))
    return n, h


def scene_frames(sc, asset, length, pre, fps, seed, label):
    if str(asset).lower().endswith((".mp4", ".mov", ".webm")):
        gen = _clip_frames(asset, length, fps)
    else:
        flash = pre if (sc.get("camera") == "shake" or sc.get("sfx") == "hit") else None
        gen = _still_frames(_prep_still(asset), length, sc.get("camera", "zoom_in"), fps, seed, flash)
    for k, frame in enumerate(gen):
        yield _apply_overlay(frame, label, k - pre)


def render(cfg, script, assets, timeline, total, captions_path, mix_path, workdir):
    fps = cfg["video"]["fps"]
    n, h = plan(script, timeline, total, fps)
    out = workdir / "final.mp4"
    fontsdir = ROOT / "assets" / "fonts"
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", str(mix_path),
           "-vf", f"subtitles=filename={captions_path.name}:fontsdir={fontsdir}",
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{total:.3f}", "-movflags", "+faststart", out.name]
    log(f"Rendering video ({sum(n)} frames, transitions: {sum(1 for x in h if x)})")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=workdir)
    written = 0
    try:
        carry = None
        for i, (sc, asset) in enumerate(zip(script["scenes"], assets)):
            if n[i] <= 0:
                continue
            pre, post = h[i], h[i + 1]
            label = overlay_label(sc["overlay"], script.get("language")) if sc.get("overlay") else None
            gen = scene_frames(sc, asset, pre + n[i] + post, pre, fps, i * 97, label)
            kind = sc.get("transition", "cut")
            for j in range(2 * pre):
                proc.stdin.write(blend(kind, carry[j], next(gen), (j + 0.5) / (2 * pre)).tobytes())
                written += 1
            for _ in range(n[i] - pre - post):
                proc.stdin.write(next(gen).tobytes())
                written += 1
            carry = [next(gen) for _ in range(2 * post)]
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg render failed")
    if written != sum(n):
        raise RuntimeError(f"Frame count mismatch: wrote {written}, planned {sum(n)}")
    return out


def finish_external(cfg, src, workdir):
    """For higgsfield_full: just normalise format/loudness of a finished video."""
    out = workdir / "final_norm.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", src,
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-r", str(cfg["video"]["fps"]),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
    return out
