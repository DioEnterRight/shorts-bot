"""Free AI pictures with a CONSISTENT character (Cloudflare Workers AI, FLUX.2 klein 4B).

  - Native tall 9:16 pictures.
  - Character scenes get our fixed character sheet (data/characters/mascot-*.png) as a reference,
    plus the video's first character picture, so the character looks the same all video.
  - Non-character scenes (cutaways, diagrams, metaphors) get NO picture references: they share the
    written art style, but each beat is free to show a genuinely different place and subject.
  - Every picture is cached by prompt+references+seed, so a retry inside a run never pays twice.
  - A failed scene falls back to FLUX.1 schnell; if that fails too, a neighbouring picture is
    reused (only if at least visuals.min_scenes_ok of the scenes worked).

Free tier: 10,000 neurons/day. A 864x1536 picture with references costs roughly 150-200
neurons [estimate, check your Cloudflare dashboard], so ~10 beats is ~2,000 per video.
"""
import base64
import hashlib
import io
import time

import requests
from PIL import Image

from ..common import OUT, env, log, stable_seed
from . import FatalProviderError, build_prompt, character_sheet_prompt, mascot_path

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
OUT_W, OUT_H = 864, 1536          # exact 9:16
REF = 496                         # reference pictures must be smaller than 512x512
CACHE = OUT / "_cache"


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
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, files=form, timeout=180)
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


def cached_call(prompt, account, token, width, height, seed, refs=()):
    key = hashlib.sha256(b"|".join([MODEL.encode(), prompt.encode(), str((width, height, seed)).encode(),
                                    *[hashlib.sha256(r).digest() for r in refs]])).hexdigest()[:24]
    path = CACHE / f"{key}.png"
    if path.exists():
        log("  (cached)")
        return Image.open(path).convert("RGB")
    img = _call(prompt, account, token, width, height, seed, refs)
    CACHE.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return img


def ensure_mascot(cfg, script, account, token):
    """Create the character sheet once per art style; it is saved in data/ and reused forever."""
    path = mascot_path(cfg, script)
    if path.exists():
        return Image.open(path)
    log("Creating the character reference sheet (one time per art style)")
    img = _call(character_sheet_prompt(cfg, script), account, token, 768, 768, 424242)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return img


def fill_gaps(paths, min_ok):
    """Replace failed scenes (None) with the nearest successful picture."""
    ok = [i for i, p in enumerate(paths) if p is not None]
    if len(ok) / len(paths) < min_ok:
        raise RuntimeError(f"Only {len(ok)}/{len(paths)} pictures worked — not making a half-empty video")
    for i, p in enumerate(paths):
        if p is None:
            j = min(ok, key=lambda k: (abs(k - i), k))
            log(f"Scene {i + 1}: re-using picture {j + 1}", "WARN")
            paths[i] = paths[j]
    return paths


def generate(cfg, script, workdir):
    from . import cloudflare_flux
    account = env("CF_ACCOUNT_ID", required=True)
    token = env("CF_API_TOKEN", required=True)
    mascot = _png_bytes(ensure_mascot(cfg, script, account, token))
    anchor = None
    paths = []
    n = len(script["scenes"])
    for i, sc in enumerate(script["scenes"]):
        prompt = build_prompt(cfg, script, sc)
        refs = []
        if sc.get("character"):
            refs.append(mascot)
            prompt += " The character must look EXACTLY like the character in image 0: same face, hair and outfit."
            if anchor is not None:
                refs.append(anchor)
                prompt += " Keep the same character design, colours and lighting as image 1."
        seed = stable_seed(script["topic"], i)
        log(f"Picture {i + 1}/{n} [{sc.get('shot')}]")
        p = workdir / f"scene_{i:02d}.png"
        try:
            img = cached_call(prompt[:2000], account, token, OUT_W, OUT_H, seed, refs)
        except FatalProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            log(f"Scene {i + 1} failed on klein ({str(e)[:150]}); trying FLUX schnell", "WARN")
            try:
                img = cloudflare_flux.image(build_prompt(cfg, script, sc), account, token, seed,
                                            cfg["visuals"].get("flux_steps", 8))
            except FatalProviderError:
                raise
            except Exception as e2:  # noqa: BLE001
                log(f"Scene {i + 1} failed on FLUX too: {str(e2)[:150]}", "WARN")
                paths.append(None)
                continue
        img.save(p)
        paths.append(p)
        if sc.get("character") and anchor is None:
            anchor = _png_bytes(img)
    return fill_gaps(paths, float(cfg["visuals"].get("min_scenes_ok", 0.75)))
