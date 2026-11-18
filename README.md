# scry-mcp.github.io

This repository builds the SCRY site from the SCRY repositories' own documents. The site has a
home, one page per tool of each server, one page per demo with its clip moving, and every other
public document. Every word about a server is read out of that server's repository at build
time, so a rebuilt site says what the repositories say.

The site's own words are few:

- `scry_site/templates/landing.html`: the home's hero, section headings and leads.
- `scry_site/home.py`: the hero's two moments, the labels of the request under the picture,
  and the install steps' titles.
- `scry_site/build.py`: the page titles, the home's description and the reference page's lead.
- `scry_site/templates/page.html`: the navigation and the foot.

## Build it

You need git, [uv](https://docs.astral.sh/uv/), and one directory holding checkouts of
[scry-core](https://github.com/scry-mcp/scry-core),
[scry-mame](https://github.com/scry-mcp/scry-mame) and
[scry-dosbox-x](https://github.com/scry-mcp/scry-dosbox-x) under those names. With this
repository cloned beside them:

```sh
uv run scry-site ../ --out _site
python3 -m http.server --directory _site 8000
```

The first line prints one line of JSON: the pages written, the files copied, and the links
inside the site it followed. The second serves the site at `http://localhost:8000`.

## What a build refuses

A build renders into a directory beside `--out` and puts it in place only once every check
passes. Otherwise it leaves `--out` as it was, prints `INVALID:` with the reason, and exits 3.

It stops at the first source that is not in the shape the site reads. In a server's `README.md`:

- no `<h1>`, or no bold opening sentence;
- an `## Install` that does not open with a sentence and a `sh` block;
- no install block (`<!-- scry-install:begin -->`), a client in it without its sentence and
  one fenced block, or two READMEs listing different clients;
- a `### Your first question` without exactly one quoted prompt;
- a `## What you can ask` item that is not a bold question, its tools and a sentence, or that
  names a tool with no entry in the reference;
- a `## See it run` that does not list each demo;
- in scry-dosbox-x's, no `demo-lead` block with its picture and the rows "You ask", "Your
  client calls" and "SCRY answers".

In the reference:

- `REFERENCE.md` without its generated index, an index entry naming a page that is not tracked
  or is named `index`, or a page in `docs/reference/` the index does not list;
- a tool's entry that does not open with its name, one sentence and its signature;
- an entry whose sections are not Try it, an optional table of modes, Arguments, What comes
  back, What it refuses, Why it works this way and Related tools, in that order;
- one tool with two entries.

In a demo's `README.md`:

- no motion block, or one whose moments disagree with their times or with the frames of
  `loop.webp`;
- a `loop.webp` that is not an animated WebP, or a `loop.webp` or `screen.png` not tracked;
- no single transcript block of numbered steps;
- a demo folder named outside lowercase letters, digits, `_` and `-`.

An example, on a tool's page or a demo's, must be the request, its quote, one or two calls each
with its reply, a sentence reading the reply, and the whole reply folded. A build also stops
on a page without a title, on scry-core's `## Credits` not being the one credits line, and on
an `--out` that names a file, the directory of the checkouts, or a place inside one.

It lists every one of these:

- a link in any source to a path its repository does not track, named by file and link;
- a link inside the built site to a page it does not hold, or to a heading that page does not
  carry, named by the built page.

## What the pages are made of

- `scry_site/sources.py` reads the sources and each part of a README the home takes.
- `scry_site/reference.py` cuts each family's page into one page per tool and the family's own
  page. A link to a tool's heading goes to that tool's page.
- `scry_site/example.py` draws every example in one shape and every code block in a framed box.
- `scry_site/motion.py` reads a demo's `loop.webp`: its size, which sets the screen frame it
  plays in, and its frame times, which light each moment while it plays.
- `scry_site/home.py` and `scry_site/demos.py` fill the home and each demo's page.
- `scry_site/render.py` renders markdown with GitHub's heading anchors, and points each
  relative link at its page here, at a copy of the file, or at the file on GitHub.
- `scry_site/check.py` follows every link inside the built site.
- `scry_site/build.py` puts it together. It also writes a markdown copy of every page made from
  a whole document, and `llms.txt`, which lists those copies.
- `scry_site/templates/` and `scry_site/static/` are the layout and the look. The fonts are
  served with the site under the SIL Open Font License (`scry_site/static/fonts/`).

## Checks

```sh
uv run ruff check .
uv run mypy --strict .
uv run pytest -q
```

Most tests build sites from small git repositories they create. `tests/test_real.py` builds
the site from the real checkouts and checks it against the design rules:

- every text's contrast, computed from `site.css`;
- the number of words on the home above its install block;
- in a headless Chrome, at 390 and 1440 px: no page scrolls sideways, no code block is wider
  than its box, and no text is under 13 px.

It finds the checkouts in `SCRY_SITE_CHECKOUTS`, else in `repos/`, else in the directory this
repository sits in. It finds Chrome in `SCRY_SITE_CHROME`, else on the `PATH`, else where macOS
installs it. Without either, it fails.

## Publishing

`.github/workflows/pages.yml` runs the checks, builds from the three repositories' `main` and
deploys to GitHub Pages, on a push here or a run started by hand. It clones them with the
workflow's own token, which reaches public repositories only.

## Licence

MIT. See `LICENSE`. The fonts keep their own licence, beside them.

## Credits

Developed by Optimiza ([Marcos Hernández](https://www.linkedin.com/in/optimiza/)), in collaboration with [MS-DOS Club](https://msdos.club) and its [podcast](https://www.ivoox.com/podcast-ms-dos-club_sq_f11160693_1.html).
