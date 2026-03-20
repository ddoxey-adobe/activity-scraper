"""
Extra scrapers: Utah venues, university calendars, attractions, and Google Events.
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

TICKETMASTER_VENUE_IDS = {
    "Delta Center":                         "KovZpZAFnJ0A",
    "Utah First Credit Union Amphitheatre": "KovZpZAJvdeA",
    "Red Butte Garden Amphitheatre":        "KovZpZAJ6e0A",
    "The Complex":                          "KovZpZAJvFnA",
    "The Depot":                            "KovZpZAJk7IA",
    "The Great Saltair":                    "KovZpZAJa16A",
    "Kilby Court":                          "KovZpZAJ6nlA",
    "Abravanel Hall":                       "KovZpZAJaJeA",
    "Capitol Theatre SLC":                  "KovZpZAJ6e6A",
    "Sandy Amphitheater":                   "KovZpZAJdFdA",
    "Maverik Center":                       "KovZpZAFnvnA",
}


def _get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as ex:
        print(f"    Fetch error {url}: {ex}")
        return None


def _serpapi(query: str, api_key: str, venue: str, category: str, url: str) -> list[dict]:
    events = []
    try:
        r = requests.get("https://serpapi.com/search", params={
            "engine": "google_events", "q": query,
            "api_key": api_key, "hl": "en", "gl": "us",
        }, timeout=10)
        r.raise_for_status()
        for e in r.json().get("events_results", []):
            events.append({
                "source": "google_events",
                "name": e.get("title", ""),
                "date": e.get("date", {}).get("start_date", ""),
                "venue": venue or e.get("venue", {}).get("name", ""),
                "category": category,
                "url": e.get("link", url),
            })
    except Exception as ex:
        print(f"    SerpAPI error '{query}': {ex}")
    return events


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
                params={"apikey": key, "venueId": venue_id,
                        "startDateTime": NOW.strftime(FMT),
                        "endDateTime": END.strftime(FMT), "size": 50},
                timeout=10,
            )
            r.raise_for_status()
            for e in r.json().get("_embedded", {}).get("events", []):
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


# ── Velour Live Music ─────────────────────────────────────────────────────────
def fetch_velour() -> list[dict]:
    events = []
    # Weekly Thursday open mic
    current = NOW
    while current <= END:
        if current.weekday() == 3:
            events.append({
                "source": "velour",
                "name": "Velour Open Mic Night",
                "date": current.strftime("%Y-%m-%d"),
                "venue": "Velour Live Music Gallery, Provo",
                "category": "Music",
                "url": "https://velourlive.com/openmic",
            })
        current += timedelta(days=1)
    # SerpAPI for ticketed shows
    api_key = os.environ.get("SERPAPI_API_KEY", "") or os.environ.get("SERPAPI_KEY", "")
    if api_key:
        events += _serpapi("Velour Live Music Provo shows", api_key, "Velour Live Music Gallery, Provo", "Music", "https://velourlive.com/shows")
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    Velour: {len(unique)} events")
    return unique


# ── Thanksgiving Point ────────────────────────────────────────────────────────
def fetch_thanksgiving_point() -> list[dict]:
    events = []
    now_str = NOW.strftime("%Y-%m-%d")
    soup = _get("https://thanksgivingpoint.org/calendar/")
    if soup:
        for item in soup.select("article, .event, .tribe-event, .event-item, .card"):
            name = item.select_one("h2, h3, h4, .entry-title, .title")
            date = item.select_one("time, .tribe-event-date-start, .event-date, .date")
            link = item.select_one("a")
            if not name or len(name.get_text(strip=True)) < 3:
                continue
            url = link["href"] if link and link.get("href") else "https://thanksgivingpoint.org/calendar/"
            if url.startswith("/"):
                url = "https://thanksgivingpoint.org" + url
            events.append({
                "source": "thanksgiving_point",
                "name": name.get_text(strip=True),
                "date": (date.get("datetime", date.get_text(strip=True))[:10] if date else ""),
                "venue": "Thanksgiving Point, Lehi",
                "category": "Community",
                "url": url,
            })
    if not events:
        known = [
            ("Tulip Festival at Thanksgiving Point",     "2026-04-10", "2026-05-10"),
            ("Thanksgiving Point Farmers Market",        "2026-06-04", "2026-09-24"),
            ("Scarecrow Festival at Thanksgiving Point", "2026-09-25", "2026-10-31"),
            ("Electric Winter at Thanksgiving Point",    "2026-11-20", "2027-01-04"),
        ]
        for n, start, end in known:
            if end >= now_str:
                events.append({"source": "thanksgiving_point", "name": n, "date": start,
                                "venue": "Thanksgiving Point, Lehi", "category": "Community",
                                "url": "https://thanksgivingpoint.org/calendar/"})
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    Thanksgiving Point: {len(unique)} events")
    return unique


# ── Utah Motorsports Campus ───────────────────────────────────────────────────
def fetch_utah_motorsports() -> list[dict]:
    now_str = NOW.strftime("%Y-%m-%d")
    known = [
        ("NASA Utah Track Day at UMC",         "2026-04-11"),
        ("REV Performance Track Day",           "2026-04-25"),
        ("Utah SBA Sportbike Track Day",        "2026-05-02"),
        ("APEX Track Days at UMC",              "2026-05-16"),
        ("NASA Utah Championship Round 1",      "2026-05-30"),
        ("IRPCA Race Weekend",                  "2026-06-13"),
        ("REV Performance Track Day",           "2026-06-27"),
        ("NASA Utah Championship Round 2",      "2026-07-18"),
        ("Utah SBA Sportbike Track Day",        "2026-08-01"),
        ("APEX Track Days at UMC",              "2026-08-15"),
        ("NASA Utah Championship Round 3",      "2026-09-05"),
        ("REV Performance Track Day",           "2026-09-19"),
        ("Utah SBA Sportbike Final Round",      "2026-10-03"),
        ("NASA Utah Championship Final Round",  "2026-10-17"),
    ]
    events = [{"source": "utah_motorsports", "name": n, "date": d,
               "venue": "Utah Motorsports Campus, Tooele", "category": "Sports",
               "url": "https://www.utahmotorsportscampus.com/"}
              for n, d in known if d >= now_str]
    api_key = os.environ.get("SERPAPI_API_KEY", "") or os.environ.get("SERPAPI_KEY", "")
    if api_key:
        extra = _serpapi("Utah Motorsports Campus racing 2026", api_key, "Utah Motorsports Campus, Tooele", "Sports", "https://www.utahmotorsportscampus.com/")
        existing = {e["name"] for e in events}
        events += [e for e in extra if e["name"] not in existing]
    print(f"    Utah Motorsports Campus: {len(events)} events")
    return events


# ── University Event Calendars ────────────────────────────────────────────────
def fetch_byu_events() -> list[dict]:
    events = []
    feeds = [
        ("https://calendar.byu.edu/api/Events?categories=9", "Arts & Entertainment"),
        ("https://calendar.byu.edu/api/Events?categories=2", "Sports"),
    ]
    for feed_url, category in feeds:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            for block in r.text.split("BEGIN:VEVENT")[1:]:
                lines = {l.split(":")[0].split(";")[0]: ":".join(l.split(":")[1:]).strip()
                         for l in block.split("\n") if ":" in l}
                name = lines.get("SUMMARY", "").strip()
                dtstart = lines.get("DTSTART", "")[:8]
                url = lines.get("URL", "https://calendar.byu.edu").strip()
                if not name or not dtstart:
                    continue
                try:
                    date = datetime.strptime(dtstart, "%Y%m%d").strftime("%Y-%m-%d")
                except ValueError:
                    date = ""
                events.append({"source": "byu", "name": name, "date": date,
                                "venue": "Brigham Young University, Provo",
                                "category": category, "url": url})
        except Exception as ex:
            print(f"    BYU feed error: {ex}")
    print(f"    BYU Events: {len(events)} events")
    return events


def fetch_slcc_events() -> list[dict]:
    events = []
    try:
        r = requests.get("https://calendar.slcc.edu/api/2/events",
                         params={"days": 30, "pp": 50, "type": "Arts,Performance,Music"},
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        for e in r.json().get("events", []):
            evt = e.get("event", {})
            name = evt.get("title", "")
            if not name:
                continue
            events.append({"source": "slcc", "name": name,
                           "date": (evt.get("first_date", "") or "")[:10],
                           "venue": evt.get("location_name", "Salt Lake Community College"),
                           "category": "Arts & Theater",
                           "url": evt.get("url", "https://calendar.slcc.edu")})
    except Exception as ex:
        print(f"    SLCC error: {ex}")
    print(f"    SLCC Events: {len(events)} events")
    return events


def fetch_weber_events() -> list[dict]:
    events = []
    soup = _get("https://apps.weber.edu/calendars/calendars.aspx?calendar=arts") or \
           _get("https://www.weber.edu/artscalendar/")
    if soup:
        for item in soup.select(".event, article, .calendar-event, tr"):
            name = item.select_one("a, .title, td")
            date = item.select_one("time, .date, .event-date")
            link = item.select_one("a")
            if not name or len(name.get_text(strip=True)) < 3:
                continue
            url = link["href"] if link and link.get("href") else "https://www.weber.edu/artscalendar/"
            if url.startswith("/"):
                url = "https://www.weber.edu" + url
            events.append({"source": "weber_state", "name": name.get_text(strip=True),
                           "date": date.get_text(strip=True)[:10] if date else "",
                           "venue": "Weber State University, Ogden",
                           "category": "Arts & Theater", "url": url})
    print(f"    Weber State: {len(events)} events")
    return events


def fetch_uvu_events() -> list[dict]:
    events = []
    soup = _get("https://www.uvu.edu/events/category/arts.html")
    if soup:
        for item in soup.select(".event-item, article, .event"):
            name = item.select_one("h2, h3, .title, a")
            date = item.select_one("time, .date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://www.uvu.edu/events/"
            events.append({"source": "uvu", "name": name.get_text(strip=True),
                           "date": date.get_text(strip=True)[:10] if date else "",
                           "venue": "Utah Valley University, Orem",
                           "category": "Arts & Theater", "url": url})
    print(f"    UVU Events: {len(events)} events")
    return events


def fetch_utah_university_events() -> list[dict]:
    events = []
    soup = _get("https://events.utah.edu/")
    if soup:
        for item in soup.select("article, .event, .tribe-event, .eventitem"):
            name = item.select_one("h2, h3, .entry-title, .tribe-event-url")
            date = item.select_one("time, .tribe-event-date-start, .event-date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://events.utah.edu/"
            events.append({"source": "utah_university", "name": name.get_text(strip=True),
                           "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                           "venue": "University of Utah, Salt Lake City",
                           "category": "Arts & Theater", "url": url})
    print(f"    U of U Events: {len(events)} events")
    return events


def fetch_utah_stadium_events() -> list[dict]:
    events = []
    soup = _get("https://www.stadium.utah.edu/all-events/")
    if soup:
        for item in soup.select("article, .event, .tribe-event"):
            name = item.select_one("h2, h3, .entry-title")
            date = item.select_one("time, .tribe-event-date-start, .event-date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://www.stadium.utah.edu/all-events/"
            events.append({"source": "utah_stadium", "name": name.get_text(strip=True),
                           "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                           "venue": "Rice-Eccles Stadium, Salt Lake City",
                           "category": "Sports", "url": url})
    print(f"    Utah Stadium Events: {len(events)} events")
    return events


# ── Desert Star Playhouse ─────────────────────────────────────────────────────
def fetch_desert_star() -> list[dict]:
    now_str = NOW.strftime("%Y-%m-%d")
    season = [
        ("Greased: Happy Days Are Here Again", "2026-01-08", "2026-03-28"),
        ("The Princess Bride",                 "2026-04-02", "2026-06-06"),
        ("Big Bang Theory Parody",             "2026-06-11", "2026-08-22"),
        ("Scooby-Doo Parody",                  "2026-08-27", "2026-11-07"),
        ("The Nutcracker Parody",              "2026-11-12", "2027-01-02"),
    ]
    events = [{"source": "desert_star", "name": n, "date": start,
               "venue": "Desert Star Playhouse, Murray", "category": "Comedy",
               "url": "https://desertstarplayhouse.com/2026-season/"}
              for n, start, end in season if end >= now_str]
    print(f"    Desert Star Playhouse: {len(events)} events")
    return events


# ── Utah Symphony & Opera (USUO) ──────────────────────────────────────────────
def fetch_usuo() -> list[dict]:
    now_str = NOW.strftime("%Y-%m-%d")
    season = [
        ("Utah Symphony: Mahler's Titan",            "2026-03-19", "Abravanel Hall"),
        ("Utah Symphony: Spring Pops",               "2026-04-17", "Abravanel Hall"),
        ("Utah Symphony: Beethoven's Ninth",         "2026-05-07", "Abravanel Hall"),
        ("Utah Opera: The Marriage of Figaro",       "2026-04-24", "Capitol Theatre"),
        ("Utah Opera: Don Pasquale",                 "2026-05-15", "Capitol Theatre"),
        ("Utah Symphony: Star Wars in Concert",      "2026-06-12", "Abravanel Hall"),
        ("Deer Valley Music Festival Opening Night", "2026-07-10", "Deer Valley"),
    ]
    events = [{"source": "usuo", "name": n, "date": d, "venue": v,
               "category": "Music", "url": "https://usuo.org/schedule/"}
              for n, d, v in season if d >= now_str]
    print(f"    USUO: {len(events)} events")
    return events


# ── Ski Resort Events ─────────────────────────────────────────────────────────
def fetch_ski_resort_events() -> list[dict]:
    now_str = NOW.strftime("%Y-%m-%d")
    known = [
        ("Alta Spring Skiing & Closing Day",       "2026-04-19", "Alta Ski Area",         "https://www.alta.com/events"),
        ("Snowbird Oktoberfest",                   "2026-09-05", "Snowbird Resort",        "https://www.snowbird.com/activities-events/events/events-calendar/"),
        ("Snowbird Spring Ski Race Series",        "2026-03-28", "Snowbird Resort",        "https://www.snowbird.com/activities-events/events/events-calendar/"),
        ("Solitude Spring Concert Series",         "2026-03-21", "Solitude Mountain",      "https://www.solitudemountain.com/things-to-do/events-and-activities"),
        ("Solitude Closing Day Party",             "2026-04-12", "Solitude Mountain",      "https://www.solitudemountain.com/things-to-do/events-and-activities"),
        ("Deer Valley Spring Celebration",         "2026-04-05", "Deer Valley Resort",     "https://www.deervalley.com/things-to-do/events"),
        ("Deer Valley Music Festival",             "2026-07-10", "Deer Valley Resort",     "https://www.deervalley.com/things-to-do/events"),
        ("Brighton Closing Day Festival",          "2026-04-19", "Brighton Resort",        "https://www.brightonresort.com/events"),
        ("Brighton Fall Bike Park Opening",        "2026-06-20", "Brighton Resort",        "https://www.brightonresort.com/events"),
        ("Park City Mountain Closing Day",         "2026-04-19", "Park City Mountain",     "https://www.parkcitymountain.com/explore-the-resort/during-your-stay/park-city-events.aspx"),
        ("Park City Mountain 4th of July",         "2026-07-04", "Park City Mountain",     "https://www.parkcitymountain.com/explore-the-resort/during-your-stay/park-city-events.aspx"),
    ]
    events = [{"source": "ski_resort", "name": n, "date": d, "venue": v,
               "category": "Sports", "url": u}
              for n, d, v, u in known if d >= now_str]
    api_key = os.environ.get("SERPAPI_API_KEY", "") or os.environ.get("SERPAPI_KEY", "")
    if api_key:
        for q, v, u in [
            ("Alta ski resort events 2026", "Alta Ski Area", "https://www.alta.com/events"),
            ("Snowbird resort events 2026", "Snowbird Resort", "https://www.snowbird.com/activities-events/events/events-calendar/"),
            ("Park City Mountain events 2026", "Park City Mountain", "https://www.parkcitymountain.com/explore-the-resort/during-your-stay/park-city-events.aspx"),
            ("Deer Valley events 2026", "Deer Valley Resort", "https://www.deervalley.com/things-to-do/events"),
        ]:
            existing = {e["name"] for e in events}
            for e in _serpapi(q, api_key, v, "Sports", u):
                if e["name"] not in existing:
                    events.append(e)
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    Ski Resort Events: {len(unique)} events")
    return unique


# ── Utah Olympic Legacy Foundation ────────────────────────────────────────────
def fetch_utah_olympic() -> list[dict]:
    events = []
    pages = [
        ("https://utaholympiclegacy.org/soho-events/", "Soldier Hollow Nordic Center"),
        ("https://utaholympiclegacy.org/park-events/", "Utah Olympic Park"),
        ("https://utaholympiclegacy.org/oval-events/", "Utah Olympic Oval"),
    ]
    for url, venue in pages:
        soup = _get(url)
        if not soup:
            continue
        current_date = ""
        for tag in soup.select("h3, h4, a[href*='/event/']"):
            if tag.name in ("h3", "h4"):
                text = tag.get_text(strip=True)
                match = re.search(
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})', text)
                if match:
                    try:
                        current_date = datetime.strptime(f"{match.group(1)} {match.group(2)} 2026", "%B %d %Y").strftime("%Y-%m-%d")
                    except ValueError:
                        current_date = ""
            elif tag.name == "a" and "/event/" in tag.get("href", ""):
                name = tag.get_text(strip=True)
                if not name or len(name) < 3:
                    continue
                href = tag["href"]
                if href.startswith("/"):
                    href = "https://utaholympiclegacy.org" + href
                events.append({"source": "utah_olympic", "name": name, "date": current_date,
                                "venue": venue, "category": "Sports", "url": href})
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    Utah Olympic Legacy: {len(unique)} events")
    return unique


# ── Soldier Hollow Classic ────────────────────────────────────────────────────
def fetch_soldier_hollow() -> list[dict]:
    now_str = NOW.strftime("%Y-%m-%d")
    days = [("2026-05-22", "Friday"), ("2026-05-23", "Saturday"),
            ("2026-05-24", "Sunday"), ("2026-05-25", "Monday — Memorial Day")]
    events = [{"source": "soldier_hollow",
               "name": f"Soldier Hollow Classic Sheepdog Championship & Festival ({label})",
               "date": date, "venue": "Soldier Hollow, Heber Valley, UT",
               "category": "Community", "url": "https://soldierhollowclassic.com/2026-tickets/"}
              for date, label in days if date >= now_str]
    print(f"    Soldier Hollow Classic: {len(events)} events")
    return events


# ── Covey Center for the Arts ─────────────────────────────────────────────────
def fetch_covey_center() -> list[dict]:
    events = []
    pages = [
        ("https://www.provo.gov/1023/Covey-Presents",  "Arts & Theater"),
        ("https://www.provo.gov/1220/Free-Concerts",   "Music"),
        ("https://www.provo.gov/1234/Black-Box-Shows",  "Theater"),
        ("https://www.provo.gov/1140/Community-Events", "Community"),
    ]
    skip = {"tickets", "visit", "classes", "rentals", "support", "about", "home",
            "search", "sign in", "contact", "giveaway", "rules", "get tickets",
            "covey presents", "free concerts", "black box", "community events",
            "ticket giveaway", "back box shows", "privacy policy", "community news",
            "business & innovation hub", "explore & enjoy", "utilities", "fly provo",
            "share feedback", "join our team", "site map", "accessibility",
            "exceptional care"}
    for url, category in pages:
        soup = _get(url)
        if not soup:
            continue
        for item in soup.select("li a, .listing a, h2 a, h3 a, h4 a"):
            name = item.get_text(strip=True)
            href = item.get("href", "")
            if not name or len(name) < 8 or any(s in name.lower() for s in skip):
                continue
            if href.startswith("/"):
                href = "https://www.provo.gov" + href
            date_text = ""
            show_soup = _get(href)
            if show_soup:
                date_tag = show_soup.find(string=re.compile(
                    r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}'))
                if date_tag:
                    match = re.search(
                        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})[^,]*,?\s*(20\d{2})?',
                        date_tag)
                    if match:
                        try:
                            year = match.group(3) or "2026"
                            date_text = datetime.strptime(f"{match.group(1)} {match.group(2)} {year}", "%B %d %Y").strftime("%Y-%m-%d")
                        except ValueError:
                            pass
            events.append({"source": "covey_center", "name": name, "date": date_text,
                           "venue": "Covey Center for the Arts", "category": category, "url": href})
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    Covey Center: {len(unique)} events")
    return unique


# ── The Ruth and Nathan Hale Theater ─────────────────────────────────────────
def fetch_the_ruth() -> list[dict]:
    now_str = NOW.strftime("%Y-%m-%d")
    events = []
    soup = _get("https://www.theruth.org/tickets")
    if soup:
        for item in soup.select(".production, .show, article, .event-item"):
            name = item.select_one("h2, h3, .title, .production-title")
            date = item.select_one("time, .dates, .run-dates, .date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://www.theruth.org/tickets"
            if url.startswith("/"):
                url = "https://www.theruth.org" + url
            events.append({"source": "the_ruth", "name": name.get_text(strip=True),
                           "date": date.get_text(strip=True)[:10] if date else "",
                           "venue": "The Ruth and Nathan Hale Theater", "category": "Theater", "url": url})
    if not events:
        season = [
            ("Fiddler on the Roof",  "2026-01-30", "2026-03-21"),
            ("Pride and Prejudice",  "2026-04-03", "2026-05-23"),
            ("The Addams Family",    "2026-06-05", "2026-07-25"),
            ("Newsies",              "2026-08-07", "2026-09-26"),
            ("Into the Woods",       "2026-10-09", "2026-11-21"),
            ("A Christmas Carol",    "2026-12-04", "2026-12-23"),
        ]
        for n, start, end in season:
            if end >= now_str:
                events.append({"source": "the_ruth", "name": n, "date": start,
                               "venue": "The Ruth and Nathan Hale Theater",
                               "category": "Theater", "url": "https://tickets.theruth.org/events"})
    print(f"    The Ruth: {len(events)} events")
    return events


# ── SCERA Shell Outdoor Theatre ───────────────────────────────────────────────
def fetch_scera_shell() -> list[dict]:
    events = []
    for path in ["/event-category/scera-shell-outdoor-theatre/",
                 "/event-category/concerts/", "/event-category/live-theater/"]:
        soup = _get(f"https://scera.org{path}")
        if not soup:
            continue
        for item in soup.select("h2, h3"):
            link = item.find("a")
            if not link:
                continue
            name = link.get_text(strip=True)
            if not name or len(name) < 3:
                continue
            url = link["href"] if link.get("href") else "https://scera.org"
            date_tag = item.find_next(string=re.compile(
                r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}'))
            date_text = ""
            if date_tag:
                match = re.search(r'(\w+ \d{1,2})[^,]*,?\s*(20\d{2})?', date_tag)
                if match:
                    try:
                        year = match.group(2) or "2026"
                        date_text = datetime.strptime(f"{match.group(1)} {year}", "%B %d %Y").strftime("%Y-%m-%d")
                    except ValueError:
                        pass
            events.append({"source": "scera_shell", "name": name, "date": date_text,
                           "venue": "SCERA Shell Outdoor Theatre", "category": "Arts & Theater", "url": url})
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    SCERA Shell: {len(unique)} events")
    return unique


# ── SCERA Center ──────────────────────────────────────────────────────────────
def fetch_scera() -> list[dict]:
    events = []
    soup = _get("https://www.scera.org/events/")
    if soup:
        for item in soup.select(".event, article, .tribe-event"):
            name = item.select_one("h2, h3, .entry-title, .tribe-event-url")
            date = item.select_one("time, .tribe-event-date-start, .event-date")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://www.scera.org/events/"
            events.append({"source": "scera", "name": name.get_text(strip=True),
                           "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                           "venue": "SCERA Center for the Arts", "category": "Arts & Theater", "url": url})
    print(f"    SCERA: {len(events)} events")
    return events


# ── The Off Broadway Theatre ──────────────────────────────────────────────────
def fetch_obt() -> list[dict]:
    events = []
    for path in ["/performances", "/2026-season", "/"]:
        soup = _get(f"https://www.theobt.org{path}")
        if not soup:
            continue
        for item in soup.select(".entry-content, .show, .production, article, .performance"):
            name = item.select_one("h1, h2, h3, .entry-title")
            date = item.select_one("time, .dates, .date, .run-dates")
            link = item.select_one("a")
            if not name or len(name.get_text(strip=True)) < 3:
                continue
            text = name.get_text(strip=True)
            if text.lower() in ["home", "about", "contact", "tickets", "donate"]:
                continue
            url = link["href"] if link and link.get("href") else "https://www.theobt.org"
            if url.startswith("/"):
                url = "https://www.theobt.org" + url
            events.append({"source": "obt", "name": f"OBT: {text}",
                           "date": (date.get_text(strip=True)[:10] if date else ""),
                           "venue": "The Off Broadway Theatre", "category": "Comedy", "url": url})
        if events:
            break
    seen = set()
    unique = [e for e in events if e["name"] not in seen and not seen.add(e["name"])]
    print(f"    OBT: {len(unique)} events")
    return unique


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
            events.append({"source": "krcl", "name": name.get_text(strip=True),
                           "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                           "venue": "", "category": category.replace("-", " ").title(), "url": url})
    print(f"    KRCL: {len(events)} events")
    return events


# ── NowPlayingUtah ────────────────────────────────────────────────────────────
def fetch_nowplaying_utah() -> list[dict]:
    events = []
    soup = _get("https://www.nowplayingutah.com/events/")
    if soup:
        for item in soup.select(".event, article, .tribe-event"):
            name = item.select_one("h2, h3, .entry-title, .tribe-event-url")
            date = item.select_one("time, .tribe-event-date-start, .event-date")
            venue = item.select_one(".tribe-venue, .venue, .location")
            link = item.select_one("a")
            if not name:
                continue
            url = link["href"] if link and link.get("href") else "https://www.nowplayingutah.com/events/"
            events.append({"source": "nowplaying_utah", "name": name.get_text(strip=True),
                           "date": date.get("datetime", date.get_text(strip=True))[:10] if date else "",
                           "venue": venue.get_text(strip=True) if venue else "",
                           "category": "Arts & Theater", "url": url})
    print(f"    NowPlayingUtah: {len(events)} events")
    return events


# ── Farmers Markets ───────────────────────────────────────────────────────────
def fetch_farmers_markets() -> list[dict]:
    events = []
    now_str = NOW.strftime("%Y-%m-%d")
    slc_dates = ["2026-06-06","2026-06-13","2026-06-20","2026-06-27",
                 "2026-07-04","2026-07-11","2026-07-18","2026-07-25",
                 "2026-08-01","2026-08-08","2026-08-15","2026-08-22","2026-08-29",
                 "2026-09-05","2026-09-12","2026-09-19","2026-09-26",
                 "2026-10-03","2026-10-10","2026-10-17"]
    for d in slc_dates:
        if d >= now_str:
            events.append({"source": "farmers_market", "name": "SLC Farmers Market at Pioneer Park",
                           "date": d, "venue": "Pioneer Park, Salt Lake City",
                           "category": "Farmers Market", "url": "https://www.slcfarmersmarket.org"})
    tp_dates = ["2026-06-04","2026-06-11","2026-06-18","2026-06-25",
                "2026-07-09","2026-07-16","2026-07-23","2026-07-30",
                "2026-08-06","2026-08-13","2026-08-20","2026-08-27",
                "2026-09-03","2026-09-10","2026-09-17","2026-09-24"]
    for d in tp_dates:
        if d >= now_str:
            events.append({"source": "farmers_market", "name": "Thanksgiving Point Farmers Market",
                           "date": d, "venue": "Thanksgiving Point, Lehi",
                           "category": "Farmers Market", "url": "https://thanksgivingpoint.org"})
    print(f"    Farmers Markets: {len(events)} events")
    return events


# ── Google Events via SerpAPI ─────────────────────────────────────────────────
def fetch_google_events() -> list[dict]:
    api_key = os.environ.get("SERPAPI_API_KEY", "") or os.environ.get("SERPAPI_KEY", "")
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
        events += _serpapi(q, api_key, "", "Event", "")
    print(f"    Google Events: {len(events)} events")
    return events


# ── Combined entry point ──────────────────────────────────────────────────────
def scrape_extra() -> list[dict]:
    all_events = []
    for fn in [
        fetch_ticketmaster_venues,
        fetch_velour,
        fetch_thanksgiving_point,
        fetch_utah_motorsports,
        fetch_byu_events,
        fetch_slcc_events,
        fetch_weber_events,
        fetch_uvu_events,
        fetch_utah_university_events,
        fetch_utah_stadium_events,
        fetch_desert_star,
        fetch_usuo,
        fetch_ski_resort_events,
        fetch_utah_olympic,
        fetch_soldier_hollow,
        fetch_covey_center,
        fetch_the_ruth,
        fetch_scera_shell,
        fetch_scera,
        fetch_obt,
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
