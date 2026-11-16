# 🌍 Explore The World — daily Shorts & Reels bot

Makes **one video a day** and posts it to **Instagram Reels** + **YouTube Shorts**, by itself, in the cloud. Your PC and phone can be off. Cost: ₹0 (your Claude subscription + free tiers).

---

## ✅ Current status (14 Nov 2026)

| Part | State |
|---|---|
| Make video (script → pictures → voice → captions → music → edit) | ✅ working |
| YouTube upload (API) | ✅ working — last test uploaded publicly |
| Instagram upload | ⚠️ needs one fix — see **Fix Instagram** below |
| Higgsfield slot | ✅ built in, test it any time (see **Higgsfield**) |

---

## The daily rhythm (automatic)

- **~4 AM IST** — Make video: picks the **language** (English or Hindi, learned from views) and the **theme** (mostly explainers), researches and pitches ~8 ideas, throws out anything too close to an old video, writes + fact-checks a scene-by-scene storyboard, draws a different picture for every beat (same character in character shots), adds voice, captions, transitions, music and sound, saves it to **Releases**.
- **~7 PM IST** — Post video: posts the oldest ready video to Instagram + YouTube.
- **Sundays** — rewrites its own `data/playbook.md` from real view stats.
- Always keeps 2 spare videos so a bad day never misses a post.

---

## 🔧 Fix Instagram (one time, ~5 min)

Your last run showed: `Cannot call API for app ... on behalf of user`. That means your Meta app isn't allowed to act for your account yet. Fix:

1. **developers.facebook.com** → your app → **App settings → Basic** → put your **Privacy Policy URL** (your policy page link) in the Privacy Policy field → **Save changes**.
2. Top of the dashboard: switch **App Mode** from **Development** to **Live**.
3. **App roles → Roles** → confirm your Facebook account is listed as **Administrator**.
4. Re-make the token (it must come from the admin): **Graph API Explorer** → your app → **Generate Access Token** → tick your Page + Instagram → in the query box run `me/accounts` → copy the Page `access_token`.
5. Update the GitHub secret **`IG_PAGE_TOKEN`** with that new token.
6. Test: **Actions → Post video → Run workflow**.

If it still fails, open the red run — the log now prints the exact fix for whatever Meta complains about.

---

## ▶️ Everyday buttons (GitHub → Actions tab)

| Button | What it does |
|---|---|
| **Make video** | Makes today's video(s). Options when you click *Run workflow*: **Test mode** (ticked by default: no keys, shows a sample — untick it to make real videos), **provider** (pick `higgsfield_test` to demo the Higgsfield pipeline) and **language** (`auto` = learned split, or force `en` / `hi`). |
| **Post video** | Posts the oldest ready video right now. |
| **Throw away ready videos** | Deletes the waiting videos (use when you don't like them), so the next Make builds fresh ones. |

---

## ⚙️ Settings — `config.yaml` (edit on github.com with the ✏️ pencil)

| Want to… | Change |
|---|---|
| ⏸ Stop everything | `paused: true` |
| Change topics | `channel → niche` |
| Languages | `languages → enabled` (`[en, hi]`, or just `[en]`) |
| Min. share of the weaker language | `allocation → floor` (0.2 = never below 20%, never above 80%) |
| Explainer vs. other themes | `themes → <name> → share` (explainer 0.8; set a theme to 0 to switch it off) |
| Switch visuals (incl. Higgsfield) | `visuals → provider` (see next section) |
| Different narrator | `languages → en/hi → voice` / `speed` |
| Picture style | `visuals → art_style` and `visuals → shots` |
| New main character | change `visuals → mascot` (bot draws a new character sheet in `data/characters/`) |
| Caption size | `languages → en/hi → caption_font_size` |
| AI labels | `disclosure` (see **AI labels** below) |
| Post time | the `cron:` line in `.github/workflows/post-video.yml` (UTC = IST − 5:30) |
| YouTube auto vs manual | `publish → youtube_mode`: `api` (auto) / `manual` (phone notification) / `off` |

---

## 🎬 Higgsfield — the swap slot

`config.yaml → visuals → provider`. Change one word:

| Value | What you get | Needs |
|---|---|---|
| `cloudflare_klein` | FREE AI pictures, same character + style every scene | nothing (default) |
| `higgsfield_test` | **Demo**: full video built from placeholder motion clips | nothing — proves the pipeline |
| `higgsfield_clips` | REAL Higgsfield motion clips + our voice/captions/music | Higgsfield |
| `higgsfield_full` | Higgsfield makes the whole video | Higgsfield |

**Check the pipeline now, no account:** Actions → Make video → Run workflow → Test mode ✅, provider `higgsfield_test` → download the result. If that looks right, real Higgsfield will too.

**When Higgsfield is back:** set `provider: higgsfield_clips` and follow **`tools/higgsfield_routine_prompt.md`** (a Claude routine drops the clips into `inbox/` and the bot assembles them). To go back to free: `cloudflare_klein`.

---

## 🇮🇳 English + Hindi

- Every video is **one** language. Hindi videos are written fresh as natural spoken **Hinglish**
  (Devanagari, with everyday English words like *brain*, *signal*, *stomach* in Latin letters so
  the voice says them in English) — never translated from an English script.
- Voice: Kokoro (free, on the runner). Hindi voices `hm_omega`, `hm_psi`, `hf_alpha`, `hf_beta`.
  Their quality is rated "C" by the model's authors — listen to the first Hindi videos and swap the
  voice in `config.yaml` if needed.
- Captions: Noto Sans Devanagari (+ Noto Sans for English words), long chunks shrink to fit.
- **Learning the split:** every morning `data/analytics.json` gets fresh views. Each language's
  score is the median of log(age-adjusted views) of its recent videos (one viral video can't
  swing it, a 2-day-old video is compared fairly with a 10-day-old one). With fewer than 4 videos
  per language it stays 50/50. Shares then move slowly toward the winner, but never past 80/20,
  and the weaker language is guaranteed a slot at least every 5 videos.

## 💡 Ideas

Claude researches first (web search), pitches ~8 specific ideas with a hook, angle, payoff and
visual moments, and the bot drops anything too similar to an earlier video (`data/ideas.json`
+ history, compared by meaning, not just title — "why does your stomach growl" = "what makes your
tummy rumble"). About 80% explainers; the rest are `story` and a small `roblox_story` experiment.

## 🎨 Visual style

Each script is a storyboard of ~8-13 beats. Every beat has its own shot (character / cutaway /
diagram / metaphor / close-up / wide), place, camera move, transition (cut / whip / zoom / fade)
and optional label. Pictures are stylised 3D-cartoon, never photoreal. The recurring character
gets a reference sheet so he looks the same; cutaways and diagrams don't, so backgrounds can change.
If a picture fails, the bot tries a second model, then re-uses a neighbour (and stops if more than
a quarter failed).

## 🏷 AI labels

- **YouTube** only requires the "altered or synthetic" flag for **realistic** content; clearly
  animated content is exempt. With `disclosure → photorealistic_visuals: false` the bot uploads with
  `containsSyntheticMedia: false`. Switch to realistic visuals → set it to `true`.
- **Instagram/Meta** asks for disclosure of photorealistic video **or realistic-sounding audio**.
  The narrator is a realistic synthetic voice, so `instagram_ai_label: true` stays on by default.
  Meta can also add its own label; no setting can prevent that.

## 🧪 Testing (offline, posts nothing)

```
pip install -r requirements.txt pytest && python -m pipeline.fetch_models
pytest -m "not slow"          # ~2 s, no keys
pytest                        # + renders an English and a Hindi test video (~2 min)
python -m pipeline.produce --test --language hi   # look at out/*/final.mp4
```

## 🗂 Bot memory (`data/`)

| File | What |
|---|---|
| `history.json` | every video: queued / published, per-platform state (`ig_state`, `yt_state`) |
| `analytics.json` | views & stats per video + the current English/Hindi split |
| `ideas.json` | every idea used (for "don't repeat yourself") |
| `playbook.md` | lessons Claude rewrites on Sundays |

State files are written atomically and pushed by `tools/save_state.sh`, which **fails the run**
if the push fails (a lost push could otherwise make the bot post the same video twice).
Posting is also guarded: before uploading, the bot checks the channel / account for the same
title / caption.

## 🔑 Secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret | For |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | writing scripts (`claude setup-token`) |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | free AI pictures (Cloudflare) |
| `IG_USER_ID`, `IG_PAGE_TOKEN` | Instagram posting |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube upload + stats |

---

## 🆘 When a run fails

GitHub emails you. Open **Actions → the red ❌ run** → read the last lines.

| Message | Fix |
|---|---|
| `Missing secret/env var: X` | add secret X, spelled exactly |
| `Cannot call API for app … on behalf of user` | do **Fix Instagram** above |
| `Cloudflare rejected the token` | re-make the Workers AI token → `CF_API_TOKEN` |
| `Claude Code call failed` | run `claude setup-token` again → update secret |
| `No video ready` | the Make run failed — fix it, then run Make video |
| `Could not push bot state` | Settings → Actions → General → Workflow permissions → **Read and write**, then re-run |
| `YouTube API uploads are staying private` (issue) | audit not approved yet → set `youtube_mode: manual` |
| `Only N/M pictures worked` | Cloudflare had a bad day; re-run Make video |
| push/permission errors | Settings → Actions → General → Workflow permissions → **Read and write** |

---

## 💸 Why it stays free

GitHub Actions (~300-400 of 2,000 free min/month) · Cloudflare AI (roughly 2,000 of 10,000 free neurons/day per video — more beats than before) · Kokoro voice + captions + music + editing (run on GitHub's machine) · Claude (your subscription) · Instagram + YouTube APIs (free). **₹0/month.**

**Language plan (`allocation.mode: weekly`):** English every day, plus exactly one Hindi video per
Mon-Sun week (made from Wednesday on). Change `weekly_quota` or set `mode: adaptive` to go back to
the split learned from views.

## Video renderer (toon2d 2D cartoon) and voice (edge-tts)

**toon2d (default for explainer and story videos).** A flat 2D ink-on-paper cartoon engine
(`toon2d/`, adapted from ReachMora 2D Long-Form, credit kept in `toon2d/CREDITS.md`). Claude Sonnet writes one
`story.json` storyboard per video (shot kinds like closeup, wide, walk, counter, chart, table, versus, map,
polaroid ending); it never writes drawing code, so a video costs one short Claude call. The engine checks the
storyboard (`plan`), Claude gets one repair round, and an automatic storyboard is the last fallback. Shorts are
vertical 9:16 with burned-in word captions and word-timed mouths. Renders take ~2-4 min per Short on the runner.
Settings: `toon2d:` in `config.yaml`. Look at shots by hand: `cd toon2d && RM_ASPECT=9:16 python -m engine stills <folder>`.

**Weekly long video (English, 16:9, YouTube only).** Sundays (`Long video (weekly)` workflow): the week's best
English Short (by analytics) is expanded by Opus into a researched ~5-minute script (`longform:` in
`config.yaml`), voiced, storyboarded and rendered by toon2d, then uploaded as `privacy: private` until you
switch it to `public`. Manual test: run the workflow with `test` ticked (no Claude, no upload, video as artifact).

**Bespoke Remotion scenes (optional, per theme with `engine: remotion`).** For every video, Claude Opus writes new
animation code for each scene with the channel's design kit (`remotion/src/kit`: the mascot with real
lip-sync and gestures, props, 1,500+ icons, arrows, meters, charts, counters, comparisons), renders a
contact sheet of its own frames, looks at it and fixes problems (2 rounds). The bot then checks every
scene (allowed imports only, no random/timers, typecheck, a crash-test render). Any scene that fails
uses the cartoon template, so a video always ships. This takes ~10-25 min per video on the runner.
Model: `claude: model: opus` in `config.yaml` (Sonnet only as automatic fallback).

**Dev tools installed in the repo** (for working on the bot with Claude Code on your PC):
graphify (`uv tool install graphifyy`, then `graphify update .` builds the code graph; hooks in
`.claude/settings.json` fail open in CI), ponytail skills (for the full plugin with hooks run
`/plugin marketplace add DietrichGebert/ponytail` and `/plugin install ponytail@ponytail` in Claude Code),
claude-motion review/taste skills (`cm-*`), and `tools/validate_skills.sh` (agentskills spec check).

- `engine: remotion` (per theme, or `render.engine`) draws videos with Remotion (the `remotion/` folder):
  camera moves, transitions, word-pop captions, stickers. `ffmpeg` switches back to the old renderer.
- Explainer videos use the `cartoon` style: animated, drawn fully in code (no AI pictures, so no
  Cloudflare credits and no "output flagged" refusals). Story videos still use AI pictures with camera
  moves. Switch per theme with `render_style` (cartoon | explainer | blocky).
- The Roblox-style theme is drawn as a 3D blocky toy world in code (original characters, no game branding).
- `voice.engine: edge` uses Microsoft's free edge-tts voices (Hindi: Madhur or Swara) with real
  per-word timing for captions. If edge-tts fails, that video uses Kokoro automatically.
  edge-tts is an unofficial use of a Microsoft service, so it can stop working without warning.
- Test-mode runs use Kokoro only (no internet voices).
