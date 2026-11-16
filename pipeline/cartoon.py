"""Cartoon storyboard fields: what the code-drawn explainer shows in each scene.

Claude picks, per scene, a layout, the guy's expression, a background mood and up to 3 props from
a fixed catalog (drawn in remotion/src/bot/cartoon/). Anything unknown is cleaned up here, so a
loose script never breaks a render. Keep these lists in sync with remotion/src/bot/schema.ts.
"""

PROPS = ["brain", "heart", "stomach", "lungs", "bladder", "kidney", "bone", "eye", "tooth", "blood_cell",
         "germ", "cell", "dna", "muscle", "thermometer", "clock", "water_drop", "fire", "snowflake", "ice_cube",
         "lightning", "zzz", "question", "exclamation", "check", "cross", "food", "cup", "phone", "sun", "moon",
         "money", "battery", "wave"]
LAYOUTS = ["actor", "props", "versus", "inside"]
MOTIONS = ["pop", "pulse", "shake", "float", "spin", "grow", "bounce", "drip"]
MOODS = ["fun", "calm", "warm", "cold", "danger", "body", "night"]
EXPRESSIONS = ["neutral", "happy", "shock", "sick", "sleepy", "think", "hot", "cold", "pain"]

ALIASES = {"bacteria": "germ", "virus": "germ", "microbe": "germ", "blood": "blood_cell", "rbc": "blood_cell",
           "water": "water_drop", "drop": "water_drop", "sweat": "water_drop", "urine": "bladder", "pee": "bladder",
           "temperature": "thermometer", "time": "clock", "energy": "battery", "sleep": "zzz", "cold": "snowflake",
           "ice": "ice_cube", "heat": "fire", "hot": "fire", "electric": "lightning", "nerve": "lightning",
           "signal": "lightning", "gut": "stomach", "lung": "lungs", "teeth": "tooth", "burger": "food",
           "coffee": "cup", "drink": "cup", "tea": "cup", "yes": "check", "no": "cross", "cash": "money"}
SHOT_LAYOUT = {"character": "actor", "wide": "actor", "cutaway": "inside", "diagram": "versus",
               "metaphor": "props", "closeup": "props"}


def _prop(x):
    name = str(x.get("name", "") if isinstance(x, dict) else x).strip().lower().replace(" ", "_")
    name = ALIASES.get(name, name)
    if name not in PROPS:
        return None
    motion = x.get("motion") if isinstance(x, dict) else None
    return {"name": name, "motion": motion if motion in MOTIONS else "pop"}


def normalize(sc):
    """Clean the scene's "cartoon" block in place (or derive one from the shot type)."""
    c = sc.get("cartoon") if isinstance(sc.get("cartoon"), dict) else {}
    props = [p for p in (_prop(x) for x in (c.get("props") or [])[:3]) if p]
    layout = c.get("layout") if c.get("layout") in LAYOUTS else SHOT_LAYOUT.get(sc.get("shot"), "props")
    if layout == "versus" and len(props) < 2:
        layout = "props" if props else "actor"
    if layout in ("props", "inside") and not props:
        props = [{"name": "question", "motion": "bounce"}]
    sc["cartoon"] = {
        "layout": layout,
        "expression": c.get("expression") if c.get("expression") in EXPRESSIONS else "neutral",
        "mood": c.get("mood") if c.get("mood") in MOODS else "body",
        "props": props,
    }
    return sc["cartoon"]
