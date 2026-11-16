"""Free AI pictures from Cloudflare Workers AI (FLUX.1 schnell). Also the per-scene fallback of klein.

Free tier: 10,000 'neurons' per day, resets 00:00 UTC, no card needed.
One picture at 8 steps is roughly 100 neurons [estimate].
"""
import base64
import io
import time

import requests
from PIL import Image

from ..common import env, log, stable_seed
from . import FatalProviderError, build_prompt

MODEL = "@cf/black-forest-labs/flux-1-schnell"


def image(prompt, account, token, seed, steps=8):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}"
    body = {"prompt": prompt[:2000], "steps": int(steps)}  # schema has no seed field we rely on
    for attempt in range(1, 5):
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=body, timeout=180)
        except requests.RequestException as e:
            log(f"Cloudflare network error: {e}", "WARN")
            time.sleep(5 * attempt)
            continue
        if r.status_code == 200:
            data = r.json()
            res = data.get("result") if isinstance(data.get("result"), dict) else data
            if res.get("image"):
                return Image.open(io.BytesIO(base64.b64decode(res["image"]))).convert("RGB")
            log(f"Cloudflare returned no image: {str(data)[:300]}", "WARN")
        else:
            log(f"Cloudflare HTTP {r.status_code}: {r.text[:300]}", "WARN")
            if r.status_code == 429:
                raise FatalProviderError("Cloudflare free daily limit reached (resets 05:30 India time).")
            if r.status_code in (401, 403):
                raise FatalProviderError("Cloudflare rejected the token. Check CF_ACCOUNT_ID and CF_API_TOKEN.")
            if r.status_code == 400:
                raise RuntimeError(f"Cloudflare refused this picture: {r.text[:300]}")
        time.sleep(5 * attempt)
    raise RuntimeError("Cloudflare image generation failed after retries")


def generate(cfg, script, workdir):
    account = env("CF_ACCOUNT_ID", required=True)
    token = env("CF_API_TOKEN", required=True)
    steps = cfg["visuals"].get("flux_steps", 8)
    paths = []
    for i, sc in enumerate(script["scenes"]):
        log(f"Picture {i + 1}/{len(script['scenes'])}")
        img = image(build_prompt(cfg, script, sc), account, token, stable_seed(script["topic"], i), steps)
        p = workdir / f"scene_{i:02d}.png"
        img.save(p)
        paths.append(p)
    return paths
