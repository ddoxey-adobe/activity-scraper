import os
import json
import anthropic

INTERESTS = """
- Indie and alternative music (local bands, small venues)
- Theater and performing arts
- Stand-up comedy and improv
- Running events: 5Ks, trail runs, fun runs
- Farmers markets and local food events
- Tech meetups and startup events
"""

BATCH_SIZE = 50


def rank_events(events: list[dict]) -> list[dict]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    ranked = []

    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i:i + BATCH_SIZE]
        events_text = "\n".join(
            f"{j+1}. [{e['date']}] {e['name']} @ {e['venue']} ({e['category']}) — {e['url']}"
            for j, e in enumerate(batch)
        )

        prompt = f"""You are a local event recommender. Here are my interests:
{INTERESTS}

Score each of the following events from 1–10 based on how interesting they'd be for me.
Return ONLY a JSON array where each item has:
  - "index": the event number (1-based)
  - "score": integer 1-10
  - "reason": one sentence explaining the score

Events:
{events_text}
"""

        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = json.loads(raw.strip())

        for s in scores:
            idx = s["index"] - 1
            if 0 <= idx < len(batch):
                event = dict(batch[idx])
                event["score"] = s["score"]
                event["reason"] = s["reason"]
                ranked.append(event)

    ranked.sort(key=lambda e: e.get("score", 0), reverse=True)
    return ranked


if __name__ == "__main__":
    with open("events_raw.json") as f:
        events = json.load(f)

    print(f"Ranking {len(events)} events...")
    ranked = rank_events(events)

    with open("events_ranked.json", "w") as f:
        json.dump(ranked, f, indent=2)

    print("\nTop 10 picks:")
    for e in ranked[:10]:
        print(f"  [{e['score']}/10] {e['name']} on {e['date']} — {e['reason']}")
