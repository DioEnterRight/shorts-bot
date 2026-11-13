"""Visual providers. Swap in config.yaml -> visuals.provider.

Every provider gets the scene list and returns one file path per scene:
a still image (.png/.jpg) or a video clip (.mp4). The editor animates stills
and trims clips, so providers never care about timing.

Special case: 'higgsfield_full' returns a finished video (see higgsfield.py).
"""


def build_prompt(cfg, visual):
    v = cfg["visuals"]
    visual = visual.replace("[GUY]", v["mascot"].strip())
    prompt = f"{v['style_prefix'].strip()}. {visual}. {v['style_suffix'].strip()}"
    return prompt[:2000]


def get_provider(name):
    if name == "cloudflare_klein":
        from . import cloudflare_klein as mod
    elif name == "cloudflare_flux":
        from . import cloudflare_flux as mod
    elif name == "placeholder":
        from . import placeholder as mod
    elif name in ("higgsfield_clips", "higgsfield_full"):
        from . import higgsfield as mod
    else:
        raise ValueError(f"Unknown visuals.provider '{name}' in config.yaml")
    return mod
