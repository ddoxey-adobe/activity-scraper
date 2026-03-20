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
    key = os.environ.get("EVENTBRITE_API_KEY", "")
    if not key:
        print("  Eventbrite: no API key, skipping")
        return []
    url = "https://www.eventbriteapi.com/v3/events/search/"
    headers = {"Authorization": f"Bearer {key}"}
    events = []
    page = 1
    while True:
        params = {
            "location.latitude": LAT,
            "location.longitude": LNG,
            "location.within": f"{RADIUS_MILES}mi",
            "start_date.range_start": NOW.strftime(FMT),
            "start_date.range_end": END.strftime(FMT),
            "expand": "venue",
            "page": page,
        }
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        for e in data.get("events", []):
            venue = e.get("venue") or {}
            events.append({
                "source": "eventbrite",
                "name": e.get("name", {}).get("text", ""),
                "date": (e.get("start", {}).get("local", "") or "")[:10],
                "venue": venue.get("name", ""),
                "category": e.get("category_id", ""),
                "url": e.get("url", ""),
            })
        if not data.get("pagination", {}).get("has_more_items"):
            break
        page += 1
        if page > 5:
            break
    return events


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
    key = os.environ.get("MEETUP_API_KEY", "")
    if not key:
        print("  Meetup: no API key, skipping")
        return []
    url = "https://api.meetup.com/gql"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    query = """
    query($lat: Float!, $lon: Float!, $radius: Float!, $after: DateTime!) {
      keywordSearch(filter: {lat: $lat, lon: $lon, radius: $radius, source: EVENTS, startDateRange: $after}) {
        edges { node { result { ... on Event {
          title dateTime venue { name } eventUrl
          group { category { name } }
        }}}}
      }
    }
    """
    events = []
    try:
        r = requests.post(url, headers=headers, json={
            "query": query,
            "variables": {"lat": LAT, "lon": LNG, "radius": float(RADIUS_MILES), "after": NOW.isoformat()}
        }, timeout=10)
        r.raise_for_status()
        edges = r.json().get("data", {}).get("keywordSearch", {}).get("edges", [])
        for edge in edges:
            e = edge.get("node", {}).get("result", {})
            if not e.get("title"):
                continue
            venue = e.get("venue") or {}
            events.append({
                "source": "meetup",
                "name": e.get("title", ""),
                "date": (e.get("dateTime", "") or "")[:10],
                "venue": venue.get("name", ""),
                "category": e.get("group", {}).get("category", {}).get("name", ""),
                "url": e.get("eventUrl", ""),
            })
    except Exception as ex:
        print(f"  Meetup error: {ex}")
    return events


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
