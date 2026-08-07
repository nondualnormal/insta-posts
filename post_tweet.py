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


def find_quote_for(date_str):
    """Versatz-Algorithmus: X postet das ZITAT (quote.txt) eines aelteren Tages.
    Sucht den Tagesordner in posts/, reels/ und published/; quote.txt bevorzugt,
    caption.txt als Fallback."""
    for base in ("posts", "reels", "published"):
        if not os.path.isdir(base):
            continue
        hits = sorted(d for d in os.listdir(base) if d.startswith(date_str))
        for folder in hits:
            for fname in ("quote.txt", "caption.txt"):
                path = f"{base}/{folder}/{fname}"
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        return folder, f.read().strip()
    return None, None


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

    # Versatz: X bekommt das Zitat von VORGESTERN (T-2) -> nie derselbe Text wie
    # der heutige Instagram-Post. Fallback: heutiges Zitat, wenn T-2 fehlt.
    from datetime import timedelta
    source_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    folder, text = find_quote_for(source_date)
    if not text:
        folder, text = find_quote_for(today)
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
