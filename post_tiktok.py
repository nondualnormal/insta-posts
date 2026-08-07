#!/usr/bin/env python3
"""Taeglicher TikTok-Post (Europe/Berlin): an Reel-Tagen wird das Tagesvideo zusaetzlich
zu TikTok hochgeladen (Content Posting API, Direct Post, PULL_FROM_URL).
env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN, RAW_BASE,
     TIKTOK_PRIVACY (optional, Default SELF_ONLY solange App-Audit aussteht), FORCE (optional).
Fehlen die TikTok-Secrets, wird sauber uebersprungen (Exit 0).
HINWEIS: Vor bestandenem App-Audit erlaubt TikTok nur private Posts (SELF_ONLY).
Nach dem Audit TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE als Repo-Variable setzen."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"


def post(url, data, headers):
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"TikTok-API-Fehler {e.code}: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)


def main():
    ck = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    cs = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    rt = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
    if not (ck and cs and rt):
        print("TikTok-Secrets fehlen - TikTok-Post uebersprungen.")
        return
    raw_base = os.environ["RAW_BASE"].rstrip("/")
    privacy = os.environ.get("TIKTOK_PRIVACY", "").strip() or "SELF_ONLY"
    force = os.environ.get("FORCE", "") == "true"

    now = datetime.now(ZoneInfo("Europe/Berlin"))
    today = now.strftime("%Y-%m-%d")
    if not force and now.hour < 7:
        print(f"{now}: vor 07:00 lokal - kein TikTok-Post in diesem Lauf.")
        return

    done = set()
    if os.path.exists("tiktoked.log"):
        with open("tiktoked.log") as f:
            done = {line.split()[0] for line in f if line.strip()}
    if today in done:
        print(f"{today}: TikTok bereits gepostet - nichts zu tun.")
        return

    reel = sorted(d for d in (os.listdir("reels") if os.path.isdir("reels") else [])
                  if d.startswith(today))
    if not reel:
        print(f"{today}: kein Reel-Tag - kein TikTok-Post.")
        return
    folder = reel[0]
    with open(f"reels/{folder}/caption.txt", encoding="utf-8") as f:
        caption = f.read().strip()
    video_url = f"{raw_base}/reels/{urllib.parse.quote(folder)}/reel.mp4"

    # 1) Access-Token aus Refresh-Token
    tok = post(TOKEN_URL,
               urllib.parse.urlencode({"client_key": ck, "client_secret": cs,
                                       "grant_type": "refresh_token",
                                       "refresh_token": rt}).encode(),
               {"Content-Type": "application/x-www-form-urlencoded"})
    access = tok.get("access_token")
    if not access:
        print(f"Kein Access-Token erhalten: {tok}", file=sys.stderr)
        raise SystemExit(1)
    if tok.get("refresh_token") and tok["refresh_token"] != rt:
        print("HINWEIS: TikTok hat einen NEUEN Refresh-Token ausgegeben - "
              "Secret TIKTOK_REFRESH_TOKEN muss aktualisiert werden!")

    # 2) Direct Post per PULL_FROM_URL
    payload = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    resp = post(INIT_URL, json.dumps(payload).encode(),
                {"Content-Type": "application/json; charset=UTF-8",
                 "Authorization": f"Bearer {access}"})
    if resp.get("error", {}).get("code") not in (None, "", "ok"):
        print(f"TikTok-Fehler: {resp['error']}", file=sys.stderr)
        raise SystemExit(1)
    publish_id = resp.get("data", {}).get("publish_id", "?")
    print(f"TikTok-Post angestossen (privacy={privacy}): publish_id={publish_id}")
    with open("tiktoked.log", "a", encoding="utf-8") as f:
        f.write(f"{today} {folder} [{privacy}] {publish_id}\n")


if __name__ == "__main__":
    main()
