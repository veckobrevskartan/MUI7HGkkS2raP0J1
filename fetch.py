#!/usr/bin/env python3
"""
OSINT Feed Fetcher - kors av GitHub Actions var 15:e minut.
Sparar data/news.json och data/polymarket.json i repots rot.
"""

import json
import re
import time
import feedparser
import requests
from datetime import datetime, timezone
from pathlib import Path

# Alltid relativ till repots rot (scripts/../data/)
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "OSINTFeed/1.0"}

RSS_SOURCES = [
    # Ukraina
    {"name": "ISW",             "category": "UKRAINA",      "severity": "high",
     "url": "https://www.understandingwar.org/rss.xml"},
    {"name": "Kyiv Independent","category": "UKRAINA",      "severity": "high",
     "url": "https://kyivindependent.com/feed/"},
    {"name": "RFE/RL Ukraine",  "category": "UKRAINA",      "severity": "med",
     "url": "https://www.rferl.org/api/zpioevpumz"},

    # Mellanöstern
    {"name": "Times of Israel", "category": "MELLANÖSTERN", "severity": "med",
     "url": "https://www.timesofisrael.com/feed/"},
    {"name": "Middle East Eye", "category": "MELLANÖSTERN", "severity": "med",
     "url": "https://www.middleeasteye.net/rss"},
    {"name": "Al-Monitor",      "category": "MELLANÖSTERN", "severity": "med",
     "url": "https://www.al-monitor.com/rss"},

    # Norden / Sverige
    {"name": "SVT Utrikes",     "category": "NORDEN",       "severity": "low",
     "url": "https://www.svt.se/nyheter/utrikes/rss.xml"},
    {"name": "MSB",             "category": "NORDEN",       "severity": "med",
     "url": "https://www.msb.se/sv/aktuellt/nyheter/rss/"},
    {"name": "Försvarsmakten",  "category": "NORDEN",       "severity": "high",
     "url": "https://www.forsvarsmakten.se/sv/aktuellt/nyheter/rss/"},

    # Kina / Taiwan
    {"name": "Taiwan News",     "category": "KINA/TAIWAN",  "severity": "med",
     "url": "https://www.taiwannews.com.tw/rss"},
    {"name": "SCMP Asia",       "category": "KINA/TAIWAN",  "severity": "med",
     "url": "https://www.scmp.com/rss/91/feed"},

    # Hybridhot
    {"name": "Bellingcat",      "category": "HYBRID",       "severity": "high",
     "url": "https://www.bellingcat.com/feed/"},
    {"name": "ACLED",           "category": "HYBRID",       "severity": "med",
     "url": "https://acleddata.com/feed/"},
    {"name": "Recorded Future", "category": "HYBRID",       "severity": "high",
     "url": "https://www.recordedfuture.com/feed"},
    {"name": "Defense One",     "category": "HYBRID",       "severity": "med",
     "url": "https://www.defenseone.com/rss/all/"},

    # General
    {"name": "Reuters",         "category": "GENERAL",      "severity": "low",
     "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "BBC World",       "category": "GENERAL",      "severity": "low",
     "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "DW World",        "category": "GENERAL",      "severity": "low",
     "url": "https://rss.dw.com/xml/rss-en-world"},
    {"name": "Guardian",        "category": "GENERAL",      "severity": "low",
     "url": "https://www.theguardian.com/world/rss"},
]

POLYMARKET_SLUGS = [
    "will-the-us-and-iran-enter-into-a-direct-military-conflict-in-2025",
    "will-russia-and-ukraine-reach-a-ceasefire-agreement-in-2025",
    "will-china-invade-taiwan-in-2025",
    "will-nato-invoke-article-5-in-2025",
    "will-there-be-a-nuclear-attack-in-2025",
    "will-iran-close-the-strait-of-hormuz-in-2025",
    "will-there-be-a-coup-in-russia-in-2025",
    "trump-new-iran-nuclear-deal-2025",
]


def time_ago(dt):
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = int((now - dt).total_seconds())
    if diff < 60:   return f"{diff}s sedan"
    if diff < 3600: return f"{diff//60}min sedan"
    if diff < 86400:return f"{diff//3600}h sedan"
    return f"{diff//86400}d sedan"


def fetch_rss():
    items = []
    sources_status = []

    for src in RSS_SOURCES:
        try:
            resp = requests.get(src["url"], headers=HEADERS, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            count = 0
            for entry in feed.entries[:8]:
                pub = None
                for attr in ("published_parsed", "updated_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        pub = datetime(*val[:6], tzinfo=timezone.utc)
                        break

                desc = ""
                if hasattr(entry, "summary"):
                    desc = re.sub(r"<[^>]+>", "", entry.summary or "")[:250].strip()

                items.append({
                    "title":    (entry.get("title") or "")[:120],
                    "body":     desc,
                    "source":   src["name"],
                    "category": src["category"],
                    "severity": src["severity"],
                    "url":      entry.get("link", ""),
                    "pubDate":  pub.isoformat() if pub else None,
                    "age":      time_ago(pub),
                })
                count += 1

            sources_status.append({"name": src["name"], "status": "ok", "count": count})
            print(f"  OK   {src['name']}: {count} poster")

        except Exception as e:
            sources_status.append({"name": src["name"], "status": "fail", "error": str(e)[:100]})
            print(f"  FEL  {src['name']}: {e}")

    items.sort(key=lambda x: x["pubDate"] or "", reverse=True)
    ok  = sum(1 for s in sources_status if s["status"] == "ok")
    fail= sum(1 for s in sources_status if s["status"] == "fail")

    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "stats":   {"ok": ok, "fail": fail, "sources": sources_status},
        "items":   items[:200],
    }


def fetch_polymarket():
    markets = []
    base = "https://gamma-api.polymarket.com/markets"

    for slug in POLYMARKET_SLUGS:
        try:
            resp = requests.get(f"{base}?slug={slug}", headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                raise ValueError("Tom respons")

            m    = data[0]
            prob = 0
            try:
                prices = json.loads(m.get("outcomePrices", "[0]"))
                prob   = round(float(prices[0]) * 100)
            except Exception:
                pass

            vol = m.get("volume", 0) or 0
            vol_str = f"${vol/1000:.0f}K" if vol > 1000 else f"${int(vol)}"

            markets.append({
                "question": m.get("question", slug),
                "prob":     prob,
                "volume":   vol_str,
                "url":      f"https://polymarket.com/event/{m.get('slug', slug)}",
                "trend":    "flat",
                "trendPct": 0,
            })
            print(f"  OK   Polymarket: {prob}% – {m.get('question','')[:50]}")
            time.sleep(0.3)

        except Exception as e:
            print(f"  FEL  Polymarket {slug}: {e}")

    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "markets": markets,
    }


def main():
    print(f"=== OSINT Fetcher {datetime.now(timezone.utc).isoformat()} ===")

    print("\n[1/2] RSS-flöden...")
    rss = fetch_rss()
    out = DATA_DIR / "news.json"
    out.write_text(json.dumps(rss, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(rss['items'])} poster → {out}")

    print("\n[2/2] Polymarket...")
    pm = fetch_polymarket()
    out2 = DATA_DIR / "polymarket.json"
    out2.write_text(json.dumps(pm, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(pm['markets'])} marknader → {out2}")

    print("\nKlar.")


if __name__ == "__main__":
    main()
