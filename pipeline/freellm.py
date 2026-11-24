"""Client for FreeLLMAPI (github.com/tashfeenahmed/freellmapi), started inside the GitHub job by tools/start_freellmapi.sh.
That script sets FREELLM_BASE_URL and FREELLM_API_KEY. Settings live in config.yaml `freellm:`.

Free-tier safety, in layers:
  1. FreeLLMAPI only routes to free-tier endpoints and fails over to the next model when one answers 429/5xx.
  2. Per video: at most `max_calls_per_video` HTTP requests (Budget).
  3. Per month: data/freellm_usage.json counts tokens; past `monthly_token_cap` the bot stops calling (that Short is made in 2D).
     The ledger is needed because the FreeLLMAPI container is new in every run, so its own counters start at zero.
  4. Money: only free keys go in FREELLMAPI_KEYS (see FREELLM_SETUP.md). Nothing here can reach a paid API.

Check the setup without making a video:  python -m pipeline.freellm --check
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from . import common
from .common import log

RETRY = (408, 429, 500, 502, 503, 504)


def settings(cfg):
    f = dict(cfg.get("freellm") or {})
    f["base_url"] = os.environ.get("FREELLM_BASE_URL", "").rstrip("/")
    f["key"] = os.environ.get("FREELLM_API_KEY", "")
    f["models"] = [m for m in (f.get("models") or ["auto:smart"]) if m]
    return f


def configured(cfg):
    f = settings(cfg)
    return bool(f["base_url"] and f["key"])


def ledger_path():
    return common.DATA / "freellm_usage.json"


def month_usage():
    return common.read_json(ledger_path(), {}).get(dt.date.today().strftime("%Y-%m"), {})


def _record(routed, usage):
    data = common.read_json(ledger_path(), {})
    m = data.setdefault(dt.date.today().strftime("%Y-%m"), {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "by_model": {}})
    m["calls"] += 1
    m["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
    m["completion_tokens"] += int(usage.get("completion_tokens") or 0)
    m["by_model"][routed] = m["by_model"].get(routed, 0) + 1
    for old in sorted(data)[:-6]:   # keep six months
        data.pop(old)
    common.write_json(ledger_path(), data)


class Budget:
    """Hard cap on HTTP requests for one video, and the monthly token cap."""
    def __init__(self, cfg):
        f = settings(cfg)
        self.left = int(f.get("max_calls_per_video", 10))
        cap = int(f.get("monthly_token_cap", 30_000_000))
        m = month_usage()
        used = int(m.get("prompt_tokens", 0)) + int(m.get("completion_tokens", 0))
        if used >= cap:
            raise RuntimeError(f"FreeLLMAPI monthly cap reached ({used:,} of {cap:,} tokens); free builder paused until next month")

    def spend(self):
        if self.left <= 0:
            raise RuntimeError("FreeLLMAPI per-video request cap reached (freellm.max_calls_per_video)")
        self.left -= 1


def _post(f, model, messages, json_mode):
    body = {"model": model, "messages": messages, "temperature": float(f.get("temperature", 0.5)),
            "max_tokens": int(f.get("max_tokens", 8000))}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f["base_url"] + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + f["key"]})
    with urllib.request.urlopen(req, timeout=int(f.get("timeout_seconds", 300))) as r:
        return json.loads(r.read()), r.headers.get("X-Routed-Via") or model


def chat(cfg, messages, budget, attempts=3):
    """-> reply text. Tries each model in freellm.models in order; inside one model, retries 408/429/5xx with a pause.
    A 429 'quota_exceeded' (every key of that route used up) moves straight to the next model."""
    f = settings(cfg)
    errors = []
    for model in f["models"]:
        json_mode = True
        i = 0
        while i < attempts:
            budget.spend()
            try:
                data, routed = _post(f, model, messages, json_mode)
                msg = data["choices"][0]["message"]
                text = msg.get("content") or ""
                usage = data.get("usage") or {}
                _record(routed, usage)
                log(f"FreeLLMAPI {model} -> {routed}: in={usage.get('prompt_tokens', '?')} out={usage.get('completion_tokens', '?')}")
                if not text.strip():
                    raise ValueError("empty reply")
                return text
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode("utf-8", "replace")
                if e.code == 400 and json_mode and "response_format" in detail:
                    json_mode = False   # this route has no JSON mode; the prompt still demands JSON
                    continue
                errors.append(f"{model}: HTTP {e.code} {detail[:120]}")
                if e.code in (401, 403):   # the gateway key is wrong: no model will work
                    raise RuntimeError(f"FreeLLMAPI refused the key (HTTP {e.code})") from None
                if e.code not in RETRY or "quota_exceeded" in detail:
                    break
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
                errors.append(f"{model}: {e!r}"[:200])
            i += 1
            log(f"FreeLLMAPI {model} attempt {i}/{attempts} failed ({errors[-1]})", "WARN")
            if i < attempts:
                time.sleep(5 * i * i)
    raise RuntimeError("FreeLLMAPI: every model failed: " + " | ".join(errors[-4:]))


def extract_json(text):
    """The first complete top-level JSON object in a reply, after dropping <think> blocks and ``` fences."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start < 0:
        raise ValueError("reply has no JSON object")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("JSON object in the reply is cut off (raise freellm.max_tokens?)")


def check(cfg):
    """One tiny request: proves the keys work, shows which models are ready and which one answers."""
    f = settings(cfg)
    if not configured(cfg):
        raise SystemExit("FREELLM_BASE_URL / FREELLM_API_KEY are not set: the 'Start FreeLLMAPI' step did not run or "
                         "the FREELLMAPI_KEYS secret is missing. See FREELLM_SETUP.md.")
    req = urllib.request.Request(f["base_url"] + "/models?available=true", headers={"Authorization": "Bearer " + f["key"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        ready = [m.get("id") for m in json.loads(r.read()).get("data", [])]
    log(f"FreeLLMAPI ready models: {len(ready)}" + (f" (e.g. {', '.join(map(str, ready[:12]))})" if ready else ""))
    if not ready:
        raise SystemExit("FreeLLMAPI has no ready model: every key in FREELLMAPI_KEYS was rejected or is used up.")
    reply = chat(cfg, [{"role": "user", "content": 'Reply with exactly this JSON: {"ok": true}'}], Budget(cfg))
    if extract_json(reply).get("ok") is not True:
        raise SystemExit(f"FreeLLMAPI answered, but not with the expected JSON: {reply[:200]}")
    m = month_usage()
    log(f"FreeLLMAPI OK. This month so far: {m.get('calls', 0)} calls, "
        f"{int(m.get('prompt_tokens', 0)) + int(m.get('completion_tokens', 0)):,} tokens")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check(common.load_config())
