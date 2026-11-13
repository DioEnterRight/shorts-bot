"""Shared helpers: config, paths, history file, shell calls."""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
MODELS = ROOT / "models"
HISTORY = DATA / "history.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def log(msg):
    print(f"[{dt.datetime.now(IST):%H:%M:%S}] {msg}", flush=True)


def load_config():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def now_ist():
    return dt.datetime.now(IST)


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
            print(res.stdout[-4000:] if res.stdout else "", res.stderr[-4000:] if res.stderr else "")
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


def load_history():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    return {"videos": []}


def save_history(hist):
    DATA.mkdir(exist_ok=True)
    HISTORY.write_text(json.dumps(hist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def db_to_gain(db):
    return 10 ** (db / 20.0)


def hex_to_ass(rgb_hex):
    """'FFE600' -> '&H0000E6FF' (ASS uses alpha+BGR)."""
    rgb_hex = rgb_hex.lstrip("#")
    r, g, b = rgb_hex[0:2], rgb_hex[2:4], rgb_hex[4:6]
    return f"&H00{b}{g}{r}".upper()
