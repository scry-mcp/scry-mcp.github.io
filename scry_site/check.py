"""Every link inside the built site lands on a file it holds and an id that file carries."""

from __future__ import annotations

import html
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote

from scry_site.sources import Invalid

_REF = re.compile(r"""\b(?:href|src)=(?:"([^"]*)"|'([^']*)')""")
_ID = re.compile(r'\sid="([^"]+)"')
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:|//", re.I)


def check(site: Path) -> int:
    """The number of internal links checked; any that misses raises `Invalid`, naming each.

    A page here is generated, so a miss names the built page; the source it came from is the
    page's own path under the repository it names.
    """
    pages = {p.relative_to(site).as_posix(): p.read_text(encoding="utf-8")
             for p in site.rglob("*.html")}
    if not pages:
        raise Invalid(f"no page under {site}")
    ids = {rel: set(_ID.findall(text)) for rel, text in pages.items()}
    misses: list[str] = []
    checked = 0
    for rel, text in pages.items():
        for a, b in _REF.findall(text):
            url = html.unescape(a or b)
            if _SCHEME.match(url):
                continue
            checked += 1
            path, _, frag = url.partition("#")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), unquote(path))) \
                if path else rel
            if url.startswith("/") or target == ".." or target.startswith("../"):
                misses.append(f"{rel}: {url} (outside the site)")
            elif not (site / target).is_file():
                misses.append(f"{rel}: {url} (no file)")
            elif frag and target in ids and unquote(frag) not in ids[target]:
                misses.append(f"{rel}: {url} (no id '{frag}')")
    if misses:
        raise Invalid("links that land nowhere:\n  " + "\n  ".join(sorted(misses)))
    if not checked:
        raise Invalid("no internal link examined")
    return checked
