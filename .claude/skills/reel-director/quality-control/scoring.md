# Quality score (implemented in `pipeline/reel_qc.py`, `WEIGHTS`)

| Category | Weight | Measured by |
|---|---:|---|
| Storytelling and creativity | 15 | vision review of the preview stills ("storytelling") |
| Cinematic camera direction | 15 | shot metrics from the compiled shots (variety of shot types and moves, repeats, static holds) blended with the vision "camera" score |
| Visual storytelling and composition | 15 | vision per-scene scores + "composition", scaled by the share of scenes that show their line |
| 3D models and environments | 10 | vision "assets" + "continuity", plus story objects per scene |
| Animation and motion | 10 | animated objects and reaction beats in the data, frozen-picture detection on the MP4 |
| Voice quality | 10 | integrated loudness (target -14 LUFS), peak (clipping), silences over 1.2 s inside the narration |
| Captions | 10 | real frames grabbed at word times, lime current-word pixels in the caption band; word timing order |
| Editing and transitions | 10 | shot lengths (0.6-4.0 s), repeats |
| Technical export quality | 5 | ffprobe: 1080x1920, 30 fps, h264/yuv420p, audio present, A/V length; black-frame detection |

Each category is scored 0-10, the total is the weighted sum scaled to 100.

- **90-100** production ready
- **80-89** minor improvements
- **70-79** requires revision
- **below 70** rework required

**Critical defects override the number** and reject the 3D video (the pipeline then makes that Short in 2D): wrong resolution or
frame rate, no audio, audio/video lengths differ by more than 0.2 s, black frames for 0.5 s or more, a frozen picture for 2.5 s or
more, no captions visible at word times.

**Honesty rules**
- A category nothing could measure is "not inspected" (for example, no vision model was ready). The score then uses only the
  inspected categories and is marked *partial*. It is never filled with a guess.
- A technically clean but boring video can't score high: storytelling, composition and camera come from looking at the pictures.
