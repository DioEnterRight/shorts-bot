#!/usr/bin/env python3
"""Level-locked mix:  python3 mix.py voice.mp3 music.wav sfx.wav  ->  mix_raw.wav
Music sits at exactly 50 % of the voice (-6 dB, gated RMS). SFX at 50 % too, with peaks capped at 0.7x the voice peak.
No ducking or compression: the voice is untouched and one linear gain per stem keeps the ratio fixed."""
import subprocess, sys, wave
import numpy as np

SR = 48000

def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()

def gated_rms(x, gate_db=-40.0):
    """RMS over 50 ms blocks louder than gate_db below the loudest block (ignores silence)."""
    k = int(0.05 * SR); n = len(x) // k
    if n == 0: raise SystemExit("audio too short")
    blocks = np.sqrt(np.mean(x[: n * k].reshape(n, k) ** 2, axis=1) + 1e-12)
    keep = blocks[20 * np.log10(blocks / blocks.max()) > gate_db]
    return float(np.sqrt(np.mean(keep ** 2)))

db = lambda r: 20 * np.log10(max(r, 1e-12))

def main(vp, mp, sp, out="mix_raw.wav"):
    v, m, s = load(vp), load(mp), load(sp)
    n = len(v); m = np.pad(m, (0, max(0, n - len(m))))[:n]; s = np.pad(s, (0, max(0, n - len(s))))[:n]
    vr, vpk = gated_rms(v), float(np.abs(v).max())
    if vr < 1e-5: raise SystemExit("voice is silent")
    m *= 0.5 * vr / gated_rms(m)
    if np.abs(s).max() > 0:
        s *= 0.5 * vr / gated_rms(s)
        if np.abs(s).max() > 0.7 * vpk: s *= 0.7 * vpk / np.abs(s).max()
    print(f"voice {db(vr):.1f} dBFS | music {db(gated_rms(m)) - db(vr):+.1f} dB vs voice | "
          f"sfx {db(gated_rms(s)) - db(vr) if np.abs(s).max() > 0 else float('-inf'):+.1f} dB vs voice, peak {np.abs(s).max() / vpk:.2f}x voice peak")
    mix = v + m + s
    pk = np.abs(mix).max()
    if pk > 0.99: mix *= 0.99 / pk   # one linear gain on the whole mix: ratios unchanged
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(out)

if __name__ == "__main__":
    if len(sys.argv) < 4: raise SystemExit(__doc__)
    main(*sys.argv[1:4])
