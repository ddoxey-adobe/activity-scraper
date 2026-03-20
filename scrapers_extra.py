"""
Extra scrapers: Utah venue-specific Ticketmaster/AXS queries, KRCL, 
NowPlayingUtah, farmers markets, and Google Events.
"""
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ActivityScraper/1.0)"}
NOW = datetime.utcnow()
END = NOW + timedelta(days=30)
FMT = "%Y-%m-%dT%H:%M:%SZ"

# Ticketmaster venue IDs for Utah venues
TICKETMASTER_VENUE_IDS = {
    "Delta Center":                    "KovZpZAFnJ0A",
    "Utah First Credit Union Amphitheatre": "KovZpZAJvdeA",
    "Red Butte Garden Amphitheatre":   "KovZpZAJ6e0A",
    "The Complex":                     "KovZpZAJvFnA",
    "The Depot":                       "KovZpZAJk7IA",
    "The Great Saltair":               "KovZpZAJa16A",
    "Kilby Court":                     "KovZpZAJ6nlA",
    "Abravanel Hall":                  "KovZpZAJaJeA",
    "Capitol Theatre SLC":             "KovZpZAJ6e6A",
    "Sandy Amphitheater":              "KovZpZAJdFdA",
    "Maverik Center":                  "KovZpZAFnvnA",
}

# AXS venue IDs (used by some Utah venues)
AXS_VENUE_IDS = {
    "Covey Center for the Arts": "250426",
    "SCERA Center for the Arts": "251048",
}


def _get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as ex:
        print(f"    Fetch error {url}: {ex}")
        return None


# ── Ticketmaster venue-specific queries ───────────────────────────────────────
def fetch_ticketmaster_venues() -> list[dict]:
    key = os.environ.get("TICKETMASTER_API_KEY", "")
    if not key:
        print("    TM Venues: no API key, skipping")
        return []

    events = []
    for venue_name, venue_id in TICKETMASTER_VENUE_IDS.items():
        try:
            r = requests.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={
                    "apikey": key,
                    "venueId": venue_id,
                    "startDateTime": NOW.strftime(FMT),
                    "endDateTime": END.strftime(FMT),
                    "size": 50,
                },
                timeout=10,
            )
            r.raise_for_status()
            items = r.json().get("_embedded", {}).get("events", [])
            for e in items:
                venue = e.get("_embedded", {}).get("venues", [{}])[0]
                events.append({
                    "source": "ticketmaster_venue",
                    "name": e.get("name", ""),
                    "date": e.get("dates", {}).get("start", {}).get("localDate", ""),
                    "venue": venue_name,
                    "category": e.get("classifications", [{}])[0].get("segment", {}).get("name", ""),
                    "url": e.get("url", ""),
                })
        except Exception as ex:
            print(f"    TM {venue_name} error: {ex}")

    print(f"    TM Venue queries: {len(events)} events")
    return events


# ── AXS venue queries (Covey Center, SCERA) ───────────────────────────────────
def fetch_axs_venues() -> list[dict]:
    events = []
    for venue_name, venue_id in AXS_VENUE_IDS.items():
        soup = _get(f"https://www.axs.com/venues/{venue_id}/events")
        if not soup:
            continue
        for item in soup.select(".event-listing, .event-card, article"):
            name = item.select_one("h2, h3, .event-name, .title")
            date = item.select_one("time, .event-date, .date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else f"https://www.axs.com/venues/{venue_id}/events"
            if url.startswith("/"):
                url = "https://www.axs.com" + url
            events.append({
                "source": "axs",
                "name": name.get_text(strip=True),
                "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                "venue": venue_name,
                "category": "Arts & Theater",
                "url": url,
            })
    print(f"    AXS Venues: {len(events)} events")
    return events


# ── Red Butte Garden (has its own ticketing) ──────────────────────────────────
def fetch_red_butte() -> list[dict]:
    soup = _get("https://redbuttegarden.org/concerts/")
    if not soup:
        return []
    events = []
    for item in soup.select(".concert, .event, article, .show"):
        name = item.select_one("h2, h3, .concert-title, .entry-title")
        date = item.select_one("time, .concert-date, .date")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link and link.get("href") else "https://redbuttegarden.org/concerts/"
        if url.startswith("/"):
            url = "https://redbuttegarden.org" + url
        events.append({
            "source": "red_butte_garden",
            "name": name.get_text(strip=True),
            "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
            "venue": "Red Butte Garden Amphitheatre",
            "category": "Music",
            "url": url,
        })
    print(f"    Red Butte Garden: {len(events)} events")
    return events


# ── SCERA Center for the Arts (direct scrape fallback) ───────────────────────
def fetch_scera() -> list[dict]:
    soup = _get("https://www.scera.org/events/")
    if not soup:
        return []
    events = []
    for item in soup.select(".event, article, .tribe-event"):
        name = item.select_one("h2, h3, .entry-title, .tribe-event-url")
        date = item.select_one("time, .tribe-event-date-start, .event-date")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link and link.get("href") else "https://www.scera.org/events/"
        events.append({
            "source": "scera",
            "name": name.get_text(strip=True),
            "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
            "venue": "SCERA Center for the Arts",
            "category": "Arts & Theater",
            "url": url,
        })
    print(f"    SCERA: {len(events)} events")
    return events


# ── Covey Center for the Arts (direct scrape fallback) ───────────────────────
def fetch_covey() -> list[dict]:
    soup = _get("https://coveycenter.org/events/")
    if not soup:
        return []
    events = []
    for item in soup.select(".event, article, .tribe-event"):
        name = item.select_one("h2, h3, .entry-title, .tribe-event-url")
        date = item.select_one("time, .tribe-event-date-start, .event-date")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link and link.get("href") else "https://coveycenter.org/events/"
        events.append({
            "source": "covey_center",
            "name": name.get_text(strip=True),
            "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
            "venue": "Covey Center for the Arts",
            "category": "Arts & Theater",
            "url": url,
        })
    print(f"    Covey Center: {len(events)} events")
    return events


# ── Repeal Jazz Club ──────────────────────────────────────────────────────────
def fetch_repeal() -> list[dict]:
    soup = _get("https://www.repealslc.com/events")
    if not soup:
        return []
    events = []
    for item in soup.select(".event, article, .show, .event-item"):
        name = item.select_one("h2, h3, .event-name, .title")
        date = item.select_one("time, .event-date, .date")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link and link.get("href") else "https://www.repealslc.com/events"
        if url.startswith("/"):
            url = "https://www.repealslc.com" + url
        events.append({
            "source": "repeal_jazz",
            "name": name.get_text(strip=True),
            "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
            "venue": "Repeal Jazz Club",
            "category": "Music",
            "url": url,
        })
    print(f"    Repeal Jazz: {len(events)} events")
    return events


# ── KRCL Events ───────────────────────────────────────────────────────────────
def fetch_krcl() -> list[dict]:
    events = []
    for category in ["live-music", "arts-culture", "community"]:
        soup = _get(f"https://krcl.org/events/?category={category}")
        if not soup:
            continue
        for item in soup.select("article, .event, .tribe-event"):
            name = item.select_one("h2, h3, .tribe-event-url, .entry-title")
            date = item.select_one("time, .tribe-event-date-start, .event-date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://krcl.org/events"
            events.append({
                "source": "krcl",
                "name": name.get_text(strip=True),
                "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                "venue": "",
                "category": category.replace("-", " ").title(),
                "url": url,
            })
    print(f"    KRCL: {len(events)} events")
    return events


# ── NowPlayingUtah ────────────────────────────────────────────────────────────
def fetch_nowplaying_utah() -> list[dict]:
    soup = _get("https://www.nowplayingutah.com/events/")
    if not soup:
        return []
    events = []
    for item in soup.select(".event, article, .tribe-event"):
        name = item.select_one("h2, h3, .entry-title, .tribe-event-url")
        date = item.select_one("time, .tribe-event-date-start, .event-date")
        venue = item.select_one(".tribe-venue, .venue, .location")
        link = item.select_one("a")
        if not name:
            continue
        url = link["href"] if link and link.get("href") else "https://www.nowplayingutah.com/events/"
        events.append({
            "source": "nowplaying_utah",
            "name": name.get_text(strip=True),
            "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
            "venue": venue.get_text(strip=True) if venue else "",
            "category": "Arts & Theater",
            "url": url,
        })
    print(f"    NowPlayingUtah: {len(events)} events")
    return events


# ── Farmers Markets ───────────────────────────────────────────────────────────
def fetch_farmers_markets() -> list[dict]:
    events = []
    now_str = datetime.utcnow().strftime("%Y-%m-%d")

    slc_dates = [
        "2026-06-06", "2026-06-13", "2026-06-20", "2026-06-27",
        "2026-07-04", "2026-07-11", "2026-07-18", "2026-07-25",
        "2026-08-01", "2026-08-08", "2026-08-15", "2026-08-22", "2026-08-29",
        "2026-09-05", "2026-09-12", "2026-09-19", "2026-09-26",
        "2026-10-03", "2026-10-10", "2026-10-17",
    ]
    for d in slc_dates:
        if d >= now_str:
            events.append({
                "source": "farmers_market",
                "name": "SLC Farmers Market at Pioneer Park",
                "date": d,
                "venue": "Pioneer Park, Salt Lake City",
                "category": "Farmers Market",
                "url": "https://www.slcfarmersmarket.org",
            })

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


# ── Google Events via SerpAPI ─────────────────────────────────────────────────
def fetch_google_events() -> list[dict]:
    api_key = os.environ.get("SERPAPI_KEY", "") or os.environ.get("SERPAPI_API_KEY", "")
    if not api_key:
        print("    Google Events: no SERPAPI key found, skipping")
        return []

    events = []
    queries = [
        "events near Lehi Utah this month",
        "farmers market Salt Lake City",
        "tech meetup Utah",
        "5K run race Utah",
        "comedy show Salt Lake City",
        "theater Salt Lake City",
        "jazz Salt Lake City",
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
        fetch_ticketmaster_venues,
        fetch_red_butte,
        fetch_scera,
        fetch_covey,
        fetch_repeal,
        fetch_krcl,
        fetch_nowplaying_utah,
        fetch_farmers_markets,
        fetch_google_events,
    ]:
        try:
            all_events.extend(fn())
        except Exception as ex:
            print(f"    {fn.__name__} error: {ex}")
    return all_events
