#!/usr/bin/env python3
"""Instagram-Post (Europe/Berlin), bis zu 2x taeglich: Video (reels/<datum>*_*) hat Vorrang,
sonst Bild (posts/<datum>_*). Zusaetzlich Story mit demselben Medium.
env: IG_TOKEN, IG_USER_ID, RAW_BASE, FORCE, EVENING_HOUR (Default 19)."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://graph.instagram.com/v23.0"


def call(url, params=None, method="GET"):
    if params:
        data = urllib.parse.urlencode(params)
        if method == "POST":
            req = urllib.request.Request(url, data=data.encode(), method="POST")
        else:
            req = urllib.request.Request(url + "?" + data)
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API-Fehler {e.code}: {body}", file=sys.stderr)
        raise SystemExit(1)


def wait_ready(creation_id, token, tries=60, delay=5):
    import time as _t
    for _ in range(tries):
        st = call(f"{API}/{creation_id}", {"fields": "status_code", "access_token": token})
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            print(f"Container-Fehler: {st}", file=sys.stderr)
            raise SystemExit(1)
        _t.sleep(delay)
    print("Container nicht rechtzeitig fertig.", file=sys.stderr)
    raise SystemExit(1)


def publish_image(ig_id, token, image_url, caption):
    c = call(f"{API}/{ig_id}/media", {"image_url": image_url, "caption": caption,
                                      "access_token": token}, method="POST")
    wait_ready(c["id"], token)
    return call(f"{API}/{ig_id}/media_publish", {"creation_id": c["id"],
                                                 "access_token": token}, method="POST")["id"]


def publish_reel(ig_id, token, video_url, caption):
    c = call(f"{API}/{ig_id}/media", {"media_type": "REELS", "video_url": video_url,
                                      "caption": caption, "share_to_feed": "true",
                                      "thumb_offset": "7000",
                                      "access_token": token}, method="POST")
    wait_ready(c["id"], token)
    return call(f"{API}/{ig_id}/media_publish", {"creation_id": c["id"],
                                                 "access_token": token}, method="POST")["id"]


def publish_story(ig_id, token, media_url, is_video):
    params = {"media_type": "STORIES", "access_token": token}
    if is_video:
        params["video_url"] = media_url
    else:
        params["image_url"] = media_url
    c = call(f"{API}/{ig_id}/media", params, method="POST")
    wait_ready(c["id"], token)
    call(f"{API}/{ig_id}/media_publish", {"creation_id": c["id"],
                                          "access_token": token}, method="POST")


def main():
    token = os.environ["IG_TOKEN"].strip()
    ig_id = os.environ["IG_USER_ID"].strip()
    raw_base = os.environ["RAW_BASE"].rstrip("/")
    force = os.environ.get("FORCE", "") == "true"

    now = datetime.now(ZoneInfo("Europe/Berlin"))
    today = now.strftime("%Y-%m-%d")
    evening = int(os.environ.get("EVENING_HOUR", "19"))

    if not force and now.hour < 7:
        print(f"{now}: vor 07:00 lokal - kein Posting in diesem Lauf.")
        return

    # Idempotenz je ORDNER (es koennen mehrere Posts pro Tag sein)
    posted_folders, posted_today = set(), 0
    if os.path.exists("posted.log"):
        with open("posted.log") as f:
            for line in f:
                p = line.split()
                if len(p) >= 2:
                    posted_folders.add(p[1])
                    if p[0] == today:
                        posted_today += 1

    # Slot-Regel: hoechstens 1 Post vor dem Abend, hoechstens 2 am Tag
    limit = 2 if (force or now.hour >= evening) else 1
    if posted_today >= limit:
        print(f"{today}: schon {posted_today} Post(s) heute (Limit {limit}) - nichts zu tun.")
        return

    reel_folders = sorted(d for d in (os.listdir("reels") if os.path.isdir("reels") else [])
                          if d.startswith(today) and d not in posted_folders)
    img_folders = sorted(d for d in os.listdir("posts")
                         if d.startswith(today) and d not in posted_folders)

    if reel_folders:
        folder = reel_folders[0]
        with open(f"reels/{folder}/caption.txt", encoding="utf-8") as f:
            caption = f.read().strip()
        url = f"{raw_base}/reels/{urllib.parse.quote(folder)}/reel.mp4"
        print(f"Poste REEL {folder} ...")
        media_id = publish_reel(ig_id, token, url, caption)
        kind = "REEL"
        story_url, story_video = url, True
    elif img_folders:
        folder = img_folders[0]
        with open(f"posts/{folder}/caption.txt", encoding="utf-8") as f:
            caption = f.read().strip()
        url = f"{raw_base}/posts/{urllib.parse.quote(folder)}/post.png"
        print(f"Poste BILD {folder} ...")
        media_id = publish_image(ig_id, token, url, caption)
        kind = "BILD"
        story_url, story_video = url, False
    else:
        print(f"{today}: kein Post-Ordner vorhanden - nichts zu tun.")
        return

    info = call(f"{API}/{media_id}", {"fields": "permalink", "access_token": token})
    permalink = info.get("permalink", "?")
    print(f"Veroeffentlicht ({kind}): {permalink}")

    with open("posted.log", "a", encoding="utf-8") as f:
        f.write(f"{today} {folder} [{kind}] {permalink} {media_id}\n")

    # Story (best effort) - nur beim ersten Post des Tages
    if posted_today > 0:
        print("Zweiter Post des Tages - keine zweite Story.")
        return
    try:
        publish_story(ig_id, token, story_url, story_video)
        print("Story veroeffentlicht.")
    except SystemExit:
        print("Story fehlgeschlagen - Hauptpost war erfolgreich.")


if __name__ == "__main__":
    main()
