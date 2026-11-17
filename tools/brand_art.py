"""Cons & Coins channel art in the toon2d style: profile pictures (1080x1080, IG + YouTube) and a YouTube banner (2560x1440).

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

NAME = "CONS & COINS"
TAGLINE = "scams, heists & money psychology, in cartoons"
HOST = make_look({"skin": "tan", "outfit": "hoodie", "color": "#2F7A5A", "shirt": "#E8E0D0",
                  "hair": "curly", "hair_col": "#1C1B22"})
CONMAN = make_look({"skin": "tan", "outfit": "suit", "color": "#2B2B33", "shirt": "#F4EFE2", "tie": "#C8242C",
                    "hair": "slick", "hair_col": "#1C1B22", "moustache": True, "hat": "fedora"})
FELT, GOLD_D = "#1F5A3C", "#C9952E"


def host(c, x, head_y, s, emotion="excited", pose="wave", face=-0.25, look=None):
    eyes, mouth, brow, tilt, ex = EMOTIONS[emotion]
    draw_char(c, x, head_y - HEAD_CY * s, s, look or HOST, face=face, eyes=eyes, mouth=mouth, brow=brow, brow_tilt=tilt,
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


def felt(c, w, h):
    c.drawRect(skia.Rect(0, 0, w, h), sp(radial(w / 2, h * .45, max(w, h) * .7,
                                                 [skia.Color(0x2E, 0x7A, 0x52), skia.Color(0x14, 0x3D, 0x29)])))
    rnd = random.Random(5)
    for _ in range(int(w * h / 700)):
        c.drawCircle(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(.6, 1.8), fp((0, 0, 0), rnd.randint(12, 30)))


def coin(c, x, y, r, face=False, hat=False):
    """Gold coin; with face=True a sly mascot, hat=True adds a fedora."""
    circ(c, x, y + r * .08, r, GOLD_D, LW * 1.4)
    circ(c, x, y, r, GOLD, LW * 1.4)
    c.drawCircle(x, y, r * .8, ink(LW * .7, GOLD_D))
    if face:
        for ex_ in (-.3, .3):   # half-closed, sly eyes
            c.drawCircle(x + ex_ * r, y - .08 * r, .1 * r, fp(INK))
            lid = skia.Path(); lid.moveTo(x + ex_ * r - .16 * r, y - .16 * r); lid.lineTo(x + ex_ * r + .16 * r, y - .12 * r)
            c.drawPath(lid, ink(LW * 1.8))
        m = skia.Path(); m.moveTo(x - .22 * r, y + .25 * r); m.quadTo(x + .05 * r, y + .4 * r, x + .3 * r, y + .16 * r)
        c.drawPath(m, ink(LW * 1.8))
    else:
        label(c, "$", x - r * .22, y + r * .32, r * .9, GOLD_D, font=MARKER, skew=0)
    if hat:
        brim = skia.Path(); brim.addOval(skia.Rect(x - r * .95, y - r * 1.02, x + r * .95, y - r * .72)); shape_ = brim
        crown = skia.Path(); crown.addRRect(skia.RRect.MakeRectXY(skia.Rect(x - r * .55, y - r * 1.55, x + r * .55, y - r * .85), r * .2, r * .2))
        c.save(); c.rotate(-8, x, y)
        c.drawPath(crown, fp("#2B2B33")); c.drawPath(crown, ink(LW * 1.2))
        c.drawRect(skia.Rect(x - r * .55, y - r * 1.05, x + r * .55, y - r * .9), fp("#C8242C"))
        c.drawPath(shape_, fp("#2B2B33")); c.drawPath(shape_, ink(LW * 1.2))
        c.restore()


def pfp_conman(out):
    s_ = skia.Surface(1080, 1080); c = s_.getCanvas()
    felt(c, 1080, 1080)
    c.drawCircle(540, 540, 430, fp(GOLD)); c.drawCircle(540, 540, 430, ink(LW * 1.4))
    host(c, 540, 560, 2.0, emotion="smug", pose="tiphat", face=-.25, look=CONMAN)
    save(s_, out / "pfp_conman.png")


def pfp_coin(out):
    s_ = skia.Surface(1080, 1080); c = s_.getCanvas()
    felt(c, 1080, 1080)
    coin(c, 540, 600, 330, face=True, hat=True)
    save(s_, out / "pfp_coin.png")


def pfp_host_cash(out):
    s_ = skia.Surface(1080, 1080); c = s_.getCanvas()
    c.drawRect(skia.Rect(0, 0, 1080, 1080), fp(GOLD))
    rnd = random.Random(2)
    for _ in range(9):
        coin(c, rnd.uniform(80, 1000), rnd.uniform(80, 1000), rnd.uniform(45, 80))
    host(c, 470, 560, 2.0, emotion="greedy", pose="hold", face=.2)
    draw_prop(c, "moneybag", 830, 760, .9, 0.0)
    save(s_, out / "pfp_host_cash.png")


def banner(out):
    w, h = 2560, 1440
    s_ = skia.Surface(w, h); c = s_.getCanvas()
    felt(c, w, h)
    rnd = random.Random(8)
    for _ in range(26):   # scattered coins, mostly outside the text area
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        if 470 < x < 2090 and 480 < y < 960:
            continue
        coin(c, x, y, rnd.uniform(40, 85))
    from engine.props import bills, doc_newspaper
    bills(c, 300, 360, -14); bills(c, 2250, 1080, 12)
    c.save(); c.translate(2280, 420); c.rotate(9); c.scale(.42, .42)
    doc_newspaper(c, {"title": "THE DAILY CON", "text": "TOO GOOD TO BE TRUE"}, 0.0); c.restore()
    card = skia.Path(); card.addRRect(skia.RRect.MakeRectXY(skia.Rect(500, 520, 2060, 920), 40, 40))
    c.drawPath(card, fp("#F6EED4")); c.drawPath(card, ink(LW * 1.4))
    host(c, 690, 700, .95, emotion="smug", pose="tiphat", face=.3, look=CONMAN)
    draw_prop(c, "moneybag", 1900, 730, .5, 0.0)
    coin(c, 1795, 830, 48); coin(c, 1840, 860, 42)
    cx = 1300
    # the marker font's "&" looks like "+", so the ampersand is drawn in Kalam
    parts = [("CONS ", MARKER, 1.0), ("&", KALAM, 1.15), (" COINS", MARKER, 1.0)]
    size = 160
    while sum(text_w(t, size * k, f) for t, f, k in parts) > 860: size *= .95
    x = cx - sum(text_w(t, size * k, f) for t, f, k in parts) / 2
    for t, f, k in parts:
        x += label(c, t, x, 730, size * k, GOLD, font=f, stroke=size * k * .12, skew=0)
    size2 = fit_size(TAGLINE, 54, 820, KALAM); tw2 = text_w(TAGLINE, size2, KALAM)
    label(c, TAGLINE, cx - tw2 / 2, 838, size2, INK, font=KALAM, skew=0)
    save(s_, out / "youtube_banner.png")
    c.drawRect(skia.Rect(507, 508, 2053, 931), ink(6, (255, 60, 60)))   # review copy with the safe area
    save(s_, out / "youtube_banner_safe_area_check.png")


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "out" / "brand")
    out.mkdir(parents=True, exist_ok=True)
    for f in (pfp_conman, pfp_coin, pfp_host_cash, banner):
        f(out)
