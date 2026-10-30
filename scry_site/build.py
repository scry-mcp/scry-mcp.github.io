"""Build the Scry site from checkouts of scry-core, scry-mame and scry-dosbox-x.

Prints one JSON line (pages, copied files, internal links followed) and exits 0; or writes
nothing, prints INVALID with the reason, and exits 3.
"""

from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import shutil
import sys
import tempfile
from importlib import resources
from pathlib import Path

from scry_site import render, sources
from scry_site.check import check
from scry_site.sources import (
    GROUPS,
    Invalid,
    Page,
    Repo,
    collect,
    flow,
    install,
    lede,
    platforms,
    read,
    repos,
    under_heading,
)

TAGLINE = "MCP servers that hold MAME or DOSBox-X open and answer by name."
# The landing's console: which demo, from which call, how many calls.
FLOW = ("dosbox-x", "bricks", "symbols_load", 3)
_KEY = re.compile(r"\{\{([a-z_]+)\}\}")


def template(name: str, **fill: str) -> str:
    """Fill every `{{key}}` in one pass, so a key that appears inside a value stays as text."""
    text = resources.files("scry_site").joinpath("templates", name).read_text(encoding="utf-8")
    return _KEY.sub(lambda m: fill[m[1]], text)


def fold(sh: str) -> str:
    """Break a line that hands a command to uv after its `--`, so every card's lines fit alike."""
    return re.sub(r"^(.* -- )(uv run .*)$", r"\1\\\n  \2", sh, flags=re.M)


def credits_line(core: Repo) -> str:
    """The credits line every Scry README closes with, rendered once for every page's footer."""
    body = under_heading(read(core, "README.md"), "Credits", "scry-core/README.md").strip()
    if "\n" in body or not body.startswith("Developed by Optimiza"):
        raise Invalid("scry-core/README.md: '## Credits' must hold one line, starting "
                      f"'Developed by Optimiza'; it holds: {body[:80]!r}")
    return inline(body)


def inline(md: str) -> str:
    return render.markdown(md).strip().removeprefix("<p>").removesuffix("</p>")


def describe(page: Page) -> str:
    """The page's first paragraph as one line of at most 200 characters, else its title."""
    md, hidden = page.markdown, sources.masked(page.markdown)
    for m in re.finditer(r"(?:^[^\n]*\S[^\n]*(?:\n|\Z))+", hidden, re.M):
        block = md[m.start():m.end()]
        if block[0].isalpha() or block[0] in "*`_":
            text = render.plain(block)
            if len(text) <= 200:
                return text
            return text[:200].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return page.title


def is_virtual(page: Page) -> bool:
    """A page made from part of its source (the getting-started page), which has no twin."""
    return page.out.endswith("getting-started.html")


def llms_txt(rs: list[Repo], pages: list[Page]) -> str:
    """The pages that have a markdown twin, by repository and group, as llmstxt.org lays out."""
    lines = ["# Scry", "", f"> {TAGLINE}", ""]
    order = {g: i for i, (g, _) in enumerate((*GROUPS, ("core", "")))}
    for r in rs:
        ps = sorted((p for p in pages if p.repo is r and not is_virtual(p)),
                    key=lambda p: (order[p.group], p.order))
        lines += [f"## {r.label}", ""]
        lines += [f"- [{p.title}]({twin_path(p)}): {describe(p)}" for p in ps]
        lines.append("")
    return "\n".join(lines)


def twin_path(page: Page) -> str:
    return page.out.removesuffix(".html") + ".md"


def sidebar(pages: list[Page], current: Page) -> str:
    here = posixpath.dirname(current.out)
    blocks = []
    for r in dict.fromkeys(p.repo for p in pages if p.group in dict(GROUPS)):
        groups = []
        for group, group_name in GROUPS:
            ps = sorted((p for p in pages if p.repo is r and p.group == group),
                        key=lambda p: p.order)
            links = "".join(
                f'<li><a{" class=on aria-current=page" if p is current else ""} '
                f'href="{posixpath.relpath(p.out, here)}">{html.escape(p.label)}</a></li>'
                for p in ps)
            if links:
                groups.append(f'<li class="grp"><span>{group_name}</span><ul>{links}</ul></li>')
        state = " open" if current.repo is r else ""
        blocks.append(f'<details{state}><summary>{r.label}</summary><ul>{"".join(groups)}</ul>'
                      "</details>")
    return f'<nav class="side" id="pages" aria-label="Pages">{"".join(blocks)}</nav>'


def shell(*, title: str, description: str, out: str, main: str, credits: str,
          side: str = "", right: str = "", kind: str = "doc") -> str:
    root = posixpath.relpath(".", posixpath.dirname(out)) if posixpath.dirname(out) else "."
    pages = '<a href="#pages">Pages</a>' if side else ""
    return template("page.html", title=html.escape(title), description=html.escape(description),
                    root=root, kind=kind, side=side, main=main, right=right, credits=credits,
                    pages=pages)


def getting_started(rs: list[Repo]) -> list[Page]:
    """Each server's own first steps, as its front door writes them."""
    out = []
    for r in rs:
        if r.key == "core":
            continue
        md = read(r, "README.md")
        where = f"{r.name}/README.md"
        body = f"# Getting started with {r.label}\n\n" + "".join(
            f"## {h}\n{under_heading(md, h, where)}" for h in ("Two minutes to a first answer",
                                                         "Platforms"))
        out.append(Page(r, "README.md", f"{r.key}/getting-started.html", "overview", body,
                        title=f"Getting started with {r.label}", label="Getting started",
                        order=1))
    return out


def landing(rs: list[Repo], pages: list[Page]) -> str:
    cards = []
    for r in rs:
        if r.key == "core":
            continue
        md = read(r, "README.md")
        where = f"{r.name}/README.md"
        needs, sh = install(md, where)
        cards.append(
            f'<article class="card"><h3>{r.label}</h3><p>{html.escape(lede(md, where))}</p>'
            f'<p class="needs">{inline(needs)} Runs on {html.escape(platforms(md, where))}.</p>'
            f'<pre tabindex="0"><code>{html.escape(fold(sh))}</code></pre>'
            f'<p class="go"><a href="{r.key}/getting-started.html">Getting started</a> · '
            f'<a href="{r.key}/index.html">The server</a> · '
            f'<a href="{r.key}/reference/index.html">Reference</a> · '
            f'<a href="https://github.com/scry-mcp/{r.name}">GitHub</a></p></article>')
    by_demo: dict[str, list[Page]] = {}
    for p in pages:
        if p.group == "demos":
            by_demo.setdefault(p.label, []).append(p)
    shots = []
    for label, ps in by_demo.items():
        img = posixpath.join(posixpath.dirname(ps[0].out), "screen.png")
        servers = " · ".join(f'<a href="{p.out}">{p.repo.label}</a>' for p in ps)
        shots.append(f'<div class="shot"><a href="{ps[0].out}" aria-hidden="true" tabindex="-1">'
                     f'<span class="crt"><img src="{img}" alt="" loading="lazy"></span></a>'
                     f"<b>{html.escape(label)}</b><small>{servers}</small></div>")
    key, demo, first, calls = FLOW
    server = next(r for r in rs if r.key == key)
    console = flow(read(server, "README.md"), demo, first, calls, f"{server.name}/README.md")
    return template("landing.html", flow_label=f"the {demo} demo, on {server.label}",
                    flow=html.escape(console), cards="".join(cards), demos="".join(shots))


def guard(base: Path, out: Path) -> None:
    """`out` is replaced whole, so it may not hold the sources, nor be anything but a directory."""
    if out.exists() and not out.is_dir():
        raise Invalid(f"--out {out} is not a directory")
    if out == base or out in base.parents:
        raise Invalid(f"--out {out} is or holds {base}, where the checkouts are; replacing it "
                      "would delete them")
    for r in repos(base):
        if out == r.root or r.root in out.parents:
            raise Invalid(f"--out {out} is inside the {r.name} checkout")


def render_site(rs: list[Repo], into: Path) -> dict[str, int]:
    pages, files = collect(rs)
    pages += getting_started(rs)
    links = render.Links({(p.repo.key, p.src): p.out for p in pages
                          if not p.out.endswith("getting-started.html")}, files)
    credits = credits_line(next(r for r in rs if r.key == "core"))
    rendered: dict[str, str] = {}
    twins: dict[str, str] = {}
    for p in pages:
        body = render.rewrite(render.markdown(p.markdown), p, links,
                              virtual=p.out.endswith("getting-started.html"))
        if not is_virtual(p):
            twins[twin_path(p)] = render.twin(p, links)
        rendered[p.out] = shell(title=f"{p.title} · Scry", description=describe(p),
                                out=p.out, main=body, credits=credits, side=sidebar(pages, p),
                                right=render.toc(body))
    if links.broken:
        raise Invalid("links in the sources to paths no repository tracks:\n  "
                      + "\n  ".join(sorted(links.broken)))
    rendered["index.html"] = shell(
        title="Scry: drive and debug the program inside the emulator",
        description=TAGLINE,
        out="index.html", main=landing(rs, pages), credits=credits, kind="landing")
    for rel, text in {**rendered, **twins, "llms.txt": llms_txt(rs, pages)}.items():
        dest = into / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    roots = {r.key: r.root for r in rs}
    screens = {(p.repo.key, posixpath.join(posixpath.dirname(p.src), "screen.png")):
               posixpath.join(posixpath.dirname(p.out), "screen.png")
               for p in pages if p.group == "demos"}
    for (key, src), rel in {**links.copies, **screens}.items():
        if src not in files[key]:
            raise Invalid(f"{key}: {src} is not tracked, and the landing shows every demo's "
                          "screen.png")
        (into / rel).parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(roots[key] / src, into / rel)
        except OSError as e:
            raise Invalid(f"cannot copy {key}/{src}: {e}") from e
    shutil.copytree(Path(str(resources.files("scry_site").joinpath("static"))), into,
                    dirs_exist_ok=True)
    (into / ".nojekyll").write_text("", encoding="utf-8")
    return {"pages": len(rendered), "copied": len({**links.copies, **screens}),
            "links": check(into)}


def build(base: Path, out: Path) -> dict[str, int]:
    """Render into a directory beside `out`, and put it in place only once it checks."""
    base, out = base.resolve(), out.resolve()
    rs = repos(base)
    guard(base, out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    try:
        report = render_site(rs, work)
        if out.exists():
            shutil.rmtree(out)
        work.rename(out)
    finally:
        if work.exists():
            shutil.rmtree(work)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scry-site", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkouts", type=Path,
                    help="the directory holding the scry-core, scry-mame and scry-dosbox-x "
                         "checkouts")
    ap.add_argument("--out", type=Path, default=Path("_site"),
                    help="where the site goes, replaced whole once it checks; default _site")
    args = ap.parse_args(argv)
    try:
        report = build(args.checkouts.expanduser(), args.out.expanduser())
    except Invalid as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 3
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
