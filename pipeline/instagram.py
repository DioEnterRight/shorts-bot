"""Instagram Reels via Meta's official API (Facebook Page route, free).

Needs two GitHub secrets:
  IG_USER_ID     your Instagram professional account ID
  IG_PAGE_TOKEN  long-lived Facebook Page access token (does not expire)
"""
import os
import time

import requests

from .common import env, log

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


def publish(video_path, caption):
    ig_id = env("IG_USER_ID", required=True)
    token = env("IG_PAGE_TOKEN", required=True)

    # 1) create an upload container
    params = {"media_type": "REELS", "upload_type": "resumable", "caption": caption[:2150],
              "share_to_feed": "true", "is_ai_generated": "true", "access_token": token}
    r = requests.post(f"{GRAPH}/{ig_id}/media", data=params, timeout=60)
    if r.status_code >= 400 and "is_ai_generated" in r.text:
        params.pop("is_ai_generated")
        r = requests.post(f"{GRAPH}/{ig_id}/media", data=params, timeout=60)
    container = _check(r, "create container")["id"]
    log(f"Instagram container {container}")

    # 2) upload the file straight from the runner (no public hosting needed)
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{VER}/{container}",
                          headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
                          data=f, timeout=600)
    up = _check(r, "upload")
    if not up.get("success", True):
        raise RuntimeError(f"Instagram upload failed: {up}")

    # 3) wait for Instagram to process it
    for _ in range(40):
        time.sleep(15)
        st = _check(requests.get(f"{GRAPH}/{container}",
                                 params={"fields": "status_code,status", "access_token": token}, timeout=60), "status")
        code = st.get("status_code")
        log(f"Instagram processing: {code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing error: {st}")
    else:
        raise RuntimeError("Instagram processing timed out")

    # 4) publish
    media_id = _check(requests.post(f"{GRAPH}/{ig_id}/media_publish",
                                    data={"creation_id": container, "access_token": token}, timeout=60),
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
