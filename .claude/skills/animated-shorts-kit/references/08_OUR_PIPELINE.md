# Our pipeline — the kit inside shorts-bot
Repo `DioEnterRight/shorts-bot`. Channel **Cons & Coins** (money, scams, heists, business, psychology), 3 Shorts a
slot of config.yaml `schedule:` (now: every hour from 00:30, English, 09:30 Hindi/Hinglish, India time). 100 % cloud: GitHub Actions makes, renders and posts; no local machine needed.

## Who does what
| step | who | where |
|---|---|---|
| idea (8 pitches, web research, no repeats) | Claude (`claude:` in config.yaml) | `pipeline/ideas.py`, `prompts/ideas.md` (quotes 02) |
| script + fact-check | Claude | `pipeline/brain.py`, `prompts/script.md` (quotes 02) |
| voice + exact word timings | edge-tts (Kokoro fallback) | `pipeline/voice.py` |
| timeline.ts | code (kit `timeline.py`) | `pipeline/studio.py` |
| shot plan (director) | FreeLLMAPI free model (`studio.director`), Claude when it is not running | `09_PLAN_FORMAT.md` |
| repairs, cheapest first | 1. `plan.py` normalizer fixes mistakes 2. `studio.autofix` climbs camera variations / moves people (no model) 3. glitches of <= `waive_max` checked frames are waived in GATE_WAIVERS with a reason 4. the director gets what is left (`repair_rounds`) 5. Claude `rescue_model` takes over (`rescue_rounds`) 6. only then the 2D engine | `pipeline/studio.py` |
| compile + gates | code (`plan.py`, kit `gates.ts`) | `code/src/engine/` |
| preview, contact sheets, judge, one fix round | Remotion + `sheet.py` + the director's model (FreeLLMAPI vision or Claude) | `10_JUDGE.md` |
| Hindi captions | Claude writes a Roman Hinglish `caption` per line; the studio lays it on the voice timings | `prompts/lang_hi.md` |
| final render 1080x1920 + sound -14 LUFS | Remotion (CPU WebGL) + `pipeline/sound.py` | |
| emergency: anything above fails | the old flat 2D engine | `toon2d/`, `pipeline/toon2d.py` |
| queue + post | GitHub Releases, Instagram + YouTube APIs | `pipeline/publish.py` |

## The daily run (`.github/workflows/make-video.yml`)
1. Hourly: one video for the next upload slot not yet covered by the queue (`pipeline/schedule.py`, `make_ahead`); theme from
   `themes` (explainer ~80 %, story ~20 %).
2. Idea → script (11-16 beats, 45-65 s; words = target_seconds x languages.<code>.words_per_second) → voice.
3. `studio.make()`: timeline → director plan → normalize + compile → gates → autofix → (director / Claude rescue rounds) → preview → contact sheets → judge →
   maybe v2 → best version → final render → mix. Every version lands in `out/<video>/versions/vN/`
   (plan.json, gates.txt, judge.json, sheet_*.jpg, preview.mp4, rounds/round_NN.json = every director round with its
   fixes and gate failures) and they are uploaded as the run's `versions` artifact, even when the build fails.
4. QC (`pipeline/qc.py`), GitHub Release, history saved. `post-video.yml` runs every 30 min and posts a slot's video
   when its time comes (up to 3 h late), tying the video to the slot so retries never double-post.

Render cost (measured, 2 CPUs): preview ~0.3 s/frame, full HD ~0.75 s/frame → a 55 s Short ≈ 10 min preview + 20 min final.
Tokens: Claude for idea (backlog reused) + script + director (one tool-free call with our own system prompt); judge on a
free FreeLLMAPI vision model. `studio.director: freellm` moves directing to free models too, see GUIDE.md §5.

## Config (`config.yaml`)
`schedule` (one line per daily upload: time + language), `video.target_seconds` (45-65), `languages.*.words_per_second` (kit pace), `studio` (director, repair_rounds, judge,
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
