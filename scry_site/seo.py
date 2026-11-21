"""What search engines and AI crawlers read: each page's canonical and social tags, `robots.txt`
and `sitemap.xml`. Every address is the one the site is served at."""

from __future__ import annotations

import html
import json
from collections.abc import Iterable
from xml.sax.saxutils import escape

from scry_site.check import NOT_FOUND

SITE = "https://scryai.net"
HOME = "index.html"
SITE_NAME = "SCRY"
IMAGE = f"{SITE}/scry-logo.png"
#: IndexNow's key is public by design: the engines fetch it from the site to know who submits.
INDEXNOW_KEY = "6ff77efa22ac35bf11e654161116942f"
#: Named one by one so that an AI search or assistant is invited by name, not left to the `*` rule.
CRAWLERS = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User",
            "PerplexityBot", "Google-Extended", "CCBot")


def url(out: str) -> str:
    """The address a built page is served at; the home answers at the root."""
    return f"{SITE}/" if out == HOME else f"{SITE}/{out}"


def head(out: str, title: str, description: str, tagline: str) -> str:
    """The tags a page carries in its head. The not-found page stays out of every index."""
    if out == NOT_FOUND:
        return '<meta name="robots" content="noindex">'
    t, d, u = (html.escape(v, quote=True) for v in (title, description, url(out)))
    tags = [f'<link rel="canonical" href="{u}">',
            '<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="{SITE_NAME}">',
            f'<meta property="og:title" content="{t}">',
            f'<meta property="og:description" content="{d}">',
            f'<meta property="og:url" content="{u}">',
            f'<meta property="og:image" content="{IMAGE}">',
            '<meta name="twitter:card" content="summary">']
    if out == HOME:
        tags.append(f'<script type="application/ld+json">{json_ld(tagline)}</script>')
    return "\n".join(tags)


def json_ld(tagline: str) -> str:
    data = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": SITE_NAME,
            "url": url(HOME), "description": tagline, "applicationCategory": "DeveloperApplication",
            "image": IMAGE, "inLanguage": "en"}
    # `</` would close the script element early.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def robots() -> str:
    allowed = "".join(f"User-agent: {name}\nAllow: /\n\n" for name in CRAWLERS)
    return f"{allowed}User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"


def sitemap(outs: Iterable[str]) -> str:
    """Every built page but the not-found one, by address."""
    locs = sorted(url(o) for o in outs if o != NOT_FOUND)
    rows = "".join(f"  <url><loc>{escape(loc)}</loc></url>\n" for loc in locs)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n')
