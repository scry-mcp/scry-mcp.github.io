from __future__ import annotations

import os
from pathlib import Path

import pytest

from scry_site import build

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("scry-core", "scry-mame", "scry-dosbox-x")


def checkouts() -> Path:
    """The directory holding the three checkouts: `SCRY_SITE_CHECKOUTS`, else `repos/` (where the
    publishing workflow clones them), else the one this repository sits in."""
    named = os.environ.get("SCRY_SITE_CHECKOUTS")
    for base in ([Path(named)] if named else [ROOT / "repos", ROOT.parent]):
        if all((base / n / "README.md").is_file() for n in NAMES):
            return base
    where = named or f"{ROOT / 'repos'} or {ROOT.parent}"
    raise pytest.fail.Exception(f"no checkouts of {', '.join(NAMES)} at {where}: set "
                                "SCRY_SITE_CHECKOUTS to the directory that holds them")


@pytest.fixture(scope="session")
def real_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The site built once from the real checkouts."""
    out = tmp_path_factory.mktemp("real") / "site"
    build.build(checkouts(), out)
    return out
