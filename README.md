# 🦴 Shorts Bot — free daily explainer videos, on autopilot

Every day, in the cloud (your PC and phone can be off):

| Time (India) | What happens |
|---|---|
| **~4:00 AM** | Claude checks yesterday's stats → picks a topic → writes + fact-checks a script → free AI pictures → voice → captions → music + sound effects → finished 9:16 video |
| **~7:00 PM** | Video posts to **Instagram Reels** by itself. For **YouTube**, you get a phone notification with the file + title ready (1 minute), until Google approves full auto. |
| **Sundays** | Claude rewrites its own "what works" playbook from real numbers |

**Cost: ₹0.** Uses your Claude subscription + free tiers only (GitHub Actions, Cloudflare AI, Meta API, YouTube API). Higgsfield plugs back in later with one line.

---

## STEP 1 — Put this folder on GitHub (5 min)

1. Go to **github.com/new** → name: `shorts-bot` → choose **Private** → **Create repository**.
2. On your PC, in this folder, run:
   ```
   git init && git add . && git commit -m "shorts bot"
   git branch -M main
   git remote add origin https://github.com/YOUR-NAME/shorts-bot.git
   git push -u origin main
   ```

## STEP 2 — Test it right now (no keys needed)

1. In your repo click **Actions** → left side **Make video** → **Run workflow** → keep ✅ *Test mode* → **Run workflow**.
2. Wait ~5 min until it turns green ✅. Click the run → scroll down → **Artifacts → test-video** → download → watch.
   (Test mode uses plain colour cards instead of AI pictures — it proves voice, captions, music and editing work.)

## STEP 3 — Add your keys (GitHub → **Settings → Secrets and variables → Actions → New repository secret**)

Each key below = one secret. Name must match exactly.

### 🧠 Claude — `CLAUDE_CODE_OAUTH_TOKEN`
1. On your PC: `npm install -g @anthropic-ai/claude-code`
2. Run: `claude setup-token` → log in with your Claude account in the browser.
3. Copy the long token it prints → save as secret **CLAUDE_CODE_OAUTH_TOKEN**.

### 🎨 Cloudflare (free AI pictures) — `CF_ACCOUNT_ID`, `CF_API_TOKEN`
1. **dash.cloudflare.com** → sign up free (no card).
2. **Account ID**: on the dashboard home, click the ⋯ next to your account name → **Copy account ID** → secret **CF_ACCOUNT_ID**.
3. **Token**: top-right profile icon → **My Profile → API Tokens → Create Token** → pick the **Workers AI** template → **Continue → Create Token** → copy → secret **CF_API_TOKEN**.

### 📸 Instagram — `IG_PAGE_TOKEN`, `IG_USER_ID` (≈15 min, one time, all clicks)
Your Instagram must be **Business/Creator** ✅ and linked to a **Facebook Page**:
- Make a free Facebook Page (facebook.com/pages/create), then Instagram app → **Edit profile → Page → Connect** your Page.

Then:
1. **developers.facebook.com** → **My Apps → Create App** → use case **Other** → type **Business** → name it `shorts-bot` → Create.
2. Top menu **Tools → Graph API Explorer**. On the right:
   - **Meta App**: pick `shorts-bot`
   - **User or Page**: *Get User Access Token*
   - **Permissions** → add: `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`, `business_management`
   - **Generate Access Token** → log in → tick your Page **and** your Instagram → Allow.
3. Copy that token → **Tools → Access Token Debugger** → paste → **Debug** → bottom: **Extend Access Token** → copy the new long token.
4. Back in **Graph API Explorer**: paste the long token in the *Access Token* box. In the query box type `me/accounts` → **Submit**.
   - Copy the `access_token` shown under your Page → secret **IG_PAGE_TOKEN** (this one never expires).
   - Note the Page `id`.
5. Query box: `PAGE_ID?fields=instagram_business_account` (use your Page id) → **Submit** → copy the `id` inside → secret **IG_USER_ID**.

### ▶️ YouTube — nothing needed today
YouTube runs in **manual mode**: each evening you get a GitHub notification (**📱 Post to YouTube**) with the video link and a ready-to-paste title. Install the **GitHub mobile app** and turn on notifications so it pings your phone.

**To make YouTube fully automatic later:**
1. Submit the YouTube API audit (text from our chat) and wait for approval.
2. Google Cloud Console → new project → enable **YouTube Data API v3** + **YouTube Analytics API** → **OAuth consent screen** (External, set to **In production**) → **Credentials → Create OAuth client ID → Desktop app** → download the JSON.
3. On your PC: `pip install google-auth-oauthlib` then `python tools/youtube_auth.py client_secret.json` → it prints 3 values → secrets **YT_CLIENT_ID**, **YT_CLIENT_SECRET**, **YT_REFRESH_TOKEN**.
   (Even before approval, these 3 secrets let the bot read your YouTube stats.)
4. In `config.yaml` change `youtube_mode: manual` → `youtube_mode: api`.

## STEP 4 — Go live

**Actions → Make video → Run workflow → untick Test mode → Run.**
First run makes **2 videos** (1 for today + 1 spare). Find them under **Releases** on your repo page. From then on everything runs by itself every day.

Want it to post right now instead of 7 PM? **Actions → Post video → Run workflow.**

---

## Everyday controls (all in `config.yaml`, edit on github.com with the ✏️ pencil)

| Want to… | Change |
|---|---|
| ⏸ Stop everything | `paused: true` |
| Change topics | `channel → niche` |
| Different narrator | `voice → voice` (`am_adam`, `am_onyx`, `bm_george`…) and `speed` |
| Bigger/smaller captions | `captions → font_size` |
| Your own music | drop royalty-free .mp3 files into `assets/music/` |
| Post time | edit the `cron:` line in `.github/workflows/post-video.yml` (it's in UTC: India time minus 5:30) |

## 🔌 Swap Higgsfield back in

`config.yaml → visuals → provider`:
- `cloudflare_flux` — free AI pictures + camera motion (now)
- `higgsfield_clips` — real Higgsfield motion clips, our voice/captions/sound
- `higgsfield_full` — Higgsfield makes the whole video

Setup steps + copy-paste prompt: **tools/higgsfield_routine_prompt.md**.

## 💸 Why it stays free

| Service | Free limit | Bot uses |
|---|---|---|
| GitHub Actions (private repo) | 2,000 min/month | ~300 min/month |
| Cloudflare Workers AI | ~100 pictures/day | ~8/day |
| Claude | your subscription | 1 short run/day |
| Kokoro voice, captions, music, editing | runs on GitHub's machine | free |
| Instagram + YouTube APIs | free | 1 post/day |

## 🆘 If something breaks

GitHub emails you when a run fails. Open **Actions** → the red ❌ run → read the last lines. Common ones:

| Message | Fix |
|---|---|
| `Missing secret/env var: X` | Add secret X (Step 3), name spelled exactly |
| `Cloudflare rejected the token` | Re-create the Workers AI token |
| `Claude Code call failed` | Run `claude setup-token` again, replace the secret |
| `Instagram … failed` | Re-do Instagram steps 2–5 (permissions or Page link missing) |
| `No video ready` | The 4 AM run failed — fix it, then run **Make video** manually |
| Push/permission errors | Settings → Actions → General → Workflow permissions → **Read and write** |
