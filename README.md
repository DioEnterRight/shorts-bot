# 🪙 Cons & Coins — daily Shorts & Reels bot

Makes and posts **3 animated cartoon Shorts a day** (Instagram Reels + YouTube Shorts) — Hindi in the morning,
English in the afternoon and evening — by itself, in the cloud. Your PC and phone can be off. Cost: ₹0 (your Claude subscription + free tiers).

---

**New here? Read [GUIDE.md](GUIDE.md)** — how to use the bot and what to change for your preferences.

## The rhythm (automatic)

- **~4 AM IST, daily — Make video.** Makes one video per line of `schedule:` in config.yaml (in slot order, so the
  morning video is ready first). For each: picks the theme, researches ~8 ideas, drops anything too close to an old video, writes and fact-checks a 45-65 s script in the kit's
  story formula, voices it (edge-tts, Kokoro as fallback), then the **animated-shorts-kit studio** directs, checks,
  previews, judges and renders a 1080x1920 cartoon (2D characters in a 3D toon world) with captions, music and SFX.
  Saved to **Releases**.
- **Every 30 min — Post video.** When a `schedule:` slot's time comes, posts that slot's video (right language) to
  Instagram + YouTube. Idle runs stop in seconds. A slot can be up to 3 h late (e.g. a slow Make run); after that its
  video waits for the next slot of that language.
- **Sundays** the bot also rewrites its own `data/playbook.md` from real view stats.

## ▶️ Buttons (GitHub → Actions tab)

| Button | What it does |
|---|---|
| **Make video** | Makes today's Short(s). **Test mode** (ticked by default: no keys, the sample story as an artifact) and **language** (`auto`, `en`, `hi`). |
| **Post video** | Posts the oldest ready Short right now (outside the schedule). |
| **Throw away ready videos** | Deletes the waiting Shorts so the next Make builds fresh ones. |
| **Test FreeLLMAPI** | Checks the free-model keys (makes nothing). |

Every Make run uploads a **versions** artifact: the contact sheets (one frame every 0.5 s), shot plan, gate report and
judge scores of each version. You are the final judge.

## ⚙️ Settings — `config.yaml`

| Want to… | Change |
|---|---|
| ⏸ Stop everything | `paused: true` |
| Change topics | `channel → niche` |
| Video length | `video → target_seconds` (45-65) |
| Upload times / how many a day / which language | `schedule` — one line per upload: `- {time: "09:00", language: hi}` (India time, 24h) |
| Explainer vs. story | `themes → <name> → share` |
| Narrator / pace | `languages → en/hi → edge_voice`, `edge_rate`, `words_per_second` |
| Who directs, repairs, judges | `studio` (+ `freellm`, see FREELLM_SETUP.md) |
| Music / SFX level | `studio → music_db`, `sfx_db` |
| YouTube auto vs manual | `publish → youtube_mode`: `api` / `manual` / `off` |

## 🎨 How a video is made — one head skill

Everything lives in **`.claude/skills/animated-shorts-kit/`** — the head skill every AI follows (Claude and the free
models): story formula, 20 characters, a 1930s downtown + grocery + workshop world with 27 named spots, 324 free 3D
props (coins, gold, furniture, cars…), measured camera grammar, the shot-plan format, the checks and the judge.
Start at its `SKILL.md`; `references/08_OUR_PIPELINE.md` explains this repo.

1. Claude: idea + script (one line = one beat).
2. Free model (FreeLLMAPI) = **director**: a shot plan per beat (where people stand, what they do, where the camera goes,
   which word it lands on). Code compiles it onto the kit engine (Three.js + Remotion).
3. The kit's **gates** check every frame (faces cut, people in walls, camera inside a shelf…). Code repairs the director's
   small mistakes and tries camera variations itself; what is left goes back to the director, and if the free model
   can't finish, Claude (Opus) takes over.
4. A preview renders; contact sheets every 0.5 s go to a free vision **judge**; one fix round; the higher score wins.
5. Final render on the GitHub runner (CPU, ~20-40 min) + sound mix at -14 LUFS.
Only if Claude's rescue also fails is that Short made by the old flat 2D engine (`toon2d/`), so a video always ships.

## 🇮🇳 English + Hindi

Every video is one language. Hindi is written fresh as natural Hinglish (Devanagari, with everyday English
words in Latin letters), never translated. The captions on screen are Hinglish in Roman letters. Voices: edge-tts Andrew (English) and Madhur (Hindi); edge-tts is an unofficial Microsoft service,
so if it fails the video uses Kokoro automatically.

## 🏷 AI labels

YouTube's "altered or synthetic" flag is for realistic content; a stylised cartoon is exempt, so
`disclosure → youtube_synthetic: false`. Meta asks for disclosure of realistic-sounding audio, and the narrator
is a synthetic voice, so `instagram_ai_label: true` stays on.

## 🧪 Testing (offline, posts nothing)

```
pip install -r requirements.txt pytest && python -m pipeline.fetch_models
(cd .claude/skills/animated-shorts-kit/code && npm ci)
pytest -m "not slow"                               # seconds, no keys
pytest                                             # + kit gates and a full offline render (~30 min)
python -m pipeline.produce --test                  # sample story -> out/*/final.mp4 (+ versions/)
```

## 🗂 Bot memory (`data/`)

| File | What |
|---|---|
| `history.json` | every Short (queued / published, per-platform state) |
| `analytics.json` | views & stats per video |
| `ideas.json` | every idea used (for "don't repeat yourself") |
| `playbook.md` | lessons Claude rewrites on Sundays |

State is pushed by `tools/save_state.sh`, which **fails the run** if the push fails (a lost push could make the
bot post twice). Before uploading, the bot also checks the account for the same title / caption.

## 🔑 Secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret | For |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | ideas + scripts (`claude setup-token`) |
| `FREELLMAPI_KEYS` | free director + judge (FREELLM_SETUP.md) |
| `IG_USER_ID`, `IG_PAGE_TOKEN` | Instagram posting |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube upload + stats |

`CF_ACCOUNT_ID` / `CF_API_TOKEN` are no longer used and can be deleted.

## 🆘 When a run fails

Open **Actions → the red ❌ run** → read the last lines.

| Message | Fix |
|---|---|
| `Missing secret/env var: X` | add secret X, spelled exactly |
| `Cannot call API for app … on behalf of user` | Meta app: set a Privacy Policy URL, switch to Live, re-make `IG_PAGE_TOKEN` from the admin account |
| `Claude Code call failed` | run `claude setup-token` again → update the secret |
| `studio: … still fails the checks` / `studio failed` (warning) | that Short was made by the emergency 2D engine; look at the `versions` artifact |
| `No video ready` | the Make run failed — fix it, then run Make video |
| `Could not push bot state` / permission errors | Settings → Actions → General → Workflow permissions → **Read and write** |
| `YouTube API uploads are staying private` (issue) | audit not approved yet → set `youtube_mode: manual` |
