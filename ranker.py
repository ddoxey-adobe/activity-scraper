import json


def rank_events(events: list[dict]) -> list[dict]:
    # Sort by date, soonest first. Events with no date go to the end.
    def sort_key(e):
        return e.get("date") or "9999-99-99"

    sorted_events = sorted(events, key=sort_key)

    # Add a placeholder score and reason so dashboard.py doesn't break
    for e in sorted_events:
        e["score"] = 0
        e["reason"] = ""

    return sorted_events


if __name__ == "__main__":
    with open("events_raw.json") as f:
        events = json.load(f)

    print(f"Sorting {len(events)} events by date...")
    ranked = rank_events(events)

    with open("events_ranked.json", "w") as f:
        json.dump(ranked, f, indent=2)

    print(f"Done! {len(ranked)} events saved to events_ranked.json")
    print("\nNext 10 upcoming events:")
    for e in ranked[:10]:
        print(f"  {e['date']} — {e['name']} @ {e['venue']}")
