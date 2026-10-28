# scry-mcp.github.io

The Scry site, built from the Scry repositories' own markdown: each server's front door, its
getting started, its reference and its demos, and scry-core's README. This repository holds the
layout, the landing page's opening lines and the build. Every other word the site shows about a
server is read out of that server's repository at build time, so a rebuilt site says what the
repositories say.

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

The first line prints one line of JSON (the pages written, the files copied, the links inside
the site it followed); the second serves the site at `http://localhost:8000`.

## What a build refuses

A build renders into a directory beside `--out` and puts it in place only once every check
passes. Otherwise it leaves `--out` as it was, prints `INVALID:` with the reason, and exits 3.
It stops at the first of these in the sources:

- a checkout that is missing or that git cannot list, or a file it cannot read;
- in a server's `README.md`: no bold opening sentence, no `## Two minutes to a first answer`
  opening with a sentence and holding a `sh` block, no `## Platforms` opening with the hosts it
  runs on, or no `<!-- demo-flow:begin bricks -->` block with the calls the landing shows;
- in a server's `REFERENCE.md`: no generated index, an index entry naming a page that is not
  tracked or named `index`, or a page under `docs/reference/` the index does not list;
- a demo directory named outside lowercase letters, digits, `_` and `-`, or one without its
  `screen.png`;
- a page without a `# ` title, or scry-core's `## Credits` not being the one credits line;
- `--out` naming a file, the directory that holds the checkouts, or a place inside one.

And it lists every one of these:

- a link in any source to a path its repository does not track, named by file and link;
- a link inside the built site to a page it does not hold or a heading that page does not carry,
  named by the built page (whose source is the same path in the repository it belongs to).

## What the pages are made of

- `scry_site/sources.py` reads the sources: which tracked markdown becomes which page, the
  reference families in the order the server's generated index lists them, the demos in the
  order its front door links them, and what the landing lifts from each front door.
- `scry_site/render.py` renders them (markdown-it-py, headings anchored the way GitHub anchors
  them) and points every relative link at its page here, at a copy of the picture, or at the file
  on GitHub.
- `scry_site/check.py` follows every link inside the built site.
- `scry_site/build.py` puts it together: the getting-started pages, the landing, the page list,
  and the swap into `--out`.
- `scry_site/templates/` and `scry_site/static/` are the layout and the look; the fonts are
  served with the site under the SIL Open Font License (`scry_site/static/fonts/`).

## Checks

```sh
uv run ruff check .
uv run mypy --strict .
uv run pytest -q
```

The tests build sites from small git repositories they create, so they need no checkout.

## Publishing

`.github/workflows/pages.yml` runs the checks, builds from the three repositories' `main` and
deploys to GitHub Pages, on a push here or a run started by hand. It clones them with the
workflow's own token, which reaches public repositories only.

## Licence

MIT. See `LICENSE`. The fonts keep their own licence, beside them.

## Credits

Developed by Optimiza ([Marcos Hernández](https://www.linkedin.com/in/optimiza/)), in collaboration with [MS-DOS Club](https://msdos.club) and its [podcast](https://www.ivoox.com/podcast-ms-dos-club_sq_f11160693_1.html).
