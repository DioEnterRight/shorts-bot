# Example: a real report from the inspector

Produced by `pipeline/reel_qc.py` on the D.B. Cooper test render made while building this skill (no voice available offline,
so the track is silent, and no vision model was reachable, so the picture categories say "not inspected"). The inspector
rejects it for the silent track, which is the correct outcome. In the pipeline this report appears in the run's job summary
and in `cartoon3d_work/quality_report.md`; with a vision model ready it also lists a score and issue for every scene.

## Reel QC: D.B. Cooper demo (silent test render)

**Score 78/100 - REJECTED (critical defect)** (partial: some categories could not be inspected, the score uses the rest)

| Category | Weight | Result |
|---|---:|---|
| Storytelling and creativity | 15 | not inspected |
| Cinematic camera direction | 15 | 8.0/10 |
| Visual storytelling and composition | 15 | not inspected |
| 3D models and environments | 10 | not inspected |
| Animation and motion | 10 | 10.0/10 |
| Voice quality | 10 | 0.0/10 |
| Captions | 10 | 10.0/10 |
| Editing and transitions | 10 | 10.0/10 |
| Technical export quality | 5 | 10.0/10 |

Critical defects: audio is silent
Notes: none
Shots: 10 (6 shot types, 9 camera moves, 0 repeats), longest 3.73 s;
animated objects 6, reaction beats 1, story objects 17 in 6 scenes.
Loudness -70.0 LUFS, peak None dBFS, length 25.53 s.
