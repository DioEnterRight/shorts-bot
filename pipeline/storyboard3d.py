"""Storyboard -> 3D project for the free builder (cartoon3d.builder = freellm).

A free LLM directs each scene in a JSON storyboard (story purpose, visual concept, set, props, hand-built story objects with
text, object animation cued to a narration word, cast with emotion and a reaction beat, shot type, camera move and focus).
This module checks it against what the engine can really draw, then compiles shots (cuts every ~3 s with purposeful coverage,
camera keys, rack focus, follow shots) into web/data.js for kit/engine/gen_main.js + gen_story.js + prefabs.js.
The creative brief the model follows lives in .claude/skills/reel-director/ (loaded into the prompts below).
"""
import json
import math
import re
import shutil
from pathlib import Path

from .common import ROOT

KIT = ROOT / ".claude" / "skills" / "cartoon-audio-short" / "kit"
GROUNDS = ("grass", "street", "wood", "stone", "tile", "sand", "snow", "carpet", "dark", "dirt", "sky")
WALLS = {"none": None, "cream": "#e8dcc2", "blue": "#5b7fb0", "green": "#5f8f6b", "red": "#a3363c", "brown": "#7a5638",
         "dark": "#2c2c38", "grey": "#9a9ca6"}
LIGHT_NAMES = ("day", "golden", "night", "indoor")
EXPRS = ("neutral", "stern", "grin", "laugh", "whistle", "nervous", "shock", "relief", "dazed", "pained", "smile", "smile_closed",
         "stubborn", "squint")
ARMS = ("hang", "point", "up", "wave", "hip", "belly", "temple", "reach", "cheek", "cross", "thumb")
SFX = ("pop", "thud", "whoosh", "tick", "shutter", "scribble", "boom", "ding", "paper", "step", "sting")
SKINS = {"light": "#f5c9a0", "tan": "#d9a073", "brown": "#a8693f", "dark": "#6e4528"}
PACK_SCALE = {"city": 5.0, "furniture": 0.7, "restaurant": 0.7, "dungeon": 0.5}   # scales that fit the 2.25 m cards (API.md)
SLOTS = {"back": (0, -10), "back_left": (-7, -9), "back_right": (7, -9), "left": (-5, -3), "right": (5, -3),
         "mid_left": (-2.2, -3.5), "mid_right": (2.2, -3.5), "near_left": (-1.9, 0.9), "near_right": (1.9, 0.9), "far": (0, -24)}
AUTO_SLOTS = ("back", "mid_left", "mid_right", "back_left", "back_right", "left", "right", "near_left")
LOOKS = {   # one recurring character per name (same name = same head and outfit in every scene)
    "man_blue": {"tunic": "#4f7fb8", "hair": "#5a3b2a"},
    "man_red": {"tunic": "#b8453f", "hair": "#2b211c"},
    "man_green": {"tunic": "#5d8a3a", "hair": "#1e1714", "stout": True},
    "man_suit": {"tunic": "#27324d", "hair": "#2b211c"},
    "boss": {"tunic": "#1f1f26", "hair": "#3b3b44", "stout": True, "brows": "#2b2b33"},
    "old_man": {"tunic": "#8a6d4b", "hair": "#e8e8e8", "beard": "#f0f0f0", "brows": "#f0f0f0"},
    "woman_pink": {"tunic": "#f1ead8", "dress": "#d85c8a", "hair": "#3b2a20"},
    "woman_teal": {"tunic": "#e7f0ee", "dress": "#3f8f8a", "hair": "#1e1714"},
    "woman_suit": {"tunic": "#e9e9ee", "dress": "#2d3350", "hair": "#6a3d24"},
    "worker": {"tunic": "#8a5d3b", "cap": "#c2733a", "apron": "#d8c9a6"},
    "thief": {"tunic": "#22222a", "cap": "#2a2a33", "moustache": "#222222"},
    "clerk": {"tunic": "#3f6a6f", "cap": "#5b4a8a", "moustache": "#4a3020"},
}
LIGHTS = {
    "day": dict(az=140, el=46, sky="#c4d6f2", ground="#8a8262", hemi=1.15, sun="#fff1dc", sunI=2.5, fog="#cadcf0", fogNear=70, fogFar=900,
                skyTop="#3f80d4", skyHor="#c3daf2", sat=1.1, vig=0.2, shadowExt=18, tint="#ffffff"),
    "golden": dict(az=8, el=14, sky="#9a90c8", ground="#6a4c40", hemi=1.0, sun="#ffb46c", sunI=2.9, fog="#f0b88c", fogNear=60, fogFar=760,
                   skyTop="#6f6eb0", skyHor="#ffc27e", sat=1.12, vig=0.26, shadowExt=18, tint="#ffe2c8"),
    "night": dict(az=200, el=35, sky="#6a7aaa", ground="#3a4268", hemi=1.15, sun="#a9bcff", sunI=2.0, fog="#27336a", fogNear=50, fogFar=600,
                  skyTop="#141a48", skyHor="#3a4c8a", sat=1.05, vig=0.28, shadowExt=18, tint="#d4dcff"),
    "indoor": dict(az=120, el=55, sky="#d9cdb8", ground="#8c7a64", hemi=1.25, sun="#ffe2b8", sunI=1.9, fog="#d9cdb8", fogNear=60, fogFar=600,
                   skyTop="#cfc4b0", skyHor="#d9cdb8", sat=1.06, vig=0.24, shadowExt=18, tint="#fff0dc"),
}

DIRECTOR = ROOT / ".claude" / "skills" / "reel-director"
# name: (height_m at size 1, what it is / how to use it). Builders live in kit/engine/prefabs.js.
PREFABS = {
    "cash_stack": (0.25, "banded stack of dollar bills; size 2-3 for a hero shot"),
    "cash_pile": (0.7, "heap of cash stacks"),
    "money_bag": (1.0, "sack with a $ sign"),
    "banknote": (1.8, "giant standing bill; text 'VALUE|SERIAL', e.g. '$20|L 0714 0771 B'"),
    "gold_bars": (0.4, "stacked gold bars"),
    "briefcase": (0.7, "leather briefcase; open: true shows cash inside"),
    "safe": (1.3, "steel safe with dial"),
    "vault_door": (5.0, "round bank vault door (put it on a wall set)"),
    "bank": (9.5, "classical bank facade; text = name on the sign"),
    "jet": (5.0, "1960s airliner with rear stairs; 'fly' in a sky scene, or parked on dirt/street"),
    "parachute": (6.0, "jumper under a canopy; anim 'fall'"),
    "newspaper": (2.0, "front page; text 'HEADLINE|subline'"),
    "document": (1.6, "paper sheet; text 'TITLE|line|line' (FBI file, contract, list)"),
    "sign": (2.5, "board on posts; text up to 3 lines"),
    "label": (3.0, "floating headline card for the ONE number/date/name to remember; text 1-2 lines"),
    "magnifier": (1.6, "magnifying glass"),
    "phone": (1.5, "smartphone; optional text on screen"),
    "laptop": (0.8, "laptop; optional text on screen"),
    "evidence_board": (3.2, "cork board with notes and red string; text 'note|note|note'"),
    "chart": (2.6, "bar chart; trend up|down; anim 'grow'"),
    "arrow": (2.4, "big arrow; trend up|down; color"),
    "question": (2.3, "giant golden question mark"),
    "clock": (2.3, "wall clock on a stand"),
    "pine_tree": (5.0, "pine tree"), "forest": (6.0, "cluster of pines (put at back/far)"),
    "mountain": (16.0, "snowy mountain (put at far)"), "cloud": (3.0, "puffy cloud"), "river": (0.0, "flat river strip"),
}
PREFAB_W = {"cash_stack": 0.66, "cash_pile": 2.2, "money_bag": 0.85, "banknote": 1.9, "gold_bars": 1.2, "briefcase": 0.9, "safe": 1.1,
            "vault_door": 5, "bank": 12, "jet": 23, "parachute": 4.4, "newspaper": 1.5, "document": 1.2, "sign": 3.2, "label": 3.4,
            "magnifier": 1.0, "phone": 0.7, "laptop": 1.1, "evidence_board": 3.8, "chart": 3.2, "arrow": 1.1, "question": 1.2, "clock": 1.4,
            "pine_tree": 3.4, "forest": 14, "mountain": 28, "cloud": 6, "river": 6}
PREFAB_BOX = {"label": (2.6, 0.65), "parachute": (3.0, 3.0), "sign": (1.75, 0.95), "clock": (1.6, 0.8), "question": (1.4, 1.0)}   # (centre y, half height)
INFO = {"label", "sign", "banknote", "newspaper", "document", "evidence_board", "chart"}
TEXT_PREFABS = {"banknote", "bank", "newspaper", "document", "sign", "label", "phone", "laptop", "evidence_board"}
COLORS = {"red": "#c8373a", "green": "#3f9b4b", "blue": "#3d6fb6", "gold": "#f2c14e", "black": "#22222a", "white": "#f4f1ea",
          "yellow": "#f2d64e", "orange": "#e2813a", "purple": "#7b4fb0", "grey": "#8d96a3"}
SHOTS = ("establishing", "wide", "medium", "close", "extreme_close", "over_shoulder", "insert", "low", "high")
MOVES = ("push_in", "pull_out", "orbit", "track", "crane_up", "crane_down", "tilt_up", "rack_focus", "follow", "hold")
ANIMS = ("none", "drop", "pop", "rise", "slide_left", "slide_right", "spin", "float", "shake", "grow", "fly", "fall")
ENTERING = {"drop", "pop", "rise", "slide_left", "slide_right"}
CINF = {"establishing": 2, "wide": 3, "medium": 8, "close": 11, "extreme_close": 13, "over_shoulder": 10, "insert": 12, "low": 8, "high": 3}
MAX_SHOT_FRAMES = 117   # a shot never runs longer than ~3.9 s
MAX_TEXT = 34           # characters per text line on objects


# ---------------------------------------------------------------- catalog
def parse_catalog():
    """kit/models/CATALOG.md -> {name: (w, h, d)} at scale 1."""
    out = {}
    pack = None
    for line in (KIT / "models" / "CATALOG.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"## (\w+)", line)
        if m:
            pack = m.group(1); continue
        if pack and not line.startswith("#"):
            for n, w, h, d in re.findall(r"([\w.\-]+) ([\d.]+)x([\d.]+)x([\d.]+)", line):
                out[f"{pack}/{n}"] = (float(w), float(h), float(d))
    return out


def catalog_text():
    """Compact model list for the prompt: height in metres after the pack's scale is applied."""
    packs = {}
    for name, (_, h, _) in parse_catalog().items():
        pack, n = name.split("/")
        packs.setdefault(pack, []).append(f"{n} {h * PACK_SCALE.get(pack, 1):.1f}")
    return "\n".join(f"{p} (name height_m): " + ", ".join(v) for p, v in packs.items())


# ---------------------------------------------------------------- validation
def _enum(val, allowed, default, what, problems, where):
    v = str(val if val is not None else "").strip().lower().replace(" ", "_").replace("-", "_")
    if v in allowed:
        return v
    if v:
        problems.append(f"{where}: {what} '{val}' is not one of {', '.join(allowed)}")
    return default


def _tokens(text):
    return [re.sub(r"[^\w\u0900-\u097f]", "", w).lower() for w in str(text).split()]


def _has_cue(cue, line):
    c = _tokens(cue)
    return bool(c) and bool(c[0]) and any(w.startswith(c[0]) for w in _tokens(line))


def _text(val, problems, where):
    lines = [t.strip() for t in str(val or "").split("|") if t.strip()][:3]
    for t in lines:
        if len(t) > MAX_TEXT:
            problems.append(f"{where}: text line '{t[:20]}...' is longer than {MAX_TEXT} characters")
    return "|".join(t[:MAX_TEXT] for t in lines)


def _prop(p, j, models, problems, w, line, scene_ground):
    p = p if isinstance(p, dict) else {"model": p}
    name = str(p.get("prefab") or p.get("model") or "").strip()
    bare = name.split("/")[-1] if name.startswith("prefab/") else name
    out = {"at": _enum(p.get("at"), tuple(SLOTS), AUTO_SLOTS[j % len(AUTO_SLOTS)], "slot", problems, w)}
    if bare in PREFABS:
        out["prefab"] = bare
        opts = {}
        if p.get("text"):
            if bare in TEXT_PREFABS:
                opts["text"] = _text(p["text"], problems, w)
            else:
                problems.append(f"{w}: '{bare}' can't show text (text objects: {', '.join(sorted(TEXT_PREFABS))})")
        if p.get("color"):
            c = str(p["color"]).lower()
            if c in COLORS:
                opts["color"] = COLORS[c]
            else:
                problems.append(f"{w}: color '{p['color']}' is not one of {', '.join(COLORS)}")
        if p.get("open"):
            opts["open"] = True
        if p.get("trend") in ("up", "down"):
            opts["trend"] = p["trend"]
        out["opts"] = opts
    elif name in models:
        out["model"] = name
    else:
        problems.append(f"{w}: unknown object '{name}' (use a prefab name or pack/name from the model list)")
        return None
    try:
        out["size"] = min(4.0, max(0.3, float(p.get("size", 1) or 1)))
    except (TypeError, ValueError):
        out["size"] = 1.0
    t = p.get("turn")
    out["turn"] = float(t) if isinstance(t, (int, float)) else None
    out["anim"] = _enum(p.get("anim"), ANIMS, "none", "anim", problems, w)
    if out["anim"] == "fly" and scene_ground != "sky":
        problems.append(f"{w}: anim 'fly' needs ground 'sky'")
        out["anim"] = "none"
    cue = str(p.get("cue") or "").strip()
    if cue and not _has_cue(cue, line):
        problems.append(f"{w}: cue '{cue}' is not a word of this scene's narration")
        cue = ""
    out["cue"] = cue
    out["hero"] = bool(p.get("hero"))
    return out


def normalize(sb, n_scenes, models, lines=None):
    """-> (clean scenes list of length n_scenes, problems). Tolerant: bad values become defaults and are reported so the model can fix them."""
    problems = []
    lines = list(lines or [""] * n_scenes) + [""] * n_scenes
    raw = sb.get("scenes") if isinstance(sb, dict) else None
    if not isinstance(raw, list) or not raw:
        raise ValueError("storyboard has no 'scenes' list")
    if len(raw) != n_scenes:
        problems.append(f"need exactly {n_scenes} scenes (one per narration line, in order), got {len(raw)}")
    roster = {}
    for j, r in enumerate((sb.get("cast") or [])[:4]):
        r = r if isinstance(r, dict) else {}
        name = str(r.get("name", "")).strip().lower() or f"person{j + 1}"
        roster[name] = {"look": _enum(r.get("look"), tuple(LOOKS), tuple(LOOKS)[j % len(LOOKS)], "look", problems, f"cast '{name}'"),
                        "skin": _enum(r.get("skin"), tuple(SKINS), "light", "skin", problems, f"cast '{name}'")}
    looks = [v["look"] for v in roster.values()]
    if len(set(looks)) < len(looks):
        problems.append("two cast members share the same look: give every character a different look")
    clean = []
    for i in range(n_scenes):
        s = raw[min(i, len(raw) - 1)]
        s = s if isinstance(s, dict) else {}
        w, line = f"scene {i + 1}", lines[i]
        ground = _enum(s.get("ground"), GROUNDS, "street", "ground", problems, w)
        props = [q for j, p in enumerate(s.get("props") or []) if (q := _prop(p, j, models, problems, w, line, ground))]
        if len(props) < 2:
            problems.append(f"{w}: add 2-6 objects")
        cast = []
        for j, c in enumerate((s.get("cast") or [])[:3]):
            c = c if isinstance(c, dict) else {"who": c}
            who = str(c.get("who", "")).strip().lower()
            if who in roster:
                base = roster[who]
            else:
                problems.append(f"{w}: cast 'who' must be a name from the top-level cast list ({', '.join(roster) or 'empty'}), got '{c.get('who')}'")
                base = {"look": _enum(c.get("look"), tuple(LOOKS), tuple(LOOKS)[j % len(LOOKS)], "look", [], w), "skin": "light"}
            react = c.get("react") if isinstance(c.get("react"), dict) else None
            if react:
                cue = str(react.get("cue") or "").strip()
                if cue and not _has_cue(cue, line):
                    problems.append(f"{w}: react cue '{cue}' is not a word of this scene's narration")
                    cue = ""
                react = {"expr": _enum(react.get("expr"), EXPRS, "shock", "react expr", problems, w),
                         "arm": _enum(react.get("arm"), ARMS, "up", "react arm", problems, w), "cue": cue}
            cast.append({"who": who, "look": base["look"], "skin": base["skin"],
                         "expr": _enum(c.get("expr"), EXPRS, "neutral", "expr", problems, w),
                         "arm": _enum(c.get("arm"), ARMS, "hang", "arm", problems, w),
                         "at": _enum(c.get("at"), ("left", "center", "right"), "", "at", problems, w),
                         "enter": _enum(c.get("enter"), ("left", "right"), "", "enter", problems, w), "react": react})
        if ground == "sky" and cast:
            problems.append(f"{w}: a 'sky' scene can't have people standing in it; remove the cast or use a ground")
            cast = []
        shot = _enum(s.get("shot") or s.get("camera"), SHOTS, "medium", "shot", problems, w)
        move = _enum(s.get("move"), MOVES, "push_in", "move", problems, w)
        if shot == "over_shoulder" and len(cast) < 2:
            problems.append(f"{w}: over_shoulder needs 2 people in the scene")
            shot = "medium"
        focus = str(s.get("focus") or "").strip().lower()
        if focus and focus not in ("hero",) and not re.fullmatch(r"prop:\d", focus) and focus not in [c["who"] for c in cast]:
            problems.append(f"{w}: focus '{s.get('focus')}' must be a cast name in this scene, 'hero' or 'prop:N'")
            focus = ""
        if move == "follow" and not any(p["anim"] in ("fly", "fall") for p in props):
            problems.append(f"{w}: move 'follow' needs an object with anim 'fly' or 'fall'")
            move = "track"
        clean.append({"purpose": str(s.get("purpose") or "")[:200], "concept": str(s.get("concept") or "")[:300],
                      "ground": ground, "wall": _enum(s.get("wall"), tuple(WALLS), "none", "wall", problems, w),
                      "light": _enum(s.get("light"), LIGHT_NAMES, "day", "light", problems, w),
                      "props": props[:6], "cast": cast, "shot": shot, "move": move, "focus": focus,
                      "sfx": _enum(s.get("sfx"), SFX, "", "sfx", problems, w)})
    for i in range(1, n_scenes):
        a, b = clean[i - 1], clean[i]
        key = lambda sc: ([p.get("model") or p.get("prefab") for p in sc["props"]], sc["ground"], sc["wall"])
        if key(a) == key(b):
            problems.append(f"scene {i + 1} repeats the set of scene {i}: change the objects or ground so the picture moves on")
        if (a["shot"], a["move"]) == (b["shot"], b["move"]):
            problems.append(f"scene {i + 1} uses the same shot and move as scene {i}: choose a different one for its purpose")
    return clean, problems[:16]


def fatal(problems, n_scenes):
    """A scene-count gap bigger than 2 can't be padded or trimmed without mismatching picture and voice."""
    for p in problems:
        m = re.match(r"need exactly (\d+) scenes .* got (\d+)", p)
        if m and abs(int(m.group(1)) - int(m.group(2))) > 2:
            return True
    return False


# ---------------------------------------------------------------- compile
def _cue_frame(cue, words, a, b, fps):
    """Frame where the cue word is spoken (scene start + 6 frames when there is no cue)."""
    c = _tokens(cue)
    if c and c[0]:
        for wd in words:
            if _tokens(wd.get("word", ""))[:1] and _tokens(wd["word"])[0].startswith(c[0]):
                return min(b - 4, max(a, round(float(wd["start"]) * fps) - 2))
    return a + 6


def _prop_offset(f, A):
    """Python twin of propAt() in gen_story.js for the moving anims the camera follows."""
    if not A:
        return (0.0, 0.0)
    u = min(1.0, max(0.0, (f - A["f0"]) / max(1, A["f1"] - A["f0"])))
    if A["type"] == "fly":
        return (-A["dist"] + 2 * A["dist"] * u, u * 2.5)
    if A["type"] == "fall":
        return (0.0, (1 - u * (0.6 + 0.4 * u)) * A["h"])
    return (0.0, 0.0)


def _subjects(props, cast):
    """Targets the camera can frame, as boxes: centre point, half height, half width."""
    people = {c["who"] or f"p{i}": {"pt": [c["x"], 1.12, c["z"]], "hh": 1.15, "hw": 0.7, "kind": "person", "h": 2.25} for i, c in enumerate(cast)}
    things = []
    for i, p in enumerate(props):
        h, w = max(0.3, p["h"]), max(0.3, p["w"])
        cy, hh = PREFAB_BOX.get(p.get("prefab"), (h * 0.5, h * 0.5))
        cy, hh = (cy * p["scale"], hh * p["scale"]) if p.get("prefab") in PREFAB_BOX else (cy, hh)
        things.append({"pt": [p["x"], (p.get("y") or 0) + cy, p["z"]], "hh": hh, "hw": w / 2, "h": h, "kind": "prop", "i": i,
                       "hero": p["hero"], "anim": p.get("anim"), "info": p.get("prefab") in INFO, "big": h > 6 or w > 8})
    return people, things


def _hero(things):
    for t in things:
        if t["hero"]:
            return t
    near = [t for t in things if t["pt"][2] > -6 and not t["big"]]
    return max(near, key=lambda t: t["h"]) if near else None


HEAD = lambda p: {"pt": [p["pt"][0], 1.78, p["pt"][2]], "hh": 0.5, "hw": 0.5, "kind": "head", "h": 1.0}
FACE = lambda p: {"pt": [p["pt"][0], 1.8, p["pt"][2]], "hh": 0.33, "hw": 0.33, "kind": "head", "h": 0.7}
# shot: (vertical fov, elevation deg, azimuth deg, minimum distance)
FRAMING = {"establishing": (50, 20, 14, 12), "wide": (44, 11, 0, 7), "medium": (38, 6, 9, 3.5), "close": (32, 3, 12, 1.8),
           "extreme_close": (26, 2, 6, 1.2), "insert": (30, 20, 22, 1.4), "low": (40, -10, 16, 3.5), "high": (40, 40, 0, 5),
           "over_shoulder": (36, 4, 0, 3)}


def _view_ok(pos, look, vfov, pts, margin=0.9):
    """True when every point projects inside the 9:16 frame (with a safety margin)."""
    f = [look[i] - pos[i] for i in range(3)]; n = math.sqrt(sum(v * v for v in f)) or 1; f = [v / n for v in f]
    r = [f[2], 0.0, -f[0]]; rn = math.hypot(r[0], r[2]) or 1; r = [r[0] / rn, 0.0, r[2] / rn]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    tv = math.tan(math.radians(vfov) / 2) * margin; th = tv * 9 / 16
    for p in pts:
        d = [p[i] - pos[i] for i in range(3)]
        z = sum(d[i] * f[i] for i in range(3))
        if z <= 0.1 or abs(sum(d[i] * u[i] for i in range(3)) / z) > tv or abs(sum(d[i] * r[i] for i in range(3)) / z) > th:
            return False
    return True


def _corners(b):
    x, y, z = b["pt"]; hw, hh = b["hw"], b["hh"]; hd = min(hw, 1.0)
    return [[x + sx * hw, y + sy * hh, z + sz * hd] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def _fit(boxes, shot, flip):
    """Camera that really fits every box corner into the 9:16 frame from the shot's angle -> (pos, look, fov)."""
    vfov, elev, az, dmin = FRAMING[shot]
    x0 = min(b["pt"][0] - b["hw"] for b in boxes); x1 = max(b["pt"][0] + b["hw"] for b in boxes)
    y0 = min(b["pt"][1] - b["hh"] for b in boxes); y1 = max(b["pt"][1] + b["hh"] for b in boxes)
    z0 = min(b["pt"][2] for b in boxes); z1 = max(b["pt"][2] for b in boxes)
    c = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]
    hv = math.tan(math.radians(vfov) / 2); hh_ = hv * 9 / 16
    d = max((x1 - x0) / 2 / hh_, (y1 - y0) / 2 / hv, dmin) * 0.9
    a, e = math.radians(az * flip), math.radians(elev)
    look = [c[0], c[1] + (0.15 * (y1 - y0) if shot == "low" else 0), c[2]]
    pts = [p for b in boxes for p in _corners(b)]
    for _ in range(40):   # pull back until the projection check passes
        pos = [c[0] + d * math.sin(a) * math.cos(e), max(0.35, c[1] + d * math.sin(e)), c[2] + d * math.cos(a) * math.cos(e)]
        if _view_ok(pos, look, vfov, pts):
            break
        d *= 1.08
    return pos, look, vfov


def _fit_dist(boxes, shot):
    pos, look, _ = _fit(boxes, shot, 1)
    return math.dist(pos, look)


def _boxes(shot, tgt, people, hero, things, sa=0, sb=0):
    """Which subjects a shot type has to show. Objects revealed during the shot (cue anims) are always in frame."""
    plist = list(people.values())
    info = [t for t in things if t["info"] and not t["big"] and t["pt"][2] > -6]
    small_hero = hero if hero and not hero["big"] else None
    if tgt["kind"] == "prop" and shot in ("insert", "close", "extreme_close"):
        return [tgt]
    if shot == "insert":
        return [small_hero] if small_hero else [HEAD(tgt)] if tgt["kind"] == "person" else [tgt]
    if shot == "close":
        return [HEAD(tgt)] if tgt["kind"] == "person" else [tgt]
    if shot == "extreme_close":
        return [FACE(tgt)] if tgt["kind"] == "person" else [tgt]
    if shot == "establishing":
        return plist + [t for t in things if t["pt"][2] > -14] or [tgt]
    if shot == "wide":
        props_near = [] if plist else [t for t in things if not t["big"] and t["pt"][2] > -6]   # no people: show the set
        out = [tgt] + plist + ([small_hero] if small_hero else []) + info + props_near
        return [b for k, b in enumerate(out) if all(b is not o for o in out[:k])]
    # medium / low / high: the subject plus the hero object and info cards next to it, but only extras that keep the
    # subject big (the frame may grow to at most 1.7x the subject-only distance)
    reveals = [t for t in things if not t["big"] and t["anim"] and t["anim"]["type"] in ENTERING and sa <= t["anim"]["f0"] <= sb]
    out = [tgt] + [b for b in ([small_hero] if small_hero else []) + reveals if b is not tgt]
    out = [b for k, b in enumerate(out) if all(b is not o for o in out[:k])]
    limit = _fit_dist(out, shot) * 1.35
    for b in sorted((b for b in info if all(b is not o for o in out) and abs(b["pt"][0] - tgt["pt"][0]) < 4.5),
                    key=lambda b: math.dist(b["pt"], tgt["pt"])):
        if _fit_dist(out + [b], shot) <= limit:
            out.append(b)
    return out


def _keys(shot, move, tgt, sa, sb, flip, boxes, anim_of=None, other=None):
    """Camera keys for one shot: fitted framing + a purposeful move."""
    if shot == "over_shoulder" and other is not None:   # behind `other`'s shoulder, looking at tgt's face
        ox, _, oz = other["pt"]; tx, _, tz = tgt["pt"]
        pos = [ox + (ox - tx) * 0.45, 1.9, oz + 3.2]
        look, fov = [tx, 1.7, tz], 34
    elif move == "follow" and anim_of and anim_of["type"] == "fall":   # camera stays, tilts with the falling object
        x, y, z = tgt["pt"]
        pos, fov = [x + 5 * flip, 1.6, z + 16], 46
        keys = []
        for f in list(range(sa, sb, 8)) + [sb]:
            _, dy = _prop_offset(f, anim_of)
            keys.append({"f": f, "pos": pos, "look": [round(x, 3), round(y + dy, 3), round(z, 3)], "fov": fov})
        return keys, "linear"
    else:
        pos, look, fov = _fit(boxes, shot, flip)
    k = lambda f, p, l, fv: {"f": f, "pos": [round(v, 3) for v in p], "look": [round(v, 3) for v in l], "fov": round(fv, 2)}
    toward = lambda p, frac: [p[i] + (look[i] - p[i]) * frac for i in range(3)]
    if move == "push_in":
        return [k(sa, pos, look, fov), k(sb, toward(pos, 0.22), look, fov - 3)], "smooth"
    if move == "pull_out":
        return [k(sa, toward(pos, 0.22), look, fov - 3), k(sb, pos, look, fov)], "smooth"
    if move == "orbit":
        r = math.hypot(pos[0] - look[0], pos[2] - look[2]); a0 = math.atan2(pos[0] - look[0], pos[2] - look[2])
        keys = []
        for n in range(5):
            a = a0 + flip * math.radians(-22 + 44 * n / 4)
            keys.append(k(sa + (sb - sa) * n // 4, [look[0] + r * math.sin(a), pos[1], look[2] + r * math.cos(a)], look, fov))
        return keys, "smooth"
    if move == "track":
        s = 1.6 * flip
        return [k(sa, [pos[0] - s, pos[1], pos[2]], [look[0] - s * 0.6, look[1], look[2]], fov),
                k(sb, [pos[0] + s, pos[1], pos[2]], [look[0] + s * 0.6, look[1], look[2]], fov)], "smooth"
    if move in ("crane_up", "crane_down"):
        lo, hi = [pos[0], max(0.5, pos[1] - 1.2), pos[2]], [pos[0], pos[1] + 2.2, pos[2] + 0.8]
        a, b = (lo, hi) if move == "crane_up" else (hi, lo)
        return [k(sa, a, look, fov), k(sb, b, look, fov)], "smooth"
    if move == "tilt_up":
        top = [look[0], look[1] + max(1.5, tgt["h"] * 0.6), look[2]]
        return [k(sa, pos, [look[0], max(0.2, look[1] - 1.0), look[2]], fov), k(sb, pos, top, fov + 2)], "smooth"
    if move == "follow" and anim_of:
        keys = []
        for f in list(range(sa, sb, 10)) + [sb]:
            dx, dy = _prop_offset(f, anim_of)
            keys.append(k(f, [pos[0] + dx, pos[1] + dy, pos[2]], [look[0] + dx, look[1] + dy, look[2]], fov))
        return keys, "linear"
    # hold / rack_focus: a breath of motion so the frame never freezes
    return [k(sa, pos, look, fov), k(sb, toward(pos, 0.05), look, fov - 0.8)], "smooth"


COVER = {   # what a director cuts to next, by what the scene contains
    "people+hero": ["insert", "close", "wide", "low", "medium"],
    "people": ["close", "wide", "low", "high", "medium"],
    "hero": ["insert", "wide", "low", "medium"],
    "set": ["wide", "low", "high", "medium"],
}
NEXT_MOVES = {"insert": ("push_in", "hold", "orbit"), "close": ("push_in", "hold", "track"), "extreme_close": ("hold", "push_in"),
              "wide": ("track", "pull_out", "crane_up"), "establishing": ("crane_down", "pull_out"), "low": ("tilt_up", "push_in", "orbit"),
              "high": ("pull_out", "crane_down"), "medium": ("orbit", "track", "push_in"), "over_shoulder": ("hold", "push_in")}


def compile_data(scenes, spans, total, fps=30, words=None):
    """Clean scenes + frame spans (+ timeline words per scene for cues) -> the dict written to web/data.js."""
    catalog = parse_catalog()
    words = words or [[] for _ in scenes]
    data_scenes, shots, recent = [], [], []
    for i, (sc, (a, b)) in enumerate(zip(scenes, spans)):
        sky = sc["ground"] == "sky"
        props = []
        for p in sc["props"]:
            x, z = SLOTS[p["at"]]
            y = 0.0
            if sky:
                x, y, z = (0.0, 0.0, 0.0) if p["anim"] == "fly" or p.get("prefab") == "jet" else (x * 1.5, -4.0, z - 6)
            rot = p["turn"] if p["turn"] is not None else (-90 if x > 4 else 90 if x < -4 else 0)
            if p.get("prefab") in ("mountain",) and not sky:
                z = min(z, -60.0); x *= 3   # big scenery lives on the horizon, not over the set
            if p.get("prefab") == "cloud" and not sky:
                y = 9.0
            if p.get("prefab"):
                scale, h, w = p["size"], PREFABS[p["prefab"]][0] * p["size"], PREFAB_W[p["prefab"]] * p["size"]
                if p["prefab"] in ("jet",) and p["turn"] is None:
                    rot = 0 if sky else 25
            else:
                pack = p["model"].split("/")[0]
                scale = PACK_SCALE.get(pack, 1) * p["size"]
                w, h = max(catalog[p["model"]][0], catalog[p["model"]][2]) * scale, catalog[p["model"]][1] * scale
            anim = None
            if p["anim"] != "none":
                f0 = _cue_frame(p["cue"], words[i], a, b, fps) if (p["cue"] or p["anim"] in ENTERING) else a
                anim = {"type": p["anim"], "f0": f0, "f1": b}
                if p["anim"] == "fly":
                    anim.update(f0=a, dist=22.0)
                if p["anim"] == "fall":
                    anim.update(f0=a, h=12.0)
                if p["anim"] == "rise":
                    anim["h"] = max(1.5, h)
            item = {"x": x, "y": y, "z": z, "scale": round(scale, 3), "rotY": round(math.radians(rot), 4), "anim": anim, "h": h, "w": w, "hero": p["hero"]}
            item.update({"prefab": p["prefab"], "opts": p["opts"]} if p.get("prefab") else {"model": p["model"]})
            props.append(item)
        data_scenes.append({"ground": sc["ground"], "wall": WALLS[sc["wall"]],
                            "props": [{k: v for k, v in q.items() if k not in ("h", "w", "hero")} for q in props]})
        layout = _cast_layout(sc["cast"])
        cast = []
        for c, pos in zip(sc["cast"], layout):
            o = dict(LOOKS[c["look"]]); o["skin"] = SKINS[c["skin"]]
            item = {"who": c["who"], "outfit": o, "expr": c["expr"], "L": c["arm"], "R": "hang", "x": pos["x"], "z": pos["z"], "look": 0,
                    "facing": round(-pos["x"] * 0.4, 2), "seed": _hash(c["look"])}
            if c["react"]:
                fr = _cue_frame(c["react"]["cue"], words[i], a, b, fps) if c["react"]["cue"] else a + (b - a) * 11 // 20
                item["react"] = {"f": fr, "expr": c["react"]["expr"], "L": c["react"]["arm"]}
            if c["enter"]:
                item["enter"] = {"f": a, "from": -1 if c["enter"] == "left" else 1}
            cast.append(item)
        people, things = _subjects(props, cast)
        hero = _hero(things)
        movers = [t for t in things if t["anim"] and t["anim"]["type"] in ("fly", "fall")]
        # the director's target for the first shot
        f = sc["focus"]
        if f in people:
            main = people[f]
        elif f.startswith("prop:") and int(f[5:]) < len(things):
            main = things[int(f[5:])]
        elif f == "hero" and hero:
            main = hero
        elif movers:
            main = movers[0]
        elif people:
            main = next(iter(people.values()))
        else:
            main = hero or (things[0] if things else {"pt": [0, 2.5, -6], "hh": 2.5, "hw": 3, "h": 5, "kind": "prop", "anim": None, "big": True})
        small = hero if hero and not hero["big"] else None
        kind = ("people+hero" if people and small else "people") if people else ("hero" if small else "set")
        if sc["shot"] in ("insert", "close", "extreme_close") and main.get("big"):
            sc = dict(sc, shot="wide")   # a jet or a bank can't fill an insert
        n = b - a + 1
        parts = max(1, math.ceil(n / MAX_SHOT_FRAMES))
        edges = [a + round(n * k / parts) for k in range(parts + 1)]
        cover = [c for c in COVER[kind] if c != sc["shot"]]
        cover = cover[i % len(cover):] + cover[:i % len(cover)]   # each scene starts its coverage somewhere else
        plist = list(people.values())
        for j in range(parts):
            sa, sb = edges[j], edges[j + 1] - 1
            flip = 1 if (i + j) % 2 == 0 else -1
            if j == 0:
                shot, move, tgt = sc["shot"], sc["move"], main
            else:
                shot = next((c for c in cover if c not in [r[0] for r in recent[-2:]]), cover[(j - 1) % len(cover)])
                cover.remove(shot); cover.append(shot)
                opts = NEXT_MOVES[shot]
                move = next((m for m in opts[(i + j) % len(opts):] + opts if (shot, m) not in recent[-3:]), opts[0])
                if shot == "insert":
                    tgt = small or main
                elif shot in ("close", "low", "extreme_close") and plist:
                    tgt = plist[(j - 1) % len(plist)]
                else:
                    tgt = main
                if movers:
                    tgt, move = movers[0], "follow"
            if recent and (shot, move) == recent[-1]:   # never the same shot + move twice in a row
                if move == "follow":
                    shot = "close" if shot != "close" else "wide"
                else:
                    opts = NEXT_MOVES[shot]
                    move = next((m for m in opts if m != move), "orbit")
            recent.append((shot, move))
            other = next((p for p in plist if p is not tgt), None) if shot == "over_shoulder" else None
            boxes = _boxes(shot, tgt, people, hero, things, sa, sb)
            keys, ease = _keys(shot, move, tgt, sa, sb, flip, boxes, tgt.get("anim") if move == "follow" else None, other)
            focus = keys[0]["look"]
            shot_d = {"a": sa, "b": sb, "scene": i, "light": sc["light"], "cam": keys, "ease": ease, "focus": focus,
                      "cinf": CINF[shot], "cast": cast, "kind": shot, "move": move}
            if move == "rack_focus":   # pull focus from the nearest other object to the subject
                fg = [t for t in things + plist if t is not tgt]
                if fg:
                    near = min(fg, key=lambda t: math.dist(t["pt"], keys[0]["pos"]))
                    shot_d["focus"], shot_d["focus2"], shot_d["cinf"] = near["pt"], tgt["pt"], max(CINF[shot], 11)
            shots.append(shot_d)
    shots[-1]["b"] = total - 1
    return {"fps": fps, "total": total, "lights": LIGHTS, "scenes": data_scenes, "shots": shots}


def write_project(project, data):
    """Install the compiled storyboard into a set-up cartoon project (web/ is already populated by setup.sh)."""
    web = Path(project) / "web"
    eng = KIT / "engine"
    (web / "main.js").write_text((eng / "gen_main.js").read_text(encoding="utf-8"), encoding="utf-8")
    (web / "story.js").write_text((eng / "gen_story.js").read_text(encoding="utf-8"), encoding="utf-8")
    (web / "prefabs.js").write_text((eng / "prefabs.js").read_text(encoding="utf-8"), encoding="utf-8")
    (web / "fonts").mkdir(exist_ok=True)
    shutil.copy(ROOT / "toon2d" / "fonts" / "Kalam-Bold.ttf", web / "fonts" / "Kalam-Bold.ttf")
    (web / "data.js").write_text("export const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")


def sfx_events(scenes, spans, fps=30):
    return [[round(a / fps, 3), sc["sfx"]] for sc, (a, _) in zip(scenes, spans) if sc["sfx"]]


def scene_words(timeline):
    """Timeline -> list of word lists, one per scene (absolute seconds)."""
    return [list(line.get("words") or []) for line in timeline]


def spans_from_timeline(timeline, frames, fps=30):
    """Frame range of every scene: from its first spoken word to the next scene's first word."""
    starts = [0] + [max(0.0, float(line["words"][0]["start"])) for line in timeline[1:]]
    a = [min(frames - 1, round(s * fps)) for s in starts]
    for i in range(1, len(a)):
        a[i] = max(a[i], a[i - 1] + 6)
    if a[-1] >= frames - 6:
        raise ValueError("storyboard timing: last scene starts too late")
    return [(a[i], (a[i + 1] - 1) if i + 1 < len(a) else frames - 1) for i in range(len(a))]


def _hash(s):
    return 3 + sum(ord(c) * (i + 1) for i, c in enumerate(s)) % 40


def _cast_layout(cast):
    n = len(cast)
    auto = {1: [0.0], 2: [-1.0, 1.0], 3: [-1.5, 0.0, 1.5]}[n] if n else []
    at = {"left": [-1.0, -1.5][n == 3], "center": 0.0, "right": [1.0, 1.5][n == 3]}
    want = [c["at"] for c in cast]
    if n and all(want) and len(set(want)) == n:
        xs = [at[w] for w in want]
    else:
        xs = auto
    return [{"x": x, "z": 0.0 if abs(x) < 0.01 else -0.2} for x in xs]


# ---------------------------------------------------------------- prompts (text from .claude/skills/reel-director)
def _skill(rel):
    return (DIRECTOR / rel).read_text(encoding="utf-8").strip()


EXAMPLE = {
    "story": {"hook": "a teller noticed one tiny detail", "turn": "the same serial number twice", "payoff": "a forger caught by his own copy machine"},
    "plan": ["Hook: the bank at night, a stack of cash pops onto the counter - the mystery object.",
             "The teller spots the detail: rack focus from the giant bill's serial number to her shocked face."],
    "cast": [{"name": "ana", "look": "woman_teal", "skin": "brown"}, {"name": "forger", "look": "thief", "skin": "light"}],
    "scenes": [
        {"purpose": "hook: a bank, a pile of cash, something is wrong", "concept": "night bank facade, cash pops onto a table in front",
         "ground": "stone", "wall": "none", "light": "night",
         "props": [{"prefab": "bank", "at": "back", "text": "FIRST CITY BANK"}, {"prefab": "cash_pile", "at": "mid_right", "size": 1.6, "anim": "pop", "cue": "cash", "hero": True},
                   {"model": "dungeon/table_medium", "at": "mid_right"}, {"model": "city/streetlight", "at": "back_left"}],
         "cast": [], "shot": "establishing", "move": "crane_down", "focus": "hero", "sfx": "pop"},
        {"purpose": "the discovery: two bills, one serial number", "concept": "giant bill with the serial in front, Ana behind it reacting",
         "ground": "tile", "wall": "cream", "light": "indoor",
         "props": [{"prefab": "banknote", "at": "near_left", "text": "$100|KB 4471 0093 A", "hero": True}, {"prefab": "magnifier", "at": "mid_right", "size": 1.2},
                   {"model": "furniture/cabinet_medium", "at": "back"}],
         "cast": [{"who": "ana", "expr": "squint", "arm": "cheek", "at": "right", "react": {"expr": "shock", "arm": "up", "cue": "same"}}],
         "shot": "medium", "move": "rack_focus", "focus": "ana", "sfx": ""}]}


def _schema(n):
    pre = "; ".join(f"{k} {v[0]:g}m: {v[1]}" for k, v in PREFABS.items())
    return f"""Reply with ONE JSON object, no markdown, no comments, in this order:
{{"story": {{"hook": .., "turn": .., "payoff": ..}},
 "plan": [{n} short strings: for each scene, what the viewer must understand and what they see first],
 "cast": [0-4 recurring characters: {{"name": short name, "look": one of {', '.join(LOOKS)}, "skin": one of {', '.join(SKINS)}}}],
 "scenes": [exactly {n} entries, one per narration line, in order]}}
Every scene entry:
  "purpose": the job of this scene in the story;  "concept": the picture in one sentence
  "ground": one of {', '.join(GROUNDS)}   ("sky" = in the air, no people)
  "wall": one of {', '.join(WALLS)}   (a back wall makes it indoors; "none" = outdoors)
  "light": one of {', '.join(LIGHT_NAMES)}
  "props": 2-6 objects, each {{"prefab": name}} OR {{"model": "pack/name"}}, plus
      "at": slot ({', '.join(SLOTS)}), "size": 0.5-3, "turn": degrees, "anim": one of {', '.join(ANIMS)},
      "cue": a word of THIS scene's narration when the object should appear/start, "hero": true for the object that carries the line,
      "text": for text objects, "color": one of {', '.join(COLORS)}, "open": true (briefcase), "trend": up|down (chart, arrow)
  "cast": 0-3 people {{"who": a name from "cast", "expr": one of {', '.join(EXPRS)}, "arm": one of {', '.join(ARMS)},
      "at": left|center|right, "enter": left|right (optional), "react": {{"expr": .., "arm": .., "cue": a word of the line}} (optional)}}
  "shot": one of {', '.join(SHOTS)};  "move": one of {', '.join(MOVES)};  "focus": a cast name, "hero" or "prop:N"
  "sfx": one of {', '.join(SFX)} or "" (at most every third scene)

Hand-built story objects (prefab name, height at size 1, use):
{pre}

Kit models for places (pack (name height_m)):
{catalog_text()}"""


def _scene_list(script, spans, fps):
    return "\n".join(f"{i + 1}. [{(b - a + 1) / fps:.1f} s] \"{sc['line']}\"   (picture idea from the writer: {sc.get('visual', '') or '-'})"
                     for i, (sc, (a, b)) in enumerate(zip(script["scenes"], spans)))


def _header(script, spans, fps):
    return f"""Title: "{script['title']}"   Mood: {script.get('mood', 'mystery')}
Narration, {len(spans)} scenes (one scene per line, timed to the voice):
{_scene_list(script, spans, fps)}"""


def build_messages(script, spans, fps=30):
    n = len(spans)
    user = f"""Direct the pictures for this Short. The engine draws flat inked cartoon people (cut-out cards) in toon-shaded 3D sets with
black outlines, cuts every ~3 s and animates the camera and objects exactly as you specify.

{_header(script, spans, fps)}

{_schema(n)}

Example of 2 scenes from a different story:
{json.dumps(EXAMPLE)}"""
    return [{"role": "system", "content": _skill("creative-direction/director-brief.md")}, {"role": "user", "content": user}]


def review_messages(script, spans, draft, fps=30):
    user = f"""{_skill("quality-control/storyboard-review.md")}

{_header(script, spans, fps)}

Storyboard to review:
{json.dumps(draft, ensure_ascii=False)}

{_schema(len(spans))}"""
    return [{"role": "system", "content": _skill("creative-direction/director-brief.md")}, {"role": "user", "content": user}]


def fix_messages(script, spans, storyboard, weak, fps=30):
    """weak: [{"n": scene number, "issue": .., "fix": ..}] from the visual review."""
    notes = "\n".join(f"- scene {w['n']}: {w.get('issue') or 'weak picture'} -> {w.get('fix') or 'make the line visible'}" for w in weak)
    user = f"""{_skill("quality-control/scene-fix.md")}

Weak scenes:
{notes}

{_header(script, spans, fps)}

Current storyboard:
{json.dumps(storyboard, ensure_ascii=False)}

{_schema(len(spans))}"""
    return [{"role": "system", "content": _skill("creative-direction/director-brief.md")}, {"role": "user", "content": user}]
