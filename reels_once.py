#!/usr/bin/env python3
import os, urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
import publish as P

FOLDERS = ["2026-08-05_breath-stillness", "2026-08-05_stop-searching-pastell"]

token = os.environ["IG_TOKEN"].strip()
ig_id = os.environ["IG_USER_ID"].strip()
raw_base = os.environ["RAW_BASE"].rstrip("/")
today = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
for folder in FOLDERS:
    with open(f"reels/{folder}/caption.txt", encoding="utf-8") as f:
        caption = f.read().strip()
    url = f"{raw_base}/reels/{urllib.parse.quote(folder)}/reel.mp4"
    print(f"Poste REEL {folder} ...")
    mid = P.publish_reel(ig_id, token, url, caption)
    info = P.call(f"{P.API}/{mid}", {"fields": "permalink", "access_token": token})
    print(" ->", info.get("permalink", "?"))
    with open("posted.log", "a", encoding="utf-8") as f:
        f.write(f"{today} {folder} [REEL-TEST] {info.get('permalink','?')}\n")
    os.makedirs("published", exist_ok=True)
    os.rename(f"reels/{folder}", f"published/{folder}")
print("fertig")
