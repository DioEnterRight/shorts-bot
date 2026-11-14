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

- **~4 AM IST** — Make video: picks a topic, writes + fact-checks the script, draws the pictures (same character every scene), adds voice, captions, music and sound, saves it to **Releases**.
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
| **Make video** | Makes today's video(s). Options when you click *Run workflow*: **Test mode** (no keys, shows a sample) and **provider** (pick `higgsfield_test` to demo the Higgsfield pipeline). |
| **Post video** | Posts the oldest ready video right now. |
| **Throw away ready videos** | Deletes the waiting videos (use when you don't like them), so the next Make builds fresh ones. |

---

## ⚙️ Settings — `config.yaml` (edit on github.com with the ✏️ pencil)

| Want to… | Change |
|---|---|
| ⏸ Stop everything | `paused: true` |
| Change topics | `channel → niche` |
| Switch visuals (incl. Higgsfield) | `visuals → provider` (see next section) |
| Different narrator | `voice → voice` / `speed` |
| New main character | delete `data/mascot.png` (bot draws a new one) |
| Caption size | `captions → font_size` |
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
| push/permission errors | Settings → Actions → General → Workflow permissions → **Read and write** |

---

## 💸 Why it stays free

GitHub Actions (~300 of 2,000 free min/month) · Cloudflare AI (~1,200 of 10,000 free credits/day) · Kokoro voice + captions + music + editing (run on GitHub's machine) · Claude (your subscription) · Instagram + YouTube APIs (free). **₹0/month.**
