#!/usr/bin/env python3
import os, sys, time, json
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from collections import defaultdict
from datetime import datetime, timezone

API_BASE = "https://v3.football.api-sports.io"
LEAGUES = {39,78,79,61,135,140,203,204}
BUCKETS = [(0,15,'0-15'),(15,30,'15-30'),(30,45,'30-45'),(45,60,'45-60'),(60,75,'60-75'),(75,200,'75-90+')]


def api_get(path, params, key):
    qs = urlencode(params)
    req = Request(f"{API_BASE}{path}?{qs}", headers={"x-apisports-key": key})
    try:
        with urlopen(req, timeout=30) as resp:
            j = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {path}: {e.read().decode('utf-8', 'ignore')}") from e
    if "response" not in j:
        raise RuntimeError(f"Bad API response: {j}")
    return j["response"]


def goal_flags(fixture_id, key):
    flags = {b[2]: False for b in BUCKETS}
    events = api_get("/fixtures/events", {"fixture": fixture_id}, key)
    for e in events:
        if e.get("type") != "Goal":
            continue
        m = int((e.get("time") or {}).get("elapsed") or -1)
        for a,z,k in BUCKETS:
            if a <= m < z:
                flags[k] = True
                break
    return flags


def summarize(ids, key):
    counts = defaultdict(int)
    for fx in ids[:10]:
        try:
            f = goal_flags(fx, key)
            for k,v in f.items():
                if v:
                    counts[k]+=1
        except Exception:
            pass
        time.sleep(0.35)
    return counts


def strongest(rows):
    return [r for r in rows if r[1] >= 8]


def main():
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        print("ERROR: API_FOOTBALL_KEY is not set.")
        return 2

    today = datetime.now(timezone.utc).date().isoformat()
    fixtures = api_get("/fixtures", {"date": today, "timezone": "Europe/London"}, key)
    fixtures = [f for f in fixtures if f.get("league",{}).get("id") in LEAGUES]

    if not fixtures:
        print(f"No fixtures found for target leagues on {today}.")
        return 0

    print(f"Strongest patterns only ({today})")
    print("="*60)
    for f in fixtures:
        league_id = f["league"]["id"]
        home_id = f["teams"]["home"]["id"]
        away_id = f["teams"]["away"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]

        hg = [x["fixture"]["id"] for x in api_get("/fixtures", {"team": home_id, "league": league_id, "last": 5}, key)]
        ag = [x["fixture"]["id"] for x in api_get("/fixtures", {"team": away_id, "league": league_id, "last": 5}, key)]
        hs = [x["fixture"]["id"] for x in api_get("/fixtures", {"team": home_id, "league": league_id, "last": 5, "venue": "home"}, key)]
        aw = [x["fixture"]["id"] for x in api_get("/fixtures", {"team": away_id, "league": league_id, "last": 5, "venue": "away"}, key)]

        g = summarize((hg+ag)[:10], key)
        s = summarize((hs+aw)[:10], key)

        strong_g = strongest([(k, g.get(k,0)) for _,_,k in BUCKETS])
        strong_s = strongest([(k, s.get(k,0)) for _,_,k in BUCKETS])

        if not strong_g and not strong_s:
            continue

        print(f"\n{home} vs {away} ({f['league']['country']} {f['league']['name']})")
        if strong_g:
            print("GENERAL FORM (strongest):", ", ".join([f"{k}={v}/10" for k,v in strong_g]))
        if strong_s:
            print("MATCH SPECIFIC (strongest):", ", ".join([f"{k}={v}/10" for k,v in strong_s]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
