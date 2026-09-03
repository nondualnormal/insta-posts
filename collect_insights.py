#!/usr/bin/env python3
"""Sammelt taeglich die Instagram-Kennzahlen aller Beitraege in metrics.csv.

Eine Zeile je Beitrag und Abruftag -> Zeitreihe (Reichweite waechst noch tagelang nach).
Laeuft im taeglichen Workflow mit; sammelt hoechstens einmal pro Tag.
env: IG_TOKEN, IG_USER_ID, FORCE (optional)
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://graph.instagram.com/v23.0"
CSV = "metrics.csv"
FIELDS = ["abgerufen", "datum_post", "ordner", "media_id", "typ", "permalink",
          "reach", "views", "likes", "comments", "saved", "shares", "interaktionen"]
# Reihenfolge = Fallback-Kette; nicht jede Metrik gibt es fuer jeden Beitragstyp
METRIC_SETS = [
    "reach,views,likes,comments,saved,shares,total_interactions",
    "reach,likes,comments,saved,shares,total_interactions",
    "reach,likes,comments",
    "reach",
]


def call(path, params, quiet=False):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if not quiet:
            print(f"API-Fehler {e.code} bei {path}: {body[:300]}", file=sys.stderr)
        return {"__error__": body, "__code__": e.code}


def main():
    token = os.environ["IG_TOKEN"].strip()
    ig_id = os.environ["IG_USER_ID"].strip()
    heute = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")

    if os.path.exists(CSV) and os.environ.get("FORCE", "") != "true":
        with open(CSV, encoding="utf-8") as f:
            if any(row.startswith(heute + ",") for row in f):
                print(f"{heute}: Kennzahlen heute schon gesammelt.")
                return

    # Ordner-Zuordnung aus posted.log (Permalink -> Ordnername)
    ordner_von = {}
    if os.path.exists("posted.log"):
        with open("posted.log", encoding="utf-8") as f:
            for line in f:
                p = line.split()
                if len(p) >= 4:
                    ordner_von[p[3]] = p[1]

    medien, after = [], None
    while True:
        params = {"fields": "id,timestamp,permalink,media_type,media_product_type",
                  "limit": "50", "access_token": token}
        if after:
            params["after"] = after
        res = call(f"{ig_id}/media", params)
        if "__error__" in res:
            print("Beitragsliste nicht abrufbar - Abbruch.", file=sys.stderr)
            raise SystemExit(1)
        medien += res.get("data", [])
        after = res.get("paging", {}).get("cursors", {}).get("after")
        if not after or not res.get("paging", {}).get("next"):
            break

    neu = []
    fehlend = 0
    for m in medien:
        werte = {}
        for mset in METRIC_SETS:
            r = call(f"{m['id']}/insights", {"metric": mset, "access_token": token}, quiet=True)
            if "__error__" not in r:
                for eintrag in r.get("data", []):
                    v = eintrag.get("values", [{}])[0].get("value")
                    werte[eintrag["name"]] = v
                break
        else:
            fehlend += 1
        neu.append({
            "abgerufen": heute,
            "datum_post": (m.get("timestamp") or "")[:10],
            "ordner": ordner_von.get(m.get("permalink", ""), ""),
            "media_id": m["id"],
            "typ": m.get("media_product_type") or m.get("media_type", ""),
            "permalink": m.get("permalink", ""),
            "reach": werte.get("reach", ""),
            "views": werte.get("views", ""),
            "likes": werte.get("likes", ""),
            "comments": werte.get("comments", ""),
            "saved": werte.get("saved", ""),
            "shares": werte.get("shares", ""),
            "interaktionen": werte.get("total_interactions", ""),
        })

    neu_datei = not os.path.exists(CSV)
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if neu_datei:
            w.writeheader()
        w.writerows(neu)

    mit_zahlen = sum(1 for r in neu if r["reach"] != "")
    print(f"{heute}: {len(neu)} Beitraege erfasst, davon {mit_zahlen} mit Kennzahlen.")
    if fehlend:
        print(f"Hinweis: {fehlend} Beitraege ohne Insights "
              f"(fehlende Berechtigung oder zu junger Beitrag).")


if __name__ == "__main__":
    main()
