# One free-built 3D Short, step by step

1. **Claude** picks the idea and writes the script (unchanged). Each scene has a narration line and a picture idea.
2. **Voice** is generated; word timings give every scene its exact frames.
3. **Director draft** (free model, `auto:smart`): the director brief + the script + the engine vocabulary -> JSON storyboard with a
   story summary, a plan line per scene, a recurring cast, and per scene: purpose, concept, set, objects (with text, size,
   animation, cue word, hero flag), people (expression, arm, entry, reaction on a word), shot, move, focus.
4. **Code checks** everything against what the engine can draw. Mistakes go back to the model (up to 2 rounds); the last round
   keeps safe defaults.
5. **Director's review** (free model) improves weak scenes on paper; kept only if it is at least as clean.
6. **Compile**: every shot is framed by fitting its subjects into 9:16, long scenes get 1-2 extra angles chosen for variety,
   reveals and reactions are placed on the frame where their word is spoken, follow shots track jets and parachutes.
7. **Visual review**: one still per scene is rendered (about 2 s each), a numbered contact sheet goes to a free vision model.
   Scenes scoring below 6 or not showing their line (max 4) are rewritten by the free text model, re-rendered and re-reviewed.
   The fix is kept only when those scenes now score higher. No vision model ready -> the step is skipped and the report says so.
8. **Full render** with music, SFX and captions (same engine, same look as before).
9. **Final inspection** -> score out of 100 + report in the job summary. Critical defect -> this Short is made in 2D instead.

## Requests per video (free tier)
Draft 1-3, review 1-3, visual review 1-2, scene fix 1-3: usually 4-8, hard cap `freellm.max_calls_per_video` (16).
Monthly cap `freellm.monthly_token_cap`, ledger `data/freellm_usage.json`. Switch the visual pass off with
`reel_qc.visual_review: false`.

## Want better pictures from a weak free model?
Add a Google AI Studio key (free tier, no billing) to `FREELLMAPI_KEYS`: Gemini models are usually among the strongest free vision +
reasoning models, and `auto:smart` picks them when they are ready. Without any vision-capable key the visual review is skipped.
