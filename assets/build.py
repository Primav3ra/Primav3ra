"""Generates the SVG plates used in the profile README.

Run from the repo root:  python assets/build.py
Needs: numpy, matplotlib, fonttools, brotli. Downloads Archivo and simple-icons on first run.
"""
import base64, io, os, re, urllib.request
from functools import lru_cache

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
os.makedirs(CACHE, exist_ok=True)

# ── tokens ────────────────────────────────────────────────────────────────
ABYSS = "#0B1D2C"   # page of the chart
DEEP = "#102638"    # plate surface
LINE = "#1F4863"    # contours, rules, outlines
TIDE = "#7FAFC8"    # secondary text
CHALK = "#EAF0F2"   # primary text
SOLAR = "#F2B544"   # the one accent

FONT_URL = "https://github.com/google/fonts/raw/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf"
ICON_URL = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{}.svg"


def fetch(url, name):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


# ── font: subset once, embed everywhere, measure with static instances ───
TTF = fetch(FONT_URL, "Archivo.ttf")
CHARS = "".join(chr(c) for c in range(32, 127)) + "°–—’‘“”×•é"


def font_face():
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    f = TTFont(TTF)
    s = subset.Subsetter(opts)
    s.populate(text=CHARS)
    s.subset(f)
    buf = io.BytesIO()
    f.flavor = "woff2"
    f.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return ("@font-face{font-family:'A';src:url(data:font/woff2;base64,%s) format('woff2');"
            "font-weight:100 900;font-stretch:62%% 125%%;}" % b64)


FACE = font_face()


@lru_cache(None)
def instance(wght, wdth):
    f = TTFont(TTF)
    inst = instancer.instantiateVariableFont(f, {"wght": wght, "wdth": wdth})
    return inst["hmtx"].metrics, inst.getBestCmap(), inst["head"].unitsPerEm


def measure(text, size, wght=400, wdth=100, tracking=0):
    hmtx, cmap, upm = instance(wght, wdth)
    units = sum(hmtx[cmap.get(ord(c), "space")][0] for c in text)
    return units * size / upm + tracking * len(text)


def wrap(text, size, width, wght=400, wdth=100):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if measure(trial, size, wght, wdth) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def T(x, y, s, size, fill=CHALK, wght=400, wdth=100, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'style="font-weight:{wght};font-stretch:{wdth}%" text-anchor="{anchor}" {extra}>{esc(s)}</text>')


def svg(w, h, body, title, extra_css=""):
    css = (FACE + "text{font-family:'A',system-ui,sans-serif;font-kerning:normal}" + extra_css)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}"><title>{esc(title)}</title><style>{css}</style>{body}</svg>')


def plate(w, h, fill=DEEP, rx=16):
    return f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{rx}" fill="{fill}" stroke="{LINE}"/>'


def write(name, content):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{name:24s} {len(content)/1024:6.1f} KB")


# ── icons ─────────────────────────────────────────────────────────────────
def icon(slug, x, y, size, fill):
    raw = open(fetch(ICON_URL.format(slug), f"{slug}.svg"), encoding="utf-8").read()
    d = re.search(r' d="([^"]+)"', raw).group(1)
    k = size / 24
    return f'<path transform="translate({x:.1f} {y:.1f}) scale({k:.4f})" d="{d}" fill="{fill}"/>'


# ── contours (hero) ───────────────────────────────────────────────────────
def contours(w, h, seed=7):
    rng = np.random.default_rng(seed)
    X, Y = np.meshgrid(np.linspace(0, 1, 260), np.linspace(0, h / w, int(260 * h / w)))
    cy = h / w / 2
    z = 1.25 * np.exp(-(((X - .5) / .30) ** 2 + ((Y - cy * 1.02) / .15) ** 2))
    for cx_, cy_, a, sx, sy in [(.08, .05, .9, .16, .14), (.93, .30, .8, .14, .12), (.72, -.02, .5, .12, .09),
                                 (.22, .36, .45, .10, .08)]:
        z += a * np.exp(-(((X - cx_) / sx) ** 2 + ((Y - cy_) / sy) ** 2))
    for _ in range(6):
        fx, fy, ph = rng.uniform(3, 9), rng.uniform(3, 9), rng.uniform(0, 6.3)
        z += .045 * np.sin(fx * X * 6.28 + ph) * np.cos(fy * Y * 6.28 + ph)
    levels = np.linspace(.12, 1.30, 22)
    fig = plt.figure()
    cs = plt.contour(X * w, Y * w, z, levels=levels)
    plt.close(fig)
    out = []
    for i, segs in enumerate(cs.allsegs):
        index = i % 5 == 4
        for seg in segs:
            if len(seg) < 6:
                continue
            pts = seg[::2]
            d = "M" + " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            out.append(f'<path d="{d}" fill="none" stroke="{TIDE if index else LINE}" '
                       f'stroke-width="{1.2 if index else .9}" opacity="{.42 if index else .75}"/>')
    return "".join(out)


# ── hero with typed roles ────────────────────────────────────────────────
def hero():
    W, H = 1000, 380
    roles = ["Software developer", "Data analyst", "Geospatial analyst", "Business development",
             "Open-source contributor"]
    size, wght, wdth, cx, ty = 27, 520, 100, W / 2, 262
    slot, typ, hold, erase = 4.2, 1.3, 2.2, .45
    period = slot * len(roles)

    typed = []
    for n, role in enumerate(roles):
        full = measure(role, size, wght, wdth)
        x0 = cx - full / 2
        t0 = n * slot
        times, widths = [0.0], [0.0]
        for i in range(1, len(role) + 1):
            times.append(t0 + typ * i / len(role))
            widths.append(measure(role[:i], size, wght, wdth))
        for i in range(len(role) - 1, -1, -1):
            times.append(t0 + typ + hold + erase * (len(role) - i) / len(role))
            widths.append(measure(role[:i], size, wght, wdth))
        if times[1] == 0:
            times, widths = times[1:], widths[1:]
            times[0] = 0.0
        kt = ";".join(f"{t / period:.4f}" for t in times)
        wv = ";".join(f"{v:.1f}" for v in widths)
        xv = ";".join(f"{x0 + v + 3:.1f}" for v in widths)
        typed.append(
            f'<clipPath id="c{n}"><rect x="{x0 - 2:.1f}" y="{ty - 30}" height="42" width="0">'
            f'<animate attributeName="width" values="{wv}" keyTimes="{kt}" calcMode="discrete" dur="{period}s" repeatCount="indefinite"/>'
            f'</rect></clipPath>'
            f'<g clip-path="url(#c{n})">{T(cx, ty, role, size, SOLAR, wght, wdth, "middle")}</g>'
            f'<rect y="{ty - 24}" width="2.5" height="30" fill="{SOLAR}" x="{x0:.1f}" opacity="0">'
            f'<animate attributeName="x" values="{xv}" keyTimes="{kt}" calcMode="discrete" dur="{period}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{t0 / period:.4f};{(t0 + slot - .25) / period:.4f}" '
            f'calcMode="discrete" dur="{period}s" repeatCount="indefinite"/></rect>')

    static = T(cx, ty, "Software, data and geospatial roles", size, SOLAR, wght, wdth, "middle", 'class="still"')
    tx, ty_ = cx, 86
    body = (
        f'<defs><clipPath id="frame"><rect width="{W}" height="{H}" rx="20"/></clipPath>'
        f'<radialGradient id="calm" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{ABYSS}" stop-opacity=".92"/>'
        f'<stop offset=".7" stop-color="{ABYSS}" stop-opacity=".55"/><stop offset="1" stop-color="{ABYSS}" stop-opacity="0"/></radialGradient></defs>'
        f'<g clip-path="url(#frame)"><rect width="{W}" height="{H}" fill="{ABYSS}"/>{contours(W, H)}'
        f'<ellipse cx="{cx}" cy="215" rx="400" ry="120" fill="url(#calm)"/></g>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="none" stroke="{LINE}"/>'
        # trig point
        f'<g class="pulse"><circle cx="{tx}" cy="{ty_}" r="6" fill="none" stroke="{SOLAR}" stroke-width="1.2">'
        f'<animate attributeName="r" values="6;34" dur="4s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values=".7;0" dur="4s" repeatCount="indefinite"/></circle></g>'
        f'<path d="M{tx} {ty_ - 8} L{tx + 8} {ty_ + 6} L{tx - 8} {ty_ + 6} Z" fill="{SOLAR}"/>'
        f'<circle cx="{tx}" cy="{ty_ + 1.5}" r="1.8" fill="{ABYSS}"/>'
        + T(tx, ty_ + 32, "26.84° N   75.57° E", 13, TIDE, 500, 118, "middle", 'letter-spacing="1.5"')
        + T(cx, 206, "Mehul Karwa", 80, CHALK, 760, 125, "middle", 'letter-spacing="-1"')
        + f'<g class="typer">{"".join(typed)}</g>' + static
        + T(cx, 312, "B.Tech Data Science, Manipal University Jaipur, 2026", 15.5, TIDE, 430, 100, "middle")
    )
    css = (".still{display:none}"
           "@media (prefers-reduced-motion:reduce){.typer,.pulse{display:none}.still{display:inline}}")
    write("hero.svg", svg(W, H, body, "Mehul Karwa: software developer, data analyst, geospatial analyst, "
                                      "business development", css))


# ── buttons ───────────────────────────────────────────────────────────────
def button(name, label, slug):
    size, wght = 16, 560
    tw = measure(label, size, wght, 100)
    W, H = int(tw + 76), 48
    body = (f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{DEEP}" stroke="{LINE}"/>'
            + icon(slug, 22, 14, 20, SOLAR) + T(54, 30, label, size, CHALK, wght))
    write(name, svg(W, H, body, label))


# ── open to ───────────────────────────────────────────────────────────────
def symbol(kind, x, y):
    s = f'fill="none" stroke="{SOLAR}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"'
    if kind == "software":   # building footprint
        return f'<rect x="{x}" y="{y}" width="22" height="22" rx="2" {s}/><rect x="{x + 6}" y="{y + 6}" width="10" height="10" fill="{SOLAR}"/>'
    if kind == "data":       # histogram
        return "".join(f'<rect x="{x + i * 7}" y="{y + 22 - h}" width="5" height="{h}" fill="{SOLAR}"/>'
                       for i, h in enumerate([9, 17, 22, 13]))
    if kind == "geo":        # contour rings with a spot height
        return (f'<ellipse cx="{x + 11}" cy="{y + 11}" rx="12" ry="9" {s}/><ellipse cx="{x + 11}" cy="{y + 11}" rx="6" ry="4.5" {s}/>'
                f'<circle cx="{x + 11}" cy="{y + 11}" r="1.6" fill="{SOLAR}"/>')
    # business: a route between two points
    return (f'<path d="M{x} {y + 20} C{x + 8} {y + 20} {x + 6} {y + 2} {x + 22} {y + 2}" {s} stroke-dasharray="3 3"/>'
            f'<circle cx="{x}" cy="{y + 20}" r="3" fill="{SOLAR}"/><circle cx="{x + 22}" cy="{y + 2}" r="3" fill="{SOLAR}"/>')


def open_to():
    W, H = 1000, 250
    items = [("software", "Software developer", "Backend, data and AI systems"),
             ("data", "Data analyst", "EDA, statistics and dashboards"),
             ("geo", "Geospatial analyst", "Earth Engine and remote sensing"),
             ("business", "Business development", "Tech-led growth and partners")]
    col = (W - 80) / 4
    body = plate(W, H) + T(W / 2, 58, "Open to full-time roles", 24, CHALK, 680, 118, "middle")
    for i, (k, name, desc) in enumerate(items):
        cx = 40 + col * i + col / 2
        if i:
            body += f'<line x1="{40 + col * i}" y1="104" x2="{40 + col * i}" y2="190" stroke="{LINE}"/>'
        body += symbol(k, cx - 11, 104)
        body += T(cx, 160, name, 17.5, CHALK, 600, 100, "middle")
        body += T(cx, 184, desc, 14, TIDE, 420, 100, "middle")
    body += T(W / 2, H - 22, "India or remote, open to relocation", 13.5, TIDE, 460, 110, "middle", 'opacity=".85"')
    write("open-to.svg", svg(W, H, body, "Open to full-time roles: software developer, data analyst, "
                                         "geospatial analyst, business development"))


# ── experience ───────────────────────────────────────────────────────────
def experience():
    W = 1000
    bullets = [
        "Benchmarked Apache DataFusion against ClickHouse for querying LLM trace data on S3 Parquet and Delta Lake, "
        "which let the team retire a self-hosted ClickHouse cluster for a zero-maintenance, data-sovereign setup.",
        "Built observability for the AI Gateway's OpenAI-compatible chat API: request and response logs, token usage, "
        "cost per model and hierarchical span traces.",
        "Wrote an async OpenTelemetry exporter over NATS that adds no request-path latency and writes logs to "
        "customer-owned S3, GCS and Azure Blob storage.",
        "Merged 100+ pull requests across Python, Rust, Go, TypeScript and PostgreSQL codebases.",
    ]
    rx, rw, fs, lh = 372, W - 372 - 44, 15.5, 23
    y = 58
    right = ""
    for b in bullets:
        lines = wrap(b, fs, rw - 22, 400)
        right += f'<rect x="{rx}" y="{y - 9}" width="7" height="7" fill="{SOLAR}"/>'
        for ln in lines:
            right += T(rx + 22, y, ln, fs, CHALK, 400, 100, extra='opacity=".92"')
            y += lh
        y += 12
    H = int(y + 18)
    left = (T(44, 74, "TrueFoundry", 36, CHALK, 740, 118)
            + T(44, 106, "Backend SDE intern", 18, SOLAR, 560)
            + T(44, 132, "June 2025 to January 2026", 15, TIDE, 440))
    ly = 176
    for ln in wrap("Enterprise AI gateway and LLMOps platform, backed by Sequoia Capital.", 14, 270, 420):
        left += T(44, ly, ln, 14, TIDE, 420)
        ly += 21
    body = plate(W, H) + left + f'<line x1="340" y1="40" x2="340" y2="{H - 40}" stroke="{LINE}"/>' + right
    write("experience.svg", svg(W, H, body, "Backend SDE intern at TrueFoundry, June 2025 to January 2026"))


# ── projects ─────────────────────────────────────────────────────────────
def motif(kind, x, y):
    s = f'fill="none" stroke="{TIDE}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"'
    if kind == "mantis":   # manual page with a cited line
        return (f'<rect x="{x}" y="{y}" width="34" height="44" rx="3" {s}/>'
                + "".join(f'<line x1="{x + 7}" y1="{y + 10 + i * 8}" x2="{x + 27}" y2="{y + 10 + i * 8}" {s}/>' for i in range(4))
                + f'<line x1="{x + 7}" y1="{y + 18}" x2="{x + 27}" y2="{y + 18}" stroke="{SOLAR}" stroke-width="2.5"/>')
    if kind == "solar":    # sun, two buildings and a cast shadow
        return (f'<circle cx="{x + 34}" cy="{y + 8}" r="7" fill="{SOLAR}"/>'
                f'<rect x="{x}" y="{y + 18}" width="14" height="26" {s}/><rect x="{x + 18}" y="{y + 30}" width="14" height="14" {s}/>'
                f'<path d="M{x + 14} {y + 18} L{x + 22} {y + 30} L{x + 14} {y + 30} Z" fill="{LINE}"/>')
    if kind == "llm":      # two bubbles
        return (f'<rect x="{x}" y="{y}" width="30" height="20" rx="6" {s}/>'
                f'<rect x="{x + 12}" y="{y + 24}" width="30" height="20" rx="6" fill="none" stroke="{SOLAR}" stroke-width="1.5"/>')
    # map: grid with pins
    return (f'<rect x="{x}" y="{y + 6}" width="42" height="36" rx="3" {s}/>'
            f'<path d="M{x + 14} {y + 6} V{y + 42} M{x + 28} {y + 6} V{y + 42}" {s} opacity=".6"/>'
            + "".join(f'<circle cx="{x + px}" cy="{y + py}" r="3.2" fill="{SOLAR if i == 0 else TIDE}"/>'
                      for i, (px, py) in enumerate([(9, 18), (22, 30), (34, 16)])))


def project(name, title, tag, tag_gold, desc, chips, kind):
    W, H, pad = 490, 300, 30
    tsize = 30
    while measure(title, tsize, 720, 118) > W - 2 * pad - 60:
        tsize -= 1
    body = plate(W, H) + motif(kind, W - pad - 44, pad) + T(pad, 64, title, tsize, CHALK, 720, 118)
    body += T(pad, 92, tag, 14.5, SOLAR if tag_gold else TIDE, 560 if tag_gold else 460)
    y = 136
    for ln in wrap(desc, 15, W - 2 * pad, 400):
        body += T(pad, y, ln, 15, CHALK, 400, extra='opacity=".9"')
        y += 23
    x = pad
    for c in chips:
        cw = measure(c, 12.5, 520) + 22
        body += (f'<rect x="{x:.1f}" y="{H - pad - 26}" width="{cw:.1f}" height="26" rx="13" fill="none" stroke="{LINE}"/>'
                 + T(x + cw / 2, H - pad - 8.5, c, 12.5, TIDE, 520, 100, "middle"))
        x += cw + 8
    assert y < H - pad - 40, f"{name}: description too long"
    write(name, svg(W, H, body, f"{title}: {tag}"))


# ── tech stack legend ────────────────────────────────────────────────────
STACK = [
    ("Languages", [("python", "Python"), ("typescript", "TypeScript"), ("rust", "Rust"), ("go", "Go")]),
    ("Backend and web", [("fastapi", "FastAPI"), ("nodedotjs", "Node.js"), ("nextdotjs", "Next.js"),
                         ("react", "React"), ("tailwindcss", "Tailwind"), ("natsdotio", "NATS")]),
    ("Data and storage", [("postgresql", "PostgreSQL"), ("mysql", "MySQL"), ("mongodb", "MongoDB"),
                          ("sqlite", "SQLite"), ("clickhouse", "ClickHouse"), ("apache", "DataFusion"),
                          ("apacheparquet", "Parquet"), ("apachespark", "Spark")]),
    ("ML and AI", [("pandas", "pandas"), ("numpy", "NumPy"), ("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"),
                   ("huggingface", "Hugging Face"), ("modelcontextprotocol", "MCP"), ("googlegemini", "Gemini")]),
    ("Geospatial", [("googleearthengine", "Earth Engine"), ("leaflet", "Leaflet"),
                    ("openstreetmap", "OpenStreetMap"), ("playwright", "Playwright")]),
    ("Cloud and ops", [("amazonwebservices", "AWS"), ("googlecloud", "Google Cloud"), ("microsoftazure", "Azure"),
                       ("docker", "Docker"), ("opentelemetry", "OpenTelemetry"), ("sentry", "Sentry"),
                       ("postman", "Postman"), ("git", "Git")]),
]


def stack():
    W, top, row_h, label_w, cell = 1000, 36, 84, 200, 94
    H = top + row_h * len(STACK) + 20
    body = plate(W, H)
    for r, (group, items) in enumerate(STACK):
        y = top + r * row_h
        if r:
            body += f'<line x1="40" y1="{y}" x2="{W - 40}" y2="{y}" stroke="{LINE}" opacity=".7"/>'
        body += T(40, y + 48, group, 15.5, TIDE, 560, 112)
        for i, (slug, name) in enumerate(items):
            cx = label_w + 40 + cell * i + cell / 2
            body += icon(slug, cx - 13, y + 16, 26, CHALK)
            body += T(cx, y + 64, name, 12.5, TIDE, 460, 100, "middle")
    write("stack.svg", svg(W, H, body, "Tech stack: " + ", ".join(n for _, it in STACK for _, n in it)))


# ── honours ──────────────────────────────────────────────────────────────
def honours():
    W, H = 1000, 290
    rows = [("Awards", [("Winner", "MOSS Hack '26, with Mantis", True),
                        ("Runner-up", "EY Techathon 5.0, 2nd of 400+ teams", False),
                        ("IELTS 8.0", "English proficiency, CEFR C1", False)]),
            ("Leadership", [("Design team lead", "Manipal Alumni Relations, 8 people", False),
                            ("Speaker coordination", "15+ global speakers, Jaipur Lit Fest", False),
                            ("Volunteer teacher", "STEM for 100+ rural students", False)])]
    col = (W - 240) / 3
    body = plate(W, H)
    for r, (label, items) in enumerate(rows):
        y = 40 + r * 130
        if r:
            body += f'<line x1="40" y1="{y - 8}" x2="{W - 40}" y2="{y - 8}" stroke="{LINE}" opacity=".7"/>'
        body += T(40, y + 52, label, 15.5, TIDE, 560, 112)
        for i, (head, sub, gold) in enumerate(items):
            x = 200 + col * i
            body += T(x, y + 44, head, 21, SOLAR if gold else CHALK, 660, 108)
            for j, ln in enumerate(wrap(sub, 14, col - 24, 420)):
                body += T(x, y + 70 + j * 20, ln, 14, TIDE, 420)
    write("honours.svg", svg(W, H, body, "Awards: MOSS Hack '26 winner, EY Techathon 5.0 runner-up, IELTS 8.0. "
                                         "Leadership: design team lead, Jaipur Literature Festival, volunteer teacher"))


if __name__ == "__main__":
    hero()
    button("btn-linkedin.svg", "LinkedIn", "linkedin")
    button("btn-email.svg", "mehulkarwa7@gmail.com", "gmail")
    open_to()
    experience()
    project("p-mantis.svg", "Mantis", "Winner, MOSS Hack '26", True,
            "An AI repair technician that diagnoses product faults from the manufacturer's own manuals. It answers "
            "with page-level citations, reads photos of error codes and draws step-by-step repair flowcharts.",
            ["FastAPI", "Next.js", "Gemini", "MOSS retrieval"], "mantis")
    project("p-solaris.svg", "SOLARIS", "Capstone in geospatial analytics", False,
            "Estimates rooftop solar yield for every building in a city on Google Earth Engine. Its 2.5D shadow "
            "model showed Indian rooftops lose 24–31% of their yield to neighbouring buildings.",
            ["Earth Engine", "FastAPI", "Leaflet", "ERA5 + MODIS"], "solar")
    project("p-mehullm.svg", "MehuLLM", "Personal AI agent", False,
            "Cloud LLMs do the reasoning while a locally fine-tuned Qwen3-1.7B writes in my own style. Trained on "
            "419K messages processed on-device, with an Indian-context PII scrubber and 15 ms hybrid search.",
            ["Python", "SQLite FTS5", "MCP", "LoRA"], "llm")
    project("p-construction.svg", "Construction Intel", "Geospatial sales intelligence", False,
            "Turns public building-permission records into a weekly ranked list of leads for cement distributors "
            "in Hyderabad, flagging projects at their peak cement-demand phase.",
            ["Python", "Playwright", "React", "Leaflet"], "map")
    stack()
    honours()
