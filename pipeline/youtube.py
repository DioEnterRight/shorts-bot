"""YouTube Shorts.

Modes (config.yaml -> publish.youtube_mode):
  manual : you get a GitHub notification with the video file + ready-to-paste title.
           (Use this until Google approves your API audit; API uploads stay locked private before that.)
  api    : uploads automatically. Needs YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN secrets.
  off    : skip.

Stats (views, % watched) work in BOTH modes if the YT_* secrets exist: reading your own
channel's stats is allowed without the audit. Manual uploads are matched by title.
"""
import os
import time

from .common import env, log, norm_text, run


def _creds():
    if not (env("YT_CLIENT_ID") and env("YT_CLIENT_SECRET") and env("YT_REFRESH_TOKEN")):
        return None
    from google.oauth2.credentials import Credentials
    return Credentials(None, refresh_token=env("YT_REFRESH_TOKEN"), token_uri="https://oauth2.googleapis.com/token",
                       client_id=env("YT_CLIENT_ID"), client_secret=env("YT_CLIENT_SECRET"))


def _client():
    from googleapiclient.discovery import build
    creds = _creds()
    if not creds:
        raise RuntimeError("YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN secrets are missing")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def shorts_title(title):
    title = title[:90]
    return title if "#shorts" in title.lower() else f"{title} #shorts"[:100]


def _norm(s):
    return norm_text(s.lower().replace("#shorts", ""))


def recent_uploads(yt, n=50):
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    return yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=n).execute().get("items", [])


def find_existing(title):
    """Guard against double uploads when saved state was lost: is this title already on the channel?"""
    try:
        target = _norm(title)
        for it in recent_uploads(_client(), 15):
            if _norm(it["snippet"]["title"]) == target:
                return it["snippet"]["resourceId"]["videoId"]
    except Exception as e:  # noqa: BLE001  (a failed check must not block posting)
        log(f"YouTube duplicate check skipped: {e}", "WARN")
    return None


def upload(video_path, meta, short=True, privacy="public"):
    """Returns (video_id, privacyStatus). short=False: a normal long video (no #shorts in the title)."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    yt = _client()
    body = {
        "snippet": {"title": shorts_title(meta["title"]) if short else meta["title"][:100],
                    "description": f"{meta['description']}\n\n{' '.join(meta['hashtags'])}",
                    "tags": [h.lstrip("#") for h in meta["hashtags"]], "categoryId": "27",
                    "defaultLanguage": meta.get("language", "en"),
                    "defaultAudioLanguage": meta.get("language", "en")},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": bool(meta.get("synthetic_youtube", True))},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True))
    resp, errors = None, 0
    while resp is None:
        try:
            _, resp = req.next_chunk()
        except HttpError as e:
            if e.resp.status not in (500, 502, 503, 504) or errors >= 4:
                raise
            errors += 1
            wait = 2 ** errors
            log(f"YouTube upload hiccup ({e.resp.status}), retrying in {wait}s", "WARN")
            time.sleep(wait)
    vid = resp["id"]
    privacy = resp.get("status", {}).get("privacyStatus", "unknown")
    log(f"YouTube uploaded: {vid} ({privacy})")
    return vid, privacy


def notify_manual(meta, tag):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    link = f"https://github.com/{repo}/releases/tag/{tag}"
    disclose = "**Yes**" if meta.get("synthetic_youtube", True) else "**No** (stylised animation is exempt)"
    body = f"""Today's Short is ready. Post it on YouTube (about 1 minute):

1. Open **{link}** and download **final.mp4**
2. YouTube app → **+** → **Upload a video** → pick the file
3. Paste the title and description below
4. Under **Altered or synthetic content** choose {disclose}
5. Publish, then close this issue

**Title**
```
{shorts_title(meta['title'])}
```

**Description**
```
{meta['description']}

{' '.join(meta['hashtags'])}
```
"""
    run(["gh", "issue", "create", "--title", f"📱 Post to YouTube: {meta['title'][:60]}", "--body", body])


def stats(videos):
    """Fill yt_* metrics for our videos. Matches by stored id, or by title for manual uploads."""
    if not _creds():
        return {}
    yt = _client()
    by_title = {_norm(i["snippet"]["title"]): i["snippet"]["resourceId"]["videoId"] for i in recent_uploads(yt)}
    for v in videos:
        if not v.get("yt_video_id"):
            vid = by_title.get(_norm(v["title"]))
            if vid:
                v["yt_video_id"] = vid
    ids = [v["yt_video_id"] for v in videos if v.get("yt_video_id")]
    out = {}
    if not ids:
        return out
    for chunk in [ids[i:i + 50] for i in range(0, len(ids), 50)]:
        for it in yt.videos().list(part="statistics,status", id=",".join(chunk)).execute().get("items", []):
            s = it["statistics"]
            out[it["id"]] = {"yt_views": int(s.get("viewCount", 0)), "yt_likes": int(s.get("likeCount", 0)),
                             "yt_comments": int(s.get("commentCount", 0)),
                             "yt_privacy": it.get("status", {}).get("privacyStatus")}
    try:
        import datetime as dt
        from googleapiclient.discovery import build
        ya = build("youtubeAnalytics", "v2", credentials=_creds(), cache_discovery=False)
        rep = ya.reports().query(ids="channel==MINE", startDate="2020-01-01",
                                 endDate=dt.date.today().isoformat(),
                                 metrics="averageViewPercentage,averageViewDuration,subscribersGained",
                                 dimensions="video", filters="video==" + ",".join(ids[:200])).execute()
        for row in rep.get("rows", []):
            out.setdefault(row[0], {}).update({"yt_avg_view_pct": round(row[1], 1),
                                               "yt_avg_view_sec": row[2], "yt_subs_gained": row[3]})
    except Exception as e:  # noqa: BLE001
        log(f"YouTube Analytics skipped: {e}", "WARN")
    return out
