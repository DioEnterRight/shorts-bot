"""Offline test cards — lets you test the whole pipeline with zero keys.

Each card shows the scene number, its shot type and what the picture is supposed to show,
in a different colour per shot type, so you can check narration-to-picture mapping,
transitions, captions and overlays in the test video.
"""
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..common import ROOT

SHOT_COLORS = {"character": ((40, 20, 60), (200, 70, 120)), "cutaway": ((60, 10, 20), (230, 90, 70)),
               "diagram": ((10, 40, 60), (40, 170, 200)), "metaphor": ((50, 30, 10), (230, 160, 40)),
               "closeup": ((15, 50, 30), (90, 200, 120)), "wide": ((20, 25, 60), (110, 120, 230))}
W, H = 864, 1536


def generate(cfg, script, workdir):
    fonts = ROOT / "assets/fonts"
    font_big = ImageFont.truetype(str(fonts / "Anton-Regular.ttf"), 90)
    font_small = ImageFont.truetype(str(fonts / "NotoSans-Bold.ttf"), 38)
    paths = []
    for i, sc in enumerate(script["scenes"]):
        a, b = SHOT_COLORS.get(sc.get("shot"), SHOT_COLORS["closeup"])
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = abs(y - H * 0.4) / (H * 0.6)
            d.line([(0, y), (W, y)], fill=tuple(int(b[k] * (1 - t) + a[k] * t) for k in range(3)))
        blob = Image.new("L", (W, H), 0)
        cx = 200 + (i * 137) % 460
        ImageDraw.Draw(blob).ellipse((cx - 220, 300, cx + 220, 740), fill=255)
        blob = blob.filter(ImageFilter.GaussianBlur(50))
        img.paste(Image.new("RGB", img.size, (255, 255, 255)), mask=blob.point(lambda v: v // 3))
        d = ImageDraw.Draw(img)
        d.text((W // 2, 420), f"{i + 1} · {sc.get('shot', '?').upper()}", font=font_big, fill="white", anchor="mm")
        wrapped = textwrap.fill(sc["visual"].replace("[GUY]", "GUY"), 34)
        d.multiline_text((W // 2, 760), wrapped, font=font_small, fill=(255, 255, 255), anchor="ma", align="center")
        p = workdir / f"scene_{i:02d}.png"
        img.save(p)
        paths.append(p)
    return paths
