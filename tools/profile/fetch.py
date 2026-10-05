"""Fetch profile data into tools/profile/data/*.json.

No token is required: the contribution calendar comes from GitHub's public
contributions page and everything else from the REST API. If GITHUB_TOKEN is set
(it is in Actions) it is sent with REST calls to avoid the anonymous rate limit.

Every source is fetched independently. A failed request keeps yesterday's value
instead of writing zeroes, and the sync date only moves when the data changes.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.request

USER = "Primav3ra"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("PROFILE_TOKEN")


def get(url, api=False):
    headers = {"User-Agent": f"{USER}-profile"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        body = r.read().decode()
    return json.loads(body) if api else body


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")


DAY = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})" id="(contribution-day-component-[\d-]+)"')
TIP = re.compile(r'for="(contribution-day-component-[\d-]+)"[^>]*>(No|[\d,]+) contributions?')


def calendar(frm=None, to=None):
    url = f"https://github.com/users/{USER}/contributions"
    if frm:
        url += f"?from={frm}&to={to}"
    html = get(url)
    dates = dict((cid, d) for d, cid in DAY.findall(html))
    counts = {cid: 0 if n == "No" else int(n.replace(",", "")) for cid, n in TIP.findall(html)}
    days = {dates[c]: counts.get(c, 0) for c in dates}
    if len(days) < 300:
        raise ValueError(f"calendar looks wrong: {len(days)} days")
    return dict(sorted(days.items()))


def streaks(days):
    ordered = sorted(days.items())
    longest = run = 0
    for _, n in ordered:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current, i = 0, len(ordered) - 1
    if i >= 0 and ordered[i][1] == 0:   # today not started yet: don't reset the streak
        i -= 1
    while i >= 0 and ordered[i][1]:
        current += 1
        i -= 1
    return current, longest


def main():
    stats = load("stats.json", {})
    cal = load("calendar.json", {})
    before = hashlib.sha1(json.dumps([stats, cal], sort_keys=True).encode()).hexdigest()
    ok = []

    try:
        user = get(f"https://api.github.com/users/{USER}", api=True)
        stats.update(name=user.get("name") or USER, followers=user["followers"],
                     public_repos=user["public_repos"], created=user["created_at"][:10])
        ok.append("user")
    except Exception as e:  # noqa: BLE001 - keep yesterday's numbers
        print("user:", e, file=sys.stderr)

    try:
        repos = get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", api=True)
        own = [r for r in repos if not r["fork"]]
        langs = {}
        for r in own:
            for k, v in get(r["languages_url"], api=True).items():
                langs[k] = langs.get(k, 0) + v
        stats.update(stars=sum(r["stargazers_count"] for r in own), languages=langs)
        ok.append("repos")
    except Exception as e:  # noqa: BLE001
        print("repos:", e, file=sys.stderr)

    try:
        cal = calendar()
        today = dt.date.today()
        created = int(stats.get("created", f"{today.year}-01-01")[:4])
        total = 0
        for y in range(created, today.year + 1):
            total += sum(calendar(f"{y}-01-01", f"{y}-12-31").values())
        cur, longest_year = streaks(cal)
        stats.update(last_year=sum(cal.values()), all_time=total, current_streak=cur,
                     longest_streak=max(longest_year, stats.get("longest_streak", 0)),
                     active_days=sum(1 for n in cal.values() if n))
        ok.append("calendar")
    except Exception as e:  # noqa: BLE001
        print("calendar:", e, file=sys.stderr)

    after = hashlib.sha1(json.dumps([stats, cal], sort_keys=True).encode()).hexdigest()
    if after != before:
        stats["updated"] = dt.date.today().isoformat()
    save("stats.json", stats)
    save("calendar.json", cal)
    print("fetched:", ", ".join(ok) or "nothing", "| changed" if after != before else "| unchanged")


if __name__ == "__main__":
    main()
