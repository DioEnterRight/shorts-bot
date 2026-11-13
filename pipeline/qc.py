"""Quality gate: never post a broken video."""
from .common import ffprobe, log


def check(path, min_s=10, max_s=89):
    info = ffprobe(path)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    problems = []
    if not v:
        problems.append("no video stream")
    else:
        w, h = int(v[0]["width"]), int(v[0]["height"])
        if abs(w / h - 9 / 16) > 0.02:
            problems.append(f"not 9:16 ({w}x{h})")
    if not a:
        problems.append("no audio")
    if not (min_s <= dur <= max_s):
        problems.append(f"length {dur:.1f}s outside {min_s}-{max_s}s")
    size_mb = int(info["format"]["size"]) / 1e6
    if size_mb > 300:
        problems.append(f"file too big ({size_mb:.0f} MB)")
    if problems:
        raise RuntimeError("Quality check failed: " + "; ".join(problems))
    log(f"QC passed: {dur:.1f}s, {size_mb:.1f} MB")
    return dur
