"""Offline test cards — lets you test the whole pipeline with zero keys."""
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from ..common import ROOT

PALETTES = [((40, 20, 60), (200, 70, 120)), ((10, 40, 60), (40, 170, 200)),
            ((50, 30, 10), (230, 140, 40)), ((15, 50, 30), (90, 200, 120))]


def generate(cfg, script, workdir):
    font_big = ImageFont.truetype(str(ROOT / "assets/fonts/Anton-Regular.ttf"), 110)
    font_small = ImageFont.truetype(str(ROOT / "assets/fonts/Anton-Regular.ttf"), 52)
    paths = []
    for i, sc in enumerate(script["scenes"]):
        a, b = PALETTES[i % len(PALETTES)]
        img = Image.new("RGB", (1080, 1920))
        d = ImageDraw.Draw(img)
        for y in range(1920):
            t = abs(y - 960) / 960
            d.line([(0, y), (1080, y)], fill=tuple(int(b[k] * (1 - t) + a[k] * t) for k in range(3)))
        # a big soft blob so motion is visible
        blob = Image.new("L", (1080, 1920), 0)
        ImageDraw.Draw(blob).ellipse((240, 560, 840, 1160), fill=255)
        blob = blob.filter(ImageFilter.GaussianBlur(60))
        img.paste(Image.new("RGB", img.size, (255, 255, 255)), mask=blob.point(lambda v: v // 4))
        d = ImageDraw.Draw(img)
        d.text((540, 380), f"SCENE {i + 1}", font=font_big, fill="white", anchor="mm")
        wrapped = textwrap.fill(sc["visual"], 30)
        d.multiline_text((540, 1450), wrapped, font=font_small, fill=(255, 255, 255), anchor="mm", align="center")
        p = workdir / f"scene_{i:02d}.png"
        img.save(p)
        paths.append(p)
    return paths
