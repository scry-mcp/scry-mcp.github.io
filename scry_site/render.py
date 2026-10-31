"""Markdown to HTML, with every link resolved to its page on the site or to the repository."""

from __future__ import annotations

import html
import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

from markdown_it import MarkdownIt
from markdown_it.common.utils import normalizeReference
from markdown_it.helpers import parseLinkDestination
from mdit_py_plugins.anchors import anchors_plugin

from scry_site.sources import GITHUB, Invalid, Page, masked_inline

_MD = MarkdownIt("gfm-like", {"linkify": False}).use(anchors_plugin, max_level=6)
# Raw HTML in markdown may quote an attribute either way; markdown-it's own output uses double.
_LINK = re.compile(r"""\b(href|src)=(?:"([^"]*)"|'([^']*)')""")
_HEADING = re.compile(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h\1>', re.S)
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:|//", re.I)
# Marks a reference use among the links markdown-it reads; a real destination never holds NUL.
_REF = "\0ref:"


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
# A reference definition's label, at the start of a line.
_DEFINITION = re.compile(r"^ {0,3}\[((?:[^\]\\]|\\.)+)\]:[ \t]*\n?[ \t]*", re.M)


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


def _inline_destinations(text: str) -> Iterator[tuple[int, int, str, bool]]:
    """Where each `[label](destination ...)` and `![alt](destination ...)` of `text` keeps its
    destination: start, end, the destination as markdown reads it, and whether it is an image.
    Brackets nest (a linked image), and the destination is read by markdown-it's own parser, so
    parentheses, `<...>` and a following title mean what they mean there."""
    opened: list[bool] = []
    bang, i = -2, 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "!":
            bang = i
        elif c == "[":
            opened.append(bang == i - 1)
        elif c == "]" and opened:
            image = opened.pop()
            if text.startswith("(", i + 1):
                start = i + 2
                while start < len(text) and text[start] in " \t\n":
                    start += 1
                found = parseLinkDestination(text, start, len(text))
                if found.ok and found.str:
                    yield start, found.pos, found.str, image
        i += 1


def _definition_destinations(text: str) -> Iterator[tuple[int, int, str, str]]:
    """The same for each `[label]: destination` line: start, end, destination and label."""
    for m in _DEFINITION.finditer(text):
        found = parseLinkDestination(text, m.end(), len(text))
        if found.ok and found.str:
            yield m.end(), found.pos, found.str, m[1]


def _read(md: str, labels: set[str]) -> tuple[list[str], list[tuple[str, bool]], set[str]]:
    """What markdown-it reads: the inline destinations, the (label, is image) of each reference
    use, and every label it found a definition for. Each scanned label is given a marker
    destination first, so a reference use is told from an inline link."""
    env: dict[str, dict[str, object]] = {
        "references": {label: {"href": _REF + label, "title": ""} for label in labels}}
    inline: list[str] = []
    used: list[tuple[str, bool]] = []
    for token in _MD.parse(md, env):
        for c in token.children or []:
            if c.type not in ("link_open", "image") or c.markup in ("autolink", "linkify"):
                continue
            dest = str(c.attrGet("href" if c.type == "link_open" else "src") or "")
            if dest.startswith(_REF):
                used.append((dest.removeprefix(_REF), c.type == "image"))
            else:
                inline.append(dest)
    return sorted(inline), used, set(env["references"])


def twin(page: Page, links: Links) -> str:
    """`page`'s own markdown with its links resolved onto the site's markdown pages, so a model
    that reads one page can follow the others. Code, fenced, indented or in a span, is as written.

    The scan is checked against markdown-it's own reading of the page: an inline destination or a
    definition it reads that the scan did not find, or the reverse, is `Invalid`, never a link left
    unresolved."""
    md = page.markdown
    hidden = masked_inline(md)
    inline = list(_inline_destinations(hidden))
    defined = list(_definition_destinations(hidden))
    labels = {normalizeReference(label) for *_, label in defined}
    read, used, found = _read(md, labels)
    scanned = sorted(_MD.normalizeLink(url) for _, _, url, _ in inline)
    if scanned != read or found != labels:
        raise Invalid(f"{page.repo.name}/{page.src}: the twin scanned the destinations {scanned} "
                      f"and the definitions {sorted(labels)}, the destinations markdown reads "
                      f"are {read} and its definitions {sorted(found)}")
    images = {label for label, image in used if image}
    edits = [*inline, *((a, b, url, normalizeReference(label) in images)
                        for a, b, url, label in defined)]
    for a, b, url, image in sorted(edits, reverse=True):
        new = resolve(url, page, links, copy=image, ext=".md")
        if new is not None:
            md = md[:a] + (f"<{new}>" if md[a] == "<" or re.search(r"[\s()]", new) else new) \
                + md[b:]
    return md


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
