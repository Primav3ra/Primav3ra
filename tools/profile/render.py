"""Render the profile console: stacked SVG slices plus README.md.

    python tools/profile/fetch.py    # refresh data/*.json
    python tools/profile/render.py   # write assets/*.svg and README.md

Every slice is 880 px wide (or a 440 px half) with a height that is a multiple
of 40, so the background grid and the neon rails line up across image cuts.
Output is deterministic: the same data always produces byte-identical files.
"""
import base64
import datetime as dt
import html
import io
import json
import math
import os
import random
import re

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, "assets")
USER = "Primav3ra"
W = 880
RAIL_L, RAIL_R = 16, 864
X0, X1 = 52, 828          # content column

# ── palette ──────────────────────────────────────────────────────────────
BG = "#04070c"
GRID = "#0a1620"
BAR = "#06101a"
RAIL = "#22d3ee"
LINE = "#12303d"
TEXT = "#c9d1d9"
WHITE = "#f0f6fc"
DIM = "#5b6b7e"
FAINT = "#344456"
CYAN = "#22d3ee"
SKY = "#67e8f9"
GREEN = "#3fb950"
AMBER = "#fbbf24"
GLOW = 'filter="url(#glow)"'

TIERS = [  # roof, left wall, right wall
    ("#1e3a8a", "#0a1430", "#112257"),
    ("#1d4ed8", "#0b1840", "#132c72"),
    ("#3b82f6", "#0d1d4b", "#17378c"),
    ("#22d3ee", "#0e2446", "#15497a"),
]
GROUND = "#08111b"

# ── fonts: subset each weight to the glyphs a file actually uses ─────────
FONTS = {400: "jbm-400.woff2", 700: "jbm-700.woff2", 800: "jbm-800.woff2"}


def face(weight, chars):
    f = TTFont(os.path.join(HERE, "fonts", FONTS[weight]), recalcTimestamp=False)
    opts = subset.Options()
    opts.flavor = "woff2"
    s = subset.Subsetter(opts)
    s.populate(text=chars + " ")
    s.subset(f)
    buf = io.BytesIO()
    f.flavor = "woff2"
    f.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'JBM';font-weight:{weight};src:url(data:font/woff2;base64,{b64})}}"


TEXT_RE = re.compile(r"<text([^>]*)>(.*?)</text>", re.S)


def fonts_for(body):
    used = {}
    for attrs, inner in TEXT_RE.findall(body):
        m = re.search(r'font-weight="(\d+)"', attrs)
        w = int(m.group(1)) if m else 400
        used.setdefault(w, set()).update(html.unescape(re.sub(r"<[^>]+>", "", inner)))
        for tw, tinner in re.findall(r'<tspan[^>]*font-weight="(\d+)"[^>]*>(.*?)</tspan>', inner):
            used.setdefault(int(tw), set()).update(html.unescape(tinner))
    return "".join(face(w, "".join(sorted(c))) for w, c in sorted(used.items()))


def esc(s):
    return html.escape(s, quote=False)


def t(x, y, s, size=14, fill=TEXT, weight=400, anchor="start", extra=""):
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" {extra}>{s}</text>')


def span(s, fill=None, weight=None):
    a = (f' fill="{fill}"' if fill else "") + (f' font-weight="{weight}"' if weight else "")
    return f"<tspan{a}>{esc(s)}</tspan>"


def adv(size):   # JetBrains Mono advance is 600/1000 em
    return .6 * size


def wrap(s, size, width):
    per = int(width // adv(size))
    lines, cur = [], ""
    for word in s.split():
        if len(cur) + len(word) + (1 if cur else 0) > per:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur]


# ── slice scaffold ───────────────────────────────────────────────────────
def slice_svg(name, h, body, title, desc="", x_off=0, w=W, top=False, bottom=False, css=""):
    assert h % 40 == 0, f"{name}: height {h} breaks the grid"
    rails = ""
    for rx in (RAIL_L, RAIL_R):
        lx = rx - x_off
        if 0 <= lx <= w:
            y1 = 16 if top else 0
            y2 = h - 16 if bottom else h
            rails += f'<line x1="{lx}" y1="{y1}" x2="{lx}" y2="{y2}"/>'
    edges = ""
    if top:
        edges += (f'<line x1="{RAIL_L - x_off}" y1="16" x2="{RAIL_R - x_off}" y2="16"/>'
                  f'<path d="M8 40V8H40M{W - 40} 8H{W - 8}V40" fill="none"/>')
    if bottom:
        edges += (f'<line x1="{RAIL_L - x_off}" y1="{h - 16}" x2="{RAIL_R - x_off}" y2="{h - 16}"/>'
                  f'<path d="M8 {h - 40}V{h - 8}H40M{W - 40} {h - 8}H{W - 8}V{h - 40}" fill="none"/>')
    frame = (f'<g stroke="{RAIL}" stroke-width="1.5" filter="url(#glow)">{rails}{edges}</g>'
             if rails or edges else "")
    defs = (f'<defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse" '
            f'patternTransform="translate({-x_off % 40} 0)"><path d="M40 0H0V40" fill="none" stroke="{GRID}"/></pattern>'
            f'<filter id="glow" filterUnits="userSpaceOnUse" x="-20" y="-20" width="{w + 40}" height="{h + 40}">'
            f'<feGaussianBlur stdDeviation="3.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/>'
            f'<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
    style = (fonts_for(body) + "text{font-family:'JBM',ui-monospace,monospace;white-space:pre}" + css
             + "@media (prefers-reduced-motion:reduce){*{animation:none!important}.motion{display:none}}")
    out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'role="img" aria-labelledby="t d"><title id="t">{esc(title)}</title><desc id="d">{esc(desc or title)}</desc>'
           f'<style>{style}</style>{defs}<rect width="{w}" height="{h}" fill="{BG}"/>'
           f'<rect width="{w}" height="{h}" fill="url(#grid)"/>{body}{frame}</svg>')
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"{name:26s} {len(out) / 1024:6.1f} KB")


def heading(y, name, num):
    return (t(X0, y, span("~/", CYAN, 800) + span(name, WHITE, 800), 21, extra='filter="url(#glow)"')
            + t(X1, y, esc(f"// {num:02d}"), 12, DIM, anchor="end", extra='letter-spacing="2"')
            + f'<line x1="{X0}" y1="{y + 14}" x2="{X1}" y2="{y + 14}" stroke="{LINE}"/>'
            + f'<line x1="{X0}" y1="{y + 14}" x2="{X0 + 120}" y2="{y + 14}" stroke="{CYAN}" stroke-width="2"/>')


def prompt(y, cmd, comment=""):
    s = span("$ ", GREEN) + span(cmd, DIM) + (span("  # " + comment, FAINT) if comment else "")
    return t(X0 - 4, y, s, 14)


# ── header ───────────────────────────────────────────────────────────────
STATUS = "OPEN TO WORK · HYDERABAD, IN"


def header():
    # The first frame already shows the first role in full, so a viewer that
    # never runs SMIL (thumbnails, some apps) still gets a complete header.
    h, ny = 400, 182
    roles = ["software developer", "data analyst", "geospatial analyst", "business development",
             "open-source contributor"]
    size, ry = 19, 228
    cw = adv(size)
    rx = X0 + cw * 2                       # after the "> " prefix
    typ, hold, erase = 1.1, 2.4, .5
    P = hold + erase + (len(roles) - 1) * (typ + hold + erase) + typ

    def steps(n, start, dur, up):
        return [(start + dur * k / n, k if up else n - k) for k in range(1, n + 1)]

    typed = ""
    for i, role in enumerate(roles):
        n = len(role)
        if i == 0:
            ev = [(0, n)] + steps(n, hold, erase, False) + steps(n, P - typ, typ, True)[:-1]
            vis, vis_t = "1;0;1", f"0;{(hold + erase) / P:.4f};{(P - typ) / P:.4f}"
        else:
            st = hold + erase + (i - 1) * (typ + hold + erase)
            ev = [(0, 0)] + steps(n, st, typ, True) + steps(n, st + typ + hold, erase, False)
            vis, vis_t = "0;1;0", f"0;{st / P:.4f};{(st + typ + hold + erase) / P:.4f}"
        kt = ";".join(f"{tm / P:.4f}" for tm, _ in ev)
        wv = ";".join(f"{cw * k:.1f}" for _, k in ev)
        xv = ";".join(f"{rx + cw * k + 2:.1f}" for _, k in ev)
        anim = f'calcMode="discrete" dur="{P:.2f}s" repeatCount="indefinite"'
        typed += (f'<clipPath id="r{i}"><rect x="{rx - 1}" y="{ry - 22}" height="30" width="{cw * n if i == 0 else 0:.1f}">'
                  f'<animate attributeName="width" values="{wv}" keyTimes="{kt}" {anim}/></rect></clipPath>'
                  f'<g clip-path="url(#r{i})">{t(rx, ry, esc(role), size, CYAN, 700, extra=GLOW)}</g>'
                  f'<g class="cursor"><rect x="{rx + cw * (n if i == 0 else 0) + 2:.1f}" y="{ry - 17}" width="{cw * .6:.1f}" '
                  f'height="21" fill="{CYAN}" opacity="{1 if i == 0 else 0}">'
                  f'<animate attributeName="x" values="{xv}" keyTimes="{kt}" {anim}/>'
                  f'<animate attributeName="opacity" values="{vis}" keyTimes="{vis_t}" {anim}/></rect></g>')
    typed = t(X0, ry, span("> ", DIM, 700), size) + typed
    name = t(X0, ny, esc("Mehul Karwa"), 54, WHITE, 800)
    rows = [("edu", "B.Tech Data Science · Manipal University Jaipur · 2026"),
            ("prev", "backend SDE intern @ TrueFoundry · AI gateway & LLMOps"),
            ("now", "operations & business development · family business"),
            ("focus", "open-source contributions"),
            ("seeking", "full-time roles · India or remote · open to relocation")]
    kv = "".join(t(X0, 270 + i * 26, span(f"{k:<9}", DIM) + span(v, TEXT if k != "seeking" else SKY), 14)
                 for i, (k, v) in enumerate(rows))
    bar = (f'<rect x="{RAIL_L}" y="16" width="{RAIL_R - RAIL_L}" height="36" fill="{BAR}"/>'
           f'<line x1="{RAIL_L}" y1="52" x2="{RAIL_R}" y2="52" stroke="{LINE}"/>'
           + t(32, 39, span("mehul", CYAN, 700) + span("@", DIM) + span("primav3ra", CYAN, 700) + span(":~", DIM), 13)
           + f'<circle cx="{X1 + 16 - len(STATUS) * (adv(12) + 1.5) - 14:.1f}" cy="34" r="4" fill="{GREEN}" class="pulse"/>'
           + t(X1 + 16, 39, esc(STATUS), 12, DIM, anchor="end", extra='letter-spacing="1.5"'))
    body = bar + prompt(112, "whoami") + name + typed + kv
    css = (".cursor{animation:blink 1.06s step-end infinite}@keyframes blink{50%{opacity:0}}"
           ".pulse{animation:pulse 2.4s ease-in-out infinite}@keyframes pulse{50%{opacity:.35}}")
    slice_svg("header.svg", h, body, "Mehul Karwa",
              "Software developer, data analyst, geospatial analyst and business development. B.Tech Data Science, "
              "Manipal University Jaipur 2026. Previously backend SDE intern at TrueFoundry. Open to full-time roles "
              "in India or remote, open to relocation.", top=True, css=css)


# ── links ────────────────────────────────────────────────────────────────
ICONS = json.load(open(os.path.join(HERE, "icons.json"), encoding="utf-8"))


def icon(slug, x, y, size, fill):
    k = size / 24
    return f'<path transform="translate({x:g} {y:g}) scale({k:.4f})" d="{ICONS[slug]}" fill="{fill}"/>'


def links():
    body = heading(48, "links", 1) + prompt(100, "ping mehul --all-channels")
    slice_svg("links.svg", 120, body, "Links")
    tiles = [("link-linkedin.svg", "linkedin", "LinkedIn", "in/mehul-karwa-424346254"),
             ("link-email.svg", "gmail", "Email", "mehulkarwa7@gmail.com")]
    for i, (fname, slug, label, sub) in enumerate(tiles):
        x_off = 440 * i
        bx = (X0 if i == 0 else 452) - x_off
        bw = 376
        body = (f'<rect x="{bx}" y="8" width="{bw}" height="64" rx="4" fill="{BAR}" stroke="{LINE}"/>'
                f'<rect x="{bx}" y="8" width="3" height="64" fill="{CYAN}"/>'
                + icon(slug, bx + 22, 28, 24, CYAN)
                + t(bx + 62, 37, esc(label), 15, WHITE, 700)
                + t(bx + 62, 57, esc(sub), 12.5, DIM)
                + t(bx + bw - 18, 46, "↗", 16, CYAN, 700, "end"))
        slice_svg(fname, 80, body, label, f"{label}: {sub}", x_off=x_off, w=440)


# ── stats ────────────────────────────────────────────────────────────────
def stats_slice(s):
    created = dt.date.fromisoformat(s["created"])
    cells = [(f'{s["last_year"]:,}', "contributions · 365d"), (f'{s["all_time"]:,}', "total contributions"),
             (str(s["active_days"]), "active days · 365d"), (f'{s["longest_streak"]}d', "longest streak"),
             (f'{s["current_streak"]}d', "current streak"), (str(s["public_repos"]), "public repos"),
             ("1", "MOSS Hack '26 win"), (created.strftime("%b %Y"), "member since")]
    body = heading(48, "stats", 2) + prompt(100, f"gh stats --user {USER}")
    cw, chh = (X1 - X0) / 4, 76
    for i, (v, label) in enumerate(cells):
        x, y = X0 + (i % 4) * cw, 132 + (i // 4) * (chh + 12)
        body += (f'<rect x="{x:g}" y="{y}" width="{cw - 12:g}" height="{chh}" rx="4" fill="{BAR}" stroke="{LINE}"/>'
                 + t(x + 16, y + 36, esc(v), 24, CYAN, 800, extra='filter="url(#glow)"')
                 + t(x + 16, y + 60, esc(label), 11.5, DIM))
    langs = sorted(s["languages"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in langs)
    top = [(k, v / total) for k, v in langs[:5]]
    top.append(("Other", 1 - sum(p for _, p in top)))
    shades = ["#22d3ee", "#3b82f6", "#6366f1", "#0ea5e9", "#1e40af", FAINT]
    y = 330
    body += t(X0, y, span("top languages ", WHITE, 700) + span("by bytes, own repos", DIM), 13)
    x = X0
    bar_w = X1 - X0
    for (k, p), c in zip(top, shades):
        seg = bar_w * p
        body += f'<rect x="{x:.1f}" y="{y + 14}" width="{max(seg - 2, 0):.1f}" height="10" fill="{c}"/>'
        x += seg
    lx = X0
    for (k, p), c in zip(top, shades):
        label = f"{k} {p * 100:.1f}%"
        body += f'<rect x="{lx}" y="{y + 42}" width="9" height="9" fill="{c}"/>' + t(lx + 15, y + 51, esc(label), 12, TEXT)
        lx += 15 + adv(12) * len(label) + 22
    body += t(X1, 420, esc(f"// last sync {s.get('updated', '')}"), 11.5, FAINT, anchor="end")
    desc = (f'{s["last_year"]:,} contributions in the last 365 days, {s["all_time"]:,} all time; '
            f'{s["active_days"]} active days; longest streak {s["longest_streak"]} days; {s["public_repos"]} public repos; '
            f'member since {created:%B %Y}. Top languages: ' + ", ".join(f"{k} {p * 100:.1f}%" for k, p in top))
    slice_svg("stats.svg", 440, body, "Stats", desc)
    return desc


# ── contribution city ────────────────────────────────────────────────────
def city(cal):
    h, s = 720, 12.6
    ox, oy = 150, 262
    days = sorted((dt.date.fromisoformat(d), n) for d, n in cal.items())
    start = days[0][0] - dt.timedelta(days=(days[0][0].weekday() + 1) % 7)   # back to Sunday
    grid = {}
    for d, n in days:
        k = (d - start).days
        grid[(k // 7, k % 7)] = (d, n)
    cols = max(c for c, _ in grid) + 1
    cmax = max(n for _, n in grid.values()) or 1
    rng = random.Random(f"{USER}-city")

    def P(c, r, z=0.0):
        return ox + (c - r) * s, oy + (c + r) * s / 2 - z

    def poly(pts, fill, extra=""):
        return f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="{fill}" {extra}/>'

    out = [poly([P(0, 0), P(cols, 0), P(cols, 7), P(0, 7)], GROUND)]
    lines = "".join(f'M{P(c, 0)[0]:.1f} {P(c, 0)[1]:.1f}L{P(c, 7)[0]:.1f} {P(c, 7)[1]:.1f}' for c in range(cols + 1))
    lines += "".join(f'M{P(0, r)[0]:.1f} {P(0, r)[1]:.1f}L{P(cols, r)[0]:.1f} {P(cols, r)[1]:.1f}' for r in range(8))
    out.append(f'<path d="{lines}" stroke="#0e1c2a" stroke-width=".8" fill="none"/>')

    flicker = 0
    a = .11
    for (c, r) in sorted(grid, key=lambda cr: (cr[0] + cr[1], cr[0])):
        d, n = grid[(c, r)]
        if not n:
            continue
        q = math.sqrt(n / cmax)
        z = 8 + 110 * q
        tier = 0 if q < .35 else 1 if q < .55 else 2 if q < .78 else 3
        roof, left, right = TIERS[tier]
        cx, cy = c + .5, r + .5
        Nn, E, S, Ww = (cx - .5 + a, cy - .5 + a), (cx + .5 - a, cy - .5 + a), (cx + .5 - a, cy + .5 - a), (cx - .5 + a, cy + .5 - a)
        out.append(poly([P(*Ww), P(*S), P(*S, z), P(*Ww, z)], left))
        out.append(poly([P(*S), P(*E), P(*E, z), P(*S, z)], right))
        out.append(poly([P(*Nn, z), P(*E, z), P(*S, z), P(*Ww, z)], roof))
        # windows: two columns per wall, one row every 7 px
        lit_p = .25 + .5 * q
        for face, (A, B) in (("l", (Ww, S)), ("r", (S, E))):
            for col_t in (.22, .58):
                fz = 6.0
                while fz + 3 < z - 4:
                    if rng.random() < lit_p:
                        t0, t1 = col_t, col_t + .2
                        pa = (A[0] + (B[0] - A[0]) * t0, A[1] + (B[1] - A[1]) * t0)
                        pb = (A[0] + (B[0] - A[0]) * t1, A[1] + (B[1] - A[1]) * t1)
                        cls = ""
                        if flicker < 46 and rng.random() < .06:
                            flicker += 1
                            cls = f'class="fl" style="animation-delay:{rng.uniform(0, 9):.2f}s"'
                        shade = SKY if rng.random() < .7 else "#a5f3fc"
                        out.append(poly([P(*pa, fz), P(*pb, fz), P(*pb, fz + 2.6), P(*pa, fz + 2.6)], shade,
                                        f'opacity="{.55 + .4 * q:.2f}" {cls}'))
                    fz += 7

    stars = "".join(f'<circle cx="{rng.uniform(X0, X1):.1f}" cy="{rng.uniform(130, 260):.1f}" '
                    f'r="{rng.choice([.6, .8, 1.1]):g}" fill="#cbd5e1" '
                    + (f'class="tw" style="animation-delay:{rng.uniform(0, 4):.1f}s"' if rng.random() < .35 else 'opacity=".55"')
                    + "/>" for _ in range(70))
    moon = (f'<defs><mask id="crescent"><rect width="{W}" height="{h}" fill="#fff"/>'
            f'<circle cx="796" cy="152" r="17" fill="#000"/></mask>'
            f'<radialGradient id="halo"><stop offset="0" stop-color="#e2e8f0" stop-opacity=".22"/>'
            f'<stop offset="1" stop-color="#e2e8f0" stop-opacity="0"/></radialGradient></defs>'
            f'<circle cx="786" cy="160" r="46" fill="url(#halo)"/>'
            f'<circle cx="786" cy="160" r="19" fill="#e2e8f0" mask="url(#crescent)"/>')
    # an earth-observation satellite instead of a plane
    sat = (f'<g class="motion"><g fill="{SKY}">'
           f'<rect x="-3" y="-3" width="6" height="6"/><rect x="-16" y="-2" width="11" height="4" opacity=".7"/>'
           f'<rect x="5" y="-2" width="11" height="4" opacity=".7"/></g>'
           f'<circle r="1.6" cy="5" fill="#f87171" class="nav"/>'
           f'<animateTransform attributeName="transform" type="translate" values="-40 200;920 132" dur="38s" repeatCount="indefinite"/></g>')
    busiest_d, busiest_n = max(grid.values(), key=lambda dn: (dn[1], dn[0]))
    total = sum(n for _, n in grid.values())
    active = sum(1 for _, n in grid.values() if n)
    info = (t(X1, 236, span(f"{total:,}", CYAN, 800) + span(" contributions · last 365 days", DIM), 12.5, anchor="end")
            + t(X1, 258, span("busiest day ", DIM) + span(f"{busiest_d:%b} {busiest_d.day}", WHITE, 700)
                + span(f" · {busiest_n}", DIM), 12.5, anchor="end")
            + t(X1, 280, span(f"{active}", WHITE, 700) + span(" active days", DIM), 12.5, anchor="end"))
    legend = t(X0, 690, span("quiet", DIM), 11.5)
    for i, col in enumerate([GROUND] + [tr[0] for tr in TIERS]):
        legend += f'<rect x="{X0 + 52 + i * 15}" y="680" width="11" height="11" fill="{col}" stroke="{LINE}" stroke-width=".6"/>'
    legend += t(X0 + 52 + 5 * 15 + 8, 690, span("skyscraper", DIM), 11.5)
    body = (heading(48, "contribution-city", 3) + prompt(100, "render-city --last 365d", "one building per day")
            + stars + moon + sat + "".join(out) + info + legend)
    css = (".fl{animation:fl 9s steps(1) infinite}@keyframes fl{0%,100%{opacity:.9}46%{opacity:.08}52%{opacity:.9}}"
           ".tw{animation:tw 4s ease-in-out infinite}@keyframes tw{50%{opacity:.15}}"
           ".nav{animation:blink 1s step-end infinite}@keyframes blink{50%{opacity:0}}")
    desc = (f"Contribution city: an isometric night skyline with one building per day of the last year, taller and "
            f"brighter for busier days. {total:,} contributions, busiest day {busiest_d:%B} {busiest_d.day} with {busiest_n}.")
    slice_svg("contribution-city.svg", h, body, "Contribution city", desc, css=css)
    return desc


# ── experience ───────────────────────────────────────────────────────────
def experience():
    rows = [
        (GREEN, "INFO", "2025-06", [("joined ", TEXT), ("TrueFoundry", WHITE), (" as backend SDE intern  ", TEXT),
                                    ("# AI gateway & LLMOps, Sequoia-backed", FAINT)]),
        (None, "", "", [("├─ benchmarked Apache DataFusion vs ClickHouse for LLM traces on S3 Parquet", TEXT)]),
        (None, "", "", [("├─ built gateway observability: logs, token usage, cost per model, span traces", TEXT)]),
        (None, "", "", [("├─ wrote an async OpenTelemetry exporter over NATS → S3, GCS, Azure Blob", TEXT)]),
        (None, "", "", [("└─ merged ", TEXT), ("100+ pull requests", CYAN), (" across Python, Rust, Go, TypeScript", TEXT)]),
        (GREEN, "INFO", "2026-01", [("internship complete", TEXT)]),
        (AMBER, "NOW ", "2026   ", [("operations & business development in the family business", TEXT)]),
        (AMBER, "NOW ", "2026   ", [("contributing to open source · looking for a full-time role", SKY)]),
    ]
    body = heading(48, "experience", 4) + prompt(100, "tail career.log")
    y = 140
    for lvl_c, lvl, date, parts in rows:
        prefix = (span(f"{lvl:<5}", lvl_c, 700) + span(f"{date:<9}", DIM)) if lvl else span(" " * 14)
        body += t(X0, y, prefix + "".join(span(p, c) for p, c in parts), 13.5)
        y += 26
    slice_svg("experience.svg", 360, body, "Experience",
              "Backend SDE intern at TrueFoundry, June 2025 to January 2026: benchmarked Apache DataFusion against "
              "ClickHouse for LLM traces, built AI gateway observability, wrote an async OpenTelemetry exporter over "
              "NATS, merged 100+ pull requests. Now in operations and business development, and contributing to open source.")


# ── projects ─────────────────────────────────────────────────────────────
PROJECTS = [
    ("card-mantis.svg", "https://github.com/Harigithub11/Mantis", "mantis", "★ MOSS HACK '26 WINNER",
     "AI repair technician that diagnoses product faults from the manufacturer's own manuals, with page-level "
     "citations, photo reading and step-by-step repair flowcharts.", ["fastapi", "next.js", "gemini", "moss"]),
    ("card-solaris.svg", "https://github.com/Primav3ra/SOLARIS-Rooftop-Solar-Mapping", "solaris", "CAPSTONE · GEOSPATIAL",
     "Rooftop solar yield for every building in a city, computed on Google Earth Engine. Shows Indian roofs lose "
     "24–31% of yield to neighbours' shade.", ["earth-engine", "pvlib", "fastapi", "maplibre"]),
    ("card-mehullm.svg", "https://github.com/Primav3ra/MehuLLM", "mehullm", "PERSONAL AI AGENT",
     "Cloud LLMs reason while a LoRA-tuned Qwen3-1.7B writes in my style. 419K messages processed on-device, "
     "Indian PII scrubbing, 15 ms hybrid search.", ["pytorch", "unsloth", "sqlite-vec", "mcp"]),
    ("card-construction.svg", "https://github.com/Primav3ra/Construction-Intelligence-Map", "construction-intel",
     "GEOSPATIAL SALES INTEL",
     "Turns public building-permission records into a weekly ranked lead list for cement distributors in "
     "Hyderabad, refreshed by GitHub Actions.", ["playwright", "pandas", "react", "leaflet"]),
]


def projects():
    slice_svg("projects.svg", 120, heading(48, "projects", 5) + prompt(100, "ls ~/projects --featured"), "Projects")
    for i, (fname, _, name, badge, desc, tags) in enumerate(PROJECTS):
        x_off = 440 * (i % 2)
        bx = (X0 if i % 2 == 0 else 452) - x_off
        bw, bh = 376, 216
        gold = "WINNER" in badge
        body = (f'<rect x="{bx}" y="8" width="{bw}" height="{bh}" rx="4" fill="{BAR}" stroke="{AMBER if gold else LINE}" '
                f'stroke-opacity="{.55 if gold else 1}"/>'
                + t(bx + 20, 44, span("./", DIM) + span(name, WHITE, 800), 18)
                + t(bx + 20, 68, esc(badge), 11, AMBER if gold else CYAN, 700, extra='letter-spacing="1.2"'))
        y = 100
        for ln in wrap(desc, 12.5, bw - 40):
            body += t(bx + 20, y, esc(ln), 12.5, TEXT)
            y += 20
        assert y < 190, f"{name}: description too long"
        tx = bx + 20
        for tag in tags:
            label = f"[{tag}]"
            body += t(tx, 204, esc(label), 11.5, DIM)
            tx += adv(11.5) * len(label) + 8
        slice_svg(fname, 240, body, name, f"{name}: {badge.lower()}. {desc} {', '.join(tags)}.", x_off=x_off, w=440)


# ── stack ────────────────────────────────────────────────────────────────
STACK = [
    ("languages", [("python", "Python"), ("typescript", "TypeScript"), ("rust", "Rust"), ("go", "Go"),
                   ("postgresql", "SQL")]),
    ("ml & ai", [("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"), ("huggingface", "HuggingFace"),
                 ("scikitlearn", "sklearn"), ("pandas", "pandas"), ("numpy", "NumPy"), ("ollama", "Ollama"),
                 ("modelcontextprotocol", "MCP")]),
    ("data", [("apache", "DataFusion"), ("clickhouse", "ClickHouse"), ("apacheparquet", "Parquet"),
              ("apachespark", "Spark"), ("postgresql", "PostgreSQL"), ("mysql", "MySQL"), ("mongodb", "MongoDB"),
              ("sqlite", "SQLite")]),
    ("geospatial", [("googleearthengine", "Earth Engine"), ("maplibre", "MapLibre"), ("leaflet", "Leaflet"),
                    ("openstreetmap", "OSM")]),
    ("backend & web", [("fastapi", "FastAPI"), ("nodedotjs", "Node.js"), ("natsdotio", "NATS"), ("react", "React"),
                       ("nextdotjs", "Next.js"), ("tailwindcss", "Tailwind"), ("playwright", "Playwright")]),
    ("cloud & ops", [("amazonwebservices", "AWS"), ("googlecloud", "GCP"), ("microsoftazure", "Azure"),
                     ("docker", "Docker"), ("opentelemetry", "OTel"), ("githubactions", "Actions"), ("sentry", "Sentry"),
                     ("git", "Git")]),
]


def stack():
    body = heading(48, "stack", 6) + prompt(100, "scan --loadout")
    y0, rh, cell = 132, 62, 78
    for r, (group, items) in enumerate(STACK):
        y = y0 + r * rh
        body += t(X0, y + 30, span(group, CYAN, 700) + span("/", DIM), 13)
        for i, (slug, name) in enumerate(items):
            cx = X0 + 150 + cell * i + cell / 2
            body += icon(slug, cx - 11, y + 6, 22, "#9fb3c8") + t(cx, y + 48, esc(name), 10.5, DIM, anchor="middle")
    h = math.ceil((y0 + rh * len(STACK) + 8) / 40) * 40
    slice_svg("stack.svg", h, body, "Tech stack",
              "Tech stack. " + " ".join(f"{g}: {', '.join(n for _, n in it)}." for g, it in STACK))


# ── achievements ─────────────────────────────────────────────────────────
def achievements():
    rows = [("★", AMBER, "winner", "MOSS Hack '26 with Mantis"),
            ("◆", CYAN, "runner-up", "EY Techathon 5.0 · 2nd of 400+ teams"),
            ("◆", CYAN, "ielts 8.0", "English proficiency · CEFR C1"),
            ("◆", CYAN, "design lead", "Manipal Alumni Relations · led an 8-member team"),
            ("◆", CYAN, "volunteer", "STEM teacher for 100+ rural students · Rotaract"),
            ("◆", CYAN, "coordination", "15+ global speakers · Jaipur Literature Festival")]
    body = heading(48, "achievements", 7) + prompt(100, "cat achievements.txt")
    for i, (mark, c, k, v) in enumerate(rows):
        body += t(X0, 140 + i * 26, span(mark + " ", c, 700) + span(f"{k:<14}", WHITE, 700) + span(v, TEXT), 13.5)
    slice_svg("achievements.svg", 280, body, "Achievements",
              "Winner of MOSS Hack '26 with Mantis; runner-up at EY Techathon 5.0, 2nd of 400+ teams; IELTS 8.0; "
              "design lead at Manipal Alumni Relations; volunteer STEM teacher; speaker coordination at Jaipur Literature Festival.")


def footer():
    body = (t(X0, 44, span("$ ", GREEN) + span("exit", TEXT), 14)
            + t(X0, 68, span("connection to ", TEXT) + span("primav3ra", CYAN, 700) + span(" closed. ", TEXT)
                + span("// EOF", FAINT), 14))
    slice_svg("footer.svg", 120, body, "Connection closed.", bottom=True)


# ── README ───────────────────────────────────────────────────────────────
def readme(stats_desc, city_desc):
    img = lambda f, alt, w="100%": f'<img src="./assets/{f}" width="{w}" align="top" alt="{html.escape(alt)}">'
    cards = [f'<a href="{url}">' + img(f, f"{n}: {b.lower()}. {d}", "50%") + "</a>"
             for f, url, n, b, d, _ in PROJECTS]
    parts = [
        "<!-- Generated by tools/profile/render.py — edit that file, not this one. -->",
        '<p align="center">',
        img("header.svg", "Mehul Karwa: software developer, data analyst, geospatial analyst, business development. "
                          "B.Tech Data Science, Manipal University Jaipur 2026. Open to full-time roles."),
        img("links.svg", "Links"),
        '<a href="https://www.linkedin.com/in/mehul-karwa-424346254">' + img("link-linkedin.svg", "LinkedIn", "50%")
        + '</a><a href="mailto:mehulkarwa7@gmail.com">' + img("link-email.svg", "Email: mehulkarwa7@gmail.com", "50%") + "</a>",
        img("stats.svg", stats_desc),
        img("contribution-city.svg", city_desc),
        img("experience.svg", "Experience: backend SDE intern at TrueFoundry, June 2025 to January 2026."),
        img("projects.svg", "Projects"),
        cards[0] + cards[1],
        cards[2] + cards[3],
        img("stack.svg", "Tech stack: Python, TypeScript, Rust, Go, PyTorch, Hugging Face, DataFusion, ClickHouse, "
                         "Earth Engine, FastAPI, React, AWS, GCP, Azure, Docker, OpenTelemetry and more."),
        img("achievements.svg", "Achievements: MOSS Hack '26 winner, EY Techathon 5.0 runner-up, IELTS 8.0."),
        img("footer.svg", "Connection closed."),
        "</p>",
    ]
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    stats = json.load(open(os.path.join(HERE, "data", "stats.json"), encoding="utf-8"))
    cal = json.load(open(os.path.join(HERE, "data", "calendar.json"), encoding="utf-8"))
    header()
    links()
    sd = stats_slice(stats)
    cd = city(cal)
    experience()
    projects()
    stack()
    achievements()
    footer()
    readme(sd, cd)


if __name__ == "__main__":
    main()
