---
paths:
  - "README.md"
  - "scry_site/templates/**"
  - "scry_site/build.py"
---

> **This is the public-face profile of this repository.** It loads when one of the public
> documents below is opened, and it says who each layer is written for and in what character. It
> is reference, not a task list.

## The layers of the public face

| layer | files or globs | audience | character | language |
|---|---|---|---|---|
| landing | `scry_site/templates/landing.html` | a stranger arriving at the site, deciding in a minute whether SCRY is worth installing | captivate: one sentence on what it does, two servers side by side with what they need and their install lines, the demos. Written here: the hero, the section headings, the link labels and the page's title and description (`scry_site/build.py`), and the site's navigation (`templates/page.html`); every word about a server is read out of its own README | English |
| repository front door | `README.md` | somebody changing the site: how it is built, what a build refuses, how it is published | practical and short: the commands, what each proves | English |

## What is public and what is not

- Public: the two layers above, and the built site, whose pages are the SCRY repositories' own
  documents under their own profiles.
- Not public: `.claude/`.

## Generated documents

Every page of the built site, and every word about a server on the landing, is generated from scry-core, scry-mame and
scry-dosbox-x. A finding about a generated page is a finding about the repository it came from,
fixed there.

## Limits

- Language: English. This line is the declaration.
- The README closes with the credits line, verbatim, its links resolving; every page's footer
  renders the same line, read out of scry-core's README:

  `Developed by Optimiza ([Marcos Hernández](https://www.linkedin.com/in/optimiza/)), in collaboration with [MS-DOS Club](https://msdos.club) and its [podcast](https://www.ivoox.com/podcast-ms-dos-club_sq_f11160693_1.html).`
- Nothing else is exempt: a dated measurement, a note on the project's own history, a
  home-directory path or an assistant's name in a tracked file outside `.claude/` is a finding.
