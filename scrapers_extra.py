"""
Extra scrapers: local Utah venues, farmers markets, arts/theater, Google Events.
No APIs required except SerpAPI (free tier: 100 searches/month).
"""
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ActivityScraper/1.0)"}


def _get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as ex:
        print(f"    Fetch error {url}: {ex}")
        return None


# ── Kilby Court ───────────────────────────────────────────────────────────────
def fetch_kilby_court() -> list[dict]:
    soup = _get("https://www.kilbycourt.com/events")
    if not soup:
        return []
    events = []
    for item in soup.select(".event-item, .eventItem, article.event"):
        name = item.select_one(".event-name, .title, h2, h3")
        date = item.select_one(".event-date, .date, time")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link else "https://www.kilbycourt.com/events"
        if url.startswith("/"):
            url = "https://www.kilbycourt.com" + url
        events.append({
            "source": "kilby_court",
            "name": name.get_text(strip=True),
            "date": date.get_text(strip=True) if date else "",
            "venue": "Kilby Court",
            "category": "Music",
            "url": url,
        })
    print(f"    Kilby Court: {len(events)} events")
    return events


# ── The Depot ─────────────────────────────────────────────────────────────────
def fetch_the_depot() -> list[dict]:
    soup = _get("https://www.depotslc.com/events")
    if not soup:
        return []
    events = []
    for item in soup.select(".event-item, article.event, .eventItem"):
        name = item.select_one(".event-name, .title, h2, h3")
        date = item.select_one(".event-date, .date, time")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link else "https://www.depotslc.com/events"
        if url.startswith("/"):
            url = "https://www.depotslc.com" + url
        events.append({
            "source": "the_depot",
            "name": name.get_text(strip=True),
            "date": date.get_text(strip=True) if date else "",
            "venue": "The Depot",
            "category": "Music",
            "url": url,
        })
    print(f"    The Depot: {len(events)} events")
    return events


# ── The State Room ────────────────────────────────────────────────────────────
def fetch_state_room() -> list[dict]:
    soup = _get("https://www.thestateroomslc.com/events")
    if not soup:
        return []
    events = []
    for item in soup.select(".event-item, article.event, .eventItem"):
        name = item.select_one(".event-name, .title, h2, h3")
        date = item.select_one(".event-date, .date, time")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link else "https://www.thestateroomslc.com/events"
        if url.startswith("/"):
            url = "https://www.thestateroomslc.com" + url
        events.append({
            "source": "state_room",
            "name": name.get_text(strip=True),
            "date": date.get_text(strip=True) if date else "",
            "venue": "The State Room",
            "category": "Music",
            "url": url,
        })
    print(f"    State Room: {len(events)} events")
    return events


# ── Farmers Markets ───────────────────────────────────────────────────────────
def fetch_farmers_markets() -> list[dict]:
    """
    Utah farmers markets don't have a unified API.
    We pull from a few known sources and supplement with SerpAPI.
    """
    events = []

    # Downtown SLC Farmers Market (Pioneer Park) — seasonal schedule
    slc_market_dates = [
        "2026-06-06", "2026-06-13", "2026-06-20", "2026-06-27",
        "2026-07-04", "2026-07-11", "2026-07-18", "2026-07-25",
        "2026-08-01", "2026-08-08", "2026-08-15", "2026-08-22", "2026-08-29",
        "2026-09-05", "2026-09-12", "2026-09-19", "2026-09-26",
        "2026-10-03", "2026-10-10", "2026-10-17",
    ]
    now_str = datetime.utcnow().strftime("%Y-%m-%d")
    for d in slc_market_dates:
        if d >= now_str:
            events.append({
                "source": "farmers_market",
                "name": "SLC Farmers Market at Pioneer Park",
                "date": d,
                "venue": "Pioneer Park, Salt Lake City",
                "category": "Farmers Market",
                "url": "https://www.slcfarmersmarket.org",
            })

    # Thanksgiving Point Farmers Market
    tp_dates = [
        "2026-06-04", "2026-06-11", "2026-06-18", "2026-06-25",
        "2026-07-09", "2026-07-16", "2026-07-23", "2026-07-30",
        "2026-08-06", "2026-08-13", "2026-08-20", "2026-08-27",
        "2026-09-03", "2026-09-10", "2026-09-17", "2026-09-24",
    ]
    for d in tp_dates:
        if d >= now_str:
            events.append({
                "source": "farmers_market",
                "name": "Thanksgiving Point Farmers Market",
                "date": d,
                "venue": "Thanksgiving Point, Lehi",
                "category": "Farmers Market",
                "url": "https://thanksgivingpoint.org",
            })

    print(f"    Farmers Markets: {len(events)} events")
    return events


# ── Utah Arts & Theater ───────────────────────────────────────────────────────
def fetch_utah_arts() -> list[dict]:
    events = []

    # Pioneer Theatre Company
    soup = _get("https://www.pioneertheatre.org/season/")
    if soup:
        for item in soup.select(".production, .show, article"):
            name = item.select_one("h2, h3, .title")
            date = item.select_one(".dates, .date, time")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link else "https://www.pioneertheatre.org"
            if url.startswith("/"):
                url = "https://www.pioneertheatre.org" + url
            events.append({
                "source": "pioneer_theatre",
                "name": name.get_text(strip=True),
                "date": date.get_text(strip=True) if date else "",
                "venue": "Pioneer Theatre Company",
                "category": "Theater",
                "url": url,
            })

    # Utah Shakespeare Festival (Cedar City — worth the drive)
    soup2 = _get("https://www.bard.org/shows/")
    if soup2:
        for item in soup2.select(".show, .production, article"):
            name = item.select_one("h2, h3, .title")
            date = item.select_one(".dates, .date, time")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link else "https://www.bard.org"
            if url.startswith("/"):
                url = "https://www.bard.org" + url
            events.append({
                "source": "utah_shakespeare",
                "name": name.get_text(strip=True),
                "date": date.get_text(strip=True) if date else "",
                "venue": "Utah Shakespeare Festival",
                "category": "Theater",
                "url": url,
            })

    print(f"    Utah Arts/Theater: {len(events)} events")
    return events


# ── Google Events via SerpAPI ─────────────────────────────────────────────────
def fetch_google_events() -> list[dict]:
    api_key = os.environ.get("SERPAPI_API_KEY", "")
    if not api_key:
        print("    Google Events: no SERPAPI_API_KEY, skipping")
        return []

    events = []
    queries = [
        "events near Lehi Utah this month",
        "farmers market Salt Lake City",
        "tech meetup Utah",
        "5K run race Utah",
    ]

    for q in queries:
        try:
            r = requests.get("https://serpapi.com/search", params={
                "engine": "google_events",
                "q": q,
                "api_key": api_key,
                "hl": "en",
                "gl": "us",
            }, timeout=10)
            r.raise_for_status()
            for e in r.json().get("events_results", []):
                date_info = e.get("date", {})
                events.append({
                    "source": "google_events",
                    "name": e.get("title", ""),
                    "date": date_info.get("start_date", ""),
                    "venue": e.get("venue", {}).get("name", ""),
                    "category": e.get("type", "Event"),
                    "url": e.get("link", ""),
                })
        except Exception as ex:
            print(f"    SerpAPI error for '{q}': {ex}")

    print(f"    Google Events: {len(events)} events")
    return events


# ── Combined entry point ──────────────────────────────────────────────────────
def scrape_extra() -> list[dict]:
    all_events = []
    for fn in [
        fetch_kilby_court,
        fetch_the_depot,
        fetch_state_room,
        fetch_farmers_markets,
        fetch_utah_arts,
        fetch_google_events,
    ]:
        try:
            all_events.extend(fn())
        except Exception as ex:
            print(f"    {fn.__name__} error: {ex}")
    return all_events
