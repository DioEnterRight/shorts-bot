"""Visual providers. Swap in config.yaml -> visuals.provider.

Every provider gets the script and returns one file path per scene: a still image
(.png/.jpg) or a video clip (.mp4). The editor animates stills, adds transitions and
trims clips, so providers never care about timing.

Special case: 'higgsfield_full' returns a finished video (see higgsfield.py).
"""
import hashlib

from ..common import DATA


class FatalProviderError(RuntimeError):
    """Retrying or falling back cannot help (bad token, daily quota used up)."""


def look(cfg, script):
    """Art style + mascot for this video (a theme may override both)."""
    v = cfg["visuals"]
    theme = (cfg.get("themes") or {}).get(script.get("theme", "explainer")) or {}
    return (theme.get("art_style") or v["art_style"]).strip(), (theme.get("mascot") or v["mascot"]).strip()


def mascot_path(cfg, script):
    """One reference picture per (art style, mascot) pair, so a new look gets a new character sheet."""
    style, mascot = look(cfg, script)
    key = hashlib.sha256(f"{style}|{mascot}".encode()).hexdigest()[:10]
    return DATA / "characters" / f"mascot-{key}.png"


def build_prompt(cfg, script, scene):
    v = cfg["visuals"]
    style, mascot = look(cfg, script)
    shot_style = (v.get("shots") or {}).get(scene.get("shot", ""), "")
    visual = scene["visual"].replace("[GUY]", mascot)
    parts = [f"{style}.", f"{shot_style}." if shot_style else "", f"Scene: {visual}."]
    if scene.get("background"):
        parts.append(f"Setting: {scene['background']}.")
    parts.append(f"{v['composition'].strip()}. {v['avoid'].strip()}.")
    return " ".join(p for p in parts if p)[:2000]


def character_sheet_prompt(cfg, script):
    v = cfg["visuals"]
    style, mascot = look(cfg, script)
    return (f"{style}. Character reference sheet: {mascot}, standing, facing camera, full body, "
            f"neutral friendly expression, plain soft grey studio background. {v['avoid'].strip()}.")


def get_provider(name):
    if name == "cloudflare_klein":
        from . import cloudflare_klein as mod
    elif name == "cloudflare_flux":
        from . import cloudflare_flux as mod
    elif name == "higgsfield_test":
        from . import higgsfield_test as mod
    elif name == "placeholder":
        from . import placeholder as mod
    elif name in ("higgsfield_clips", "higgsfield_full"):
        from . import higgsfield as mod
    else:
        raise ValueError(f"Unknown visuals.provider '{name}' in config.yaml")
    return mod
