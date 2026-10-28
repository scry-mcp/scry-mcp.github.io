"""Markdown to HTML, with every link resolved to its page on the site or to the repository."""

from __future__ import annotations

import html
import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin

from scry_site.sources import GITHUB, Page

_MD = MarkdownIt("gfm-like", {"linkify": False}).use(anchors_plugin, max_level=6)
# Raw HTML in markdown may quote an attribute either way; markdown-it's own output uses double.
_LINK = re.compile(r"""\b(href|src)=(?:"([^"]*)"|'([^']*)')""")
_HEADING = re.compile(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h\1>', re.S)
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:|//", re.I)


@dataclass
class Links:
    """What rendering learned: the pages by source, the files to copy, and the links that miss."""

    pages: dict[tuple[str, str], str]
    tracked: dict[str, set[str]]
    copies: dict[tuple[str, str], str] = field(default_factory=dict)
    broken: list[str] = field(default_factory=list)


def markdown(md: str) -> str:
    html_ = str(_MD.render(md))
    return html_.replace("<pre>", '<pre tabindex="0">')


def rewrite(body: str, page: Page, links: Links, virtual: bool = False) -> str:
    """A link to a page the site renders goes to it, to any other tracked file to GitHub, and
    a picture is copied beside the site so it shows.

    A relative link naming nothing the repository tracks is recorded in `links.broken`.
    `virtual` marks a page made from part of its source: a link to one of the source's own
    headings goes to the page made from the whole source.
    """
    key_ = page.repo.key
    here = posixpath.dirname(page.out)
    own = links.tracked[key_]

    def fix(m: re.Match[str]) -> str:
        attr, url = m[1], html.unescape(m[2] if m[2] is not None else m[3])
        if _SCHEME.match(url) or (url.startswith("#") and not virtual):
            return m[0]
        path, _, frag = url.partition("#")
        path = unquote(path.partition("?")[0])
        target = posixpath.normpath(posixpath.join(posixpath.dirname(page.src), path or page.src))
        if url.startswith("/") or target.startswith("../") or target == "..":
            links.broken.append(f"{page.repo.name}/{page.src}: {url} (outside the repository)")
            return m[0]
        readme = "README.md" if target == "." else posixpath.join(target, "README.md")
        if (key_, target) not in links.pages and (key_, readme) in links.pages:
            target = readme
        if (key_, target) in links.pages:
            dest = links.pages[(key_, target)]
        elif target in own and attr == "src":
            dest = links.copies.setdefault((key_, target), f"{key_}/{target}")
        elif target in own or any(t.startswith(target + "/") for t in own):
            kind = "blob" if target in own else "tree"
            dest = f"{GITHUB}/{page.repo.name}/{kind}/main/{quote(target)}"
            return f'{attr}="{html.escape(dest + ("#" + frag if frag else ""))}"'
        else:
            links.broken.append(f"{page.repo.name}/{page.src}: {url}")
            return m[0]
        rel = posixpath.relpath(dest, here)
        return f'{attr}="{html.escape(rel + ("#" + frag if frag else ""))}"'

    return _LINK.sub(fix, body)


def toc(body: str) -> str:
    rows = [f'<li class="l{lvl}"><a href="#{i}">{re.sub(r"<[^>]+>", "", t)}</a></li>'
            for lvl, i, t in _HEADING.findall(body)]
    if not rows:
        return ""
    return (f'<nav class="toc" aria-label="On this page"><p>On this page</p>'
            f'<ul>{"".join(rows)}</ul></nav>')
