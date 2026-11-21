"""Measurement with Google Analytics behind the visitor's choice: the banner, the script tag that
carries the property's id, and the privacy and cookies pages. With no id there is none of it."""

from __future__ import annotations

import re
from collections.abc import Mapping

from scry_site.sources import Invalid

ENV = "SCRY_GA4_ID"
HOST = "scryai.net"
_ID = re.compile(r"G-[A-Z0-9]{6,14}")
AUTHOR = "https://github.com/Optimiza"


def measurement_id(env: Mapping[str, str]) -> str:
    """The property's id from the environment, "" for a build that measures nothing."""
    value = env.get(ENV, "")
    if value and not _ID.fullmatch(value):
        raise Invalid(f"{ENV} is {value!r}, which is not a Google Analytics id like G-ABC123DEF4")
    return value


def banner(root: str, mid: str) -> str:
    """Shown by `consent.js` while no choice stands; both answers are the same button."""
    if not mid:
        return ""
    return (f'<section class="consent" id="consent" aria-label="Cookies and measurement" hidden>'
            f'<div class="wrap"><p><strong>Cookies and measurement.</strong> We would like to '
            f'count visits with Google Analytics, which sets cookies only if you accept. The '
            f'site works the same if you reject. <a href="{root}/cookies.html">About the '
            f'cookies</a></p><div class="choices">'
            f'<button class="btn" type="button" data-consent="denied" hidden>Reject</button>'
            f'<button class="btn" type="button" data-consent="granted" hidden>Accept</button>'
            f'</div></div></section>')


def script(root: str, mid: str) -> str:
    if not mid:
        return ""
    return f'<script defer src="{root}/consent.js" data-ga="{mid}" data-host="{HOST}"></script>'


COOKIES = """<h1>Cookies</h1>
<p class="lead">This site sets no cookies until you accept measurement.</p>
<h2>What the site keeps</h2>
<p>Your choice, in your browser's local storage under <code>scry-consent-v1</code>. It stays on
your device for six months, after which the site asks again.</p>
<h2>If you accept</h2>
<p>Google Analytics sets the cookies <code>_ga</code> and <code>_ga_</code> followed by the
property's id. They tell one visit from another and count the pages seen. The advertising
signals stay off: nothing is used to show you ads.</p>
<h2>Change your choice</h2>
<p>Rejecting works the same as never being asked. Press the button to be asked again.</p>
<p><button class="btn" type="button" data-consent="reset" hidden>Change my choice</button></p>
<p class="muted">The privacy notice says who runs the site: <a href="privacy.html">Privacy</a>.</p>
"""

PRIVACY = f"""<h1>Privacy</h1>
<p class="lead">The site collects nothing about you unless you accept measurement.</p>
<h2>Who runs it</h2>
<p>Optimiza, the author of SCRY, at <a href="{AUTHOR}">{AUTHOR.removeprefix("https://")}</a>.
Write there with any question about your data.</p>
<h2>What is collected, and why</h2>
<p>Only if you accept: the pages you visit and how you reached them, counted by Google Analytics
to learn which pages are read. There are no accounts and no forms, and nothing is sold or used
for advertising.</p>
<h2>Your rights</h2>
<p>You can reject, or withdraw your choice at any time from the
<a href="cookies.html">cookies page</a>. You may also ask for access to your data, its correction
or its erasure.</p>
"""
