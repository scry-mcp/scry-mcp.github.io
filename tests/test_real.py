"""The site built from the real checkouts of the three repositories, as they are, held to the
design rules' counts: contrast, the home's words, and widths measured in a headless Chrome."""

from __future__ import annotations

import functools
import http.server
import re
import threading
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

import pytest
from chrome import Chrome, binary
from conftest import checkouts
from look import Unreadable, contrast, home_limits

from scry_site import build

CSS = resources.files("scry_site").joinpath("static", "site.css").read_text(encoding="utf-8")
#: What a page measures at a width, every fold opened: how wide the page scrolls, how many panes
#: hold a line wider than their box, and how many elements show text under 13 px.
MEASURE = """(() => {
  document.querySelectorAll('details').forEach(d => d.open = true);
  const panes = [...document.querySelectorAll('pre')].filter(
    p => p.offsetParent && p.scrollWidth > p.clientWidth + 1).length;
  let small = 0;
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || !r.width || !r.height) continue;
    if ([...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
        && parseFloat(cs.fontSize) < 13) small++;
  }
  return [document.documentElement.scrollWidth, panes, small];
})()"""
#: One page of each kind the site makes.
KINDS = ("index.html", "reference/index.html", "mame/index.html", "mame/reference/index.html",
         "dosbox-x/reference/run/index.html", "dosbox-x/reference/breakpoints/watch_add.html",
         "mame/reference/scan/scan.html", "dosbox-x/demos/monkey/index.html",
         "mame/demos/gridlee/index.html", "mame/contributing.html", "core/index.html")


def test_the_real_checkouts_build(real_site: Path) -> None:
    assert (real_site / "index.html").is_file()
    assert len(list(real_site.rglob("*.html"))) > len(KINDS)


def test_every_text_meets_its_contrast_floor_as_the_stylesheet_declares_it() -> None:
    rows = contrast(CSS)
    assert len(rows) == 44
    assert [r for r in rows if r[2] < r[3]] == []


def test_the_contrast_check_fails_a_muted_text_too_dark_and_reads_nothing_as_invalid() -> None:
    dark = CSS.replace("--muted:#a9a59d", "--muted:#555555", 1)
    assert dark != CSS
    assert len([r for r in contrast(dark) if r[2] < r[3]]) == 5
    with pytest.raises(Unreadable, match="no colour token"):
        contrast("")


@pytest.mark.parametrize(("old", "message"), [
    ("--fog:193,18,31", "the fog's colour not found"),
    ("at 22% 12%,rgba(var(--fog),.26)", "the fog's alpha not found"),
    ("--mamebox:#12182a", "token onmame or mamebox is not"),
])
def test_a_stylesheet_missing_what_the_table_reads_is_unreadable(old: str, message: str) -> None:
    assert old in CSS
    with pytest.raises(Unreadable, match=re.escape(message)):
        contrast(CSS.replace(old, "", 1))


def test_a_checkout_directory_without_the_three_fails_the_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRY_SITE_CHECKOUTS", str(tmp_path))
    with pytest.raises(pytest.fail.Exception, match="set SCRY_SITE_CHECKOUTS"):
        checkouts()


def test_the_home_holds_its_countable_limits(real_site: Path) -> None:
    assert home_limits((real_site / "index.html").read_text()) == []


def test_the_home_limit_fails_twelve_more_words_above_the_install_block(real_site: Path) -> None:
    home = (real_site / "index.html").read_text()
    more = home.replace('<p class="cta">', "<p>" + " word" * 12 + '</p><p class="cta">', 1)
    assert more != home
    found = home_limits(more)
    assert len(found) == 1 and found[0].endswith("words above the install block, over 80")


def test_each_hero_limit_is_counted_and_a_part_missing_is_unreadable(real_site: Path) -> None:
    home = (real_site / "index.html").read_text()
    long = re.sub(r"<h1>(.*?)</h1>", r"<h1>\1 and far beyond</h1>", home, count=1)
    assert [f for f in home_limits(long) if f.startswith("the heading")] == [
        "the heading has 7 words, over 5: 'See inside the machine and far beyond'"]
    with pytest.raises(Unreadable, match="no a section's lead"):
        home_limits(home.replace('class="lead"', 'class="other"'))
    with pytest.raises(Unreadable, match="no '<section id=\"install\">'"):
        home_limits(home.replace('id="install"', 'id="other"'))


@pytest.fixture(scope="module")
def chrome() -> Iterator[Chrome]:
    path = binary()
    if path is None:
        pytest.fail("no Chrome to measure the pages in: set SCRY_SITE_CHROME to one")
    with Chrome(path) as c:
        yield c


@pytest.mark.parametrize("width", [390, 1440])
def test_no_page_scrolls_sideways_no_pane_overflows_and_no_text_is_under_13_px(
        real_site: Path, chrome: Chrome, width: int) -> None:
    found = {}
    for page in KINDS:
        chrome.load((real_site / page).as_uri(), width, 844)
        found[page] = chrome.answer(MEASURE)
    assert found == {page: [width, 0, 0] for page in KINDS}


#: Where a reader at the end of a command page stands. On a wide screen: the side list starts
#: under the top bar, and the open command, the section being read (the last one) and the next
#: command, where there is one, show inside the list's box and the window. On a phone: the way
#: back shows, 44 px high, above the foot's last link, and lands on the folded list, opened.
REACH = """(async () => {
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  scrollTo(0, document.documentElement.scrollHeight); await frame();
  const bar = document.querySelector('.menubar').getBoundingClientRect().bottom;
  const box = e => e.getBoundingClientRect();
  const inside = (e, top = bar, bottom = innerHeight) => box(e).height > 0
    && box(e).top >= top && box(e).bottom <= bottom;
  // a list's scrollTop is a whole pixel, so its edge may cut a row by less than one
  const shows = (e, frame) => inside(e, Math.max(bar, box(frame).top) - 1,
                                     Math.min(innerHeight, box(frame).bottom) + 1);
  if (innerWidth >= 960) {
    const side = document.querySelector('.side-d'), open = side.querySelector('a[aria-current]');
    const read = side.querySelector('.sub a[aria-current]');
    const next = open.parentElement.nextElementSibling;
    const last = side.querySelector('.sub li:last-child a');
    return [box(side).top >= bar, shows(open, side), read === last && shows(read, side),
            !next || shows(next.firstElementChild, side)];
  }
  const back = document.querySelector('.tolist'), rewind = document.querySelector('.eject a');
  const shown = inside(back) && box(back).height >= 44 && box(rewind).bottom <= box(back).top;
  back.click(); await frame();
  const fold = document.querySelector('.side-m');
  return [shown, inside(fold.querySelector('summary')), fold.open,
          inside(fold.querySelector('ul a'))];
})()"""
COMMANDS = [p for p in KINDS if "/reference/" in p and not p.endswith("index.html")]


@pytest.mark.parametrize(("width", "height"), [(390, 844), (1440, 900), (1440, 700)])
def test_the_end_of_a_command_page_reaches_its_side_list(
        real_site: Path, chrome: Chrome, width: int, height: int) -> None:
    found = {}
    for page in [*COMMANDS, "dosbox-x/reference/session/start.html"]:
        chrome.load((real_site / page).as_uri(), width, height)
        found[page] = chrome.answer(REACH)
    assert found == {page: [True] * 4 for page in found}


#: From the end of a tool's or a family's page, without scrolling the page back: the way up to
#: the server's reference shows, a finger's height (36 px on a desktop), and the list's last group
#: holds every family of the server, the one open marked, its last link brought into view by the
#: list's own scroll. On a phone the list is reached by its corner link (a command page) or its
#: summary (a family page).
UP = """(async () => {
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  scrollTo(0, document.documentElement.scrollHeight); await frame();
  const wide = innerWidth >= 960, tall = wide ? 36 : 44;
  if (!wide) {
    const back = document.querySelector('.tolist');
    if (back) back.click();
    else { document.querySelector('.side-m > summary').click(); await frame();
           document.querySelector('#side-list').scrollIntoView(); }
    await frame();
  }
  const bar = document.querySelector('.menubar').getBoundingClientRect().bottom;
  const shows = e => { const b = e.getBoundingClientRect();
    return b.height >= tall && b.top >= bar - 1 && b.bottom <= innerHeight + 1; };
  const up = document.querySelector(wide ? '.side-top a.up' : '.side-m a.up');
  const said = [shows(up), /reference\\/index\\.html$/.test(up.href)];
  const list = document.querySelector(wide ? '.side-d' : '.side-m');
  const grp = [...list.querySelectorAll('.grp')].at(-1);
  const fams = [...grp.nextElementSibling.querySelectorAll('a')];
  fams.at(-1).scrollIntoView({block: 'nearest'}); await frame();
  return [...said, grp.textContent, fams.length,
          fams.filter(a => a.getAttribute('aria-current')).length, shows(fams.at(-1)),
          !wide || scrollY + innerHeight >= document.documentElement.scrollHeight - 2];
})()"""


@pytest.mark.parametrize(("width", "height"), [(390, 844), (1440, 900), (1440, 700)])
def test_the_end_of_a_tool_or_family_page_reaches_the_reference_and_every_family(
        real_site: Path, chrome: Chrome, width: int, height: int) -> None:
    found = {}
    for page in [*COMMANDS, "dosbox-x/reference/session/start.html",
                 "mame/reference/breakpoints/index.html"]:
        fams = len(list((real_site / page).parent.parent.glob("*/index.html")))
        chrome.load((real_site / page).as_uri(), width, height)
        found[page] = chrome.answer(UP)
        assert fams > 10
        assert found[page][3] == fams, page
    assert found == {page: [True, True, "Families", found[page][3], 1, True, True]
                     for page in found}


#: At the end of a page, in a short window: the wide side list starts under the bar and ends at
#: least 24 px above the foot.
FITS = """(async () => {
  scrollTo(0, document.documentElement.scrollHeight);
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const side = document.querySelector('.side').getBoundingClientRect();
  return [side.top >= document.querySelector('.menubar').getBoundingClientRect().bottom - 1,
          side.bottom <= document.querySelector('.foot').getBoundingClientRect().top - 23];
})()"""


def test_the_end_of_a_family_or_document_page_fits_its_side_list_under_the_bar(
        real_site: Path, chrome: Chrome) -> None:
    found = {}
    for page in ("dosbox-x/reference/breakpoints/index.html", "core/docs/katas.html",
                 "mame/contributing.html", "dosbox-x/reference/session/start.html"):
        chrome.load((real_site / page).as_uri(), 1440, 700)
        found[page] = chrome.answer(FITS)
    assert found == {page: [True, True] for page in found}


def test_a_command_page_seen_whole_from_its_top_marks_no_section_as_read(
        real_site: Path, chrome: Chrome) -> None:
    chrome.load((real_site / "mame/reference/session/close.html").as_uri(), 1440, 4000)
    assert chrome.answer("[scrollY, document.documentElement.scrollHeight <= innerHeight, "
                         "document.querySelectorAll('.side-d .sub a[aria-current]').length]") \
        == [0, True, 0]


#: How many of a command page's controls, brought into the window at its bottom edge and focused,
#: lie under the corner link back to the side list.
UNDER = """(() => {
  const back = document.querySelector('.tolist'), k = back.getBoundingClientRect();
  const all = [...document.querySelectorAll('main a, main button, main summary')]
    .filter(e => e !== back && e.offsetParent);
  let under = 0;
  for (const e of all) {
    scrollTo(0, scrollY + e.getBoundingClientRect().bottom - innerHeight + 4);
    e.focus();
    const f = e.getBoundingClientRect();
    if (f.right > k.left && f.left < k.right && f.bottom > k.top && f.top < k.bottom) under++;
  }
  return [all.length > 0, under];
})()"""


def test_no_focused_control_hides_under_the_way_back(real_site: Path, chrome: Chrome) -> None:
    found = {}
    for page in COMMANDS:
        chrome.load((real_site / page).as_uri(), 390, 844)
        found[page] = chrome.answer(UNDER)
    assert found == {page: [True, 0] for page in COMMANDS}


#: Whether the focused link's ring (its box grown by the outline's width and offset) lies inside
#: the box of the wide side list's half that holds it, the way up or the list, which clips what
#: overflows it.
RING = """(() => {
  const a = document.activeElement, side = a.closest('.side-top, .side-d') || document.body;
  const cs = getComputedStyle(a), grow = parseFloat(cs.outlineWidth) + parseFloat(cs.outlineOffset);
  const r = a.getBoundingClientRect(), box = side.getBoundingClientRect();
  return [side.contains(a), cs.outlineStyle, r.left - grow >= box.left + side.clientLeft,
          r.right + grow <= box.left + side.clientLeft + side.clientWidth];
})()"""


def test_a_focused_link_in_the_wide_side_list_shows_its_whole_ring(
        real_site: Path, chrome: Chrome) -> None:
    chrome.load((real_site / "dosbox-x/reference/session/start.html").as_uri(), 1440, 900)
    chrome.answer("document.querySelector('.menubar nav a:last-child').focus()")
    rings = []
    for _ in range(2):
        chrome.ws.call("Input.dispatchKeyEvent", type="keyDown", key="Tab", code="Tab",
                       windowsVirtualKeyCode=9)
        rings.append([chrome.answer("document.activeElement.closest('.side-top, .side-d')"
                                    "?.className"), *chrome.answer(RING)])
    assert rings == [["side-top", True, "solid", True, True], ["side-d", True, "solid", True, True]]


def test_a_page_the_width_case_measures_exists(real_site: Path) -> None:
    assert [p for p in KINDS if not (real_site / p).is_file()] == []


def test_the_width_count_sees_a_pane_wider_than_its_box(tmp_path: Path, chrome: Chrome) -> None:
    page = tmp_path / "wide.html"
    page.write_text('<!doctype html><meta charset="utf-8"><body style="margin:0">'
                    '<div style="width:200px"><pre style="overflow:auto;font-size:12px">'
                    + "x" * 400 + "</pre></div>")
    chrome.load(page.as_uri(), 390, 844)
    assert chrome.answer(MEASURE) == [390, 1, 1]


#: The crumbs' links at a width: how many there are, and the lowest one's height.
CRUMBS = """(() => { const hs = [...document.querySelectorAll('.crumbs a')]
  .map(a => a.getBoundingClientRect().height);
  return [hs.length > 0, Math.min(...hs) >= 44]; })()"""


#: On a phone, the folded list opened from the end of the page: whether it ends above the text.
OPENED = """(async () => {
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  scrollTo(0, document.documentElement.scrollHeight); await frame();
  const fold = document.querySelector('.side-m'); fold.open = true; await frame();
  dispatchEvent(new Event('scroll')); await frame();
  return fold.getBoundingClientRect().bottom
    <= document.querySelector('main').getBoundingClientRect().top;
})()"""


def test_a_phones_opened_side_list_ends_above_the_text(real_site: Path, chrome: Chrome) -> None:
    found = {}
    for page in ("mame/reference/breakpoints/breakpoint_at.html",
                 "mame/reference/breakpoints/index.html", "mame/contributing.html"):
        chrome.load((real_site / page).as_uri(), 390, 844)
        found[page] = chrome.answer(OPENED)
    assert found == {page: True for page in found}


def test_a_finger_takes_every_crumb_on_a_phone(real_site: Path, chrome: Chrome) -> None:
    found = {}
    for page in ("reference/index.html", "mame/reference/breakpoints/index.html",
                 "mame/reference/breakpoints/breakpoint_at.html",
                 "dosbox-x/demos/monkey/index.html"):
        chrome.load((real_site / page).as_uri(), 390, 844)
        found[page] = chrome.answer(CRUMBS)
    assert found == {page: [True, True] for page in found}


# ---- measurement: what a visitor's choice does in a real browser ------------------------------

PROPERTY = "G-TESTTEST12"
STATE = """(() => ({
  banner: (() => { const b = document.getElementById('consent'); return b ? !b.hidden : null; })(),
  tags: [...document.querySelectorAll('script[src*="googletagmanager"]')].map(s => s.src),
  layer: (window.dataLayer || []).map(c => Array.from(c)),
  stored: JSON.parse(localStorage.getItem('scry-consent-v1') || 'null')
}))()"""
BANNER = """(() => {
  const b = document.getElementById('consent');
  return [document.documentElement.scrollWidth,
          [...b.querySelectorAll('button')].map(x => Math.round(x.getBoundingClientRect().height))];
})()"""
GOOGLE = ["*googletagmanager.com*", "*google-analytics.com*", "*analytics.google.com*"]


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """The real site built with a property id and served on 127.0.0.1, which that copy names as
    the one host that measures."""
    out = tmp_path_factory.mktemp("measured") / "site"
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SCRY_GA4_ID", PROPERTY)
        build.build(checkouts(), out)
    for page in ("index.html", "cookies.html"):
        f = out / page
        text = f.read_text()
        assert 'data-host="scryai.net"' in text
        f.write_text(text.replace('data-host="scryai.net"', 'data-host="127.0.0.1"'))

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def fresh(chrome: Chrome, url: str, width: int = 1440) -> None:
    """The page with no stored choice, and no request to Google able to leave the machine."""
    chrome.ws.call("Network.enable")
    chrome.ws.call("Network.setBlockedURLs", urls=GOOGLE)
    chrome.load(url, width, 900)
    chrome.answer("localStorage.clear()")
    chrome.load(url, width, 900)


def click(chrome: Chrome, choice: str) -> None:
    assert chrome.answer(f"(document.querySelector('[data-consent={choice}]').click(), true)")


def test_before_a_choice_the_banner_shows_and_nothing_is_sent_to_google(
        measured: str, chrome: Chrome) -> None:
    fresh(chrome, f"http://{measured}/index.html")
    assert chrome.answer(STATE) == {"banner": True, "tags": [], "layer": [], "stored": None}


def test_the_banner_fits_a_phone_and_both_answers_are_a_finger_high(
        measured: str, chrome: Chrome) -> None:
    fresh(chrome, f"http://{measured}/index.html", width=390)
    width, heights = chrome.answer(BANNER)
    assert width == 390
    assert len(heights) == 2 and min(heights) >= 44


def test_accepting_loads_the_tag_once_with_the_advertising_signals_denied(
        measured: str, chrome: Chrome) -> None:
    fresh(chrome, f"http://{measured}/index.html")
    click(chrome, "granted")
    state = chrome.answer(STATE)
    assert state["banner"] is False
    assert state["tags"] == [f"https://www.googletagmanager.com/gtag/js?id={PROPERTY}"]
    assert state["stored"]["decision"] == "granted"
    commands = state["layer"]
    assert commands[0] == ["consent", "default", {
        "ad_storage": "denied", "ad_user_data": "denied", "ad_personalization": "denied",
        "analytics_storage": "denied"}]
    assert commands[1] == ["consent", "update", {"analytics_storage": "granted"}]
    assert [c[:2] for c in commands[2:]] == [["js", commands[2][1]], ["config", PROPERTY]]


def test_rejecting_loads_nothing_and_is_remembered_on_the_next_visit(
        measured: str, chrome: Chrome) -> None:
    url = f"http://{measured}/index.html"
    fresh(chrome, url)
    click(chrome, "denied")
    assert chrome.answer(STATE)["banner"] is False
    chrome.load(url, 1440, 900)
    state = chrome.answer(STATE)
    assert (state["banner"], state["tags"], state["layer"]) == (False, [], [])
    assert state["stored"]["decision"] == "denied"


def test_a_visitor_who_accepted_before_is_measured_without_being_asked(
        measured: str, chrome: Chrome) -> None:
    url = f"http://{measured}/index.html"
    fresh(chrome, url)
    chrome.answer("localStorage.setItem('scry-consent-v1', JSON.stringify("
                  "{decision: 'granted', at: Date.now()}))")
    chrome.load(url, 1440, 900)
    state = chrome.answer(STATE)
    assert state["banner"] is False
    assert len(state["tags"]) == 1


@pytest.mark.parametrize("stored", [
    "{decision: 'granted', at: Date.now() - 184 * 24 * 3600 * 1000}",
    "{decision: 'granted', at: Date.now() + 60000}",
    "{decision: 'maybe', at: Date.now()}"])
def test_a_choice_that_expired_or_is_not_one_asks_again_and_loads_nothing(
        measured: str, chrome: Chrome, stored: str) -> None:
    url = f"http://{measured}/index.html"
    fresh(chrome, url)
    chrome.answer(f"localStorage.setItem('scry-consent-v1', JSON.stringify({stored}))")
    chrome.load(url, 1440, 900)
    state = chrome.answer(STATE)
    assert (state["banner"], state["tags"], state["layer"]) == (True, [], [])


def test_another_host_neither_asks_nor_measures(measured: str, chrome: Chrome) -> None:
    other = measured.replace("127.0.0.1", "localhost")
    fresh(chrome, f"http://{other}/index.html")
    assert chrome.answer(STATE) == {"banner": False, "tags": [], "layer": [], "stored": None}


def test_a_browser_that_denies_storage_still_asks_and_keeps_the_answer_for_the_visit(
        measured: str, chrome: Chrome) -> None:
    url = f"http://{measured}/index.html"
    fresh(chrome, url)
    denied = chrome.ws.call("Page.addScriptToEvaluateOnNewDocument", source=(
        "Object.defineProperty(window, 'localStorage', {configurable: true, get() {"
        " throw new DOMException('denied', 'SecurityError'); }});"))["identifier"]
    try:
        chrome.load(url, 1440, 900)
        assert chrome.answer("document.getElementById('consent').hidden") is False
        click(chrome, "denied")
        assert chrome.answer("document.getElementById('consent').hidden") is True
    finally:
        chrome.ws.call("Page.removeScriptToEvaluateOnNewDocument", identifier=denied)


def test_the_cookies_page_withdraws_the_choice_and_asks_again(
        measured: str, chrome: Chrome) -> None:
    url = f"http://{measured}/cookies.html"
    fresh(chrome, url)
    assert chrome.answer("document.querySelector('[data-consent=reset]').hidden") is False
    click(chrome, "granted")
    assert chrome.answer(STATE)["stored"]["decision"] == "granted"
    click(chrome, "reset")
    state = chrome.answer(STATE)
    assert state["banner"] is True and state["stored"] is None


def test_rejecting_after_accepting_in_the_same_visit_withdraws_analytics_storage(
        measured: str, chrome: Chrome) -> None:
    fresh(chrome, f"http://{measured}/cookies.html")
    click(chrome, "granted")
    click(chrome, "reset")
    click(chrome, "denied")
    last = chrome.answer(STATE)["layer"][-1]
    assert last == ["consent", "update", {"analytics_storage": "denied"}]


def test_the_cookies_and_privacy_pages_hold_the_site_s_layout_at_both_widths(
        real_site: Path, chrome: Chrome) -> None:
    for width in (390, 1440):
        for page in ("cookies.html", "privacy.html"):
            chrome.load((real_site / page).as_uri(), width, 844)
            assert chrome.answer(MEASURE) == [width, 0, 0], (page, width)
