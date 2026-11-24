---
name: reel-director
description: Cinematic creative direction and strict production QC for the 3D cartoon Shorts. Directs every scene (story purpose, visual concept, hand-built story objects with text, cue-timed reveals, reaction beats, purposeful shot + camera move), then checks real rendered pixels with a vision review, fixes only weak scenes, re-checks, and scores the final MP4 out of 100. Use when making or reviewing a 3D Short, when the free 3D builder runs, or when asked why a video looks generic.
---

# Reel director

Two jobs, one skill:
1. **Director** (before rendering): understand the whole story, then give every scene a reason to exist, a picture that shows the
   EVENT of the line (not a topic illustration), a hero object, a shot + move chosen for the scene's purpose, and reveals timed to
   the spoken word.
2. **Production supervisor** (after rendering): look at real frames, find specific defects, fix only those scenes, verify the fix on
   re-rendered pixels, and write a quality report. Never claim something was checked or fixed without the pixels to prove it.

## Where it runs
The daily pipeline uses it automatically when `config.yaml -> cartoon3d.builder: freellm` (free models via FreeLLMAPI):

| Step | Code | Skill file used |
|---|---|---|
| Director draft: story, plan, cast, scenes | `pipeline/storyboard3d.py build_messages` | `creative-direction/director-brief.md` (system prompt) |
| Code checks (unknown objects, cue not spoken, text too long, shot rules, repeats) + up to 2 repair rounds | `storyboard3d.normalize`, `cartoon3d._ask` | - |
| Director's review of the whole storyboard (kept only if not worse) | `storyboard3d.review_messages` | `quality-control/storyboard-review.md` |
| Compile: fitted framing, coverage cuts every <= 3.9 s, camera keys, rack focus, follow shots, cue frames | `storyboard3d.compile_data` | - |
| **Visual review on real stills** (one per scene, contact sheet, free vision model) | `reel_qc.preview_review` | `quality-control/visual-review.md` |
| Fix only weak scenes, re-render their stills, re-review; keep the fix only if it scores better | `cartoon3d.visual_pass` | `quality-control/scene-fix.md` |
| Full render (voice, music, SFX, burned captions) | `cartoon3d._finish` | - |
| **Final inspection + 100-point score**, critical defects reject the 3D video (the Short is then made in 2D) | `reel_qc.inspect_final` | `quality-control/scoring.md`, `quality-control/technical-inspection.md` |

The report is written to the run's **job summary** (open the run on GitHub, scroll down) and to `cartoon3d_work/quality_report.md`.

## What the director can actually control (engine vocabulary)
- **Story objects** (`kit/engine/prefabs.js`): cash_stack, cash_pile, money_bag, banknote (value + serial text), gold_bars, briefcase
  (open with cash), safe, vault_door, bank (name sign), jet (1960s airliner, flies in "sky" scenes), parachute (falls), newspaper,
  document, sign, label (the one number to remember), magnifier, phone, laptop, evidence_board (notes + red string), chart (grows),
  arrow, question, clock, pine_tree, forest, mountain, cloud, river. Plus 324 KayKit models for places.
- **Object animation**: drop, pop, rise, slide_left/right, spin, float, shake, grow, fly, fall; each can start on a spoken word (`cue`).
- **People**: recurring cast with fixed looks, expression + arm pose, `enter` from a side, `react` (new expression on a word, with a hop).
- **Camera**: shots establishing, wide, medium, close, extreme_close, over_shoulder, insert, low, high; moves push_in, pull_out, orbit,
  track, crane_up/down, tilt_up, rack_focus, follow, hold. Every shot is framed by fitting its subjects (person, hero object, info
  card) into the 9:16 frame, so the important things are never cut off.
- **Sets**: ground (incl. "sky" with a cloud sea), back wall, light (day, golden, night, indoor), depth slots foreground -> far.

## Rules
1. Preserve creative ambition: never simplify a scene because a simpler one is easier to build.
2. Every scene shows the event of its line; text on objects carries the one fact to remember, never the whole sentence.
3. Shot + move follow the camera grammar in `director-brief.md`; never the same shot + move twice in a row.
4. 1-2 animated objects per scene at most; motion must mean something.
5. Fix only weak scenes; keep scenes that already work untouched.
6. Never report a category as checked when nothing inspected it ("not inspected" in the report).
7. Free tiers only: all model calls go through FreeLLMAPI with the per-video and monthly caps in `config.yaml -> freellm`.

## Files
- `creative-direction/director-brief.md`: the creative brief (storytelling, camera grammar, 3D scene design, animation, continuity).
- `quality-control/storyboard-review.md`, `visual-review.md`, `scene-fix.md`: review prompts.
- `quality-control/scoring.md`: weights, thresholds, critical defects.
- `quality-control/technical-inspection.md`: what the final inspector measures and how.
- `workflows/pipeline.md`: the run step by step, budgets, what happens on failure.
- `examples/quality-report.md`: a real report from the inspector.
