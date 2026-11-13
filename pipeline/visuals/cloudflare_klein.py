"""Free AI pictures with CONSISTENT character + style (Cloudflare Workers AI, FLUX.2 klein 4B).

Why this beats the old mode:
  - Native tall 9:16 pictures (no cropping a square).
  - Every scene gets REFERENCE pictures: our fixed main character (data/mascot.png)
    + the video's first scene as a style anchor -> same guy, same look, same lighting.

Free tier: 10,000 neurons/day. One 864x1536 picture with 2 references is ~170 neurons,
so a 7-scene video is ~1,200 neurons. Plenty of room for the daily video + the spare.
"""
import base64
import io
import time

import requests
from PIL import Image

from ..common import DATA, env, log
from . import build_prompt

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
OUT_W, OUT_H = 864, 1536          # exact 9:16
REF = 496                         # reference pictures must be smaller than 512x512
MASCOT = DATA / "mascot.png"


def _png_bytes(img, size=REF):
    im = img.convert("RGB").copy()
    im.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _call(prompt, account, token, width, height, seed, refs=()):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}"
    form = {"prompt": (None, prompt), "width": (None, str(width)), "height": (None, str(height)),
            "seed": (None, str(seed))}
    for i, data in enumerate(refs[:4]):
        form[f"input_image_{i}"] = (f"ref{i}.png", data, "image/png")
    for attempt in range(1, 5):
        r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, files=form, timeout=180)
        if r.status_code == 200:
            data = r.json()
            res = data.get("result") if isinstance(data.get("result"), dict) else data
            if res.get("image"):
                return Image.open(io.BytesIO(base64.b64decode(res["image"]))).convert("RGB")
            log(f"Cloudflare returned no image: {str(data)[:300]}")
        else:
            log(f"Cloudflare HTTP {r.status_code}: {r.text[:300]}")
            if r.status_code == 429:
                raise RuntimeError("Cloudflare free daily limit reached (resets 05:30 India time).")
            if r.status_code in (401, 403):
                raise RuntimeError("Cloudflare rejected the token. Check CF_ACCOUNT_ID and CF_API_TOKEN.")
            if r.status_code == 400:
                raise RuntimeError(f"Cloudflare refused the request: {r.text[:300]}")
        time.sleep(5 * attempt)
    raise RuntimeError("Cloudflare image generation failed after retries")


def ensure_mascot(cfg, account, token):
    """Create our fixed main character once; it is saved in data/ and reused forever."""
    if MASCOT.exists():
        return Image.open(MASCOT)
    log("Creating the channel's main character (one time only)")
    v = cfg["visuals"]
    prompt = (f"{v['style_prefix'].strip()}. Character reference portrait: {v['mascot'].strip()}, "
              "standing, facing camera, full upper body, neutral friendly expression, plain soft grey "
              f"studio background. {v['style_suffix'].strip()}")
    img = _call(prompt, account, token, 768, 768, 424242)
    DATA.mkdir(exist_ok=True)
    img.save(MASCOT)
    return img


def generate(cfg, script, workdir):
    account = env("CF_ACCOUNT_ID", required=True)
    token = env("CF_API_TOKEN", required=True)
    mascot = _png_bytes(ensure_mascot(cfg, account, token))
    setting = script.get("setting", "").strip()
    base_seed = abs(hash(script["topic"])) % 1_000_000
    anchor = None
    paths = []
    for i, sc in enumerate(script["scenes"]):
        has_guy = "[GUY]" in sc["visual"]
        parts = [build_prompt(cfg, sc["visual"])]
        if setting:
            parts.append(f"Setting for the whole video: {setting}.")
        refs = []
        if has_guy:
            refs.append(mascot)
            parts.append("The man must look EXACTLY like the character in image 0: same face, head, body, "
                         "skin tone and grey t-shirt.")
        if anchor is not None:
            refs.append(anchor)
            parts.append(f"Match the art style, colours and lighting of image {len(refs) - 1}.")
        log(f"Picture {i + 1}/{len(script['scenes'])}")
        img = _call(" ".join(parts)[:2000], account, token, OUT_W, OUT_H, base_seed + i, refs)
        p = workdir / f"scene_{i:02d}.png"
        img.save(p)
        paths.append(p)
        if anchor is None:
            anchor = _png_bytes(img)
    return paths
