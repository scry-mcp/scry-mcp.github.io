"""The home: the hero, the install per client, what one can ask, the demos and the two emulators.

The hero's own words, the section headings and their leads are `templates/landing.html`; every
word about a server is read out of its README."""

from __future__ import annotations

import html
import posixpath
import re
from dataclasses import dataclass

from scry_site import example, motion
from scry_site.sources import Ask, Invalid, Page, Repo

#: The hero is this server's lead, and these are its picture's moments, in order.
HERO = "dosbox-x"
HERO_MOMENTS = ("The game's own line", "The line SCRY wrote")
EXCHANGE = ("You", "Client", "SCRY")
ASKS_PER_SERVER = 3
DEMO_CARDS = 8


@dataclass(frozen=True)
class Demo:
    """A demo as the home and a demo page's "More demos" show it."""

    name: str
    title: str
    says: str
    pages: tuple[Page, ...]
    clip: motion.Clip


@dataclass(frozen=True)
class Server:
    """What the home shows of one server, its markdown already rendered."""

    repo: Repo
    lede: str
    needs: str
    clone: str
    clients: tuple[tuple[str, str, str, str], ...]
    question: tuple[str, str, str]
    asks: tuple[Ask, ...]
    reference: str
    first_demo: str


def card(d: Demo, here: str, *, lazy: bool = True) -> str:
    """A demo as a card: its picture moving, its name and its sentence, linked to its page."""
    first = d.pages[0]
    href = posixpath.relpath(first.out, here)
    base = posixpath.relpath(posixpath.dirname(first.out), here) + "/"
    on = " · ".join(p.repo.label for p in d.pages)
    return (f'<li><a href="{href}">{motion.picture(base, d.clip, "", lazy=lazy)}'
            f"<div><b>{html.escape(d.title)}</b><span>{d.says}</span>"
            f'<small class="on">{html.escape(on)}</small></div></a></li>')


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _install(servers: list[Server]) -> tuple[str, str]:
    """The emulator switch and the three steps, and the rules that show the chosen blocks."""
    names = [[c[0] for c in s.clients] for s in servers]
    if any(n != names[0] for n in names):
        raise Invalid(f"the READMEs list different clients: {names}")
    switch = "".join(
        f'<label><input type="radio" name="srv" id="srv-{s.repo.key}"'
        f'{" checked" if i == 0 else ""}>{html.escape(s.repo.label)}</label>'
        for i, s in enumerate(servers))
    strip = "".join(
        f'<label><input type="radio" name="cli" id="cli-{_slug(n)}"'
        f'{" checked" if i == 0 else ""}>{html.escape(n)}</label>'
        for i, n in enumerate(names[0]))
    get = "".join(f'<div class="for-{s.repo.key}"><p>{s.needs}</p>{s.clone}</div>'
                  for s in servers)
    panels = []
    for i, n in enumerate(names[0]):
        blocks = "".join(f'<div class="for-{s.repo.key}"><p>{s.clients[i][1]}</p>'
                         f"{example.pane(s.clients[i][2], s.clients[i][3], copy=True)}</div>"
                         for s in servers)
        panels.append(f'<div class="panel" data-cli="{_slug(n)}">{blocks}</div>')
    ask = "".join(f'<div class="for-{s.repo.key}">{s.question[0]}{example.ask_html(s.question[1])}'
                  f'<div class="muted">{s.question[2]}</div></div>' for s in servers)
    css = ",\n".join(f'.install:has(#cli-{_slug(n)}:checked) .panel[data-cli="{_slug(n)}"]'
                     for n in names[0]) + "{display:block}\n"
    css += ",\n".join(f".install:has(#srv-{s.repo.key}:checked) .for-{o.repo.key}"
                      for s in servers for o in servers if o is not s) + "{display:none}"
    section = (
        f'<fieldset class="switch"><legend>Your emulator</legend>{switch}</fieldset>'
        '<ol class="steps-n">'
        f"<li><h3>Get the server</h3>{get}</li>"
        f'<li><h3>Add it to your client</h3><fieldset class="clients"><legend>Your client'
        f'</legend>{strip}</fieldset>{"".join(panels)}</li>'
        f"<li><h3>Ask your first question</h3>{ask}</li></ol>")
    return section, css


def _asks(servers: list[Server], tool_pages: dict[tuple[str, str], str]) -> str:
    cards = []
    for s in servers:
        for t in (t for a in s.asks for t in a.tools if (s.repo.key, t) not in tool_pages):
            raise Invalid(f"{s.repo.name}/README.md: 'What you can ask' names `{t}`, which has "
                          "no entry in the reference")
        for a in s.asks[:ASKS_PER_SERVER]:
            links = [f'<a href="{tool_pages[(s.repo.key, t)]}">{t}</a>' for t in a.tools]
            tag = "mame" if s.repo.key == "mame" else "dos"
            cards.append(f'<li><span class="tag {tag}">{html.escape(s.repo.label)}</span>'
                         f"<q>{html.escape(a.question)}</q>"
                         f'<p class="tools">{", ".join(links)}</p><p>{a.says}</p></li>')
    return f'<ul class="asks">{"".join(cards)}</ul>'


def _demos(demos: list[Demo]) -> str:
    shown, rest = demos[:DEMO_CARDS], demos[DEMO_CARDS:]
    more = ""
    if rest:
        links = ", ".join(f'<a href="{d.pages[0].out}">{html.escape(d.title)}</a>' for d in rest)
        more = f'<p class="more">And {links}.</p>'
    return f'<ul class="shots">{"".join(card(d, ".") for d in shown)}</ul>{more}'


def _emulators(servers: list[Server]) -> str:
    boxes = []
    for s in servers:
        cls = "mame-box" if s.repo.key == "mame" else "dos-box"
        prompt = ('<p class="prompt" aria-hidden="true">C:\\SCRY&gt;<span class="cur"></span></p>'
                  if cls == "dos-box" else "")
        boxes.append(
            f'<div class="{cls}"><h3>{html.escape(s.repo.label)}</h3><p>{s.lede}</p>'
            '<ul class="menu">'
            '<li><a href="#install">Install</a></li>'
            f'<li><a href="{s.reference}">Reference</a></li>'
            f'<li><a href="{s.first_demo}">Demos</a></li>'
            f'<li><a href="https://github.com/scry-mcp/{s.repo.name}">GitHub</a></li>'
            f"</ul>{prompt}</div>")
    return f'<div class="machines">{"".join(boxes)}</div>'


def hero(lead_rows: tuple[tuple[str, str], ...], d: Demo, alt: str, moments: int) -> str:
    """The hero's picture, its moments and the exchange under it, copied from the lead."""
    if moments != len(HERO_MOMENTS):
        raise Invalid(f"the hero names {len(HERO_MOMENTS)} moments and {d.name}'s picture has "
                      f"{moments}")
    base = posixpath.dirname(d.pages[0].out) + "/"
    takes = "".join(f"<li><span>{html.escape(m)}</span></li>" for m in HERO_MOMENTS)
    rows = "".join(f'<li><b>{who}</b><span{" class=said" if i == 0 else ""}>{td}</span></li>'
                   for i, (who, (_, td)) in enumerate(zip(EXCHANGE, lead_rows, strict=True)))
    return (
        f'<figure class="shot timed" style="max-width:{d.clip.width}px">'
        f'{motion.picture(base, d.clip, alt, tape=True)}'
        f'{motion.osd(d.title, d.clip)}<figcaption><ol class="takes row">{takes}</ol>'
        "</figcaption></figure>"
        '<ol class="exchange" aria-label="One request about the game above: what you ask, the '
        f'call, the reply">{rows}</ol>')


def slots(servers: list[Server], demos: list[Demo],
          tool_pages: dict[tuple[str, str], str]) -> tuple[dict[str, str], str]:
    """What the home's template is filled with, and the style its install switches need."""
    install, css = _install(servers)
    return {"install": install, "asks": _asks(servers, tool_pages), "demos": _demos(demos),
            "emulators": _emulators(servers)}, css
