"""ONE-TIME: get your YouTube refresh token (run on your own computer).

  pip install google-auth-oauthlib
  python tools/youtube_auth.py path/to/client_secret.json

A browser opens, you pick your YouTube channel, and it prints three values.
Put them in GitHub secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

if len(sys.argv) != 2:
    sys.exit(__doc__)
flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
info = json.load(open(sys.argv[1]))
info = info.get("installed") or info.get("web")
print("\nAdd these as GitHub secrets:\n")
print("YT_CLIENT_ID     =", info["client_id"])
print("YT_CLIENT_SECRET =", info["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
