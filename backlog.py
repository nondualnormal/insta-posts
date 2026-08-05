#!/usr/bin/env python3
"""Einmalig: veroeffentlicht die vier vorgezogenen Posts sofort und archiviert sie."""
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://graph.instagram.com/v23.0"

FOLDERS = [
    "2026-09-01_resistance-ends",
    "2026-09-02_joy-and-sorrow-one",
    "2026-09-03_whole-universe-this-moment",
    "2026-09-04_wanting-what-you-do",
]


def call(url, params, method="POST"):
    data = urllib.parse.urlencode(params)
    if method == "POST":
        req = urllib.request.Request(url, data=data.encode(), method="POST")
    else:
        req = urllib.request.Request(url + "?" + data)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"API-Fehler {e.code}: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)


def main():
    token = os.environ["IG_TOKEN"].strip()
    ig_id = os.environ["IG_USER_ID"].strip()
    raw_base = os.environ["RAW_BASE"].rstrip("/")
    today = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")

    os.makedirs("published", exist_ok=True)
    for folder in FOLDERS:
        if not os.path.isdir(f"posts/{folder}"):
            print(f"{folder}: nicht vorhanden - uebersprungen")
            continue
        with open(f"posts/{folder}/caption.txt", encoding="utf-8") as f:
            caption = f.read().strip()
        image_url = f"{raw_base}/posts/{urllib.parse.quote(folder)}/post.png"
        print(f"Poste {folder} ...")
        c = call(f"{API}/{ig_id}/media", {
            "image_url": image_url, "caption": caption, "access_token": token})
        p = call(f"{API}/{ig_id}/media_publish", {
            "creation_id": c["id"], "access_token": token})
        info = call(f"{API}/{p['id']}", {
            "fields": "permalink", "access_token": token}, method="GET")
        permalink = info.get("permalink", "?")
        print(f"  -> {permalink}")
        with open("posted.log", "a", encoding="utf-8") as f:
            f.write(f"{today} {folder} (vorgezogen) {permalink}\n")
        shutil.move(f"posts/{folder}", f"published/{folder}")
        time.sleep(10)
    print("Backlog fertig.")


if __name__ == "__main__":
    main()
