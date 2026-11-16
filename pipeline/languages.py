"""Language profiles (config.yaml -> languages). One video = one language."""
import re

from .common import ROOT

LATIN = re.compile(r"[A-Za-z]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def profile(cfg, code):
    langs = cfg["languages"]
    if code not in langs.get("enabled", []) or code not in langs:
        raise ValueError(f"Language '{code}' is not enabled in config.yaml -> languages")
    p = dict(langs[code])
    p["code"] = code
    return p


def enabled(cfg):
    return list(cfg["languages"]["enabled"])


def prompt_text(p):
    return (ROOT / p["prompt"]).read_text(encoding="utf-8")


def is_latin_word(word):
    return bool(LATIN.search(word)) and not DEVANAGARI.search(word)


def script_ok(text, code):
    """Light sanity check that a Hindi script really is mostly Devanagari (and English is not)."""
    words = [w for w in text.split() if LATIN.search(w) or DEVANAGARI.search(w)]
    if not words:
        return False
    deva = sum(1 for w in words if DEVANAGARI.search(w)) / len(words)
    return deva >= 0.5 if code == "hi" else deva < 0.05
