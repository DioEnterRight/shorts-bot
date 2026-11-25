"""Sound for the kit's videos (02_STORY_FORMULA 'Sound'): one narrator, a music bed that never stops 10-15 dB under the
voice, SFX tucked under the voice, master at -14 LUFS. Synths come from the 2D engine (toon2d/engine/audio.py)."""
import sys

import numpy as np
import soundfile as sf

from .common import ROOT, log, run

sys.path.insert(0, str(ROOT / "toon2d"))
from engine import audio as A  # noqa: E402

MOODS = ("mystery", "upbeat", "dramatic", "calm", "tense")


def mix(voice_wav, sfx_events, mood, music_db=-13.0, sfx_db=-10.0):
    """-> stereo float mix. Levels are locked to the gated RMS of the voice; the voice itself is untouched."""
    v, sr = sf.read(str(voice_wav), dtype="float64", always_2d=True)
    if sr != A.SR:
        raise RuntimeError(f"voice must be {A.SR} Hz, got {sr}")
    voice = np.repeat(v[:, :1], 2, 1)
    n, length = len(voice), len(voice) / A.SR
    music = A.music_bed(length, mood if mood in MOODS else "mystery", [])[:n]
    music = np.pad(music, ((0, n - len(music)), (0, 0)))
    sfx = np.zeros((n, 2))
    for t, name in sfx_events:
        A.place(sfx, A.SFX[name](), float(t), 0.8)
    env = A.lp(np.abs(voice).mean(1), 6, 1)
    gate = env > np.percentile(env[env > 0], 40) * 0.5
    vref = np.sqrt(np.mean(voice[gate] ** 2))
    rms = lambda x: np.sqrt(np.mean(x[np.abs(x).mean(1) > 1e-5] ** 2)) + 1e-9
    music *= vref * 10 ** (music_db / 20) / rms(music)
    tt = np.arange(n) / A.SR
    music *= (np.minimum(1, tt / 0.3) * np.clip((length - tt) / 0.6, 0, 1))[:, None]   # soft in/out only, no ducking
    if np.abs(sfx).max() > 0:
        sfx *= vref * 10 ** (sfx_db / 20) / rms(sfx)
        vpk, spk = np.abs(voice).max(), np.abs(sfx).max()
        if spk > 0.7 * vpk:
            sfx *= 0.7 * vpk / spk
    db = lambda x: 20 * np.log10(np.sqrt(np.mean(x[gate] ** 2)) + 1e-12)
    log(f"sound: music {db(music) - db(voice):+.1f} dB under the voice, {len(sfx_events)} sfx, mood {mood}")
    return voice + music + sfx


def finish(picture, voice_wav, sfx_events, mood, cfg, out):
    """silent picture + voice -> final mp4 with the mix at -14 LUFS"""
    st = cfg["studio"]
    work = out.parent
    raw = work / "mix_raw.wav"
    sf.write(raw, mix(voice_wav, sfx_events, mood, float(st.get("music_db", -13)), float(st.get("sfx_db", -10))).astype(np.float32), A.SR)
    A.loudness(str(raw), str(work / "mix.wav"), -14.0)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(picture), "-i", str(work / "mix.wav"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(out)])
    return out
