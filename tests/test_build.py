from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scry_site import build
from scry_site.check import check
from scry_site.sources import Invalid

CREDITS = "Developed by Optimiza ([the author](https://example.org/a)), with [friends](https://example.org/b)."

SERVER_README = """# scry-{key}

**Drive {label} from your MCP client, live.** More words.

## What it can do

- Things, shown in [the demo](demos/{demo}/).

## Two minutes to a first answer

You need git and a {label} with its debugger. More, said later.

```sh
git clone https://github.com/scry-mcp/scry-{key}
```

## Platforms

macOS and Windows. Each, said in [Session](REFERENCE.md#the-session).

## See it run

<!-- demo-flow:begin {demo} -->
```
start()
-> {{"summary": "start: ok"}}
```

```
symbols_load(path="game.sym")
-> {{"summary": "symbols_load: 3 loaded"}}
```

```
breakpoint_at(ref="hit")
-> {{"summary": "armed"}}
```

```
resume(seconds=60)
-> {{"summary": "resume: stopped at hit"}}
```
<!-- demo-flow:end {demo} -->

## Credits

{credits}
"""

REFERENCE = """# scry-{key}: reference

## Index

<!-- scry-reference:begin index -->
- [Session](docs/reference/session.md): [`start`](docs/reference/session.md#start)
- [Read](docs/reference/read.md): [`registers`](docs/reference/read.md#registers)
<!-- scry-reference:end index -->

## The session

The [front door](README.md) and the [licence](LICENSE).
"""


def git_repo(root: Path, files: dict[str, str | bytes]) -> None:
    root.mkdir(parents=True)
    for rel, body in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            f.write_bytes(body)
        else:
            f.write_text(body, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)


def server(key: str, label: str, demo: str) -> dict[str, str | bytes]:
    return {
        "README.md": SERVER_README.format(key=key, label=label, demo=demo, credits=CREDITS),
        "REFERENCE.md": REFERENCE.format(key=key),
        "LICENSE": "MIT\n",
        "CONTRIBUTING.md": "# Contributing\n\nRun the battery.\n",
        "docs/reference/session.md": "# The Session tools\n\n## `start`\n\nStarts.\n",
        "docs/reference/read.md":
            "# The Read tools\n\n## `registers`\n\nSee [start](session.md#start).\n",
        f"demos/{demo}/README.md": f"# {demo.title()}: a demo\n\n![screen](screen.png)\n",
        f"demos/{demo}/screen.png": b"\x89PNG\r\n",
    }


@pytest.fixture()
def repos(tmp_path: Path) -> Path:
    base = tmp_path / "repos"
    git_repo(base / "scry-mame", server("mame", "MAME", "gridlee"))
    git_repo(base / "scry-dosbox-x", server("dosbox-x", "DOSBox-X", "bricks"))
    git_repo(base / "scry-core", {
        "README.md": f"# scry-core\n\nShared.\n\n## Credits\n\n{CREDITS}\n"})
    return base


def test_builds_every_page_and_lands_every_link(repos: Path, tmp_path: Path) -> None:
    report = build.build(repos, tmp_path / "site")
    site = tmp_path / "site"
    assert report["pages"] == 16
    assert report["links"] > 0
    landing = (site / "index.html").read_text()
    assert "Drive DOSBox-X from your MCP client, live." in landing
    assert "git clone https://github.com/scry-mcp/scry-mame" in landing
    assert "symbols_load(path=" in landing and "resume(seconds=60)" in landing
    assert "start()" not in landing
    assert "You need git and a MAME with its debugger. Runs on macOS and Windows." in landing
    read = (site / "mame/reference/read.html").read_text()
    assert 'href="session.html#start"' in read
    assert 'href="https://example.org/a"' in read
    assert (site / "dosbox-x/demos/bricks/screen.png").read_bytes() == b"\x89PNG\r\n"
    assert (site / "fonts/vt323.woff2").is_file()
    assert (site / ".nojekyll").is_file()


def test_a_link_outside_the_site_goes_to_the_repository(repos: Path, tmp_path: Path) -> None:
    build.build(repos, tmp_path / "site")
    ref = (tmp_path / "site/mame/reference/index.html").read_text()
    assert 'href="https://github.com/scry-mcp/scry-mame/blob/main/LICENSE"' in ref
    assert 'href="../index.html"' in ref


def test_the_sidebar_follows_the_reference_index(repos: Path, tmp_path: Path) -> None:
    build.build(repos, tmp_path / "site")
    page = (tmp_path / "site/mame/index.html").read_text()
    assert page.index(">Session<") < page.index(">Read<")


def test_a_link_to_an_untracked_path_is_invalid(repos: Path, tmp_path: Path) -> None:
    readme = repos / "scry-mame/docs/reference/read.md"
    readme.write_text(readme.read_text() + "\nSee [gone](../../nowhere.md).\n")
    with pytest.raises(Invalid, match=r"scry-mame/docs/reference/read.md: \.\./\.\./nowhere.md"):
        build.build(repos, tmp_path / "site")
    assert not (tmp_path / "site").exists()


def test_a_reference_page_the_index_misses_is_invalid(repos: Path, tmp_path: Path) -> None:
    extra = repos / "scry-dosbox-x/docs/reference/extra.md"
    extra.write_text("# Extra\n")
    subprocess.run(["git", "-C", str(repos / "scry-dosbox-x"), "add", "-A"], check=True)
    with pytest.raises(Invalid, match="does not list: \\['docs/reference/extra.md'\\]"):
        build.build(repos, tmp_path / "site")


def test_an_index_naming_an_untracked_page_is_invalid(repos: Path, tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(repos / "scry-mame"), "rm", "-q", "--cached",
                    "docs/reference/read.md"], check=True)
    with pytest.raises(Invalid, match="names docs/reference/read.md, which is not tracked"):
        build.build(repos, tmp_path / "site")


@pytest.mark.parametrize(("path", "old", "new", "message"), [
    ("scry-mame/README.md", "## Two minutes to a first answer", "## Quick start",
     "no section '## Two minutes to a first answer'"),
    ("scry-mame/README.md", "**Drive", "Drive", "no bold opening sentence"),
    ("scry-mame/README.md", "```sh", "```bash", "hold a ```sh block"),
    ("scry-mame/README.md", "macOS and Windows.", "", "does not open with the hosts"),
    ("scry-dosbox-x/README.md", "symbols_load(path", "load(path",
     "no 3 calls from 'symbols_load\\('"),
    ("scry-dosbox-x/README.md", "demo-flow:begin bricks", "demo-flow:begin other",
     "no '<!-- demo-flow:begin bricks -->'"),
    ("scry-mame/REFERENCE.md", "scry-reference:begin index", "index",
     "no '<!-- scry-reference:begin index -->'"),
    ("scry-mame/CONTRIBUTING.md", "# Contributing", "Contributing", "no level-one heading"),
    ("scry-core/README.md", "## Credits", "## Thanks", "no section '## Credits'"),
    ("scry-core/README.md", "Developed by", "Made by", "must hold one line"),
])
def test_a_source_the_site_reads_from_is_required(repos: Path, tmp_path: Path, path: str,
                                                  old: str, new: str, message: str) -> None:
    f = repos / path
    text = f.read_text()
    assert old in text
    f.write_text(text.replace(old, new, 1))
    with pytest.raises(Invalid, match=message.replace("*", r"\*")):
        build.build(repos, tmp_path / "site")


def test_a_missing_checkout_is_invalid(repos: Path, tmp_path: Path) -> None:
    (repos / "scry-core/README.md").unlink()
    with pytest.raises(Invalid, match="no scry-core checkout"):
        build.build(repos, tmp_path / "site")


def test_check_names_a_missing_file_and_a_missing_id(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text('<h2 id="here">x</h2><a href="#here">ok</a>'
                                     '<a href="b.html#gone">x</a><img src="pic.png">'
                                     '<a href="https://example.org/">out</a>')
    (tmp_path / "b.html").write_text('<p id="there">y</p>')
    with pytest.raises(Invalid) as e:
        check(tmp_path)
    assert "a.html: b.html#gone (no id 'gone')" in str(e.value)
    assert "a.html: pic.png (no file)" in str(e.value)


def test_check_examining_nothing_is_invalid(tmp_path: Path) -> None:
    with pytest.raises(Invalid, match="no page"):
        check(tmp_path)
    (tmp_path / "a.html").write_text('<a href="https://example.org/">out</a>')
    with pytest.raises(Invalid, match="no internal link examined"):
        check(tmp_path)


def test_main_reports_and_exits(repos: Path, tmp_path: Path,
                                capsys: pytest.CaptureFixture[str]) -> None:
    assert build.main([str(repos), "--out", str(tmp_path / "site")]) == 0
    assert json.loads(capsys.readouterr().out)["pages"] == 16
    assert build.main([str(tmp_path / "none"), "--out", str(tmp_path / "x")]) == 3
    assert capsys.readouterr().err.startswith("INVALID: no scry-mame checkout")


def track(repo: Path, rel: str, body: str | bytes) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        f.write_bytes(body)
    else:
        f.write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)


def append(f: Path, text: str) -> None:
    f.write_text(f.read_text() + text)


@pytest.mark.parametrize("breaks", ["landing", "check"])
def test_a_failed_build_leaves_the_previous_site(repos: Path, tmp_path: Path,
                                                 breaks: str) -> None:
    site = tmp_path / "site"
    build.build(repos, site)
    (site / "marker").write_text("previous")
    if breaks == "landing":
        f = repos / "scry-dosbox-x/README.md"
        f.write_text(f.read_text().replace("demo-flow:begin bricks", "demo-flow:begin x"))
    else:
        append(repos / "scry-mame/docs/reference/read.md", "\n[gone](session.md#nowhere)\n")
    with pytest.raises(Invalid):
        build.build(repos, site)
    assert (site / "marker").read_text() == "previous"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["repos", "site"]


@pytest.mark.parametrize("where", [".", "repos", "repos/scry-mame", "file"])
def test_out_never_replaces_the_sources_or_a_file(repos: Path, tmp_path: Path,
                                                  where: str) -> None:
    out = tmp_path / where
    if where == "file":
        out.write_text("x")
    with pytest.raises(Invalid, match="--out"):
        build.build(repos, out)
    assert (repos / "scry-mame/README.md").is_file()


@pytest.mark.parametrize(("setup", "message"), [
    ("not_git", "not a git checkout"),
    ("deleted", "cannot read scry-mame/CONTRIBUTING.md"),
    ("no_reference", "cannot read scry-mame/REFERENCE.md"),
])
def test_an_unreadable_source_is_invalid(repos: Path, tmp_path: Path, setup: str,
                                         message: str) -> None:
    mame = repos / "scry-mame"
    if setup == "not_git":
        subprocess.run(["rm", "-rf", str(mame / ".git")], check=True)
    elif setup == "deleted":
        (mame / "CONTRIBUTING.md").unlink()
    else:
        (mame / "REFERENCE.md").unlink()
    with pytest.raises(Invalid, match=message):
        build.build(repos, tmp_path / "site")


def test_names_with_digits_and_hyphens_are_pages(repos: Path, tmp_path: Path) -> None:
    dx = repos / "scry-dosbox-x"
    track(dx, "demos/speed-fight/README.md", "# Speed Fight: a demo\n\n![s](screen.png)\n")
    track(dx, "demos/speed-fight/screen.png", b"png")
    ref = dx / "REFERENCE.md"
    ref.write_text(ref.read_text().replace(
        "<!-- scry-reference:end index -->",
        "- [Gfx2](docs/reference/gfx-2.md): [`g`](docs/reference/gfx-2.md#g)\n"
        "<!-- scry-reference:end index -->"))
    track(dx, "docs/reference/gfx-2.md", "# The Gfx2 tools\n\n## `g`\n")
    build.build(repos, tmp_path / "site")
    assert (tmp_path / "site/dosbox-x/demos/speed-fight/index.html").is_file()
    page = (tmp_path / "site/dosbox-x/reference/gfx-2.html").read_text()
    assert ">Gfx2<" in page


def test_a_family_named_index_is_invalid(repos: Path, tmp_path: Path) -> None:
    dx = repos / "scry-dosbox-x"
    ref = dx / "REFERENCE.md"
    ref.write_text(ref.read_text().replace(
        "<!-- scry-reference:end index -->",
        "- [Index](docs/reference/index.md): [`i`](docs/reference/index.md#i)\n"
        "<!-- scry-reference:end index -->"))
    track(dx, "docs/reference/index.md", "# Index\n")
    with pytest.raises(Invalid, match="'index'"):
        build.build(repos, tmp_path / "site")


def test_links_land_on_the_page_the_repository_means(repos: Path, tmp_path: Path) -> None:
    mame = repos / "scry-mame"
    track(mame, "docs/diagram.svg", "<svg/>")
    append(mame / "docs/reference/read.md",
           "\n[home](../..) [top](../../#scry-mame) [demo](../../demos/gridlee/) "
           "[spaced](session.md#start) ![d](../diagram.svg) [up](HTTPS://example.org/)\n")
    build.build(repos, tmp_path / "site")
    site = tmp_path / "site"
    read = (site / "mame/reference/read.html").read_text()
    assert 'href="../index.html"' in read
    assert 'href="../index.html#scry-mame"' in read
    assert 'href="../demos/gridlee/index.html"' in read
    assert 'src="../docs/diagram.svg"' in read
    assert (site / "mame/docs/diagram.svg").read_text() == "<svg/>"
    assert 'href="HTTPS://example.org/"' in read
    assert 'src="screen.png"' in (site / "mame/demos/gridlee/index.html").read_text()


def test_getting_started_sends_a_fragment_to_the_server_page(repos: Path,
                                                             tmp_path: Path) -> None:
    f = repos / "scry-mame/README.md"
    f.write_text(f.read_text().replace("macOS and Windows.",
                                       "macOS and Windows. See [it](#see-it-run)."))
    build.build(repos, tmp_path / "site")
    page = (tmp_path / "site/mame/getting-started.html").read_text()
    assert 'href="index.html#see-it-run"' in page


def test_a_template_key_inside_a_page_is_left_alone(repos: Path, tmp_path: Path) -> None:
    append(repos / "scry-mame/docs/reference/read.md", "\nLiteral `{{credits}}` and {{main}}.\n")
    build.build(repos, tmp_path / "site")
    read = (tmp_path / "site/mame/reference/read.html").read_text()
    assert "<code>{{credits}}</code> and {{main}}." in read


def test_check_refuses_a_link_out_of_the_site(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text("<a href='../outside.html'>x</a><a href=\"/etc/hosts\">y</a>")
    (tmp_path.parent / "outside.html").write_text("")
    with pytest.raises(Invalid) as e:
        check(tmp_path)
    assert "a.html: ../outside.html (outside the site)" in str(e.value)
    assert "a.html: /etc/hosts (outside the site)" in str(e.value)
