"""Which markdown of the three repositories becomes which page, and what the landing takes."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

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


SERVERS = (("mame", "scry-mame", "MAME"), ("dosbox-x", "scry-dosbox-x", "DOSBox-X"))
GROUPS = (("overview", "Overview"), ("demos", "Demos"), ("reference", "Reference"),
          ("contributing", "Contributing"))


def repos(base: Path) -> list[Repo]:
    found = [Repo(k, n, label, base / n) for k, n, label in SERVERS]
    found.append(Repo("core", "scry-core", "Core", base / "scry-core"))
    for r in found:
        if not (r.root / "README.md").is_file():
            raise Invalid(f"no {r.name} checkout at {r.root}")
    return found


def tracked(repo: Repo) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(repo.root), "ls-files", "-z"], check=True,
                             capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise Invalid(f"{repo.root} is not a git checkout git can list: {e}") from e
    return [f for f in out.split("\0") if f]


def read(repo: Repo, src: str) -> str:
    try:
        return (repo.root / src).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Invalid(f"cannot read {repo.name}/{src}: {e}") from e


def title_of(md: str, where: str) -> str:
    m = re.search(r"^# (.+)$", md, re.M)
    if not m:
        raise Invalid(f"{where}: no level-one heading ('# ...') to title the page")
    return m[1].replace("`", "").strip()


def section(md: str, heading: str, where: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    if not m:
        raise Invalid(f"{where}: no section '## {heading}'")
    return m[1]


def lede(md: str, where: str) -> str:
    m = re.search(r"^\*\*(.+?)\*\*", md, re.M | re.S)
    if not m:
        raise Invalid(f"{where}: no bold opening sentence ('**...**' at the start of a line)")
    return " ".join(m[1].split())


def install(md: str, where: str) -> tuple[str, str]:
    """The sentence that says what a first run needs, and the ```sh block that installs."""
    body = section(md, "Two minutes to a first answer", where)
    m = re.search(r"\A\s*(.+?\.)(?=\s|$).*?```sh\n(.*?)```", body, re.S)
    if not m:
        raise Invalid(f"{where}: 'Two minutes to a first answer' does not open with a sentence "
                      "and hold a ```sh block")
    return " ".join(m[1].split()), m[2].strip()


def platforms(md: str, where: str) -> str:
    """The hosts the server runs on: the first clause of its 'Platforms' section."""
    m = re.match(r"\s*([^.:\n\[\]`]+)[.:]", section(md, "Platforms", where))
    if not m:
        raise Invalid(f"{where}: 'Platforms' does not open with the hosts it runs on")
    return m[1]


def flow(md: str, name: str, first_call: str, calls: int, where: str) -> str:
    """`calls` consecutive call blocks of a demo flow, from the first that calls `first_call`."""
    m = re.search(rf"<!-- demo-flow:begin {name} -->\n(.*?)<!-- demo-flow:end {name} -->", md,
                  re.S)
    if not m:
        raise Invalid(f"{where}: no '<!-- demo-flow:begin {name} -->' ... 'end' block")
    blocks = re.findall(r"^```\n(.*?)^```", m[1], re.M | re.S)
    starts = [i for i, b in enumerate(blocks) if b.startswith(f"{first_call}(")]
    if not starts or starts[0] + calls > len(blocks):
        raise Invalid(f"{where}: the {name} flow has no {calls} calls from '{first_call}('")
    return "\n".join(blocks[starts[0]:starts[0] + calls])


def roster(reference_md: str, where: str) -> list[tuple[str, str]]:
    """The families, `(page name, label)`, in the order of REFERENCE.md's generated index."""
    m = re.search(r"<!-- scry-reference:begin index -->(.*?)<!-- scry-reference:end index -->",
                  reference_md, re.S)
    if not m:
        raise Invalid(f"{where}: no '<!-- scry-reference:begin index -->' ... 'end' block")
    found = re.findall(rf"^- \[([^\]]+)\]\(docs/reference/({NAME})\.md\)", m[1], re.M)
    if not found:
        raise Invalid(f"{where}: the generated index links no 'docs/reference/<family>.md'")
    return [(name, label) for label, name in found]


def demo_order(readme: str, names: list[str]) -> list[str]:
    """The demos in the order the front door first links them; unlinked ones last."""
    def first(n: str) -> int:
        i = readme.find(f"demos/{n}/")
        return i if i >= 0 else len(readme)
    return sorted(names, key=lambda n: (first(n), n))


def collect(rs: list[Repo]) -> tuple[list[Page], dict[str, set[str]]]:
    """Every page, and every repository's tracked files."""
    pages: list[Page] = []
    files = {r.key: set(tracked(r)) for r in rs}
    for r in rs:
        if r.key == "core":
            pages.append(Page(r, "README.md", "core/index.html", "core", read(r, "README.md"),
                              label="Core"))
            continue
        own = files[r.key]
        readme = read(r, "README.md")
        reference = read(r, "REFERENCE.md")
        pages.append(Page(r, "README.md", f"{r.key}/index.html", "overview", readme,
                          label="The server"))
        pages.append(Page(r, "REFERENCE.md", f"{r.key}/reference/index.html", "reference",
                          reference, label="Reference index"))
        families = roster(reference, f"{r.name}/REFERENCE.md")
        for i, (fam, fam_label) in enumerate(families, 1):
            src = f"docs/reference/{fam}.md"
            if fam == "index":
                raise Invalid(f"{r.name}: a family named 'index' would replace the reference index")
            if src not in own:
                raise Invalid(f"{r.name}: the index names {src}, which is not tracked")
            pages.append(Page(r, src, f"{r.key}/reference/{fam}.html", "reference",
                              read(r, src), label=fam_label, order=i))
        listed = {f for f, _ in families}
        unlisted = sorted(f for f in own if f.startswith("docs/reference/") and f.endswith(".md")
                          and f.removeprefix("docs/reference/").removesuffix(".md") not in listed)
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
    return pages, files
