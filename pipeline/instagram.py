"""Instagram Reels via Meta's official API (Facebook Page route, free).

Needs two GitHub secrets:
  IG_USER_ID     your Instagram professional account ID
  IG_PAGE_TOKEN  long-lived Facebook Page access token (does not expire)
"""
import os
import time

import requests

from .common import env, log, norm_text, run

VER = "v26.0"
GRAPH = f"https://graph.facebook.com/{VER}"


def _check(r, what):
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}
    if r.status_code >= 400 or "error" in data:
        msg = str(data)
        hint = ""
        if "Cannot call API for app" in msg or "on behalf of user" in msg:
            hint = ("\nHINT: Your Meta app can't act for your account yet. Fix (one time):\n"
                    "  1. developers.facebook.com -> your app -> top bar: switch App Mode to LIVE\n"
                    "     (needs the Privacy Policy URL filled in under App settings -> Basic -> use your policy page).\n"
                    "  2. App roles -> Roles: make sure your Facebook account is listed (Administrator).\n"
                    "  3. Re-generate IG_PAGE_TOKEN (Graph API Explorer -> me/accounts) and update the secret.")
        elif "does not exist" in msg or "nonexisting field" in msg or "Unsupported" in msg:
            hint = "\nHINT: Check IG_USER_ID is your Instagram account id (from PAGE_ID?fields=instagram_business_account)."
        elif "expired" in msg or "session has been invalidated" in msg or r.status_code == 190:
            hint = "\nHINT: IG_PAGE_TOKEN expired. Re-make a long-lived token and update the secret."
        raise RuntimeError(f"Instagram {what} failed ({r.status_code}): {msg[:500]}{hint}")
    return data


def _ig_copy(video_path):
    """Re-encode to the exact format Instagram likes (1080x1920, 30fps, H.264 High, AAC 48k, faststart).
    Rules out 'bad video file' as the reason for ProcessingFailedError."""
    out = video_path.with_name("ig.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", video_path,
         "-vf", "scale=1080:1920:flags=lanczos,setsar=1", "-r", "30",
         "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-preset", "veryfast", "-crf", "20",
         "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p", "-g", "60",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", out])
    log(f"Instagram copy: {out.stat().st_size / 1e6:.1f} MB")
    return out


def _container(ig_id, token, caption, extra, ai_label=True):
    # is_ai_generated: official self-disclosure flag of the Content Publishing API (changelog 22 Jun 2026)
    params = {"media_type": "REELS", "caption": caption[:2150], "share_to_feed": "true",
              "access_token": token, **extra}
    if ai_label:
        params["is_ai_generated"] = "true"
    r = requests.post(f"{GRAPH}/{ig_id}/media", data=params, timeout=60)
    cid = _check(r, "create container")["id"]
    log(f"Instagram container {cid}")
    return cid


def _upload_file(ig_id, token, caption, path, ai_label=True):
    """Way 1: push the file straight from the runner (resumable upload)."""
    cid = _container(ig_id, token, caption, {"upload_type": "resumable"}, ai_label)
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{VER}/{cid}",
                          headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
                                   "Content-Type": "application/octet-stream"},
                          data=f.read(), timeout=600)
    log(f"Instagram upload reply: HTTP {r.status_code} {r.text[:300]}")
    up = _check(r, "upload")
    if not up.get("success", True):
        raise RuntimeError(f"Instagram upload failed: {up}")
    return cid


def _upload_url(ig_id, token, caption, url, ai_label=True):
    """Way 2: Instagram downloads the video itself from a public link."""
    return _container(ig_id, token, caption, {"video_url": url}, ai_label)


def _delete_media_branch():
    """The 'media' branch exists only so Instagram can fetch the file. Remove it once posted."""
    repo, tok = env("GITHUB_REPOSITORY"), env("GH_TOKEN")
    if not repo or not tok:
        return
    res = run(["gh", "api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/media"], check=False, capture=True)
    log("Temporary media branch removed" if res.returncode == 0 else "Temporary media branch not removed", "INFO")


def _branch_public_url(path):
    """Push the video to a throwaway 'media' branch of THIS repo and return its raw.githubusercontent.com link
    (a direct link, no redirects). Instagram can fetch it only if the repo is PUBLIC."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path
    repo = env("GITHUB_REPOSITORY")
    tok = env("GH_TOKEN")
    if not repo or not tok:
        raise RuntimeError("GITHUB_REPOSITORY / GH_TOKEN missing (only works inside GitHub Actions)")
    name = f"reel-{int(time.time())}.mp4"
    d = Path(tempfile.mkdtemp())
    shutil.copy(path, d / name)

    def git(*a):
        subprocess.run(["git", "-c", "user.name=shorts-bot", "-c", "user.email=shorts-bot@users.noreply.github.com",
                        *a], cwd=d, check=True, capture_output=True, text=True)
    try:
        git("init", "-q", "-b", "media")
        git("add", name)
        git("commit", "-q", "-m", "temporary video for Instagram")
        git("push", "-q", "--force", f"https://x-access-token:{tok}@github.com/{repo}.git", "media:media")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"could not push media branch: {(e.stderr or '').replace(tok, '***')[-300:]}")
    url = f"https://raw.githubusercontent.com/{repo}/media/{name}"
    code = None
    for _ in range(8):
        code = requests.head(url, timeout=30, allow_redirects=False).status_code
        if code == 200:
            log(f"Instagram media link ready: {url}")
            return url
        time.sleep(5)
    raise RuntimeError(f"media link answers HTTP {code}. If 404: your repo is PRIVATE - make it Public "
                       "(Settings -> General -> bottom -> Change visibility) so Instagram can download the video.")


def _temp_public_url(path):
    """Park the video on a free temporary public host (auto-deletes) so Instagram can fetch it.
    Needed because Meta's resumable upload only works for 'Facebook Login for Business' apps."""
    with open(path, "rb") as f:
        r = requests.post("https://litterbox.catbox.moe/resources/internals/api.php",
                          data={"reqtype": "fileupload", "time": "12h"},
                          files={"fileToUpload": ("reel.mp4", f, "video/mp4")}, timeout=300)
    url = r.text.strip()
    if r.status_code != 200 or not url.startswith("https://"):
        raise RuntimeError(f"temporary host refused the file: HTTP {r.status_code} {url[:200]}")
    log(f"Instagram temp link: {url}")
    return url


def notify_manual(meta, tag):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    link = f"https://github.com/{repo}/releases/tag/{tag}"
    body = f"""Instagram auto-post failed, so post this one by hand (about 1 minute):

1. Open **{link}** and download **final.mp4** to your phone
2. Instagram app -> **+** -> **Reel** -> pick the file
3. Paste the caption below
4. Turn on **AI label** if shown (the bot's setting for this video: see config `disclosure`), then Share

**Caption**
```
{meta.get('caption', '')}
```
"""
    run(["gh", "issue", "create", "--title", f"📱 Post to Instagram: {meta['title'][:60]}", "--body", body],
        check=False)


def _wait(token, cid):
    for _ in range(40):
        time.sleep(15)
        st = _check(requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": token},
                                 timeout=60), "status")
        code = st.get("status_code")
        log(f"Instagram processing: {code} {st.get('status', '')}")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing error: {st}")
    raise RuntimeError("Instagram processing timed out")


def find_existing(caption):
    """Guard against double posts when saved state was lost: is this caption already among recent posts?"""
    try:
        ig_id, token = env("IG_USER_ID", required=True), env("IG_PAGE_TOKEN", required=True)
        r = requests.get(f"{GRAPH}/{ig_id}/media", params={"fields": "id,caption", "limit": 10,
                                                           "access_token": token}, timeout=60)
        target = norm_text(caption)[:120]
        for m in _check(r, "recent media").get("data", []):
            if target and norm_text(m.get("caption", ""))[:120] == target:
                return m["id"]
    except Exception as e:  # noqa: BLE001  (a failed check must not block posting)
        log(f"Instagram duplicate check skipped: {e}", "WARN")
    return None


def publish(video_path, caption, video_url=None, ai_label=True):
    ig_id = env("IG_USER_ID", required=True)
    token = env("IG_PAGE_TOKEN", required=True)
    try:
        ig_file = _ig_copy(video_path)
    except Exception as e:  # noqa: BLE001  (no ffmpeg etc. -> just use the original file)
        log(f"Instagram re-encode skipped: {e}")
        ig_file = video_path

    attempts = []
    # Way A: video parked on a 'media' branch of this repo (direct link; repo must be PUBLIC)
    attempts.append(("repo media link", lambda: _upload_url(ig_id, token, caption, _branch_public_url(ig_file), ai_label)))
    # Way A2: temporary public host
    attempts.append(("temporary public link",
                     lambda: _upload_url(ig_id, token, caption, _temp_public_url(ig_file), ai_label)))
    # Way B: the GitHub release link (works only when the repo is public)
    if video_url:
        attempts.append(("GitHub release link", lambda: _upload_url(ig_id, token, caption, video_url, ai_label)))
    # Way C: direct file push (only works for 'Facebook Login for Business' apps)
    attempts.append(("direct file upload", lambda: _upload_file(ig_id, token, caption, ig_file, ai_label)))

    cid, errs = None, []
    for name, fn in attempts:
        try:
            log(f"Instagram: trying {name}")
            c = fn()
            _wait(token, c)
            cid = c
            break
        except Exception as e:  # noqa: BLE001
            errs.append(f"{name}: {e}")
            log(f"Instagram {name} failed: {str(e)[:400]}")
            time.sleep(20)
    _delete_media_branch()
    if not cid:
        raise RuntimeError("all Instagram ways failed ->\n  " + "\n  ".join(errs))

    media_id = _check(requests.post(f"{GRAPH}/{ig_id}/media_publish",
                                    data={"creation_id": cid, "access_token": token}, timeout=60),
                      "publish")["id"]
    link = ""
    try:
        link = _check(requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": token},
                                   timeout=60), "permalink").get("permalink", "")
    except RuntimeError:
        pass
    log(f"Instagram published: {media_id} {link}")
    return media_id, link


METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "ig_reels_avg_watch_time"]


def insights(media_id):
    token = env("IG_PAGE_TOKEN", required=True)

    def ask(metrics):
        r = requests.get(f"{GRAPH}/{media_id}/insights",
                         params={"metric": ",".join(metrics), "access_token": token}, timeout=60)
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "insights error"))
        return {d["name"]: (d.get("values") or [{}])[0].get("value", 0) for d in data.get("data", [])}

    try:
        raw = ask(METRICS)
    except RuntimeError:
        raw = {}
        for m in METRICS:  # some metrics may be unavailable; ask one by one
            try:
                raw.update(ask([m]))
            except RuntimeError:
                pass
    return {"ig_views": raw.get("views", 0), "ig_reach": raw.get("reach", 0), "ig_likes": raw.get("likes", 0),
            "ig_comments": raw.get("comments", 0), "ig_shares": raw.get("shares", 0),
            "ig_saves": raw.get("saved", 0), "ig_avg_watch_ms": raw.get("ig_reels_avg_watch_time", 0)}
