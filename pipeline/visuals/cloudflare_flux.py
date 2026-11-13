"""Free AI pictures from Cloudflare Workers AI (FLUX.1 schnell).

Free tier: 10,000 'neurons' per day, resets 00:00 UTC, no card needed.
One 1024x1024 picture at 8 steps is about 96 neurons -> ~100 pictures/day free.
We use ~8 per video.
"""
import base64
import io
import time

import requests
from PIL import Image

from ..common import env, log
from . import build_prompt

MODEL = "@cf/black-forest-labs/flux-1-schnell"


def _one(prompt, steps, account, token, seed):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}"
    body = {"prompt": prompt, "steps": int(steps), "seed": int(seed)}
    for attempt in range(1, 5):
        r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=body, timeout=180)
        if r.status_code == 200:
            data = r.json()
            res = data.get("result") if isinstance(data.get("result"), dict) else data
            img_b64 = res.get("image")
            if img_b64:
                return Image.open(io.BytesIO(base64.b64decode(img_b64))).convert("RGB")
            log(f"Cloudflare returned no image: {str(data)[:300]}")
        else:
            log(f"Cloudflare HTTP {r.status_code}: {r.text[:300]}")
            if r.status_code == 429:
                raise RuntimeError("Cloudflare free daily limit reached (resets 00:00 UTC). Try again tomorrow.")
            if r.status_code in (401, 403):
                raise RuntimeError("Cloudflare rejected the token. Check CF_ACCOUNT_ID and CF_API_TOKEN secrets.")
        time.sleep(5 * attempt)
    raise RuntimeError("Cloudflare image generation failed after retries")


def generate(cfg, script, workdir):
    account = env("CF_ACCOUNT_ID", required=True)
    token = env("CF_API_TOKEN", required=True)
    steps = cfg["visuals"].get("flux_steps", 8)
    paths = []
    base_seed = abs(hash(script["topic"])) % 1_000_000
    for i, sc in enumerate(script["scenes"]):
        prompt = build_prompt(cfg, sc["visual"])
        log(f"Picture {i + 1}/{len(script['scenes'])}")
        img = _one(prompt, steps, account, token, base_seed + i)
        p = workdir / f"scene_{i:02d}.png"
        img.save(p)
        paths.append(p)
    return paths
