#!/usr/bin/env python3
"""Stream frames/f%04d.jpg as raw rgb24 to stdout:  python3 frames_rgb.py frames 1100 | ffmpeg -f rawvideo -pix_fmt rgb24 ...
JPEGs are full-range YCbCr; ffmpeg's handling of that range differs by version (newer ones keep it full range).
Pillow decodes to RGB here, so ffmpeg only ever sees RGB, the same proven path the 2D engine uses."""
import sys
from PIL import Image

d, n = sys.argv[1], int(sys.argv[2])
out = sys.stdout.buffer
size = None
for i in range(n):
    im = Image.open(f"{d}/f{i:04d}.jpg").convert("RGB")
    if size is None:
        size = im.size
    elif im.size != size:
        sys.exit(f"frame {i} is {im.size}, expected {size}")
    out.write(im.tobytes())
