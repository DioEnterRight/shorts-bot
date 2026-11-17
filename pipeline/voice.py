"""Voiceover: Microsoft edge-tts (primary, real per-word timestamps) with Kokoro as the fallback.

Each scene line is spoken separately, so we know exactly when every line starts.
edge-tts streams a WordBoundary event per spoken word; align_words() maps those onto the
script's own words (numbers and symbols can be spoken as several words). If edge-tts fails for
any line after retries, the WHOLE video falls back to Kokoro so the voice never changes mid-video.
Kokoro gives no timestamps, so word times are estimated from each word's phoneme count.

edge-tts uses Microsoft's free read-aloud service without an official licence: it can rate-limit
or stop working at any time, which is why Kokoro stays wired in.

Hindi/Hinglish: espeak-ng phonemizes Devanagari with Hindi rules and English words (written in
Latin letters) with English rules, but marks every switch with "(en)"/"(hi)". Kokoro would
read those markers as sounds, so we phonemize ourselves, drop the markers and pass phonemes.
"""
import asyncio
import difflib
import re
import subprocess
import time

import numpy as np
import soundfile as sf

from .common import MODELS, is_wordchar, log, norm_text

SR = 24000
LANG_SWITCH = re.compile(r"\([a-z]{2}(?:-[a-z]{2})?\)")


def _trim(x, thresh=0.01, pad=0.03):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(pad * SR))
    b = min(len(x), idx[-1] + int(pad * SR))
    return x[a:b]


def _word_weights(words, sizes=None):
    """Relative speaking time per word. sizes = phoneme count per word when known."""
    w = []
    for i, word in enumerate(words):
        core = "".join(ch for ch in word if is_wordchar(ch))
        size = sizes[i] if sizes else len(core)
        weight = 1.2 + size * 0.55
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


def _phoneme_sizes(kokoro, words, lp):
    try:
        return [max(1, len(phonemes_for(kokoro, w, lp["tts_lang"]).replace(" ", ""))) for w in words]
    except Exception:  # noqa: BLE001 - estimate falls back to letter counts
        return None


def synthesize(cfg, script, lp, workdir, allow_edge=True):
    """lp = language profile. Returns (wav path, timeline, seconds, engine name)."""
    engine = cfg["voice"].get("engine", "kokoro")
    if engine == "edge" and allow_edge and lp.get("edge_voice"):
        try:
            return (*_synthesize_edge(cfg, script, lp, workdir), "edge")
        except Exception as e:  # noqa: BLE001 - any edge failure means Kokoro for the whole video
            log(f"edge-tts failed ({e}); using Kokoro for this video", "WARN")
    elif engine not in ("edge", "kokoro"):
        raise ValueError(f"voice.engine must be edge or kokoro, not {engine!r}")
    return (*_synthesize_kokoro(cfg, script, lp, workdir), "kokoro")


def pace_wpm(timeline):
    """Words per minute over the whole voice track, pauses included (target 160-180 for Shorts)."""
    words = sum(len(line["words"]) for line in timeline)
    return words / max(timeline[-1]["end"], 1e-6) * 60


def _synthesize_kokoro(cfg, script, lp, workdir):
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
        weights = _word_weights(words, _phoneme_sizes(k, words, lp))
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


# ---------------- edge-tts ----------------

def align_words(words, marks, dur):
    """Map spoken-word timestamps onto the script's words (clean-room, sequence alignment).

    words: script words for one line. marks: [(start, end, text)] from WordBoundary, seconds
    from the start of the line. Matched words take the mark times; unmatched words (e.g. "37°C"
    spoken as "thirty seven degrees") share the gap between their matched neighbours in
    proportion to their length. Result is monotonic and inside [0, dur].
    """
    if not words:
        return []
    keys = [norm_text(w) for w in words]
    mkeys = [norm_text(m[2]) for m in marks]
    times = [None] * len(words)
    sm = difflib.SequenceMatcher(a=keys, b=mkeys, autojunk=False)
    for blk in sm.get_matching_blocks():
        for j in range(blk.size):
            m = marks[blk.b + j]
            times[blk.a + j] = [m[0], m[1]]
    for op, a0, a1, b0, b1 in sm.get_opcodes():   # replaced spans: give them the marks' time range
        if op == "replace" and b1 > b0:
            lo, hi = marks[b0][0], marks[b1 - 1][1]
            sizes = [max(1, len(keys[i])) for i in range(a0, a1)]
            edges = np.concatenate([[0], np.cumsum(sizes)]) / sum(sizes) * (hi - lo) + lo
            for k, i in enumerate(range(a0, a1)):
                times[i] = [edges[k], edges[k + 1]]
    i = 0
    while i < len(words):           # anything still unmatched: spread over the free gap
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else 0.0
        hi = times[j][0] if j < len(words) else dur
        hi = max(hi, lo)
        sizes = [max(1, len(keys[x])) for x in range(i, j)]
        edges = np.concatenate([[0], np.cumsum(sizes)]) / sum(sizes) * (hi - lo) + lo
        for k, x in enumerate(range(i, j)):
            times[x] = [edges[k], edges[k + 1]]
        i = j
    prev = 0.0
    for t in times:                 # monotonic, inside the line
        t[0] = min(max(t[0], prev), dur)
        t[1] = min(max(t[1], t[0] + 0.04), dur)
        prev = t[0]
    return [(float(a), float(b)) for a, b in times]


async def _edge_stream(text, voice, rate):
    import edge_tts

    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    audio, marks = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":   # offset/duration are in 100-nanosecond ticks
            marks.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    if not audio:
        raise RuntimeError("edge-tts returned no audio")
    return bytes(audio), marks


def _decode_mp3(data):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "pipe:1"], input=data, capture_output=True, check=True)
    return np.frombuffer(out.stdout, dtype=np.float32).copy()


def edge_line(text, voice, rate, retries):
    """One spoken line -> (samples at SR, marks). Retries with backoff, then raises."""
    for attempt in range(1, retries + 1):
        try:
            data, marks = asyncio.run(_edge_stream(text, voice, rate))
            return _decode_mp3(data), marks
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                raise
            log(f"edge-tts attempt {attempt} failed ({e}); retrying", "WARN")
            time.sleep(2 * attempt)


def _synthesize_edge(cfg, script, lp, workdir):
    vc = cfg["voice"]
    gap = np.zeros(int(vc["gap_seconds"] * SR), dtype=np.float32)
    t = 0.15
    pieces, timeline = [np.zeros(int(t * SR), dtype=np.float32)], []
    for i, sc in enumerate(script["scenes"]):
        log(f"Voice line {i + 1}/{len(script['scenes'])} (edge-tts)")
        raw, marks = edge_line(sc["line"], lp["edge_voice"], lp.get("edge_rate", "+0%"),
                               int(vc.get("edge_retries", 3)))
        idx = np.where(np.abs(raw) > 0.01)[0]
        if len(idx) == 0 or len(raw) < SR * 0.2:
            raise RuntimeError(f"edge-tts line {i + 1} came out empty")
        a = max(0, idx[0] - int(0.03 * SR))
        b = min(len(raw), idx[-1] + int(0.03 * SR))
        samples, lead = raw[a:b], a / SR
        dur = len(samples) / SR
        shifted = [(m0 - lead, m1 - lead, txt) for m0, m1, txt in marks]
        words = sc["line"].split()
        spans = align_words(words, shifted, dur)
        timeline.append({"start": t, "end": t + dur,
                         "words": [{"word": w, "start": t + s0, "end": t + s1} for w, (s0, s1) in zip(words, spans)]})
        pieces += [samples, gap]
        t += dur + len(gap) / SR
    audio = np.concatenate(pieces)
    path = workdir / "voice.wav"
    sf.write(path, audio, SR)
    log(f"Voice length: {len(audio) / SR:.1f}s (edge-tts {lp['edge_voice']})")
    return path, timeline, len(audio) / SR
