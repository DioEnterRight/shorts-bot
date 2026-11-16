"""Quality gate: never post a broken video."""
from .common import ffprobe, log


def check(path, min_s=10, max_s=89, fps=30):
    info = ffprobe(path)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    problems = []
    if not v:
        problems.append("no video stream")
    else:
        w, h = int(v[0]["width"]), int(v[0]["height"])
        if (w, h) != (1080, 1920):
            problems.append(f"not 1080x1920 ({w}x{h})")
        num, den = (int(x) for x in v[0].get("avg_frame_rate", "0/1").split("/"))
        if den and abs(num / den - fps) > 0.5:
            problems.append(f"frame rate {num / den:.2f} != {fps}")
        if v[0].get("codec_name") != "h264" or v[0].get("pix_fmt") != "yuv420p":
            problems.append(f"video codec {v[0].get('codec_name')}/{v[0].get('pix_fmt')} (want h264/yuv420p)")
    if not a:
        problems.append("no audio")
    else:
        if a[0].get("codec_name") != "aac" or int(a[0].get("sample_rate", 0)) != 48000:
            problems.append(f"audio {a[0].get('codec_name')}@{a[0].get('sample_rate')} (want aac@48000)")
        if v and "duration" in v[0] and "duration" in a[0]:
            gap = abs(float(v[0]["duration"]) - float(a[0]["duration"]))
            if gap > 0.25:
                problems.append(f"audio/video length differ by {gap:.2f}s")
    if not (min_s <= dur <= max_s):
        problems.append(f"length {dur:.1f}s outside {min_s}-{max_s}s")
    size_mb = int(info["format"]["size"]) / 1e6
    if size_mb > 300:
        problems.append(f"file too big ({size_mb:.0f} MB)")
    if problems:
        raise RuntimeError("Quality check failed: " + "; ".join(problems))
    log(f"QC passed: {dur:.1f}s, {size_mb:.1f} MB")
    return dur
