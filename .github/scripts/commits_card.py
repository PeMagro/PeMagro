"""Gera assets/commits-dark.svg e commits-light.svg: um card no estilo Claude com o total de commits.

Uso:
  GH_LOGIN=PeMagro GH_TOKEN=... python3 .github/scripts/commits_card.py
  python3 .github/scripts/commits_card.py --placeholder   (card "atualizando...")
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets"
API = "https://api.github.com/graphql"

# Paletas inspiradas no Claude: (fundo, borda, texto, texto suave, terracota, pílula, níveis do mapa)
THEMES = {
    "light": ("#FAF9F5", "#E8E6DC", "#141413", "#87867F", "#D97757", "#F0EEE6",
              ["#EDEAE0", "#F5D3C2", "#EDAA8C", "#D97757", "#A8462A"]),
    "dark": ("#1F1E1D", "#3D3D3A", "#FAF9F5", "#A6A39A", "#D97757", "#2A2927",
             ["#33322F", "#5A3A2C", "#8C4A31", "#C2603F", "#E8845F"]),
}


def gql(token, query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-commits-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch(login, token):
    data = gql(token, """
      query($login: String!) {
        user(login: $login) {
          contributionsCollection {
            contributionYears
            totalCommitContributions
            contributionCalendar { weeks { contributionDays { date contributionCount } } }
          }
        }
      }""", {"login": login})["user"]["contributionsCollection"]

    total = 0
    for year in data["contributionYears"]:
        y = gql(token, """
          query($login: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $login) {
              contributionsCollection(from: $from, to: $to) { totalCommitContributions }
            }
          }""", {"login": login, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        total += y["user"]["contributionsCollection"]["totalCommitContributions"]

    weeks = [[d["contributionCount"] for d in w["contributionDays"]]
             for w in data["contributionCalendar"]["weeks"]]
    days = [c for w in weeks for c in w]

    # sequência atual (hoje sem contribuição ainda não quebra a sequência)
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i] == 0:
        i -= 1
    while i >= 0 and days[i] > 0:
        cur, i = cur + 1, i - 1

    best = run = 0
    for c in days:
        run = run + 1 if c > 0 else 0
        best = max(best, run)

    since = min(data["contributionYears"]) if data["contributionYears"] else date.today().year
    return {
        "total": total,
        "year": data["totalCommitContributions"],
        "streak": cur,
        "best": best,
        "since": since,
        "weeks": weeks[-26:],
    }


def dias(n):
    return f"{n} dia" if n == 1 else f"{n} dias"


def fmt(n):
    return f"{n:,}".replace(",", ".")


def spark(cx, cy, r, color):
    rays = "".join(
        f'<rect x="{cx - 2.6:.1f}" y="{cy - r}" width="5.2" height="{r}" rx="2.6" '
        f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 45)
    )
    return (f'<g fill="{color}"><g class="spin" style="transform-origin:{cx}px {cy}px">'
            f'{rays}</g></g>')


def render(s, theme):
    IVORY, BORDER, INK, MUTED, CLAY, PILL, LEVELS = THEMES[theme]
    ph = s is None
    total = "…" if ph else fmt(s["total"])
    since = "" if ph else f', desde {s["since"]}'
    stats = [
        ("últimos 12 meses", "…" if ph else fmt(s["year"])),
        ("sequência atual", "…" if ph else dias(s["streak"])),
        ("maior sequência", "…" if ph else dias(s["best"])),
    ]
    weeks = [[0] * 7] * 26 if ph else s["weeks"]
    peak = max([c for w in weeks for c in w] + [1])

    cells = []
    for wi, w in enumerate(weeks):
        for di, c in enumerate(w):
            lvl = 0 if c == 0 else min(4, max(1, -(-c * 4 // peak)))
            delay = (wi * 7 + di) * 0.006
            cells.append(
                f'<rect class="c" x="{690 + wi * 17.5:.1f}" y="{62 + di * 17.5:.1f}" '
                f'width="14" height="14" rx="3.5" fill="{LEVELS[lvl]}" '
                f'style="animation-delay:{delay:.3f}s"/>')

    pills, x = [], 64
    for label, value in stats:
        w = 188
        pills.append(
            f'<rect x="{x}" y="224" width="{w}" height="50" rx="12" fill="{PILL}" stroke="{BORDER}"/>'
            f'<text x="{x + 16}" y="244" font-size="12" fill="{MUTED}">{label}</text>'
            f'<text x="{x + 16}" y="264" font-size="16" font-weight="700" fill="{INK}">{value}</text>')
        x += w + 12

    legend = "".join(
        f'<rect x="{1040 + i * 18}" y="196" width="13" height="13" rx="3" fill="{c}"/>'
        for i, c in enumerate(LEVELS))

    now = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
    footer = "sincronizando com o GitHub…" if ph else f"atualizado em {now} · GitHub Actions"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" font-family="'Segoe UI', Helvetica, Arial, sans-serif">
  <style>
    .spin{{animation:spin 14s linear infinite}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    .cur{{animation:blink 1.1s steps(1) infinite}}
    @keyframes blink{{50%{{opacity:0}}}}
    .c{{animation:fade .5s ease-out both}}
    @keyframes fade{{from{{opacity:0}}}}
    .mono{{font-family:ui-monospace,'Cascadia Code',Consolas,monospace}}
    .serif{{font-family:Georgia,'Times New Roman',serif}}
  </style>
  <rect x="1" y="1" width="1198" height="298" rx="20" fill="{IVORY}" stroke="{BORDER}" stroke-width="2"/>

  {spark(80, 66, 14, CLAY)}
  <text x="106" y="72" class="mono" font-size="16" fill="{INK}"><tspan fill="{CLAY}">&gt;</tspan> quantos commits eu já fiz?</text>
  <rect class="cur" x="382" y="57" width="9" height="19" fill="{CLAY}"/>

  <text x="64" y="170" class="serif" font-size="78" fill="{INK}">{total}<tspan dx="16" font-size="36" font-style="italic" fill="{CLAY}">commits</tspan></text>
  <text x="64" y="202" font-size="15" fill="{MUTED}">no total{since}</text>

  {"".join(pills)}

  {"".join(cells)}
  <text x="690" y="206" font-size="12" fill="{MUTED}">últimas 26 semanas</text>
  <text x="1032" y="206" font-size="12" fill="{MUTED}" text-anchor="end">menos</text>
  {legend}
  <text x="1136" y="206" font-size="12" fill="{MUTED}" text-anchor="start">mais</text>

  <text x="1136" y="264" class="mono" font-size="12" fill="{MUTED}" text-anchor="end">{footer}</text>
</svg>
'''


def main():
    if "--placeholder" in sys.argv:
        stats = None
    else:
        login, token = os.environ["GH_LOGIN"], os.environ["GH_TOKEN"]
        stats = fetch(login, token)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (ASSETS / f"commits-{theme}.svg").write_text(render(stats, theme), encoding="utf-8")
    print("ok" + ("" if stats is None else f" total={stats['total']}"))


if __name__ == "__main__":
    main()
