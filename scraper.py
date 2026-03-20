import os
import json
import requests
from datetime import datetime, timedelta
from scrapers_extra import scrape_extra

CITY = "Lehi, UT"
LAT, LNG = 40.3916, -111.8508
RADIUS_MILES = 50
DAYS_AHEAD = 30

NOW = datetime.utcnow()
END = NOW + timedelta(days=DAYS_AHEAD)
FMT = "%Y-%m-%dT%H:%M:%SZ"


def fetch_ticketmaster() -> list[dict]:
    key = os.environ["TICKETMASTER_API_KEY"]
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    events = []
    page = 0
    while True:
        params = {
            "apikey": key,
            "latlong": f"{LAT},{LNG}",
            "radius": RADIUS_MILES,
            "unit": "miles",
            "startDateTime": NOW.strftime(FMT),
            "endDateTime": END.strftime(FMT),
            "classificationName": "music,arts,theatre,comedy,sports",
            "size": 200,
            "page": page,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("_embedded", {}).get("events", [])
        if not items:
            break
        for e in items:
            venue = e.get("_embedded", {}).get("venues", [{}])[0]
            events.append({
                "source": "ticketmaster",
                "name": e.get("name", ""),
                "date": e.get("dates", {}).get("start", {}).get("localDate", ""),
                "venue": venue.get("name", ""),
                "category": e.get("classifications", [{}])[0].get("segment", {}).get("name", ""),
                "url": e.get("url", ""),
            })
        total_pages = data.get("page", {}).get("totalPages", 1)
        page += 1
        if page >= total_pages or page >= 5:
            break
    return events


def fetch_eventbrite() -> list[dict]:
    """
    Eventbrite deprecated their public location-based search API in 2023.
    Eventbrite events are now caught via the Google Events SerpAPI queries instead.
    """
    print("  Eventbrite: using SerpAPI for discovery instead")
    return []


def fetch_bandsintown() -> list[dict]:
    app_id = os.environ.get("BANDSINTOWN_APP_ID", "")
    if not app_id:
        print("  Bandsintown: no app ID, skipping")
        return []
    seed_artists = ["local+utah+bands", "indie+rock", "alternative"]
    events = []
    for artist in seed_artists:
        url = f"https://rest.bandsintown.com/artists/{artist}/events"
        params = {"app_id": app_id, "date": f"{NOW.strftime('%Y-%m-%d')},{END.strftime('%Y-%m-%d')}"}
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                continue
            for e in r.json():
                venue = e.get("venue", {})
                region = venue.get("region", "")
                city = venue.get("city", "")
                if "UT" not in region and "Utah" not in city:
                    continue
                events.append({
                    "source": "bandsintown",
                    "name": f"{e.get('artist', {}).get('name', '')} @ {venue.get('name', '')}",
                    "date": (e.get("datetime", "") or "")[:10],
                    "venue": venue.get("name", ""),
                    "category": "Music",
                    "url": e.get("url", ""),
                })
        except Exception:
            continue
    return events


def fetch_meetup() -> list[dict]:
    """
    Meetup API now requires a Pro subscription ($30+/month).
    Meetup events are caught via Google Events SerpAPI queries instead.
    """
    print("  Meetup: Pro subscription required, using SerpAPI instead")
    return []


def deduplicate(events: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for e in events:
        key = (e["name"].lower().strip(), e["date"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def scrape_all() -> list[dict]:
    all_events = []
    for fn, label in [
        (fetch_ticketmaster, "Ticketmaster"),
        (fetch_eventbrite, "Eventbrite"),
        (fetch_bandsintown, "Bandsintown"),
        (fetch_meetup, "Meetup"),
    ]:
        try:
            results = fn()
            print(f"  {label}: {len(results)} events")
            all_events.extend(results)
        except Exception as ex:
            print(f"  {label} error: {ex}")

    print("  Extra sources:")
    all_events.extend(scrape_extra())

    deduped = deduplicate(all_events)
    print(f"  Total after dedup: {len(deduped)}")
    return deduped


if __name__ == "__main__":
    print("Scraping events...")
    events = scrape_all()
    with open("events_raw.json", "w") as f:
        json.dump(events, f, indent=2)
    print(f"Saved {len(events)} events to events_raw.json")
