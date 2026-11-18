"""The site built from the real checkouts of the three repositories, as they are, held to the
design rules' counts: contrast, the home's words, and widths measured in a headless Chrome."""

from __future__ import annotations

import re
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

import pytest
from chrome import Chrome, binary
from conftest import checkouts
from look import Unreadable, contrast, home_limits

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
