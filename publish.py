#!/usr/bin/env python3
"""Veroeffentlicht den heutigen Post (Europe/Berlin) auf Instagram via Graph API.
Laeuft in GitHub Actions. Erwartet env: IG_TOKEN, IG_USER_ID, RAW_BASE, FORCE (optional).
"""
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
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API-Fehler {e.code}: {body}", file=sys.stderr)
        raise SystemExit(1)


def wait_ready(creation_id, token, tries=20, delay=4):
    """Wartet, bis der Media-Container fertig verarbeitet ist."""
    import time as _t
    for _ in range(tries):
        st = call(f"{API}/{creation_id}", {"fields": "status_code", "access_token": token}, method="GET")
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            print(f"Container-Fehler: {st}", file=sys.stderr)
            raise SystemExit(1)
        _t.sleep(delay)
    print("Container nicht rechtzeitig fertig.", file=sys.stderr)
    raise SystemExit(1)


def main():
    token = os.environ["IG_TOKEN"].strip()
    ig_id = os.environ["IG_USER_ID"].strip()
    raw_base = os.environ["RAW_BASE"].rstrip("/")
    force = os.environ.get("FORCE", "") == "true"

    now = datetime.now(ZoneInfo("Europe/Berlin"))
    today = now.strftime("%Y-%m-%d")

    # Nur um/nach 12:00 lokal posten (zwei Cron-Zeiten decken Sommer-/Winterzeit ab)
    if not force and now.hour < 12:
        print(f"{now}: vor 12:00 lokal - kein Posting in diesem Lauf.")
        return

    posted = set()
    if os.path.exists("posted.log"):
        with open("posted.log") as f:
            posted = {line.split()[0] for line in f if line.strip()}
    if today in posted:
        print(f"{today}: bereits gepostet - nichts zu tun.")
        return

    folders = sorted(d for d in os.listdir("posts") if d.startswith(today))
    if not folders:
        print(f"{today}: kein Post-Ordner vorhanden - nichts zu tun.")
        return
    folder = folders[0]

    with open(f"posts/{folder}/caption.txt", encoding="utf-8") as f:
        caption = f.read().strip()
    image_url = f"{raw_base}/posts/{urllib.parse.quote(folder)}/post.png"
    print(f"Poste {folder} ...")

    c = call(f"{API}/{ig_id}/media", {
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    }, method="POST")
    creation_id = c["id"]
    wait_ready(creation_id, token)

    p = call(f"{API}/{ig_id}/media_publish", {
        "creation_id": creation_id,
        "access_token": token,
    }, method="POST")
    media_id = p["id"]

    info = call(f"{API}/{media_id}", {
        "fields": "permalink",
        "access_token": token,
    })
    permalink = info.get("permalink", "?")
    print(f"Veroeffentlicht: {permalink}")

    with open("posted.log", "a", encoding="utf-8") as f:
        f.write(f"{today} {folder} {permalink}\n")


if __name__ == "__main__":
    main()
