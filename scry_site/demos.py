"""A demo's page: what it is, its picture moving with its moments, then its guide, its steps to
try in the one shape of an example, and more demos."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

from scry_site import example, motion
from scry_site.sources import Invalid, Motion, Page, marked

_STEP = re.compile(r"^### (\d+)\. (.+)\n", re.M)


def steps(md: str, where: str, inline: Callable[[str], str],
          block: Callable[[str], str]) -> str:
    """The guide's transcript block: each step a figure, its number and title over its example."""
    body = marked(md, "demo-transcript", "", where)
    parts = _STEP.split(body)
    if parts[0].strip() or len(parts) < 4:
        raise Invalid(f"{where}: the transcript block is not a list of '### N. Title' steps")
    out = []
    for n, title, text in zip(parts[1::3], parts[2::3], parts[3::3], strict=True):
        ex = example.parse(text, f"{where}, step {n}", located=False)
        caption = f"<b>{n}</b><strong>{inline(title)}</strong>"
        out.append(example.render(ex, caption=caption, inline=inline, block=block))
    return "".join(out)


def main(page: Page, m: Motion, c: motion.Clip, *, server: str, crumbs: str, more: str,
         inline: Callable[[str], str], block: Callable[[str], str]) -> tuple[str, str]:
    """The page, and the keyframes that light its moments."""
    where = f"{page.repo.name}/{page.src}"
    md = page.markdown
    closing = "<!-- demo-motion:end -->"
    after = md[md.index(closing) + len(closing):]
    if not re.fullmatch(r"# [^\n]+", md[:md.index("<!-- demo-motion:begin -->")].strip()):
        raise Invalid(f"{where}: text stands between the title and the motion block, and the "
                      "page shows only the title, the picture and what follows it")
    first = re.search(r"^## ", after, re.M)
    if not first:
        raise Invalid(f"{where}: nothing under the motion block is a '## ' section")
    intro, rest = after[:first.start()], after[first.start():]
    begin, close = "<!-- demo-transcript:begin -->", "<!-- demo-transcript:end -->"
    if rest.count(begin) != 1 or rest.count(close) != 1:
        raise Invalid(f"{where}: no single '{begin}' ... '{close}' block")
    head, tail = rest.split(begin)
    tail = tail.split(close)[1]
    tag = "mame" if page.repo.key == "mame" else "dos"
    takes = "".join(f"<li><span>{inline(t)}</span></li>" for t in m.moments)
    name = page.title.split(":")[0]
    body = (
        f'{crumbs}<header class="cmd-head"><p class="tags"><span class="tag {tag}">'
        f"{html.escape(server)}</span></p><h1>{html.escape(page.title)}</h1></header>"
        '<div class="demo-top timed">'
        f'<figure class="shot" style="max-width:{c.width}px">'
        f'{motion.picture("", c, m.alt, tape=True)}{motion.osd(name, c)}'
        "</figure>"
        f'<div class="intro">{block(intro)}</div>'
        '<div class="watch"><h2 id="what-you-are-watching">What you are watching</h2>'
        f'<ol class="takes">{takes}</ol></div></div>'
        f"{block(head)}{steps(rest, where, inline, block)}{block(tail)}"
        f'<h2 id="more-demos">More demos</h2><ul class="shots">{more}</ul>')
    return body, motion.keyframes(c, m.ms, where)
