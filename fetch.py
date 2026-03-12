#!/usr/bin/env python3
"""
OSINT Feed Fetcher
Kör av GitHub Actions var 15:e minut.
Hämtar RSS-flöden och Polymarket-data, sparar som JSON i data/.
"""

import json
import os
import time
import feedparser
import requests
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── RSS-KÄLLOR ──────────────────────────────────────────────────────────────
RSS_SOURCES = [
    # Ukraina / konflikt
    {"name": "ISW",            "category": "UKRAINA",      "severity": "high",
     "url": "https://www.understandingwar.org/rss.xml"},
    {"name": "Kyiv Independent","category": "UKRAINA",     "severity": "high",
     "url": "https://kyivindependent.com/feed/"},
    {"name": "RFE/RL Ukraine", "category": "UKRAINA",      "severity": "med",
     "url": "https://www.rferl.org/api/zpioevpumz"},

    # Mellanöstern
    {"name": "Al-Monitor",     "category": "MELLANÖSTERN", "severity": "med",
     "url": "https://www.al-monitor.com/rss"},
    {"name": "Times of Israel","category": "MELLANÖSTERN", "severity": "med",
     "url": "https://www.timesofisrael.com/feed/"},
    {"name": "Middle East Eye","category": "MELLANÖSTERN", "severity": "med",
     "url": "https://www.middleeasteye.net/rss"},

    # Norden / Sverige
    {"name": "SVT Utrikes",    "category": "NORDEN",       "severity": "low",
     "url": "https://www.svt.se/nyheter/utrikes/rss.xml"},
    {"name": "MSB",            "category": "NORDEN",       "severity": "med",
     "url": "https://www.msb.se/sv/aktuellt/nyheter/rss/"},
    {"name": "Säpo",           "category": "NORDEN",       "severity": "high",
     "url": "https://www.sakerhetspolisen.se/rss"},

    # Kina / Taiwan
    {"name": "SCMP Asia",      "category": "KINA/TAIWAN",  "severity": "med",
     "url": "https://www.scmp.com/rss/91/feed"},
    {"name": "Taiwan News",    "category": "KINA/TAIWAN",  "severity": "med",
     "url": "https://www.taiwannews.com.tw/rss"},

    # Hybridhot / säkerhet
    {"name": "Bellingcat",     "category": "HYBRID",       "severity": "high",
     "url": "https://www.bellingcat.com/feed/"},
    {"name": "ACLED",          "category": "HYBRID",       "severity": "med",
     "url": "https://acleddata.com/feed/"},
    {"name": "Defense One",    "category": "HYBRID",       "severity": "med",
     "url": "https://www.defenseone.com/rss/all/"},
    {"name": "Recorded Future","category": "HYBRID",       "severity": "high",
     "url": "https://www.recordedfuture.com/feed"},

    # Generella säkerhetsnyheter
    {"name": "Reuters World",  "category": "GENERAL",      "severity": "low",
     "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "BBC World",      "category": "GENERAL",      "severity": "low",
     "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "DW World",       "category": "GENERAL",      "severity": "low",
     "url": "https://rss.dw.com/xml/rss-en-world"},
    {"name": "Guardian World", "category": "GENERAL",      "severity": "low",
     "url": "https://www.theguardian.com/world/rss"},
]

# ── POLYMARKET-MARKNADER ────────────────────────────────────────────────────
POLYMARKET_SLUGS = [
    "will-the-us-and-iran-enter-into-a-direct-military-conflict-in-2025",
    "will-russia-and-ukraine-reach-a-ceasefire-agreement-in-2025",
    "will-china-invade-taiwan-in-2025",
    "will-nato-invoke-article-5-in-2025",
    "will-there-be-a-nuclear-attack-in-2025",
    "will-iran-close-the-strait-of-hormuz-in-2025",
    "trump-new-iran-nuclear-deal-2025",
    "will-there-be-a-coup-in-russia-in-2025",
    "will-sweden-be-involved-in-armed-conflict-in-2025",
]

HEADERS = {"User-Agent": "OSINTFeed/1.0 (+https://github.com)"}


def time_ago(dt):
    if not dt:
        return "okänd tid"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = int((now - dt).total_seconds())
    if diff < 60:
        return f"{diff}s sedan"
    if diff < 3600:
        return f"{diff//60}min sedan"
    if diff < 86400:
        return f"{diff//3600}h sedan"
    return f"{diff//86400}d sedan"


def fetch_rss():
    items = []
    stats = {"ok": 0, "fail": 0, "sources": []}

    for src in RSS_SOURCES:
        try:
            resp = requests.get(src["url"], headers=HEADERS, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            count = 0
            for entry in feed.entries[:8]:
                # Parsa datum
                pub = None
                for attr in ("published_parsed", "updated_parsed"):
                    if hasattr(entry, attr) and getattr(entry, attr):
                        pub = datetime(*getattr(entry, attr)[:6], tzinfo=timezone.utc)
                        break

                # Rensa beskrivning
                desc = ""
                if hasattr(entry, "summary"):
                    import re
                    desc = re.sub(r"<[^>]+>", "", entry.summary or "")[:250]

                items.append({
                    "title":    entry.get("title", "(Ingen rubrik)")[:120],
                    "body":     desc,
                    "source":   src["name"],
                    "category": src["category"],
                    "severity": src["severity"],
                    "url":      entry.get("link", ""),
                    "pubDate":  pub.isoformat() if pub else None,
                    "age":      time_ago(pub),
                })
                count += 1

            stats["ok"] += 1
            stats["sources"].append({"name": src["name"], "status": "ok", "count": count})
            print(f"  OK  {src['name']}: {count} poster")

        except Exception as e:
            stats["fail"] += 1
            stats["sources"].append({"name": src["name"], "status": "fail", "error": str(e)[:100]})
            print(f"  FEL {src['name']}: {e}")

    # Sortera nyaste först
    items.sort(key=lambda x: x["pubDate"] or "", reverse=True)

    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "stats":   stats,
        "items":   items[:150],  # Max 150 poster totalt
    }


def fetch_polymarket():
    markets = []
    gamma_base = "https://gamma-api.polymarket.com/markets"

    for slug in POLYMARKET_SLUGS:
        try:
            resp = requests.get(f"{gamma_base}?slug={slug}", headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                raise ValueError("Tom respons")

            m = data[0]
            prob = 0
            try:
                prices = json.loads(m.get("outcomePrices", "[0]"))
                prob = round(float(prices[0]) * 100)
            except Exception:
                pass

            vol = m.get("volume", 0)
            vol_str = f"${vol/1000:.0f}K" if vol > 1000 else f"${vol:.0f}"

            markets.append({
                "question": m.get("question", slug),
                "prob":     prob,
                "volume":   vol_str,
                "url":      f"https://polymarket.com/event/{m.get('slug', slug)}",
                "trend":    "flat",
                "trendPct": 0,
            })
            print(f"  OK  Polymarket: {m.get('question','')[:50]} → {prob}%")
            time.sleep(0.3)

        except Exception as e:
            print(f"  FEL Polymarket {slug}: {e}")

    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "markets": markets,
    }


def main():
    print("=== OSINT Feed Fetcher ===")
    print(f"Startar: {datetime.now(timezone.utc).isoformat()}")

    print("\n[1/2] Hämtar RSS-flöden...")
    rss_data = fetch_rss()
    with open(DATA_DIR / "news.json", "w", encoding="utf-8") as f:
        json.dump(rss_data, f, ensure_ascii=False, indent=2)
    print(f"  → {len(rss_data['items'])} poster sparade till data/news.json")

    print("\n[2/2] Hämtar Polymarket...")
    pm_data = fetch_polymarket()
    with open(DATA_DIR / "polymarket.json", "w", encoding="utf-8") as f:
        json.dump(pm_data, f, ensure_ascii=False, indent=2)
    print(f"  → {len(pm_data['markets'])} marknader sparade till data/polymarket.json")

    print(f"\nKlar: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
