"""
Smart deduplication for events using fuzzy name matching + date/venue context.

Strategy:
1. Exact dedup: same normalized name + same date (already done in scrapers)
2. Fuzzy dedup: similar name + same date → keep the one with more info
3. Venue dedup: same name + same venue + date within 1 day → same event
"""
import json
import re
from difflib import SequenceMatcher


def normalize(text: str) -> str:
    """Lowercase, strip punctuation and common filler words."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)           # remove punctuation
    text = re.sub(r'\b(the|a|an|at|w|with|feat|featuring|presents|live|show|tour)\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def similarity(a: str, b: str) -> float:
    """Return similarity ratio between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def venue_similarity(a: str, b: str) -> float:
    """Venue names can be abbreviated — use partial matching."""
    if not a or not b:
        return 0.5  # unknown venue = neutral, don't penalize
    return similarity(a, b)


def date_distance(d1: str, d2: str) -> int:
    """Return number of days between two YYYY-MM-DD dates. -1 if unparseable."""
    try:
        from datetime import datetime
        a = datetime.strptime(d1, "%Y-%m-%d")
        b = datetime.strptime(d2, "%Y-%m-%d")
        return abs((a - b).days)
    except Exception:
        return -1


def score_quality(event: dict) -> int:
    """
    Score how 'complete' an event record is.
    Higher = more information = prefer to keep this one.
    """
    score = 0
    if event.get("name") and len(event["name"]) > 5:
        score += len(event["name"])          # longer names have more detail
    if event.get("date"):
        score += 10
    if event.get("venue"):
        score += 5
    if event.get("url") and "ticketmaster" in event.get("url", ""):
        score += 3                           # prefer ticketmaster links (have tickets)
    if event.get("reason"):
        score += 20                          # already AI-ranked
    # Prefer certain sources
    preferred = {"ticketmaster", "ticketmaster_venue", "predicthq", "google_events"}
    if event.get("source") in preferred:
        score += 5
    return score


def is_duplicate(e1: dict, e2: dict,
                 name_threshold: float = 0.72,
                 max_date_gap: int = 1) -> bool:
    """
    Returns True if two events are likely the same event.

    Checks:
    - Name similarity above threshold
    - Date within max_date_gap days
    - Venue similarity (if both have venues)
    """
    # Must have dates that are close (or both empty)
    d1, d2 = e1.get("date", ""), e2.get("date", "")
    if d1 and d2:
        gap = date_distance(d1, d2)
        if gap < 0 or gap > max_date_gap:
            return False
    elif d1 != d2:
        # One has a date, one doesn't — don't merge
        return False

    # Name similarity check
    name_sim = similarity(e1.get("name", ""), e2.get("name", ""))
    if name_sim < name_threshold:
        return False

    # If both have venues and they're very different, not a duplicate
    v1, v2 = e1.get("venue", ""), e2.get("venue", "")
    if v1 and v2:
        vsim = venue_similarity(v1, v2)
        if vsim < 0.4:
            return False

    return True


def deduplicate(events: list[dict]) -> tuple[list[dict], int]:
    """
    Deduplicate a list of events using fuzzy matching.
    Returns (deduplicated_list, number_of_duplicates_removed).
    """
    if not events:
        return [], 0

    # Sort by quality descending so we keep the best version
    events_sorted = sorted(events, key=score_quality, reverse=True)

    kept = []
    removed = 0

    for candidate in events_sorted:
        is_dup = False
        for existing in kept:
            if is_duplicate(candidate, existing):
                is_dup = True
                removed += 1
                break
        if not is_dup:
            kept.append(candidate)

    # Re-sort by date
    kept.sort(key=lambda e: e.get("date") or "9999-99-99")
    return kept, removed


if __name__ == "__main__":
    with open("events_raw.json") as f:
        events = json.load(f)

    print(f"Before dedup: {len(events)} events")
    deduped, removed = deduplicate(events)
    print(f"After dedup:  {len(deduped)} events ({removed} duplicates removed)")

    # Show examples of what was merged
    print("\nSample — checking first 200 events for near-duplicates:")
    sample = events[:200]
    for i, e1 in enumerate(sample):
        for e2 in sample[i+1:]:
            sim = similarity(e1.get("name",""), e2.get("name",""))
            gap = date_distance(e1.get("date",""), e2.get("date",""))
            if sim > 0.72 and 0 <= gap <= 1 and e1.get("name") != e2.get("name"):
                print(f"  MERGE: '{e1['name']}' ({e1['source']}) <-> '{e2['name']}' ({e2['source']}) | sim={sim:.2f} | dates: {e1['date']} / {e2['date']}")

    with open("events_raw.json", "w") as f:
        json.dump(deduped, f, indent=2)
    print(f"\nSaved {len(deduped)} deduplicated events to events_raw.json")
