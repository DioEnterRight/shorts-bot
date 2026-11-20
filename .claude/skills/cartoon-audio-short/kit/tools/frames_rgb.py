#!/usr/bin/env python3
"""Stream frames/f%04d.jpg as raw rgb24 to stdout:  python3 frames_rgb.py frames 1100 | ffmpeg -f rawvideo -pix_fmt rgb24 ...
JPEGs are full-range YCbCr; ffmpeg's handling of that range differs by version (newer ones keep it full range).
Pillow decodes to RGB here, so ffmpeg only ever sees RGB, the same proven path the 2D engine uses.
CAPTIONS=1 also burns in 3-word caption chunks (current word lime, the rest cream, dark outline) from work/words.json,
the same look as the 2D Shorts. Fails fast if the font or word timings are missing."""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

LIME, CREAM, INK = (184, 240, 74), (255, 246, 220), (24, 22, 27)
CHUNK = 3


def caption_chunks(words):
    """words: [{w, s, e}] -> [(start, end, [w...], [start...])], 3 words each; a chunk stays until the next one starts."""
    chunks = []
    for j in range(0, len(words), CHUNK):
        part = words[j:j + CHUNK]
        nxt = words[j + CHUNK]["s"] if j + CHUNK < len(words) else part[-1]["e"] + 0.15
        chunks.append((part[0]["s"], nxt, [w["w"] for w in part], [w["s"] for w in part]))
    return chunks


def caption_at(chunks, t):
    for a, b, ws, ts in chunks:
        if a <= t < b:
            return ws, max(k for k, x in enumerate(ts) if x <= t)
    return None


def draw_caption(im, words, k, font_path, y_frac=0.79, size=96):
    W, H = im.size
    size = size * W / 1080
    gap = lambda f: f.size * 0.3
    f = ImageFont.truetype(font_path, int(size))
    widths = [f.getlength(w) for w in words]
    while sum(widths) + gap(f) * (len(words) - 1) > W - 120 * W / 1080 and f.size > 50 * W / 1080:
        f = ImageFont.truetype(font_path, int(f.size * 0.9)); widths = [f.getlength(w) for w in words]
    x = W / 2 - (sum(widths) + gap(f) * (len(words) - 1)) / 2
    d = ImageDraw.Draw(im)
    for i, (w, wd) in enumerate(zip(words, widths)):
        d.text((x, H * y_frac), w, font=f, anchor="ls", fill=LIME if i == k else CREAM, stroke_width=max(2, int(f.size * 0.09)), stroke_fill=INK)
        x += wd + gap(f)


def main(frames_dir, n, project="."):
    caps = None
    if os.environ.get("CAPTIONS") == "1":
        font = os.path.join(project, "fonts", "Kalam-Bold.ttf")
        words_json = os.path.join(project, "work", "words.json")
        for need in (font, words_json):
            if not os.path.exists(need):
                sys.exit(f"frames_rgb: CAPTIONS=1 but {need} is missing")
        caps = caption_chunks(json.load(open(words_json, encoding="utf-8")))
        ImageFont.truetype(font, 40)   # fails here, not mid-video
    out = sys.stdout.buffer
    size = None
    for i in range(n):
        im = Image.open(f"{frames_dir}/f{i:04d}.jpg").convert("RGB")
        if size is None:
            size = im.size
        elif im.size != size:
            sys.exit(f"frame {i} is {im.size}, expected {size}")
        if caps:
            hit = caption_at(caps, i / 30)
            if hit:
                draw_caption(im, hit[0], hit[1], font)
        out.write(im.tobytes())


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
