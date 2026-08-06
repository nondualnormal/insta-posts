#!/usr/bin/env python3
"""Taeglicher X/Twitter-Post (Europe/Berlin): postet das Tages-Zitat (caption.txt des
Tagesposts, Reel-Tag hat Vorrang) als reinen Text-Tweet via X API v2 (OAuth 1.0a, ohne SDK).
env: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, FORCE (optional).
Fehlen die X-Secrets, wird sauber uebersprungen (Exit 0)."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TWEET_URL = "https://api.twitter.com/2/tweets"
MAX_LEN = 280

# Dezente, wechselnde Emojis: erst Stichwort-Match im Zitat, sonst Tagesrotation.
EMOJI_KEYWORDS = [
    (("freedom", "free", "peace", "war"), "\U0001F305"),          # 🌅
    (("love", "heart"), "\U0001F90D"),                            # 🤍
    (("silence", "stillness", "quiet", "rest", "calm"), "\U0001F319"),  # 🌙
    (("nature", "alive", "breath", "life"), "\U0001F33F"),        # 🌿
    (("light", "sun", "shine", "bright"), "☀️"),        # ☀️
    (("sacred", "holy", "presence", "wonder"), "✨"),         # ✨
    (("water", "flow", "river", "sea", "ocean"), "\U0001F30A"),   # 🌊
    (("let go", "letting go", "surrender", "release"), "\U0001F343"),  # 🍃
    (("joy", "play", "smile"), "\U0001F338"),                     # 🌸
]
EMOJI_ROTATION = ["\U0001FAB7", "\U0001F33F", "✨", "\U0001F319",
                  "☀️", "\U0001F343", "\U0001F338", "\U0001F4AB"]


def pick_emoji(text, day_of_year):
    low = text.lower()
    for keys, emoji in EMOJI_KEYWORDS:
        if any(k in low for k in keys):
            return emoji
    return EMOJI_ROTATION[day_of_year % len(EMOJI_ROTATION)]


def pct(s):
    return urllib.parse.quote(str(s), safe="~-._")


def oauth1_header(method, url, api_key, api_secret, token, token_secret):
    p = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    base = "&".join([method.upper(), pct(url),
                     pct("&".join(f"{pct(k)}={pct(v)}" for k, v in sorted(p.items())))])
    key = f"{pct(api_secret)}&{pct(token_secret)}"
    sig = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    p["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{pct(k)}="{pct(v)}"' for k, v in sorted(p.items()))


def find_today_caption(today):
    """Gleiche Logik wie publish.py: Reel-Ordner hat Vorrang, sonst Bild-Ordner."""
    reel = sorted(d for d in (os.listdir("reels") if os.path.isdir("reels") else [])
                  if d.startswith(today))
    img = sorted(d for d in (os.listdir("posts") if os.path.isdir("posts") else [])
                 if d.startswith(today))
    if reel:
        folder, path = reel[0], f"reels/{reel[0]}/caption.txt"
    elif img:
        folder, path = img[0], f"posts/{img[0]}/caption.txt"
    else:
        return None, None
    with open(path, encoding="utf-8") as f:
        return folder, f.read().strip()


def main():
    keys = [os.environ.get(k, "").strip() for k in
            ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(keys):
        print("X-Secrets fehlen - Tweet uebersprungen.")
        return
    api_key, api_secret, token, token_secret = keys
    force = os.environ.get("FORCE", "") == "true"

    now = datetime.now(ZoneInfo("Europe/Berlin"))
    today = now.strftime("%Y-%m-%d")
    if not force and now.hour < 9:
        print(f"{now}: vor 09:00 lokal - kein Tweet in diesem Lauf.")
        return

    tweeted = set()
    if os.path.exists("tweeted.log"):
        with open("tweeted.log") as f:
            tweeted = {line.split()[0] for line in f if line.strip()}
    if today in tweeted:
        print(f"{today}: bereits getweetet - nichts zu tun.")
        return

    folder, text = find_today_caption(today)
    if not text:
        print(f"{today}: kein Post-Ordner vorhanden - kein Tweet.")
        return
    emoji = pick_emoji(text, now.timetuple().tm_yday)
    decorated = f"{emoji} {text}"
    if len(decorated) <= MAX_LEN:
        text = decorated
    elif len(text) > MAX_LEN:
        print(f"WARNUNG: Zitat hat {len(text)} Zeichen (> {MAX_LEN}) - Tweet uebersprungen "
              "(nicht kuerzen).", file=sys.stderr)
        return
    # sonst: Zitat passt nur ohne Emoji -> ohne Emoji posten

    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(TWEET_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": oauth1_header("POST", TWEET_URL, api_key, api_secret,
                                       token, token_secret),
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"X-API-Fehler {e.code}: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    tweet_id = resp.get("data", {}).get("id", "?")
    print(f"Tweet veroeffentlicht: https://x.com/i/status/{tweet_id}")
    with open("tweeted.log", "a", encoding="utf-8") as f:
        f.write(f"{today} {folder} https://x.com/i/status/{tweet_id}\n")


if __name__ == "__main__":
    main()
