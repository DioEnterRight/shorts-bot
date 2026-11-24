# 🪙 Cons & Coins — daily Shorts & Reels bot

Makes **one 2D cartoon Short a day** (Instagram Reels + YouTube Shorts) and **one long English video a week**
(YouTube), by itself, in the cloud. Your PC and phone can be off. Cost: ₹0 (your Claude subscription + free tiers).

---

## The rhythm (automatic)

- **~4 AM IST, daily — Make video.** Picks the language (English every day, one Hindi video a week) and theme,
  researches ~8 ideas, drops anything too close to an old video, writes and fact-checks the script, voices it
  (edge-tts, Kokoro as fallback), then Claude writes one storyboard and the **toon2d** engine draws it: a vertical
  1080x1920 cartoon with captions, music and sound. Saved to **Releases**.
- **~7 PM IST, daily — Post video.** Posts the oldest ready video to Instagram + YouTube.
- **Sundays ~10 AM IST — Long video.** The week's best English Short becomes a researched ~5-minute 16:9 video,
  uploaded to YouTube as **private** (set `longform → privacy: public` once you like them).
- **Sundays** the bot also rewrites its own `data/playbook.md` from real view stats.
- Keeps 1 ready Short (`buffer`), so each daily run makes one; if a 3D build fails, that Short is made in 2D.

## ▶️ Buttons (GitHub → Actions tab)

| Button | What it does |
|---|---|
| **Make video** | Makes today's Short(s). **Test mode** (ticked by default: no keys, sample video as an artifact) and **language** (`auto`, `en`, `hi`). |
| **Post video** | Posts the oldest ready Short right now. |
| **Long video (weekly)** | Makes the long video now. **test** = offline sample, no upload. **upload** off = keep the file only. |
| **Throw away ready videos** | Deletes the waiting Shorts so the next Make builds fresh ones. |

## ⚙️ Settings — `config.yaml`

| Want to… | Change |
|---|---|
| ⏸ Stop everything | `paused: true` |
| Change topics | `channel → niche` |
| Language plan | `allocation` (`mode: weekly`, `weekly_quota: {hi: 1}`; `mode: adaptive` = learn from views) |
| Explainer vs. other themes | `themes → <name> → share` |
| Different narrator | `languages → en/hi → edge_voice` (Kokoro fallback: `voice`) |
| Storyboard model, captions, music level | `toon2d` |
| Long video length, privacy | `longform` (`minutes`, `privacy`, `enabled`) |
| Post time | the `cron:` line in `.github/workflows/post-video.yml` (UTC = IST − 5:30) |
| YouTube auto vs manual | `publish → youtube_mode`: `api` / `manual` / `off` |

## 🎨 How a video is drawn

`toon2d/` is a flat 2D ink-on-paper cartoon engine (Python + skia, CPU only), adapted from ReachMora 2D
Long-Form (credit in `toon2d/CREDITS.md`). Claude Sonnet writes one `story.json` per video: shot kinds like
closeup, wide, walk, counter, chart, table, versus, map, list and a polaroid ending, cued to spoken words. It
never writes drawing code, so a video costs one short Claude call. The engine checks the storyboard, Claude
gets one repair round, and an automatic storyboard is the last fallback, so a video always ships. Mouths
follow the words; Shorts get burned-in captions. A Short renders in ~2-4 min on the runner.
Look at shots by hand: `cd toon2d && RM_ASPECT=9:16 python -m engine stills <video folder>/toon2d`.

**Mixed 3D + 2D Shorts (default: `video → style: cartoon3d`).** For every Short, Claude (Opus) runs the
`cartoon-audio-short` skill on the runner: it builds a new inked, painted 3D world, original card characters, poses,
cameras and a sound-cue table, checks one or two contact sheets, and the bot renders it in Chrome (CPU WebGL,
~30-60 min) and mixes it. If anything fails, that Short is made in toon2d instead. This costs far more tokens
than toon2d: every Claude call logs `Claude usage: ...`, and `/usage` in Claude Code before and after a run shows
the share of your weekly limit. Too much? Set `style: toon2d`. Test mode renders the kit's soldier example.

**Free 3D builder (`cartoon3d → builder: freellm`).** Claude still writes the idea and script; your FreeLLMAPI
(started inside the job from the `FREELLMAPI_KEYS` secret, like roblox-stories-bot) plans the 3D world as a small JSON
storyboard, code checks and compiles it, then the same renderer draws it. Setup, quality design and free-tier
safety: [FREELLM_SETUP.md](FREELLM_SETUP.md). Creative direction and QC come from the **reel-director** skill
([.claude/skills/reel-director/SKILL.md](.claude/skills/reel-director/SKILL.md)): story objects, cue-timed reveals, purposeful
camera, a vision check of real stills with targeted fixes, and a 100-point report in each run's job summary.

## 🇮🇳 English + Hindi

Every video is one language. Hindi is written fresh as natural Hinglish (Devanagari, with everyday English
words in Latin letters), never translated. On-screen text stays in Roman letters (the cartoon fonts have no
Devanagari). Voices: edge-tts Andrew (English) and Madhur (Hindi); edge-tts is an unofficial Microsoft service,
so if it fails the video uses Kokoro automatically.

## 🏷 AI labels

YouTube's "altered or synthetic" flag is for realistic content; a 2D cartoon is exempt, so
`disclosure → youtube_synthetic: false`. Meta asks for disclosure of realistic-sounding audio, and the narrator
is a synthetic voice, so `instagram_ai_label: true` stays on.

## 🧪 Testing (offline, posts nothing)

```
pip install -r requirements.txt pytest && python -m pipeline.fetch_models
pytest -m "not slow"                               # seconds, no keys
pytest                                             # + full offline renders (several minutes)
python -m pipeline.produce --test --language hi    # look at out/*/final.mp4
python -m pipeline.longform --test                 # 16:9 sample long video
```

## 🗂 Bot memory (`data/`)

| File | What |
|---|---|
| `history.json` | every Short (queued / published, per-platform state) and every long video (`longform`) |
| `analytics.json` | views & stats per video + the language split |
| `ideas.json` | every idea used (for "don't repeat yourself") |
| `playbook.md` | lessons Claude rewrites on Sundays |

State is pushed by `tools/save_state.sh`, which **fails the run** if the push fails (a lost push could make the
bot post twice). Before uploading, the bot also checks the account for the same title / caption.

## 🔑 Secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret | For |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | ideas, scripts, storyboards (`claude setup-token`) |
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
| `Storyboard problems: …` (warning) | fine: Claude's second try or the automatic storyboard was used |
| `No video ready` | the Make run failed — fix it, then run Make video |
| `Could not push bot state` / permission errors | Settings → Actions → General → Workflow permissions → **Read and write** |
| `YouTube API uploads are staying private` (issue) | audit not approved yet → set `youtube_mode: manual` |

## 🎨 Channel art

`python tools/brand_art.py out/brand` redraws the profile pictures (1080x1080, Instagram + YouTube) and the
YouTube banner (2560x1440) with the video engine, so they match the videos.

## 🛠 Dev tools (for working on the bot with Claude Code)

graphify (`uv tool install graphifyy`, then `graphify update .`; hooks in `.claude/settings.json` fail open in
CI), ponytail skills (`/plugin marketplace add DietrichGebert/ponytail`, `/plugin install ponytail@ponytail`),
and `tools/validate_skills.sh` (agentskills spec check).
