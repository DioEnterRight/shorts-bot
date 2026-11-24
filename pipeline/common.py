"""Shared helpers: config, paths, state files, shell calls."""
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
MODELS = ROOT / "models"
HISTORY = DATA / "history.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HISTORY_VERSION = 2

SECRET_ENV = ("CLAUDE_CODE_OAUTH_TOKEN", "FREELLM_API_KEY", "FREELLMAPI_KEYS", "CF_API_TOKEN", "IG_PAGE_TOKEN", "YT_CLIENT_SECRET",
              "YT_REFRESH_TOKEN", "GH_TOKEN")


def redact(text):
    """Never let a secret reach the log."""
    text = str(text)
    for name in SECRET_ENV:
        val = os.environ.get(name, "").strip()
        if len(val) >= 8:
            text = text.replace(val, "***")
    return text


def log(msg, level="INFO"):
    print(f"[{dt.datetime.now(IST):%H:%M:%S}] {level:<5} {redact(msg)}", flush=True)


def load_config():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def now_ist():
    return dt.datetime.now(IST)


def parse_time(s):
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=IST)


def env(name, required=False):
    val = os.environ.get(name, "").strip()
    if required and not val:
        sys.exit(f"Missing secret/env var: {name}. Add it in GitHub > Settings > Secrets and variables > Actions.")
    return val


def run(cmd, check=True, capture=False, **kw):
    """Run a command. Prints it (minus long args) for the log."""
    short = " ".join(str(c) if len(str(c)) < 120 else str(c)[:60] + "..." for c in cmd)
    log(f"$ {short}")
    res = subprocess.run([str(c) for c in cmd], check=False, text=True,
                         capture_output=capture, **kw)
    if check and res.returncode != 0:
        if capture:
            print(redact(res.stdout[-4000:] if res.stdout else ""), redact(res.stderr[-4000:] if res.stderr else ""))
        raise RuntimeError(f"Command failed ({res.returncode}): {short}")
    return res


def ffprobe(path):
    res = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", path], capture=True)
    return json.loads(res.stdout)


def duration_of(path):
    return float(ffprobe(path)["format"]["duration"])


def slugify(text, n=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].strip("-") or "video"


def is_wordchar(ch):
    """Letters, digits AND combining marks (Devanagari matras are marks; regex \\w drops them)."""
    import unicodedata
    return unicodedata.category(ch)[0] in "LMN"


def norm_text(s):
    return "".join(ch for ch in s.lower() if is_wordchar(ch))


def stable_seed(*parts, mod=1_000_000):
    """Deterministic seed (Python's hash() changes every process)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16) % mod


# ---------------- state files (atomic) ----------------
def read_json(path, default):
    path = pathlib.Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, obj):
    """Write via temp file + rename so a crash never leaves a half-written state file."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def migrate_history(hist):
    """v1 -> v2: explicit per-platform states + language/theme fields."""
    if hist.get("version", 1) >= HISTORY_VERSION:
        return hist
    for v in hist.get("videos", []):
        v.setdefault("language", "en")
        v.setdefault("theme", "explainer")
        if v.get("ig_media_id"):
            v.setdefault("ig_state", "posted")
        if v.get("yt_done") and "yt_state" not in v:
            # v1 set yt_done=True both after a real upload and after a manual-upload notice
            v["yt_state"] = "posted" if v.get("yt_video_id") else "manual_notified"
        v.pop("yt_done", None)
    hist["version"] = HISTORY_VERSION
    return hist


def load_history():
    return migrate_history(read_json(HISTORY, {"version": HISTORY_VERSION, "videos": []}))


def save_history(hist):
    hist["version"] = HISTORY_VERSION
    write_json(HISTORY, hist)


def db_to_gain(db):
    return 10 ** (db / 20.0)


def hex_to_ass(rgb_hex):
    """'FFE600' -> '&H0000E6FF' (ASS uses alpha+BGR)."""
    rgb_hex = rgb_hex.lstrip("#")
    r, g, b = rgb_hex[0:2], rgb_hex[2:4], rgb_hex[4:6]
    return f"&H00{b}{g}{r}".upper()
