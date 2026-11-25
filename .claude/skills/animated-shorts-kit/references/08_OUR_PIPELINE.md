# Our pipeline — the kit inside shorts-bot
Repo `DioEnterRight/shorts-bot`. Channel **Cons & Coins** (money, scams, heists, business, psychology), English every
day + one Hindi (Hinglish) Short a week. 100 % cloud: GitHub Actions makes, renders and posts; no local machine needed.

## Who does what
| step | who | where |
|---|---|---|
| idea (8 pitches, web research, no repeats) | Claude (`claude:` in config.yaml) | `pipeline/ideas.py`, `prompts/ideas.md` (quotes 02) |
| script + fact-check | Claude | `pipeline/brain.py`, `prompts/script.md` (quotes 02) |
| voice + exact word timings | edge-tts (Kokoro fallback) | `pipeline/voice.py` |
| timeline.ts | code (kit `timeline.py`) | `pipeline/studio.py` |
| shot plan (director) + repairs | FreeLLMAPI free model (`studio.director`), Claude when it is not running | `09_PLAN_FORMAT.md` |
| compile + gates | code (`plan.py`, kit `gates.ts`) | `code/src/engine/` |
| preview, contact sheets, judge, one fix round | Remotion + `sheet.py` + FreeLLMAPI vision | `10_JUDGE.md` |
| final render 1080x1920 + sound -14 LUFS | Remotion (CPU WebGL) + `pipeline/sound.py` | |
| emergency: anything above fails | the old flat 2D engine | `toon2d/`, `pipeline/toon2d.py` |
| queue + post | GitHub Releases, Instagram + YouTube APIs | `pipeline/publish.py` |

## The daily run (`.github/workflows/make-video.yml`)
1. Slot: language (`allocation`) and theme (`themes`: explainer ~80 %, story ~20 %).
2. Idea → script (11-16 beats, 45-65 s at 3.3-3.8 words/s) → voice.
3. `studio.make()`: timeline → director plan → compile → gates (repair rounds) → preview → contact sheets → judge →
   maybe v2 → best version → final render → mix. Every version lands in `out/<video>/versions/vN/`
   (plan.json, gates.txt, judge.json, sheet_*.jpg, preview.mp4) and the sheets are uploaded as the run's `versions` artifact.
4. QC (`pipeline/qc.py`), GitHub Release, history saved. Posting happens in `post-video.yml`.

Render cost (measured, 2 CPUs): preview ~0.3 s/frame, full HD ~0.75 s/frame → a 55 s Short ≈ 10 min preview + 20 min final.
Tokens: Claude only for idea + script; the director/judge use free models (`freellm.max_calls_per_video`, `monthly_token_cap`).

## Config (`config.yaml`)
`video.target_seconds` (45-65), `languages.*.words_per_second` (kit pace), `studio` (director, repair_rounds, judge,
good_enough, music_db, sfx_db, render_timeout_minutes), `freellm` (models, caps), `toon2d` (emergency only).

## Working by hand (Claude Code)
- Test the whole chain offline: `python -m pipeline.produce --test` (sample script + `prompts/sample_plan.json`).
- One video by hand: put `timeline.ts` in `code/src/videos/<id>/` (timeline.py), write `plan.json`, then
  `python3 code/src/engine/tools/plan.py plan.json code/src/videos/<id>`, `VIDEO=<id> npm run gates`, `VIDEO=<id> npm run preview`.
- Improve the engine, not one video: new spots go in `library/environments/spots.json` (check them with a still),
  new solids in `kits/*/…Data.ts`, new props via KayKit models, new characters in `charparts.ts` (LOOKS + SHAPES + `Who`).
  The plan compiler reads actions, characters and expressions straight from the engine's types.
- Tests: `python -m pytest -q -m "not slow"` (seconds). `-m slow` = gates + full offline render.
- Never post, push or touch `data/` while testing.

## Rules that stay
Original stories and characters only, no real living people as targets, no logos/brands, facts checked, money talk is
education not advice. The user is the final judge.
