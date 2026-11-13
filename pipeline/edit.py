"""Editor: turns pictures/clips + mix + captions into the final 1080x1920 MP4.

Frames are drawn in Python with sub-pixel camera moves (smooth, no jitter),
then piped into ffmpeg which burns captions, adds audio and encodes.
"""
import math
import random
import subprocess

import numpy as np
from PIL import Image, ImageFilter

from .common import ROOT, log, run

W, H = 1080, 1920


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


def _still_frames(img, n, motion, fps, seed, flash):
    base_w = min(img.width, img.height * W / H)
    base_h = base_w * H / W
    cx0, cy0 = img.width / 2, img.height / 2
    for f in range(n):
        p = f / max(n - 1, 1)
        z, dx, dy = _camera(motion, p, f / fps, seed)
        bw, bh = base_w / z, base_h / z
        room_x = (img.width - bw) / 2
        room_y = (img.height - bh) / 2
        cx = cx0 + dx * room_x
        cy = cy0 + dy * room_y
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        frame = img.resize((W, H), Image.BILINEAR, box=box)
        if flash and f < 3:
            frame = Image.blend(frame, Image.new("RGB", (W, H), (255, 255, 255)), 0.55 - f * 0.18)
        yield frame.tobytes()


def _clip_frames(path, n, fps):
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},tpad=stop_mode=clone:stop_duration=60",
         "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    size = W * H * 3
    got = 0
    last = None
    while got < n:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        last = buf
        got += 1
        yield buf
    proc.wait()
    while got < n and last is not None:  # safety: hold last frame
        got += 1
        yield last


def render(cfg, script, assets, timeline, total, captions_path, mix_path, workdir):
    fps = cfg["video"]["fps"]
    # cut points: hard cut just before each line starts
    cuts = [0.0] + [max(0.0, t["start"] - 0.06) for t in timeline[1:]] + [total]
    frames_at = [round(c * fps) for c in cuts]
    out = workdir / "final.mp4"
    fontsdir = ROOT / "assets" / "fonts"
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", str(mix_path),
           "-vf", f"subtitles=filename={captions_path.name}:fontsdir={fontsdir}",
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{total:.3f}", "-movflags", "+faststart", out.name]
    log("Rendering video")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=workdir)
    try:
        for i, (sc, asset) in enumerate(zip(script["scenes"], assets)):
            n = frames_at[i + 1] - frames_at[i]
            if n <= 0:
                continue
            if str(asset).lower().endswith((".mp4", ".mov", ".webm")):
                gen = _clip_frames(asset, n, fps)
            else:
                gen = _still_frames(_prep_still(asset), n, sc.get("motion", "zoom_in"), fps, i * 97,
                                    flash=sc.get("motion") == "shake" or sc.get("sfx") == "hit")
            for buf in gen:
                proc.stdin.write(buf)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg render failed")
    return out


def finish_external(cfg, src, workdir):
    """For higgsfield_full: just normalise format/loudness of a finished video."""
    out = workdir / "final_norm.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", src,
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    return out
