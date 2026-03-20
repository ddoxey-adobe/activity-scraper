import json
from datetime import datetime


def generate_dashboard(events: list[dict], output: str = "dashboard.html"):
    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    def score_color(s):
        if s >= 8: return "#22c55e"
        if s >= 5: return "#f59e0b"
        return "#94a3b8"

    cards = ""
    for e in events:
        score = e.get("score", 0)
        color = score_color(score)
        reason = e.get("reason", "")
        cards += f"""
        <div class="card" data-score="{score}" data-category="{e.get('category','').lower()}">
          <div class="score-badge" style="background:{color}">{score}/10</div>
          <div class="card-body">
            <a class="event-name" href="{e.get('url','#')}" target="_blank">{e.get('name','')}</a>
            <div class="meta">📅 {e.get('date','')} &nbsp;·&nbsp; 📍 {e.get('venue','')}</div>
            <div class="meta source">via {e.get('source','').capitalize()} · {e.get('category','')}</div>
            <div class="reason">💡 {reason}</div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local Events — Lehi, UT</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0 }}
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh }}
  header {{ background: #1e293b; padding: 1.5rem 2rem; border-bottom: 1px solid #334155 }}
  header h1 {{ font-size: 1.4rem; font-weight: 700 }}
  header p {{ color: #94a3b8; font-size: 0.85rem; margin-top: .25rem }}
  .controls {{ padding: 1rem 2rem; display: flex; gap: .75rem; flex-wrap: wrap }}
  .controls button {{ background: #1e293b; color: #cbd5e1; border: 1px solid #334155;
    padding: .4rem .9rem; border-radius: 999px; cursor: pointer; font-size: .85rem; transition: all .15s }}
  .controls button.active, .controls button:hover {{ background: #6366f1; color: white; border-color: #6366f1 }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1rem; padding: 0 2rem 2rem }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px;
    display: flex; gap: .75rem; padding: 1rem; transition: transform .15s }}
  .card:hover {{ transform: translateY(-2px) }}
  .card.hidden {{ display: none }}
  .score-badge {{ min-width: 52px; height: 52px; border-radius: 10px; display: flex;
    align-items: center; justify-content: center; font-weight: 700; font-size: .9rem; color: #0f172a }}
  .card-body {{ flex: 1; overflow: hidden }}
  .event-name {{ font-weight: 600; color: #f1f5f9; text-decoration: none; display: block;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis }}
  .event-name:hover {{ color: #818cf8 }}
  .meta {{ font-size: .78rem; color: #94a3b8; margin-top: .25rem }}
  .source {{ color: #64748b }}
  .reason {{ font-size: .8rem; color: #cbd5e1; margin-top: .5rem; font-style: italic }}
</style>
</head>
<body>
<header>
  <h1>🗓️ Upcoming Events near Lehi, UT</h1>
  <p>Last updated: {generated} · {len(events)} events ranked by AI</p>
</header>
<div class="controls">
  <button class="active" onclick="filter('all', this)">All</button>
  <button onclick="filter('high', this)">⭐ Score 8+</button>
  <button onclick="filter('music', this)">🎵 Music</button>
  <button onclick="filter('comedy', this)">😂 Comedy</button>
  <button onclick="filter('sports', this)">🏃 Sports</button>
  <button onclick="filter('arts', this)">🎭 Arts</button>
  <button onclick="filter('tech', this)">💻 Tech</button>
  <button onclick="filter('food', this)">🥦 Food</button>
</div>
<div class="grid" id="grid">{cards}</div>
<script>
  function filter(type, btn) {{
    document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.card').forEach(c => {{
      const cat = c.dataset.category;
      const score = parseInt(c.dataset.score);
      let show = type === 'all'
        || (type === 'high' && score >= 8)
        || (type === 'music' && cat.includes('music'))
        || (type === 'comedy' && cat.includes('comedy'))
        || (type === 'sports' && (cat.includes('sport') || cat.includes('run') || cat.includes('fitness')))
        || (type === 'arts' && (cat.includes('art') || cat.includes('theatre') || cat.includes('theater')))
        || (type === 'tech' && (cat.includes('tech') || cat.includes('startup')))
        || (type === 'food' && (cat.includes('food') || cat.includes('market')));
      c.classList.toggle('hidden', !show);
    }});
  }}
</script>
</body>
</html>"""

    with open(output, "w") as f:
        f.write(html)
    print(f"Dashboard written to {output}")


if __name__ == "__main__":
    with open("events_ranked.json") as f:
        events = json.load(f)
    generate_dashboard(events)
