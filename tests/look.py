"""What the design rules count, measured: contrast read out of the stylesheet, and the words a
page shows."""

from __future__ import annotations

import re
from html.parser import HTMLParser

# ---- contrast ------------------------------------------------------------------------------

#: Every text-on-ground pair the design system uses, and its WCAG floor: 4.5 for text, 3 for a
#: control's border and the focus ring. `fogpeak` and `grainpeak` are computed (see `tokens`).
PAIRS = [
    ("fg", ("bg", "grainpeak", "surface", "surface2", "fogpeak"), 4.5),
    ("muted", ("bg", "grainpeak", "surface", "surface2", "fogpeak"), 4.5),
    ("link", ("bg", "grainpeak", "surface", "surface2"), 4.5),
    ("red", ("bg", "grainpeak", "surface", "surface2", "fogpeak"), 4.5),
    ("onbtn", ("btn",), 4.5),
    ("bg", ("fg",), 4.5),
    ("screenlabel", ("screenbar", "bg"), 4.5),
    *((name, ("screen",), 4.5) for name in ("screenfg", "screendim", "screenkey", "screennum",
                                            "screencall", "screenok", "screenbad")),
    ("screenok", ("bg",), 4.5),
    ("onmame", ("mamebox",), 4.5), ("onmame2", ("mamebox",), 4.5),
    ("ondos", ("dos",), 4.5), ("ondos2", ("dos",), 4.5), ("dos", ("ondos",), 4.5),
    ("edge", ("bg", "surface", "fogpeak"), 3.0),
    ("focus", ("bg", "surface", "surface2", "fogpeak", "mamebox"), 3.0),
]


class Unreadable(Exception):
    """The stylesheet does not hold what the table is computed from."""


def _rgb(h: str) -> list[float]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lum(c: list[float]) -> float:
    v = [x / 255 for x in c]
    v = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(_rgb(a)), _lum(_rgb(b))), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _over(top: list[float], alpha: float, under: list[float]) -> list[float]:
    return [u + (t - u) * alpha for t, u in zip(top, under, strict=True)]


def _number(css: str, pattern: str, what: str) -> float:
    m = re.search(pattern, css, re.S)
    if not m:
        raise Unreadable(f"{what} not found")
    return float(m[1])


def tokens(css: str) -> dict[str, str]:
    """The colour tokens of `:root`, with the two grounds the texture makes: the fog at its centre
    under a scan line and a grain at full strength, and black under a grain."""
    root = re.search(r":root\{(.*?)\}", css, re.S)
    t = dict(re.findall(r"--([a-z0-9]+):(#[0-9a-fA-F]{6})\b", root[1] if root else ""))
    if not t:
        raise Unreadable("no colour token read from :root")
    fog = re.search(r"--fog:(\d+),(\d+),(\d+)", css)
    if not fog:
        raise Unreadable("the fog's colour not found")
    fog_a = _number(css, r"radial-gradient\(70% 75% at 22% 12%,rgba\(var\(--fog\),(\.\d+)\)",
                    "the fog's alpha")
    line_a = _number(css, r"\.band::before\{.*?repeating-linear-gradient\(0deg,"
                          r"rgba\(255,255,255,(\.\d+)\)", "the scan line's alpha")
    grain_a = _number(css, r"body::before\{[^}]*?opacity:(\.\d+)", "the grain's opacity") \
        * _number(css, r"0 0 0 (\.\d+) 0'/%3E", "the grain's alpha")
    white = [255.0] * 3
    black = [float(x) for x in _rgb(t["bg"])]
    peak = _over(white, grain_a, _over(white, line_a,
                                       _over([float(x) for x in fog.groups()], fog_a, black)))
    t["fogpeak"] = "#" + "".join(f"{round(x):02x}" for x in peak)
    t["grainpeak"] = "#" + "".join(f"{round(x):02x}" for x in _over(white, grain_a, black))
    return t


def contrast(css: str) -> list[tuple[str, str, float, float]]:
    """Every pair, `(text, ground, ratio, floor)`."""
    t = tokens(css)
    rows = []
    for fg, grounds, floor in PAIRS:
        for bg in grounds:
            if fg not in t or bg not in t:
                raise Unreadable(f"token {fg} or {bg} is not in the stylesheet")
            rows.append((fg, bg, ratio(t[fg], t[bg]), floor))
    return rows


# ---- words ---------------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z0-9][\w'./:\\$~=()\"-]*")


def words(text: str) -> int:
    return len(_WORD.findall(text))


class _Text(HTMLParser):
    """The text a reader sees in the page's `<main>`, up to the install block."""

    def __init__(self) -> None:
        super().__init__()
        self.before: list[str] = []
        self.reached = False
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "section" and dict(attrs).get("id") == "install":
            self.reached = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and not self.reached:
            self.before.append(data)


def read(page: str) -> _Text:
    main = page[page.index("<main"):page.index("</main>") + len("</main>")]
    t = _Text()
    t.feed(main)
    t.close()
    if not t.reached:
        raise Unreadable("no '<section id=\"install\">' on the page")
    return t


def home_limits(page: str) -> list[str]:
    """Each countable limit of the home it breaks: 80 words above the install block, the hero's
    heading, paragraph and moments, and each section's lead."""
    found = []
    above = words(" ".join(read(page).before))
    if above > 80:
        found.append(f"{above} words above the install block, over 80")
    takes = re.search(r'<ol class="takes row">(.*?)</ol>', page, re.S)
    parts = [(5, "the heading", re.findall(r"<h1>(.*?)</h1>", page, re.S)),
             (40, "the paragraph", re.findall(r'<p class="sub">(.*?)</p>', page, re.S)),
             (25, "a section's lead", re.findall(r'<p class="lead">(.*?)</p>', page, re.S)),
             (6, "a moment", re.findall(r"<li>(.*?)</li>", takes[1] if takes else "", re.S))]
    for limit, what, found_html in parts:
        if not found_html:
            raise Unreadable(f"no {what} on the page")
        for fragment in found_html:
            text = " ".join(re.sub(r"<[^>]+>", " ", fragment).split())
            if words(text) > limit:
                found.append(f"{what} has {words(text)} words, over {limit}: {text!r}")
    return found
