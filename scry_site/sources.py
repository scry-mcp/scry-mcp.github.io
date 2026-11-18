"""Which markdown of the three repositories becomes which page, and what the home takes."""

from __future__ import annotations

import functools
import html
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt

GITHUB = "https://github.com/scry-mcp"
NAME = r"[a-z0-9_-]+"


class Invalid(Exception):
    """A source the site needs is not there: nothing built is a verdict."""


@dataclass(frozen=True)
class Repo:
    key: str
    name: str
    label: str
    root: Path


@dataclass
class Page:
    repo: Repo
    src: str
    out: str
    group: str
    markdown: str
    title: str = ""
    label: str = ""
    order: int = 0


@dataclass
class Family:
    """A page of `docs/reference/`: its tools, in its own order, and the sentence the index
    gives it."""

    page: Page
    about: str
    tools: list[str] = field(default_factory=list)


SERVERS = (("mame", "scry-mame", "MAME"), ("dosbox-x", "scry-dosbox-x", "DOSBox-X"))
GROUPS = (("overview", "Overview"), ("demos", "Demos"), ("reference", "Reference"),
          ("contributing", "Contributing"))
#: A tool's entry in its family's page, between the markers the reference generator writes.
ENTRY = re.compile(r"<!-- scry-reference:begin (\w+) -->\n(.*?)<!-- scry-reference:end \1 -->\n?",
                   re.S)


def repos(base: Path) -> list[Repo]:
    found = [Repo(k, n, label, base / n) for k, n, label in SERVERS]
    found.append(Repo("core", "scry-core", "scry-core", base / "scry-core"))
    for r in found:
        if not (r.root / "README.md").is_file():
            raise Invalid(f"no {r.name} checkout at {r.root}")
    return found


def tracked(repo: Repo) -> list[str]:
    """The files git tracks, symbolic links left out: a copy follows a link out of the tree."""
    try:
        out = subprocess.run(["git", "-C", str(repo.root), "ls-files", "-s", "-z"], check=True,
                             capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise Invalid(f"{repo.root} is not a git checkout git can list: {e}") from e
    rows = (row.split("\t", 1) for row in out.split("\0") if row)
    return [path for stage, path in rows if not stage.startswith("120000 ")]


_CREDITS = "Developed by Optimiza ([Marcos Hernández]({}))"
CREDITS_LINKEDIN = _CREDITS.format("https://www.linkedin.com/in/optimiza/")
CREDITS_GITHUB = _CREDITS.format("https://github.com/Optimiza")


def read(repo: Repo, src: str) -> str:
    """A source's text, as every page, twin and `llms.txt` line of the site is made from it.
    The credits line's link to the author is read as their GitHub; the build refuses any other
    mention of LinkedIn in what it writes."""
    try:
        text = (repo.root / src).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Invalid(f"cannot read {repo.name}/{src}: {e}") from e
    return text.replace(CREDITS_LINKEDIN, CREDITS_GITHUB)


_BLOCKS = MarkdownIt("commonmark")
# The lines markdown-it counts: it ends one at "\n", "\r\n" or a lone "\r", and nothing else.
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+")
# A code span: a backtick run, then the next run of the same length, within one paragraph.
_SPAN = re.compile(r"(?<![\\`])(`+)(?!`)(?:(?!\n[ \t]*\n).)*?(?<!`)\1(?!`)", re.S)


def _blank(text: str) -> str:
    return re.sub(r"[^\r\n]", " ", text)


@functools.cache
def masked(md: str) -> str:
    """`md` with every fenced or indented code block, fences included, blanked to spaces, same
    length: a `# ` or `**` inside code is never a heading or a lede, and a link in it is not one.
    Which lines are code is markdown-it's own answer, so a fence in a list item counts."""
    lines = _LINE.findall(md)
    for token in _BLOCKS.parse(md):
        if token.type in ("fence", "code_block") and token.map:
            for i in range(*token.map):
                lines[i] = _blank(lines[i])
    return "".join(lines)


def masked_inline(md: str) -> str:
    """`masked(md)` with the code spans blanked too."""
    return _SPAN.sub(lambda m: _blank(m[0]), masked(md))


def text_of(fragment: str) -> str:
    """An HTML fragment as one line of text."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def title_of(md: str, where: str) -> str:
    """The page's title: its `# ` heading, or the text of the `<h1>` a front door opens with."""
    hidden = masked(md)
    m = re.search(r"^# (.+)$", hidden, re.M)
    if m:
        return m[1].replace("`", "").strip()
    m = re.search(r"\A\s*<h1[^>]*>(.*?)</h1>", hidden, re.S)
    if not m or not text_of(m[1]):
        raise Invalid(f"{where}: no level-one heading ('# ...' or an opening '<h1>') to title "
                      "the page")
    return text_of(m[1])


def section(md: str, heading: str, where: str, level: int = 2) -> str:
    """The text under `heading` at `level`, up to the next heading of that level or higher."""
    hashes = "#" * level
    m = re.search(rf"^{hashes} {re.escape(heading)}\n(.*?)(?=^#{{1,{level}}} |\Z)", masked(md),
                  re.M | re.S)
    if not m:
        raise Invalid(f"{where}: no section '{hashes} {heading}'")
    return md[m.start(1):m.end(1)]


def marked(md: str, kind: str, label: str, where: str) -> str:
    """What sits between `<!-- {kind}:begin {label} -->` and its `end` marker."""
    tail = f" {label}" if label else ""
    m = re.search(rf"<!-- {kind}:begin{tail} -->\n(.*?)<!-- {kind}:end{tail} -->", md, re.S)
    if not m:
        raise Invalid(f"{where}: no '<!-- {kind}:begin{tail} -->' ... 'end' block")
    return m[1]


def lede(md: str, where: str) -> str:
    """The bold sentence a front door opens with, under its `<h1>`, as HTML."""
    m = re.search(r"^<p align=\"center\"><b>(.+?)</b></p>$", md, re.M)
    if not m:
        raise Invalid(f"{where}: no bold opening sentence ('<p align=\"center\"><b>...</b></p>')")
    return m[1]


def paragraphs(md: str) -> list[str]:
    """The blocks of `md` separated by blank lines, a fenced block whole."""
    blocks: list[str] = []
    current: list[str] = []
    fence = ""
    for line in md.split("\n"):
        if fence:
            current.append(line)
            if line.startswith(fence):
                fence = ""
            continue
        if line.startswith("```"):
            fence = "```"
        if line.strip() or fence:
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


@dataclass(frozen=True)
class Fence:
    language: str
    code: str


def fence_of(block: str, where: str) -> Fence:
    m = re.fullmatch(r"```(\w*)\n((?:(?!```).)*?)\n?```", block, re.S)
    if not m:
        raise Invalid(f"{where}: a fenced block was expected, found {block[:60]!r}")
    return Fence(m[1], m[2])


def get_server(md: str, where: str) -> tuple[str, Fence]:
    """What `## Install` says a reader needs, and the ```sh block that clones the server."""
    blocks = paragraphs(section(md, "Install", where).split("\n### ")[0])
    if len(blocks) < 2 or not blocks[1].startswith("```sh"):
        raise Invalid(f"{where}: '## Install' does not open with a sentence and a ```sh block")
    return " ".join(blocks[0].split()), fence_of(blocks[1], where)


@dataclass(frozen=True)
class Client:
    name: str
    says: str
    fence: Fence


def clients(md: str, where: str) -> list[Client]:
    """The README's block of clients, which scry-core's `install` table writes."""
    body = marked(md, "scry-install", "", where)
    # one paragraph, then one fenced block holding no other fence
    found = re.findall(r"<details(?: open)?><summary>([^<]+)</summary>\n\n((?:(?!\n\n).)+)\n\n"
                       r"(```\w*\n(?:(?!```).)*?```)\n\n</details>", body, re.S)
    if not found or len(found) != body.count("<details"):
        raise Invalid(f"{where}: the install block holds {body.count('<details')} clients and "
                      f"{len(found)} read as a name, a sentence and a fenced block")
    return [Client(n, " ".join(s.split()), fence_of(f, where)) for n, s, f in found]


@dataclass(frozen=True)
class Question:
    before: str
    ask: str
    after: str


def first_question(md: str, where: str) -> Question:
    """`### Your first question`: what it needs, the prompt, what the client does."""
    body = section(md, "Your first question", where, level=3)
    blocks = paragraphs(body)
    quotes = [i for i, b in enumerate(blocks) if b.startswith("> ")]
    if len(quotes) != 1:
        raise Invalid(f"{where}: 'Your first question' holds {len(quotes)} quoted prompts, not 1")
    i = quotes[0]
    ask = " ".join(line.removeprefix(">").strip() for line in blocks[i].split("\n"))
    return Question("\n\n".join(blocks[:i]), ask, "\n\n".join(blocks[i + 1:]))


@dataclass(frozen=True)
class Ask:
    question: str
    tools: tuple[str, ...]
    says: str


def asks(md: str, where: str) -> list[Ask]:
    """The questions of `## What you can ask`, each with its tools and its sentence."""
    items = re.split(r"^- ", section(md, "What you can ask", where).strip(), flags=re.M)[1:]
    # an item is one paragraph: words after the list would join its last sentence
    found = [None if "\n\n" in i.strip() else
             re.fullmatch(r'\*\*"(.+?)"\*\* ((?:`\w+`, )*`\w+`)\. (.+)', " ".join(i.split()))
             for i in items]
    if not found or not all(found):
        raise Invalid(f"{where}: 'What you can ask' is not a list of '**\"question\"** `tool`. "
                      "sentence' items")
    return [Ask(m[1], tuple(re.findall(r"`(\w+)`", m[2])), m[3]) for m in found if m]


def demo_sentences(md: str, where: str) -> dict[str, str]:
    """The sentence `## See it run` gives each demo it lists."""
    body = section(md, "See it run", where)
    found = re.findall(rf"^- \[`demos/({NAME})/`\]\(demos/\1/\): (.+?)(?=\n- |\n\n|\Z)", body,
                       re.M | re.S)
    if not found:
        raise Invalid(f"{where}: 'See it run' lists no '- [`demos/<name>/`](demos/<name>/): ...'")
    return {name: " ".join(text.split()) for name, text in found}


@dataclass(frozen=True)
class Lead:
    """A front door's lead: its demo's picture and the exchange under it."""

    demo: str
    alt: str
    rows: tuple[tuple[str, str], ...]


LEAD_ROWS = ("You ask", "Your client calls", "SCRY answers")


def lead(md: str, where: str) -> Lead:
    m = re.search(rf"<!-- demo-lead:begin ({NAME}) -->\n(.*?)<!-- demo-lead:end \1 -->", md, re.S)
    if not m:
        raise Invalid(f"{where}: no '<!-- demo-lead:begin <demo> -->' ... 'end' block")
    demo, body = m[1], m[2]
    alt = re.search(rf'<img src="demos/{demo}/loop\.webp" alt="([^"]*)"', body)
    rows = tuple(re.findall(r'<tr><th align="left">([^<]+)</th><td>(.*?)</td></tr>', body))
    if not alt or tuple(r[0] for r in rows[:3]) != LEAD_ROWS:
        raise Invalid(f"{where}: the lead of {demo} does not show its loop.webp and the rows "
                      f"{', '.join(LEAD_ROWS)}")
    return Lead(demo, html.unescape(alt[1]), rows[:3])


@dataclass(frozen=True)
class Motion:
    """A demo guide's moving picture: its alt text, its moments and how long each lasts."""

    alt: str
    moments: tuple[str, ...]
    ms: tuple[int, ...]


def motion(md: str, where: str) -> Motion:
    body = marked(md, "demo-motion", "", where)
    alt = re.search(r'<img src="loop\.webp" alt="([^"]*)"', body)
    ms = re.search(r"<!-- moments-ms: (\d+(?:,\d+)*) -->", body)
    moments = re.findall(r"^\d+\. (.+(?:\n(?!\d+\. |\n|<!--).+)*)", body, re.M)
    if not alt or not ms:
        raise Invalid(f"{where}: the motion block has no '<img src=\"loop.webp\" alt=...>' or no "
                      "'<!-- moments-ms: ... -->'")
    rest = re.sub(r"^<p[^>]*><picture>.*?</picture></p>$", "", body, flags=re.M | re.S)
    rest = re.sub(r"^\d+\. .+(?:\n(?!\d+\. |\n|<!--).+)*", "", rest, flags=re.M)
    if rest.replace(ms[0], "").strip():
        raise Invalid(f"{where}: the motion block holds more than its picture, its moments and "
                      "their times, and the page shows only those")
    durations = tuple(int(x) for x in ms[1].split(","))
    if len(durations) != len(moments):
        raise Invalid(f"{where}: the motion block names {len(moments)} moments and times "
                      f"{len(durations)}")
    return Motion(html.unescape(alt[1]), tuple(" ".join(t.split()) for t in moments), durations)


def roster(reference_md: str, where: str) -> list[tuple[str, str, str]]:
    """The families, `(page name, label, sentence)`, in the order of REFERENCE.md's generated
    index."""
    body = marked(reference_md, "scry-reference", "index", where)
    found = re.findall(rf"^- \[([^\]]+)\]\(docs/reference/({NAME})\.md\): (.+?) \[`", body, re.M)
    if not found:
        raise Invalid(f"{where}: the generated index links no 'docs/reference/<family>.md'")
    return [(name, label, about) for label, name, about in found]


def demo_order(readme: str, names: list[str]) -> list[str]:
    """The demos in the order the front door first links them; unlinked ones last."""
    def first(n: str) -> int:
        i = readme.find(f"demos/{n}/")
        return i if i >= 0 else len(readme)
    return sorted(names, key=lambda n: (first(n), n))


def collect(rs: list[Repo]) -> tuple[list[Page], list[Family], dict[str, set[str]]]:
    """Every page made from a whole source, every family of the reference, and every
    repository's tracked files."""
    pages: list[Page] = []
    families: list[Family] = []
    files = {r.key: set(tracked(r)) for r in rs}
    for r in rs:
        own = files[r.key]
        if r.key == "core":
            pages.append(Page(r, "README.md", "core/index.html", "core", read(r, "README.md")))
            docs = sorted(f for f in own if re.fullmatch(rf"docs/{NAME}\.md", f))
            pages += [Page(r, f, f"core/{f.removesuffix('.md')}.html", "core", read(r, f),
                           order=i) for i, f in enumerate(docs, 1)]
            continue
        readme = read(r, "README.md")
        reference = read(r, "REFERENCE.md")
        pages.append(Page(r, "README.md", f"{r.key}/index.html", "overview", readme))
        pages.append(Page(r, "REFERENCE.md", f"{r.key}/reference/index.html", "reference",
                          reference, label="All families"))
        listed = roster(reference, f"{r.name}/REFERENCE.md")
        for i, (fam, fam_label, about) in enumerate(listed, 1):
            src = f"docs/reference/{fam}.md"
            if fam == "index":
                raise Invalid(f"{r.name}: a family named 'index' would replace the reference index")
            if src not in own:
                raise Invalid(f"{r.name}: the index names {src}, which is not tracked")
            page = Page(r, src, f"{r.key}/reference/{fam}/index.html", "reference",
                        read(r, src), label=fam_label, order=i)
            pages.append(page)
            tools = [m[1] for m in ENTRY.finditer(page.markdown)]
            if not tools:
                raise Invalid(f"{r.name}/{src}: no '<!-- scry-reference:begin <tool> -->' entry")
            families.append(Family(page, about, tools))
        names = {f for f, _, _ in listed}
        unlisted = sorted(f for f in own if re.fullmatch(rf"docs/reference/{NAME}\.md", f)
                          and f.removeprefix("docs/reference/").removesuffix(".md") not in names)
        if unlisted:
            raise Invalid(f"{r.name}: reference pages the generated index does not list: "
                          f"{unlisted}")
        demos = [m[1] for f in own if (m := re.fullmatch(rf"demos/({NAME})/README\.md", f))]
        odd = sorted(f for f in own if re.fullmatch(r"demos/[^/]+/README\.md", f)
                     and not re.fullmatch(rf"demos/{NAME}/README\.md", f))
        if odd:
            raise Invalid(f"{r.name}: demo directories named outside [a-z0-9_-]: {odd}")
        for i, d in enumerate(demo_order(readme, demos)):
            src = f"demos/{d}/README.md"
            pages.append(Page(r, src, f"{r.key}/demos/{d}/index.html", "demos", read(r, src),
                              order=i))
        if "CONTRIBUTING.md" in own:
            pages.append(Page(r, "CONTRIBUTING.md", f"{r.key}/contributing.html", "contributing",
                              read(r, "CONTRIBUTING.md"), label="Contributing"))
    for p in pages:
        p.title = title_of(p.markdown, f"{p.repo.name}/{p.src}")
        p.label = p.label or p.title.split(":")[0]
    return pages, families, files
