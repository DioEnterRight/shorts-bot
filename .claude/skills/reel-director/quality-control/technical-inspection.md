# Final inspection (what `reel_qc.inspect_final` really measures)

All checks run on the finished MP4 on the GitHub runner with ffmpeg/ffprobe (no paid service, no model call):

| Check | Tool | Defect |
|---|---|---|
| Resolution, frame rate, codec, pixel format | `ffprobe` | not 1080x1920 / 30 fps (critical), not h264 yuv420p |
| Audio present, A/V length | `ffprobe` | no audio (critical), lengths differ > 0.2 s (critical) or > 0.08 s |
| Black frames | `blackdetect=d=0.25:pix_th=0.06` | >= 0.5 s total (critical), shorter flashes |
| Frozen picture | `freezedetect=n=0.0008:d=1.6` | >= 2.5 s (critical), >= 1.6 s lowers motion |
| Loudness and peak | `ebur128=peak=true` | outside -16.5..-11.5 LUFS, peak above -0.5 dBFS |
| Silences in the narration | `silencedetect=n=-40dB:d=1.2` | each gap lowers voice |
| Captions | frames grabbed at 6 word times, lime pixels in the bottom band | none visible (critical), some missing |
| Shots | compiled `data.js` | shots > 4.0 s or < 0.6 s, same shot + move twice, few shot types or moves |

The **visual review** (before the long render) is the only step that judges meaning: it sends a numbered contact sheet of one real
still per scene and the narration lines to a free vision model through FreeLLMAPI (images are routed only to vision-capable models).

Not measured (stated so nobody assumes otherwise): pronunciation accuracy (no speech recognition runs), frame-by-frame motion
quality between the stills, and anything in the Claude-built 3D path (the inspector runs on the free builder's videos).
