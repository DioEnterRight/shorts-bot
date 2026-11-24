"""Storyboard -> 3D project. A free LLM only fills in a short JSON storyboard (what each scene shows); this module checks it
against the real model catalog, compiles it into the engine's data file (kit/engine/gen_story.js + gen_main.js read it) and
leaves the shot design (camera moves, cuts every ~3 s, cast layout, lights) to code, so the result is deterministic.

Storyboard shape, one entry per script scene, in order:
  {"scenes": [{"ground": "street", "wall": "none", "light": "day",
               "props": [{"model": "city/building_A", "at": "back", "size": 1.2}],
               "cast":  [{"look": "man_suit", "skin": "tan", "expr": "grin", "arm": "point", "at": "left"}],
               "camera": "medium", "sfx": "pop"}]}
"""
import json
import math
import re
from pathlib import Path

from .common import ROOT

KIT = ROOT / ".claude" / "skills" / "cartoon-audio-short" / "kit"
GROUNDS = ("grass", "street", "wood", "stone", "tile", "sand", "snow", "carpet", "dark", "dirt")
WALLS = {"none": None, "cream": "#e8dcc2", "blue": "#5b7fb0", "green": "#5f8f6b", "red": "#a3363c", "brown": "#7a5638",
         "dark": "#2c2c38", "grey": "#9a9ca6"}
LIGHT_NAMES = ("day", "golden", "night", "indoor")
CAMERAS = ("close", "medium", "wide", "low", "side", "high")
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
CYCLE = ("medium", "close", "wide", "low", "side", "high")
CINF = {"close": 11, "medium": 8, "wide": 3, "low": 8, "side": 8, "high": 3}
MAX_SHOT_FRAMES = 117   # a shot never runs longer than ~3.9 s


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
    v = str(val if val is not None else "").strip().lower().replace(" ", "_")
    if v in allowed:
        return v
    if v:
        problems.append(f"{where}: {what} '{val}' is not one of {', '.join(allowed)}")
    return default


def normalize(sb, n_scenes, models):
    """-> (clean scenes list of length n_scenes, problems). Tolerant: bad values become defaults and are reported so the model can fix them."""
    problems = []
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
        w = f"scene {i + 1}"
        props = []
        for j, p in enumerate(s.get("props") or []):
            p = p if isinstance(p, dict) else {"model": p}
            name = str(p.get("model", "")).strip()
            if name not in models:
                problems.append(f"{w}: unknown model '{name}' (use exact names from the list)"); continue
            at = _enum(p.get("at"), tuple(SLOTS), AUTO_SLOTS[len(props) % len(AUTO_SLOTS)], "slot", problems, w)
            try:
                size = min(3.0, max(0.3, float(p.get("size", 1) or 1)))
            except (TypeError, ValueError):
                size = 1.0
            turn = p.get("turn")
            props.append({"model": name, "at": at, "size": size, "turn": float(turn) if isinstance(turn, (int, float)) else None})
        if len(props) < 2:
            problems.append(f"{w}: add 2-6 props from the model list")
        cast = []
        for j, c in enumerate((s.get("cast") or [])[:3]):
            c = c if isinstance(c, dict) else {"who": c}
            who = str(c.get("who", "")).strip().lower()
            if who in roster:
                base = roster[who]
            else:
                problems.append(f"{w}: cast 'who' must be a name from the top-level cast list ({', '.join(roster) or 'empty'}), got '{c.get('who')}'")
                base = {"look": _enum(c.get("look"), tuple(LOOKS), tuple(LOOKS)[j % len(LOOKS)], "look", [], w), "skin": "light"}
            cast.append({
                "look": base["look"], "skin": base["skin"],
                "expr": _enum(c.get("expr"), EXPRS, "neutral", "expr", problems, w),
                "arm": _enum(c.get("arm"), ARMS, "hang", "arm", problems, w),
                "at": _enum(c.get("at"), ("left", "center", "right"), "", "at", problems, w)})
        clean.append({
            "ground": _enum(s.get("ground"), GROUNDS, "street", "ground", problems, w),
            "wall": _enum(s.get("wall"), tuple(WALLS), "none", "wall", problems, w),
            "light": _enum(s.get("light"), LIGHT_NAMES, "day", "light", problems, w),
            "props": props[:6], "cast": cast,
            "camera": _enum(s.get("camera"), CAMERAS, "medium", "camera", problems, w),
            "sfx": _enum(s.get("sfx"), SFX, "", "sfx", problems, w)})
    for i in range(1, n_scenes):
        a, b = clean[i - 1], clean[i]
        if [p["model"] for p in a["props"]] == [p["model"] for p in b["props"]] and a["ground"] == b["ground"] and a["wall"] == b["wall"]:
            problems.append(f"scene {i + 1} repeats the set of scene {i}: change the props or ground so the background changes")
    return clean, problems[:14]


def fatal(problems, n_scenes):
    """A scene-count gap bigger than 2 can't be padded or trimmed without mismatching picture and voice."""
    for p in problems:
        m = re.match(r"need exactly (\d+) scenes .* got (\d+)", p)
        if m and abs(int(m.group(1)) - int(m.group(2))) > 2:
            return True
    return False


# ---------------------------------------------------------------- compile
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


def _cam(preset, F, flip, has_cast, pull):
    fx, fz = F
    if has_cast:
        P = {"close": ((fx + 0.25, 1.75, fz + 3.4), (fx, 1.55, fz), 32),
             "medium": ((fx, 1.5, fz + 6.8), (fx, 1.3, fz), 38),
             "wide": ((fx, 3.4, fz + 13.5), (fx, 1.6, fz - 3), 46),
             "low": ((fx + 1.8, 0.6, fz + 5.2), (fx, 1.7, fz), 40),
             "side": ((fx + 5.0 * flip, 1.5, fz + 4.2), (fx, 1.4, fz), 36),
             "high": ((fx, 5.0, fz + 8.5), (fx, 0.9, fz), 40)}[preset]
    else:   # no people: show the set
        P = {"close": ((0, 2.2, 6), (0, 2.5, -8), 40), "medium": ((0, 3, 9), (0, 3, -9), 46), "wide": ((0, 4, 14), (0, 3, -10), 52),
             "low": ((3, 0.8, 8), (0, 3.5, -8), 48), "side": ((6 * flip, 2.5, 9), (0, 3, -8), 46), "high": ((0, 7, 12), (0, 2, -8), 50)}[preset]
    pos, look, fov = list(P[0]), list(P[1]), P[2]
    k = 0.06 * (-1 if pull else 1)   # slow push in, or pull out on alternate shots
    end = [pos[i] - (pos[i] - look[i]) * k for i in range(3)]
    return ([{"f": 0, "pos": pos, "look": look, "fov": fov}, {"f": 1, "pos": end, "look": look, "fov": fov - (1.5 if not pull else -1.5)}], look)


def compile_data(scenes, spans, total, fps=30):
    """Clean scenes + frame spans -> the dict written to web/data.js."""
    data_scenes, shots, prev = [], [], None
    for i, (sc, (a, b)) in enumerate(zip(scenes, spans)):
        props = []
        for p in sc["props"]:
            x, z = SLOTS[p["at"]]
            pack = p["model"].split("/")[0]
            rot = p["turn"] if p["turn"] is not None else (-90 if x > 4 else 90 if x < -4 else 0)   # side props face the middle
            props.append({"model": p["model"], "x": x, "z": z, "scale": PACK_SCALE.get(pack, 1) * p["size"], "rotY": math.radians(rot)})
        data_scenes.append({"ground": sc["ground"], "wall": WALLS[sc["wall"]], "props": props})
        layout = _cast_layout(sc["cast"])
        cast = []
        for c, pos in zip(sc["cast"], layout):
            o = dict(LOOKS[c["look"]]); o["skin"] = SKINS[c["skin"]]
            cast.append({"outfit": o, "expr": c["expr"], "L": c["arm"], "R": "hang", "x": pos["x"], "z": pos["z"], "look": 0,
                         "facing": round(-pos["x"] * 0.4, 2), "seed": _hash(c["look"])})
        n = b - a + 1
        parts = max(1, math.ceil(n / MAX_SHOT_FRAMES))
        edges = [a + round(n * k / parts) for k in range(parts + 1)]
        cyc = [sc["camera"]] + [c for c in CYCLE if c != sc["camera"]]
        for j in range(parts):
            preset = cyc[j % len(cyc)]
            if preset == prev:
                preset = cyc[(j + 1) % len(cyc)]
            prev = preset
            who = cast[j % len(cast)] if cast else None
            keys, focus = _cam(preset, (who["x"], who["z"]) if who else (0, 0), 1 if (i + j) % 2 == 0 else -1, bool(who), pull=(j % 2 == 1))
            sa, sb = edges[j], edges[j + 1] - 1
            keys[0]["f"], keys[1]["f"] = sa, sb
            shots.append({"a": sa, "b": sb, "scene": i, "light": sc["light"], "cam": keys, "focus": focus, "cinf": CINF[preset] if who else 3, "cast": cast})
    shots[-1]["b"] = total - 1
    return {"fps": fps, "total": total, "lights": LIGHTS, "scenes": data_scenes, "shots": shots}


def write_project(project, data):
    """Install the compiled storyboard into a set-up cartoon project (web/ is already populated by setup.sh)."""
    web = Path(project) / "web"
    (web / "main.js").write_text((KIT / "engine" / "gen_main.js").read_text(encoding="utf-8"), encoding="utf-8")
    (web / "story.js").write_text((KIT / "engine" / "gen_story.js").read_text(encoding="utf-8"), encoding="utf-8")
    (web / "data.js").write_text("export const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")


def sfx_events(scenes, spans, fps=30):
    return [[round(a / fps, 3), sc["sfx"]] for sc, (a, _) in zip(scenes, spans) if sc["sfx"]]


# ---------------------------------------------------------------- prompts
SYSTEM = ("You are the art director of a hit faceless YouTube Shorts channel about money, scams and heists. "
          "Every 3-4 seconds the picture must show exactly what the narrator is saying, so a viewer with the sound off "
          "still follows the story. You think visually, you are concrete, and you follow the output format exactly.")

EXAMPLE = {
    "plan": ["Hook: a baker is rich from bread alone - show him proud in his shop full of bread and money.",
             "His rival spies from across the street - outside, night, rival hiding by a car, shop lit across the road."],
    "cast": [{"name": "baker", "look": "worker", "skin": "tan"}, {"name": "rival", "look": "thief", "skin": "light"}],
    "scenes": [
        {"ground": "tile", "wall": "cream", "light": "indoor",
         "props": [{"model": "restaurant/crate_buns", "at": "mid_left", "size": 1.4}, {"model": "dungeon/chest_gold", "at": "mid_right", "size": 1.6},
                   {"model": "furniture/shelf_B_large_decorated", "at": "back"}, {"model": "furniture/pictureframe_large_A", "at": "back_left"}],
         "cast": [{"who": "baker", "expr": "grin", "arm": "thumb", "at": "center"}], "camera": "medium", "sfx": "ding"},
        {"ground": "street", "wall": "none", "light": "night",
         "props": [{"model": "city/building_C", "at": "back"}, {"model": "city/car_sedan", "at": "near_left", "turn": 30},
                   {"model": "city/streetlight", "at": "mid_right"}],
         "cast": [{"who": "rival", "expr": "squint", "arm": "cheek", "at": "right"}], "camera": "low", "sfx": ""}]}


def _schema(n):
    return f"""Reply with ONE JSON object, no markdown, no comments, in this order:
{{"plan": [{n} short strings: for each scene, what the viewer must understand and how the set shows it],
 "cast": [0-4 recurring characters: {{"name": short name, "look": one of {', '.join(LOOKS)}, "skin": one of {', '.join(SKINS)}}}],
 "scenes": [exactly {n} entries, one per narration line, in order]}}
Every scene entry:
  "ground": one of {', '.join(GROUNDS)}
  "wall": one of {', '.join(WALLS)}   (a back wall makes it indoors; "none" = outdoors with sky)
  "light": one of {', '.join(LIGHT_NAMES)}
  "props": 2-6 objects {{"model": "pack/name", "at": slot, "size": 0.5-3 (optional), "turn": degrees (optional)}}
      slots: {', '.join(SLOTS)}. back/far = background; mid_* stand right beside the people and are seen in most shots;
      near_* are in the foreground. Put the 1-2 props that tell the story in mid_left / mid_right.
  "cast": 0-3 people in this scene {{"who": a name from "cast", "expr": one of {', '.join(EXPRS)}, "arm": one of {', '.join(ARMS)},
      "at": left|center|right}}
  "camera": one of {', '.join(CAMERAS)}   (close = face and emotion, wide = place, low = power, high = small/defeated)
  "sfx": one of {', '.join(SFX)} or "" (a sound at the start of the scene, at most every third scene)"""


RULES = """Rules for a great Short:
- Literal and clear beats clever: if the line says money, show coins, chests or a gold chest; a bank or city = buildings; a deal = two people facing each other; food scam = food props.
- The emotion of each line goes in "expr" and "arm" (shock + up when something goes wrong, grin + thumb when someone wins, nervous + temple when someone panics).
- Change the set every scene (different ground, wall or story props). Return to an earlier place only when the story does.
- Keep the same characters through the story; extras are fine. Props are already scaled to stand next to 2.25 m people;
  use "size" 1.5-3 only for small story objects (coins, keys, food) so they read on a phone screen.
- Use only model names from the list below, exactly as written, with the pack: pack/name."""


def _scene_list(script, spans, fps):
    return "\n".join(f"{i + 1}. [{(b - a + 1) / fps:.1f} s] \"{sc['line']}\"   (picture idea: {sc.get('visual', '') or '-'})"
                     for i, (sc, (a, b)) in enumerate(zip(script["scenes"], spans)))


def build_messages(script, spans, fps=30):
    n = len(spans)
    user = f"""Plan the pictures for this Short. A fixed 3D engine draws it: flat inked cartoon people (cut-out cards) standing in
painted low-poly 3D sets. You choose the set, the props, the people and their emotion for each scene; the engine adds
camera moves and cuts every ~3 seconds.

Title: "{script['title']}"   Mood: {script.get('mood', 'mystery')}
Narration, {n} scenes:
{_scene_list(script, spans, fps)}

{_schema(n)}

{RULES}

Models (pack (name height_m)):
{catalog_text()}

Example for a different story (2 scenes):
{json.dumps(EXAMPLE)}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def review_messages(script, spans, draft, fps=30):
    """Second pass: a strict review that returns an improved storyboard."""
    n = len(spans)
    user = f"""Review this storyboard for the Short "{script['title']}" like a strict art director, then return the improved version.

Narration:
{_scene_list(script, spans, fps)}

Storyboard to review:
{json.dumps(draft, ensure_ascii=False)}

Check every scene: (1) would a viewer with the sound off understand the line from the props and the people?
(2) is the key story object in mid_left/mid_right and big enough? (3) does the emotion match the line?
(4) does the set change from the scene before? (5) are characters consistent? (6) does the light fit the moment?
Fix every weak scene. Keep what already works.

{_schema(n)}

{RULES}

Models (pack (name height_m)):
{catalog_text()}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
