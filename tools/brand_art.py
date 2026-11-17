"""Channel art in the toon2d style: profile pictures (1080x1080, IG + YouTube) and a YouTube banner (2560x1440).

    python tools/brand_art.py out/brand

Drawn with the video engine itself (same host character, ink, fonts, icons and world map), so the art
matches the videos. The banner keeps text and the host inside YouTube's 1546x423 all-devices safe area.
"""
import math
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "toon2d"))
import skia  # noqa: E402
from engine.kit import (CREAM, GOLD, INK, KALAM, LIME, LW, MARKER, EMOTIONS, HEAD_CY, POSES, circ, draw_char, fit_size,  # noqa: E402
                        fp, ink, label, make_look, radial, sp, text_w)
from engine.props import draw_prop  # noqa: E402
from engine.sets import SETS  # noqa: E402

NAME = "EXPLORE THE WORLD"
TAGLINE = "weird science, history & you, explained in cartoons"
HOST = make_look({"skin": "tan", "outfit": "hoodie", "color": "#2F7A5A", "shirt": "#E8E0D0",
                  "hair": "curly", "hair_col": "#1C1B22"})
NAVY, OCEAN, LAND = "#0E1840", "#7FC8F8", "#86C96A"


def host(c, x, head_y, s, emotion="excited", pose="wave", face=-0.25):
    eyes, mouth, brow, tilt, ex = EMOTIONS[emotion]
    draw_char(c, x, head_y - HEAD_CY * s, s, HOST, face=face, eyes=eyes, mouth=mouth, brow=brow, brow_tilt=tilt,
              arms=POSES[pose], pupil=ex.get("pupil", 0), sparkle=0.6 if ex.get("sparkle") else 0, light=-1)


def globe(c, x, y, r, face=False, seed=3):
    """Ink-outlined cartoon Earth (optionally with a face)."""
    disk = skia.Path(); disk.addCircle(x, y, r)
    c.drawPath(disk, fp(OCEAN)); c.save(); c.clipPath(disk, doAntiAlias=True)
    rnd = random.Random(seed)
    for (dx, dy, rx, ry) in ((-.45, -.25, .42, .34), (.38, -.42, .30, .22), (.30, .32, .40, .30), (-.25, .55, .22, .15)):
        p = skia.Path(); pts = []
        for i in range(12):
            a = i * math.pi / 6; k = 1 + rnd.uniform(-.25, .25)
            pts.append((x + (dx + rx * k * math.cos(a)) * r, y + (dy + ry * k * math.sin(a)) * r))
        p.moveTo(*pts[0])
        for i in range(12):
            a, b = pts[i], pts[(i + 1) % 12]; p.quadTo(a[0], a[1], (a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        p.close(); c.drawPath(p, fp(LAND)); c.drawPath(p, ink(LW * .8))
    shade = skia.Path(); shade.addCircle(x + r * .28, y + r * .22, r * 1.02)
    c.drawPath(skia.Op(disk, shade, skia.PathOp.kDifference_PathOp), fp((255, 255, 255), 70))
    c.drawPath(skia.Op(shade, disk, skia.PathOp.kIntersect_PathOp), fp((0, 0, 0), 0))
    c.restore()
    hl = skia.Path(); hl.addArc(skia.Rect(x - r * .78, y - r * .78, x + r * .78, y + r * .78), 200, 50)
    c.drawPath(hl, ink(r * .06, (255, 255, 255), 200))
    if face:
        for ex_ in (-.3, .3):
            circ(c, x + ex_ * r, y - .05 * r, .16 * r, "#FFFFFF", LW)
            c.drawCircle(x + ex_ * r + .04 * r, y - .03 * r, .07 * r, fp(INK))
        m = skia.Path(); m.moveTo(x - .25 * r, y + .25 * r); m.quadTo(x, y + .5 * r, x + .25 * r, y + .25 * r)
        c.drawPath(m, ink(LW * 1.6))
    c.drawPath(disk, ink(LW * 1.4))


def paper(c, w, h, top="#FFF3D6", edge="#F0D9A8"):
    c.drawRect(skia.Rect(0, 0, w, h), sp(radial(w / 2, h * .45, max(w, h) * .75,
                                                 [skia.Color(*bytes.fromhex(top[1:])), skia.Color(*bytes.fromhex(edge[1:]))])))
    rnd = random.Random(9)
    for _ in range(int(w * h / 900)):
        c.drawCircle(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(.6, 2.2), fp("#9A8F6E", rnd.randint(10, 30)))


def save(surf, path):
    surf.makeImageSnapshot().save(str(path), skia.kPNG)
    print(path)


def pfp_host_globe(out):
    s_ = skia.Surface(1080, 1080); c = s_.getCanvas()
    paper(c, 1080, 1080)
    globe(c, 540, 470, 400)
    host(c, 540, 560, 2.15, emotion="excited", pose="wave", face=-.2)
    save(s_, out / "pfp_host_globe.png")


def pfp_globe_face(out):
    s_ = skia.Surface(1080, 1080); c = s_.getCanvas()
    c.drawRect(skia.Rect(0, 0, 1080, 1080), fp(NAVY))
    for i in range(0, 1080, 90):
        c.drawLine(i, 0, i, 1080, ink(2, "#1A2658")); c.drawLine(0, i, 1080, i, ink(2, "#1A2658"))
    globe(c, 540, 540, 380, face=True)
    save(s_, out / "pfp_globe_face.png")


def pfp_host_map(out):
    s_ = skia.Surface(1080, 1080); c = s_.getCanvas()
    c.save(); c.translate(540 - 960 * .9, 540 - 540 * .9); c.scale(.9, .9); SETS["map"](c, {"seed": 4}); c.restore()
    c.drawCircle(540, 560, 430, fp(GOLD)); c.drawCircle(540, 560, 430, ink(LW * 1.4))
    host(c, 540, 520, 2.0, emotion="confident", pose="point", face=.25)
    save(s_, out / "pfp_host_map.png")


def banner(out):
    w, h = 2560, 1440
    s_ = skia.Surface(w, h); c = s_.getCanvas()
    k = h / 1080; c.save(); c.translate(w / 2 - 960 * k, 0); c.scale(k, k); SETS["map"](c, {"seed": 2}); c.restore()
    band = skia.Path(); band.addRRect(skia.RRect.MakeRectXY(skia.Rect(480, 520, 2080, 920), 46, 46))
    c.drawPath(band, fp(NAVY, 150))
    # host (left, inside the safe area) and a globe (right, desktop/TV only beyond x=2053)
    host(c, 640, 650, 1.05, emotion="excited", pose="wave", face=.3)
    globe(c, 2300, 720, 230, face=True)
    for name, x, y, s in (("bulb", 1830, 650, .5), ("brain", 1975, 690, .42), ("clock", 1905, 845, .36)):
        draw_prop(c, name, x, y, s, 0.0)
    cx = 1270
    size = fit_size(NAME, 140, 840, MARKER); tw = text_w(NAME, size, MARKER)
    label(c, NAME, cx - tw / 2, 720, size, CREAM, font=MARKER, stroke=size * .12, skew=0, rot=-2)
    size2 = fit_size(TAGLINE, 56, 820, KALAM); tw2 = text_w(TAGLINE, size2, KALAM)
    label(c, TAGLINE, cx - tw2 / 2, 830, size2, LIME, font=KALAM, stroke=size2 * .1, skew=0)
    save(s_, out / "youtube_banner.png")
    # safe-area check copy for review only
    c.drawRect(skia.Rect(507, 508, 2053, 931), ink(6, (255, 60, 60)))
    save(s_, out / "youtube_banner_safe_area_check.png")


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "out" / "brand")
    out.mkdir(parents=True, exist_ok=True)
    for f in (pfp_host_globe, pfp_globe_face, pfp_host_map, banner):
        f(out)
