"""Every link inside the built site lands on a file it holds and an id that file carries."""

from __future__ import annotations

import html
import posixpath
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

from scry_site.sources import Invalid

_REF = re.compile(r"""\b(?:href|src|srcset|poster)=(?:"([^"]*)"|'([^']*)')""")
_ID = re.compile(r'\sid="([^"]+)"')
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:|//", re.I)
# Served for every address that holds no page, so its links start at the site's root.
NOT_FOUND = "404.html"


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
    # Compared by exact spelling: `is_file` on a case-insensitive disk finds `Guide.html` as
    # `guide.html`, and S3, on a case-sensitive one, does not.
    held = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    misses = [f"{rel}: the id '{i}' is held twice" for rel, text in sorted(pages.items())
              for i, n in Counter(_ID.findall(text)).items() if n > 1]
    checked = 0
    for rel, text in pages.items():
        for a, b in _REF.findall(text):
            url = html.unescape(a or b)
            if _SCHEME.match(url):
                continue
            checked += 1
            path, _, frag = url.partition("#")
            if rel == NOT_FOUND and path.startswith("/"):
                # The address `/` is the home, which CloudFront serves as its root object.
                path, base = path[1:] or "index.html", ""
            elif path.startswith("/"):
                misses.append(f"{rel}: {url} (outside the site)")
                continue
            else:
                base = posixpath.dirname(rel)
            target = posixpath.normpath(posixpath.join(base, unquote(path))) if path else rel
            if target == ".." or target.startswith("../"):
                misses.append(f"{rel}: {url} (outside the site)")
            elif target not in held:
                misses.append(f"{rel}: {url} (no file)")
            elif frag and target in ids and unquote(frag) not in ids[target]:
                misses.append(f"{rel}: {url} (no id '{frag}')")
    if misses:
        raise Invalid("links that land nowhere:\n  " + "\n  ".join(sorted(misses)))
    if not checked:
        raise Invalid("no internal link examined")
    return checked
