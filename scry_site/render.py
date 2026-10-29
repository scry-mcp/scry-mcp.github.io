"""Markdown to HTML, with every link resolved to its page on the site or to the repository."""

from __future__ import annotations

import html
import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin

from scry_site.sources import GITHUB, Page, masked

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


#: Files a link points at that the site serves itself, so a browser plays them in place.
MEDIA = (".wav",)
# `[text](url)` and `![alt](url)`, an optional title kept apart.
_MD_LINK = re.compile(r"(!?)(\[[^\]]*\]\()([^)\s]+)(\s+\"[^\"]*\")?\)")


def resolve(url: str, page: Page, links: Links, *, virtual: bool = False, copy: bool = False,
            ext: str = ".html") -> str | None:
    """Where `url`, written in `page`, goes on the site, or None to leave it as written.

    A link to a page the site renders goes to it (`ext` is how its pages are spelled), to any
    other tracked file to GitHub, and a file `copy` asks for (a picture) or `MEDIA` is copied
    beside the site. A relative link naming nothing the repository tracks is recorded in
    `links.broken`. `virtual` marks a page made from part of its source: a link to one of the
    source's own headings goes to the page made from the whole source.
    """
    key_ = page.repo.key
    own = links.tracked[key_]
    if _SCHEME.match(url) or (url.startswith("#") and not virtual):
        return None
    path, _, frag = url.partition("#")
    path = unquote(path.partition("?")[0])
    target = posixpath.normpath(posixpath.join(posixpath.dirname(page.src), path or page.src))
    if url.startswith("/") or target.startswith("../") or target == "..":
        links.broken.append(f"{page.repo.name}/{page.src}: {url} (outside the repository)")
        return None
    readme = "README.md" if target == "." else posixpath.join(target, "README.md")
    if (key_, target) not in links.pages and (key_, readme) in links.pages:
        target = readme
    tail = "#" + frag if frag else ""
    if (key_, target) in links.pages:
        dest = links.pages[(key_, target)]
        if ext != ".html":
            dest = dest.removesuffix(".html") + ext
    elif target in own and (copy or target.endswith(MEDIA)):
        dest = links.copies.setdefault((key_, target), f"{key_}/{target}")
    elif target in own or any(t.startswith(target + "/") for t in own):
        kind = "blob" if target in own else "tree"
        return f"{GITHUB}/{page.repo.name}/{kind}/main/{quote(target)}{tail}"
    else:
        links.broken.append(f"{page.repo.name}/{page.src}: {url}")
        return None
    return posixpath.relpath(dest, posixpath.dirname(page.out)) + tail


def rewrite(body: str, page: Page, links: Links, virtual: bool = False) -> str:
    """`page`'s HTML with every link resolved (see `resolve`)."""
    def fix(m: re.Match[str]) -> str:
        attr, url = m[1], html.unescape(m[2] if m[2] is not None else m[3])
        new = resolve(url, page, links, virtual=virtual, copy=attr == "src")
        return m[0] if new is None else f'{attr}="{html.escape(new)}"'

    return _LINK.sub(fix, body)


def twin(page: Page, links: Links) -> str:
    """`page`'s own markdown with its links resolved onto the site's markdown pages, so a model
    that reads one page can follow the others. Links inside a fenced block are code."""
    hidden = masked(page.markdown)

    def fix(m: re.Match[str]) -> str:
        url = m[3]
        if hidden[m.start(3):m.end(3)] != url:
            return m[0]
        new = resolve(url, page, links, copy=bool(m[1]), ext=".md")
        return m[0] if new is None else f"{m[1]}{m[2]}{new}{m[4] or ''})"

    return _MD_LINK.sub(fix, page.markdown)


def plain(md: str) -> str:
    """`md` as one line of text: the tags gone, the entities read, the white space folded."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", markdown(md))).split())


def toc(body: str) -> str:
    rows = [f'<li class="l{lvl}"><a href="#{i}">{re.sub(r"<[^>]+>", "", t)}</a></li>'
            for lvl, i, t in _HEADING.findall(body)]
    if not rows:
        return ""
    return (f'<nav class="toc" aria-label="On this page"><p>On this page</p>'
            f'<ul>{"".join(rows)}</ul></nav>')
