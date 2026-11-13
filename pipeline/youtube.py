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
import re

from .common import env, log, run


def _creds():
    if not (env("YT_CLIENT_ID") and env("YT_CLIENT_SECRET") and env("YT_REFRESH_TOKEN")):
        return None
    from google.oauth2.credentials import Credentials
    return Credentials(None, refresh_token=env("YT_REFRESH_TOKEN"), token_uri="https://oauth2.googleapis.com/token",
                       client_id=env("YT_CLIENT_ID"), client_secret=env("YT_CLIENT_SECRET"))


def upload(video_path, meta):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = _creds()
    if not creds:
        raise RuntimeError("youtube_mode is 'api' but YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN secrets are missing")
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    title = meta["title"][:90]
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"[:100]
    body = {
        "snippet": {"title": title, "description": f"{meta['description']}\n\n{' '.join(meta['hashtags'])}",
                    "tags": [h.lstrip("#") for h in meta["hashtags"]], "categoryId": "27"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    privacy = resp.get("status", {}).get("privacyStatus")
    log(f"YouTube uploaded: {vid} ({privacy})")
    if privacy != "public":
        log("NOTE: YouTube kept it private — your API audit is probably not approved yet. Use youtube_mode: manual.")
    return vid


def notify_manual(meta, tag):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    link = f"https://github.com/{repo}/releases/tag/{tag}"
    title = meta["title"][:90] + " #shorts"
    body = f"""Today's Short is ready. Post it on YouTube (about 1 minute):

1. Open **{link}** and download **final.mp4**
2. YouTube app → **+** → **Upload a video** → pick the file
3. Paste the title and description below
4. Under **Altered or synthetic content** choose **Yes**
5. Publish, then close this issue

**Title**
```
{title}
```

**Description**
```
{meta['description']}

{' '.join(meta['hashtags'])}
```
"""
    run(["gh", "issue", "create", "--title", f"📱 Post to YouTube: {meta['title'][:60]}", "--body", body])


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("#shorts", ""))


def stats(videos):
    """Fill yt_* metrics for our videos. Matches by stored id, or by title for manual uploads."""
    creds = _creds()
    if not creds:
        return {}
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50).execute().get("items", [])
    by_title = {_norm(i["snippet"]["title"]): i["snippet"]["resourceId"]["videoId"] for i in items}
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
        for it in yt.videos().list(part="statistics", id=",".join(chunk)).execute().get("items", []):
            s = it["statistics"]
            out[it["id"]] = {"yt_views": int(s.get("viewCount", 0)), "yt_likes": int(s.get("likeCount", 0)),
                             "yt_comments": int(s.get("commentCount", 0))}
    try:
        import datetime as dt
        ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        rep = ya.reports().query(ids="channel==MINE", startDate="2020-01-01",
                                 endDate=dt.date.today().isoformat(),
                                 metrics="averageViewPercentage,averageViewDuration,subscribersGained",
                                 dimensions="video", filters="video==" + ",".join(ids[:200])).execute()
        for row in rep.get("rows", []):
            out.setdefault(row[0], {}).update({"yt_avg_view_pct": round(row[1], 1),
                                               "yt_avg_view_sec": row[2], "yt_subs_gained": row[3]})
    except Exception as e:  # noqa: BLE001
        log(f"YouTube Analytics skipped: {e}")
    return out
