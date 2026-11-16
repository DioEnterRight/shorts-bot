"""Voiceover with Kokoro (free, open source, runs on the GitHub runner CPU).

Each scene line is spoken separately, so we know exactly when every line starts.
Word times inside a line are estimated from word length (good enough for 1-2 word captions).

Hindi/Hinglish: espeak-ng phonemizes Devanagari with Hindi rules and English words (written in
Latin letters) with English rules, but marks every switch with "(en)"/"(hi)". Kokoro would
read those markers as sounds, so we phonemize ourselves, drop the markers and pass phonemes.
"""
import re

import numpy as np
import soundfile as sf

from .common import MODELS, is_wordchar, log

SR = 24000
LANG_SWITCH = re.compile(r"\([a-z]{2}(?:-[a-z]{2})?\)")


def _trim(x, thresh=0.01, pad=0.03):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(pad * SR))
    b = min(len(x), idx[-1] + int(pad * SR))
    return x[a:b]


def _word_weights(words):
    w = []
    for word in words:
        core = "".join(ch for ch in word if is_wordchar(ch))
        weight = 1.2 + len(core) * 0.55
        if re.search(r"[,;:]$", word):
            weight += 2.0
        elif re.search(r"[.!?।]$", word):
            weight += 2.6
        w.append(weight)
    return np.array(w)


def phonemes_for(kokoro, text, tts_lang):
    """Phoneme string with espeak's language-switch markers removed."""
    return LANG_SWITCH.sub("", kokoro.tokenizer.phonemize(text, tts_lang)).strip()


def speak(kokoro, text, lp):
    if lp["tts_lang"].startswith("en"):
        return kokoro.create(text, voice=lp["voice"], speed=float(lp["speed"]), lang=lp["tts_lang"])
    return kokoro.create(phonemes_for(kokoro, text, lp["tts_lang"]), voice=lp["voice"],
                         speed=float(lp["speed"]), is_phonemes=True)


def synthesize(cfg, script, lp, workdir):
    """lp = language profile. Returns (wav path, timeline, seconds)."""
    from kokoro_onnx import Kokoro

    k = Kokoro(str(MODELS / "kokoro.onnx"), str(MODELS / "voices.bin"))
    gap = np.zeros(int(cfg["voice"]["gap_seconds"] * SR), dtype=np.float32)
    pieces, timeline = [], []
    t = 0.15  # tiny breath before the first word
    pieces.append(np.zeros(int(t * SR), dtype=np.float32))
    for i, sc in enumerate(script["scenes"]):
        log(f"Voice line {i + 1}/{len(script['scenes'])}")
        samples, sr = speak(k, sc["line"], lp)
        if sr != SR:
            raise RuntimeError(f"Unexpected Kokoro sample rate {sr}")
        samples = _trim(samples.astype(np.float32))
        if len(samples) < SR * 0.2:
            raise RuntimeError(f"Voice line {i + 1} came out empty: {sc['line'][:60]}")
        dur = len(samples) / SR
        words = sc["line"].split()
        weights = _word_weights(words)
        bounds = np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * dur
        word_times = [{"word": w, "start": t + bounds[j], "end": t + bounds[j + 1]} for j, w in enumerate(words)]
        timeline.append({"start": t, "end": t + dur, "words": word_times})
        pieces.append(samples)
        pieces.append(gap)
        t += dur + len(gap) / SR
    audio = np.concatenate(pieces)
    path = workdir / "voice.wav"
    sf.write(path, audio, SR)
    log(f"Voice length: {len(audio) / SR:.1f}s")
    return path, timeline, len(audio) / SR
